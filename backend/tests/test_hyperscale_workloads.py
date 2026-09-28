"""
Unit & Integration Test Suite for Hyperscale Workload Hierarchy, CUR 2.0 Ingestion & Policy Guardrails
"""

import os
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

_backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_backend_dir))

from engines.cur_ingestion_engine import cur_ingestion_engine
from engines.workload_hierarchy_engine import workload_hierarchy_engine
from engines.policy_guardrails_engine import policy_guardrails_engine
from main import app

client = TestClient(app)


def test_cur_parquet_generation_and_ingest(tmp_path):
    """Verifies synthesis of realistic AWS CUR 2.0 Parquet and zero-copy DuckDB lakehouse ingestion."""
    parquet_file = str(tmp_path / "test_cur.parquet")
    generated_path = cur_ingestion_engine.generate_sample_cur_parquet(parquet_file, num_records=100)
    assert os.path.exists(generated_path)

    # Ingest into lakehouse
    res = cur_ingestion_engine.ingest_cur_parquet(generated_path)
    assert res["status"] == "success"
    assert res["records_ingested"] >= 100
    assert res["ingestion_latency_ms"] >= 0.0

    # Query workloads directly from CUR Parquet
    workloads = cur_ingestion_engine.query_workloads_from_cur(generated_path)
    assert len(workloads) > 0
    assert "team" in workloads[0]
    assert "workload" in workloads[0]
    assert "total_monthly_spend" in workloads[0]


def test_workload_hierarchy_tree_builder():
    """Verifies multi-level tree construction (Org -> Account -> Team -> Workload -> Node)."""
    sample_inventory = {
        "metadata": {"account_id": "111122223333", "account_name": "Prod-Environment"},
        "compute": {
            "nodes": [
                {
                    "instance_id": "i-test-01",
                    "name": "checkout-api-1",
                    "instance_type": "m5.2xlarge",
                    "state": "running",
                    "cpu_utilization": 4.5,
                    "cost": 150.0,
                    "tags": {"Team": "checkout", "Environment": "production", "Workload": "checkout-asg"}
                },
                {
                    "instance_id": "i-test-02",
                    "name": "checkout-api-2",
                    "instance_type": "m5.2xlarge",
                    "state": "running",
                    "cpu_utilization": 45.0,
                    "cost": 150.0,
                    "tags": {"Team": "checkout", "Environment": "production", "Workload": "checkout-asg"}
                },
                {
                    "instance_id": "i-test-03",
                    "name": "data-worker-1",
                    "instance_type": "r5.xlarge",
                    "state": "running",
                    "cpu_utilization": 60.0,
                    "cost": 120.0,
                    "tags": {"Team": "data-infra", "Environment": "staging", "Workload": "kafka-fleet"}
                }
            ]
        }
    }

    tree = workload_hierarchy_engine.build_tree_from_inventory(sample_inventory, org_name="Acme-Global")
    assert tree["organization_name"] == "Acme-Global"
    assert tree["total_nodes_managed"] == 3
    assert tree["total_monthly_spend"] == 420.0
    assert tree["total_potential_savings"] > 0.0

    account = tree["accounts"][0]
    assert account["account_id"] == "111122223333"
    assert len(account["teams"]) == 2  # checkout and data-infra

    checkout_team = next(t for t in account["teams"] if t["team_name"] == "checkout")
    assert checkout_team["node_count"] == 2
    assert len(checkout_team["workloads"]) == 1
    asg = checkout_team["workloads"][0]
    assert asg["workload_name"] == "checkout-asg"
    assert asg["idle_nodes_count"] == 1


def test_policy_guardrails_evaluation():
    """Verifies batch evaluation of automated enterprise FinOps guardrails."""
    policies = policy_guardrails_engine.list_policies()
    assert len(policies) >= 5

    sample_inventory = {
        "compute": {
            "nodes": [
                {
                    "instance_id": "i-idle-dev",
                    "name": "dev-box",
                    "instance_type": "c5.xlarge",
                    "state": "running",
                    "cpu_utilization": 2.1,
                    "cost": 50.0,
                    "tags": {"Environment": "development"}
                }
            ]
        },
        "ec2_other_resources": {
            "ebs_volumes": [
                {"volume_id": "vol-orphan-1", "size_gb": 100, "is_orphaned": True, "cost": 10.0}
            ],
            "elastic_ips": [
                {"public_ip": "54.21.34.55", "is_unattached": True, "estimated_monthly_cost": 3.65}
            ]
        }
    }

    eval_result = policy_guardrails_engine.evaluate_fleet(sample_inventory)
    assert eval_result["total_violations_detected"] >= 3
    assert eval_result["total_recoverable_monthly_savings"] > 40.0
    assert len(eval_result["policy_evaluations"]) >= 5


def test_fastapi_hyperscale_endpoints():
    """Verifies REST endpoints for workload tree, CUR sync, and policy management."""
    # 1. GET /api/v2/workloads/tree
    res_tree = client.get("/api/v2/workloads/tree")
    assert res_tree.status_code == 200
    tree_data = res_tree.json()
    assert "total_monthly_spend" in tree_data
    assert "accounts" in tree_data

    # 2. GET /api/v2/workloads/cur
    res_cur = client.get("/api/v2/workloads/cur")
    assert res_cur.status_code == 200
    cur_data = res_cur.json()
    assert cur_data["status"] == "success"
    assert "workloads" in cur_data

    # 3. GET /api/v2/policies
    res_pol = client.get("/api/v2/policies")
    assert res_pol.status_code == 200
    assert res_pol.json()["count"] >= 5

    # 4. POST /api/v2/policies/evaluate
    res_eval = client.post("/api/v2/policies/evaluate")
    assert res_eval.status_code == 200
    eval_data = res_eval.json()
    assert "total_violations_detected" in eval_data

    # 5. POST /api/v2/policies/{policy_id}/toggle
    res_toggle = client.post("/api/v2/policies/pol-idle-dev-cpu/toggle", json={"is_enabled": False})
    assert res_toggle.status_code == 200
    assert res_toggle.json()["policy"]["is_enabled"] is False

    # Restore policy
    client.post("/api/v2/policies/pol-idle-dev-cpu/toggle", json={"is_enabled": True})


def test_policy_remediation_and_commitments():
    """Verifies 1-click Terraform PR generation for guardrails and commitment arbitrage engine."""
    # 1. Remediate zombie EBS volume
    res_rem = client.post("/api/v2/policies/pol-zombie-ebs/remediate", json={"resource_id": "vol-0a1b2c3d4e5f"})
    assert res_rem.status_code == 200
    rem_data = res_rem.json()
    assert rem_data["status"] == "success"
    assert "terraform_hcl" in rem_data
    assert "resource \"aws_ebs_snapshot\"" in rem_data["terraform_hcl"]
    assert rem_data["estimated_monthly_savings"] > 0
    assert "canary_watchdog_id" in rem_data

    # 2. Get commitment portfolio
    res_port = client.get("/api/v2/commitments/portfolio?coverage_target=0.80")
    assert res_port.status_code == 200
    port_data = res_port.json()
    assert port_data["coverage_target_ratio"] == 0.80
    assert len(port_data["plans"]) >= 3
    assert port_data["plans"][0]["monthly_savings"] > 0
    assert "iac_templates" in port_data
    assert "aws_savingsplans_savings_plan" in port_data["iac_templates"]["terraform"]
