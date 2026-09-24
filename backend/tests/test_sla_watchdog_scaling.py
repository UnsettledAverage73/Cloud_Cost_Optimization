"""
Unit & Integration Tests for CloudPulse Post-Remediation SLA Watchdog & Automated Rollback Engine (Milestone 3 - Priority 3).
Verifies 60-minute watch periods, CloudWatch SLA threshold comparisons, automated git revert PR generation,
FastAPI endpoints, and CLI 'cloudpulse watch' command execution.
"""

import json
import argparse
import pytest

try:
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
except Exception:
    try:
        from fastapi.testclient import TestClient
        from backend.main import app
        client = TestClient(app)
    except Exception:
        TestClient = None
        client = None

try:
    from services.sla_watchdog import SLAWatchdog, sla_watchdog
    from cli_main import cmd_watch
except ImportError:
    from backend.services.sla_watchdog import SLAWatchdog, sla_watchdog
    from backend.cli_main import cmd_watch


@pytest.fixture
def watchdog():
    """Returns an isolated SLA watchdog instance for deterministic testing."""
    return SLAWatchdog(load_disk=False)


def test_watchdog_initialization(watchdog):
    """Verifies that the watchdog initializes with default tracking periods."""
    watches = watchdog.list_watches()
    assert len(watches) >= 2
    watch_ids = [w["watch_id"] for w in watches]
    assert "watch-i-07d01b00f95a4cc41-graviton" in watch_ids
    assert "watch-i-07d01b00f95a4cc41-ebs-gp3" in watch_ids


def test_register_watch_period(watchdog):
    """Verifies custom registration of a post-remediation SLA watch window."""
    entry = watchdog.register_watch(
        resource_id="i-test-instance-1234",
        remediation_action="downsize_instance",
        repo_name="org/infra",
        file_path="terraform/ec2.tf",
        previous_config={"instance_type": "m5.2xlarge", "monthly_cost": 280.32},
        applied_config={"instance_type": "m5.large", "monthly_cost": 70.08},
        baseline_metrics={"p95_latency_ms": 50.0, "error_rate_pct": 0.0, "cpu_utilization_avg": 20.0},
        duration_minutes=60,
        max_latency_increase_pct=15.0,
    )

    assert entry["watch_id"].startswith("watch-")
    assert entry["resource_id"] == "i-test-instance-1234"
    assert entry["status"] == "MONITORING"
    assert entry["sla_breached"] is False
    assert entry["baseline_metrics"]["p95_latency_ms"] == 50.0


def test_evaluate_health_healthy(watchdog):
    """Verifies that within-SLA metrics maintain HEALTHY/MONITORING status without triggering rollback."""
    # EBS upgrade baseline is 6.5 ms. Test with 6.6 ms (+1.5% increase, well under 15% threshold)
    result = watchdog.evaluate_health(
        watch_id="watch-i-07d01b00f95a4cc41-ebs-gp3",
        observed_metrics={"p95_latency_ms": 6.6, "error_rate_pct": 0.0, "cpu_utilization_avg": 10.0},
    )

    assert result["sla_breached"] is False
    assert result["status"] in ("HEALTHY", "MONITORING")
    assert len(result["breach_reasons"]) == 0
    assert result["rollback_pr"] is None


def test_evaluate_health_breach_and_automated_rollback(watchdog):
    """Verifies that exceeding the 15% latency threshold triggers automated git revert PR generation."""
    # Baseline is 6.5 ms. Provide 12.0 ms (+85% increase, exceeds 15% SLA threshold)
    result = watchdog.evaluate_health(
        watch_id="watch-i-07d01b00f95a4cc41-ebs-gp3",
        observed_metrics={"p95_latency_ms": 12.0, "error_rate_pct": 0.01, "cpu_utilization_avg": 25.0},
    )

    assert result["sla_breached"] is True
    assert result["status"] == "ROLLED_BACK"
    assert any("latency" in r.lower() for r in result["breach_reasons"])

    rollback = result["rollback_pr"]
    assert rollback is not None
    assert rollback["status"] == "rollback_pr_ready"
    assert "github.com" in rollback["pull_request_url"]
    assert "cloudpulse/rollback-" in rollback["branch_name"]
    assert "[SLA ROLLBACK]" in rollback["pr_title"]
    assert rollback["restored_config"]["volume_type"] == "gp2"
    assert "+  type = \"gp2\"" in rollback["revert_diff"]


def test_manual_rollback_trigger(watchdog):
    """Verifies direct manual operator rollback invocation via watchdog engine."""
    rollback = watchdog.trigger_automated_rollback(
        watch_id="watch-i-07d01b00f95a4cc41-graviton",
        breach_reasons=["Manual user trigger"],
    )

    assert rollback["watch_id"] == "watch-i-07d01b00f95a4cc41-graviton"
    assert rollback["resource_id"] == "i-07d01b00f95a4cc41"
    assert "+  type = \"t3.large\"" in rollback["revert_diff"]
    assert rollback["restored_config"]["instance_type"] == "t3.large"

    # Watch status should be ROLLED_BACK
    watch = watchdog.get_watch("watch-i-07d01b00f95a4cc41-graviton")
    assert watch["status"] == "ROLLED_BACK"
    assert watch["sla_breached"] is True


def test_fastapi_sla_watch_endpoints():
    """Verifies the REST API endpoints for SLA watchdog operations."""
    if not client:
        pytest.skip("FastAPI client not available in local test environment")

    # 1. GET /api/v2/sla/watches
    res = client.get("/api/v2/sla/watches")
    assert res.status_code == 200
    data = res.json()
    assert "watches" in data
    assert len(data["watches"]) >= 2

    # 2. GET /api/v2/sla/watches/{watch_id}
    res = client.get("/api/v2/sla/watches/watch-i-07d01b00f95a4cc41-graviton")
    assert res.status_code == 200
    watch_data = res.json()["watch"]
    assert watch_data["resource_id"] == "i-07d01b00f95a4cc41"

    # 3. POST /api/v2/sla/watch (register)
    reg_payload = {
        "resource_id": "i-api-test-99",
        "remediation_action": "downsize_instance",
        "repo_name": "org/infra",
        "file_path": "terraform/compute.tf",
        "previous_config": {"instance_type": "c5.xlarge"},
        "applied_config": {"instance_type": "c5.large"},
        "baseline_metrics": {"p95_latency_ms": 30.0, "error_rate_pct": 0.0},
        "duration_minutes": 60,
        "max_latency_increase_pct": 15.0,
    }
    res = client.post("/api/v2/sla/watch", json=reg_payload)
    assert res.status_code == 200
    created = res.json()["watch"]
    created_id = created["watch_id"]

    # 4. POST /api/v2/sla/watches/{watch_id}/evaluate (simulate breach)
    eval_payload = {
        "metrics": {"p95_latency_ms": 50.0, "error_rate_pct": 0.02}
    }
    res = client.post(f"/api/v2/sla/watches/{created_id}/evaluate", json=eval_payload)
    assert res.status_code == 200
    eval_res = res.json()["evaluation"]
    assert eval_res["sla_breached"] is True
    assert eval_res["rollback_pr"] is not None

    # 5. POST /api/v2/sla/watches/{watch_id}/rollback
    res = client.post(f"/api/v2/sla/watches/{created_id}/rollback", json={"reason": "Manual operator override"})
    assert res.status_code == 200
    rollback_res = res.json()["rollback"]
    assert rollback_res["watch_id"] == created_id


def test_cli_cmd_watch_list(capsys):
    """Verifies running the CLI 'cloudpulse watch' command to list watches."""
    args = argparse.Namespace(
        command="watch",
        watch_id=None,
        evaluate=False,
        rollback=False,
        latency=None,
        format="table",
        output=None,
        json_only=False,
    )
    cmd_watch(args)
    captured = capsys.readouterr().out
    assert "CLOUDPULSE POST-REMEDIATION SLA WATCHDOG" in captured
    assert "watch-i-07d01b00f95a4cc41" in captured


def test_cli_cmd_watch_json(capsys):
    """Verifies running 'cloudpulse watch --json' outputs valid JSON data."""
    args = argparse.Namespace(
        command="watch",
        watch_id=None,
        evaluate=False,
        rollback=False,
        latency=None,
        format="json",
        output=None,
        json_only=True,
    )
    cmd_watch(args)
    captured = capsys.readouterr().out
    data = json.loads(captured)
    assert isinstance(data, list)
    assert len(data) >= 2
    assert "resource_id" in data[0]


def test_cli_cmd_watch_evaluate_breach(capsys):
    """Verifies CLI evaluation triggering automated rollback on breach."""
    args = argparse.Namespace(
        command="watch",
        watch_id="watch-i-07d01b00f95a4cc41-ebs-gp3",
        evaluate=True,
        rollback=False,
        latency=68.0,
        format="table",
        output=None,
        json_only=False,
    )
    cmd_watch(args)
    captured = capsys.readouterr().out
    assert "HEALTH EVALUATION" in captured
    assert "SLA Breached" in captured
    assert "True" in captured
    assert "Rollback PR Synthesized:" in captured
