import pytest
from unittest.mock import patch, MagicMock
from testing.runner import CloudPulseTestRunner, TestResult, TestSuiteReport
from cli_main import load_config, save_config, get_backend_url, main
import json

def test_test_runner_initialization():
    runner = CloudPulseTestRunner(base_url="https://test-backend.internal", timeout=12.0)
    assert runner.base_url == "https://test-backend.internal"
    assert runner.timeout == 12.0

def test_test_runner_report_structure():
    results = [
        TestResult(
            category="Infrastructure",
            name="DB Ping",
            method="GET",
            endpoint="/api/v2/database/status",
            status_code=200,
            expected_code=200,
            elapsed_ms=120.0,
            passed=True,
            summary="200 OK"
        ),
        TestResult(
            category="Billing",
            name="FOCUS Spend",
            method="GET",
            endpoint="/api/v2/focus/spend",
            status_code=200,
            expected_code=200,
            elapsed_ms=180.0,
            passed=True,
            summary="200 OK"
        )
    ]
    report = TestSuiteReport(
        base_url="https://test-backend.internal",
        timestamp="2026-09-18 15:30:00 UTC",
        total_tests=2,
        passed_tests=2,
        failed_tests=0,
        success_rate_percent=100.0,
        total_duration_ms=300.0,
        avg_latency_ms=150.0,
        p95_latency_ms=180.0,
        min_latency_ms=120.0,
        max_latency_ms=180.0,
        results=results
    )
    report_dict = report.to_dict()
    assert report_dict["passed_tests"] == 2
    assert report_dict["failed_tests"] == 0
    assert report_dict["success_rate_percent"] == 100.0
    assert len(report_dict["results"]) == 2

def test_cli_config_management(tmp_path):
    with patch("cli_main.CONFIG_FILE", tmp_path / "config.json"), \
         patch("cli_main.CONFIG_DIR", tmp_path):
        save_config({"backend_url": "https://custom-cloudpulse.com"})
        conf = load_config()
        assert conf.get("backend_url") == "https://custom-cloudpulse.com"
        url = get_backend_url()
        assert url == "https://custom-cloudpulse.com"

def test_cli_override_url():
    url = get_backend_url("https://override-url.com/")
    assert url == "https://override-url.com"

def test_test_runner_html_generation(tmp_path):
    runner = CloudPulseTestRunner(base_url="https://test.internal")
    results = [
        TestResult(
            category="AI",
            name="Copilot Chat",
            method="POST",
            endpoint="/api/v2/copilot/chat",
            status_code=200,
            expected_code=200,
            elapsed_ms=45.0,
            passed=True,
            summary="200 OK",
            response_sample="Hello from copilot"
        )
    ]
    report = TestSuiteReport(
        base_url="https://test.internal",
        timestamp="2026-09-18 15:30:00 UTC",
        total_tests=1,
        passed_tests=1,
        failed_tests=0,
        success_rate_percent=100.0,
        total_duration_ms=45.0,
        avg_latency_ms=45.0,
        p95_latency_ms=45.0,
        min_latency_ms=45.0,
        max_latency_ms=45.0,
        results=results
    )
    html_file = tmp_path / "report.html"
    runner.generate_html_report(report, str(html_file))
    assert html_file.exists()
    content = html_file.read_text()
    assert "CloudPulse Production Health & Test Suite" in content
    assert "Copilot Chat" in content
