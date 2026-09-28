"""
CloudPulse FinOps Analytics & Cost Optimization Microservice
Port: 8002
Provides dashboard executive summaries, node inventory, spend analytics,
ARIMA/Holt-Winters forecasting, FOCUS 1.0 Lakehouse OLAP, and PoV PDF/HTML reports.
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, APIRouter, HTTPException, status, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

_backend_dir = Path(__file__).resolve().parent.parent
_repo_dir = _backend_dir.parent
for p in [str(_backend_dir), str(_repo_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from microservices.shared_state import (
        _db, _ensure_live_aws_state, _frontend_spend, _frontend_nodes,
        _normalize_node, _frontend_alerts, _frontend_optimizations,
        get_realtime_store
    )
    from schemas import NodeSchema
    from services.cost_analytics import (
        calculate_finops_health_score, calculate_spend_forecast,
        detect_cost_anomalies, evaluate_inventory_optimizations
    )
    from services.anomaly_detector import anomaly_detector
    from services.spend_forecaster import spend_forecaster
    from engines.focus_spec import FOCUSNormalizer
    from engines.focus_lakehouse import focus_lakehouse
    from engines.finops_analyzer import FinOpsAnalyzer
    from engines.cur_ingestion_engine import cur_ingestion_engine
    from engines.workload_hierarchy_engine import workload_hierarchy_engine
    from engines.policy_guardrails_engine import policy_guardrails_engine
    from engines.commitment_optimizer import CommitmentOptimizer
    from engines.pdf_dossier_engine import pdf_dossier_engine
    from core.state import resolve_active_inventory
    from collectors.multicloud_connector import multicloud_orchestrator
    from database.connection import SyncSessionLocal
    from database.models import DailySpendRecord
except ImportError:
    from backend.microservices.shared_state import (
        _db, _ensure_live_aws_state, _frontend_spend, _frontend_nodes,
        _normalize_node, _frontend_alerts, _frontend_optimizations,
        get_realtime_store
    )
    from backend.schemas import NodeSchema
    from backend.services.cost_analytics import (
        calculate_finops_health_score, calculate_spend_forecast,
        detect_cost_anomalies, evaluate_inventory_optimizations
    )
    from backend.services.anomaly_detector import anomaly_detector
    from backend.services.spend_forecaster import spend_forecaster
    from backend.engines.focus_spec import FOCUSNormalizer
    from backend.engines.focus_lakehouse import focus_lakehouse
    from backend.engines.finops_analyzer import FinOpsAnalyzer
    from backend.engines.cur_ingestion_engine import cur_ingestion_engine
    from backend.engines.workload_hierarchy_engine import workload_hierarchy_engine
    from backend.engines.policy_guardrails_engine import policy_guardrails_engine
    from backend.engines.commitment_optimizer import CommitmentOptimizer
    from backend.engines.pdf_dossier_engine import pdf_dossier_engine
    from backend.core.state import resolve_active_inventory
    from backend.collectors.multicloud_connector import multicloud_orchestrator
    from backend.database.connection import SyncSessionLocal
    from backend.database.models import DailySpendRecord

router = APIRouter(tags=["FinOps Analytics Microservice"])


# =========================================================================
# 1. EXECUTIVE DASHBOARD & INVENTORY
# =========================================================================

@router.get("/api/v1/dashboard/summary")
async def get_executive_summary():
    _ensure_live_aws_state()
    db = _db()
    total_nodes = len(db["nodes"])
    running_nodes = sum(1 for n in db["nodes"] if n["state"] == "running")
    
    spend_rows = _frontend_spend()
    monthly_spend = sum(row.get("aws", 0) for row in spend_rows)
    wasted_eip = sum(eip.get("estimated_monthly_cost", 3.65) for eip in db["elastic_ips"] if eip.get("is_unattached"))
    wasted_ebs = sum(v.get("cost", 10.0) for v in db["ebs_volumes"] if v.get("is_orphaned"))
    total_wasted = wasted_eip + wasted_ebs

    critical_security_risks = sum(1 for sg in db["security_groups"] if sg.get("is_publicly_exposed"))

    return {
        "monthly_spend": round(monthly_spend, 2),
        "total_nodes": total_nodes,
        "running_nodes": running_nodes,
        "stopped_nodes": total_nodes - running_nodes,
        "wasted_monthly_spend": round(total_wasted, 2),
        "critical_security_risks": critical_security_risks,
        "last_synced": db["metadata"].get("timestamp")
    }


@router.get("/api/v1/resources/nodes", response_model=List[NodeSchema])
@router.get("/api/nodes", response_model=List[NodeSchema])
async def get_nodes(status: Optional[str] = None, search: Optional[str] = None):
    return _frontend_nodes(status=status, search=search)


@router.get("/api/v1/resources/nodes/{instance_id}")
async def get_node_details(instance_id: str):
    _ensure_live_aws_state()
    nodes = _db()["nodes"]
    node = next((n for n in nodes if n["instance_id"] == instance_id), None)
    if not node:
        raise HTTPException(status_code=404, detail="Instance ID not found")
    details = _normalize_node(node)
    attached_vols = set(node.get("attached_volume_ids") or [])
    details["volumes_detail"] = [
        volume for volume in _db().get("ebs_volumes", [])
        if any(attachment.get("InstanceId") == instance_id for attachment in volume.get("attachments", []))
        or volume.get("attached_instance_id") == instance_id
        or volume.get("volume_id") in attached_vols
    ]
    details["network_interfaces"] = [
        eni for eni in _db().get("network_interfaces", [])
        if eni.get("attached_instance_id") == instance_id
    ]
    db_sgs = {sg.get("group_id"): sg for sg in _db().get("security_groups", []) if isinstance(sg, dict)}
    details["security_groups_detail"] = [
        db_sgs.get(sg.get("group_id"), sg) for sg in node.get("security_groups", []) if isinstance(sg, dict)
    ]
    return details


@router.get("/api/v1/resources/inventory")
async def get_full_inventory():
    _ensure_live_aws_state()
    db = _db()
    return {
        "metadata": db["metadata"],
        "compute": {"nodes": db["nodes"]},
        "ec2_other_resources": {
            "ebs_volumes": db.get("ebs_volumes", []),
            "elastic_ips": db.get("elastic_ips", []),
            "amis": db.get("amis", []),
            "network_interfaces": db.get("network_interfaces", []),
            "ebs_snapshots": db.get("ebs_snapshots", []),
            "security_groups": db.get("security_groups", []),
            "cloudwatch_log_groups": db.get("cloudwatch_log_groups", []),
        },
        "rds": {
            "instances": db.get("rds_instances", []),
            "clusters": db.get("rds_clusters", []),
            "snapshots": db.get("rds_manual_snapshots", [])
        },
        "vpc": db.get("vpc_resources", {"nat_gateways": db.get("nat_gateways", []), "vpc_endpoints": db.get("vpc_endpoints", [])}),
        "s3": {"buckets": db.get("s3_buckets", [])},
        "load_balancers": db.get("load_balancers", []),
        "daily_spend": db.get("daily_spend", []),
        "service_breakdown": db.get("service_breakdown", []),
        "summary": db.get("summary", {})
    }


@router.get("/api/spend")
async def get_spend():
    return _frontend_spend()


@router.get("/api/alerts")
async def get_alerts():
    return _frontend_alerts()


@router.get("/api/optimizations")
@router.get("/api/v1/optimizations")
async def get_optimizations():
    return _frontend_optimizations()


@router.get("/api/optimizations/applied")
async def get_applied_optimizations():
    return _db().get("applied_optimizations", [])


# =========================================================================
# 2. FINOPS HEALTH SCORE, FORECAST & ANOMALIES (V1 & V2)
# =========================================================================

@router.get("/api/v1/analytics/health-score")
async def get_health_score():
    return calculate_finops_health_score(_db())


@router.get("/api/v1/analytics/forecast")
async def get_forecast(budget: float = 600.0):
    _ensure_live_aws_state()
    spend_rows = _frontend_spend()
    return calculate_spend_forecast(spend_rows, monthly_budget=budget)


@router.get("/api/v1/analytics/anomalies")
async def get_anomalies():
    _ensure_live_aws_state()
    spend_rows = _frontend_spend()
    return {"anomalies": detect_cost_anomalies(spend_rows)}


@router.get("/api/v2/analytics/anomalies")
async def get_v2_cost_anomalies(severity: Optional[str] = None):
    if not anomaly_detector.cached_anomalies:
        inventory = resolve_active_inventory()
        focus_records = FOCUSNormalizer.convert_inventory_to_focus(inventory)
        anomaly_detector.scan_inventory_and_focus(inventory, focus_records)

    anomalies = anomaly_detector.get_anomalies(severity)
    return {
        "count": len(anomalies),
        "severity_filter": severity or "ALL",
        "anomalies": anomalies
    }


@router.post("/api/v2/analytics/anomalies/scan")
async def trigger_v2_anomaly_scan():
    inventory = resolve_active_inventory()
    focus_records = FOCUSNormalizer.convert_inventory_to_focus(inventory)
    anomalies = anomaly_detector.scan_inventory_and_focus(inventory, focus_records)
    return {
        "status": "scan_complete",
        "anomalies_detected": len(anomalies),
        "anomalies": anomalies
    }


@router.get("/api/v2/analytics/forecast")
async def get_v2_spend_forecast(days: int = 30, budget: float = 100.0):
    inventory = resolve_active_inventory()
    forecast = spend_forecaster.forecast_from_inventory(
        inventory=inventory,
        forecast_days=days,
        monthly_budget=budget
    )
    return forecast


@router.post("/api/v2/analytics/forecast")
async def calculate_custom_v2_forecast(payload: dict):
    history = payload.get("daily_history", [])
    days = int(payload.get("forecast_days", 30))
    budget = float(payload.get("monthly_budget", 100.0))
    mtd = payload.get("mtd_spend")
    if mtd is not None:
        mtd = float(mtd)

    forecast = spend_forecaster.forecast_spend(
        daily_history=history,
        forecast_days=days,
        monthly_budget=budget,
        mtd_spend=mtd
    )
    return forecast


# =========================================================================
# 3. FOCUS 1.0 & DUCKDB LAKEHOUSE
# =========================================================================

@router.get("/api/v2/focus/spend")
async def get_focus_spend(limit: int = 100):
    session = SyncSessionLocal()
    try:
        records = session.query(DailySpendRecord).order_by(
            DailySpendRecord.time.desc(), DailySpendRecord.billed_cost.desc()
        ).limit(limit).all()

        total_billed = sum(float(r.billed_cost) for r in records)
        total_effective = sum(float(r.effective_cost) for r in records)

        return {
            "specification": "FOCUS 1.0",
            "count": len(records),
            "summary": {
                "total_billed_cost": round(total_billed, 2),
                "total_effective_cost": round(total_effective, 2)
            },
            "records": [r.to_dict() for r in records]
        }
    except Exception:
        spend_rows = focus_lakehouse.get_spend_by_service() if focus_lakehouse else []
        return {
            "specification": "FOCUS 1.0 (In-Memory Fallback)",
            "count": len(spend_rows),
            "records": spend_rows
        }
    finally:
        session.close()


@router.post("/api/v2/focus/query")
async def execute_focus_sql_query(payload: dict):
    sql = payload.get("query")
    if not sql:
        raise HTTPException(status_code=400, detail="SQL query is required")

    db = get_realtime_store()
    if db and focus_lakehouse:
        focus_records = FOCUSNormalizer.normalize_inventory(db)
        focus_lakehouse.load_focus_records(focus_records)

    try:
        result = focus_lakehouse.execute_query(sql) if focus_lakehouse else []
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/v2/focus/analytics")
async def get_focus_analytics():
    db = get_realtime_store()
    if db and focus_lakehouse:
        focus_records = FOCUSNormalizer.normalize_inventory(db)
        focus_lakehouse.load_focus_records(focus_records)

    return {
        "status": "success",
        "spend_by_service": focus_lakehouse.get_spend_by_service() if focus_lakehouse else [],
        "spend_by_account": focus_lakehouse.get_spend_by_account() if focus_lakehouse else [],
        "top_cost_drivers": focus_lakehouse.get_top_cost_drivers(limit=10) if focus_lakehouse else []
    }


# =========================================================================
# 4. MULTI-CLOUD INGEST & SUMMARY
# =========================================================================

@router.get("/api/v2/multicloud/summary")
async def get_multicloud_summary():
    summary_spend = resolve_active_inventory().get("summary", {}).get("estimated_monthly_spend", 74.16)
    return multicloud_orchestrator.get_cross_cloud_summary(aws_spend=summary_spend)


@router.post("/api/v2/multicloud/ingest")
async def ingest_multicloud_records(payload: dict):
    provider = payload.get("provider", "").lower()
    records = payload.get("records", [])
    if provider == "azure":
        normalized = multicloud_orchestrator.ingest_azure_batch(records)
    elif provider == "gcp":
        normalized = multicloud_orchestrator.ingest_gcp_batch(records)
    else:
        raise HTTPException(status_code=400, detail="Provider must be 'azure' or 'gcp'")

    return {
        "status": "ingested",
        "provider": provider.upper(),
        "records_ingested": len(normalized),
        "focus_records": normalized
    }


# =========================================================================
# 5. 48-HOUR PROOF-OF-VALUE (PoV) EXECUTIVE REPORTS
# =========================================================================

@router.get("/api/v2/analytics/pov/summary")
async def get_pov_summary(currency: str = "INR", rate: float = 84.0):
    try:
        from services.currency_converter import currency_converter
        from services.pov_reporter import PoVReporter
    except ImportError:
        from backend.services.currency_converter import currency_converter
        from backend.services.pov_reporter import PoVReporter

    currency_converter.usd_to_inr_rate = rate
    reporter = PoVReporter(currency=currency, usd_to_inr_rate=rate)

    inventory = resolve_active_inventory()
    focus_records = FOCUSNormalizer.convert_inventory_to_focus(inventory)
    anomalies = anomaly_detector.scan_inventory_and_focus(inventory, focus_records)

    gross_monthly = float(inventory.get("summary", {}).get("estimated_monthly_spend", 0.0))
    eval_res = FinOpsAnalyzer.evaluate(_db())
    findings = eval_res.get("findings", [])
    savings_monthly = round(sum(float(f.get("monthly_savings", 0.0)) for f in findings), 2)
    savings_annual = round(savings_monthly * 12, 2)
    acct_id = inventory.get("metadata", {}).get("account_id") or "Connected Account"

    return {
        "account_id": acct_id,
        "currency": currency.upper(),
        "exchange_rate": rate,
        "gross_monthly_spend_usd": gross_monthly,
        "gross_annual_spend_usd": round(gross_monthly * 12, 2),
        "gross_monthly_spend_formatted": currency_converter.format_dual(gross_monthly, primary_currency=currency),
        "gross_annual_spend_formatted": currency_converter.format_dual(gross_monthly * 12, primary_currency=currency),
        "recoverable_monthly_savings_usd": savings_monthly,
        "recoverable_annual_savings_usd": savings_annual,
        "recoverable_annual_savings_formatted": currency_converter.format_dual(savings_annual, primary_currency=currency),
        "waste_percentage": round((savings_monthly / gross_monthly * 100), 1) if gross_monthly > 0 else 0.0,
        "total_compute_nodes": len(inventory.get("compute", {}).get("nodes", [])),
        "anomalies_count": len(anomalies),
        "anomalies_critical": sum(1 for a in anomalies if a.get("severity") == "CRITICAL")
    }


@router.get("/api/v2/analytics/pov/report.html", response_class=HTMLResponse)
async def get_pov_html_report(currency: str = "INR", rate: float = 84.0, account_name: str = "Enterprise Cloud Fleet"):
    try:
        from services.currency_converter import currency_converter
        from services.pov_reporter import PoVReporter
    except ImportError:
        from backend.services.currency_converter import currency_converter
        from backend.services.pov_reporter import PoVReporter

    currency_converter.usd_to_inr_rate = rate
    reporter = PoVReporter(currency=currency, usd_to_inr_rate=rate)

    inventory = resolve_active_inventory()
    focus_records = FOCUSNormalizer.convert_inventory_to_focus(inventory)
    anomalies = anomaly_detector.scan_inventory_and_focus(inventory, focus_records)

    html_content = reporter.generate_html_report(
        inventory=inventory,
        anomalies=anomalies,
        account_name=account_name
    )
    return HTMLResponse(content=html_content, status_code=200)


@router.get("/api/v2/reports/catalog")
async def get_report_catalog():
    """Returns metadata for the 4 enterprise persona audit dossiers."""
    return {
        "status": "success",
        "engine": "In-Process Native Vector Streaming (ReportLab Platypus)",
        "catalog": pdf_dossier_engine.REPORT_CATALOG
    }


@router.get("/api/v2/reports/pdf")
async def get_enterprise_pdf_dossier(
    report_type: str = "executive",
    account_id: Optional[str] = None,
    currency: str = "USD",
    instance_id: Optional[str] = None,
    inline: bool = False
):
    """
    Generates a publication-grade, monochrome vector PDF dossier in <50ms.
    Supported report_type: executive | engineering | security_hygiene | telemetry_snapshot
    """
    import time
    t0 = time.perf_counter()
    inventory = resolve_active_inventory()
    acc_id = account_id or inventory.get("metadata", {}).get("account_id", "123456789012")
    acc_name = inventory.get("metadata", {}).get("account_name", "Enterprise-Core-AWS")

    stream = pdf_dossier_engine.build_pdf_stream(
        report_type=report_type,
        inventory=inventory,
        account_id=acc_id,
        account_name=acc_name,
        currency=currency,
        instance_id=instance_id
    )
    latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    disposition = "inline" if inline else "attachment"
    filename = f"CloudPulse_{report_type}_{acc_id}.pdf"

    return StreamingResponse(
        stream,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'{disposition}; filename="{filename}"',
            "X-Render-Latency-Ms": str(latency_ms),
            "X-Report-Type": report_type,
            "X-Account-Id": acc_id
        }
    )


@router.get("/api/v2/analytics/pov/report.pdf")
@router.get("/api/v1/reports/inventory-cost.pdf")
async def get_pov_pdf_report(
    currency: str = "USD",
    rate: float = 84.0,
    account_name: str = "Enterprise Cloud Fleet",
    inline: bool = True
):
    inventory = resolve_active_inventory()
    acc_id = inventory.get("metadata", {}).get("account_id", "123456789012")

    stream = pdf_dossier_engine.build_pdf_stream(
        report_type="executive",
        inventory=inventory,
        account_id=acc_id,
        account_name=account_name,
        currency=currency
    )
    disposition = "inline" if inline else "attachment"
    return StreamingResponse(
        stream,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="CloudPulse_Executive_Cost_Report.pdf"'}
    )


# =========================================================================
# 5. ENTERPRISE HYPERSCALE: WORKLOAD TREE & POLICY GUARDRAILS
# =========================================================================

@router.get("/api/v2/workloads/tree")
async def get_workload_tree(org_name: str = "Enterprise Cloud Fleet"):
    inventory = resolve_active_inventory()
    tree = workload_hierarchy_engine.build_tree_from_inventory(inventory, org_name=org_name)
    return tree


@router.get("/api/v2/workloads/cur")
async def get_cur_workloads():
    workloads = cur_ingestion_engine.query_workloads_from_cur()
    return {
        "status": "success",
        "workload_count": len(workloads),
        "workloads": workloads
    }


@router.post("/api/v2/cur/sync")
async def sync_cur_dataset(payload: Optional[dict] = None):
    payload = payload or {}
    path = payload.get("parquet_path")
    res = cur_ingestion_engine.ingest_cur_parquet(path or "backend/data/cur/sample_cur_2_0.parquet")
    return res


@router.get("/api/v2/policies")
async def list_enterprise_policies():
    return {
        "count": len(policy_guardrails_engine.list_policies()),
        "policies": policy_guardrails_engine.list_policies()
    }


@router.post("/api/v2/policies/evaluate")
async def evaluate_enterprise_policies(simulate: bool = True):
    inventory = resolve_active_inventory()
    eval_res = policy_guardrails_engine.evaluate_fleet(inventory, simulate_hyperscale=simulate)
    return eval_res


@router.post("/api/v2/policies/{policy_id}/toggle")
async def toggle_enterprise_policy(policy_id: str, payload: dict):
    enabled = bool(payload.get("is_enabled", True))
    res = policy_guardrails_engine.toggle_policy(policy_id, enabled)
    if not res:
        raise HTTPException(status_code=404, detail="Policy not found")
    return {"status": "success", "policy": res}


@router.post("/api/v2/policies/{policy_id}/remediate")
async def remediate_enterprise_policy(policy_id: str, payload: Optional[dict] = None):
    payload = payload or {}
    resource_id = payload.get("resource_id")
    try:
        res = policy_guardrails_engine.remediate_policy(policy_id, resource_id=resource_id)
        return res
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/api/v2/commitments/portfolio")
async def get_commitment_portfolio(coverage_target: float = 0.75):
    inventory = resolve_active_inventory()
    portfolio = CommitmentOptimizer.analyze_portfolio(inventory, coverage_target=coverage_target)
    return portfolio


# Standalone Microservice FastAPI App definition
app = FastAPI(
    title="CloudPulse FinOps Analytics & Cost Optimization Microservice",
    version="2.0.0",
    description="Executive dashboard analytics, FOCUS 1.0 Lakehouse, and spend forecasting."
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
    return {"status": "healthy", "service": "analytics_service", "port": 8002}


app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8002))
    uvicorn.run("microservices.analytics_service:app", host="0.0.0.0", port=port, reload=True)
