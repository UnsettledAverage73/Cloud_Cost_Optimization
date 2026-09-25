import pytest
import json
import argparse
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from services.finops_rag import FinOpsRAGPipeline, finops_rag_pipeline
from main import app


@pytest.fixture
def sample_inventory():
    return {
        "metadata": {"region": "us-east-1", "organization": "TestCorp"},
        "compute": {
            "nodes": [
                {
                    "instance_id": "i-compute123",
                    "name": "web-worker",
                    "instance_type": "t3.micro",
                    "state": "running",
                    "cost": 12.0,
                    "metrics": {"cpu_utilization_avg": 1.2, "cpu_utilization_max": 3.0}
                }
            ]
        },
        "ec2_other_resources": {
            "ebs_volumes": [
                {
                    "volume_id": "vol-orphan123",
                    "size_gb": 50,
                    "volume_type": "gp2",
                    "status": "available",
                    "is_orphaned": True,
                    "cost": 5.0
                }
            ],
            "elastic_ips": [
                {
                    "public_ip": "54.10.20.30",
                    "is_unattached": True,
                    "association_id": None
                }
            ],
            "security_groups": [
                {
                    "group_id": "sg-open22",
                    "group_name": "insecure-sg",
                    "is_publicly_exposed": True,
                    "inbound_rules": [
                        {"protocol": "tcp", "from_port": 22, "to_port": 22, "is_open_to_world": True}
                    ]
                }
            ],
            "cloudwatch_log_groups": [
                {
                    "log_group_name": "/aws/lambda/orphan-logs",
                    "retention_in_days": None,
                    "is_never_expire": True,
                    "stored_gb": 10.0,
                    "cost": 5.0
                }
            ]
        },
        "vpc_resources": {"nat_gateways": []}
    }


def test_rag_retrieval_broad(sample_inventory):
    pipeline = FinOpsRAGPipeline()
    retrieved = pipeline.retrieve_context(inventory=sample_inventory)

    assert retrieved["total_retrieved_items"] >= 5
    assert len(retrieved["nodes"]) == 1
    assert len(retrieved["ebs_volumes"]) == 1
    assert len(retrieved["elastic_ips"]) == 1
    assert len(retrieved["security_groups"]) == 1
    assert len(retrieved["cloudwatch_logs"]) == 1
    assert "t3.micro" in retrieved["pricing_rate_cards"]


def test_rag_retrieval_domain_targeted(sample_inventory):
    pipeline = FinOpsRAGPipeline()
    
    # Target: Storage only
    ret_storage = pipeline.retrieve_context(query="What can we clean up in EBS storage?", inventory=sample_inventory)
    assert "storage" in ret_storage["domains"]
    assert len(ret_storage["ebs_volumes"]) == 1
    assert len(ret_storage["nodes"]) == 0

    # Target: Specific resource ID
    ret_specific = pipeline.retrieve_context(query="Tell me about i-compute123", inventory=sample_inventory)
    assert len(ret_specific["nodes"]) == 1
    assert ret_specific["nodes"][0]["instance_id"] == "i-compute123"


def test_rag_augmentation_calculations(sample_inventory):
    pipeline = FinOpsRAGPipeline()
    retrieved = pipeline.retrieve_context(inventory=sample_inventory)
    augmented = pipeline.augment_context(retrieved)

    # 1. Check computed savings
    # Idle compute: 12.0 * 0.70 = 8.40
    # Orphaned EBS: 5.00
    # Unattached EIP: 3.60
    # Never expire logs: 5.0 * 0.5 = 2.50
    # Total = 8.40 + 5.00 + 3.60 + 2.50 = 19.50
    assert augmented["total_monthly_savings"] >= 15.0
    assert augmented["total_annual_savings"] >= 180.0

    # 2. Check prompt content
    prompt = augmented["augmented_prompt"]
    assert "i-compute123" in prompt
    assert "vol-orphan123" in prompt
    assert "54.10.20.30" in prompt
    assert "sg-open22" in prompt
    assert "RECOVERABLE SAVINGS" in prompt


def test_rag_ask_with_mocked_llm(sample_inventory):
    pipeline = FinOpsRAGPipeline()
    with patch.object(pipeline.engine, "chat_completion", return_value="Mocked Groq RAG Response: Delete vol-orphan123 to save $5.00/mo."):
        with patch.object(pipeline.engine, "is_available", return_value=True):
            res = pipeline.ask("How to save money?", inventory=sample_inventory)
            assert res["status"] == "success"
            assert res["provider"] == "groq"
            assert "vol-orphan123" in res["answer"]


def test_rag_ask_deterministic_fallback(sample_inventory):
    pipeline = FinOpsRAGPipeline()
    with patch.object(pipeline.engine, "is_available", return_value=False):
        res = pipeline.ask("How to save money?", inventory=sample_inventory, use_cache=False)
        assert res["status"] == "fallback"
        assert res["provider"] == "deterministic_rag_fallback"
        assert "vol-orphan123" in res["answer"]
        assert "54.10.20.30" in res["answer"]


def test_rag_generate_recommendations(sample_inventory):
    pipeline = FinOpsRAGPipeline()
    with patch.object(pipeline.engine, "chat_completion", return_value="# Executive Recommendation Report\nMigrate to Graviton t4g.micro"):
        with patch.object(pipeline.engine, "is_available", return_value=True):
            rec = pipeline.generate_recommendations(inventory=sample_inventory)
            assert rec["status"] == "success"
            assert rec["monthly_savings"] > 0
            assert "Graviton" in rec["report_markdown"]


def test_api_rag_endpoints(sample_inventory):
    client = TestClient(app)

    # 1. GET /api/v2/copilot/rag/status
    res_status = client.get("/api/v2/copilot/rag/status")
    assert res_status.status_code == 200
    data = res_status.json()
    assert data["pipeline"] == "FinOpsRAGPipeline"
    assert "retrieval_sources" in data

    # 2. POST /api/v2/copilot/rag/ask
    res_ask = client.post("/api/v2/copilot/rag/ask", json={
        "query": "How much can I save on unattached EIPs?",
        "inventory": sample_inventory
    })
    assert res_ask.status_code == 200
    ask_data = res_ask.json()
    assert "answer" in ask_data
    assert "potential_monthly_savings" in ask_data

    # 3. POST /api/v2/copilot/rag/recommendations
    res_rec = client.post("/api/v2/copilot/rag/recommendations", json={
        "focus_domain": "storage",
        "inventory": sample_inventory
    })
    assert res_rec.status_code == 200
    rec_data = res_rec.json()
    assert "report_markdown" in rec_data
    assert "monthly_savings" in rec_data


def test_cli_recommend_and_rag_test(capsys, tmp_path):
    from cli_main import cmd_recommend, cmd_rag_test

    # 1. CLI recommend to file (mock remote http_json to trigger local pipeline immediately)
    out_file = tmp_path / "rag_recommendations.md"
    args = argparse.Namespace(url=None, focus="compute", format="markdown", output=str(out_file), json_only=False)
    with patch("cli_main.http_json", side_effect=RuntimeError("local mode")):
        cmd_recommend(args)
    assert out_file.exists()
    content = out_file.read_text()
    assert "POTENTIAL MONTHLY RECOVERY" in content

    # 2. CLI rag-test
    with patch.object(finops_rag_pipeline.engine, "chat_completion", return_value="The biggest waste is unattached EBS volume vol-orphan123 costing $5.00/mo."):
        cmd_rag_test(argparse.Namespace())
    out = capsys.readouterr().out
    assert "GROQ FINOPS RAG END-TO-END VERIFICATION" in out
    assert "100% OPERATIONAL" in out


def test_rag_with_kubernetes_and_focus_lakehouse(sample_inventory):
    pipeline = FinOpsRAGPipeline()
    ret = pipeline.retrieve_context(query="Analyze Kubernetes container efficiency and FOCUS Lakehouse spend", inventory=sample_inventory)
    
    assert "kubernetes" in ret["domains"] or "lakehouse" in ret["domains"]
    assert "citations" in ret
    assert any("OpenCost" in c or "AWS" in c for c in ret["citations"])
    
    aug = pipeline.augment_context(ret)
    assert "formatted_monthly_savings" in aug
    assert "₹" in aug["formatted_monthly_savings"]
    assert "$" in aug["formatted_monthly_savings"]
    assert "citations" in aug


def test_copilot_chat_extended_routes():
    from copilot.agent import FinOpsAutonomousCopilot
    copilot = FinOpsAutonomousCopilot()
    
    # 1. Kubernetes container routing
    k8s_res = copilot.chat("Analyze our Kubernetes pods and container waste")
    assert k8s_res["tool_called"] == "kubernetes_allocations"
    assert "Kubernetes" in k8s_res["answer"]
    
    # 2. Well-Architected policy routing
    policy_res = copilot.chat("What is our Well-Architected policy for idle compute?")
    assert policy_res["tool_called"] == "vector_knowledge"
    assert "Well-Architected" in policy_res["answer"]

