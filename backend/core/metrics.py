"""
CloudPulse Production Observability & Prometheus Metrics Engine
Standard Google SRE Prometheus counters, gauges, histograms, and OpenTelemetry instrumentation.
"""

import time
import logging
from typing import Dict, Any, Optional
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    REGISTRY
)

logger = logging.getLogger("cloudpulse.sre.metrics")

# Default Prometheus HTTP metrics
HTTP_REQUESTS_TOTAL = Counter(
    "cloudpulse_http_requests_total",
    "Total incoming HTTP requests processed by CloudPulse backend",
    ["method", "endpoint", "status"]
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "cloudpulse_http_request_duration_seconds",
    "Wall-clock HTTP request processing duration in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)

ACTIVE_REQUESTS = Gauge(
    "cloudpulse_active_requests",
    "Number of active concurrent requests currently being processed"
)

# FinOps Domain Metrics
MONTHLY_SPEND_ANALYZED = Gauge(
    "cloudpulse_monthly_spend_analyzed_usd",
    "Total annualized/monthly cloud infrastructure spend analyzed by FinOps engine"
)

POTENTIAL_SAVINGS_IDENTIFIED = Gauge(
    "cloudpulse_potential_savings_identified_usd",
    "Total potential monthly waste/idle savings identified across all vectors"
)

REMEDIATIONS_EXECUTED_TOTAL = Counter(
    "cloudpulse_remediations_executed_total",
    "Total automated or manual FinOps remediations executed",
    ["action_type", "environment"]
)

KUBERNETES_WORKLOADS_MONITORED = Gauge(
    "cloudpulse_k8s_workloads_monitored",
    "Count of active Kubernetes pods and containers tracked via CNCF OpenCost"
)

FOCUS_RECORDS_INDEXED = Gauge(
    "cloudpulse_focus_records_indexed",
    "Count of FOCUS 1.0 specification cost records indexed in DuckDB Lakehouse"
)

VECTOR_POLICIES_INDEXED = Gauge(
    "cloudpulse_vector_policies_indexed",
    "Count of Well-Architected and FinOps policies active in semantic vector store"
)


def get_prometheus_metrics() -> bytes:
    """Serializes all registered metrics into Prometheus exposition text format."""
    return generate_latest(REGISTRY)


def record_request_metric(method: str, endpoint: str, status_code: int, duration_seconds: float):
    """Utility invoked by SRE middleware on each completed request."""
    # Normalize paths with path params to prevent metric cardinality explosion
    norm_endpoint = _normalize_endpoint(endpoint)
    HTTP_REQUESTS_TOTAL.labels(method=method, endpoint=norm_endpoint, status=str(status_code)).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(method=method, endpoint=norm_endpoint).observe(duration_seconds)


def sync_domain_gauges(inventory: Optional[Dict[str, Any]] = None):
    """Synchronizes live domain gauges with current system state."""
    try:
        from core.state import get_realtime_store
        from services.vector_store import vector_knowledge_store
        from services.opencost_engine import opencost_engine
        from engines.focus_lakehouse import focus_lakehouse
    except ImportError:
        try:
            from backend.core.state import get_realtime_store
            from backend.services.vector_store import vector_knowledge_store
            from backend.services.opencost_engine import opencost_engine
            from backend.engines.focus_lakehouse import focus_lakehouse
        except ImportError:
            return

    inv = inventory or get_realtime_store()
    nodes = inv.get("nodes", [])
    spend = sum(float(n.get("cost", 7.60)) for n in nodes)
    MONTHLY_SPEND_ANALYZED.set(round(spend, 2))

    # Vector policies
    if vector_knowledge_store:
        try:
            VECTOR_POLICIES_INDEXED.set(len(vector_knowledge_store.get_all_documents()))
        except Exception:
            pass

    # OpenCost workloads
    if opencost_engine:
        try:
            KUBERNETES_WORKLOADS_MONITORED.set(len(getattr(opencost_engine, "workloads", [])))
        except Exception:
            pass

    # FOCUS records
    if focus_lakehouse:
        try:
            row = focus_lakehouse.conn.execute("SELECT COUNT(*) FROM focus_costs").fetchone()
            if row:
                FOCUS_RECORDS_INDEXED.set(row[0])
        except Exception:
            pass


def _normalize_endpoint(path: str) -> str:
    """Collapses dynamic IDs in URL paths to keep metric cardinality low."""
    if not path:
        return "/"
    parts = path.strip("/").split("/")
    norm_parts = []
    for p in parts:
        # Check if segment looks like an ID, UUID, or AWS resource
        if any([
            p.startswith(("i-", "vol-", "snap-", "vpc-", "eipalloc-", "sg-", "watch-")),
            len(p) > 24 and any(c.isdigit() for c in p),
            p.isdigit()
        ]):
            norm_parts.append("{id}")
        else:
            norm_parts.append(p)
    return "/" + "/".join(norm_parts)
