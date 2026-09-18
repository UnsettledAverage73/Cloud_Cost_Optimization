import sys
import os
import pytest
from fastapi.testclient import TestClient

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from main import app
    from database.connection import ping_database, SyncSessionLocal
    from database.models import Organization, ConnectedAWSAccount, DailySpendRecord, ResourceTelemetry
    from onboarding.cloudformation import get_onboarding_package, generate_cloudformation_yaml
    from onboarding.tenant_manager import TenantManager
    from copilot.tools.sql_analytics_tool import execute_readonly_sql
    from copilot.tools.pricing_rag_tool import lookup_aws_pricing
    from copilot.tools.cloudtrail_forensics_tool import investigate_event_spikes
    from copilot.tools.terraform_pr_tool import generate_terraform_remediation_pr
    from copilot.agent import FinOpsAutonomousCopilot
except ImportError:
    from backend.main import app
    from backend.database.connection import ping_database, SyncSessionLocal
    from backend.database.models import Organization, ConnectedAWSAccount, DailySpendRecord, ResourceTelemetry
    from backend.onboarding.cloudformation import get_onboarding_package, generate_cloudformation_yaml
    from backend.onboarding.tenant_manager import TenantManager
    from backend.copilot.tools.sql_analytics_tool import execute_readonly_sql
    from backend.copilot.tools.pricing_rag_tool import lookup_aws_pricing
    from backend.copilot.tools.cloudtrail_forensics_tool import investigate_event_spikes
    from backend.copilot.tools.terraform_pr_tool import generate_terraform_remediation_pr
    from backend.copilot.agent import FinOpsAutonomousCopilot

client = TestClient(app)

def test_timescaledb_ping():
    """Verify live connection to PostgreSQL and TimescaleDB extension."""
    status = ping_database()
    assert status["status"] == "connected"
    assert "timescaledb_version" in status
    assert status["timescaledb_version"] != "not installed"

def test_timescaledb_hypertables_query():
    """Test querying TimescaleDB hypertable models."""
    session = SyncSessionLocal()
    try:
        spend_count = session.query(DailySpendRecord).count()
        telemetry_count = session.query(ResourceTelemetry).count()
        assert spend_count > 0, "Expected seeded spend records in hypertable"
        assert telemetry_count > 0, "Expected seeded telemetry records in hypertable"
    finally:
        session.close()

def test_cloudformation_package_generation():
    """Verify 1-click CloudFormation template generation with ExternalId."""
    package = get_onboarding_package(org_id="test-org-123")
    assert "external_id" in package
    assert package["external_id"].startswith("cp-")
    assert "quick_create_url" in package
    assert "console.aws.amazon.com/cloudformation" in package["quick_create_url"]
    assert "template_yaml" in package
    assert "CloudPulseFinOpsRole" in package["template_yaml"]
    assert "sts:ExternalId" in package["template_yaml"]

def test_tenant_account_registration():
    """Test registering an AWS account under an organization."""
    session = SyncSessionLocal()
    try:
        manager = TenantManager(session)
        org = session.query(Organization).first()
        assert org is not None

        new_acc = manager.register_aws_account(
            organization_id=str(org.id),
            account_id="998877665544",
            account_name="Staging VPC Account",
            role_arn="arn:aws:iam::998877665544:role/CloudPulseStagingRole",
            external_id="cp-test-staging-external-id",
            regions=["us-east-1", "eu-central-1"],
            validate_immediately=False
        )
        assert new_acc["account_id"] == "998877665544"
        assert new_acc["status"] == "pending"
    finally:
        session.close()

def test_readonly_sql_tool_safety():
    """Test that mutating queries are blocked and SELECT queries succeed."""
    # Forbidden mutating statements
    drop_res = execute_readonly_sql("DROP TABLE organizations;")
    assert drop_res["success"] is False
    assert "Security violation" in drop_res["error"]

    delete_res = execute_readonly_sql("DELETE FROM cloud_resources WHERE id='123';")
    assert delete_res["success"] is False
    assert "Security violation" in delete_res["error"]

    # Valid SELECT query
    valid_res = execute_readonly_sql("SELECT service_name, billed_cost FROM daily_spend_records LIMIT 5;")
    assert valid_res["success"] is True
    assert valid_res["row_count"] <= 5
    assert len(valid_res["columns"]) == 2

def test_pricing_rag_graviton_calculation():
    """Test pricing RAG tool returns accurate rates and Graviton ROI."""
    res = lookup_aws_pricing("m5.2xlarge")
    assert res["found"] is True
    assert res["architecture"] == "x86_64"
    assert "graviton_recommendation" in res
    assert res["graviton_recommendation"] is not None
    graviton = res["graviton_recommendation"]
    assert graviton["instance_type"] == "m6g.2xlarge" or "m6g" in graviton["instance_type"]
    assert graviton["monthly_savings"] > 0

def test_cloudtrail_forensics_tool():
    """Test forensic investigation of cost spike root cause."""
    forensics = investigate_event_spikes(service="AmazonEC2")
    assert forensics["service_investigated"] == "AmazonEC2"
    assert forensics["matched_events_count"] > 0
    suspect = forensics["primary_suspect"]
    assert suspect is not None
    assert "event_name" in suspect
    assert "username" in suspect

def test_terraform_pr_generator():
    """Test automated Terraform / OpenTofu PR generation."""
    pr = generate_terraform_remediation_pr(
        finding_id="find-idle-m5",
        resource_id="i-09f81a2b3c4d5e6f7",
        action_type="downsize_ec2",
        current_config={"instance_type": "m5.2xlarge", "name": "ml_worker"},
        recommended_config={"instance_type": "t4g.medium"},
        monthly_savings=243.80
    )
    assert pr["status"] == "ready_to_open"
    assert "finops/optimize" in pr["branch_name"]
    assert "243.80" in pr["commit_title"]
    assert "t4g.medium" in pr["hcl_after"]
    assert "--- a/terraform/compute.tf" in pr["unified_diff"]

def test_copilot_chat_autonomous_routing():
    """Test autonomous Copilot handles spend breakdown and pricing inquiries."""
    copilot = FinOpsAutonomousCopilot()

    # Spend breakdown prompt
    chat1 = copilot.chat("What is our spend breakdown by service?")
    assert chat1["tool_called"] == "sql_analytics"
    assert "AmazonEC2" in chat1["answer"]

    # Pricing prompt
    chat2 = copilot.chat("Compare m5.2xlarge with Graviton pricing")
    assert chat2["tool_called"] == "pricing_rag"
    assert "Graviton" in chat2["answer"]

    # Forensics prompt
    chat3 = copilot.chat("Why did we have a spike in cloud spend?")
    assert chat3["tool_called"] == "cloudtrail_forensics"
    assert "Root-Cause" in chat3["answer"]

def test_v2_api_endpoints():
    """Test live v2 FastAPI endpoints via TestClient."""
    # 1. Database status
    r = client.get("/api/v2/database/status")
    assert r.status_code == 200
    assert r.json()["status"] == "connected"

    # 2. CloudFormation Onboarding
    r = client.get("/api/v2/onboarding/cloudformation")
    assert r.status_code == 200
    assert "quick_create_url" in r.json()

    # 3. List Accounts
    r = client.get("/api/v2/onboarding/accounts")
    assert r.status_code == 200
    assert "accounts" in r.json()

    # 4. TimescaleDB Telemetry Hypertable
    r = client.get("/api/v2/telemetry/hypertable?limit=10")
    assert r.status_code == 200
    assert r.json()["count"] > 0

    # 5. FOCUS 1.0 Spend Records
    r = client.get("/api/v2/focus/spend?limit=10")
    assert r.status_code == 200
    assert r.json()["specification"] == "FOCUS 1.0"
    assert len(r.json()["records"]) > 0

    # 6. Copilot Chat Endpoint
    r = client.post("/api/v2/copilot/chat", json={"message": "Show spend by service"})
    assert r.status_code == 200
    assert "answer" in r.json()

    # 7. Copilot Diagnose Spike Endpoint
    r = client.post("/api/v2/copilot/diagnose-spike", json={"service": "AmazonEC2"})
    assert r.status_code == 200
    assert "forensics" in r.json()
    assert "remediation_pr" in r.json()

    # 8. Copilot Generate IaC PR Endpoint
    r = client.post("/api/v2/copilot/generate-iac-pr", json={
        "finding_id": "test-finding",
        "resource_id": "i-09f81a2b3c4d5e6f7",
        "monthly_savings": 243.80
    })
    assert r.status_code == 200
    assert "unified_diff" in r.json()

    # 9. Copilot Pricing Catalog Endpoint
    r = client.get("/api/v2/copilot/pricing?resource_type=m5.2xlarge")
    assert r.status_code == 200
    assert r.json()["found"] is True
