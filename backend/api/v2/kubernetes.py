"""
CloudPulse Kubernetes & CNCF OpenCost Domain API Router
Workload allocations, container efficiency analytics, and 1-click YAML rightsizing diffs.
"""

from typing import Optional
from fastapi import APIRouter

try:
    from services.opencost_engine import opencost_engine
except ImportError:
    from backend.services.opencost_engine import opencost_engine

router = APIRouter(prefix="/api/v2/kubernetes", tags=["Kubernetes & OpenCost"])


@router.get("/allocations")
@router.get("/workloads")
async def get_kubernetes_allocations(
    namespace: Optional[str] = None,
    currency: str = "USD",
    rate: float = 84.0
):
    """Returns granular Kubernetes workload resource and cost allocations."""
    return opencost_engine.get_workload_allocations(namespace=namespace, currency=currency, rate=rate)


@router.get("/efficiency")
@router.get("/summary")
async def get_kubernetes_efficiency(
    currency: str = "USD",
    rate: float = 84.0
):
    """Returns cluster efficiency score, idle capacity waste, and namespace breakdowns."""
    return opencost_engine.get_cluster_efficiency(currency=currency, rate=rate)


@router.get("/recommendations")
@router.get("/rightsizing")
async def get_kubernetes_recommendations(
    threshold: float = 40.0,
    efficiency_threshold: Optional[float] = None,
    currency: str = "USD",
    rate: float = 84.0
):
    """Returns 1-click YAML rightsizing recommendations for over-provisioned workloads."""
    t = efficiency_threshold if efficiency_threshold is not None else threshold
    return opencost_engine.get_rightsizing_recommendations(
        efficiency_threshold=t,
        currency=currency,
        rate=rate
    )


@router.post("/ingest")
async def ingest_kubernetes_opencost_payload(payload: dict):
    """Ingests OpenCost allocation JSON telemetry into the active workload inventory."""
    count = opencost_engine.ingest_opencost_payload(payload)
    return {"status": "success", "ingested_workloads": count}


@router.get("/status")
async def get_kubernetes_status():
    """Returns real-time Kubernetes cluster connection status, provider, and sync state."""
    return opencost_engine.get_status()


@router.post("/sync")
async def sync_kubernetes_realtime(force_provider: Optional[str] = None):
    """Triggers immediate real-time sync with OpenCost endpoint or live kubectl cluster."""
    result = opencost_engine.sync_realtime()
    return result


@router.post("/config")
async def update_kubernetes_config(payload: dict):
    """Updates OpenCost endpoint URL, cluster name, or telemetry mode."""
    if "opencost_url" in payload:
        opencost_engine.opencost_url = str(payload["opencost_url"]).strip()
    if "cluster_name" in payload:
        opencost_engine.cluster_name = str(payload["cluster_name"]).strip()
    if "mode" in payload:
        opencost_engine.mode = str(payload["mode"]).strip()
    opencost_engine._save_config()
    # If URL was provided, attempt sync immediately
    if "opencost_url" in payload:
        opencost_engine.fetch_live_opencost()
    return opencost_engine.get_status()


@router.post("/clear-demo")
async def clear_kubernetes_demo():
    """Flushes all mock workloads and enforces strict real-time telemetry mode."""
    return opencost_engine.clear_mock_data()
