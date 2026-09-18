import pytest
from fastapi.testclient import TestClient
import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from data.cloud_simulator import CloudSimulator
from data.finops_database import (
    record_remediation_audit,
    get_remediation_audit_logs,
    upsert_optimization,
    mark_optimization_applied,
    get_all_optimizations,
)
from services.cost_analytics import (
    calculate_finops_health_score,
    calculate_spend_forecast,
    detect_cost_anomalies,
    evaluate_inventory_optimizations,
)
from services.pricing_service import AWSPricingClient
from services.remediator import AutoRemediator
from services.finops_agent import FinOpsAgent

client = TestClient(app)


# ==============================================================================
# 1. CLOUD SIMULATOR TESTS
# ==============================================================================

def test_cloud_simulator_generation():
    env = CloudSimulator.generate_full_environment(org_name="TestOrg", region="us-east-1")
    assert env["metadata"]["organization"] == "TestOrg"
    assert len(env["nodes"]) >= 4
    assert len(env["ebs_volumes"]) >= 2
    assert len(env["elastic_ips"]) >= 2
    assert len(env["telemetry"]) == 24
    assert len(env["spend"]) == 30


# ==============================================================================
# 2. COST ANALYTICS & HEALTH SCORE TESTS
# ==============================================================================

def test_cost_analytics_health_score():
    env = CloudSimulator.generate_full_environment()
    health = calculate_finops_health_score(env)
    assert 0.0 <= health["overall_health_score"] <= 100.0
    assert health["grade"] in ["A", "B", "C", "D", "F"]
    assert "compute_efficiency" in health["pillars"]
    assert "storage_optimization" in health["pillars"]
    assert "network_cleanliness" in health["pillars"]
    assert "security_posture" in health["pillars"]


def test_evaluate_inventory_optimizations():
    env = CloudSimulator.generate_full_environment()
    opts = evaluate_inventory_optimizations(env)
    assert len(opts) > 0
    categories = [o["category"] for o in opts]
    assert "Network Waste" in categories or "Storage Waste" in categories


def test_cost_anomalies_detection():
    spend = [
        {"day": f"2026-09-0{i}", "aws": 10.0} for i in range(1, 8)
    ]
    # Inject spike
    spend.append({"day": "2026-09-08", "aws": 25.0})
    anomalies = detect_cost_anomalies(spend)
    assert len(anomalies) >= 1
    assert anomalies[0]["severity"] in ["HIGH", "CRITICAL"]


def test_spend_forecast():
    spend = [{"day": f"2026-09-0{i}", "aws": 20.0} for i in range(1, 8)]
    forecast = calculate_spend_forecast(spend, monthly_budget=700.0)
    assert forecast["current_daily_burn"] == 20.0
    assert forecast["projected_month_end"] == 600.0
    assert forecast["variance"] == 100.0
    assert forecast["budget_status"] == "healthy"


# ==============================================================================
# 3. PRICING SERVICE TESTS
# ==============================================================================

def test_pricing_client_catalog():
    pricing = AWSPricingClient()
    cost_t3 = pricing.get_instance_monthly_cost("t3.medium")
    assert cost_t3 == 30.40
    ebs_cost = pricing.get_ebs_monthly_cost("gp3", 100)
    assert ebs_cost == 8.00
    savings = pricing.calculate_gp2_to_gp3_savings(100)
    assert savings == 2.00


# ==============================================================================
# 4. REMEDIATOR (DRY RUN) TESTS
# ==============================================================================

def test_remediator_dry_run():
    remediator = AutoRemediator(dry_run=True)
    res_eip = remediator.release_unattached_eip("54.210.12.3")
    assert res_eip["status"] == "success"
    assert res_eip["dry_run"] is True

    res_vol = remediator.delete_unattached_volume("vol-0992817361abce")
    assert res_vol["status"] == "success"
    assert res_vol["dry_run"] is True

    res_gp3 = remediator.upgrade_volume_to_gp3("vol-0992817361abce")
    assert res_gp3["status"] == "success"

    res_stop = remediator.stop_idle_instance("i-036358db85d245e3a")
    assert res_stop["status"] == "success"

    res_retention = remediator.set_log_group_retention("/aws/lambda/test", retention_days=30)
    assert res_retention["status"] == "success"


# ==============================================================================
# 5. PERSISTENT LEDGER DATABASE TESTS
# ==============================================================================

def test_finops_database_audit_and_optimizations():
    record_remediation_audit("release_eip", "1.2.3.4", dry_run=True, status="simulated", details={"test": True})
    logs = get_remediation_audit_logs(limit=10)
    assert len(logs) >= 1
    assert logs[0]["action"] == "release_eip"

    opt = {
        "id": "rec-test-001",
        "resource_id": "vol-test-123",
        "type": "Idle Storage",
        "title": "Delete test volume",
        "description": "Test description",
        "monthly_savings": 15.00,
        "action": "delete_volume"
    }
    upsert_optimization(opt)
    mark_optimization_applied("rec-test-001", applied=True)
    all_opts = get_all_optimizations()
    assert any(o["id"] == "rec-test-001" and o["status"] == "applied" for o in all_opts)


# ==============================================================================
# 6. FINOPS AGENT SLASH COMMANDS TESTS
# ==============================================================================

def test_finops_agent_slash_commands():
    env = CloudSimulator.generate_full_environment()
    agent = FinOpsAgent(data_store=env)

    resp_health = agent.ask("/health")
    assert resp_health["type"] == "health_breakdown"
    assert "FinOps Health Score" in resp_health["summary"]

    resp_audit = agent.ask("/audit")
    assert resp_audit["type"] == "audit_report"
    assert resp_audit["findings_count"] > 0

    resp_optimize = agent.ask("/optimize")
    assert resp_optimize["type"] == "optimization_plan"
    assert resp_optimize["total_potential_savings"] > 0

    resp_forecast = agent.ask("/forecast")
    assert resp_forecast["type"] == "cost_forecast"

    resp_pricing = agent.ask("/pricing t3.large us-east-1")
    assert resp_pricing["type"] == "pricing_lookup"
    assert resp_pricing["monthly_rate"] == 60.80

    resp_remediate = agent.ask("/remediate")
    assert resp_remediate["type"] == "remediation_plan"
    assert resp_remediate["dry_run"] is True


# ==============================================================================
# 7. LIVE FASTAPI ENDPOINTS INTEGRATION TESTS
# ==============================================================================

def test_api_endpoints():
    # 1. Enable Demo Mode
    r_demo = client.post("/api/v1/demo/enable")
    assert r_demo.status_code == 200
    assert r_demo.json()["demo_mode"] is True

    # 2. Executive summary
    r_sum = client.get("/api/v1/dashboard/summary")
    assert r_sum.status_code == 200
    assert "monthly_spend" in r_sum.json()
    assert r_sum.json()["total_nodes"] >= 4

    # 3. Nodes
    r_nodes = client.get("/api/nodes")
    assert r_nodes.status_code == 200
    assert len(r_nodes.json()) >= 4

    # 4. Telemetry
    r_telem = client.get("/api/telemetry")
    assert r_telem.status_code == 200
    assert len(r_telem.json()) >= 1

    # 5. Spend
    r_spend = client.get("/api/spend")
    assert r_spend.status_code == 200
    assert len(r_spend.json()) >= 1

    # 6. Alerts
    r_alerts = client.get("/api/alerts")
    assert r_alerts.status_code == 200

    # 7. Optimizations
    r_opts = client.get("/api/optimizations")
    assert r_opts.status_code == 200

    # 8. Analytics: Health Score
    r_health = client.get("/api/v1/analytics/health-score")
    assert r_health.status_code == 200
    assert "overall_health_score" in r_health.json()

    # 9. Analytics: Forecast
    r_forecast = client.get("/api/v1/analytics/forecast")
    assert r_forecast.status_code == 200
    assert "projected_month_end" in r_forecast.json()

    # 10. Agent Chat
    r_chat = client.post("/api/v1/agent/chat", json={"query": "/health"})
    assert r_chat.status_code == 200
    assert "summary" in r_chat.json()

    # 11. Remediation Execute (Dry Run)
    r_rem = client.post("/api/v1/remediate/execute", json={"action": "release_eip", "resource_id": "34.195.88.204", "dry_run": True})
    assert r_rem.status_code == 200
    assert r_rem.json()["dry_run"] is True

    # 12. Remediation Audit Logs
    r_audit = client.get("/api/v1/remediate/audit")
    assert r_audit.status_code == 200
    assert "audit_logs" in r_audit.json()
