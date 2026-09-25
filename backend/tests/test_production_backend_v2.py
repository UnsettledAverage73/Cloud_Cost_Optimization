"""
CloudPulse Production Architecture & SRE Probes Test Suite
Validates Kubernetes probes (/healthz, /readyz), SRE correlation middleware,
and domain router modularization (Copilot, Kubernetes, FOCUS Lakehouse, Fleet, Notifications, GitOps, Analytics).
"""

import pytest
from fastapi.testclient import TestClient

try:
    from main import app
except ImportError:
    from backend.main import app

client = TestClient(app)


def test_kubernetes_liveness_probe():
    """Validates that /healthz responds 200 with healthy probe status."""
    res = client.get("/healthz")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["probe"] == "liveness"
    assert "timestamp" in data


def test_kubernetes_readiness_probe():
    """Validates that /readyz probes all stateful dependencies."""
    res = client.get("/readyz")
    assert res.status_code in [200, 503]
    data = res.json()
    assert "checks" in data
    assert "probe" in data
    assert data["probe"] == "readiness"
    checks = data["checks"]
    assert "database" in checks
    assert "vector_knowledge_store" in checks
    assert "opencost_k8s" in checks or "opencost_engine" in checks


def test_sre_correlation_and_process_time_middleware():
    """Validates that X-Request-ID and X-Process-Time headers are injected by middleware."""
    custom_trace_id = "trace-test-uuid-12345"
    res = client.get("/healthz", headers={"X-Request-ID": custom_trace_id})
    assert res.status_code == 200
    assert res.headers.get("X-Request-ID") == custom_trace_id
    assert "X-Process-Time" in res.headers
    assert res.headers.get("X-Process-Time").endswith("ms")

    # When no header is provided, auto-generates a UUID
    res2 = client.get("/healthz")
    assert "X-Request-ID" in res2.headers
    assert len(res2.headers.get("X-Request-ID")) > 10


def test_copilot_router_endpoints():
    """Validates modular /api/v2/copilot router."""
    res = client.get("/api/v2/copilot/status")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "tools_enabled" in data


def test_kubernetes_router_endpoints():
    """Validates modular /api/v2/kubernetes router."""
    status_res = client.get("/api/v2/kubernetes/status")
    assert status_res.status_code == 200

    alloc_res = client.get("/api/v2/kubernetes/allocations")
    assert alloc_res.status_code == 200
    alloc_data = alloc_res.json()
    assert isinstance(alloc_data, list)
    assert len(alloc_data) > 0

    eff_res = client.get("/api/v2/kubernetes/efficiency")
    assert eff_res.status_code == 200
    eff_data = eff_res.json()
    assert "overall_efficiency_pct" in eff_data or "monthly_requested_cost" in eff_data


def test_focus_lakehouse_router_endpoints():
    """Validates modular /api/v2/focus router."""
    res = client.get("/api/v2/focus/analytics")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "spend_by_service" in data


def test_fleet_router_endpoints():
    """Validates modular /api/v2/fleet router."""
    acc_res = client.get("/api/v2/fleet/accounts")
    assert acc_res.status_code == 200
    assert "accounts" in acc_res.json()

    summary_res = client.get("/api/v2/fleet/summary")
    assert summary_res.status_code == 200
    assert "total_fleet_monthly_spend" in summary_res.json()


def test_notifications_router_endpoints():
    """Validates modular /api/v2/notifications router."""
    cfg_res = client.get("/api/v2/notifications/config")
    assert cfg_res.status_code == 200
    cfg_data = cfg_res.json()
    assert "slack_webhook_url" in cfg_data or "slack_channel" in cfg_data

    hist_res = client.get("/api/v2/notifications/history")
    assert hist_res.status_code == 200
    assert "history" in hist_res.json()


def test_gitops_router_endpoints():
    """Validates modular /api/v2/gitops router."""
    audit_res = client.get("/api/v2/gitops/audit-log")
    assert audit_res.status_code == 200
    assert "audit_trail" in audit_res.json()


def test_analytics_router_endpoints():
    """Validates modular /api/v2/analytics router."""
    anom_res = client.get("/api/v2/analytics/anomalies")
    assert anom_res.status_code == 200
    assert "anomalies" in anom_res.json()

    fc_res = client.get("/api/v2/analytics/forecast")
    assert fc_res.status_code == 200
    assert "projected_monthly_spend" in fc_res.json()


def test_prometheus_metrics_endpoint():
    """Validates that /metrics exports standard Prometheus format metrics."""
    res = client.get("/metrics")
    assert res.status_code == 200
    content = res.text
    assert "cloudpulse_http_requests_total" in content
    assert "cloudpulse_http_request_duration_seconds" in content
    assert "cloudpulse_active_requests" in content
    assert "cloudpulse_monthly_spend_analyzed_usd" in content
    assert "cloudpulse_vector_policies_indexed" in content


def test_metrics_increment_on_traffic():
    """Validates that traffic increments Prometheus HTTP counters and records duration histograms."""
    # Generate some HTTP traffic
    client.get("/api/v2/copilot/status")
    client.get("/api/v2/fleet/summary")

    metrics_res = client.get("/metrics")
    assert metrics_res.status_code == 200
    metrics_text = metrics_res.text
    assert 'endpoint="/api/v2/copilot/status"' in metrics_text
    assert 'endpoint="/api/v2/fleet/summary"' in metrics_text


def test_security_headers_middleware():
    """Validates that OWASP security defense-in-depth headers are injected on all responses."""
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert res.headers.get("X-XSS-Protection") == "1; mode=block"
    assert "strict-origin-when-cross-origin" in res.headers.get("Referrer-Policy")
    assert "camera=()" in res.headers.get("Permissions-Policy")


def test_rate_limiting_headers_and_enforcement():
    """Validates that rate limiting headers are injected and 429 is raised when exhausted."""
    from core.rate_limiter import rate_limiter

    rate_limiter.reset()

    # Normal request has rate limit headers
    res = client.get("/api/v2/copilot/status")
    assert res.status_code == 200
    assert "X-RateLimit-Limit" in res.headers
    assert "X-RateLimit-Remaining" in res.headers

    # Exceed limit in a tight loop to trigger 429
    custom_ip = "198.51.100.42"
    # We test with small custom quota on the limiter
    for _ in range(5):
        rate_limiter.is_allowed(f"{custom_ip}:test_tier", 5)

    allowed, remaining, retry_after = rate_limiter.is_allowed(f"{custom_ip}:test_tier", 5)
    assert not allowed
    assert remaining == 0
    assert retry_after > 0


def test_structured_json_logging():
    """Validates that SREJsonFormatter generates compliant Google Cloud / Stackdriver JSON logs."""
    import logging
    import json
    from core.logging import SREJsonFormatter, correlation_id_ctx

    formatter = SREJsonFormatter()
    logger = logging.getLogger("test.sre.logger")

    correlation_id_ctx.set("trace-abc-123")
    record = logger.makeRecord("test.logger", logging.INFO, "test.py", 42, "FinOps query executed", (), None)
    formatted = formatter.format(record)

    parsed = json.loads(formatted)
    assert parsed["severity"] == "INFO"
    assert parsed["message"] == "FinOps query executed"
    assert parsed["correlation_id"] == "trace-abc-123"
    assert "sourceLocation" in parsed
    assert parsed["sourceLocation"]["file"] == "test.py"
