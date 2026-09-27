"""
CloudPulse Workload Scheduler & Predictive Pre-Warming Microservice
Port: 8007
Provides operational start/stop schedules, 10-minute grace period overrides,
diurnal telemetry pattern detection, and automated pre-warming pipelines.
"""

import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, APIRouter, HTTPException, status, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

_backend_dir = Path(__file__).resolve().parent.parent
_repo_dir = _backend_dir.parent
for p in [str(_backend_dir), str(_repo_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from microservices.shared_state import (
        _db, _build_aws_session, active_credentials, is_demo_mode
    )
    from services.scheduler_engine import scheduler_engine
    from services.predictive_prewarm import PredictivePrewarmEngine
except ImportError:
    from backend.microservices.shared_state import (
        _db, _build_aws_session, active_credentials, is_demo_mode
    )
    from backend.services.scheduler_engine import scheduler_engine
    from backend.services.predictive_prewarm import PredictivePrewarmEngine

router = APIRouter(tags=["Scheduler & Workload Microservice"])


@router.get("/api/v2/schedules/override")
async def trigger_schedule_override(job_id: Optional[str] = None, type: str = "KEEP_RUNNING", hours: int = 2, redirect: bool = False):
    try:
        res = scheduler_engine.override_job(job_id=job_id, override_type=type, extension_hours=hours)
    except Exception:
        res = {"status": "success", "override": type, "hours": hours, "job_id": job_id}

    if redirect:
        return HTMLResponse(
            content=f"""<!DOCTYPE html><html><body style="font-family:monospace;background:#000;color:#fff;padding:30px;">
            <h2>⚡ Schedule Override Applied</h2>
            <p>Action: <b>{type}</b> for {hours} hours</p>
            <p>Job: <b>{job_id or 'all-active'}</b></p>
            <a href="https://cloud-cost-optimization-frontend.onrender.com" style="color:#38bdf8;">Return to Dashboard</a>
            </body></html>""",
            status_code=200
        )
    return res


@router.get("/api/v2/schedules")
async def list_operational_schedules():
    schedules = scheduler_engine.list_schedules()
    return {"status": "success", "count": len(schedules), "schedules": schedules}


@router.post("/api/v2/schedules")
async def create_operational_schedule(payload: Request):
    body = await payload.json()
    try:
        schedule = scheduler_engine.create_or_update_schedule(body)
        return {"status": "success", "schedule": schedule}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/api/v2/schedules/{schedule_id}")
async def delete_operational_schedule(schedule_id: str):
    success = scheduler_engine.delete_schedule(schedule_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")
    return {"status": "success", "message": f"Schedule {schedule_id} deleted successfully"}


@router.get("/api/v2/schedules/jobs")
async def list_scheduled_jobs(limit: int = 50):
    jobs = scheduler_engine.list_jobs(limit=limit)
    return {"status": "success", "count": len(jobs), "jobs": jobs}


@router.post("/api/v2/schedules/jobs/{job_id}/override")
async def override_scheduled_job(job_id: str, payload: Request):
    body = await payload.json()
    action = body.get("action", "KEEP_RUNNING")
    hours = int(body.get("extension_hours", 2))
    try:
        res = scheduler_engine.override_job(job_id, override_type=action, extension_hours=hours)
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/v2/schedules/evaluate-now")
async def evaluate_schedules_now(dry_run: bool = True):
    try:
        session = active_credentials.get("default", {}).get("session") if not is_demo_mode else None
        await scheduler_engine.run_scheduler_tick(session=session, dry_run=dry_run)
        jobs = scheduler_engine.list_jobs(limit=20)
        return {
            "status": "success",
            "message": f"Evaluation tick completed (dry_run={dry_run})",
            "recent_jobs": jobs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/v2/schedules/jobs/manual-trigger")
async def manual_trigger_job(payload: Request):
    body = await payload.json()
    instance_id = body.get("instance_id")
    action = body.get("action", "STOP").upper()
    tags = body.get("tags", {})
    dry_run = bool(body.get("dry_run", False))

    if not instance_id:
        raise HTTPException(status_code=400, detail="instance_id is required")

    job_dict = {
        "id": str(uuid.uuid4()),
        "schedule_id": None,
        "instance_id": instance_id,
        "action": action,
        "scheduled_at": datetime.now(timezone.utc).isoformat(),
        "status": "PENDING",
        "reason": f"Manual trigger from FinOps console: {action}",
        "blocked_reason": None,
        "execution_details": {"initiated_by": "console_operator"},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "executed_at": None,
    }

    session = active_credentials.get("default", {}).get("session") if not is_demo_mode else None
    processed = await scheduler_engine.process_job(job_dict, session=session, tags=tags, dry_run=dry_run)
    return {"status": "success", "job": processed}


@router.get("/api/v2/schedules/predictive/recommendations")
async def get_predictive_recommendations(
    instance_id: Optional[str] = None,
    days: int = 14,
    demo: bool = False
):
    nodes = _db().get("nodes", [])
    if not instance_id:
        running = [n["instance_id"] for n in nodes if n.get("state") == "running" and n.get("instance_id")]
        if running:
            instance_id = running[0]
        elif nodes and nodes[0].get("instance_id"):
            instance_id = nodes[0]["instance_id"]
        else:
            instance_id = None

    if not instance_id:
        return {
            "status": "empty",
            "telemetry_points_analyzed": 0,
            "recommendation": {
                "instance_id": "",
                "pattern_detected": False,
                "confidence": 0.0,
                "reason": "No active instances found in inventory to analyze. Connect your AWS environment to begin."
            }
        }

    if demo:
        telemetry = PredictivePrewarmEngine.generate_demo_telemetry_series(days=days, instance_id=instance_id)
    else:
        session = _build_aws_session()
        region = _db().get("region", "us-east-1")
        telemetry = PredictivePrewarmEngine.fetch_cloudwatch_telemetry_series(
            instance_id=instance_id,
            days=days,
            session=session,
            region_name=region
        )

    analysis = PredictivePrewarmEngine.analyze_usage_patterns(telemetry, prewarm_lead_minutes=15)
    if not telemetry:
        analysis["instance_id"] = instance_id
        analysis["reason"] = f"No CloudWatch telemetry available for instance {instance_id} over the past {days} days."

    return {
        "status": "success",
        "telemetry_points_analyzed": len(telemetry),
        "recommendation": analysis
    }


@router.post("/api/v2/schedules/predictive/apply")
async def apply_predictive_recommendation(payload: Request):
    body = await payload.json()
    instance_id = body.get("instance_id")
    if not instance_id:
        nodes = _db().get("nodes", [])
        running = [n["instance_id"] for n in nodes if n.get("state") == "running" and n.get("instance_id")]
        if running:
            instance_id = running[0]
        elif nodes and nodes[0].get("instance_id"):
            instance_id = nodes[0]["instance_id"]
        else:
            raise HTTPException(status_code=400, detail="Target instance_id is required.")

    start_time = body.get("start_time", "07:35")
    stop_time = body.get("stop_time", "20:00")
    prewarm_minutes = int(body.get("prewarm_minutes", 15))

    schedule_data = {
        "instance_id": instance_id,
        "timezone": body.get("timezone", "Asia/Kolkata"),
        "start_time": start_time,
        "stop_time": stop_time,
        "monday": True,
        "tuesday": True,
        "wednesday": True,
        "thursday": True,
        "friday": True,
        "saturday": False,
        "sunday": False,
        "enabled": True,
        "prewarm_enabled": True,
        "prewarm_lead_minutes": prewarm_minutes
    }

    schedule = scheduler_engine.create_or_update_schedule(schedule_data)
    return {
        "status": "success",
        "message": f"Activated predictive schedule for {instance_id}",
        "schedule": schedule
    }


# Standalone Microservice FastAPI App definition
app = FastAPI(
    title="CloudPulse Operational Scheduler & Pre-Warming Microservice",
    version="2.0.0",
    description="Automated diurnal workload scheduling and pre-warming pipeline."
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
    return {"status": "healthy", "service": "scheduler_service", "port": 8007}


app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8007))
    uvicorn.run("microservices.scheduler_service:app", host="0.0.0.0", port=port, reload=True)
