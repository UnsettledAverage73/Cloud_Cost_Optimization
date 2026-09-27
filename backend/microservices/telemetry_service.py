"""
CloudPulse Real-Time Telemetry & Metric Streaming Microservice
Port: 8003
Provides sub-second hypervisor & in-guest agent telemetry ingestion,
WebSocket live feeds, TimescaleDB hypertable persistence, and fleet telemetry status.
"""

import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, APIRouter, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

_backend_dir = Path(__file__).resolve().parent.parent
_repo_dir = _backend_dir.parent
for p in [str(_backend_dir), str(_repo_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from microservices.shared_state import (
        _db, _ensure_live_aws_state, _live_instance_telemetry,
        _frontend_telemetry, _build_aws_session, _saved_credentials
    )
    from schemas import IngestionPayload
    from database.connection import SyncSessionLocal
    from database.models import ConnectedAWSAccount, ResourceTelemetry, CloudResource
    from services.telemetry_streamer import telemetry_hub
except ImportError:
    from backend.microservices.shared_state import (
        _db, _ensure_live_aws_state, _live_instance_telemetry,
        _frontend_telemetry, _build_aws_session, _saved_credentials
    )
    from backend.schemas import IngestionPayload
    from backend.database.connection import SyncSessionLocal
    from backend.database.models import ConnectedAWSAccount, ResourceTelemetry, CloudResource
    from backend.services.telemetry_streamer import telemetry_hub

router = APIRouter(tags=["Telemetry & Streaming Microservice"])


# =========================================================================
# 1. INGESTION ENDPOINTS (V1 & V2)
# =========================================================================

@router.post("/api/v1/ingest", status_code=status.HTTP_201_CREATED)
async def ingest_cloud_data(payload: IngestionPayload):
    """Receives raw output from OptiScale Python script and updates DB state."""
    db = _db()
    db["metadata"] = payload.metadata
    db["nodes"] = payload.compute.get("nodes", [])
    db["ebs_volumes"] = payload.ec2_other_resources.get("ebs_volumes", [])
    db["elastic_ips"] = payload.ec2_other_resources.get("elastic_ips", [])
    db["security_groups"] = payload.ec2_other_resources.get("security_groups", [])
    db["telemetry"] = [t.dict() for t in payload.telemetry]
    return {"status": "success", "message": "Telemetry and resource data ingested successfully"}


@router.post("/api/v2/agent/ingest")
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
        account = session.query(ConnectedAWSAccount).first()
        account_id = account.id if account else uuid.uuid4()

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

        try:
            net = telemetry.get("network", {})
            datapoint = {
                "timestamp": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                "cpu": float(cpu.get("utilization_percent", 0.0)),
                "mem": float(memory.get("percent_used", 0.0)),
                "disk": float(disk.get("percent_used", 0.0)),
                "net_in_bytes": int(net.get("bytes_recv", 0)),
                "net_out_bytes": int(net.get("bytes_sent", 0)),
                "packets_in": int(net.get("packets_recv", 0)),
                "packets_out": int(net.get("packets_sent", 0)),
                "cpu_credits": 144.0,
                "is_guest_agent": True,
            }
            await telemetry_hub.broadcast_tick(resource_id, datapoint)
        except Exception:
            pass

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


# =========================================================================
# 2. QUERY & STREAMING METRICS
# =========================================================================

@router.get("/api/v1/telemetry/{instance_id}")
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


@router.get("/api/telemetry")
async def get_frontend_telemetry(timeframe: str = "24h", instance_id: Optional[str] = None):
    return _frontend_telemetry(timeframe=timeframe)


@router.get("/api/v2/telemetry/hypertable")
async def get_telemetry_hypertable(resource_id: Optional[str] = None, limit: int = 50):
    session = SyncSessionLocal()
    try:
        query = session.query(ResourceTelemetry)
        if resource_id:
            query = query.filter(ResourceTelemetry.resource_id == resource_id)
        records = query.order_by(ResourceTelemetry.time.desc()).limit(limit).all()
        return {"count": len(records), "telemetry": [r.to_dict() for r in records]}
    finally:
        session.close()


@router.websocket("/ws/telemetry/{instance_id}")
async def stream_instance_telemetry(websocket: WebSocket, instance_id: str):
    aws_session = _build_aws_session()
    aws_region = (_saved_credentials() or {}).get("region", "us-east-1") if _saved_credentials() else os.environ.get("AWS_REGION", "us-east-1")
    await telemetry_hub.register_listener(instance_id, websocket, session=aws_session, region_name=aws_region)
    try:
        while True:
            _ = await websocket.receive_text()
    except (WebSocketDisconnect, Exception):
        telemetry_hub.unregister_listener(instance_id, websocket)


@router.get("/api/v2/telemetry/{instance_id}/live")
async def get_live_instance_telemetry(instance_id: str):
    aws_session = _build_aws_session()
    aws_region = (_saved_credentials() or {}).get("region", "us-east-1") if _saved_credentials() else os.environ.get("AWS_REGION", "us-east-1")
    telemetry_hub._seed_buffer_if_empty(instance_id, session=aws_session, region_name=aws_region)
    pts = list(telemetry_hub.buffers.get(instance_id, []))
    return {
        "instance_id": instance_id,
        "region": aws_region,
        "ring_buffer_points": len(pts),
        "history": pts,
        "datapoints": pts
    }


@router.get("/api/v2/agent/fleet-status")
async def get_agent_fleet_status():
    nodes = _db().get("nodes", [])
    fleet_nodes = []
    streaming_count = 0

    for n in nodes:
        inst_id = n.get("instance_id") or n.get("id") or "i-default"
        buf = telemetry_hub.buffers.get(inst_id, [])
        is_streaming = False
        latest_tick = None
        if len(buf) > 0:
            latest_tick = buf[-1]
            is_streaming = latest_tick.get("is_guest_agent", False)

        if is_streaming:
            streaming_count += 1

        fleet_nodes.append({
            "instance_id": inst_id,
            "name": n.get("name", "EC2 Node"),
            "instance_type": n.get("instance_type") or n.get("type") or "t3.micro",
            "state": n.get("state", "running"),
            "region": n.get("region", "us-east-1"),
            "streaming": is_streaming,
            "latest_metrics": latest_tick or {
                "cpu": n.get("cpu_utilization", 0.0),
                "mem": 0.0,
                "disk": 0.0,
                "net_in_bytes": 0,
                "is_guest_agent": False
            }
        })

    return {
        "status": "active",
        "total_instances": len(fleet_nodes),
        "streaming_instances": streaming_count,
        "user_consent": {
            "telemetry_enabled": True,
            "scope": "in-guest-hardware-only",
            "data_collection": ["cpu_percent", "memory_percent", "disk_percent", "network_throughput"],
            "privacy_guarantee": "Zero inspection of application data, files, or environment variables."
        },
        "install_command_linux": "curl -fsSL https://cloud-cost-optimization.onrender.com/api/v2/agent/install-script?os=linux | bash",
        "install_command_windows": "irm https://cloud-cost-optimization.onrender.com/api/v2/agent/install-script?os=windows | iex",
        "instances": fleet_nodes
    }


@router.get("/api/v2/agent/hosts")
async def list_agent_hosts():
    session = SyncSessionLocal()
    try:
        hosts = session.query(CloudResource).filter_by(service="host-agent").all()
        return {
            "count": len(hosts),
            "hosts": [h.to_dict() for h in hosts]
        }
    finally:
        session.close()


# Standalone Microservice FastAPI App definition
app = FastAPI(
    title="CloudPulse Telemetry & Metric Streaming Microservice",
    version="2.0.0",
    description="Real-time multi-OS guest agent and hypervisor metric streaming."
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
    return {"status": "healthy", "service": "telemetry_service", "port": 8003}


app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8003))
    uvicorn.run("microservices.telemetry_service:app", host="0.0.0.0", port=port, reload=True)
