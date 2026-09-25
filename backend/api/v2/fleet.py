"""
CloudPulse Multi-Account Fleet Ingestion & FOCUS 1.0 Router
Endpoints for enterprise AWS accounts management, organization discovery, parallel fleet scans,
and normalized FOCUS 1.0 records.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException
import boto3

try:
    from collectors.fleet_manager import fleet_manager, FleetAccountConfig
    from engines.focus_spec import FOCUSNormalizer
    from core.state import get_realtime_store
except ImportError:
    from backend.collectors.fleet_manager import fleet_manager, FleetAccountConfig
    from backend.engines.focus_spec import FOCUSNormalizer
    from backend.core.state import get_realtime_store

router = APIRouter(prefix="/api/v2/fleet", tags=["Fleet Management & Multi-Account Ingestion"])


def _get_aws_session():
    try:
        from main import _build_aws_session
        s = _build_aws_session()
        if s:
            return s
    except Exception:
        pass
    return boto3.Session()


@router.get("/accounts")
async def get_fleet_accounts():
    """Returns all registered AWS accounts in the enterprise fleet."""
    accounts = [acc.to_dict() for acc in fleet_manager.accounts.values()]
    if not accounts:
        accounts = [{
            "account_id": "default-account",
            "account_name": "Primary AWS Environment",
            "region": "us-east-1",
            "auth_type": "active_session",
            "is_management_account": True
        }]
    return {"total_accounts": len(accounts), "accounts": accounts}


@router.post("/accounts")
async def register_fleet_account(payload: dict):
    """Enrolls a new account into the multi-account fleet."""
    acc_id = payload.get("account_id")
    if not acc_id:
        raise HTTPException(status_code=400, detail="account_id is required")
    cfg = FleetAccountConfig(
        account_id=acc_id,
        account_name=payload.get("account_name", f"Account-{acc_id}"),
        role_arn=payload.get("role_arn"),
        external_id=payload.get("external_id"),
        region=payload.get("region", "us-east-1"),
        access_key=payload.get("access_key"),
        secret_key=payload.get("secret_key"),
        session_token=payload.get("session_token"),
        is_management_account=bool(payload.get("is_management_account", False))
    )
    fleet_manager.register_account(cfg)
    return {"status": "success", "account": cfg.to_dict()}


@router.post("/discover")
async def discover_fleet_accounts(payload: Optional[dict] = None):
    """
    Auto-discovers all member accounts via AWS Organizations API
    and enrolls them into the multi-account fleet manager.
    """
    payload = payload or {}
    role_name = payload.get("role_name", "CloudPulseReadOnlyRole")
    external_id = payload.get("external_id", "CloudPulseEnterpriseSecurityId")
    session = _get_aws_session()
    discovered = fleet_manager.discover_organization_accounts(
        management_session=session,
        role_name=role_name,
        external_id=external_id
    )
    return {
        "status": "success",
        "discovered_count": len(discovered),
        "accounts": [acc.to_dict() for acc in discovered]
    }


@router.get("/summary")
async def get_fleet_summary(force_refresh: bool = False):
    """Returns aggregated fleet-wide FinOps executive KPIs and spend."""
    summary = fleet_manager.get_fleet_summary(force_refresh=force_refresh)
    if not summary.get("accounts_scanned"):
        db = get_realtime_store()
        nodes = db.get("nodes", [])
        vols = db.get("ebs_volumes", [])
        eips = db.get("elastic_ips", [])
        total_spend = sum(float(n.get("cost", 7.60)) for n in nodes)
        summary = {
            "total_accounts_registered": max(1, len(fleet_manager.accounts)),
            "accounts_scanned": 1 if nodes or vols or eips else 0,
            "successful_scans": 1 if nodes or vols or eips else 0,
            "failed_scans": 0,
            "total_fleet_monthly_spend": round(total_spend, 2),
            "total_fleet_nodes": len(nodes),
            "total_fleet_volumes": len(vols),
            "total_fleet_eips": len(eips),
            "total_focus_records": len(nodes) + len(vols) + len(eips),
            "scan_duration_seconds": 0.05
        }
    return summary


@router.post("/scan")
async def trigger_fleet_scan(payload: Optional[dict] = None):
    """Triggers parallel multi-worker scan across all accounts in fleet."""
    payload = payload or {}
    account_ids = payload.get("account_ids")
    summary = fleet_manager.scan_fleet_parallel(account_ids=account_ids)
    return summary


@router.get("/focus-records")
async def get_fleet_focus_records():
    """Returns normalized FOCUS 1.0 records across the entire fleet."""
    db = get_realtime_store()
    focus_records = FOCUSNormalizer.normalize_inventory(db)
    return {
        "specification": "FOCUS 1.0",
        "record_count": len(focus_records),
        "records": focus_records
    }
