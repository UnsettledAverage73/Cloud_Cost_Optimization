"""
CloudPulse GitOps Autonomous Remediation & PR Engine Router
Endpoints for generating production-ready Infrastructure as Code Pull Requests,
multi-vector batch PR orchestration, and immutable GitOps audit trails.
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException

try:
    from services.gitops_engine import gitops_engine
    from services.sla_watchdog import sla_watchdog
    from services.notification_engine import notification_engine
    from engines.finops_analyzer import FinOpsAnalyzer
    from core.state import resolve_active_inventory
except ImportError:
    from backend.services.gitops_engine import gitops_engine
    from backend.services.sla_watchdog import sla_watchdog
    from backend.services.notification_engine import notification_engine
    from backend.engines.finops_analyzer import FinOpsAnalyzer
    from backend.core.state import resolve_active_inventory

logger = logging.getLogger("cloudpulse.api.gitops")
router = APIRouter(prefix="/api/v2/gitops", tags=["GitOps Remediation & IaC PRs"])


@router.post("/pr")
async def create_gitops_remediation_pr(payload: dict):
    """Creates a production-ready GitOps Pull Request package."""
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
    # Auto-enroll into 60-min SLA watchdog
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

    # Dispatch GitOps PR notification to Slack & Teams
    try:
        notification_engine.dispatch_event("gitops_pr", pr_package)
    except Exception as notif_e:
        logger.debug(f"GitOps PR notification notice: {notif_e}")

    return pr_package


@router.post("/batch-pr")
async def create_gitops_batch_remediation_pr(payload: Optional[dict] = None):
    """Creates a unified multi-resource batch GitOps Pull Request package across all 5 resource vectors."""
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

    # Auto-enroll each remediated finding into 60-min SLA watchdog
    try:
        for f in findings:
            res_id = f.get("resource_id") or f.get("id")
            if res_id and not any(w.get("resource_id") == res_id for w in sla_watchdog.list_watches()):
                sla_watchdog.register_watch(
                    resource_id=res_id,
                    remediation_action=f.get("action", "batch_optimization"),
                    previous_config={"type": "standard", "monthly_cost": float(f.get("monthly_savings", 10.0)) * 1.5},
                    applied_config={"type": "optimized", "monthly_cost": float(f.get("monthly_savings", 10.0)) * 0.5},
                    baseline_metrics={"p95_latency_ms": 32.0, "error_rate_pct": 0.0, "cpu_utilization_avg": 8.0}
                )
    except Exception as e:
        logger.debug(f"Auto-enroll batch SLA watch: {e}")

    # Dispatch GitOps Batch PR notification to Slack & Teams
    try:
        notification_engine.dispatch_event("gitops_pr", pkg)
    except Exception as notif_e:
        logger.debug(f"GitOps batch PR notification notice: {notif_e}")

    return pkg


@router.get("/audit-log")
async def get_gitops_audit_log(limit: int = 50):
    """Returns immutable audit trail of all GitOps PRs and remediations."""
    return {"count": len(gitops_engine.audit_log), "audit_trail": gitops_engine.get_audit_trail(limit)}
