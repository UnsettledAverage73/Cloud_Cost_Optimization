import pytest
import time
import json
import argparse
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from engines.focus_spec import FOCUSNormalizer
from collectors.fleet_cache import FleetStateCache, fleet_cache
from collectors.fleet_manager import FleetManager, FleetAccountConfig, fleet_manager
from cli_main import cmd_fleet
from main import app


@pytest.fixture
def sample_fleet_inventory():
    return {
        "metadata": {
            "account_id": "111122223333",
            "account_name": "Production-Cluster",
            "region": "us-east-1"
        },
        "compute": {
            "nodes": [
                {
                    "instance_id": "i-worker01",
                    "name": "app-server-01",
                    "instance_type": "t3.medium",
                    "availability_zone": "us-east-1a",
                    "cost": 30.40,
                    "tags": {"Environment": "Production"}
                }
            ]
        },
        "ec2_other_resources": {
            "ebs_volumes": [
                {
                    "volume_id": "vol-app01",
                    "volume_type": "gp3",
                    "size_gb": 100,
                    "cost": 8.00
                }
            ],
            "elastic_ips": [
                {
                    "public_ip": "52.20.10.5",
                    "allocation_id": "eipalloc-123"
                }
            ]
        },
        "summary": {
            "estimated_monthly_spend": 42.05
        }
    }


def test_focus_normalizer_resource_cost():
    rec = FOCUSNormalizer.normalize_resource_cost(
        resource_id="i-test123",
        resource_name="test-instance",
        service_name="Amazon Elastic Compute Cloud - Compute",
        region_id="us-east-1",
        account_id="123456789012",
        account_name="TestAccount",
        billed_cost=15.50,
        pricing_category="On-Demand"
    )

    assert rec["ResourceId"] == "i-test123"
    assert rec["ProviderName"] == "AWS"
    assert rec["BillingAccountId"] == "123456789012"
    assert rec["BilledCost"] == 15.50
    assert rec["EffectiveCost"] == 15.50
    assert rec["Currency"] == "USD"
    assert rec["ServiceCategory"] == "Compute"
    assert rec["PricingCategory"] == "On-Demand"
    assert "ChargeId" in rec
    assert rec["UsageQuantity"] == 730.0


def test_focus_normalizer_service_categories():
    assert FOCUSNormalizer._map_service_category("Amazon Elastic Compute Cloud - Compute") == "Compute"
    assert FOCUSNormalizer._map_service_category("Amazon Elastic Block Store") == "Storage"
    assert FOCUSNormalizer._map_service_category("Amazon Simple Storage Service") == "Storage"
    assert FOCUSNormalizer._map_service_category("Amazon Relational Database Service") == "Database"
    assert FOCUSNormalizer._map_service_category("Amazon Virtual Private Cloud") == "Networking"
    assert FOCUSNormalizer._map_service_category("Custom Unknown Cloud Service") == "Other"


def test_focus_normalizer_inventory(sample_fleet_inventory):
    records = FOCUSNormalizer.normalize_inventory(sample_fleet_inventory)
    assert len(records) == 3

    node_rec = next(r for r in records if r["ResourceId"] == "i-worker01")
    assert node_rec["BillingAccountId"] == "111122223333"
    assert node_rec["ServiceCategory"] == "Compute"
    assert node_rec["BilledCost"] == 30.40

    vol_rec = next(r for r in records if r["ResourceId"] == "vol-app01")
    assert vol_rec["ServiceCategory"] == "Storage"
    assert vol_rec["BilledCost"] == 8.00

    eip_rec = next(r for r in records if r["ResourceId"] == "52.20.10.5")
    assert eip_rec["ServiceCategory"] == "Networking"
    assert eip_rec["BilledCost"] == 3.60


def test_fleet_state_cache(tmp_path):
    cache = FleetStateCache(default_ttl_seconds=2)
    cache.set("test_key", {"status": "ok"}, ttl_seconds=1)

    assert cache.get("test_key") == {"status": "ok"}
    assert not cache.is_stale("test_key")

    # Let it expire
    time.sleep(1.1)
    assert cache.is_stale("test_key")
    # stale-while-revalidate still returns last known data
    assert cache.get("test_key") == {"status": "ok"}

    # Async refresh test
    def dummy_refresh():
        return {"status": "refreshed"}

    cache.trigger_async_refresh("test_key", dummy_refresh)
    time.sleep(0.3)
    assert cache.get("test_key") == {"status": "refreshed"}


def test_fleet_account_config():
    cfg_role = FleetAccountConfig(
        account_id="111111111111",
        account_name="App-Prod",
        role_arn="arn:aws:iam::111111111111:role/FinOps",
        external_id="secret123",
        region="us-west-2"
    )
    d_role = cfg_role.to_dict()
    assert d_role["account_id"] == "111111111111"
    assert d_role["auth_type"] == "assume_role"
    assert d_role["region"] == "us-west-2"

    cfg_keys = FleetAccountConfig(
        account_id="222222222222",
        account_name="App-Dev",
        access_key="AKIA123",
        secret_key="secretKey456"
    )
    d_keys = cfg_keys.to_dict()
    assert d_keys["account_id"] == "222222222222"
    assert d_keys["auth_type"] == "keys"


def test_fleet_manager_parallel_scan(sample_fleet_inventory):
    manager = FleetManager(max_workers=4)
    # Clear out any auto-enrolled accounts for isolated unit test
    manager.accounts = {}

    manager.register_account(FleetAccountConfig(
        account_id="acc-prod-1",
        account_name="Prod-Cluster-1",
        region="us-east-1"
    ))
    manager.register_account(FleetAccountConfig(
        account_id="acc-prod-2",
        account_name="Prod-Cluster-2",
        region="us-west-2"
    ))

    with patch("collectors.fleet_manager.AWSDataIngestionOrchestrator") as mock_orch_cls:
        mock_instance = MagicMock()
        mock_instance.execute_full_pipeline.return_value = sample_fleet_inventory
        mock_orch_cls.return_value = mock_instance

        summary = manager.scan_fleet_parallel(["acc-prod-1", "acc-prod-2"])

        assert summary["total_accounts_registered"] == 2
        assert summary["accounts_scanned"] == 2
        assert summary["successful_scans"] == 2
        assert summary["failed_scans"] == 0
        assert summary["total_fleet_nodes"] == 2
        assert summary["total_fleet_volumes"] == 2
        assert summary["total_fleet_eips"] == 2
        assert summary["total_focus_records"] == 6
        assert summary["total_fleet_monthly_spend"] == round(42.05 * 2, 2)


def test_fleet_manager_resilience():
    manager = FleetManager(max_workers=2)
    manager.accounts = {}

    manager.register_account(FleetAccountConfig(
        account_id="acc-good",
        account_name="Good-Account",
        region="us-east-1"
    ))
    manager.register_account(FleetAccountConfig(
        account_id="acc-bad",
        account_name="Bad-Account",
        region="fail-region"
    ))

    def mock_orch_side_effect(session, region):
        mock_orch = MagicMock()
        if region == "fail-region":
            mock_orch.execute_full_pipeline.side_effect = RuntimeError("AWS STS Access Denied")
        else:
            mock_orch.execute_full_pipeline.return_value = {
                "metadata": {"region": region},
                "compute": {"nodes": [{"instance_id": "i-ok", "cost": 10.0}]},
                "summary": {"estimated_monthly_spend": 10.0}
            }
        return mock_orch

    with patch("collectors.fleet_manager.AWSDataIngestionOrchestrator", side_effect=mock_orch_side_effect), \
         patch("collectors.fleet_manager.fleet_cache"):
        summary = manager.scan_fleet_parallel(["acc-good", "acc-bad"])
        assert summary["accounts_scanned"] == 2
        assert summary["successful_scans"] == 1
        assert summary["failed_scans"] == 1


def test_fleet_fastapi_endpoints():
    client = TestClient(app)

    # 1. Accounts endpoint
    res = client.get("/api/v2/fleet/accounts")
    assert res.status_code == 200
    data = res.json()
    assert "total_accounts" in data
    assert "accounts" in data

    # 2. Register account endpoint
    post_res = client.post("/api/v2/fleet/accounts", json={
        "account_id": "999988887777",
        "account_name": "FinOps-Test-Subaccount",
        "region": "eu-west-1",
        "role_arn": "arn:aws:iam::999988887777:role/FinOpsAudit"
    })
    assert post_res.status_code == 200
    reg_data = post_res.json()
    assert reg_data["status"] == "success"
    assert reg_data["account"]["account_id"] == "999988887777"

    # 3. Fleet summary endpoint
    sum_res = client.get("/api/v2/fleet/summary")
    assert sum_res.status_code == 200
    sum_data = sum_res.json()
    assert "total_fleet_monthly_spend" in sum_data
    assert "total_fleet_nodes" in sum_data
    assert "total_focus_records" in sum_data

    # 4. FOCUS records endpoint
    focus_res = client.get("/api/v2/fleet/focus-records")
    assert focus_res.status_code == 200
    focus_data = focus_res.json()
    assert focus_data["specification"] == "FOCUS 1.0"
    assert "records" in focus_data
    assert isinstance(focus_data["records"], list)


def test_cli_cmd_fleet(capsys):
    mock_summary_data = {
        "total_accounts_registered": 3,
        "accounts_scanned": 3,
        "successful_scans": 3,
        "failed_scans": 0,
        "total_fleet_monthly_spend": 150.75,
        "total_fleet_nodes": 6,
        "total_fleet_volumes": 8,
        "total_fleet_eips": 2,
        "total_focus_records": 16,
        "scan_duration_seconds": 1.2
    }

    mock_accounts_data = {
        "total_accounts": 2,
        "accounts": [
            {
                "account_id": "111111111111",
                "account_name": "Org-Root",
                "region": "us-east-1",
                "auth_type": "assume_role",
                "is_management_account": True
            },
            {
                "account_id": "222222222222",
                "account_name": "Workload-Prod",
                "region": "us-east-1",
                "auth_type": "assume_role",
                "is_management_account": False
            }
        ]
    }

    # Test summary table
    args_summary = argparse.Namespace(
        fleet_action="summary",
        format="table",
        output=None,
        url="http://testbackend",
        json_only=False
    )
    with patch("cli_main.http_json", return_value=mock_summary_data):
        cmd_fleet(args_summary)
        out = capsys.readouterr().out
        assert "CLOUDPULSE ENTERPRISE FLEET EXECUTIVE SUMMARY" in out
        assert "$150.75" in out
        assert "16 normalized cost lines" in out

    # Test summary JSON
    args_json = argparse.Namespace(
        fleet_action="summary",
        format="json",
        output=None,
        url="http://testbackend",
        json_only=True
    )
    with patch("cli_main.http_json", return_value=mock_summary_data):
        cmd_fleet(args_json)
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["total_fleet_nodes"] == 6

    # Test accounts table
    args_accounts = argparse.Namespace(
        fleet_action="accounts",
        format="table",
        output=None,
        url="http://testbackend",
        json_only=False
    )
    with patch("cli_main.http_json", return_value=mock_accounts_data):
        cmd_fleet(args_accounts)
        out = capsys.readouterr().out
        assert "CLOUDPULSE MULTI-ACCOUNT FLEET INVENTORY" in out
        assert "111111111111" in out
        assert "Org-Root" in out
