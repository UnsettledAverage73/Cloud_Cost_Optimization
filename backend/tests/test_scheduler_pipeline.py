import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

try:
    from main import app
    from services.scheduler_engine import scheduler_engine, SchedulerEngine
    from remediation.guardian import GuardianValidator
    from database.models import Schedule, ScheduledJob
except ImportError:
    from backend.main import app
    from backend.services.scheduler_engine import scheduler_engine, SchedulerEngine
    from backend.remediation.guardian import GuardianValidator
    from backend.database.models import Schedule, ScheduledJob

client = TestClient(app)


def test_guardian_validator_start_non_destructive():
    """START and PREWARM actions must always pass Guardian validation."""
    is_safe, reason, checks = asyncio.run(
        GuardianValidator.guardian_check("i-test01", action="START")
    )
    assert is_safe is True
    assert "approved" in reason.lower()
    assert checks["guardrails_passed"] is True

    is_safe2, _, _ = asyncio.run(
        GuardianValidator.guardian_check("i-test01", action="PREWARM")
    )
    assert is_safe2 is True


def test_guardian_validator_blocks_active_ssh():
    """Guardian must block STOP if active SSH / terminal session is detected."""
    tags = {"active_ssh": "true"}
    is_safe, reason, checks = asyncio.run(
        GuardianValidator.guardian_check("i-ssh01", action="STOP", tags=tags)
    )
    assert is_safe is False
    assert "active ssh" in reason.lower()
    assert checks["active_ssh"] is True


def test_guardian_validator_blocks_backup_running():
    """Guardian must block STOP if backup or volume snapshot is running."""
    tags = {"backup_running": "yes"}
    is_safe, reason, checks = asyncio.run(
        GuardianValidator.guardian_check("i-snap01", action="STOP", tags=tags)
    )
    assert is_safe is False
    assert "backup" in reason.lower()
    assert checks["backup_running"] is True


def test_guardian_validator_blocks_production_and_keepalive():
    """Guardian must block STOP if instance is in Production or marked keepalive."""
    # 1. Keepalive tag
    is_safe, reason, _ = asyncio.run(
        GuardianValidator.guardian_check("i-prod01", action="STOP", tags={"keepalive": "true"})
    )
    assert is_safe is False
    assert "protected" in reason.lower() or "keepalive" in reason.lower()

    # 2. Production env
    is_safe2, reason2, _ = asyncio.run(
        GuardianValidator.guardian_check("i-prod02", action="STOP", tags={"env": "prod"})
    )
    assert is_safe2 is False
    assert "production" in reason2.lower()


def test_scheduler_crud_and_eval():
    """Verify schedule creation, weekday matching, and job generation."""
    eng = SchedulerEngine()
    test_sched = {
        "instance_id": "i-unit-test-42",
        "timezone": "UTC",
        "start_time": "09:00",
        "stop_time": "18:00",
        "monday": True,
        "tuesday": True,
        "wednesday": True,
        "thursday": True,
        "friday": True,
        "saturday": False,
        "sunday": False,
        "prewarm_minutes": 15,
        "grace_period_minutes": 10,
        "enabled": True,
    }
    saved = eng.create_or_update_schedule(test_sched)
    assert saved["instance_id"] == "i-unit-test-42"
    assert saved["start_time"] == "09:00"

    # Test prewarm evaluation at 08:45 UTC on a Wednesday (2026-09-23)
    target_dt = datetime(2026, 9, 23, 8, 45, 0, tzinfo=timezone.utc)
    jobs = eng.evaluate_schedules(now_dt=target_dt)
    prewarm_jobs = [j for j in jobs if j["action"] == "PREWARM" and j["instance_id"] == "i-unit-test-42"]
    assert len(prewarm_jobs) >= 1
    assert prewarm_jobs[0]["action"] == "PREWARM"


def test_grace_period_override():
    """Test developer [KEEP RUNNING] override during grace period."""
    eng = SchedulerEngine()
    job = {
        "id": "job-override-test-01",
        "instance_id": "i-override-test",
        "action": "STOP",
        "scheduled_at": datetime.now(timezone.utc).isoformat(),
        "status": "NOTIFYING",
        "reason": "Grace period warning",
        "execution_details": {},
    }
    eng._record_job(job)

    # Click KEEP RUNNING for 3 hours
    res = eng.override_job("job-override-test-01", override_type="KEEP_RUNNING", extension_hours=3)
    assert res["success"] is True
    assert res["job"]["status"] == "OVERRIDDEN"
    assert "Keep running for 3h" in res["job"]["reason"]


def test_api_schedules_endpoints():
    """Test FastAPI REST endpoints for schedules and jobs."""
    # 1. GET /api/v2/schedules
    resp = client.get("/api/v2/schedules")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert "schedules" in data

    # 2. POST /api/v2/schedules
    new_payload = {
        "instance_id": "i-fastapi-test",
        "timezone": "Asia/Kolkata",
        "start_time": "07:30",
        "stop_time": "19:30",
        "monday": True,
        "tuesday": True,
        "prewarm_minutes": 20,
        "enabled": True,
    }
    create_resp = client.post("/api/v2/schedules", json=new_payload)
    assert create_resp.status_code == 200
    sched = create_resp.json()["schedule"]
    sched_id = sched["id"]
    assert sched["instance_id"] == "i-fastapi-test"

    # 3. GET /api/v2/schedules/jobs
    jobs_resp = client.get("/api/v2/schedules/jobs")
    assert jobs_resp.status_code == 200
    assert "jobs" in jobs_resp.json()

    # 4. POST /api/v2/schedules/jobs/manual-trigger with dry_run
    trigger_resp = client.post("/api/v2/schedules/jobs/manual-trigger", json={
        "instance_id": "i-fastapi-test",
        "action": "START",
        "dry_run": True
    })
    assert trigger_resp.status_code == 200
    res_job = trigger_resp.json()["job"]
    assert res_job["status"] == "SUCCESS"

    # 5. DELETE /api/v2/schedules/{id}
    del_resp = client.delete(f"/api/v2/schedules/{sched_id}")
    assert del_resp.status_code == 200
