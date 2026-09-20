"""
Unit & Integration Tests for CloudPulse Kubernetes OpenCost & Workload FinOps Engine (Milestone 2 - Priority 3).
Verifies pod cost allocation, cluster efficiency aggregation, rightsizing YAML diffs,
FOCUS 1.0 lakehouse ingestion, FastAPI endpoints, and CLI k8s command.
"""

import json
import argparse
import pytest
from fastapi.testclient import TestClient

from services.opencost_engine import KubernetesCostEngine, opencost_engine
from engines.focus_lakehouse import FOCUSLakehouse
from cli_main import cmd_k8s
from main import app


@pytest.fixture
def custom_k8s_engine():
    workloads = [
        {
            "cluster": "test-cluster",
            "namespace": "production",
            "workload": "api-service",
            "kind": "Deployment",
            "replicas": 2,
            "container": "api",
            "requested_cpu_cores": 2.0,
            "utilized_cpu_cores": 0.4,
            "requested_ram_gib": 4.0,
            "utilized_ram_gib": 1.0,
            "storage_pvc_gib": 10.0,
            "labels": {"app": "api"}
        },
        {
            "cluster": "test-cluster",
            "namespace": "staging",
            "workload": "worker",
            "kind": "StatefulSet",
            "replicas": 1,
            "container": "worker",
            "requested_cpu_cores": 1.0,
            "utilized_cpu_cores": 0.8,
            "requested_ram_gib": 2.0,
            "utilized_ram_gib": 1.6,
            "storage_pvc_gib": 0.0,
            "labels": {"app": "worker"}
        }
    ]
    return KubernetesCostEngine(workloads=workloads)


def test_kubernetes_cost_calculation(custom_k8s_engine):
    """Verifies requested vs utilized spend and efficiency scoring for a workload."""
    workload = custom_k8s_engine.workloads[0]
    metrics = custom_k8s_engine.calculate_workload_cost(workload)

    assert metrics["workload"] == "api-service"
    assert metrics["requested_cpu_cores"] == 4.0  # 2 cores * 2 replicas
    assert metrics["utilized_cpu_cores"] == 0.8   # 0.4 cores * 2 replicas
    assert metrics["monthly_requested_cost"] > metrics["monthly_utilized_cost"]
    assert metrics["monthly_idle_waste"] > 0.0
    assert metrics["overall_efficiency_pct"] == 22.5  # (20% CPU + 25% RAM) / 2


def test_cluster_efficiency_aggregation(custom_k8s_engine):
    """Verifies cluster-level efficiency metrics and namespace breakdowns."""
    eff = custom_k8s_engine.get_cluster_efficiency(currency="USD")

    assert eff["cluster_count"] == 1
    assert eff["total_workloads"] == 2
    assert eff["monthly_requested_cost"] > 0.0
    assert eff["monthly_idle_waste"] > 0.0
    assert eff["overall_efficiency_pct"] > 0.0
    assert len(eff["namespaces"]) == 2

    # Namespace ordering by requested spend
    ns_names = [n["namespace"] for n in eff["namespaces"]]
    assert "production" in ns_names
    assert "staging" in ns_names


def test_rightsizing_recommendations_and_yaml_diff(custom_k8s_engine):
    """Verifies identification of over-provisioned pods and generation of clean YAML patch diffs."""
    recs = custom_k8s_engine.get_rightsizing_recommendations(efficiency_threshold=30.0)

    assert len(recs) == 1
    rec = recs[0]
    assert rec["workload"] == "api-service"
    assert rec["monthly_savings"] > 0.0
    assert rec["annual_savings"] == round(rec["monthly_savings"] * 12.0, 2)
    assert "--- a/k8s/production/api-service.yaml" in rec["yaml_diff"]
    assert "+++ b/k8s/production/api-service.yaml" in rec["yaml_diff"]
    assert "-            cpu:" in rec["yaml_diff"]
    assert "+            cpu:" in rec["yaml_diff"]


def test_focus_1_0_kubernetes_transformation(custom_k8s_engine):
    """Verifies that Kubernetes workloads are mapped into standard FOCUS 1.0 schema and queryable via DuckDB."""
    records = custom_k8s_engine.to_focus_records(account_id="999888777666", region="us-west-2")

    assert len(records) == 2
    first = records[0]
    assert first["BillingAccountId"] == "999888777666"
    assert first["ServiceName"] == "Amazon Elastic Kubernetes Service"
    assert first["ServiceCategory"] == "Container"
    assert first["PricingCategory"] == "Allocated"
    assert "k8s/test-cluster/production/api-service" in first["ResourceId"]

    # Ingest into FOCUSLakehouse
    lakehouse = FOCUSLakehouse()
    lakehouse.load_focus_records(records, clear_existing=True)
    res = lakehouse.execute_query("SELECT SUM(EffectiveCost) as container_spend FROM focus_costs WHERE ServiceName LIKE '%Kubernetes%'")
    assert res["row_count"] == 1
    assert res["rows"][0]["container_spend"] > 0.0


def test_opencost_payload_ingestion():
    """Verifies dynamic ingestion of standard OpenCost API payload."""
    engine = KubernetesCostEngine(workloads=[])
    payload = {
        "code": 200,
        "data": [
            {
                "prod/payment-service": {
                    "cluster": "eks-live",
                    "cpuCoreRequestAverage": 1.5,
                    "cpuCoreUsageAverage": 0.3,
                    "ramByteRequestAverage": 1024**3 * 4,
                    "ramByteUsageAverage": 1024**3 * 1,
                    "controllerKind": "Deployment",
                    "replicas": 3
                }
            }
        ]
    }
    ingested_count = engine.ingest_opencost_payload(payload)
    assert ingested_count == 1
    assert len(engine.workloads) == 1
    w = engine.workloads[0]
    assert w["namespace"] == "prod"
    assert w["workload"] == "payment-service"
    assert w["requested_cpu_cores"] == 1.5


def test_fastapi_kubernetes_endpoints():
    """Verifies FastAPI endpoints for allocations, efficiency, recommendations, and ingestion."""
    client = TestClient(app)

    # 1. Allocations
    resp_alloc = client.get("/api/v2/kubernetes/allocations")
    assert resp_alloc.status_code == 200
    alloc_data = resp_alloc.json()
    assert isinstance(alloc_data, list)
    assert len(alloc_data) > 0

    # 2. Efficiency
    resp_eff = client.get("/api/v2/kubernetes/efficiency?currency=INR")
    assert resp_eff.status_code == 200
    eff_data = resp_eff.json()
    assert "overall_efficiency_pct" in eff_data
    assert "formatted_idle_waste" in eff_data

    # 3. Recommendations
    resp_recs = client.get("/api/v2/kubernetes/recommendations?threshold=50.0")
    assert resp_recs.status_code == 200
    recs_data = resp_recs.json()
    assert isinstance(recs_data, list)
    assert any("yaml_diff" in r for r in recs_data)

    # 4. Ingest
    sample_payload = {
        "data": [
            {
                "finance/billing-worker": {
                    "cluster": "eks-core",
                    "cpuCoreRequestAverage": 2.0,
                    "cpuCoreUsageAverage": 0.5,
                    "ramByteRequestAverage": 1024**3 * 2,
                    "ramByteUsageAverage": 1024**3 * 0.5
                }
            }
        ]
    }
    resp_ingest = client.post("/api/v2/kubernetes/ingest", json=sample_payload)
    assert resp_ingest.status_code == 200
    assert resp_ingest.json()["ingested_workloads"] == 1


def test_cli_cmd_k8s_workload_table(capsys):
    """Verifies CLI cmd_k8s table output."""
    args = argparse.Namespace(
        namespace=None,
        efficiency=False,
        recommend=False,
        threshold=40.0,
        currency="USD",
        format="table",
        json_only=False,
        output=None,
        url="http://localhost:8000"
    )
    cmd_k8s(args)
    captured = capsys.readouterr().out
    assert "CLOUDPULSE KUBERNETES OPENCOST ENGINE: KUBERNETES WORKLOAD COST ALLOCATIONS" in captured
    assert "NAMESPACE" in captured
    assert "WORKLOAD" in captured


def test_cli_cmd_k8s_efficiency(capsys):
    """Verifies CLI cmd_k8s --efficiency output."""
    args = argparse.Namespace(
        namespace=None,
        efficiency=True,
        recommend=False,
        threshold=40.0,
        currency="INR",
        format="table",
        json_only=False,
        output=None,
        url="http://localhost:8000"
    )
    cmd_k8s(args)
    captured = capsys.readouterr().out
    assert "KUBERNETES CLUSTER EFFICIENCY & IDLE CAPACITY" in captured
    assert "Overall Cluster Efficiency" in captured
    assert "Recoverable Idle Waste" in captured


def test_cli_cmd_k8s_recommendations(capsys):
    """Verifies CLI cmd_k8s --recommend output."""
    args = argparse.Namespace(
        namespace=None,
        efficiency=False,
        recommend=True,
        threshold=40.0,
        currency="USD",
        format="table",
        json_only=False,
        output=None,
        url="http://localhost:8000"
    )
    cmd_k8s(args)
    captured = capsys.readouterr().out
    assert "KUBERNETES WORKLOAD RIGHTSIZING RECOMMENDATIONS" in captured
    assert "--- a/k8s/" in captured
    assert "+++ b/k8s/" in captured


def test_cli_cmd_k8s_json_format(capsys):
    """Verifies CLI cmd_k8s with --json."""
    args = argparse.Namespace(
        namespace=None,
        efficiency=True,
        recommend=False,
        threshold=40.0,
        currency="USD",
        format="json",
        json_only=True,
        output=None,
        url="http://localhost:8000"
    )
    cmd_k8s(args)
    captured = capsys.readouterr().out
    data = json.loads(captured)
    assert "overall_efficiency_pct" in data
    assert "namespaces" in data
