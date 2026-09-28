"""
Unit & Integration Test Suite for In-Process Vector PDF Dossier Engine (Engine 6)
"""

import time
import pytest
from fastapi.testclient import TestClient

from engines.pdf_dossier_engine import pdf_dossier_engine
from main import app

client = TestClient(app)


def test_pdf_engine_generates_all_four_report_types():
    """Verifies that all 4 enterprise persona reports generate valid PDF binary streams."""
    report_types = ["executive", "engineering", "security_hygiene", "telemetry_snapshot"]

    sample_inventory = {
        "metadata": {"account_id": "111122223333", "account_name": "Prod-Payments-Fleet"},
        "summary": {"estimated_monthly_spend": 54200.0},
        "compute": {
            "nodes": [
                {"instance_id": "i-09f1a23c4d5e6789a", "name": "checkout-01", "cost": 277.40, "cpu_utilization": 12.1, "state": "running"},
                {"instance_id": "i-09f1a23c4d5e6789b", "name": "checkout-02", "cost": 277.40, "cpu_utilization": 8.4, "state": "running"}
            ]
        }
    }

    for rtype in report_types:
        t0 = time.perf_counter()
        stream = pdf_dossier_engine.build_pdf_stream(
            report_type=rtype,
            inventory=sample_inventory,
            account_id="111122223333",
            currency="USD"
        )
        latency_ms = (time.perf_counter() - t0) * 1000
        content = stream.getvalue()

        # 1. Valid PDF Magic Header
        assert content.startswith(b"%PDF-"), f"Report {rtype} failed PDF magic header check"
        # 2. Non-trivial file size (> 2KB)
        assert len(content) > 2048, f"Report {rtype} is too small: {len(content)} bytes"
        # 3. Low latency execution (< 250ms even on constrained CI CPU)
        assert latency_ms < 250.0, f"Report {rtype} latency exceeded threshold: {latency_ms}ms"


def test_pdf_engine_dual_currency_inr():
    """Verifies formatting with INR (Indian Rupees) dual currency."""
    stream = pdf_dossier_engine.build_pdf_stream(
        report_type="executive",
        currency="INR"
    )
    content = stream.getvalue()
    assert content.startswith(b"%PDF-")
    assert len(content) > 2048


def test_api_v2_reports_catalog_endpoint():
    """Verifies metadata catalog endpoint returns all 4 reports."""
    res = client.get("/api/v2/reports/catalog")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert len(data["catalog"]) == 4
    ids = [c["id"] for c in data["catalog"]]
    assert "executive" in ids
    assert "engineering" in ids
    assert "security_hygiene" in ids
    assert "telemetry_snapshot" in ids


def test_api_v2_reports_pdf_streaming_endpoint():
    """Verifies HTTP streaming endpoint delivers proper headers and binary PDF."""
    for rtype in ["executive", "engineering", "security_hygiene", "telemetry_snapshot"]:
        res = client.get(f"/api/v2/reports/pdf?report_type={rtype}&currency=USD")
        assert res.status_code == 200
        assert res.headers["content-type"] == "application/pdf"
        assert "X-Render-Latency-Ms" in res.headers
        assert res.headers["X-Report-Type"] == rtype
        assert res.content.startswith(b"%PDF-")


def test_legacy_pov_pdf_endpoint_compatibility():
    """Verifies that legacy /api/v2/analytics/pov/report.pdf uses vector engine without errors."""
    res = client.get("/api/v2/analytics/pov/report.pdf")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content.startswith(b"%PDF-")
