"""
CloudPulse Kubernetes & CNCF OpenCost Microservice
Port: 8008
Provides workload allocations, container efficiency analytics, OpenCost JSON ingest,
and 1-click YAML rightsizing diffs.
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, APIRouter, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

_backend_dir = Path(__file__).resolve().parent.parent
_repo_dir = _backend_dir.parent
for p in [str(_backend_dir), str(_repo_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from services.opencost_engine import opencost_engine
except ImportError:
    from backend.services.opencost_engine import opencost_engine

router = APIRouter(tags=["Kubernetes & OpenCost Microservice"])


@router.get("/api/v2/kubernetes/allocations")
@router.get("/api/v2/kubernetes/workloads")
async def get_kubernetes_allocations(
    namespace: Optional[str] = None,
    currency: str = "USD",
    rate: float = 84.0
):
    return opencost_engine.get_workload_allocations(namespace=namespace, currency=currency, rate=rate)


@router.get("/api/v2/kubernetes/efficiency")
@router.get("/api/v2/kubernetes/summary")
async def get_kubernetes_efficiency(
    currency: str = "USD",
    rate: float = 84.0
):
    return opencost_engine.get_cluster_efficiency(currency=currency, rate=rate)


@router.get("/api/v2/kubernetes/recommendations")
@router.get("/api/v2/kubernetes/rightsizing")
async def get_kubernetes_recommendations(
    threshold: float = 40.0,
    efficiency_threshold: Optional[float] = None,
    currency: str = "USD",
    rate: float = 84.0
):
    t = efficiency_threshold if efficiency_threshold is not None else threshold
    return opencost_engine.get_rightsizing_recommendations(
        efficiency_threshold=t,
        currency=currency,
        rate=rate
    )


@router.post("/api/v2/kubernetes/ingest")
async def ingest_kubernetes_opencost_payload(payload: dict):
    count = opencost_engine.ingest_opencost_payload(payload)
    return {"status": "success", "ingested_workloads": count}


@router.get("/api/v2/kubernetes/status")
async def get_kubernetes_status():
    return opencost_engine.get_status()


@router.post("/api/v2/kubernetes/sync")
async def sync_kubernetes_realtime(force_provider: Optional[str] = None):
    result = opencost_engine.sync_realtime()
    return result


@router.post("/api/v2/kubernetes/config")
async def update_kubernetes_config(payload: dict):
    if "opencost_url" in payload:
        opencost_engine.opencost_url = str(payload["opencost_url"]).strip()
    if "cluster_name" in payload:
        opencost_engine.cluster_name = str(payload["cluster_name"]).strip()
    if "mode" in payload:
        opencost_engine.mode = str(payload["mode"]).strip()
    opencost_engine._save_config()
    if "opencost_url" in payload:
        opencost_engine.fetch_live_opencost()
    return opencost_engine.get_status()


@router.post("/api/v2/kubernetes/clear-demo")
async def clear_kubernetes_demo():
    return opencost_engine.clear_mock_data()


# Standalone Microservice FastAPI App definition
app = FastAPI(
    title="CloudPulse Kubernetes & OpenCost Microservice",
    version="2.0.0",
    description="Container cost allocation and rightsizing."
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
    return {"status": "healthy", "service": "kubernetes_service", "port": 8008}


app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8008))
    uvicorn.run("microservices.kubernetes_service:app", host="0.0.0.0", port=port, reload=True)
