import pytest
import time
import json
import numpy as np
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from services.vector_store import TextVectorizer, VectorKnowledgeStore, vector_knowledge_store
from services.query_cache import FinOpsQueryCache, query_cache
from services.finops_rag import FinOpsRAGPipeline
from main import app


def test_text_vectorizer():
    vectorizer = TextVectorizer(vector_dim=128)
    vec1 = vectorizer.vectorize("AWS Graviton ARM compute instance")
    vec2 = vectorizer.vectorize("Graviton processor migration for EC2")
    vec3 = vectorizer.vectorize("S3 glacier deep archive bucket policy")

    # Verify unit length normalization
    assert math_is_close(float(np.linalg.norm(vec1)), 1.0, abs_tol=1e-3)
    assert math_is_close(float(np.linalg.norm(vec2)), 1.0, abs_tol=1e-3)

    # Cosine similarity between related texts should be substantially higher than unrelated
    sim_related = float(np.dot(vec1, vec2))
    sim_unrelated = float(np.dot(vec1, vec3))
    assert sim_related > sim_unrelated
    assert sim_related > 0.10


def math_is_close(a, b, abs_tol=1e-4):
    return abs(a - b) <= abs_tol


def test_vector_knowledge_store_bootstrap():
    store = VectorKnowledgeStore(vector_dim=256)
    docs = store.get_all_documents()
    assert len(docs) >= 8

    categories = {d["category"] for d in docs}
    assert "well-architected" in categories
    assert "modernization" in categories
    assert "storage" in categories
    assert "networking" in categories
    assert "tagging-policy" in categories
    assert "focus-standards" in categories


def test_vector_knowledge_store_search():
    store = VectorKnowledgeStore(vector_dim=256)

    # 1. EBS gp2 -> gp3 search
    results_storage = store.search("how to upgrade ebs gp2 volumes to gp3", top_k=2)
    assert len(results_storage) > 0
    top_storage = results_storage[0]
    assert "gp3" in top_storage["title"].lower() or "ebs" in top_storage["title"].lower()

    # 2. Graviton search
    results_graviton = store.search("Migrate workloads to Graviton ARM processors", top_k=2)
    assert len(results_graviton) > 0
    top_graviton = results_graviton[0]
    assert "graviton" in top_graviton["title"].lower()

    # 3. Mandatory tagging search
    results_tagging = store.search("mandatory tags environment owner cost center", top_k=2)
    assert len(results_tagging) > 0
    top_tagging = results_tagging[0]
    assert "tagging" in top_tagging["title"].lower()


def test_vector_knowledge_store_custom_document():
    store = VectorKnowledgeStore(vector_dim=256)
    store.add_document(
        doc_id="corp-aurora-serverless",
        title="Corporate Aurora Serverless v2 Auto-Pause Standard",
        content="All non-production RDS Aurora clusters must have serverless v2 auto-pause configured after 30 minutes of zero client connections.",
        category="database",
        tags=["aurora", "rds", "serverless", "auto-pause"]
    )

    results = store.search("Aurora Serverless auto-pause idle database", top_k=1)
    assert len(results) == 1
    assert results[0]["id"] == "corp-aurora-serverless"
    assert results[0]["category"] == "database"


def test_query_cache():
    cache = FinOpsQueryCache(default_ttl_seconds=2)
    cache.clear()

    q = "What is our Graviton savings potential?"
    fp = "ts:100:2:2"
    mock_resp = {"answer": "You can save $13.14/month by moving to Graviton.", "status": "success"}

    # 1. Cache miss initially
    assert cache.get(q, fp) is None

    # 2. Set cache entry
    cache.set(q, mock_resp, fp, ttl_seconds=1)

    # 3. Cache hit
    hit = cache.get(q, fp)
    assert hit is not None
    assert hit["answer"] == mock_resp["answer"]
    assert hit["cached"] is True
    assert hit["cache_hit"] is True

    # 4. Inventory fingerprint invalidation (e.g. instance terminated or created)
    different_fp = "ts:80:1:2"
    assert cache.get(q, different_fp) is None

    # 5. TTL expiration
    time.sleep(1.1)
    assert cache.get(q, fp) is None

    stats = cache.get_stats()
    assert stats["hits"] >= 1
    assert stats["misses"] >= 2


def test_fastapi_knowledge_and_cache_endpoints():
    client = TestClient(app)

    # 1. Search endpoint
    s_res = client.get("/api/v2/copilot/knowledge/search?q=graviton&limit=2")
    assert s_res.status_code == 200
    s_data = s_res.json()
    assert s_data["count"] > 0
    assert "results" in s_data

    # 2. Policies list endpoint
    p_res = client.get("/api/v2/copilot/knowledge/policies")
    assert p_res.status_code == 200
    p_data = p_res.json()
    assert p_data["count"] >= 8

    # 3. Index new policy endpoint
    i_res = client.post("/api/v2/copilot/knowledge/index", json={
        "id": "test-finops-policy-s3",
        "title": "S3 Intelligent Tiering Policy",
        "content": "Objects over 128KB not accessed for 30 days must transition to Archive Instant Access.",
        "category": "storage"
    })
    assert i_res.status_code == 200
    assert i_res.json()["status"] == "success"

    # 4. Cache stats endpoint
    c_res = client.get("/api/v2/copilot/rag/cache-stats")
    assert c_res.status_code == 200
    assert "hit_rate_percent" in c_res.json()

    # 5. Clear cache endpoint
    del_res = client.delete("/api/v2/copilot/rag/cache")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "success"


def test_finops_rag_hybrid_retrieval_and_cache():
    pipeline = FinOpsRAGPipeline()
    sample_inventory = {
        "metadata": {"region": "us-east-1", "timestamp": "2026-09-19T00:00:00Z"},
        "compute": {
            "nodes": [
                {
                    "instance_id": "i-hybrid-01",
                    "instance_type": "t3.micro",
                    "state": "running",
                    "cost": 7.60,
                    "metrics": {"cpu_utilization_avg": 0.2}
                }
            ]
        },
        "ec2_other_resources": {
            "ebs_volumes": [
                {
                    "volume_id": "vol-hybrid-01",
                    "volume_type": "gp2",
                    "size_gb": 100,
                    "cost": 10.00
                }
            ]
        },
        "summary": {"estimated_monthly_spend": 17.60}
    }

    # 1. Test hybrid retrieval
    retrieved = pipeline.retrieve_context(
        query="Should we upgrade our gp2 EBS storage to gp3?",
        inventory=sample_inventory
    )
    assert len(retrieved["ebs_volumes"]) == 1
    assert "semantic_policies" in retrieved
    assert len(retrieved["semantic_policies"]) > 0

    # 2. Test augment stage
    augmented = pipeline.augment_context(retrieved, user_query="Should we upgrade our gp2 EBS storage to gp3?")
    assert "AWS Well-Architected Framework & Enterprise Policy Guidelines" in augmented["augmented_prompt"]
    assert len(augmented["semantic_policies"]) > 0

    # 3. Test ask with query caching
    res1 = pipeline.ask("How to optimize our gp2 volumes?", inventory=sample_inventory, use_cache=True)
    assert res1["status"] in ["success", "fallback"]
    assert res1.get("cached") is False

    # Second call should be retrieved from query cache
    res2 = pipeline.ask("How to optimize our gp2 volumes?", inventory=sample_inventory, use_cache=True)
    assert res2.get("cached") is True
