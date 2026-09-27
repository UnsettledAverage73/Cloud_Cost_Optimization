"""
CloudPulse FinOps High-Performance Microservices Gateway & Aggregator
Architecture: Zero-Latency In-Memory ASGI Gateway mounting decoupled autonomous microservices.
Maintains 100% backward compatibility for existing tests, frontend routers, and CLI utilities.
"""

import os
import sys
from pathlib import Path

# Ensure backend and repository root directories are in sys.path
_backend_dir = Path(__file__).resolve().parent
_repo_dir = _backend_dir.parent
for _p in [str(_backend_dir), str(_repo_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse

# Auto-load local .env if present
for cand in [_backend_dir / ".env", _repo_dir / ".env"]:
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

# Microservices Shared State & Re-exports for 100% Backward Compatibility
try:
    from microservices.shared_state import (
        _db, _build_aws_session, active_credentials, connected_accounts,
        last_live_error, is_demo_mode, revoked_security_groups,
        _load_persisted_state, _persist_state, _connection_signature,
        _public_connection_record, _set_connection_mode, _save_active_credentials,
        _saved_credentials, _connection_state, _estimate_instance_monthly_cost,
        _estimate_ebs_monthly_cost, _activate_connected_account, _is_permission_denied,
        _refresh_live_aws_state, _ensure_live_aws_state, _node_volume_count,
        _frontend_nodes, _normalize_node, _normalize_telemetry_points,
        _live_instance_telemetry, _frontend_telemetry, _frontend_spend,
        _frontend_alerts, _frontend_optimizations, finops_agent, finops_notifier
    )
    from microservices import (
        microservices_router, copilot_router, analytics_router,
        telemetry_router, remediation_router, fleet_router,
        notifications_router, scheduler_router, kubernetes_router, agent_router
    )
    from microservices.copilot_service import copilot_agent
    from core.state import REALTIME_STORE, get_realtime_store, resolve_active_inventory
    from core.middleware import CorrelationIdMiddleware
    from core.security import SecurityHeadersMiddleware
    from core.rate_limiter import RateLimitMiddleware
    from database.connection import ping_database, SyncSessionLocal
    from services.scheduler_engine import scheduler_engine
    from engines.focus_lakehouse import focus_lakehouse
    from services.vector_store import vector_knowledge_store
    from services.rbac_middleware import rbac_manager
    from api.v2.health import router as health_router
except ImportError:
    from backend.microservices.shared_state import (
        _db, _build_aws_session, active_credentials, connected_accounts,
        last_live_error, is_demo_mode, revoked_security_groups,
        _load_persisted_state, _persist_state, _connection_signature,
        _public_connection_record, _set_connection_mode, _save_active_credentials,
        _saved_credentials, _connection_state, _estimate_instance_monthly_cost,
        _estimate_ebs_monthly_cost, _activate_connected_account, _is_permission_denied,
        _refresh_live_aws_state, _ensure_live_aws_state, _node_volume_count,
        _frontend_nodes, _normalize_node, _normalize_telemetry_points,
        _live_instance_telemetry, _frontend_telemetry, _frontend_spend,
        _frontend_alerts, _frontend_optimizations, finops_agent, finops_notifier
    )
    from backend.microservices import (
        microservices_router, copilot_router, analytics_router,
        telemetry_router, remediation_router, fleet_router,
        notifications_router, scheduler_router, kubernetes_router, agent_router
    )
    from backend.microservices.copilot_service import copilot_agent
    from backend.core.state import REALTIME_STORE, get_realtime_store, resolve_active_inventory
    from backend.core.middleware import CorrelationIdMiddleware
    from backend.core.security import SecurityHeadersMiddleware
    from backend.core.rate_limiter import RateLimitMiddleware
    from backend.database.connection import ping_database, SyncSessionLocal
    from backend.services.scheduler_engine import scheduler_engine
    from backend.engines.focus_lakehouse import focus_lakehouse
    from backend.services.vector_store import vector_knowledge_store
    from backend.services.rbac_middleware import rbac_manager
    from backend.api.v2.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup if reachable
    try:
        try:
            from database.init_db import initialize_database
        except ImportError:
            from backend.database.init_db import initialize_database
        initialize_database()
        print("✅ Database schema initialized successfully.")
    except Exception as e:
        print(f"⚠️ Startup database initialization notice: {e}")

    try:
        scheduler_engine.start_worker()
        print("✅ Background scheduler worker initialized.")
    except Exception as e:
        print(f"⚠️ Scheduler startup note: {e}")

    yield

    # Graceful shutdown & connection draining
    try:
        scheduler_engine.stop_worker()
        print("🛑 Background scheduler worker stopped gracefully.")
    except Exception:
        pass

    try:
        if focus_lakehouse and hasattr(focus_lakehouse, "conn") and focus_lakehouse.conn:
            focus_lakehouse.conn.close()
            print("🛑 DuckDB Lakehouse connections drained.")
    except Exception:
        pass

    try:
        if vector_knowledge_store:
            vector_knowledge_store.save_to_disk()
            print("🛑 Vector knowledge store synchronized to disk.")
    except Exception:
        pass


app = FastAPI(
    title="CloudPulse FinOps Microservices Gateway",
    version="2.0.0",
    description="Ultra-low latency ASGI API Gateway mounting autonomous FinOps microservices.",
    lifespan=lifespan,
)

# Enable CORS with secure origins per W3C specification
_cors_origins_env = os.getenv("ALLOWED_ORIGINS", "")
if _cors_origins_env:
    _allowed_cors_origins = [orig.strip() for orig in _cors_origins_env.split(",") if orig.strip()]
else:
    _allowed_cors_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://cloud-cost-optimization-frontend.onrender.com",
        "https://cloud-cost-optimization.onrender.com",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_cors_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$|^https://[a-zA-Z0-9-]+\.onrender\.com$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. OWASP & Google Security Headers Middleware
app.add_middleware(SecurityHeadersMiddleware)

# 2. Production Sliding-Window Rate Limiter
app.add_middleware(RateLimitMiddleware)

# 3. Google SRE Correlation ID and Process Time Middleware
app.add_middleware(CorrelationIdMiddleware)

# Mount SRE Health Probes (/healthz, /readyz, /metrics)
app.include_router(health_router)

# Mount Autonomous Domain Microservice Routers (<0.1ms In-Process ASGI Dispatch)
app.include_router(copilot_router)
app.include_router(analytics_router)
app.include_router(telemetry_router)
app.include_router(remediation_router)
app.include_router(fleet_router)
app.include_router(notifications_router)
app.include_router(scheduler_router)
app.include_router(kubernetes_router)
app.include_router(agent_router)


# =========================================================================
# SYSTEM & GATEWAY CONFIGURATION ENDPOINTS
# =========================================================================

@app.get("/api/v2/database/status")
async def get_database_status():
    """Returns real-time connection status and TimescaleDB extension version."""
    status_info = ping_database()
    return status_info


@app.put("/api/settings")
async def update_settings(payload: dict):
    org_name = payload.get("orgName")
    if org_name:
        _db()["metadata"]["organization"] = org_name

    meta = _db()["metadata"]
    if "slackWebhookUrl" in payload:
        meta["slack_webhook_url"] = payload["slackWebhookUrl"]
        if payload["slackWebhookUrl"]:
            os.environ["SLACK_WEBHOOK_URL"] = payload["slackWebhookUrl"]
    if "teamsWebhookUrl" in payload:
        meta["teams_webhook_url"] = payload["teamsWebhookUrl"]
        if payload["teamsWebhookUrl"]:
            os.environ["TEAMS_WEBHOOK_URL"] = payload["teamsWebhookUrl"]
    if "slackBotToken" in payload and payload["slackBotToken"] and not payload["slackBotToken"].startswith("••••"):
        meta["slack_bot_token"] = payload["slackBotToken"]
        os.environ["SLACK_BOT_TOKEN"] = payload["slackBotToken"]
    if "slackChannel" in payload:
        meta["slack_channel"] = payload["slackChannel"]
        if payload["slackChannel"]:
            os.environ["SLACK_CHANNEL"] = payload["slackChannel"]
    if "whatsappTo" in payload:
        meta["whatsapp_to"] = payload["whatsappTo"]
        if payload["whatsappTo"]:
            os.environ["WHATSAPP_ALERT_TO"] = payload["whatsappTo"]

    return {
        "status": "saved",
        "organization": meta.get("organization", ""),
        "slack_webhook_url": meta.get("slack_webhook_url", os.getenv("SLACK_WEBHOOK_URL", "")),
        "teams_webhook_url": meta.get("teams_webhook_url", os.getenv("TEAMS_WEBHOOK_URL", "")),
        "slack_channel": meta.get("slack_channel", os.getenv("SLACK_CHANNEL", "all-average")),
        "whatsapp_to": meta.get("whatsapp_to", os.getenv("WHATSAPP_ALERT_TO", ""))
    }


@app.get("/api/settings")
async def get_settings():
    metadata = _db()["metadata"]
    raw_token = metadata.get("slack_bot_token") or os.getenv("SLACK_BOT_TOKEN", "")
    masked_token = f"••••••••{raw_token[-4:]}" if len(raw_token) > 4 else ("••••••••" if raw_token else "")

    return {
        "organization": metadata.get("organization", ""),
        "region": metadata.get("region", "us-east-1"),
        "timestamp": metadata.get("timestamp"),
        "slack_webhook_url": metadata.get("slack_webhook_url") or os.getenv("SLACK_WEBHOOK_URL", ""),
        "teams_webhook_url": metadata.get("teams_webhook_url") or os.getenv("TEAMS_WEBHOOK_URL", ""),
        "slack_bot_token": masked_token,
        "slack_channel": metadata.get("slack_channel") or os.getenv("SLACK_CHANNEL", "all-average"),
        "whatsapp_to": metadata.get("whatsapp_to") or os.getenv("WHATSAPP_ALERT_TO", ""),
    }


@app.get("/api/v1/security/audit")
async def get_security_audit():
    _ensure_live_aws_state()
    db = _db()
    return {
        "exposed_security_groups": [sg for sg in db.get("security_groups", []) if sg.get("is_publicly_exposed")],
        "all_security_groups": db.get("security_groups", []),
        "unattached_elastic_ips": [eip for eip in db.get("elastic_ips", []) if eip.get("is_unattached")],
        "orphaned_ebs_volumes": [v for v in db.get("ebs_volumes", []) if v.get("is_orphaned")]
    }


@app.get("/api/v2/auth/verify-role")
async def verify_rbac_role(api_key: Optional[str] = None, permission: Optional[str] = None):
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


__all__ = [
    "app",
    "_db",
    "_build_aws_session",
    "active_credentials",
    "connected_accounts",
    "last_live_error",
    "is_demo_mode",
    "revoked_security_groups",
    "resolve_active_inventory",
    "copilot_agent",
    "finops_agent",
    "finops_notifier",
]
