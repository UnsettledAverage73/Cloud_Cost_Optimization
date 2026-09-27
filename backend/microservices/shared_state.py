"""
CloudPulse Microservices Shared State & Cloud Ingestion Utilities
Provides thread-safe access to live inventory, session persistence,
and normalization adapters used across distributed microservice domains.
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Union

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from botocore.config import Config
from fastapi import HTTPException

# Safe import resolvers
try:
    from core.state import REALTIME_STORE, get_realtime_store, resolve_active_inventory
    from schemas import CloudConnectRequest
    from collectors.orchestrator import AWSDataIngestionOrchestrator
    from engines.finops_analyzer import FinOpsAnalyzer
    from services.finops_agent import FinOpsAgent
    from services.notifier import FinOpsNotifier
    from services.llm_engine import llm_engine
except ImportError:
    from backend.core.state import REALTIME_STORE, get_realtime_store, resolve_active_inventory
    from backend.schemas import CloudConnectRequest
    from backend.collectors.orchestrator import AWSDataIngestionOrchestrator
    from backend.engines.finops_analyzer import FinOpsAnalyzer
    from backend.services.finops_agent import FinOpsAgent
    from backend.services.notifier import FinOpsNotifier
    try:
        from backend.services.llm_engine import llm_engine
    except ImportError:
        llm_engine = None

STATE_FILE = Path(__file__).resolve().parent.parent / ".cloudpulse_state.json"

active_credentials: Dict[str, Any] = {}
connected_accounts: List[Dict[str, Any]] = []
last_live_error: str = ""
is_demo_mode: bool = False
revoked_security_groups: set = set()

_last_live_refresh_time: float = 0.0
LIVE_CACHE_TTL_SECONDS: float = 180.0

AWS_CLIENT_CONFIG = Config(
    connect_timeout=3,
    read_timeout=8,
    retries={"max_attempts": 1, "mode": "standard"},
)

_INSTANCE_MONTHLY_RATES = {
    "t3.nano": 3.80,
    "t3.micro": 7.60,
    "t3.small": 15.20,
    "t3.medium": 30.40,
    "t3.large": 60.80,
}

finops_agent = FinOpsAgent(data_store=REALTIME_STORE)
finops_notifier = FinOpsNotifier()


def _db() -> Dict[str, Any]:
    return get_realtime_store()


def _load_persisted_state():
    global active_credentials, connected_accounts, revoked_security_groups
    if not STATE_FILE.exists():
        return

    try:
        state = json.loads(STATE_FILE.read_text())
    except Exception:
        return

    active = state.get("active_connection")
    if isinstance(active, dict) and active:
        active_credentials["default"] = active

    accounts = state.get("connected_accounts", [])
    if isinstance(accounts, list):
        connected_accounts[:] = [item for item in accounts if isinstance(item, dict)]

    revoked = state.get("revoked_security_groups", [])
    if isinstance(revoked, list):
        revoked_security_groups.update(revoked)


def _persist_state():
    state = {
        "active_connection": active_credentials.get("default"),
        "connected_accounts": connected_accounts,
        "revoked_security_groups": list(revoked_security_groups),
    }
    try:
        STATE_FILE.write_text(json.dumps(state, indent=2, default=str))
    except Exception:
        pass


_load_persisted_state()


def _connection_signature(payload: dict) -> tuple:
    return (
        (payload.get("provider") or "").lower(),
        (payload.get("account_name") or "").strip().lower(),
        (payload.get("region") or "").strip().lower(),
        (payload.get("role_arn") or "").strip().lower(),
        (payload.get("access_key") or "").strip()[-4:],
    )


def _public_connection_record(payload: dict) -> dict:
    return {
        "provider": payload.get("provider"),
        "account_name": payload.get("account_name"),
        "auth_method": payload.get("auth_method"),
        "role_arn": payload.get("role_arn"),
        "region": payload.get("region"),
        "connected_at": payload.get("connected_at"),
        "active": payload.get("active", False),
        "access_key_last4": payload.get("access_key_last4"),
        "session_token_present": bool(payload.get("session_token")),
    }


def _set_connection_mode(access_mode: str, warning: Optional[str] = None):
    if not active_credentials.get("default"):
        return
    active_credentials["default"]["access_mode"] = access_mode
    if warning:
        active_credentials["default"]["warning"] = warning
    elif "warning" in active_credentials["default"]:
        active_credentials["default"].pop("warning", None)
    _persist_state()


def _save_active_credentials(credentials: CloudConnectRequest):
    profile = {
        "provider": credentials.provider,
        "account_name": credentials.account_name,
        "auth_method": credentials.auth_method,
        "access_key": credentials.access_key,
        "secret_key": credentials.secret_key,
        "session_token": credentials.session_token,
        "role_arn": credentials.role_arn,
        "region": credentials.region,
    }
    active_credentials["default"] = profile

    profile_key = (
        credentials.provider.lower(),
        (credentials.account_name or "").strip().lower(),
        (credentials.region or "").strip().lower(),
        (credentials.role_arn or "").strip().lower(),
        (credentials.access_key or "").strip()[-4:],
    )

    existing_index = next(
        (
            idx
            for idx, item in enumerate(connected_accounts)
            if (
                (item.get("provider") or "").lower(),
                (item.get("account_name") or "").strip().lower(),
                (item.get("region") or "").strip().lower(),
                (item.get("role_arn") or "").strip().lower(),
                (item.get("access_key_last4") or "").strip(),
            ) == profile_key
        ),
        None,
    )

    connected_record = {
        "provider": credentials.provider,
        "account_name": credentials.account_name,
        "auth_method": credentials.auth_method,
        "access_key": credentials.access_key,
        "secret_key": credentials.secret_key,
        "session_token": credentials.session_token,
        "role_arn": credentials.role_arn,
        "region": credentials.region,
        "connected_at": datetime.now(timezone.utc).isoformat(),
        "active": True,
        "access_key_last4": (credentials.access_key or "").strip()[-4:] or None,
        "session_token_present": bool(credentials.session_token),
    }

    if existing_index is not None:
        for idx, item in enumerate(connected_accounts):
            item["active"] = idx == existing_index
        connected_accounts[existing_index] = {**connected_accounts[existing_index], **connected_record}
    else:
        for item in connected_accounts:
            item["active"] = False
        connected_accounts.append(connected_record)

    _persist_state()


def _saved_credentials() -> Optional[Dict[str, Any]]:
    return active_credentials.get("default")


def _connection_state() -> Dict[str, Any]:
    global is_demo_mode
    if is_demo_mode:
        return {
            "connected": True,
            "provider": "AWS (Simulation Demo)",
            "account_name": _db()["metadata"].get("organization", "Demo Sandbox"),
            "region": _db()["metadata"].get("region", "us-east-1"),
            "auth_method": "simulation",
            "role_arn": "arn:aws:iam::123456789012:role/FinOpsDemoRole",
            "access_mode": "demo",
            "warning": None,
            "connected_accounts": [_public_connection_record(item) for item in connected_accounts],
        }
    creds = _saved_credentials()
    if not creds:
        return {
            "connected": False,
            "provider": None,
            "account_name": None,
            "region": None,
            "access_mode": None,
            "warning": None,
            "connected_accounts": [_public_connection_record(item) for item in connected_accounts],
        }
    return {
        "connected": True,
        "provider": creds.get("provider"),
        "account_name": creds.get("account_name"),
        "region": creds.get("region"),
        "auth_method": creds.get("auth_method"),
        "role_arn": creds.get("role_arn"),
        "access_mode": creds.get("access_mode", "live"),
        "warning": creds.get("warning"),
        "connected_accounts": [_public_connection_record(item) for item in connected_accounts],
    }


def _estimate_instance_monthly_cost(instance_type: str) -> float:
    return _INSTANCE_MONTHLY_RATES.get(instance_type, 10.00)


def _estimate_ebs_monthly_cost(volume: dict) -> float:
    volume_type = (volume.get("volume_type") or volume.get("VolumeType") or "gp3").lower()
    size_gb = volume.get("size_gb") or volume.get("Size") or 0
    rate = 0.08 if volume_type.startswith("gp3") else 0.10 if volume_type.startswith("gp2") else 0.12
    return round(float(size_gb) * rate, 2)


def _build_aws_session() -> Optional[boto3.Session]:
    creds = _saved_credentials()
    if not creds or creds.get("provider", "").upper() != "AWS":
        if os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY"):
            return boto3.Session(
                region_name=os.environ.get("AWS_DEFAULT_REGION", os.environ.get("AWS_REGION", "us-east-1")),
                aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
                aws_session_token=os.environ.get("AWS_SESSION_TOKEN"),
            )
        return None

    session_kwargs = {
        "region_name": creds.get("region", "us-east-1"),
    }
    if creds.get("access_key"):
        session_kwargs["aws_access_key_id"] = creds["access_key"]
    if creds.get("secret_key"):
        session_kwargs["aws_secret_access_key"] = creds["secret_key"]
    if creds.get("session_token"):
        session_kwargs["aws_session_token"] = creds["session_token"]

    return boto3.Session(**session_kwargs)


def _activate_connected_account(selector: dict) -> dict:
    target_signature = _connection_signature(selector)
    match = next(
        (
            item
            for item in connected_accounts
            if _connection_signature(item) == target_signature
        ),
        None,
    )

    if not match:
        raise HTTPException(status_code=404, detail="Saved AWS account not found.")

    if not (match.get("access_key") and match.get("secret_key")):
        raise HTTPException(status_code=400, detail="Saved account does not include credentials required to reconnect.")

    for item in connected_accounts:
        item["active"] = _connection_signature(item) == target_signature

    active_credentials["default"] = {
        "provider": match.get("provider"),
        "account_name": match.get("account_name"),
        "auth_method": match.get("auth_method"),
        "access_key": match.get("access_key"),
        "secret_key": match.get("secret_key"),
        "session_token": match.get("session_token"),
        "role_arn": match.get("role_arn"),
        "region": match.get("region"),
    }
    _persist_state()
    return match


def _is_permission_denied(error_message: str) -> bool:
    lowered = (error_message or "").lower()
    return (
        "unauthorizedoperation" in lowered
        or "accessdenied" in lowered
        or "explicit deny" in lowered
        or "not authorized to perform" in lowered
        or "expiredtoken" in lowered
        or "token has expired" in lowered
        or "authfailure" in lowered
        or "invalidclienttokenid" in lowered
        or "signaturedoesnotmatch" in lowered
        or "credentials not found" in lowered
    )


def _tag_lookup(tags):
    return {tag.get("Key"): tag.get("Value") for tag in tags or []}


def _optional_pages(client, operation):
    try:
        return list(client.get_paginator(operation).paginate())
    except (ClientError, BotoCoreError):
        return []


def _optional_call(client, operation, **kwargs):
    try:
        return getattr(client, operation)(**kwargs)
    except (ClientError, BotoCoreError):
        return {}


def _refresh_live_aws_state(force: bool = False) -> bool:
    global last_live_error, _last_live_refresh_time
    now = time.time()
    db = _db()
    if not force and (now - _last_live_refresh_time) < LIVE_CACHE_TTL_SECONDS and db.get("nodes"):
        return True

    session = _build_aws_session()
    if not session:
        last_live_error = "No AWS session is configured."
        return False

    try:
        region = session.region_name or "us-east-1"
        orchestrator = AWSDataIngestionOrchestrator(session, region)
        data = orchestrator.execute_full_pipeline()

        db["nodes"] = data["nodes"]
        db["ebs_volumes"] = data["ebs_volumes"]
        db["ebs_snapshots"] = data["ebs_snapshots"]
        db["s3_buckets"] = data["s3_buckets"]
        db["rds_instances"] = data.get("rds_instances", [])
        db["rds_clusters"] = data.get("rds_clusters", [])
        db["rds_manual_snapshots"] = data.get("rds_manual_snapshots", [])
        db["elastic_ips"] = data["elastic_ips"]
        db["nat_gateways"] = data["nat_gateways"]
        db["vpc_endpoints"] = data["vpc_endpoints"]
        db["network_interfaces"] = data["network_interfaces"]
        db["load_balancers"] = data.get("load_balancers", [])
        db["security_groups"] = data["security_groups"]
        for sg in db["security_groups"]:
            if sg.get("group_id") in revoked_security_groups:
                sg["is_publicly_exposed"] = False
                sg["exposed_ports"] = []
        db["amis"] = data["amis"]
        db["cloudwatch_log_groups"] = data["cloudwatch_log_groups"]
        db["daily_spend"] = data.get("daily_spend", [])
        db["service_breakdown"] = data.get("service_breakdown", [])
        db["summary"] = data.get("summary", {})
        db["vpc_resources"] = {
            "nat_gateways": data["nat_gateways"],
            "vpc_endpoints": data["vpc_endpoints"],
        }
        db["metadata"]["region"] = region
        db["metadata"]["timestamp"] = datetime.now(timezone.utc).isoformat()
        saved = _saved_credentials() or {}
        db["metadata"]["organization"] = saved.get("account_name", db["metadata"].get("organization", "CloudPulse Fleet"))
        _last_live_refresh_time = time.time()
        return True
    except (ClientError, BotoCoreError) as error:
        if isinstance(error, ClientError):
            error_data = error.response.get("Error", {})
            last_live_error = f"{error_data.get('Code', 'AWS error')}: {error_data.get('Message', str(error))}"
        else:
            last_live_error = f"{type(error).__name__}: {error}"
        return False
    except Exception as error:
        last_live_error = f"{type(error).__name__}: {error}"
        return False


def _ensure_live_aws_state():
    if is_demo_mode:
        return
    if not _build_aws_session():
        raise HTTPException(status_code=401, detail="Connect an AWS account before loading live data.")
    if not _refresh_live_aws_state():
        if _is_permission_denied(last_live_error):
            return
        raise HTTPException(status_code=502, detail=f"AWS data refresh failed: {last_live_error}")


def _node_volume_count(node: dict) -> int:
    return int(node.get("volumes") or 1)


def _normalize_node(node: dict) -> dict:
    db = _db()
    region = db["metadata"].get("region", "us-east-1")
    inst_type = node.get("instance_type") or node.get("type", "t3.micro")
    return {
        **node,
        "type": inst_type,
        "instance_type": inst_type,
        "region": node.get("region") or region,
        "volumes": _node_volume_count(node),
    }


def _frontend_nodes(status: Optional[str] = None, search: Optional[str] = None) -> List[dict]:
    _ensure_live_aws_state()
    db = _db()
    nodes = []
    for node in db["nodes"]:
        normalized = _normalize_node(node)
        if status and normalized["state"].lower() != status.lower():
            continue
        if search and search.lower() not in normalized["instance_id"].lower() and search.lower() not in normalized["name"].lower():
            continue
        nodes.append(normalized)
    return nodes


def _normalize_telemetry_points() -> List[dict]:
    points = []
    for item in _db()["telemetry"]:
        points.append(
            {
                "time": item["timestamp"],
                "cpu": item["cpu_utilization"],
                "mem": item["mem_used_percent"],
                "netIn": item.get("net_in_mb", 0),
                "netOut": item.get("net_out_mb", 0),
                "read": round(item.get("net_in_mb", 0) * 0.08, 2),
                "write": round(item.get("net_out_mb", 0) * 0.06, 2),
            }
        )
    return points


def _live_instance_telemetry(instance_id: str, timeframe: str = "24h") -> Optional[List[dict]]:
    session = _build_aws_session()
    if not session:
        return None

    try:
        cloudwatch = session.client("cloudwatch", config=AWS_CLIENT_CONFIG)
        hours = {"1h": 1, "6h": 6, "24h": 24, "7d": 168}.get(timeframe, 24)
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)
        period = 3600

        def fetch_metric(metric_name: str):
            response = cloudwatch.get_metric_statistics(
                Namespace="AWS/EC2",
                MetricName=metric_name,
                Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
                StartTime=start_time,
                EndTime=end_time,
                Period=period,
                Statistics=["Average"],
            )
            return sorted(response.get("Datapoints", []), key=lambda point: point["Timestamp"])

        cpu_points = fetch_metric("CPUUtilization")
        net_in_points = fetch_metric("NetworkIn")
        net_out_points = fetch_metric("NetworkOut")

        timeline = {}

        for point in cpu_points:
            key = point["Timestamp"].replace(minute=0, second=0, microsecond=0)
            timeline.setdefault(key, {})["cpu"] = round(point.get("Average", 0), 2)
            timeline[key]["time"] = key.strftime("%H:%M")

        for point in net_in_points:
            key = point["Timestamp"].replace(minute=0, second=0, microsecond=0)
            timeline.setdefault(key, {})["netIn"] = round(point.get("Average", 0) / (1024 * 1024), 2)
            timeline[key]["time"] = key.strftime("%H:%M")

        for point in net_out_points:
            key = point["Timestamp"].replace(minute=0, second=0, microsecond=0)
            timeline.setdefault(key, {})["netOut"] = round(point.get("Average", 0) / (1024 * 1024), 2)
            timeline[key]["time"] = key.strftime("%H:%M")

        values = []
        for _, point in sorted(timeline.items(), key=lambda item: item[0]):
            cpu = point.get("cpu", 0)
            net_in = point.get("netIn", 0)
            net_out = point.get("netOut", 0)
            values.append(
                {
                    "time": point["time"],
                    "cpu": cpu,
                    "mem": 0,
                    "netIn": net_in,
                    "netOut": net_out,
                    "read": round(net_in * 0.08, 2),
                    "write": round(net_out * 0.06, 2),
                }
            )

        return values
    except (ClientError, BotoCoreError):
        return None


def _frontend_telemetry(timeframe: str = "24h") -> List[dict]:
    _ensure_live_aws_state()
    first_node = _db()["nodes"][0] if _db()["nodes"] else None
    if not first_node or is_demo_mode or not _build_aws_session():
        return _normalize_telemetry_points()
    live = _live_instance_telemetry(first_node["instance_id"], timeframe)
    return live or _normalize_telemetry_points()


def _frontend_spend() -> List[dict]:
    _ensure_live_aws_state()
    if is_demo_mode or not _build_aws_session():
        return _db().get("spend", [])
    try:
        cost = _build_aws_session().client("ce", config=AWS_CLIENT_CONFIG)
        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=30)
        response = cost.get_cost_and_usage(
            TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
            Granularity="DAILY",
            Metrics=["UnblendedCost"],
        )
        res = [
            {
                "day": item["TimePeriod"]["Start"],
                "aws": round(float(item["Total"].get("UnblendedCost", {}).get("Amount", 0)), 2),
                "gcp": 0,
                "azure": 0,
            }
            for item in response.get("ResultsByTime", [])
        ]
        return res if res else _db().get("spend", [])
    except (ClientError, BotoCoreError):
        return _db().get("spend", [])


def _frontend_alerts() -> List[dict]:
    _ensure_live_aws_state()
    db = _db()
    alerts = []

    for sg in db["security_groups"]:
        if sg["is_publicly_exposed"]:
            alerts.append(
                {
                    "id": f"sg-{sg['group_id']}",
                    "title": f"Public security group: {sg['group_name']}",
                    "desc": f"Ports {', '.join(map(str, sg['exposed_ports']))} are exposed to the internet.",
                    "tone": "red",
                    "tag": "Security",
                }
            )

    for eip in db["elastic_ips"]:
        if eip["is_unattached"]:
            alerts.append(
                {
                    "id": f"eip-{eip['public_ip']}",
                    "title": f"Unattached Elastic IP {eip['public_ip']}",
                    "desc": "Release the address to stop paying idle public IP charges.",
                    "tone": "amber",
                    "tag": "Cost",
                }
            )

    for vol in db["ebs_volumes"]:
        if vol.get("is_orphaned"):
            alerts.append(
                {
                    "id": f"vol-{vol['volume_id']}",
                    "title": f"Orphaned EBS volume {vol['volume_id']}",
                    "desc": "Volume is detached and can likely be deleted after validation.",
                    "tone": "amber",
                    "tag": "Storage",
                }
            )

    return alerts


def _frontend_optimizations() -> List[dict]:
    _ensure_live_aws_state()
    db = _db()
    analysis = FinOpsAnalyzer.evaluate(db)
    recommendations = []

    for f in analysis.get("findings", []):
        ai_rationale = f.get("ai_rationale")
        if not ai_rationale and len(recommendations) < 3 and llm_engine and llm_engine.is_available():
            try:
                ai_rationale = llm_engine.generate_recommendation_rationale(f)
                f["ai_rationale"] = ai_rationale
            except Exception:
                ai_rationale = f.get("description", "")

        recommendations.append(
            {
                "id": f["id"],
                "type": f.get("type", "Cost Optimization"),
                "title": f["title"],
                "desc": f.get("description", ""),
                "save": f"${f.get('monthly_savings', 0.0):.2f}/mo",
                "savings": f.get("monthly_savings", 0.0),
                "effort": f.get("effort", "Low"),
                "action": f.get("action", ""),
                "is_alternative": f.get("is_alternative", False),
                "conflict_note": f.get("conflict_note", ""),
                "alternative_to": f.get("alternative_to"),
                "ai_rationale": ai_rationale or f.get("description", ""),
            }
        )

    return recommendations
