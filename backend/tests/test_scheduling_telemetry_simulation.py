import asyncio
import pytest
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from backend.services.predictive_prewarm import PredictivePrewarmEngine
from backend.services.scheduler_engine import SchedulerEngine
from backend.remediation.guardian import GuardianValidator


def test_predictive_prewarm_from_telemetry():
    """
    Step 1: Test telemetry generation and usage pattern detection.
    Should detect activity ramp-up at ~07:45 and set pre-warm start at ~07:30-07:35.
    """
    instance_id = "i-0a817b3c4d5e6f001"
    telemetry = PredictivePrewarmEngine.generate_demo_telemetry_series(days=14, instance_id=instance_id)

    assert len(telemetry) > 500
    assert any(pt["cpu_utilization"] < 5.0 for pt in telemetry) # Has overnight micro-idle
    assert any(pt["cpu_utilization"] > 60.0 for pt in telemetry) # Has peak workload

    # Analyze patterns
    analysis = PredictivePrewarmEngine.analyze_usage_patterns(telemetry, prewarm_lead_minutes=15)

    print("\n--- Telemetry Pattern Analysis Output ---")
    print(f"Instance ID: {analysis['instance_id']}")
    print(f"Pattern Detected: {analysis['pattern_detected']}")
    print(f"Confidence: {analysis['confidence'] * 100}%")
    print(f"Detected Activity Start: {analysis['detected_activity_start']}")
    print(f"Recommended Pre-Warm Start: {analysis['recommended_start_time']}")
    print(f"Recommended Stop Time: {analysis['recommended_stop_time']}")
    print(f"Estimated Compute Savings: {analysis['estimated_savings_percent']}%")
    print(f"Reason: {analysis['reason']}")

    assert analysis["pattern_detected"] is True
    assert analysis["confidence"] >= 0.80
    assert "07:" in analysis["detected_activity_start"] # Ramps up around 07:30 - 07:45
    assert analysis["estimated_savings_percent"] > 50.0


def test_complete_scheduling_pipeline_lifecycle():
    """
    Step 2: Test complete scheduling pipeline lifecycle across simulated timeline:
    - Pre-warm event at 07:35 -> Guardian Approved -> Started
    - Active SSH safety gate at 12:00 -> Stop Blocked by Guardian
    - Grace period notification at 19:50 -> Status NOTIFYING
    - Developer [KEEP RUNNING] override -> Status OVERRIDDEN
    - Scheduled stop at 20:00 -> Guardian Clear -> Successfully Stopped
    """
    eng = SchedulerEngine()
    instance_id = "i-telemetry-demo-node"

    # 1. Apply Predictive Schedule generated from telemetry
    sched_data = {
        "id": "sched-predictive-node-1",
        "instance_id": instance_id,
        "timezone": "UTC",
        "start_time": "07:50",
        "stop_time": "20:00",
        "monday": True,
        "tuesday": True,
        "wednesday": True,
        "thursday": True,
        "friday": True,
        "saturday": False,
        "sunday": False,
        "prewarm_minutes": 15,    # Triggers at 07:35
        "grace_period_minutes": 10, # Triggers at 19:50
        "enabled": True,
    }
    eng.create_or_update_schedule(sched_data)

    # -------------------------------------------------------------
    # Scenario A: 07:35 UTC (Pre-Warming Lead Time)
    # -------------------------------------------------------------
    t_prewarm = datetime(2026, 9, 23, 7, 35, 0, tzinfo=timezone.utc) # Wednesday
    due_jobs = eng.evaluate_schedules(now_dt=t_prewarm)
    assert len(due_jobs) >= 1

    prewarm_job = due_jobs[0]
    assert prewarm_job["action"] == "PREWARM"
    assert prewarm_job["instance_id"] == instance_id

    # Execute prewarm through Guardian and Safe Executor
    res_prewarm = asyncio.run(eng.process_job(prewarm_job, session=None, dry_run=True))
    assert res_prewarm["status"] == "SUCCESS"
    assert res_prewarm["execution_details"]["guardian_checks"]["guardrails_passed"] is True

    # -------------------------------------------------------------
    # Scenario B: 12:00 UTC (Active SSH Session Blocks Accidental Stop)
    # -------------------------------------------------------------
    midday_stop_job = {
        "id": "job-midday-stop-test",
        "schedule_id": None,
        "instance_id": instance_id,
        "action": "STOP",
        "scheduled_at": datetime(2026, 9, 23, 12, 0, 0, tzinfo=timezone.utc).isoformat(),
        "status": "PENDING",
        "reason": "Midday maintenance attempt",
        "execution_details": {},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "executed_at": None,
    }
    # Simulate active developer SSH session
    ssh_tags = {"active_ssh": "true", "active_sessions": "1"}
    blocked_job = asyncio.run(eng.process_job(midday_stop_job, session=None, tags=ssh_tags, dry_run=True))

    assert blocked_job["status"] == "BLOCKED"
    assert "active ssh" in blocked_job["blocked_reason"].lower()
    assert blocked_job["execution_details"]["guardian_checks"]["active_ssh"] is True

    # -------------------------------------------------------------
    # Scenario C: 19:50 UTC (10-minute Grace Period Notification)
    # -------------------------------------------------------------
    t_grace = datetime(2026, 9, 23, 19, 50, 0, tzinfo=timezone.utc)
    grace_jobs = eng.evaluate_schedules(now_dt=t_grace)
    assert len(grace_jobs) >= 1

    notifying_job = grace_jobs[0]
    assert notifying_job["status"] == "NOTIFYING"
    assert notifying_job["action"] == "STOP"
    assert "grace period" in notifying_job["reason"].lower()

    # -------------------------------------------------------------
    # Scenario D: Developer Override [KEEP RUNNING (3 Hours)]
    # -------------------------------------------------------------
    eng._record_job(notifying_job)
    override_result = eng.override_job(notifying_job["id"], override_type="KEEP_RUNNING", extension_hours=3)

    assert override_result["success"] is True
    assert override_result["job"]["status"] == "OVERRIDDEN"
    assert "Keep running for 3h" in override_result["job"]["reason"]

    # -------------------------------------------------------------
    # Scenario E: 20:00 UTC Normal Evening Stop (When Grace Passes & SSH Clear)
    # -------------------------------------------------------------
    t_stop = datetime(2026, 9, 23, 20, 0, 0, tzinfo=timezone.utc)
    stop_jobs = eng.evaluate_schedules(now_dt=t_stop)
    assert len(stop_jobs) >= 1

    evening_stop_job = stop_jobs[0]
    clean_tags = {"active_ssh": "false", "backup_running": "false", "env": "development"}
    final_stop_res = asyncio.run(eng.process_job(evening_stop_job, session=None, tags=clean_tags, dry_run=True))

    assert final_stop_res["status"] == "SUCCESS"
    assert final_stop_res["execution_details"]["guardian_checks"]["guardrails_passed"] is True

    # -------------------------------------------------------------
    # Scenario F: Auditable History Verification
    # -------------------------------------------------------------
    all_jobs = eng.list_jobs(limit=10)
    assert len(all_jobs) >= 4
    statuses = [j["status"] for j in all_jobs]
    assert "SUCCESS" in statuses
    assert "BLOCKED" in statuses
    assert "OVERRIDDEN" in statuses


if __name__ == "__main__":
    test_predictive_prewarm_from_telemetry()
    test_complete_scheduling_pipeline_lifecycle()
    print("\n✅ ALL TELEMETRY & SCHEDULING PIPELINE SIMULATION TESTS PASSED!")
