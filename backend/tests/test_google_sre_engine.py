import pytest
from backend.engines.google_sre_engine import GoogleSreEngine, google_sre_engine

def test_evaluate_golden_signals():
    engine = GoogleSreEngine()
    signals = engine.evaluate_golden_signals(
        resource_id="i-test12345",
        resource_name="Checkout-Service",
        base_latency_ms=40.0,
        base_rps=500.0,
        error_count=5,
        total_requests=20000,
        cpu_pct=52.0,
        mem_pct=64.0,
        disk_pct=40.0
    )

    assert signals["resource_id"] == "i-test12345"
    assert signals["health_status"] == "HEALTHY"
    latency = signals["signals"]["latency"]
    assert latency["p50_ms"] < latency["p90_ms"] < latency["p95_ms"] < latency["p99_ms"]
    assert latency["p95_ms"] > 0
    assert signals["signals"]["traffic"]["requests_per_second"] == 500.0
    assert signals["signals"]["errors"]["error_rate_pct"] > 0.0
    assert signals["signals"]["saturation"]["headroom_pct"] == 36.0


def test_calculate_error_budget_healthy():
    engine = GoogleSreEngine()
    budget = engine.calculate_error_budget(
        slo_target=0.999,
        window_days=30,
        total_requests=1000000,
        successful_requests=999800,
        recent_1h_error_rate_pct=0.01,
        recent_6h_error_rate_pct=0.01
    )

    assert budget["slo_target_pct"] == 99.9
    assert budget["budget_remaining_pct"] > 70.0
    assert budget["deployment_freeze_active"] is False
    assert budget["status"] in ("HEALTHY", "AT_RISK")


def test_calculate_error_budget_fast_burn_freeze():
    engine = GoogleSreEngine()
    budget = engine.calculate_error_budget(
        slo_target=0.999,
        window_days=30,
        total_requests=1000000,
        successful_requests=990000,
        recent_1h_error_rate_pct=1.8, # 18x burn rate
        recent_6h_error_rate_pct=0.8
    )

    assert budget["burn_rate_1h"] >= 14.4
    assert budget["fast_burn_alert_14x"] is True
    assert budget["deployment_freeze_active"] is True
    assert "FREEZE" in budget["status"] or "FAST_BURN" in budget["status"]


def test_evaluate_canary_rollout():
    engine = GoogleSreEngine()
    result = engine.evaluate_canary_rollout(
        baseline_id="i-baseline-x86",
        canary_id="i-canary-arm64",
        baseline_p95_ms=38.0,
        canary_p95_ms=39.0,
        baseline_error_rate=0.0,
        canary_error_rate=0.0,
        baseline_cpu_pct=50.0,
        canary_cpu_pct=25.0
    )

    assert result["canary_score"] >= 80.0
    assert result["canary_passed"] is True
    assert result["metrics"]["latency"]["status"] == "PASS"


def test_generate_blameless_postmortem():
    engine = GoogleSreEngine()
    postmortem = engine.generate_blameless_postmortem(
        incident_id="INC-8291",
        service_name="Payment-Gateway",
        incident_title="P95 Latency Spike on Downsized EC2 Instance",
        root_cause_summary="Workload CPU peaked during midnight billing batch.",
        detection_time="2026-10-03T01:00:00Z",
        mitigation_time="2026-10-03T01:08:00Z",
        affected_resources=["i-07d01b00f95a4cc41"]
    )

    assert postmortem["incident_id"] == "INC-8291"
    assert postmortem["metrics"]["mttr_minutes"] == 8.0
    assert len(postmortem["five_whys"]) == 5
    assert len(postmortem["action_items"]) == 3


def test_sre_api_endpoints():
    from fastapi.testclient import TestClient
    from backend.main import app

    client = TestClient(app)

    # 1. Golden signals
    res = client.get("/api/v2/sre/golden-signals")
    assert res.status_code == 200
    data = res.json()
    assert "signals" in data
    assert "latency" in data["signals"]
    assert "traffic" in data["signals"]
    assert "errors" in data["signals"]
    assert "saturation" in data["signals"]

    # 2. Error budget
    res = client.get("/api/v2/sre/error-budget?slo_target=0.999")
    assert res.status_code == 200
    budget = res.json()
    assert budget["slo_target_pct"] == 99.9
    assert "burn_rate_1h" in budget
    assert "deployment_freeze_active" in budget

    # 3. Canary analysis
    res = client.get("/api/v2/sre/canary-analysis")
    assert res.status_code == 200
    canary = res.json()
    assert "canary_score" in canary
    assert "metrics" in canary

    # 4. Generate postmortem
    res = client.post("/api/v2/sre/postmortem/generate", json={
        "incident_id": "INC-TEST-SRE",
        "title": "Automated Revert Verification"
    })
    assert res.status_code == 200
    pm = res.json()
    assert pm["incident_id"] == "INC-TEST-SRE"
    assert "five_whys" in pm
    assert "action_items" in pm

