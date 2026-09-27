"""
CloudPulse Autonomous Copilot & System Architect Microservice
Port: 8001
Provides SemIf / Jev System-1 decision-making, Groq LLM FinOps Copilot,
RAG pipeline, CloudTrail forensics, and automated IaC/Terraform generation.
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, APIRouter, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

_backend_dir = Path(__file__).resolve().parent.parent
_repo_dir = _backend_dir.parent
for p in [str(_backend_dir), str(_repo_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from microservices.shared_state import _db, finops_agent
    from copilot.agent import FinOpsAutonomousCopilot
    from copilot.tools.pricing_rag_tool import lookup_aws_pricing
    from services.finops_rag import finops_rag_pipeline
    from services.vector_store import vector_knowledge_store
    from services.query_cache import query_cache
    from services.opencost_engine import opencost_engine
    from engines.focus_lakehouse import focus_lakehouse
    from copilot.jew_architect import jew_architect
except ImportError:
    from backend.microservices.shared_state import _db, finops_agent
    from backend.copilot.agent import FinOpsAutonomousCopilot
    from backend.copilot.tools.pricing_rag_tool import lookup_aws_pricing
    from backend.services.finops_rag import finops_rag_pipeline
    from backend.services.vector_store import vector_knowledge_store
    from backend.services.query_cache import query_cache
    from backend.services.opencost_engine import opencost_engine
    from backend.engines.focus_lakehouse import focus_lakehouse
    from backend.copilot.jew_architect import jew_architect

router = APIRouter(tags=["Copilot & Architect Microservice"])
copilot_agent = FinOpsAutonomousCopilot()


@router.post("/api/v1/agent/chat")
async def chat_with_finops_agent(payload: dict):
    """
    Autonomous FinOps AI Assistant query router:
    Supports slash commands (/audit, /optimize, /forecast, /health, /pricing, /remediate)
    and natural language FinOps questions via local Ollama or cloud LLMs.
    """
    query = payload.get("query") or payload.get("prompt")
    if not query:
        raise HTTPException(status_code=400, detail="Query parameter is required")
    finops_agent.data_store = _db()
    return finops_agent.ask(query)


@router.post("/api/v2/copilot/chat")
async def copilot_chat(payload: dict):
    """
    Autonomous LLM FinOps Copilot conversation endpoint with multi-tool dispatch:
    - Text-to-SQL over TimescaleDB
    - Live Pricing Catalog RAG & Graviton ROI
    - CloudTrail root-cause spike forensics
    - Terraform/OpenTofu PR generation
    """
    user_message = payload.get("message") or payload.get("prompt") or payload.get("query") or ""
    history = payload.get("history", [])
    response = copilot_agent.chat(user_message=user_message, history=history)
    return response


@router.post("/api/v2/architect/chat")
async def architect_chat(payload: dict):
    """
    Jew / Jev System Architect: One-Model AI Cloud System Architect.
    Uses SemIf (OpenJev open-source) for fast System-1 tool/function decision-making,
    pluggable with Jev (TypeSafe AI), instrumented with LangSmith tracing.
    """
    user_message = payload.get("message") or payload.get("prompt") or payload.get("query") or ""
    history = payload.get("history", [])
    response = jew_architect.chat(user_message=user_message, history=history)
    return response


@router.post("/api/v2/copilot/diagnose-spike")
async def copilot_diagnose_spike(payload: dict):
    """
    Autonomous root-cause cost anomaly diagnostic agent correlating CloudWatch metrics,
    CloudTrail events, AWS Pricing Catalog, and generating Terraform remediation code.
    """
    service = payload.get("service", "AmazonEC2")
    spike_date = payload.get("spike_date")
    diagnostic = copilot_agent.diagnose_spike(service=service, spike_date=spike_date)
    return diagnostic


@router.post("/api/v2/copilot/generate-iac-pr")
async def copilot_generate_iac_pr(payload: dict):
    """
    Generates ready-to-merge Terraform/OpenTofu Pull Request code for safe remediation.
    """
    finding_id = payload.get("finding_id", "find-idle-ec2-m5")
    resource_id = payload.get("resource_id")
    if not resource_id:
        db = _db()
        nodes = db.get("nodes", [])
        if nodes:
            resource_id = nodes[0].get("instance_id")
        else:
            resource_id = "unidentified-workload"
    action_type = payload.get("action_type", "downsize_ec2")
    current_config = payload.get("current_config", {"instance_type": "m5.2xlarge", "name": "worker_node"})
    recommended_config = payload.get("recommended_config", {"instance_type": "t4g.medium"})
    monthly_savings = float(payload.get("monthly_savings", 243.80))

    pr = copilot_agent.run_tool("terraform_pr", {
        "finding_id": finding_id,
        "resource_id": resource_id,
        "action_type": action_type,
        "current_config": current_config,
        "recommended_config": recommended_config,
        "monthly_savings": monthly_savings
    })
    return pr


@router.get("/api/v2/copilot/pricing")
async def get_pricing_rate_card(resource_type: str = "m5.2xlarge", region: str = "us-east-1"):
    """
    Queries real-time AWS rate card and computes Graviton modernization savings.
    """
    pricing = lookup_aws_pricing(resource_type=resource_type, region=region)
    return pricing


@router.post("/api/v2/copilot/rag/ask")
async def copilot_rag_ask(payload: dict):
    """
    Direct endpoint for FinOps RAG queries across multi-domain cloud and container telemetry.
    """
    query = payload.get("query") or payload.get("message") or payload.get("prompt") or ""
    custom_inv = payload.get("inventory")
    response = finops_rag_pipeline.ask(query=query, inventory=custom_inv)
    return response


@router.post("/api/v2/copilot/rag/recommendations")
async def copilot_rag_recommendations(payload: Optional[dict] = None):
    """
    Executes complete FinOps RAG recommendation synthesis across live cloud inventory.
    """
    payload = payload or {}
    custom_inv = payload.get("inventory")
    focus_domain = payload.get("focus_domain") or payload.get("focus") or payload.get("domain")
    response = finops_rag_pipeline.generate_recommendations(inventory=custom_inv, focus_domain=focus_domain)
    return response


@router.get("/api/v2/copilot/rag/status")
async def get_copilot_rag_status():
    """
    Returns live Groq RAG pipeline status, active model, and inventory telemetry counts.
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


@router.get("/api/v2/copilot/knowledge/search")
async def search_knowledge_base(q: str = "", limit: int = 3):
    """Executes semantic vector search over Well-Architected and FinOps policies."""
    results = vector_knowledge_store.search(query=q, top_k=limit)
    return {"query": q, "count": len(results), "results": results}


@router.get("/api/v2/copilot/knowledge/policies")
async def list_knowledge_policies():
    """Lists all indexed policies in the semantic vector store."""
    docs = vector_knowledge_store.get_all_documents()
    return {"count": len(docs), "policies": docs}


@router.post("/api/v2/copilot/knowledge/index")
async def index_knowledge_policy(payload: dict):
    """Indexes a new custom organization FinOps policy into the vector knowledge base."""
    import uuid as _uuid
    doc_id = payload.get("id") or str(_uuid.uuid4())
    title = payload.get("title")
    content = payload.get("content")
    if not title or not content:
        raise HTTPException(status_code=400, detail="title and content are required")
    category = payload.get("category", "custom-policy")
    tags = payload.get("tags", [])
    vector_knowledge_store.add_document(doc_id=doc_id, title=title, content=content, category=category, tags=tags)
    vector_knowledge_store.save_to_disk()
    return {"status": "success", "indexed_id": doc_id}


@router.get("/api/v2/copilot/rag/cache-stats")
async def get_rag_cache_stats():
    """Returns RAG query cache performance metrics and hit rates."""
    return query_cache.get_stats()


@router.delete("/api/v2/copilot/rag/cache")
async def clear_rag_cache():
    """Clears the RAG query cache."""
    query_cache.clear()
    return {"status": "success", "message": "Query cache cleared"}


@router.get("/api/v2/copilot/status")
@router.get("/api/v1/copilot/status")
async def get_copilot_status():
    """
    Returns active FinOps Copilot status, LLM model cascade, and operational tools.
    """
    engine_ready = copilot_agent.engine and copilot_agent.engine.is_available()
    active_model = getattr(copilot_agent.engine, "active_model", "compound-mini") if copilot_agent.engine else None
    return {
        "status": "ready" if engine_ready else "heuristic_fallback",
        "provider": copilot_agent.provider,
        "active_model": active_model,
        "tools_enabled": ["sql_analytics", "pricing_rag", "cloudtrail_forensics", "terraform_pr", "finops_rag", "vector_knowledge_store"],
        "groq_configured": bool(copilot_agent.groq_api_key),
        "api_endpoints": [
            "/api/v2/copilot/chat",
            "/api/v2/copilot/rag/ask",
            "/api/v2/copilot/rag/recommendations",
            "/api/v2/copilot/rag/status",
            "/api/v2/copilot/rag/cache-stats",
            "/api/v2/copilot/knowledge/search",
            "/api/v2/copilot/knowledge/policies",
            "/api/v2/copilot/diagnose-spike",
            "/api/v2/copilot/generate-iac-pr",
            "/api/v2/copilot/pricing",
            "/api/v2/architect/chat",
        ]
    }


# Standalone Microservice FastAPI App definition
app = FastAPI(
    title="CloudPulse Copilot & System Architect Microservice",
    version="2.0.0",
    description="Autonomous System-1/System-2 FinOps AI agent, SemIf/Jev architect, and RAG knowledge service."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz():
    return {"status": "healthy", "service": "copilot_service", "port": 8001}


app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8001))
    uvicorn.run("microservices.copilot_service:app", host="0.0.0.0", port=port, reload=True)
