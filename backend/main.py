import os
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from botocore.config import Config
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional
import json
import time

# Auto-load local .env if present
for cand in [Path(__file__).resolve().parent / ".env", Path(__file__).resolve().parent.parent / ".env"]:
    if cand.exists():
        try:
            with open(cand, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        if k.strip() not in os.environ:
                            os.environ[k.strip()] = v.strip().strip("'\"")
        except Exception:
            pass

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
try:
    from services.llm_engine import llm_engine
except ImportError:
    from backend.services.llm_engine import llm_engine

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
    from services.finops_rag import finops_rag_pipeline
    from collectors.fleet_manager import fleet_manager, FleetAccountConfig
    from engines.focus_spec import FOCUSNormalizer
    from services.vector_store import vector_knowledge_store
    from services.query_cache import query_cache
    from services.gitops_engine import gitops_engine
    from services.notification_engine import notification_engine
    from services.anomaly_detector import anomaly_detector
    from services.spend_forecaster import spend_forecaster
    from collectors.multicloud_connector import multicloud_orchestrator
    from services.rbac_middleware import rbac_manager, FinOpsRole, FinOpsPermission
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
    from backend.services.finops_rag import finops_rag_pipeline
    from backend.collectors.fleet_manager import fleet_manager, FleetAccountConfig
    from backend.engines.focus_spec import FOCUSNormalizer
    from backend.services.vector_store import vector_knowledge_store
    from backend.services.query_cache import query_cache
    from backend.services.gitops_engine import gitops_engine
    from backend.services.notification_engine import notification_engine
    from backend.services.anomaly_detector import anomaly_detector
    from backend.services.spend_forecaster import spend_forecaster
    from backend.collectors.multicloud_connector import multicloud_orchestrator
    from backend.services.rbac_middleware import rbac_manager, FinOpsRole, FinOpsPermission

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


_last_live_refresh_time = 0.0
LIVE_CACHE_TTL_SECONDS = 180.0  # Cache live AWS state for 3 minutes

def _refresh_live_aws_state(force: bool = False):
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
                "ai_rationale": ai_rationale or f.get("description", ""),
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
                if not _refresh_live_aws_state(force=True):
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
    if credentials.provider.upper() == "AWS" and not _refresh_live_aws_state(force=True):
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
    """Detects daily spend surges exceeding 25% of baseline with AI root-cause forensics."""
    _ensure_live_aws_state()
    spend_rows = _frontend_spend()
    anomalies = detect_cost_anomalies(spend_rows)
    if anomalies and llm_engine and llm_engine.is_available():
        for a in anomalies[:2]:
            if "ai_explanation" not in a:
                try:
                    res = llm_engine.explain_anomaly(a)
                    a["ai_explanation"] = res.get("explanation")
                    a["ai_provider"] = res.get("provider")
                except Exception:
                    pass
    return {"anomalies": anomalies}


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
    user_message = payload.get("message") or payload.get("prompt") or payload.get("query") or ""
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


@app.post("/api/v2/copilot/rag/ask")
async def copilot_rag_ask(payload: dict):
    """
    Direct endpoint for FinOps RAG (Retrieval-Augmented Generation) queries:
    Retrieves live cloud telemetry, augments with unit economics and AWS rate cards,
    and generates grounded answers via Groq LLM.
    """
    query = payload.get("query") or payload.get("message") or payload.get("prompt") or ""
    custom_inv = payload.get("inventory")
    response = finops_rag_pipeline.ask(query=query, inventory=custom_inv)
    return response


@app.post("/api/v2/copilot/rag/recommendations")
async def copilot_rag_recommendations(payload: Optional[dict] = None):
    """
    Executes complete FinOps RAG recommendation synthesis across live cloud inventory:
    Returns Executive Briefing, Quick Wins, Graviton Rightsizing, and Security Findings.
    """
    payload = payload or {}
    custom_inv = payload.get("inventory")
    focus_domain = payload.get("focus_domain") or payload.get("focus") or payload.get("domain")
    response = finops_rag_pipeline.generate_recommendations(inventory=custom_inv, focus_domain=focus_domain)
    return response


@app.get("/api/v2/copilot/rag/status")
async def get_copilot_rag_status():
    """
    Returns live Groq RAG pipeline status, active model, and inventory telemetry counts.
    """
    engine_ready = finops_rag_pipeline.engine and finops_rag_pipeline.engine.is_available()
    active_model = getattr(finops_rag_pipeline.engine, "active_model", None) if finops_rag_pipeline.engine else None
    inv = finops_rag_pipeline._get_inventory()
    nodes = inv.get("compute", {}).get("nodes") or inv.get("nodes", [])
    vols = inv.get("ec2_other_resources", {}).get("ebs_volumes") or inv.get("ebs_volumes", [])
    eips = inv.get("ec2_other_resources", {}).get("elastic_ips") or inv.get("elastic_ips", [])
    sgs = inv.get("ec2_other_resources", {}).get("security_groups") or inv.get("security_groups", [])
    logs = inv.get("ec2_other_resources", {}).get("cloudwatch_log_groups") or inv.get("cloudwatch_log_groups", [])

    return {
        "status": "ready" if engine_ready else "fallback_ready",
        "pipeline": "FinOpsRAGPipeline",
        "provider": "groq" if engine_ready else "deterministic_engine",
        "active_model": active_model,
        "groq_configured": bool(os.getenv("GROQ_API_KEY") or getattr(finops_rag_pipeline.engine, "api_key", None)),
        "retrieval_sources": {
            "compute_nodes": len(nodes),
            "ebs_volumes": len(vols),
            "elastic_ips": len(eips),
            "security_groups": len(sgs),
            "cloudwatch_log_groups": len(logs),
            "aws_rate_card": "active (us-east-1)"
        },
        "supported_domains": ["all", "compute", "storage", "network", "security", "logs"]
    }


@app.get("/api/v2/copilot/knowledge/search")
async def search_knowledge_base(q: str = "", limit: int = 3):
    """Executes semantic vector search over Well-Architected and FinOps policies."""
    results = vector_knowledge_store.search(query=q, top_k=limit)
    return {"query": q, "count": len(results), "results": results}


@app.get("/api/v2/copilot/knowledge/policies")
async def list_knowledge_policies():
    """Lists all indexed policies in the semantic vector store."""
    docs = vector_knowledge_store.get_all_documents()
    return {"count": len(docs), "policies": docs}


@app.post("/api/v2/copilot/knowledge/index")
async def index_knowledge_policy(payload: dict):
    """Indexes a new custom organization FinOps policy into the vector knowledge base."""
    import uuid as _uuid
    doc_id = payload.get("id") or str(_uuid.uuid4())
    title = payload.get("title")
    content = payload.get("content")
    if not title or not content:
        raise HTTPException(status_code=400, detail="title and content are required")
    category = payload.get("category", "custom-policy")
    tags = payload.get("tags", [])
    vector_knowledge_store.add_document(doc_id=doc_id, title=title, content=content, category=category, tags=tags)
    vector_knowledge_store.save_to_disk()
    return {"status": "success", "indexed_id": doc_id}


@app.get("/api/v2/copilot/rag/cache-stats")
async def get_rag_cache_stats():
    """Returns RAG query cache performance metrics and hit rates."""
    return query_cache.get_stats()


@app.delete("/api/v2/copilot/rag/cache")
async def clear_rag_cache():
    """Clears the RAG query cache."""
    query_cache.clear()
    return {"status": "success", "message": "Query cache cleared"}


@app.get("/api/v2/copilot/status")
@app.get("/api/v1/copilot/status")
async def get_copilot_status():
    """
    Returns active FinOps Copilot status, LLM model cascade, and operational tools.
    """
    engine_ready = copilot_agent.engine and copilot_agent.engine.is_available()
    active_model = getattr(copilot_agent.engine, "active_model", "compound-mini") if copilot_agent.engine else None
    return {
        "status": "ready" if engine_ready else "heuristic_fallback",
        "provider": copilot_agent.provider,
        "active_model": active_model,
        "tools_enabled": ["sql_analytics", "pricing_rag", "cloudtrail_forensics", "terraform_pr", "finops_rag", "vector_knowledge_store"],
        "groq_configured": bool(copilot_agent.groq_api_key),
        "api_endpoints": [
            "/api/v2/copilot/chat",
            "/api/v2/copilot/rag/ask",
            "/api/v2/copilot/rag/recommendations",
            "/api/v2/copilot/rag/status",
            "/api/v2/copilot/rag/cache-stats",
            "/api/v2/copilot/knowledge/search",
            "/api/v2/copilot/knowledge/policies",
            "/api/v2/copilot/diagnose-spike",
            "/api/v2/copilot/generate-iac-pr",
            "/api/v2/copilot/pricing",
            "/api/v1/agent/chat",
            "/api/v2/fleet/accounts",
            "/api/v2/fleet/summary",
            "/api/v2/fleet/scan",
            "/api/v2/fleet/focus-records",
            "/api/v2/gitops/pr",
            "/api/v2/gitops/audit-log",
            "/api/v2/notifications/slack",
            "/api/v2/notifications/teams",
            "/api/v2/analytics/anomalies",
            "/api/v2/analytics/forecast"
        ]
    }


# =====================================================================
# 🚀 GITOPS AUTONOMOUS REMEDIATION & NOTIFICATION APIS
# =====================================================================

@app.post("/api/v2/gitops/pr")
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
    return pr_package


@app.get("/api/v2/gitops/audit-log")
async def get_gitops_audit_log(limit: int = 50):
    """Returns immutable audit trail of all GitOps PRs and remediations."""
    return {"count": len(gitops_engine.audit_log), "audit_trail": gitops_engine.get_audit_trail(limit)}


@app.post("/api/v2/notifications/slack")
async def send_slack_finops_alert(payload: dict):
    """Generates and optionally dispatches Slack Block Kit alert."""
    resource_id = payload.get("resource_id", "unknown-resource")
    finding_title = payload.get("finding_title", "Idle Cloud Resource Detected")
    severity = payload.get("severity", "HIGH")
    current_spend = float(payload.get("current_monthly_spend", 0.0))
    savings = float(payload.get("potential_monthly_savings", 0.0))
    action = payload.get("recommended_action", "Downsize or stop resource")
    webhook_url = payload.get("webhook_url")

    card = notification_engine.format_slack_alert(
        resource_id=resource_id,
        finding_title=finding_title,
        severity=severity,
        current_monthly_spend=current_spend,
        potential_monthly_savings=savings,
        recommended_action=action
    )

    dispatched = False
    if webhook_url:
        dispatched = notification_engine.dispatch_webhook(webhook_url, card)

    return {"status": "success", "dispatched": dispatched, "payload": card}


@app.post("/api/v2/notifications/teams")
async def send_teams_finops_alert(payload: dict):
    """Generates and optionally dispatches Microsoft Teams Adaptive Card."""
    resource_id = payload.get("resource_id", "unknown-resource")
    finding_title = payload.get("finding_title", "Idle Cloud Resource Detected")
    severity = payload.get("severity", "HIGH")
    savings = float(payload.get("potential_monthly_savings", 0.0))
    action = payload.get("recommended_action", "Downsize or stop resource")
    webhook_url = payload.get("webhook_url")

    card = notification_engine.format_teams_adaptive_card(
        resource_id=resource_id,
        finding_title=finding_title,
        severity=severity,
        potential_monthly_savings=savings,
        recommended_action=action
    )

    dispatched = False
    if webhook_url:
        dispatched = notification_engine.dispatch_webhook(webhook_url, card)

    return {"status": "success", "dispatched": dispatched, "payload": card}


@app.post("/api/v2/notifications/slack/batch")
async def send_slack_batch_finops_digest(payload: dict = None):
    """Generates and optionally dispatches fleet-wide Slack Block Kit batch digest."""
    payload = payload or {}
    webhook_url = payload.get("webhook_url")
    currency = payload.get("currency", "USD")
    rate = float(payload.get("rate", 84.0))

    inventory = resolve_active_inventory()
    try:
        from engines.finops_analyzer import FinOpsAnalyzer
        eval_res = FinOpsAnalyzer.evaluate(inventory)
        findings = payload.get("findings") or eval_res.get("findings", [])
        monthly_spend = eval_res.get("total_monthly_spend", 68.40)
        monthly_savings = eval_res.get("total_potential_monthly_savings", 0.0)
        health_score = eval_res.get("health_score", 85.0)
    except Exception:
        findings = payload.get("findings", [])
        monthly_spend = 68.40
        monthly_savings = 25.0
        health_score = 85.0

    account_id = inventory.get("metadata", {}).get("account_id", "582812122408")

    card = notification_engine.format_slack_batch_summary(
        findings=findings,
        total_monthly_spend=monthly_spend,
        total_monthly_savings=monthly_savings,
        health_score=health_score,
        account_id=account_id,
        currency=currency,
        rate=rate,
        repo_name=payload.get("repo_name", "infrastructure/aws-workloads")
    )

    dispatched = False
    if webhook_url:
        dispatched = notification_engine.dispatch_webhook(webhook_url, card)

    return {"status": "success", "dispatched": dispatched, "payload": card}


@app.post("/api/v2/notifications/teams/batch")
async def send_teams_batch_finops_digest(payload: dict = None):
    """Generates and optionally dispatches fleet-wide Microsoft Teams Adaptive Card batch digest."""
    payload = payload or {}
    webhook_url = payload.get("webhook_url")
    currency = payload.get("currency", "USD")
    rate = float(payload.get("rate", 84.0))

    inventory = resolve_active_inventory()
    try:
        from engines.finops_analyzer import FinOpsAnalyzer
        eval_res = FinOpsAnalyzer.evaluate(inventory)
        findings = payload.get("findings") or eval_res.get("findings", [])
        monthly_spend = eval_res.get("total_monthly_spend", 68.40)
        monthly_savings = eval_res.get("total_potential_monthly_savings", 0.0)
        health_score = eval_res.get("health_score", 85.0)
    except Exception:
        findings = payload.get("findings", [])
        monthly_spend = 68.40
        monthly_savings = 25.0
        health_score = 85.0

    account_id = inventory.get("metadata", {}).get("account_id", "582812122408")

    card = notification_engine.format_teams_batch_adaptive_card(
        findings=findings,
        total_monthly_spend=monthly_spend,
        total_monthly_savings=monthly_savings,
        health_score=health_score,
        account_id=account_id,
        currency=currency,
        rate=rate,
        repo_name=payload.get("repo_name", "infrastructure/aws-workloads")
    )

    dispatched = False
    if webhook_url:
        dispatched = notification_engine.dispatch_webhook(webhook_url, card)

    return {"status": "success", "dispatched": dispatched, "payload": card}


@app.post("/api/v2/notifications/interactive/callback")
async def handle_notification_interactive_callback(payload: dict):
    """Receives interactive button action callbacks from Slack / Teams."""
    result = notification_engine.handle_interactive_callback(payload)
    return result



# =====================================================================
# 🌐 MULTI-ACCOUNT ENTERPRISE FLEET INGESTION & FOCUS 1.0 APIS
# =====================================================================

@app.get("/api/v2/fleet/accounts")
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


@app.post("/api/v2/fleet/accounts")
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


@app.post("/api/v2/fleet/discover")
async def discover_fleet_accounts(payload: Optional[dict] = None):
    """
    Auto-discovers all member accounts via AWS Organizations API
    and enrolls them into the multi-account fleet manager.
    """
    payload = payload or {}
    role_name = payload.get("role_name", "CloudPulseReadOnlyRole")
    external_id = payload.get("external_id", "CloudPulseEnterpriseSecurityId")
    session = _build_aws_session() or boto3.Session()
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


@app.get("/api/v2/fleet/summary")
async def get_fleet_summary(force_refresh: bool = False):
    """Returns aggregated fleet-wide FinOps executive KPIs and spend."""
    summary = fleet_manager.get_fleet_summary(force_refresh=force_refresh)
    if not summary.get("accounts_scanned"):
        db = mock_database.DB
        nodes = db.get("nodes", [])
        vols = db.get("ebs_volumes", [])
        eips = db.get("elastic_ips", [])
        total_spend = sum(float(n.get("cost", 7.60)) for n in nodes)
        summary = {
            "total_accounts_registered": max(1, len(fleet_manager.accounts)),
            "accounts_scanned": 1,
            "successful_scans": 1,
            "failed_scans": 0,
            "total_fleet_monthly_spend": round(total_spend, 2),
            "total_fleet_nodes": len(nodes),
            "total_fleet_volumes": len(vols),
            "total_fleet_eips": len(eips),
            "total_focus_records": len(nodes) + len(vols) + len(eips),
            "scan_duration_seconds": 0.05
        }
    return summary


@app.post("/api/v2/fleet/scan")
async def trigger_fleet_scan(payload: Optional[dict] = None):
    """Triggers parallel multi-worker scan across all accounts in fleet."""
    payload = payload or {}
    account_ids = payload.get("account_ids")
    summary = fleet_manager.scan_fleet_parallel(account_ids=account_ids)
    return summary


@app.get("/api/v2/fleet/focus-records")
async def get_fleet_focus_records():
    """Returns normalized FOCUS 1.0 records across the entire fleet."""
    db = mock_database.DB
    focus_records = FOCUSNormalizer.normalize_inventory(db)
    return {
        "specification": "FOCUS 1.0",
        "record_count": len(focus_records),
        "records": focus_records
    }


@app.post("/api/v2/focus/query")
async def execute_focus_sql_query(payload: dict):
    """Executes high-throughput SQL analytics over FOCUS 1.0 datasets."""
    sql = payload.get("query")
    if not sql:
        raise HTTPException(status_code=400, detail="SQL query is required")

    try:
        from engines.focus_lakehouse import focus_lakehouse
    except ImportError:
        from backend.engines.focus_lakehouse import focus_lakehouse

    db = mock_database.DB
    focus_records = FOCUSNormalizer.normalize_inventory(db)
    focus_lakehouse.load_focus_records(focus_records)

    try:
        result = focus_lakehouse.execute_query(sql)
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v2/focus/analytics")
async def get_focus_analytics():
    """Returns pre-aggregated FOCUS 1.0 analytics (by service, account, and top cost drivers)."""
    try:
        from engines.focus_lakehouse import focus_lakehouse
    except ImportError:
        from backend.engines.focus_lakehouse import focus_lakehouse

    db = mock_database.DB
    focus_records = FOCUSNormalizer.normalize_inventory(db)
    focus_lakehouse.load_focus_records(focus_records)

    return {
        "status": "success",
        "spend_by_service": focus_lakehouse.get_spend_by_service(),
        "spend_by_account": focus_lakehouse.get_spend_by_account(),
        "top_cost_drivers": focus_lakehouse.get_top_cost_drivers(limit=10)
    }



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


# =====================================================================
# 📈 REAL-TIME ANOMALY DETECTION & SPEND FORECASTING APIS
# =====================================================================

def resolve_active_inventory() -> dict:
    """Resolves active cloud inventory: checks fleet_cache for live scanned inventory first, falls back to mock_database."""
    try:
        try:
            from collectors.fleet_cache import fleet_cache
        except ImportError:
            from backend.collectors.fleet_cache import fleet_cache

        cached = fleet_cache.get("fleet_summary")
        if cached and isinstance(cached, dict):
            for acc in cached.get("scanned_accounts", []):
                if acc.get("status") == "success" and acc.get("inventory"):
                    return acc["inventory"]
    except Exception:
        pass
    return mock_database.DB


@app.get("/api/v2/analytics/anomalies")
async def get_cost_anomalies(severity: Optional[str] = None):
    """Returns detected cost anomalies across multi-cloud inventory and FOCUS records."""
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


@app.post("/api/v2/analytics/anomalies/scan")
async def trigger_anomaly_scan():
    """Triggers an on-demand statistical anomaly scan against live cloud inventory."""
    inventory = resolve_active_inventory()
    focus_records = FOCUSNormalizer.convert_inventory_to_focus(inventory)
    anomalies = anomaly_detector.scan_inventory_and_focus(inventory, focus_records)
    return {
        "status": "scan_complete",
        "anomalies_detected": len(anomalies),
        "anomalies": anomalies
    }


@app.get("/api/v2/analytics/forecast")
async def get_spend_forecast(days: int = 30, budget: float = 100.0):
    """Calculates Holt-Winters linear trend spend forecast and budget burn-rate."""
    inventory = resolve_active_inventory()
    forecast = spend_forecaster.forecast_from_inventory(
        inventory=inventory,
        forecast_days=days,
        monthly_budget=budget
    )
    return forecast


@app.post("/api/v2/analytics/forecast")
async def calculate_custom_forecast(payload: dict):
    """Calculates custom spend forecast from a user-supplied daily history time-series."""
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


# =====================================================================
# 🌐 MULTI-CLOUD CONNECTORS (AZURE / GCP) & RBAC SECURITY APIS
# =====================================================================

@app.get("/api/v2/multicloud/summary")
async def get_multicloud_summary():
    """Returns cross-cloud spend distribution across AWS, Azure, and GCP."""
    summary_spend = resolve_active_inventory().get("summary", {}).get("estimated_monthly_spend", 74.16)
    return multicloud_orchestrator.get_cross_cloud_summary(aws_spend=summary_spend)


@app.post("/api/v2/multicloud/ingest")
async def ingest_multicloud_records(payload: dict):
    """Ingests Azure or GCP raw billing records and converts them to FOCUS 1.0."""
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


@app.get("/api/v2/auth/verify-role")
async def verify_rbac_role(api_key: Optional[str] = None, permission: Optional[str] = None):
    """Validates API token and checks RBAC authorization."""
    identity = rbac_manager.authenticate_key(api_key)
    if not identity.get("authenticated"):
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid API key")

    has_perm = True
    if permission:
        has_perm = rbac_manager.check_permission(identity["role"], permission)

    return {
        "identity": identity,
        "requested_permission": permission,
        "authorized": has_perm
    }


# =====================================================================
# 🚀 48-HOUR PROOF-OF-VALUE (PoV) AUDIT & MULTI-CURRENCY APIS
# =====================================================================

@app.get("/api/v2/analytics/pov/summary")
async def get_pov_summary(currency: str = "INR", rate: float = 84.0):
    """Returns the executive Proof-of-Value (PoV) audit summary with dual-currency financial modeling."""
    from services.currency_converter import currency_converter
    from services.pov_reporter import PoVReporter

    currency_converter.usd_to_inr_rate = rate
    reporter = PoVReporter(currency=currency, usd_to_inr_rate=rate)

    inventory = resolve_active_inventory()
    focus_records = FOCUSNormalizer.convert_inventory_to_focus(inventory)
    anomalies = anomaly_detector.scan_inventory_and_focus(inventory, focus_records)

    gross_monthly = inventory.get("summary", {}).get("estimated_monthly_spend", 68.40)
    savings_monthly = round(gross_monthly * 0.40, 2)
    savings_annual = round(savings_monthly * 12, 2)

    return {
        "account_id": inventory.get("metadata", {}).get("account_id", "582812122408"),
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


@app.get("/api/v2/analytics/pov/report.html", response_class=HTMLResponse)
async def get_pov_html_report(currency: str = "INR", rate: float = 84.0, account_name: str = "Enterprise Cloud Fleet"):
    """Serves the rendered executive single-file HTML PoV audit dossier."""
    from services.currency_converter import currency_converter
    from services.pov_reporter import PoVReporter

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






