"""
Unit & Integration Tests for CloudPulse Multi-Cloud Fleet (Azure / GCP), RBAC Security & Container HA (Phase 5).
Verifies Azure/GCP FOCUS 1.0 mapping, multi-cloud spend consolidation, RBAC role authorization,
FastAPI REST endpoints, and CLI multicloud command.
"""

import json
import pytest
import argparse
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from collectors.multicloud_connector import (
    AzureCostConnector, GCPCostConnector, MultiCloudOrchestrator, multicloud_orchestrator
)
from services.rbac_middleware import (
    FinOpsRole, FinOpsPermission, RBACSecurityManager, rbac_manager
)
from cli_main import cmd_multicloud
from main import app


def test_azure_cost_connector_focus_normalization():
    """Verifies that Azure Cost Management records conform to FOCUS 1.0 schema."""
    raw_azure = {
        "resourceId": "/subscriptions/sub-9999/resourceGroups/rg-core/providers/Microsoft.Compute/virtualMachines/vm-prod-01",
        "resourceName": "vm-prod-01",
        "consumedService": "Microsoft.Compute",
        "cost": 42.50,
        "region": "westeurope",
        "subscriptionId": "sub-9999",
        "subscriptionName": "Azure Europe Prod",
        "pricingModel": "On-Demand"
    }
    record = AzureCostConnector.normalize_azure_record(raw_azure)
    assert record["ProviderName"] == "Azure"
    assert record["ServiceCategory"] == "Compute"
    assert record["EffectiveCost"] == 42.50
    assert record["Currency"] == "USD"
    assert record["RegionId"] == "westeurope"
    assert record["ChargeCategory"] == "Usage"


def test_gcp_cost_connector_focus_normalization():
    """Verifies that GCP BigQuery billing records conform to FOCUS 1.0 schema."""
    raw_gcp = {
        "project": {"id": "prj-analytics", "name": "BigQuery Analytics"},
        "service": {"description": "Compute Engine"},
        "sku": {"description": "e2-medium instance"},
        "cost": 25.10,
        "location": {"region": "us-central1"},
        "currency": "USD"
    }
    record = GCPCostConnector.normalize_gcp_record(raw_gcp)
    assert record["ProviderName"] == "GCP"
    assert record["ServiceCategory"] == "Compute"
    assert record["EffectiveCost"] == 25.10
    assert record["RegionId"] == "us-central1"
    assert record["SubAccountId"] == "prj-analytics"


def test_multicloud_orchestrator_spend_aggregation():
    """Verifies cross-cloud consolidation across AWS, Azure, and GCP."""
    orchestrator = MultiCloudOrchestrator()
    # Unconnected state: Azure & GCP report $0 and NOT CONNECTED
    summary = orchestrator.get_cross_cloud_summary(aws_spend=74.16, aws_focus_count=18)

    assert "total_multicloud_monthly_spend" in summary
    assert summary["total_multicloud_monthly_spend"] == 74.16
    assert summary["providers"]["AWS"]["status"] == "ACTIVE SYNC"
    assert summary["providers"]["Azure"]["status"] == "NOT CONNECTED"
    assert summary["providers"]["GCP"]["status"] == "NOT CONNECTED"

    # Explicit batch ingestion of Azure & GCP records
    orchestrator.ingest_azure_batch([{"cost": 50.0, "consumedService": "Microsoft.Compute", "resourceId": "azure-vm-1"}])
    orchestrator.ingest_gcp_batch([{"cost": 30.0, "service": {"description": "Compute Engine"}, "resource": {"name": "gcp-vm-1"}}])

    updated = orchestrator.get_cross_cloud_summary(aws_spend=74.16, aws_focus_count=18)
    assert updated["total_multicloud_monthly_spend"] == 154.16
    assert updated["providers"]["Azure"]["status"] == "ACTIVE SYNC"
    assert updated["providers"]["GCP"]["status"] == "ACTIVE SYNC"

    total_shares = (
        updated["providers"]["AWS"]["share_percent"] +
        updated["providers"]["Azure"]["share_percent"] +
        updated["providers"]["GCP"]["share_percent"]
    )
    assert 99.0 <= total_shares <= 101.0  # Accounts for minor rounding


def test_rbac_manager_admin_permissions():
    """Verifies that FINOPS_ADMIN has all enterprise capabilities."""
    assert rbac_manager.check_permission("FINOPS_ADMIN", "gitops:apply") is True
    assert rbac_manager.check_permission("FINOPS_ADMIN", "manage:accounts") is True
    assert rbac_manager.check_permission("FINOPS_ADMIN", "trigger:scan") is True
    assert rbac_manager.check_permission("FINOPS_ADMIN", "read:dashboards") is True


def test_rbac_manager_analyst_and_viewer_restrictions():
    """Verifies that non-admin roles cannot execute destructive or mutation actions."""
    # Analyst cannot apply gitops PR or manage accounts
    assert rbac_manager.check_permission("FINOPS_ANALYST", "gitops:apply") is False
    assert rbac_manager.check_permission("FINOPS_ANALYST", "manage:accounts") is False
    assert rbac_manager.check_permission("FINOPS_ANALYST", "query:copilot") is True

    # Viewer can only read
    assert rbac_manager.check_permission("VIEWER", "gitops:apply") is False
    assert rbac_manager.check_permission("VIEWER", "trigger:scan") is False
    assert rbac_manager.check_permission("VIEWER", "read:dashboards") is True


def test_rbac_manager_api_key_authentication():
    """Verifies API key authentication and role resolution."""
    admin_auth = rbac_manager.authenticate_key("cp-admin-key-999")
    assert admin_auth["authenticated"] is True
    assert admin_auth["role"] == "FINOPS_ADMIN"

    analyst_auth = rbac_manager.authenticate_key("cp-analyst-key-123")
    assert analyst_auth["authenticated"] is True
    assert analyst_auth["role"] == "FINOPS_ANALYST"

    invalid_auth = rbac_manager.authenticate_key("invalid-token-xyz")
    assert invalid_auth["authenticated"] is False


def test_api_multicloud_summary_endpoint():
    """Verifies FastAPI GET /api/v2/multicloud/summary endpoint."""
    client = TestClient(app)
    response = client.get("/api/v2/multicloud/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_multicloud_monthly_spend" in data
    assert "providers" in data
    assert "AWS" in data["providers"]
    assert "Azure" in data["providers"]
    assert "GCP" in data["providers"]


def test_api_multicloud_ingest_endpoint():
    """Verifies FastAPI POST /api/v2/multicloud/ingest endpoint."""
    client = TestClient(app)
    payload = {
        "provider": "azure",
        "records": [
            {
                "resourceId": "/subscriptions/sub-test/virtualMachines/test-vm",
                "consumedService": "Microsoft.Compute",
                "cost": 15.00
            }
        ]
    }
    response = client.post("/api/v2/multicloud/ingest", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ingested"
    assert data["provider"] == "AZURE"
    assert data["records_ingested"] == 1


def test_api_auth_verify_role_endpoint():
    """Verifies FastAPI GET /api/v2/auth/verify-role endpoint."""
    client = TestClient(app)

    # Valid key with permitted action
    res_valid = client.get("/api/v2/auth/verify-role?api_key=cp-admin-key-999&permission=gitops:apply")
    assert res_valid.status_code == 200
    data_valid = res_valid.json()
    assert data_valid["authorized"] is True

    # Valid key with unpermitted action
    res_restricted = client.get("/api/v2/auth/verify-role?api_key=cp-analyst-key-123&permission=gitops:apply")
    assert res_restricted.status_code == 200
    data_restricted = res_restricted.json()
    assert data_restricted["authorized"] is False

    # Invalid key
    res_invalid = client.get("/api/v2/auth/verify-role?api_key=bad-key")
    assert res_invalid.status_code == 401


def test_cli_cmd_multicloud_table_and_json(capsys):
    """Verifies CLI cmd_multicloud in table and JSON modes."""
    args_table = argparse.Namespace(
        format="table",
        json_only=False,
        output=None,
        url="http://localhost:8000"
    )
    cmd_multicloud(args_table)
    captured = capsys.readouterr().out
    assert "CLOUDPULSE MULTI-CLOUD FLEET" in captured
    assert "AWS" in captured
    assert "Azure" in captured
    assert "GCP" in captured

    args_json = argparse.Namespace(
        format="json",
        json_only=True,
        output=None,
        url="http://localhost:8000"
    )
    cmd_multicloud(args_json)
    captured_json = capsys.readouterr().out
    data = json.loads(captured_json)
    assert "total_multicloud_monthly_spend" in data
    assert "providers" in data
