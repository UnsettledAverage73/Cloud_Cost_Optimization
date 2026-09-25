"""
CloudPulse Copilot & RAG Domain API Router
Autonomous FinOps LLM assistant, semantic knowledge base, and rate card endpoints.
"""

import os
import uuid
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends

try:
    from copilot.agent import FinOpsAutonomousCopilot
    from copilot.tools.pricing_rag_tool import lookup_aws_pricing
    from services.finops_rag import finops_rag_pipeline
    from services.vector_store import vector_knowledge_store
    from services.query_cache import query_cache
    from services.opencost_engine import opencost_engine
    from engines.focus_lakehouse import focus_lakehouse
except ImportError:
    from backend.copilot.agent import FinOpsAutonomousCopilot
    from backend.copilot.tools.pricing_rag_tool import lookup_aws_pricing
    from backend.services.finops_rag import finops_rag_pipeline
    from backend.services.vector_store import vector_knowledge_store
    from backend.services.query_cache import query_cache
    from backend.services.opencost_engine import opencost_engine
    from backend.engines.focus_lakehouse import focus_lakehouse

router = APIRouter(prefix="/api/v2/copilot", tags=["Copilot & RAG Engine"])

# Copilot Agent instance
copilot_agent = FinOpsAutonomousCopilot()


@router.post("/chat")
async def copilot_chat(payload: dict):
    """
    Primary FinOps Copilot endpoint powered by Groq LLM and live telemetry tools.
    """
    message = payload.get("message") or payload.get("prompt") or ""
    history = payload.get("history", [])
    response = copilot_agent.chat(user_message=message, history=history)
    return response


@router.post("/rag/ask")
async def copilot_rag_ask(payload: dict):
    """
    Direct endpoint for FinOps RAG queries across multi-domain cloud and container telemetry.
    """
    query = payload.get("query") or payload.get("message") or payload.get("prompt") or ""
    custom_inv = payload.get("inventory")
    response = finops_rag_pipeline.ask(query=query, inventory=custom_inv)
    return response


@router.post("/rag/recommendations")
async def copilot_rag_recommendations(payload: Optional[dict] = None):
    """
    Executes complete FinOps RAG recommendation synthesis across live cloud inventory.
    """
    payload = payload or {}
    custom_inv = payload.get("inventory")
    focus_domain = payload.get("focus_domain") or payload.get("focus") or payload.get("domain")
    response = finops_rag_pipeline.generate_recommendations(inventory=custom_inv, focus_domain=focus_domain)
    return response


@router.get("/rag/status")
async def get_copilot_rag_status():
    """
    Returns live Groq RAG pipeline status, active model, and multi-domain telemetry counts.
    """
    engine_ready = finops_rag_pipeline.engine and finops_rag_pipeline.engine.is_available()
    active_model = getattr(finops_rag_pipeline.engine, "active_model", None) if finops_rag_pipeline.engine else None
    inv = finops_rag_pipeline._get_inventory()
    nodes = inv.get("compute", {}).get("nodes") or inv.get("nodes", [])
    vols = inv.get("ec2_other_resources", {}).get("ebs_volumes") or inv.get("ebs_volumes", [])
    eips = inv.get("ec2_other_resources", {}).get("elastic_ips") or inv.get("elastic_ips", [])
    sgs = inv.get("ec2_other_resources", {}).get("security_groups") or inv.get("security_groups", [])
    logs = inv.get("ec2_other_resources", {}).get("cloudwatch_log_groups") or inv.get("cloudwatch_log_groups", [])

    k8s_count = len(getattr(opencost_engine, "workloads", [])) if opencost_engine else 0
    lake_count = 0
    if focus_lakehouse:
        try:
            c = focus_lakehouse.conn.execute("SELECT COUNT(*) FROM focus_costs").fetchone()
            lake_count = c[0] if c else 0
        except Exception:
            pass
    policy_count = len(vector_knowledge_store.get_all_documents()) if vector_knowledge_store else 0

    return {
        "status": "ready" if engine_ready else "fallback_ready",
        "pipeline": "FinOpsRAGPipeline",
        "provider": "groq" if engine_ready else "deterministic_engine",
        "active_model": active_model,
        "groq_configured": bool(os.getenv("GROQ_API_KEY") or getattr(finops_rag_pipeline.engine, "api_key", None)),
        "retrieval_sources": {
            "compute_nodes": len(nodes),
            "ebs_volumes": len(vols),
            "elastic_ips": len(eips),
            "security_groups": len(sgs),
            "cloudwatch_log_groups": len(logs),
            "kubernetes_workloads": k8s_count,
            "focus_lakehouse_records": lake_count,
            "indexed_finops_policies": policy_count,
            "aws_rate_card": "active (us-east-1)"
        },
        "supported_domains": ["all", "compute", "storage", "network", "security", "logs", "kubernetes", "lakehouse"]
    }


@router.get("/rag/cache-stats")
async def get_rag_cache_stats():
    """Returns RAG query cache performance metrics and hit rates."""
    return query_cache.get_stats()


@router.delete("/rag/cache")
async def clear_rag_cache():
    """Clears the RAG query cache."""
    query_cache.clear()
    return {"status": "success", "message": "Query cache cleared"}


@router.get("/knowledge/search")
async def search_knowledge_base(q: str = "", limit: int = 3):
    """Executes semantic vector search over Well-Architected and FinOps policies."""
    results = vector_knowledge_store.search(query=q, top_k=limit)
    return {"query": q, "count": len(results), "results": results}


@router.get("/knowledge/policies")
async def list_knowledge_policies():
    """Lists all indexed policies in the semantic vector store."""
    docs = vector_knowledge_store.get_all_documents()
    return {"count": len(docs), "policies": docs}


@router.post("/knowledge/index")
async def index_knowledge_policy(payload: dict):
    """Indexes a new custom organization FinOps policy into the vector knowledge base."""
    doc_id = payload.get("id") or str(uuid.uuid4())
    title = payload.get("title")
    content = payload.get("content")
    if not title or not content:
        raise HTTPException(status_code=400, detail="title and content are required")
    category = payload.get("category", "custom-policy")
    tags = payload.get("tags", [])
    vector_knowledge_store.add_document(doc_id=doc_id, title=title, content=content, category=category, tags=tags)
    vector_knowledge_store.save_to_disk()
    return {"status": "success", "indexed_id": doc_id}


@router.get("/status")
async def get_copilot_status():
    """Returns active FinOps Copilot status and tools."""
    engine_ready = copilot_agent.engine and copilot_agent.engine.is_available()
    active_model = getattr(copilot_agent.engine, "active_model", "compound-mini") if copilot_agent.engine else None
    return {
        "status": "ready" if engine_ready else "heuristic_fallback",
        "provider": copilot_agent.provider,
        "active_model": active_model,
        "tools_enabled": [
            "sql_analytics", "pricing_rag", "cloudtrail_forensics",
            "terraform_pr", "kubernetes_allocations", "focus_lakehouse", "vector_knowledge"
        ],
        "groq_configured": bool(copilot_agent.groq_api_key)
    }


@router.get("/pricing")
async def get_pricing(resource_type: str = "m5.2xlarge", region: str = "us-east-1"):
    """Returns real-time AWS pricing rate cards and Graviton ROI comparisons."""
    pricing = lookup_aws_pricing(resource_type=resource_type, region=region)
    return pricing


@router.post("/diagnose-spike")
async def copilot_diagnose_spike(payload: Optional[dict] = None):
    """
    Autonomous root-cause cost anomaly diagnostic agent correlating CloudWatch metrics,
    CloudTrail events, AWS Pricing Catalog, and generating Terraform remediation code.
    """
    payload = payload or {}
    service = payload.get("service", "AmazonEC2")
    spike_date = payload.get("spike_date")
    diagnostic = copilot_agent.diagnose_spike(service=service, spike_date=spike_date)
    return diagnostic


@router.post("/generate-iac-pr")
async def copilot_generate_iac_pr(payload: dict):
    """Autonomous Terraform/OpenTofu remediation pull request generator."""
    res = copilot_agent.run_tool("terraform_pr", payload)
    return res
