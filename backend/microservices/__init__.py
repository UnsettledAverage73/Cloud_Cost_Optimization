"""
CloudPulse Microservices Registry & Router Aggregator
Exports all domain microservices for zero-latency ASGI mounting and standalone execution.
"""

from fastapi import APIRouter

try:
    from microservices.copilot_service import router as copilot_router, app as copilot_app
    from microservices.analytics_service import router as analytics_router, app as analytics_app
    from microservices.telemetry_service import router as telemetry_router, app as telemetry_app
    from microservices.remediation_service import router as remediation_router, app as remediation_app
    from microservices.fleet_service import router as fleet_router, app as fleet_app
    from microservices.notifications_service import router as notifications_router, app as notifications_app
    from microservices.scheduler_service import router as scheduler_router, app as scheduler_app
    from microservices.kubernetes_service import router as kubernetes_router, app as kubernetes_app
    from microservices.agent_service import router as agent_router, app as agent_app
except ImportError:
    from backend.microservices.copilot_service import router as copilot_router, app as copilot_app
    from backend.microservices.analytics_service import router as analytics_router, app as analytics_app
    from backend.microservices.telemetry_service import router as telemetry_router, app as telemetry_app
    from backend.microservices.remediation_service import router as remediation_router, app as remediation_app
    from backend.microservices.fleet_service import router as fleet_router, app as fleet_app
    from backend.microservices.notifications_service import router as notifications_router, app as notifications_app
    from backend.microservices.scheduler_service import router as scheduler_router, app as scheduler_app
    from backend.microservices.kubernetes_service import router as kubernetes_router, app as kubernetes_app
    from backend.microservices.agent_service import router as agent_router, app as agent_app

microservices_router = APIRouter()

microservices_router.include_router(copilot_router)
microservices_router.include_router(analytics_router)
microservices_router.include_router(telemetry_router)
microservices_router.include_router(remediation_router)
microservices_router.include_router(fleet_router)
microservices_router.include_router(notifications_router)
microservices_router.include_router(scheduler_router)
microservices_router.include_router(kubernetes_router)
microservices_router.include_router(agent_router)

__all__ = [
    "microservices_router",
    "copilot_router",
    "copilot_app",
    "analytics_router",
    "analytics_app",
    "telemetry_router",
    "telemetry_app",
    "remediation_router",
    "remediation_app",
    "fleet_router",
    "fleet_app",
    "notifications_router",
    "notifications_app",
    "scheduler_router",
    "scheduler_app",
    "kubernetes_router",
    "kubernetes_app",
    "agent_router",
    "agent_app",
]
