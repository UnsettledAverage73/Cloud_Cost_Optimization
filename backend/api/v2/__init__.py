"""
CloudPulse API V2 Aggregator Module
Mounts all modular domain routers: Health, Copilot, Kubernetes, FOCUS Lakehouse,
Fleet Ingestion, Notifications, GitOps, and Real-Time Analytics.
"""

from fastapi import APIRouter

try:
    from api.v2.health import router as health_router
    from api.v2.copilot import router as copilot_router
    from api.v2.kubernetes import router as kubernetes_router
    from api.v2.focus import router as focus_router
    from api.v2.fleet import router as fleet_router
    from api.v2.notifications import router as notifications_router
    from api.v2.gitops import router as gitops_router
    from api.v2.analytics import router as analytics_router
except ImportError:
    from backend.api.v2.health import router as health_router
    from backend.api.v2.copilot import router as copilot_router
    from backend.api.v2.kubernetes import router as kubernetes_router
    from backend.api.v2.focus import router as focus_router
    from backend.api.v2.fleet import router as fleet_router
    from backend.api.v2.notifications import router as notifications_router
    from backend.api.v2.gitops import router as gitops_router
    from backend.api.v2.analytics import router as analytics_router

api_v2_router = APIRouter()

# Mount health probes at root level (/healthz, /readyz)
api_v2_router.include_router(health_router)

# Mount domain routers
api_v2_router.include_router(copilot_router)
api_v2_router.include_router(kubernetes_router)
api_v2_router.include_router(focus_router)
api_v2_router.include_router(fleet_router)
api_v2_router.include_router(notifications_router)
api_v2_router.include_router(gitops_router)
api_v2_router.include_router(analytics_router)

__all__ = [
    "api_v2_router",
    "health_router",
    "copilot_router",
    "kubernetes_router",
    "focus_router",
    "fleet_router",
    "notifications_router",
    "gitops_router",
    "analytics_router",
]
