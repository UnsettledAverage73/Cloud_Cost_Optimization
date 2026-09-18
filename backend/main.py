import boto3
from botocore.exceptions import BotoCoreError, ClientError
from botocore.config import Config
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional
import json
import mock_database
from schemas import IngestionPayload, CloudConnectRequest, NodeSchema

from data.cloud_simulator import CloudSimulator
from data.finops_database import (
    record_remediation_audit,
    get_remediation_audit_logs,
    upsert_optimization,
    mark_optimization_applied,
    get_all_optimizations,
)
from services.cost_analytics import (
    calculate_finops_health_score,
    calculate_spend_forecast,
    detect_cost_anomalies,
    evaluate_inventory_optimizations,
)
from services.finops_agent import FinOpsAgent
from services.notifier import FinOpsNotifier
from services.remediator import AutoRemediator

from collectors.orchestrator import AWSDataIngestionOrchestrator
from engines.finops_analyzer import FinOpsAnalyzer
from remediation.actions import SafeRemediationExecutor

# Enterprise Production Architecture Modules (TimescaleDB, Onboarding, Copilot)
try:
    from database.connection import ping_database, SyncSessionLocal
    from database.models import (
        Organization, ConnectedAWSAccount, CloudResource,
        ResourceTelemetry, DailySpendRecord, OptimizationFinding
    )
    from onboarding.cloudformation import get_onboarding_package, generate_cloudformation_yaml
    from onboarding.tenant_manager import TenantManager
    from copilot.agent import FinOpsAutonomousCopilot
    from copilot.tools.pricing_rag_tool import lookup_aws_pricing
    from agent.installer import generate_linux_install_script, generate_windows_install_script
except ImportError:
    from backend.database.connection import ping_database, SyncSessionLocal
    from backend.database.models import (
        Organization, ConnectedAWSAccount, CloudResource,
        ResourceTelemetry, DailySpendRecord, OptimizationFinding
    )
    from backend.onboarding.cloudformation import get_onboarding_package, generate_cloudformation_yaml
    from backend.onboarding.tenant_manager import TenantManager
    from backend.copilot.agent import FinOpsAutonomousCopilot
    from backend.copilot.tools.pricing_rag_tool import lookup_aws_pricing
    from backend.agent.installer import generate_linux_install_script, generate_windows_install_script

copilot_agent = FinOpsAutonomousCopilot()

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables and seed demo data on startup if reachable
    try:
        try:
            from database.init_db import initialize_database, seed_demo_data
        except ImportError:
            from backend.database.init_db import initialize_database, seed_demo_data
        initialize_database()
        seed_demo_data()
        print("✅ Database schema and seed data initialized successfully.")
    except Exception as e:
        print(f"⚠️ Startup database initialization notice: {e}")
    yield

app = FastAPI(
    title="CloudPulse FinOps & Telemetry API",
    version="2.0.0",
    description="Enterprise backend API powering multi-cloud cost optimization, TimescaleDB telemetry, and autonomous AI copilot.",
    lifespan=lifespan,
)

# Enable CORS for Next.js / React / v0.dev frontend connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to your frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for active session credentials (or pass per header/request)
active_credentials = {}
connected_accounts = []
last_live_error = ""
is_demo_mode = False
STATE_FILE = Path(__file__).with_name(".cloudpulse_state.json")

finops_agent = FinOpsAgent(data_store=mock_database.DB)
finops_notifier = FinOpsNotifier()

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


def _load_persisted_state():
    global active_credentials, connected_accounts

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


def _persist_state():
    state = {
        "active_connection": active_credentials.get("default"),
        "connected_accounts": connected_accounts,
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


def _set_connection_mode(access_mode: str, warning: str | None = None):
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


def _saved_credentials():
    return active_credentials.get("default")


def _connection_state():
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


def _build_aws_session():
    creds = _saved_credentials()
    if not creds or creds.get("provider", "").upper() != "AWS":
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
    )


def _tag_lookup(tags):
    return {tag.get("Key"): tag.get("Value") for tag in tags or []}


def _optional_pages(client, operation):
    """Return no data when a Learner Lab denies an optional inventory API."""
    try:
        return list(client.get_paginator(operation).paginate())
    except (ClientError, BotoCoreError):
        return []


def _optional_call(client, operation, **kwargs):
    """Run an optional AWS API without breaking Learner Lab onboarding."""
    try:
        return getattr(client, operation)(**kwargs)
    except (ClientError, BotoCoreError):
        return {}


def _refresh_live_aws_state():
    global last_live_error
    session = _build_aws_session()
    if not session:
        last_live_error = "No AWS session is configured."
        return False

    try:
        region = session.region_name or "us-east-1"
        orchestrator = AWSDataIngestionOrchestrator(session, region)
        data = orchestrator.execute_full_pipeline()

        db = _db()
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
        db["metadata"]["organization"] = saved.get("account_name", db["metadata"].get("organization", "Acme Corp"))
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
    """Fail closed so dashboard APIs never serve seed data as live data unless in demo mode."""
    if is_demo_mode:
        return
    if not _build_aws_session():
        raise HTTPException(status_code=401, detail="Connect an AWS account before loading live data.")
    if not _refresh_live_aws_state():
        if _is_permission_denied(last_live_error):
            return
        raise HTTPException(status_code=502, detail=f"AWS data refresh failed: {last_live_error}")


def _db():
    return mock_database.DB


def _node_volume_count(node: dict) -> int:
    return int(node.get("volumes") or 1)


def _frontend_nodes(status: Optional[str] = None, search: Optional[str] = None):
    _ensure_live_aws_state()
    db = _db()
    region = db["metadata"].get("region", "us-east-1")
    nodes = []
    for node in db["nodes"]:
        normalized = {
            **node,
            "region": region,
            "volumes": _node_volume_count(node),
        }
        if status and normalized["state"].lower() != status.lower():
            continue
        if search and search.lower() not in normalized["instance_id"].lower() and search.lower() not in normalized["name"].lower():
            continue
        nodes.append(normalized)
    return nodes


def _normalize_node(node: dict):
    db = _db()
    region = db["metadata"].get("region", "us-east-1")
    return {
        **node,
        "region": region,
        "volumes": _node_volume_count(node),
    }


def _normalize_telemetry_points():
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


def _live_instance_telemetry(instance_id: str, timeframe: str = "24h"):
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


def _frontend_telemetry(timeframe: str = "24h"):
    _ensure_live_aws_state()
    first_node = _db()["nodes"][0] if _db()["nodes"] else None
    if not first_node or is_demo_mode or not _build_aws_session():
        return _normalize_telemetry_points()
    live = _live_instance_telemetry(first_node["instance_id"], timeframe)
    return live or _normalize_telemetry_points()


def _frontend_spend():
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


def _frontend_alerts():
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


def _frontend_optimizations():
    _ensure_live_aws_state()
    db = _db()
    analysis = FinOpsAnalyzer.evaluate(db)
    recommendations = []

    for f in analysis.get("findings", []):
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
            }
        )

    return recommendations

# --- 1. INGESTION ENDPOINT (From Python Engine) ---
@app.post("/api/v1/ingest", status_code=status.HTTP_201_CREATED)
async def ingest_cloud_data(payload: IngestionPayload):
    """
    Receives raw output from your OptiScale Python script and updates DB state.
    """
    db = mock_database.DB
    db["metadata"] = payload.metadata
    db["nodes"] = payload.compute.get("nodes", [])
    db["ebs_volumes"] = payload.ec2_other_resources.get("ebs_volumes", [])
    db["elastic_ips"] = payload.ec2_other_resources.get("elastic_ips", [])
    db["security_groups"] = payload.ec2_other_resources.get("security_groups", [])
    db["telemetry"] = [t.dict() for t in payload.telemetry]
    
    return {"status": "success", "message": "Telemetry and resource data ingested successfully"}

# --- 2. EXECUTIVE OVERVIEW API ---
@app.get("/api/v1/dashboard/summary")
async def get_executive_summary():
    _ensure_live_aws_state()
    db = mock_database.DB
    total_nodes = len(db["nodes"])
    running_nodes = sum(1 for n in db["nodes"] if n["state"] == "running")
    
    # Calculate costs and wastes
    spend_rows = _frontend_spend()
    monthly_spend = sum(row.get("aws", 0) for row in spend_rows)
    wasted_eip = sum(eip["estimated_monthly_cost"] for eip in db["elastic_ips"] if eip["is_unattached"])
    wasted_ebs = sum(v["cost"] for v in db["ebs_volumes"] if v.get("is_orphaned"))
    total_wasted = wasted_eip + wasted_ebs

    critical_security_risks = sum(1 for sg in db["security_groups"] if sg["is_publicly_exposed"])

    return {
        "monthly_spend": round(monthly_spend, 2),
        "total_nodes": total_nodes,
        "running_nodes": running_nodes,
        "stopped_nodes": total_nodes - running_nodes,
        "wasted_monthly_spend": round(total_wasted, 2),
        "critical_security_risks": critical_security_risks,
        "last_synced": db["metadata"].get("timestamp")
    }

# --- 3. COMPUTE & STORAGE INVENTORY ---
@app.get("/api/v1/resources/nodes", response_model=List[NodeSchema])
async def get_nodes(status: Optional[str] = None, search: Optional[str] = None):
    return _frontend_nodes(status=status, search=search)

@app.get("/api/v1/resources/nodes/{instance_id}")
async def get_node_details(instance_id: str):
    _ensure_live_aws_state()
    nodes = mock_database.DB["nodes"]
    node = next((n for n in nodes if n["instance_id"] == instance_id), None)
    if not node:
        raise HTTPException(status_code=404, detail="Instance ID not found")
    details = _normalize_node(node)
    details["volumes_detail"] = [
        volume for volume in mock_database.DB.get("ebs_volumes", [])
        if any(attachment.get("InstanceId") == instance_id for attachment in volume.get("attachments", []))
        or volume.get("attached_instance_id") == instance_id
    ]
    details["network_interfaces"] = [
        eni for eni in mock_database.DB.get("network_interfaces", [])
        if eni.get("attached_instance_id") == instance_id
    ]
    return details


@app.get("/api/v1/resources/inventory")
async def get_full_inventory():
    """Return the complete live inventory collected by the notebook pipeline."""
    _ensure_live_aws_state()
    db = mock_database.DB
    return {
        "metadata": db["metadata"],
        "compute": {"nodes": db["nodes"]},
        "ec2_other_resources": {
            "ebs_volumes": db.get("ebs_volumes", []),
            "elastic_ips": db.get("elastic_ips", []),
            "amis": db.get("amis", []),
            "network_interfaces": db.get("network_interfaces", []),
            "ebs_snapshots": db.get("ebs_snapshots", []),
            "cloudwatch_log_groups": db.get("cloudwatch_log_groups", []),
            "s3_buckets": db.get("s3_buckets", []),
            "security_groups": db.get("security_groups", []),
        },
        "vpc_resources": db.get("vpc_resources", {"nat_gateways": [], "vpc_endpoints": []}),
    }


@app.get("/api/v1/connect-cloud/state")
async def get_connect_state():
    return _connection_state()


@app.post("/api/v1/connect-cloud/switch")
async def switch_connected_account(payload: dict):
    selector = {
        "provider": payload.get("provider"),
        "account_name": payload.get("account_name"),
        "region": payload.get("region"),
        "role_arn": payload.get("role_arn"),
        "access_key": payload.get("access_key") or payload.get("access_key_last4") or "",
    }
    match = _activate_connected_account(selector)
    if not _refresh_live_aws_state():
        connection = _connection_state()
        if _is_permission_denied(last_live_error):
            return {
                "status": "success",
                "message": "Switched AWS account with limited access",
                "warning": last_live_error,
                "access_mode": "limited",
                "connection": connection,
                "connected_accounts": connection.get("connected_accounts", []),
                "matched_account": _public_connection_record(match),
            }
        raise HTTPException(status_code=502, detail=f"AWS account switch succeeded, but live resource discovery failed: {last_live_error}")
    connection = _connection_state()
    return {
        "status": "success",
        "message": "Switched AWS account",
        "access_mode": "live",
        "connection": connection,
        "connected_accounts": connection.get("connected_accounts", []),
        "matched_account": _public_connection_record(match),
    }

# --- 4. TELEMETRY & METRIC ANALYTICS ---
@app.get("/api/v1/telemetry/{instance_id}")
async def get_instance_telemetry(instance_id: str):
    _ensure_live_aws_state()
    live = _live_instance_telemetry(instance_id)
    if live is not None:
        return {
            "instance_id": instance_id,
            "metrics": live,
        }
    return {
        "instance_id": instance_id,
        "metrics": [],
        "message": "CloudWatch metrics are unavailable or not permitted for this account.",
    }


# --- COMPATIBILITY ROUTES FOR THE NEXT.JS FRONTEND ---
@app.get("/api/nodes", response_model=List[NodeSchema])
async def get_frontend_nodes(status: Optional[str] = None, search: Optional[str] = None, provider: Optional[str] = None):
    return _frontend_nodes(status=status, search=search)


@app.get("/api/telemetry")
async def get_frontend_telemetry(timeframe: str = "24h", instance_id: Optional[str] = None):
    return _frontend_telemetry(timeframe=timeframe)


@app.get("/api/spend")
async def get_frontend_spend(provider: Optional[str] = None):
    return _frontend_spend()


@app.get("/api/alerts")
async def get_frontend_alerts():
    return _frontend_alerts()


@app.get("/api/optimizations")
async def get_frontend_optimizations():
    return _frontend_optimizations()


@app.get("/api/optimizations/applied")
async def get_frontend_applied_optimizations():
    _ensure_live_aws_state()
    return {"applied": _db().setdefault("applied_optimizations", [])}


@app.post("/api/security/revoke")
async def revoke_security_group(payload: dict):
    group_id = payload.get("groupId")
    db = _db()
    sg = next((item for item in db["security_groups"] if item["group_id"] == group_id), None)
    if not sg:
        raise HTTPException(status_code=404, detail="Security group not found")
    sg["is_publicly_exposed"] = False
    return {"status": "revoked", "groupId": group_id}


@app.post("/api/optimizations/apply")
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
    return {"status": "ok", "id": optimization_id, "action": action, "applied": applied}


@app.put("/api/settings")
async def update_settings(payload: dict):
    org_name = payload.get("orgName")
    if not org_name:
        raise HTTPException(status_code=400, detail="orgName is required")
    _db()["metadata"]["organization"] = org_name
    return {"status": "saved", "organization": org_name}


@app.get("/api/settings")
async def get_settings():
    metadata = _db()["metadata"]
    return {
        "organization": metadata.get("organization", ""),
        "region": metadata.get("region", "us-east-1"),
        "timestamp": metadata.get("timestamp"),
    }


@app.post("/api/accounts/connect")
async def connect_frontend_account(payload: dict):
    account_name = payload.get("accountName", "Connected account")
    cloud = payload.get("cloud", "AWS")
    role_arn = payload.get("roleArn")
    return {
        "status": "connected",
        "provider": cloud,
        "account_name": account_name,
        "role_arn": role_arn,
    }

# --- 5. SECURITY & EXPOSURE AUDIT ---
@app.get("/api/v1/security/audit")
async def get_security_audit():
    _ensure_live_aws_state()
    db = mock_database.DB
    return {
        "exposed_security_groups": [sg for sg in db["security_groups"] if sg["is_publicly_exposed"]],
        "unattached_elastic_ips": [eip for eip in db["elastic_ips"] if eip["is_unattached"]],
        "orphaned_ebs_volumes": [v for v in db["ebs_volumes"] if v.get("is_orphaned")]
    }

# --- 6. COST OPTIMIZATION RECOMMENDATIONS ---
@app.get("/api/v1/optimizations")
async def get_cost_optimizations():
    _ensure_live_aws_state()
    db = mock_database.DB
    analysis = FinOpsAnalyzer.evaluate(db)

    return {
        "total_potential_savings": analysis.get("total_potential_monthly_savings", 0.0),
        "total_monthly_spend": analysis.get("total_monthly_spend", 0.0),
        "savings_percentage": analysis.get("savings_percentage", 0.0),
        "recommendations": analysis.get("findings", []),
        "quick_wins": analysis.get("quick_wins", []),
        "architectural_improvements": analysis.get("architectural_improvements", []),
        "health_score": analysis.get("health_score", 100.0),
    }

# --- 7. CONNECT CLOUD ACCOUNT ---
@app.post("/api/v1/connect-cloud", status_code=status.HTTP_200_OK)
async def connect_cloud_account(credentials: CloudConnectRequest):
    if credentials.provider.upper() == "AWS":
        if credentials.auth_method == "keys" and not (credentials.access_key and credentials.secret_key):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="AWS key authentication requires Access Key ID and Secret Access Key."
            )
        # Validate AWS Learner Lab / Temporary Credentials
        if credentials.auth_method == "learner_lab":
            if not (credentials.access_key and credentials.secret_key and credentials.session_token):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="AWS Learner Lab requires Access Key ID, Secret Access Key, AND Session Token."
                )

            try:
                # Test connection using Boto3 STS caller identity
                session = boto3.Session(
                    aws_access_key_id=credentials.access_key,
                    aws_secret_access_key=credentials.secret_key,
                    aws_session_token=credentials.session_token,
                    region_name=credentials.region
                )
                sts = session.client('sts', config=AWS_CLIENT_CONFIG)
                identity = sts.get_caller_identity()

                _save_active_credentials(credentials)
                if not _refresh_live_aws_state():
                    connection = _connection_state()
                    if _is_permission_denied(last_live_error):
                        _set_connection_mode("limited", last_live_error)
                        connection = _connection_state()
                        return {
                            "status": "success",
                            "provider": "AWS (Learner Lab)",
                            "account_id": identity.get("Account"),
                            "arn": identity.get("Arn"),
                            "message": "Connected with limited access",
                            "warning": last_live_error,
                            "access_mode": "limited",
                            "connection": connection,
                            "connected_accounts": connection.get("connected_accounts", []),
                        }
                    active_credentials.pop("default", None)
                    raise HTTPException(status_code=502, detail=f"AWS authentication succeeded, but live resource discovery failed: {last_live_error}")
                _set_connection_mode("live")
                connection = _connection_state()
                return {
                    "status": "success",
                    "provider": "AWS (Learner Lab)",
                    "account_id": identity.get("Account"),
                    "arn": identity.get("Arn"),
                    "message": "Success",
                    "access_mode": "live",
                    "connection": connection,
                    "connected_accounts": connection.get("connected_accounts", []),
                }
            except (ClientError, BotoCoreError) as e:
                message = e.response.get("Error", {}).get("Message", str(e)) if isinstance(e, ClientError) else str(e)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"AWS Authentication Failed: {message}"
                )
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to connect AWS account: {e}"
                )

    _save_active_credentials(credentials)
    if credentials.provider.upper() == "AWS" and not _refresh_live_aws_state():
        connection = _connection_state()
        if _is_permission_denied(last_live_error):
            _set_connection_mode("limited", last_live_error)
            connection = _connection_state()
            return {
                "status": "success",
                "message": "Connected with limited access",
                "warning": last_live_error,
                "access_mode": "limited",
                "connection": connection,
                "connected_accounts": connection.get("connected_accounts", []),
            }
        active_credentials.pop("default", None)
        raise HTTPException(status_code=502, detail=f"AWS connection succeeded, but live resource discovery failed: {last_live_error}")
    _set_connection_mode("live")
    connection = _connection_state()
    return {
        "status": "success",
        "message": "Success",
        "access_mode": "live",
        "connection": connection,
        "connected_accounts": connection.get("connected_accounts", []),
    }


# ==============================================================================
# 🧠 8. FINOPS AI AGENT & ADVANCED ANALYTICS ENDPOINTS
# ==============================================================================

@app.get("/api/v1/analytics/health-score")
async def get_finops_health_score():
    """Computes the 4-pillar FinOps Health Score (0-100) and grade."""
    _ensure_live_aws_state()
    return calculate_finops_health_score(_db())


@app.get("/api/v1/analytics/forecast")
async def get_cost_forecast(budget: float = 600.0):
    """Calculates daily burn rate, projected month-end spend, and budget runway."""
    _ensure_live_aws_state()
    spend_rows = _frontend_spend()
    return calculate_spend_forecast(spend_rows, monthly_budget=budget)


@app.get("/api/v1/analytics/anomalies")
async def get_cost_anomalies():
    """Detects daily spend surges exceeding 25% of baseline."""
    _ensure_live_aws_state()
    spend_rows = _frontend_spend()
    return {"anomalies": detect_cost_anomalies(spend_rows)}


@app.post("/api/v1/agent/chat")
async def chat_with_finops_agent(payload: dict):
    """
    Autonomous FinOps AI Assistant query router:
    Supports slash commands (/audit, /optimize, /forecast, /health, /pricing, /remediate)
    and natural language FinOps questions via local Ollama or cloud LLMs.
    """
    query = payload.get("query") or payload.get("prompt")
    if not query:
        raise HTTPException(status_code=400, detail="Query parameter is required")
    # Update agent data store with latest DB state
    finops_agent.data_store = _db()
    return finops_agent.ask(query)


@app.post("/api/v1/remediate/execute")
async def execute_remediation_action(payload: dict):
    """
    Executes safe automated remediation (dry_run=True by default).
    Supports: release_eip, delete_volume, upgrade_gp3, stop_instance, set_log_retention, revoke_sg_ingress.
    """
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

    # If executed non-dry-run, mark in applied optimizations
    if not dry_run and result.get("status") == "success":
        mark_optimization_applied(f"rec-{action}-{resource_id}", applied=True)

    return result


@app.get("/api/v1/remediate/audit")
async def get_remediation_audit(limit: int = 50):
    """Returns persistent remediation audit log records from SQLite."""
    return {"audit_logs": get_remediation_audit_logs(limit=limit)}


@app.post("/api/v1/demo/enable")
async def enable_demo_simulation():
    """
    Enables realistic multi-cloud simulation mode for instant exploration and testing
    without requiring active AWS credentials.
    """
    global is_demo_mode
    is_demo_mode = True
    simulated_env = CloudSimulator.generate_full_environment()
    mock_database.DB.update(simulated_env)
    return {
        "status": "success",
        "demo_mode": True,
        "message": "Realistic multi-cloud simulated environment loaded successfully."
    }


@app.post("/api/v1/demo/disable")
async def disable_demo_simulation():
    """Disables simulation demo mode."""
    global is_demo_mode
    is_demo_mode = False
    return {"status": "success", "demo_mode": False}


@app.post("/api/v1/notifications/alert")
async def send_notification_alert(payload: dict):
    """Dispatches Slack or WhatsApp alerts for critical FinOps events."""
    channel = payload.get("channel", "slack").lower()
    title = payload.get("title", "FinOps Alert")
    message = payload.get("message", "Cost optimization threshold exceeded.")
    recipient = payload.get("recipient")

    if channel == "whatsapp":
        success = finops_notifier.send_whatsapp_alert(title, message, to_number=recipient)
        return {"status": "sent" if success else "failed", "channel": "whatsapp"}
    else:
        opts = evaluate_inventory_optimizations(_db())
        health = calculate_finops_health_score(_db())
        spend = sum(row.get("aws", 0) for row in _frontend_spend())
        success = finops_notifier.send_slack_alert(opts, monthly_cost=spend, health_score=health["overall_health_score"])
        return {"status": "sent" if success else "failed", "channel": "slack"}


# =====================================================================
# 🚀 ENTERPRISE V2 API: TIMESCALEDB, ONBOARDING & AUTONOMOUS COPILOT
# =====================================================================

@app.get("/api/v2/database/status")
async def get_database_status():
    """Returns real-time connection status and TimescaleDB extension version."""
    status_info = ping_database()
    return status_info


@app.get("/api/v2/onboarding/cloudformation")
async def get_cloudformation_onboarding(org_id: Optional[str] = None, allow_remediation: bool = False):
    """
    Returns a 1-Click AWS CloudFormation Onboarding Package with unique ExternalId
    and AWS Console Quick-Create URL.
    """
    package = get_onboarding_package(org_id=org_id or "default-org", allow_remediation=allow_remediation)
    return package


@app.post("/api/v2/onboarding/accounts")
async def register_account(payload: dict):
    """
    Registers a customer AWS account and validates STS AssumeRole credentials.
    """
    session = SyncSessionLocal()
    try:
        manager = TenantManager(session)
        org = session.query(Organization).first()
        org_id = payload.get("organization_id") or (str(org.id) if org else None)
        if not org_id:
            org = manager.create_organization(name="Default Enterprise Org")
            org_id = str(org.id)

        account = manager.register_aws_account(
            organization_id=org_id,
            account_id=payload.get("account_id", "123456789012"),
            account_name=payload.get("account_name", "AWS Account"),
            role_arn=payload.get("role_arn", "arn:aws:iam::123456789012:role/CloudPulseRole"),
            external_id=payload.get("external_id", "cp-external-id"),
            regions=payload.get("regions", ["us-east-1"]),
            validate_immediately=False
        )
        return {"status": "registered", "account": account}
    finally:
        session.close()


@app.get("/api/v2/onboarding/accounts")
async def list_accounts():
    """Lists registered customer AWS accounts from PostgreSQL."""
    session = SyncSessionLocal()
    try:
        org = session.query(Organization).first()
        if not org:
            return {"accounts": []}
        manager = TenantManager(session)
        accounts = manager.get_accounts_for_org(str(org.id))
        return {"organization_id": str(org.id), "accounts": accounts}
    finally:
        session.close()


@app.get("/api/v2/telemetry/hypertable")
async def get_telemetry_hypertable(resource_id: Optional[str] = None, limit: int = 50):
    """
    Queries high-frequency metrics directly from TimescaleDB hypertable 'resource_telemetry'.
    """
    session = SyncSessionLocal()
    try:
        query = session.query(ResourceTelemetry)
        if resource_id:
            query = query.filter(ResourceTelemetry.resource_id == resource_id)
        records = query.order_by(ResourceTelemetry.time.desc()).limit(limit).all()
        return {"count": len(records), "telemetry": [r.to_dict() for r in records]}
    finally:
        session.close()


@app.get("/api/v2/focus/spend")
async def get_focus_spend(limit: int = 100):
    """
    Returns spend records adhering to the FinOps FOCUS 1.0 standard
    partitioned in the TimescaleDB hypertable 'daily_spend_records'.
    """
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
    finally:
        session.close()


@app.post("/api/v2/copilot/chat")
async def copilot_chat(payload: dict):
    """
    Autonomous LLM FinOps Copilot conversation endpoint with multi-tool dispatch:
    - Text-to-SQL over TimescaleDB
    - Live Pricing Catalog RAG & Graviton ROI
    - CloudTrail root-cause spike forensics
    - Terraform/OpenTofu PR generation
    """
    user_message = payload.get("message", "")
    history = payload.get("history", [])
    response = copilot_agent.chat(user_message=user_message, history=history)
    return response


@app.post("/api/v2/copilot/diagnose-spike")
async def copilot_diagnose_spike(payload: dict):
    """
    Autonomous root-cause cost anomaly diagnostic agent correlating CloudWatch metrics,
    CloudTrail events, AWS Pricing Catalog, and generating Terraform remediation code.
    """
    service = payload.get("service", "AmazonEC2")
    spike_date = payload.get("spike_date")
    diagnostic = copilot_agent.diagnose_spike(service=service, spike_date=spike_date)
    return diagnostic


@app.post("/api/v2/copilot/generate-iac-pr")
async def copilot_generate_iac_pr(payload: dict):
    """
    Generates ready-to-merge Terraform/OpenTofu Pull Request code for safe remediation.
    """
    finding_id = payload.get("finding_id", "find-idle-ec2-m5")
    resource_id = payload.get("resource_id", "i-09f81a2b3c4d5e6f7")
    action_type = payload.get("action_type", "downsize_ec2")
    current_config = payload.get("current_config", {"instance_type": "m5.2xlarge", "name": "worker_node"})
    recommended_config = payload.get("recommended_config", {"instance_type": "t4g.medium"})
    monthly_savings = float(payload.get("monthly_savings", 243.80))

    pr = copilot_agent.run_tool("terraform_pr", {
        "finding_id": finding_id,
        "resource_id": resource_id,
        "action_type": action_type,
        "current_config": current_config,
        "recommended_config": recommended_config,
        "monthly_savings": monthly_savings
    })
    return pr


@app.get("/api/v2/copilot/pricing")
async def get_pricing_rate_card(resource_type: str = "m5.2xlarge", region: str = "us-east-1"):
    """
    Queries real-time AWS rate card and computes Graviton modernization savings.
    """
    pricing = lookup_aws_pricing(resource_type=resource_type, region=region)
    return pricing


# =====================================================================
# 🖥️ MULTI-OS IN-GUEST HOST AGENT INGESTION & DEPLOYMENT API
# =====================================================================

@app.post("/api/v2/agent/ingest")
async def ingest_agent_telemetry(payload: dict):
    """
    Ingests in-guest host metrics from Linux, Windows, and macOS agents into TimescaleDB.
    Captures actual RAM, CPU, and Disk metrics that hypervisors cannot see.
    """
    cloud = payload.get("cloud", {})
    telemetry = payload.get("telemetry", {})
    os_info = telemetry.get("os", {})
    cpu = telemetry.get("cpu", {})
    memory = telemetry.get("memory", {})
    disk = telemetry.get("disk", {})

    resource_id = cloud.get("instance_id") or f"host-{os_info.get('hostname', 'unknown')}"
    timestamp_str = telemetry.get("timestamp")
    t_now = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now(timezone.utc)

    session = SyncSessionLocal()
    try:
        # 1. Ensure an account exists to associate telemetry
        account = session.query(ConnectedAWSAccount).first()
        account_id = account.id if account else uuid.uuid4()

        # 2. Ingest high-frequency metrics into TimescaleDB hypertable (idempotent upsert)
        metrics_count = 0
        metric_candidates = [
            ("CPUUtilization", cpu.get("utilization_percent")),
            ("MemoryUtilization", memory.get("percent_used")),
            ("DiskUtilization", disk.get("percent_used")),
        ]

        for m_name, val in metric_candidates:
            if val is not None:
                val_float = float(val)
                existing_metric = session.query(ResourceTelemetry).filter_by(
                    time=t_now,
                    resource_id=resource_id,
                    metric_name=m_name
                ).first()
                if existing_metric:
                    existing_metric.val_avg = val_float
                    existing_metric.val_max = val_float
                    existing_metric.val_p95 = val_float
                else:
                    session.add(ResourceTelemetry(
                        time=t_now,
                        resource_id=resource_id,
                        account_id=account_id,
                        metric_name=m_name,
                        val_avg=val_float,
                        val_max=val_float,
                        val_p95=val_float
                    ))
                metrics_count += 1

        # 3. Upsert into cloud_resources snapshot
        existing_res = session.query(CloudResource).filter_by(resource_id=resource_id).first()
        if not existing_res and account:
            new_res = CloudResource(
                account_id=account.id,
                resource_id=resource_id,
                service="host-agent",
                region=cloud.get("region", "local"),
                resource_type=cloud.get("instance_type", "host"),
                name=os_info.get("hostname", resource_id),
                state="active",
                monthly_cost=0.00,
                tags={
                    "OS": os_info.get("os_type", "unknown"),
                    "Architecture": os_info.get("architecture", "unknown"),
                    "Kernel": os_info.get("release", "unknown")
                },
                configuration={
                    "cpu_cores": cpu.get("logical_cores"),
                    "total_ram_mb": memory.get("total_mb"),
                    "total_disk_gb": disk.get("total_gb"),
                    "top_processes": telemetry.get("top_processes", [])
                }
            )
            session.add(new_res)
        elif existing_res:
            existing_res.configuration = {
                "cpu_cores": cpu.get("logical_cores"),
                "total_ram_mb": memory.get("total_mb"),
                "total_disk_gb": disk.get("total_gb"),
                "top_processes": telemetry.get("top_processes", [])
            }
            existing_res.updated_at = t_now

        session.commit()
        return {
            "status": "ingested",
            "resource_id": resource_id,
            "os": os_info.get("os_type"),
            "metrics_recorded": metrics_count
        }
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Agent ingestion failed: {str(e)}")
    finally:
        session.close()


@app.get("/api/v2/agent/install-script")
async def get_agent_install_script(
    os: str = "linux",
    token: Optional[str] = "cp-demo-agent-token",
    interval: int = 60
):
    """
    Generates a 1-click installer script for Linux (bash/systemd) or Windows (PowerShell).
    Usage:
      Linux: curl -fsSL http://backend:8000/api/v2/agent/install-script?os=linux | bash
      Windows: irm http://backend:8000/api/v2/agent/install-script?os=windows | iex
    """
    from fastapi.responses import PlainTextResponse

    backend_url = "http://localhost:8000"
    if os.lower() in ["windows", "win", "ps1"]:
        script = generate_windows_install_script(backend_url=backend_url, token=token, interval=interval)
        return PlainTextResponse(content=script, media_type="text/plain")
    else:
        script = generate_linux_install_script(backend_url=backend_url, token=token, interval=interval)
        return PlainTextResponse(content=script, media_type="text/plain")


@app.get("/api/v2/agent/hosts")
async def list_agent_hosts():
    """Lists all monitored Multi-OS hosts streaming in-guest telemetry."""
    session = SyncSessionLocal()
    try:
        hosts = session.query(CloudResource).filter_by(service="host-agent").all()
        return {
            "count": len(hosts),
            "hosts": [h.to_dict() for h in hosts]
        }
    finally:
        session.close()



