"""
Unit & Integration Tests for CloudPulse Autonomous GitOps Remediation & Notification Engine (Phase 3).
Verifies safety pre-flight verification, Terraform diff generation, Slack/Teams alerting, and CLI apply.
"""

import os
import json
import time
import pytest
import argparse
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from services.gitops_engine import GitOpsRemediationEngine, gitops_engine
from services.notification_engine import FinOpsNotificationEngine, notification_engine
from cli_main import cmd_apply, cmd_notify
from main import app


@pytest.fixture
def clean_gitops_engine():
    engine = GitOpsRemediationEngine()
    engine.audit_log = []
    return engine


def test_preflight_safety_production_enforcement(clean_gitops_engine):
    """Verifies that production resources strictly require GitOps PR approval."""
    preflight = clean_gitops_engine.evaluate_preflight_safety(
        resource_id="i-0a106c14603cb65a0",
        action="downsize",
        environment="production"
    )
    assert preflight["passed"] is True
    assert preflight["is_production"] is True
    assert preflight["requires_pr_approval"] is True
    assert "GitOps PR" in preflight["policy_applied"]


def test_preflight_safety_destructive_actions(clean_gitops_engine):
    """Verifies that destructive actions like terminate or delete require PR approval regardless of env."""
    preflight = clean_gitops_engine.evaluate_preflight_safety(
        resource_id="i-devtest",
        action="terminate",
        environment="development"
    )
    assert preflight["passed"] is True
    assert preflight["is_production"] is False
    assert preflight["requires_pr_approval"] is True


def test_gitops_ec2_remediation_pr_package(clean_gitops_engine):
    """Tests Terraform diff generation and branch naming for EC2 compute rightsizing."""
    pkg = clean_gitops_engine.create_remediation_pr(
        resource_id="i-0a106c14603cb65a0",
        action="graviton",
        from_type="t3.micro",
        to_type="t4g.micro",
        environment="production",
        repo_name="org/infra",
        monthly_savings=1.46
    )
    assert pkg["status"] == "pr_ready"
    assert "i-0a106c14603cb65a0" in pkg["branch_name"]
    assert pkg["file_path"] == "terraform/compute.tf"
    assert '-  instance_type = "t3.micro"' in pkg["diff"]
    assert '+  instance_type = "t4g.micro"' in pkg["diff"]
    assert "$1.46" in pkg["pr_body"]
    assert "https://github.com/org/infra/pull/" in pkg["pull_request_url"]
    assert len(clean_gitops_engine.audit_log) == 1


def test_gitops_ebs_volume_modernization_pr(clean_gitops_engine):
    """Tests storage modernization PR generation from gp2 to gp3."""
    pkg = clean_gitops_engine.create_remediation_pr(
        resource_id="vol-00d9bb20516b3992b",
        action="modernize",
        from_type="gp2",
        to_type="gp3",
        environment="production",
        monthly_savings=0.40
    )
    assert pkg["file_path"] == "terraform/storage.tf"
    assert '-  type = "gp2"' in pkg["diff"]
    assert '+  type = "gp3"' in pkg["diff"]
    assert "modernize vol-00d9bb20516b3992b storage" in pkg["title"]


def test_gitops_eip_release_pr(clean_gitops_engine):
    """Tests unattached Elastic IP remediation PR generation."""
    pkg = clean_gitops_engine.create_remediation_pr(
        resource_id="54.210.10.15",
        action="release",
        environment="production",
        monthly_savings=3.65
    )
    assert pkg["file_path"] == "terraform/networking.tf"
    assert "resource \"aws_eip\" \"eip_54_210_10_15\"" in pkg["diff"]
    assert "release unattached Elastic IP 54.210.10.15" in pkg["title"]


def test_gitops_audit_log_retrieval(clean_gitops_engine):
    """Tests audit trail retrieval and slicing."""
    for i in range(5):
        clean_gitops_engine.create_remediation_pr(
            resource_id=f"i-node-{i}",
            action="downsize",
            monthly_savings=2.50
        )
    trail = clean_gitops_engine.get_audit_trail(limit=3)
    assert len(trail) == 3
    assert trail[0]["resource_id"] if "resource_id" in trail[0] else "i-node-4" in trail[0]["title"]


def test_notification_slack_block_kit_formatting():
    """Verifies that Slack Block Kit contains headers, metric fields, and interactive action buttons."""
    card = notification_engine.format_slack_alert(
        resource_id="i-0a106c14603cb65a0",
        finding_title="Idle Compute Node Detected",
        severity="HIGH",
        current_monthly_spend=7.60,
        potential_monthly_savings=1.46,
        recommended_action="Migrate to Graviton t4g.micro"
    )
    assert "blocks" in card
    blocks = card["blocks"]
    header = blocks[0]
    assert header["type"] == "header"
    assert "HIGH" in header["text"]["text"]

    # Check action buttons
    actions = [b for b in blocks if b.get("type") == "actions"]
    assert len(actions) == 1
    elements = actions[0]["elements"]
    button_texts = [e["text"]["text"] for e in elements]
    assert any("Open Terraform PR" in b for b in button_texts)
    assert any("1-Click Remediate" in b for b in button_texts)
    assert any("Snooze" in b for b in button_texts)


def test_notification_teams_adaptive_card_formatting():
    """Verifies Microsoft Teams Adaptive Card schema and action elements."""
    card = notification_engine.format_teams_adaptive_card(
        resource_id="vol-00d9bb20516b3992b",
        finding_title="gp2 Legacy Volume Detected",
        severity="MEDIUM",
        current_monthly_spend=2.00,
        potential_monthly_savings=0.40,
        recommended_action="Modernize to gp3"
    )
    assert card["type"] == "message"
    attachments = card["attachments"]
    assert len(attachments) == 1
    content = attachments[0]["content"]
    assert content["$schema"] == "http://adaptivecards.io/schemas/adaptive-card.json"
    assert content["version"] == "1.4"
    assert "actions" in content
    actions = content["actions"]
    assert len(actions) >= 2


def test_api_gitops_pr_endpoint():
    """Verifies FastAPI POST /api/v2/gitops/pr endpoint."""
    client = TestClient(app)
    payload = {
        "resource_id": "i-0a106c14603cb65a0",
        "action": "graviton",
        "from_type": "t3.micro",
        "to_type": "t4g.micro",
        "environment": "production",
        "monthly_savings": 1.46
    }
    response = client.post("/api/v2/gitops/pr", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pr_ready"
    assert data["file_path"] == "terraform/compute.tf"
    assert data["estimated_monthly_savings"] == 1.46


def test_api_gitops_audit_log_endpoint():
    """Verifies FastAPI GET /api/v2/gitops/audit-log endpoint."""
    client = TestClient(app)
    response = client.get("/api/v2/gitops/audit-log?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "count" in data
    assert "audit_trail" in data
    assert isinstance(data["audit_trail"], list)


def test_api_notifications_slack():
    """Verifies FastAPI POST /api/v2/notifications/slack endpoint."""
    client = TestClient(app)
    payload = {
        "resource_id": "i-0a106c14603cb65a0",
        "finding_title": "Underutilized EC2 Instance",
        "severity": "HIGH",
        "current_monthly_spend": 7.60,
        "potential_monthly_savings": 1.46,
        "recommended_action": "Migrate to Graviton t4g.micro"
    }
    response = client.post("/api/v2/notifications/slack", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "blocks" in data["payload"]


def test_api_notifications_teams():
    """Verifies FastAPI POST /api/v2/notifications/teams endpoint."""
    client = TestClient(app)
    payload = {
        "resource_id": "vol-00d9bb20516b3992b",
        "finding_title": "Unattached EBS Volume",
        "severity": "CRITICAL",
        "current_monthly_spend": 5.00,
        "potential_monthly_savings": 5.00,
        "recommended_action": "Snapshot and terminate volume"
    }
    response = client.post("/api/v2/notifications/teams", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["payload"]["type"] == "message"


def test_cli_cmd_apply_dry_run(capsys):
    """Verifies CLI cmd_apply in dry-run mode."""
    args = argparse.Namespace(
        resource_id="i-0a106c14603cb65a0",
        action="graviton",
        from_type="t3.micro",
        to_type="t4g.micro",
        environment="production",
        repo="infrastructure/aws-workloads",
        savings=1.46,
        dry_run=True,
        slack=None,
        teams=None,
        format="table",
        json_only=False,
        output=None,
        url="http://localhost:8000"
    )
    cmd_apply(args)
    captured = capsys.readouterr().out
    assert "GITOPS REMEDIATION PRE-FLIGHT (DRY-RUN SIMULATION)" in captured
    assert "i-0a106c14603cb65a0" in captured
    assert "GRAVITON" in captured
    assert "terraform/compute.tf" in captured
    assert "DRY-RUN" in captured


def test_cli_cmd_apply_json(capsys):
    """Verifies CLI cmd_apply with --json output."""
    args = argparse.Namespace(
        resource_id="i-0a106c14603cb65a0",
        action="graviton",
        from_type="t3.micro",
        to_type="t4g.micro",
        environment="production",
        repo="infrastructure/aws-workloads",
        savings=1.46,
        dry_run=True,
        slack=None,
        teams=None,
        format="json",
        json_only=True,
        output=None,
        url="http://localhost:8000"
    )
    cmd_apply(args)
    captured = capsys.readouterr().out
    payload = json.loads(captured)
    assert payload["mode"] == "dry_run"
    assert payload["resource_id"] == "i-0a106c14603cb65a0"
    assert payload["status"] == "dry_run_simulation_passed"


def test_gitops_create_batch_remediation_pr(clean_gitops_engine):
    """Tests multi-resource batch remediation PR generation with dual-currency calculations."""
    sample_findings = [
        {"resource_id": "vol-12345", "action": "upgrade_gp3", "monthly_savings": 10.0, "title": "Upgrade gp2 to gp3"},
        {"resource_id": "i-abcdef", "action": "graviton", "monthly_savings": 15.0, "title": "Migrate to Graviton"},
        {"resource_id": "54.210.1.2", "action": "release_eip", "monthly_savings": 3.60, "title": "Release unattached EIP"}
    ]
    pkg = clean_gitops_engine.create_batch_remediation_pr(
        findings=sample_findings,
        environment="staging",
        repo_name="org/cloud-infra"
    )
    assert pkg["status"] == "pr_ready"
    assert pkg["findings_count"] == 3
    assert pkg["total_monthly_savings"] == 28.60
    assert pkg["total_annual_savings"] == round(28.60 * 12.0, 2)
    assert "storage.tf" in pkg["diff"]
    assert "compute.tf" in pkg["diff"]
    assert "networking.tf" in pkg["diff"]
    assert "batch-optimization" in pkg["branch_name"]
    assert "Batch Optimization Summary" in pkg["pr_body"]


def test_cli_cmd_apply_batch(capsys):
    """Verifies CLI cmd_apply --batch --dry-run output formatting."""
    args = argparse.Namespace(
        resource_id=None,
        batch=True,
        demo=True,
        action="downsize",
        from_type=None,
        to_type=None,
        environment="production",
        repo="infrastructure/aws-workloads",
        savings=0.0,
        dry_run=True,
        slack=None,
        teams=None,
        format="table",
        json_only=False,
        output=None,
        url="http://localhost:8000"
    )
    cmd_apply(args)
    captured = capsys.readouterr().out
    assert "GITOPS BATCH REMEDIATION AUTOPILOT" in captured
    assert "Consolidated Savings" in captured
    assert "Annual Fleet Recovery" in captured
    assert "storage.tf" in captured
    assert "compute.tf" in captured


def test_notification_slack_batch_summary_formatting():
    """Verifies that Slack batch digest generates valid Block Kit with dual currency and interactive buttons."""
    findings = [
        {"resource_id": "vol-12345", "category": "Storage", "action": "delete_volume", "monthly_savings": 10.0},
        {"resource_id": "i-67890", "category": "Compute", "action": "migrate_graviton", "monthly_savings": 25.0}
    ]
    card = notification_engine.format_slack_batch_summary(
        findings=findings,
        total_monthly_spend=100.0,
        total_monthly_savings=35.0,
        health_score=82.5,
        account_id="123456789012",
        currency="USD",
        rate=84.0
    )
    assert "blocks" in card
    blocks = card["blocks"]
    header = blocks[0]
    assert header["type"] == "header"
    assert "Fleet Optimization Digest" in header["text"]["text"]

    fields_sec = blocks[1]
    assert fields_sec["type"] == "section"
    assert any("82.5/100" in f["text"] for f in fields_sec["fields"])
    assert any("$100.00" in f["text"] for f in fields_sec["fields"])

    actions = [b for b in blocks if b.get("type") == "actions"]
    assert len(actions) == 1
    elements = actions[0]["elements"]
    action_ids = [e.get("action_id") for e in elements]
    assert "cloudpulse_batch_pr" in action_ids
    assert "cloudpulse_view_pov" in action_ids
    assert "cloudpulse_snooze" in action_ids


def test_notification_teams_batch_adaptive_card_formatting():
    """Verifies that Teams batch digest formats valid Adaptive Card v1.4 schema."""
    findings = [
        {"resource_id": "vol-12345", "category": "Storage", "action": "delete_volume", "monthly_savings": 10.0},
        {"resource_id": "i-67890", "category": "Compute", "action": "migrate_graviton", "monthly_savings": 25.0}
    ]
    card = notification_engine.format_teams_batch_adaptive_card(
        findings=findings,
        total_monthly_spend=100.0,
        total_monthly_savings=35.0,
        health_score=82.5,
        account_id="123456789012",
        currency="INR",
        rate=84.0
    )
    assert card["type"] == "message"
    attachments = card["attachments"]
    assert len(attachments) == 1
    content = attachments[0]["content"]
    assert content["$schema"] == "http://adaptivecards.io/schemas/adaptive-card.json"
    assert content["version"] == "1.4"
    assert "actions" in content
    actions = content["actions"]
    assert any(a.get("type") == "Action.Submit" and a.get("data", {}).get("action") == "batch_pr" for a in actions)
    assert any(a.get("type") == "Action.OpenUrl" for a in actions)


def test_notification_interactive_callbacks():
    """Verifies that interactive callbacks trigger appropriate automated actions."""
    # Test batch_pr action
    res_pr = notification_engine.handle_interactive_callback({"action": "batch_pr", "repo": "org/repo"})
    assert res_pr["status"] == "success"
    assert "Batch Remediation PR created" in res_pr["message"]
    assert "https://github.com/org/repo/pull/" in res_pr["pr_url"]

    # Test apply/remediate action
    res_apply = notification_engine.handle_interactive_callback({"action": "apply", "resource_id": "i-test123"})
    assert res_apply["status"] == "success"
    assert res_apply["scheduled"] is True

    # Test snooze action
    res_snooze = notification_engine.handle_interactive_callback({"action": "snooze"})
    assert res_snooze["status"] == "success"
    assert res_snooze["snoozed_days"] == 14

    # Test unknown action
    res_unk = notification_engine.handle_interactive_callback({"action": "unknown_action"})
    assert res_unk["status"] == "ignored"


def test_notification_slack_api_dispatch(monkeypatch):
    """Verifies direct Slack Web API dispatch with bot token."""
    from unittest.mock import MagicMock
    import urllib.request

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({"ok": True}).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=5.0: mock_resp)

    card = {"text": "Test alert", "blocks": []}
    success = notification_engine.dispatch_slack_api("xoxb-test-token", "#finops-alerts", card)
    assert success is True

    # Test empty token
    assert notification_engine.dispatch_slack_api("", "#general", card) is False



def test_api_notifications_slack_batch():
    """Verifies FastAPI POST /api/v2/notifications/slack/batch endpoint."""
    client = TestClient(app)
    payload = {
        "currency": "USD",
        "rate": 84.0,
        "repo_name": "custom/repo",
        "findings": [
            {"resource_id": "vol-abc", "category": "Storage", "action": "delete_volume", "monthly_savings": 5.0}
        ]
    }
    response = client.post("/api/v2/notifications/slack/batch", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "blocks" in data["payload"]
    assert "cloudpulse_batch_pr" in json.dumps(data["payload"])


def test_api_notifications_teams_batch():
    """Verifies FastAPI POST /api/v2/notifications/teams/batch endpoint."""
    client = TestClient(app)
    payload = {
        "currency": "INR",
        "rate": 84.0,
        "findings": [
            {"resource_id": "i-xyz", "category": "Compute", "action": "migrate_graviton", "monthly_savings": 15.0}
        ]
    }
    response = client.post("/api/v2/notifications/teams/batch", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["payload"]["type"] == "message"
    assert "attachments" in data["payload"]


def test_api_notifications_interactive_callback():
    """Verifies FastAPI POST /api/v2/notifications/interactive/callback endpoint."""
    client = TestClient(app)
    payload = {"action": "batch_pr", "repo": "fleet/infra"}
    response = client.post("/api/v2/notifications/interactive/callback", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "https://github.com/fleet/infra/pull/" in data["pr_url"]


def test_cli_cmd_notify_slack_batch_dry_run(capsys):
    """Verifies CLI cmd_notify with --channel slack --batch --dry-run."""
    args = argparse.Namespace(
        channel="slack",
        batch=True,
        dry_run=True,
        currency="USD",
        webhook=None,
        to=None,
        title="Fleet Alert",
        message="Monthly optimization",
        url="http://localhost:8000"
    )
    cmd_notify(args)
    captured = capsys.readouterr().out
    assert "CLOUDPULSE MULTI-CHANNEL NOTIFICATION DISPATCHER" in captured
    assert "Target Channel   : SLACK" in captured
    assert "FLEET BATCH DIGEST" in captured
    assert "cloudpulse_batch_pr" in captured


def test_cli_cmd_notify_teams_batch_dry_run(capsys):
    """Verifies CLI cmd_notify with --channel teams --batch --dry-run."""
    args = argparse.Namespace(
        channel="teams",
        batch=True,
        dry_run=True,
        currency="INR",
        webhook=None,
        to=None,
        title="Fleet Alert",
        message="Monthly optimization",
        url="http://localhost:8000"
    )
    cmd_notify(args)
    captured = capsys.readouterr().out
    assert "CLOUDPULSE MULTI-CHANNEL NOTIFICATION DISPATCHER" in captured
    assert "Target Channel   : TEAMS" in captured
    assert "FLEET BATCH DIGEST" in captured
    assert "AdaptiveCard" in captured


