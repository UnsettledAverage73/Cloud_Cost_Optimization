"""
CloudPulse GitOps, SLA Watchdog & Automated Remediation Microservice
Port: 8004
Provides production-ready Terraform/OpenTofu PR generation, closed-loop SLA watchdogs,
canary performance verification, automated 60-minute rollbacks, and GitHub App webhooks.
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, APIRouter, HTTPException, status, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

_backend_dir = Path(__file__).resolve().parent.parent
_repo_dir = _backend_dir.parent
for p in [str(_backend_dir), str(_repo_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

logger = logging.getLogger("cloudpulse.microservices.remediation")

try:
    from microservices.shared_state import (
        _db, _build_aws_session, revoked_security_groups, _persist_state
    )
    from data.finops_database import (
        record_remediation_audit, get_remediation_audit_logs,
        mark_optimization_applied
    )
    from services.remediator import AutoRemediator
    from services.gitops_engine import gitops_engine
    from services.sla_watchdog import sla_watchdog
    from services.github_app_engine import github_app_engine
    from services.notification_engine import notification_engine
    from engines.finops_analyzer import FinOpsAnalyzer
    from core.state import resolve_active_inventory
except ImportError:
    from backend.microservices.shared_state import (
        _db, _build_aws_session, revoked_security_groups, _persist_state
    )
    from backend.data.finops_database import (
        record_remediation_audit, get_remediation_audit_logs,
        mark_optimization_applied
    )
    from backend.services.remediator import AutoRemediator
    from backend.services.gitops_engine import gitops_engine
    from backend.services.sla_watchdog import sla_watchdog
    from backend.services.github_app_engine import github_app_engine
    from backend.services.notification_engine import notification_engine
    from backend.engines.finops_analyzer import FinOpsAnalyzer
    from backend.core.state import resolve_active_inventory

router = APIRouter(tags=["Remediation & GitOps Microservice"])


# =========================================================================
# 1. IMMEDIATE & SECURITY REMEDIATION
# =========================================================================

@router.post("/api/security/revoke")
async def revoke_security_group(payload: dict):
    group_id = payload.get("groupId")
    if not group_id:
        raise HTTPException(status_code=400, detail="Missing groupId")

    revoked_security_groups.add(group_id)
    _persist_state()

    db = _db()
    aws_live_revoked = False
    aws_note = "Local state updated"
    session = _build_aws_session()
    if session:
        try:
            region = session.region_name or "us-east-1"
            ec2 = session.client("ec2", region_name=region)
            resp = ec2.describe_security_groups(GroupIds=[group_id])
            sgs = resp.get("SecurityGroups", [])
            if sgs:
                to_revoke = []
                for perm in sgs[0].get("IpPermissions", []):
                    pub_ipv4 = [r for r in perm.get("IpRanges", []) if r.get("CidrIp") == "0.0.0.0/0"]
                    pub_ipv6 = [r for r in perm.get("Ipv6Ranges", []) if r.get("CidrIpv6") == "::/0"]
                    if pub_ipv4 or pub_ipv6:
                        rule = {"IpProtocol": perm.get("IpProtocol")}
                        if "FromPort" in perm:
                            rule["FromPort"] = perm["FromPort"]
                        if "ToPort" in perm:
                            rule["ToPort"] = perm["ToPort"]
                        if pub_ipv4:
                            rule["IpRanges"] = [{"CidrIp": "0.0.0.0/0"}]
                        if pub_ipv6:
                            rule["Ipv6Ranges"] = [{"CidrIpv6": "::/0"}]
                        to_revoke.append(rule)
                if to_revoke:
                    ec2.revoke_security_group_ingress(GroupId=group_id, IpPermissions=to_revoke)
                    aws_live_revoked = True
                    aws_note = f"Revoked {len(to_revoke)} ingress permission(s) on AWS EC2."
        except Exception as e:
            logger.warning(f"Could not execute live EC2 ingress revocation: {e}")
            aws_note = f"Live AWS EC2 sync skipped/denied: {e}"

    found = False
    for sg in db.get("security_groups", []):
        if sg.get("group_id") == group_id:
            sg["is_publicly_exposed"] = False
            sg["exposed_ports"] = []
            found = True

    if not found:
        db.setdefault("security_groups", []).append({
            "group_id": group_id,
            "group_name": payload.get("groupName", group_id),
            "is_publicly_exposed": False,
            "exposed_ports": []
        })

    if "summary" in db and isinstance(db["summary"], dict):
        db["summary"]["critical_security_risks"] = sum(
            1 for s in db.get("security_groups", []) if s.get("is_publicly_exposed")
        )

    return {
        "status": "revoked",
        "groupId": group_id,
        "aws_live_revoked": aws_live_revoked,
        "note": aws_note
    }


@router.post("/api/optimizations/apply")
async def apply_optimization(payload: dict):
    optimization_id = payload.get("id")
    action = payload.get("action", "apply")
    if not optimization_id:
        raise HTTPException(status_code=400, detail="Optimization id is required")
    applied = _db().setdefault("applied_optimizations", [])
    if action == "revert":
        if optimization_id in applied:
            applied.remove(optimization_id)
    elif optimization_id not in applied:
        applied.append(optimization_id)
        try:
            res_id = payload.get("resource_id") or optimization_id
            act_type = payload.get("action_type") or ("upgrade_gp3" if "storage" in str(optimization_id).lower() else "migrate_graviton")
            sla_watchdog.register_watch(
                resource_id=res_id,
                remediation_action=act_type,
                previous_config=payload.get("previous_config", {"config": "baseline"}),
                applied_config=payload.get("applied_config", {"config": "optimized"}),
                baseline_metrics={"p95_latency_ms": 35.0, "error_rate_pct": 0.0, "cpu_utilization_avg": 5.0}
            )
        except Exception as e:
            logger.debug(f"Auto-enroll SLA watch skipped: {e}")
    return {"status": "ok", "id": optimization_id, "action": action, "applied": applied}


@router.post("/api/v1/remediate/execute")
async def execute_remediation_action(payload: dict):
    action = payload.get("action")
    resource_id = payload.get("resource_id")
    dry_run = payload.get("dry_run", True)

    if not action or not resource_id:
        raise HTTPException(status_code=400, detail="action and resource_id are required")

    session = _build_aws_session()
    region = _db()["metadata"].get("region", "us-east-1")
    remediator = AutoRemediator(region=region, dry_run=dry_run, session=session)

    if action == "release_eip":
        result = remediator.release_unattached_eip(resource_id)
    elif action == "delete_volume":
        result = remediator.delete_unattached_volume(resource_id)
    elif action == "upgrade_gp3":
        result = remediator.upgrade_volume_to_gp3(resource_id)
    elif action == "stop_instance":
        result = remediator.stop_idle_instance(resource_id)
    elif action == "set_log_retention":
        days = payload.get("retention_days", 30)
        result = remediator.set_log_group_retention(resource_id, retention_days=days)
    elif action == "revoke_sg_ingress":
        port = payload.get("port", 22)
        result = remediator.revoke_security_group_ingress(resource_id, port=port)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported action: {action}")

    if not dry_run and result.get("status") == "success":
        mark_optimization_applied(f"rec-{action}-{resource_id}", applied=True)

    return result


@router.get("/api/v1/remediate/audit")
async def get_remediation_audit(limit: int = 50):
    return {"audit_logs": get_remediation_audit_logs(limit=limit)}


# =========================================================================
# 2. GITOPS IAC PULL REQUEST ENGINE
# =========================================================================

@router.post("/api/v2/gitops/pr")
async def create_gitops_remediation_pr(payload: dict):
    resource_id = payload.get("resource_id")
    if not resource_id:
        raise HTTPException(status_code=400, detail="resource_id is required")
    action = payload.get("action", "downsize")
    from_type = payload.get("from_type")
    to_type = payload.get("to_type")
    environment = payload.get("environment", "production")
    repo_name = payload.get("repo_name", "infrastructure/aws-workloads")
    monthly_savings = float(payload.get("monthly_savings", 0.0))

    pr_package = gitops_engine.create_remediation_pr(
        resource_id=resource_id,
        action=action,
        from_type=from_type,
        to_type=to_type,
        environment=environment,
        repo_name=repo_name,
        monthly_savings=monthly_savings
    )

    try:
        if not any(w.get("resource_id") == resource_id for w in sla_watchdog.list_watches()):
            sla_watchdog.register_watch(
                resource_id=resource_id,
                remediation_action=action,
                previous_config={"instance_type": from_type} if from_type else {"config": "previous"},
                applied_config={"instance_type": to_type} if to_type else {"config": "applied"},
                baseline_metrics={"p95_latency_ms": 38.0, "error_rate_pct": 0.0, "cpu_utilization_avg": 5.0}
            )
    except Exception as e:
        logger.debug(f"Auto-enroll PR SLA watch: {e}")

    try:
        notification_engine.dispatch_event("gitops_pr", pr_package)
    except Exception:
        pass

    return pr_package


@router.post("/api/v2/gitops/batch-pr")
async def create_gitops_batch_remediation_pr(payload: Optional[dict] = None):
    payload = payload or {}
    findings = payload.get("findings")
    if not findings:
        inventory = resolve_active_inventory()
        try:
            eval_res = FinOpsAnalyzer.evaluate(inventory)
            findings = eval_res.get("findings", [])
        except Exception:
            findings = []

    environment = payload.get("environment", "production")
    repo_name = payload.get("repo_name", "infrastructure/aws-workloads")
    target_branch = payload.get("target_branch", "main")

    pkg = gitops_engine.create_batch_remediation_pr(
        findings=findings,
        environment=environment,
        repo_name=repo_name,
        target_branch=target_branch
    )

    try:
        for f in findings:
            res_id = f.get("resource_id") or f.get("id")
            if res_id and not any(w.get("resource_id") == res_id for w in sla_watchdog.list_watches()):
                sla_watchdog.register_watch(
                    resource_id=res_id,
                    remediation_action=f.get("action", "batch_optimization"),
                    previous_config=f.get("current_config", {}),
                    applied_config=f.get("recommended_config", {}),
                    baseline_metrics={"p95_latency_ms": 35.0, "error_rate_pct": 0.0, "cpu_utilization_avg": 5.0}
                )
    except Exception:
        pass

    try:
        notification_engine.dispatch_event("gitops_batch_pr", pkg)
    except Exception:
        pass

    return pkg


@router.get("/api/v2/gitops/trigger-batch-pr")
async def trigger_batch_pr_from_chat():
    inventory = resolve_active_inventory()
    findings = FinOpsAnalyzer.evaluate(inventory).get("findings", [])
    pkg = gitops_engine.create_batch_remediation_pr(findings=findings)
    return HTMLResponse(content=f"""
    <!DOCTYPE html><html><body style="font-family: monospace; background:#000; color:#fff; padding:20px;">
    <h2>🚀 GitOps Batch Remediation PR Dispatched</h2>
    <p>PR Branch: <b>{pkg.get('branch_name')}</b></p>
    <p>Monthly Savings: <b>${pkg.get('total_monthly_savings'):.2f}/mo</b></p>
    <pre>{pkg.get('unified_diff')}</pre>
    </body></html>
    """)


@router.get("/api/v2/gitops/trigger-single-pr")
async def trigger_single_pr_from_chat(resource_id: str = "i-09f1a23c4d5e67890", action: str = "downsize", from_type: str = "m5.2xlarge", to_type: str = "t4g.medium", savings: float = 243.80):
    pkg = gitops_engine.create_remediation_pr(
        resource_id=resource_id, action=action, from_type=from_type, to_type=to_type, monthly_savings=savings
    )
    return HTMLResponse(content=f"""
    <!DOCTYPE html><html><body style="font-family: monospace; background:#000; color:#fff; padding:20px;">
    <h2>🚀 GitOps Single Remediation PR Created</h2>
    <p>Resource: <b>{resource_id}</b> ({from_type} &rarr; {to_type})</p>
    <p>Branch: <b>{pkg.get('branch_name')}</b></p>
    <pre>{pkg.get('unified_diff')}</pre>
    </body></html>
    """)


@router.get("/api/v2/remediation/trigger-apply")
async def trigger_apply_remediation(finding_id: str, action: str = "apply"):
    applied = _db().setdefault("applied_optimizations", [])
    if action == "apply" and finding_id not in applied:
        applied.append(finding_id)
    elif action == "revert" and finding_id in applied:
        applied.remove(finding_id)
    return HTMLResponse(content=f"""
    <!DOCTYPE html><html><body style="font-family: monospace; background:#000; color:#fff; padding:20px;">
    <h2>✅ Remediation State Updated</h2>
    <p>Finding: <b>{finding_id}</b></p>
    <p>Action: <b>{action}</b></p>
    </body></html>
    """)


@router.get("/api/v2/gitops/audit-log")
async def get_gitops_audit_log(limit: int = 50):
    return {"count": len(gitops_engine.audit_log), "audit_trail": gitops_engine.get_audit_trail(limit)}


# =========================================================================
# 3. GITHUB APP WEBHOOKS & PR ANALYZER
# =========================================================================

@router.post("/api/v2/github/webhook")
async def handle_github_webhook(request: Request):
    payload = await request.json()
    result = github_app_engine.handle_webhook_payload(payload=payload)
    return result


@router.post("/api/v2/github/analyze-pr")
async def analyze_github_pr_diff(payload: dict):
    diff_text = payload.get("diff", "")
    file_path = payload.get("file_path", "terraform/compute.tf")
    currency = payload.get("currency", "USD")
    rate = float(payload.get("rate", 84.0))
    pr_number = payload.get("pull_number")

    analysis = github_app_engine.analyze_diff(diff_text, file_path=file_path)
    comment = github_app_engine.format_pr_comment(analysis, currency=currency, rate=rate, pr_number=pr_number)
    check_run = github_app_engine.format_check_run(analysis, currency=currency, rate=rate)

    return {
        "status": "success",
        "analysis": analysis,
        "comment_markdown": comment,
        "comment": comment,
        "check_run": check_run
    }


@router.get("/api/v2/github/status")
async def get_github_app_status():
    return github_app_engine.get_status()


# =========================================================================
# 4. CLOSED-LOOP SLA WATCHDOG & CANARY ROLLBACKS
# =========================================================================

@router.get("/api/v2/sla/watches")
async def list_sla_watches():
    return {"watches": sla_watchdog.list_watches()}


@router.get("/api/v2/sla/watches/{watch_id}")
async def get_sla_watch(watch_id: str):
    watch = sla_watchdog.get_watch(watch_id)
    if not watch:
        raise HTTPException(status_code=404, detail="Watch ID not found")
    return {"watch": watch, **watch}


@router.post("/api/v2/sla/watch")
async def register_sla_watch(payload: dict):
    resource_id = payload.get("resource_id")
    if not resource_id:
        raise HTTPException(status_code=400, detail="resource_id is required")
    watch = sla_watchdog.register_watch(
        resource_id=resource_id,
        remediation_action=payload.get("remediation_action") or payload.get("action", "downsize"),
        repo_name=payload.get("repo_name", "infrastructure/aws-workloads"),
        file_path=payload.get("file_path", "terraform/compute.tf"),
        previous_config=payload.get("previous_config", {}),
        applied_config=payload.get("applied_config", {}),
        baseline_metrics=payload.get("baseline_metrics", {}),
        duration_minutes=int(payload.get("duration_minutes", 60)),
        max_latency_increase_pct=float(payload.get("max_latency_increase_pct", 15.0))
    )
    return {"status": "registered", "watch": watch, **watch}


@router.post("/api/v2/sla/watches/{watch_id}/evaluate")
async def evaluate_sla_watch(watch_id: str, payload: Optional[dict] = None):
    payload = payload or {}
    metrics = payload.get("metrics") or payload.get("telemetry")
    result = sla_watchdog.evaluate_health(watch_id, current_metrics=metrics)
    return {"status": "success", "evaluation": result, **result}


@router.post("/api/v2/sla/watches/{watch_id}/rollback")
async def trigger_sla_rollback(watch_id: str, payload: Optional[dict] = None):
    reason = (payload or {}).get("reason", "Manual user requested rollback")
    result = sla_watchdog.trigger_automated_rollback(watch_id, breach_reasons=[reason] if reason else None)
    return {"status": "rolled_back", "rollback": {"watch_id": watch_id, **result}, **result}


# Standalone Microservice FastAPI App definition
app = FastAPI(
    title="CloudPulse Remediation, GitOps & SLA Watchdog Microservice",
    version="2.0.0",
    description="Automated Terraform/OpenTofu PR generation and canary rollback safety."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz():
    return {"status": "healthy", "service": "remediation_service", "port": 8004}


app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8004))
    uvicorn.run("microservices.remediation_service:app", host="0.0.0.0", port=port, reload=True)
