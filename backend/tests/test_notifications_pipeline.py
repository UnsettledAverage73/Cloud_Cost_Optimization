"""
Comprehensive Unit & Integration Test Suite for CloudPulse Multi-Channel Notification Pipeline
Validates Slack Block Kit & Microsoft Teams Adaptive Cards across all functionalities:
1. FinOps Single Waste Alerts
2. Fleet Batch Optimization Digests
3. Real-Time Cost Anomaly Spikes
4. Operational Scheduler 10-Minute Pre-Stop Grace Period Warnings
5. Post-Remediation SLA Watchdog & Automated Revert Alerts
6. GitOps Pull Request Alerts
7. Interactive Two-Way Callbacks (Batch PR, Apply, Snooze, Keep Running, Stop Now, Acknowledge)
8. Universal Event Router, Configuration & Delivery History
9. FastAPI Notification Endpoints
"""

import json
from unittest.mock import MagicMock
import urllib.request
import pytest
from fastapi.testclient import TestClient

from main import app
from services.notification_engine import notification_engine, FinOpsNotificationEngine


def test_slack_waste_alert_block_kit():
    """Validates Slack Block Kit structure for single resource waste alerts."""
    card = notification_engine.format_slack_alert(
        resource_id="i-0a106c14603cb65a0",
        finding_title="Idle Compute Instance",
        severity="HIGH",
        current_monthly_spend=60.80,
        potential_monthly_savings=24.50,
        recommended_action="Downsize to Graviton t4g.small",
        repo_name="org/infra"
    )
    assert "blocks" in card
    assert "text" in card
    blocks = card["blocks"]
    assert blocks[0]["type"] == "header"
    assert "Waste Alert" in blocks[0]["text"]["text"]
    assert any("i-0a106c14603cb65a0" in str(b) for b in blocks)
    actions = next(b for b in blocks if b.get("type") == "actions")
    action_ids = [e["action_id"] for e in actions["elements"]]
    assert "cloudpulse_open_pr" in action_ids
    assert "cloudpulse_apply_now" in action_ids
    assert "cloudpulse_snooze" in action_ids


def test_teams_waste_alert_adaptive_card():
    """Validates Microsoft Teams Adaptive Card v1.4 structure for single resource waste alerts."""
    card = notification_engine.format_teams_adaptive_card(
        resource_id="vol-00d9bb20516b3992b",
        finding_title="Unattached gp2 Storage Volume",
        severity="MEDIUM",
        current_monthly_spend=12.00,
        potential_monthly_savings=12.00,
        recommended_action="Delete unattached volume"
    )
    assert card["type"] == "message"
    attachments = card["attachments"]
    assert len(attachments) == 1
    content = attachments[0]["content"]
    assert content["type"] == "AdaptiveCard"
    assert content["version"] == "1.4"
    actions = content["actions"]
    assert any(a.get("title") == "🚀 Open Terraform PR" for a in actions)
    assert any(a.get("title") == "⚡ 1-Click Remediate" for a in actions)


def test_slack_and_teams_batch_summary():
    """Validates fleet batch summary digests for Slack and Teams with dual currency."""
    sample_findings = [
        {"resource_id": "i-1234", "category": "Compute", "action": "downsize", "monthly_savings": 20.0},
        {"resource_id": "vol-5678", "category": "Storage", "action": "upgrade_gp3", "monthly_savings": 5.0}
    ]
    # Slack
    slack_card = notification_engine.format_slack_batch_summary(
        findings=sample_findings,
        total_monthly_spend=100.0,
        total_monthly_savings=25.0,
        health_score=88.0,
        account_id="582812122408",
        currency="USD"
    )
    assert "blocks" in slack_card
    assert any("Fleet Optimization Digest" in str(b) for b in slack_card["blocks"])

    # Teams
    teams_card = notification_engine.format_teams_batch_adaptive_card(
        findings=sample_findings,
        total_monthly_spend=100.0,
        total_monthly_savings=25.0,
        health_score=88.0,
        account_id="582812122408",
        currency="INR"
    )
    assert teams_card["type"] == "message"
    card_content = teams_card["attachments"][0]["content"]
    assert any("Fleet FinOps Optimization Digest" in str(b) for b in card_content["body"])


def test_anomaly_notifications_slack_and_teams():
    """Validates real-time cost anomaly alert formatting."""
    anomaly_data = {
        "resource_id": "i-runaway-compute",
        "service": "Amazon EC2",
        "severity": "CRITICAL",
        "observed_value": 85.50,
        "expected_baseline": 15.00,
        "percentage_increase": 470.0,
        "root_cause_analysis": "Sudden unmonitored scale out in us-east-1"
    }

    # Slack Anomaly Card
    slack_card = notification_engine.format_slack_anomaly_alert(anomaly_data)
    assert "blocks" in slack_card
    assert any("Cost Spike Detected: +470.0% Surge" in str(b) for b in slack_card["blocks"])
    actions = next(b for b in slack_card["blocks"] if b.get("type") == "actions")
    assert any(e.get("action_id") == "cloudpulse_anomaly_pr" for e in actions["elements"])

    # Teams Anomaly Card
    teams_card = notification_engine.format_teams_anomaly_alert(anomaly_data)
    content = teams_card["attachments"][0]["content"]
    assert any("+470.0%" in str(b) for b in content["body"])


def test_grace_period_notifications_slack_and_teams():
    """Validates operational scheduler 10-minute grace period alert formatting."""
    job = {
        "id": "job-grace-test-123",
        "instance_id": "i-dev-workstation",
        "action": "STOP",
        "reason": "Non-production evening auto-shutdown"
    }

    # Slack Grace Period
    slack_card = notification_engine.format_slack_grace_period_alert(job)
    assert any("10 Minutes" in str(b) for b in slack_card["blocks"])
    actions = next(b for b in slack_card["blocks"] if b.get("type") == "actions")
    action_ids = [e["action_id"] for e in actions["elements"]]
    assert "cloudpulse_scheduler_keep_running" in action_ids
    assert "cloudpulse_scheduler_stop_now" in action_ids

    # Teams Grace Period
    teams_card = notification_engine.format_teams_grace_period_alert(job)
    content = teams_card["attachments"][0]["content"]
    assert any("Shutdown Imminent" in str(b) for b in content["body"])
    actions = content["actions"]
    assert any("Keep Running" in a.get("title", "") for a in actions)
    assert any("Stop Now" in a.get("title", "") for a in actions)


def test_sla_breach_notifications_slack_and_teams():
    """Validates post-remediation SLA watchdog breach alert formatting."""
    watch = {
        "watch_id": "watch-sla-001",
        "resource_id": "i-app-cluster",
        "remediation_action": "migrate_graviton"
    }
    reasons = ["P95 latency spiked by +28.5%", "5xx error rate rose to 2.1%"]
    rollback_pr = {"pull_request_url": "https://github.com/org/repo/pull/999"}

    # Slack SLA Alert
    slack_card = notification_engine.format_slack_sla_breach_alert(watch, reasons, rollback_pr)
    assert any("Automated Revert Triggered" in str(b) for b in slack_card["blocks"])
    assert any("https://github.com/org/repo/pull/999" in str(b) for b in slack_card["blocks"])

    # Teams SLA Alert
    teams_card = notification_engine.format_teams_sla_breach_alert(watch, reasons, rollback_pr)
    content = teams_card["attachments"][0]["content"]
    assert any("Automated Revert Triggered" in str(b) for b in content["body"])


def test_gitops_pr_notifications_slack_and_teams():
    """Validates GitOps PR opening notifications for Slack and Teams."""
    pr_pkg = {
        "repo_name": "infrastructure/aws-workloads",
        "branch_name": "finops/remediate-i-1234",
        "pull_request_url": "https://github.com/infrastructure/aws-workloads/pull/123",
        "estimated_monthly_savings": 32.50,
        "title": "Migrate i-1234 to Graviton3"
    }

    slack_card = notification_engine.format_slack_gitops_pr_alert(pr_pkg)
    assert "https://github.com/infrastructure/aws-workloads/pull/123" in str(slack_card)

    teams_card = notification_engine.format_teams_gitops_pr_alert(pr_pkg)
    assert "https://github.com/infrastructure/aws-workloads/pull/123" in str(teams_card)


def test_interactive_callbacks_full_suite():
    """Validates two-way interactive callback execution across all supported actions."""
    # 1. Batch PR callback
    res_batch = notification_engine.handle_interactive_callback({"action": "batch_pr", "repo": "test/infra"})
    assert res_batch["status"] == "success"
    assert "pr_url" in res_batch

    # 2. Single Resource PR callback
    res_pr = notification_engine.handle_interactive_callback({
        "action": "pr",
        "resource_id": "i-test-unit",
        "remediation_action": "migrate_graviton",
        "monthly_savings": 25.0
    })
    assert res_pr["status"] == "success"
    assert "i-test-unit" in res_pr["branch"]

    # 3. Direct Apply / Remediate callback
    res_apply = notification_engine.handle_interactive_callback({
        "action": "apply",
        "resource_id": "i-test-unit",
        "remediation_action": "stop"
    })
    assert res_apply["status"] == "success"
    assert res_apply["scheduled"] is True

    # 4. Snooze callback
    res_snooze = notification_engine.handle_interactive_callback({"action": "snooze"})
    assert res_snooze["status"] == "success"
    assert res_snooze["snoozed_days"] == 14

    # 5. Grace period keep running callback
    res_keep = notification_engine.handle_interactive_callback({
        "action": "keep_running",
        "job_id": "nonexistent-job-id",
        "hours": 3
    })
    assert res_keep["status"] == "success"
    assert "+3 hours" in res_keep["message"]

    # 6. Grace period stop now callback
    res_stop = notification_engine.handle_interactive_callback({
        "action": "stop_now",
        "job_id": "nonexistent-job-id"
    })
    assert res_stop["status"] == "success"

    # 7. Anomaly acknowledge callback
    res_ack = notification_engine.handle_interactive_callback({
        "action": "anomaly_acknowledge",
        "resource_id": "i-runaway-node"
    })
    assert res_ack["status"] == "success"
    assert res_ack["acknowledged"] is True

    # 8. Slack URL-encoded format parser
    slack_payload = {
        "payload": json.dumps({
            "type": "block_actions",
            "actions": [{"action_id": "cloudpulse_snooze", "value": json.dumps({"action": "snooze", "days": 7})}]
        })
    }
    res_slack = notification_engine.handle_interactive_callback(slack_payload)
    assert res_slack["status"] == "success"
    assert res_slack["snoozed_days"] == 7


def test_notification_configuration_and_history():
    """Validates configuration CRUD and delivery history tracking."""
    # Update config
    cfg = notification_engine.update_config({
        "slack_channel": "#finops-test-alerts",
        "enabled_channels": {"slack": True, "teams": True}
    })
    assert cfg["slack_channel"] == "#finops-test-alerts"
    assert cfg["enabled_channels"]["slack"] is True

    # Record delivery history
    notification_engine.record_history({
        "channel": "slack",
        "target": "#finops-test-alerts",
        "status": "DELIVERED",
        "event_type": "unit_test"
    })
    hist = notification_engine.get_history(limit=5)
    assert len(hist) > 0
    assert hist[0]["channel"] == "slack"
    assert hist[0]["status"] == "DELIVERED"


def test_universal_dispatcher_mock(monkeypatch):
    """Validates universal event routing with mocked webhooks."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__enter__.return_value = mock_resp
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=5.0: mock_resp)

    # Configure mock webhook endpoints
    notification_engine.update_config({
        "slack_webhook_url": "https://hooks.slack.com/services/T00/B00/UNITTEST",
        "teams_webhook_url": "https://prod-00.westus.logic.azure.com:443/workflows/unit/invoke",
        "enabled_channels": {"slack": True, "teams": True}
    })

    # Dispatch test event
    dispatch_res = notification_engine.dispatch_event("test", {}, channels=["slack", "teams"])
    assert dispatch_res["status"] == "completed"
    assert dispatch_res["results"]["slack"] is True
    assert dispatch_res["results"]["teams"] is True


def test_api_notification_endpoints():
    """Validates FastAPI REST endpoints for the complete notification pipeline."""
    client = TestClient(app)

    # 1. GET & POST /api/v2/notifications/config
    res_cfg = client.get("/api/v2/notifications/config")
    assert res_cfg.status_code == 200
    assert "enabled_channels" in res_cfg.json()

    res_update = client.post("/api/v2/notifications/config", json={
        "slack_channel": "#finops-api-test"
    })
    assert res_update.status_code == 200
    assert res_update.json()["slack_channel"] == "#finops-api-test"

    # 2. GET /api/v2/notifications/history
    res_hist = client.get("/api/v2/notifications/history")
    assert res_hist.status_code == 200
    assert "history" in res_hist.json()

    # 3. POST /api/v2/notifications/anomaly
    res_anom = client.post("/api/v2/notifications/anomaly", json={
        "resource_id": "i-api-test",
        "observed_value": 90.0,
        "expected_baseline": 20.0,
        "percentage_increase": 350.0
    })
    assert res_anom.status_code == 200

    # 4. POST /api/v2/notifications/grace-period
    res_grace = client.post("/api/v2/notifications/grace-period", json={
        "job": {"id": "job-api-1", "instance_id": "i-api-test", "action": "STOP"}
    })
    assert res_grace.status_code == 200

    # 5. POST /api/v2/notifications/sla
    res_sla = client.post("/api/v2/notifications/sla", json={
        "watch": {"resource_id": "i-api-test", "remediation_action": "migrate_graviton"},
        "breach_reasons": ["P95 latency breach"]
    })
    assert res_sla.status_code == 200

    # 6. POST /api/v2/notifications/interactive/callback (JSON)
    res_cb = client.post("/api/v2/notifications/interactive/callback", json={
        "action": "snooze"
    })
    assert res_cb.status_code == 200
    assert res_cb.json()["status"] == "success"

    # 7. POST /api/v2/notifications/interactive/callback (Form-urlencoded for Slack)
    res_cb_slack = client.post(
        "/api/v2/notifications/interactive/callback",
        data={"payload": json.dumps({"actions": [{"action_id": "cloudpulse_snooze", "value": json.dumps({"action": "snooze"})}]})},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert res_cb_slack.status_code == 200
    assert res_cb_slack.json()["status"] == "success"
