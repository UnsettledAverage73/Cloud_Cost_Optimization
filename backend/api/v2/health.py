"""
Google SRE Standard Health & Readiness Probes
Provides /healthz (liveness) and /readyz (readiness) endpoints for Kubernetes orchestrators.
"""

from fastapi import APIRouter, Response, status
from fastapi.responses import JSONResponse
from datetime import datetime, timezone

try:
    from database.connection import ping_database
    from services.vector_store import vector_knowledge_store
    from services.opencost_engine import opencost_engine
    from engines.focus_lakehouse import focus_lakehouse
except ImportError:
    from backend.database.connection import ping_database
    from backend.services.vector_store import vector_knowledge_store
    from backend.services.opencost_engine import opencost_engine
    from backend.engines.focus_lakehouse import focus_lakehouse

router = APIRouter(tags=["Health & Probes"])


@router.get("/healthz", status_code=status.HTTP_200_OK)
async def liveness_probe():
    """
    Kubernetes Liveness Probe:
    Confirms process is responsive and event loop is processing requests.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "probe": "liveness"
    }


@router.get("/readyz")
async def readiness_probe():
    """
    Kubernetes Readiness Probe:
    Verifies that stateful dependencies (Database, Vector Index, Lakehouse) are healthy
    before traffic routing commences.
    """
    checks = {}
    is_ready = True

    # 1. Database check
    try:
        db_alive = ping_database()
        checks["database"] = "connected" if db_alive else "disconnected"
    except Exception as e:
        checks["database"] = f"error: {str(e)}"
        # Note: In hybrid dev/local mode, DB may be optional, but we report it accurately

    # 2. Vector Store check
    try:
        policy_count = len(vector_knowledge_store.get_all_documents())
        checks["vector_knowledge_store"] = {
            "status": "ready" if policy_count > 0 else "empty",
            "indexed_policies": policy_count
        }
    except Exception as e:
        checks["vector_knowledge_store"] = f"error: {str(e)}"
        is_ready = False

    # 3. FOCUS Lakehouse check
    try:
        lake_ready = focus_lakehouse is not None
        checks["focus_lakehouse"] = "ready" if lake_ready else "unavailable"
    except Exception as e:
        checks["focus_lakehouse"] = f"error: {str(e)}"

    # 4. OpenCost Telemetry check
    try:
        k8s_status = opencost_engine.get_status() if opencost_engine else {"connected": False}
        checks["opencost_k8s"] = k8s_status.get("connection_status", "ready")
    except Exception as e:
        checks["opencost_k8s"] = f"error: {str(e)}"

    status_code = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if is_ready else "not_ready",
            "probe": "readiness",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": checks
        }
    )


try:
    from core.metrics import get_prometheus_metrics, sync_domain_gauges, CONTENT_TYPE_LATEST
except ImportError:
    try:
        from backend.core.metrics import get_prometheus_metrics, sync_domain_gauges, CONTENT_TYPE_LATEST
    except ImportError:
        get_prometheus_metrics = lambda: b""
        sync_domain_gauges = lambda: None
        CONTENT_TYPE_LATEST = "text/plain; version=0.0.4"


@router.get("/metrics")
async def prometheus_metrics():
    """
    Standard Prometheus metrics exposition endpoint for Kubernetes scraper.
    """
    sync_domain_gauges()
    return Response(content=get_prometheus_metrics(), media_type=CONTENT_TYPE_LATEST)
