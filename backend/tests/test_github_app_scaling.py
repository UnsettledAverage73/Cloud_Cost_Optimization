"""
Unit & Integration Tests for CloudPulse Native GitHub App & CI/CD Guardrail Engine (Milestone 3 - Priority 2).
Verifies HMAC signature verification, diff cost analysis (reductions vs spikes),
PR markdown comments, GitHub check-runs, FastAPI endpoints, and CLI gh command.
"""

import hmac
import hashlib
import json
import argparse
import pytest
from fastapi.testclient import TestClient

from services.github_app_engine import GitHubAppEngine, github_app_engine
from cli_main import cmd_gh
from main import app


@pytest.fixture
def custom_gh_engine():
    return GitHubAppEngine(spike_threshold_usd=50.0, webhook_secret="test-secret-key-123")


def test_github_signature_verification(custom_gh_engine):
    """Verifies HMAC SHA-256 webhook signature validation."""
    payload = b'{"action": "opened", "pull_request": {"number": 10}}'
    secret = "test-secret-key-123"

    # Valid signature
    valid_sig = "sha256=" + hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    assert custom_gh_engine.verify_signature(payload, valid_sig) is True

    # Invalid / Tampered signature
    invalid_sig = "sha256=" + hmac.new(b"wrong-secret", payload, hashlib.sha256).hexdigest()
    assert custom_gh_engine.verify_signature(payload, invalid_sig) is False

    # Missing signature header
    assert custom_gh_engine.verify_signature(payload, None) is False

    # Unauthenticated / Dev mode engine without secret
    open_engine = GitHubAppEngine(webhook_secret=None)
    assert open_engine.verify_signature(payload, None) is True


def test_diff_cost_analysis_reduction(custom_gh_engine):
    """Verifies that downsizing compute and modernizing storage correctly computes cost reductions."""
    diff_text = """
--- a/terraform/compute.tf
+++ b/terraform/compute.tf
@@ -10,3 +10,3 @@
 resource "aws_instance" "worker" {
-  instance_type = "t3.xlarge"
+  instance_type = "t4g.medium"
 }
"""
    analysis = custom_gh_engine.analyze_diff(diff_text)

    assert analysis["impact_type"] == "COST_REDUCTION"
    assert analysis["monthly_diff"] < 0
    assert analysis["baseline_monthly_spend"] == 121.60
    assert analysis["projected_monthly_spend"] == 24.32
    assert analysis["monthly_diff"] == -97.28
    assert analysis["annual_diff"] == round(-97.28 * 12.0, 2)
    assert analysis["is_cost_spike"] is False
    assert len(analysis["changes"]) == 1


def test_diff_cost_analysis_spike(custom_gh_engine):
    """Verifies detection of unintended cost spikes and guardrail violations."""
    diff_text = """
--- a/terraform/compute.tf
+++ b/terraform/compute.tf
@@ -10,3 +10,3 @@
 resource "aws_instance" "worker" {
-  instance_type = "t3.micro"
+  instance_type = "m5.24xlarge"
 }
"""
    analysis = custom_gh_engine.analyze_diff(diff_text)

    assert analysis["impact_type"] == "COST_INCREASE"
    assert analysis["monthly_diff"] > 50.0
    assert analysis["is_cost_spike"] is True
    assert analysis["projected_monthly_spend"] > 3000.0


def test_pr_comment_formatting_markdown(custom_gh_engine):
    """Verifies generation of GitHub Flavored Markdown PR comment with dual currency."""
    analysis = {
        "impact_type": "COST_REDUCTION",
        "baseline_monthly_spend": 100.0,
        "projected_monthly_spend": 20.0,
        "monthly_diff": -80.0,
        "annual_diff": -960.0,
        "is_cost_spike": False,
        "changes": [
            {"resource": "EC2 Instance", "action": "Downsize t3.xlarge to t4g.medium", "delta": -80.0}
        ]
    }
    comment = custom_gh_engine.format_pr_comment(analysis, currency="INR", rate=84.0, pr_number=42)

    assert "CloudPulse FinOps CI/CD Guardrail (PR #42)" in comment
    assert "Cost Reduction:" in comment
    assert "₹6,720.00 ($80.00)/mo" in comment
    assert "Passed FinOps Guardrails" in comment
    assert "EC2 Instance" in comment


def test_check_run_generation(custom_gh_engine):
    """Verifies GitHub Check Run status schema for success and action_required conclusions."""
    # 1. Success check run
    analysis_success = {
        "monthly_diff": -25.0,
        "annual_diff": -300.0,
        "baseline_monthly_spend": 50.0,
        "projected_monthly_spend": 25.0,
        "is_cost_spike": False,
        "changes": []
    }
    check_success = custom_gh_engine.format_check_run(analysis_success, head_sha="commit-123", currency="USD")
    assert check_success["name"] == "cloudpulse/finops-guardrail"
    assert check_success["head_sha"] == "commit-123"
    assert check_success["conclusion"] == "success"
    assert "Cost Reduction:" in check_success["output"]["title"]

    # 2. Action required check run (Cost Spike)
    analysis_spike = {
        "monthly_diff": 250.0,
        "annual_diff": 3000.0,
        "baseline_monthly_spend": 50.0,
        "projected_monthly_spend": 300.0,
        "is_cost_spike": True,
        "changes": []
    }
    check_spike = custom_gh_engine.format_check_run(analysis_spike, head_sha="commit-456", currency="USD")
    assert check_spike["conclusion"] == "action_required"
    assert "Cost Spike:" in check_spike["output"]["title"]


def test_fastapi_github_endpoints():
    """Verifies FastAPI endpoints for analyze-pr, webhook, and status."""
    client = TestClient(app)

    # 1. Analyze PR Diff Endpoint
    payload = {
        "diff": """
--- a/terraform/storage.tf
+++ b/terraform/storage.tf
@@ -1,3 +1,3 @@
 resource "aws_ebs_volume" "data" {
-  type = "gp2"
+  type = "gp3"
 }
""",
        "currency": "USD",
        "pull_number": 88
    }
    resp = client.post("/api/v2/github/analyze-pr", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert "comment_markdown" in data
    assert data["check_run"]["conclusion"] == "success"

    # 2. Webhook Listener Endpoint
    webhook_payload = {
        "action": "opened",
        "repository": {"full_name": "org/infrastructure"},
        "pull_request": {
            "number": 15,
            "head": {"sha": "abc999"},
            "body": "- instance_type = \"t3.xlarge\"\n+ instance_type = \"t4g.medium\""
        }
    }
    resp_wh = client.post("/api/v2/github/webhook", json=webhook_payload)
    assert resp_wh.status_code == 200
    data_wh = resp_wh.json()
    assert data_wh["status"] == "success"
    assert data_wh["pull_number"] == 15
    assert data_wh["repository"] == "org/infrastructure"

    # 3. Status Endpoint
    resp_status = client.get("/api/v2/github/status")
    assert resp_status.status_code == 200
    assert resp_status.json()["status"] == "active"
    assert resp_status.json()["spike_threshold_usd"] > 0


def test_cli_cmd_gh_default_reduction(capsys):
    """Verifies CLI cmd_gh execution for cost reduction diff."""
    args = argparse.Namespace(
        diff=None,
        pr=77,
        threshold=50.0,
        currency="USD",
        format="table",
        json_only=False,
        output=None,
        url="http://localhost:8000"
    )
    cmd_gh(args)
    captured = capsys.readouterr().out
    assert "CLOUDPULSE CI/CD FINOPS GUARDRAIL & GITHUB APP AUDIT" in captured
    assert "🟢 PASSED (COST REDUCTION VERIFIED)" in captured
    assert "GitHub Check Run" in captured
    assert "SUCCESS" in captured


def test_cli_cmd_gh_cost_spike(capsys):
    """Verifies CLI cmd_gh execution when a cost spike is detected."""
    diff_spike = '+  instance_type = "m5.24xlarge"'
    args = argparse.Namespace(
        diff=diff_spike,
        pr=99,
        threshold=50.0,
        currency="INR",
        format="table",
        json_only=False,
        output=None,
        url="http://localhost:8000"
    )
    cmd_gh(args)
    captured = capsys.readouterr().out
    assert "🚨 ACTION REQUIRED (COST SPIKE DETECTED)" in captured
    assert "GitHub Check Run" in captured
    assert "ACTION_REQUIRED" in captured


def test_cli_cmd_gh_json_format(capsys):
    """Verifies CLI cmd_gh with --json output format."""
    args = argparse.Namespace(
        diff=None,
        pr=10,
        threshold=50.0,
        currency="USD",
        format="json",
        json_only=True,
        output=None,
        url="http://localhost:8000"
    )
    cmd_gh(args)
    captured = capsys.readouterr().out
    payload = json.loads(captured)
    assert "analysis" in payload
    assert "check_run" in payload
    assert "comment_markdown" in payload
