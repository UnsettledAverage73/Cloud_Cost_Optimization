#!/usr/bin/env python3
"""
CloudPulse Production Test Runner & Health Auditor
Automated integration testing, latency benchmarking, and synthetic verification.
Compatible with standard Python 3 (zero-dependency stdlib fallback).
"""

import sys
import os
import time
import json
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict

# Color codes for terminal reporting
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

@dataclass
class TestResult:
    __test__ = False
    category: str
    name: str
    method: str
    endpoint: str
    status_code: int
    expected_code: int
    elapsed_ms: float
    passed: bool
    summary: str
    error: Optional[str] = None
    response_sample: Optional[str] = None

@dataclass
class TestSuiteReport:
    __test__ = False
    base_url: str
    timestamp: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    success_rate_percent: float
    total_duration_ms: float
    avg_latency_ms: float
    p95_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    results: List[TestResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class CloudPulseTestRunner:
    """Comprehensive test runner for the CloudPulse backend."""

    DEFAULT_BASE_URL = "https://cloud-cost-optimization.onrender.com"

    def __init__(self, base_url: Optional[str] = None, timeout: float = 20.0, verbose: bool = False):
        self.base_url = (base_url or os.getenv("CLOUDPULSE_API_URL", self.DEFAULT_BASE_URL)).rstrip("/")
        self.timeout = timeout
        self.verbose = verbose

    def _execute_request(self, method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = self.base_url + path
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "CloudPulse-AutomatedTester/2.0"
        }
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        start_time = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                raw_bytes = resp.read()
                raw_text = raw_bytes.decode("utf-8", errors="ignore")
                try:
                    json_data = json.loads(raw_text)
                except Exception:
                    json_data = raw_text
                return {
                    "code": resp.getcode(),
                    "elapsed_ms": elapsed_ms,
                    "data": json_data,
                    "raw": raw_text,
                    "error": None
                }
        except urllib.error.HTTPError as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            raw_text = e.read().decode("utf-8", errors="ignore")
            try:
                json_data = json.loads(raw_text)
            except Exception:
                json_data = raw_text
            return {
                "code": e.code,
                "elapsed_ms": elapsed_ms,
                "data": json_data,
                "raw": raw_text,
                "error": f"HTTP {e.code}: {e.reason}"
            }
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return {
                "code": 0,
                "elapsed_ms": elapsed_ms,
                "data": None,
                "raw": "",
                "error": str(e)
            }

    def ensure_environment_ready(self):
        """Enables demo simulation mode if AWS credentials are not actively linked."""
        try:
            res = self._execute_request("POST", "/api/v1/demo/enable")
            if self.verbose:
                print(f"Demo mode initialization: {res.get('code')}")
        except Exception:
            pass

    def run_all_tests(self) -> TestSuiteReport:
        """Executes the complete test suite and returns structured results."""
        self.ensure_environment_ready()

        test_cases = [
            # 1. Database & TimescaleDB Infrastructure
            {
                "category": "Infrastructure & Storage",
                "name": "PostgreSQL & TimescaleDB Health Check",
                "method": "GET",
                "path": "/api/v2/database/status",
                "body": None,
                "expected_code": 200,
                "validator": lambda d: d.get("status") == "connected" and "postgres_version" in d
            },
            {
                "category": "Infrastructure & Storage",
                "name": "TimescaleDB Hypertable Telemetry Query",
                "method": "GET",
                "path": "/api/v2/telemetry/hypertable?limit=25",
                "body": None,
                "expected_code": 200,
                "validator": lambda d: "telemetry" in d and isinstance(d["telemetry"], list)
            },

            # 2. Multi-Cloud Spend & FOCUS 1.0
            {
                "category": "Spend & Billing",
                "name": "FOCUS 1.0 Normalized Cost Data",
                "method": "GET",
                "path": "/api/v2/focus/spend",
                "body": None,
                "expected_code": 200,
                "validator": lambda d: d.get("specification") == "FOCUS 1.0" and "summary" in d
            },
            {
                "category": "Spend & Billing",
                "name": "Multi-Cloud Historical Daily Spend",
                "method": "GET",
                "path": "/api/spend",
                "body": None,
                "expected_code": 200,
                "validator": lambda d: isinstance(d, list) and len(d) > 0
            },

            # 3. Customer Onboarding & CloudFormation
            {
                "category": "Customer Onboarding",
                "name": "1-Click CloudFormation Package Generator",
                "method": "GET",
                "path": "/api/v2/onboarding/cloudformation?allow_remediation=true",
                "body": None,
                "expected_code": 200,
                "validator": lambda d: "external_id" in d and "quick_create_url" in d and "template_yaml" in d
            },
            {
                "category": "Customer Onboarding",
                "name": "Connected AWS Accounts Listing",
                "method": "GET",
                "path": "/api/v2/onboarding/accounts",
                "body": None,
                "expected_code": 200,
                "validator": lambda d: "accounts" in d and isinstance(d["accounts"], list)
            },

            # 4. Multi-OS Telemetry Agent Pipeline
            {
                "category": "Multi-OS Agent",
                "name": "Linux Bash 1-Liner Script Generator",
                "method": "GET",
                "path": "/api/v2/agent/install-script?os=linux",
                "body": None,
                "expected_code": 200,
                "validator": lambda d: isinstance(d, str) and "#!/usr/bin/env bash" in d
            },
            {
                "category": "Multi-OS Agent",
                "name": "Windows PowerShell 1-Liner Script Generator",
                "method": "GET",
                "path": "/api/v2/agent/install-script?os=windows",
                "body": None,
                "expected_code": 200,
                "validator": lambda d: isinstance(d, str) and "CloudPulse Multi-OS Windows Agent" in d
            },
            {
                "category": "Multi-OS Agent",
                "name": "In-Guest Telemetry Ingestion (RAM/CPU/Processes)",
                "method": "POST",
                "path": "/api/v2/agent/ingest",
                "body": {
                    "host_id": "synthetic-test-node-01",
                    "hostname": "prod-synthetics-worker",
                    "os": "Linux",
                    "os_family": "linux",
                    "metrics": {
                        "cpu_percent": 12.4,
                        "memory_percent": 38.5,
                        "memory_total_mb": 16384,
                        "memory_used_mb": 6307,
                        "disk_percent": 41.2
                    },
                    "cloud": {"provider": "aws", "instance_type": "m5.xlarge", "region": "us-east-1"},
                    "top_processes": [{"pid": 801, "name": "uvicorn", "cpu_percent": 3.2, "memory_percent": 5.1}]
                },
                "expected_code": 200,
                "validator": lambda d: d.get("status") == "ingested"
            },
            {
                "category": "Multi-OS Agent",
                "name": "Active Agent Hosts Discovery",
                "method": "GET",
                "path": "/api/v2/agent/hosts",
                "body": None,
                "expected_code": 200,
                "validator": lambda d: "hosts" in d and isinstance(d["hosts"], list)
            },

            # 5. Autonomous FinOps AI Copilot
            {
                "category": "Autonomous AI Copilot",
                "name": "AI Copilot Natural Language Advisory",
                "method": "POST",
                "path": "/api/v2/copilot/chat",
                "body": {
                    "prompt": "What are our largest areas of cloud waste and recommended immediate actions?",
                    "history": []
                },
                "expected_code": 200,
                "validator": lambda d: "answer" in d and len(d["answer"]) > 10
            },
            {
                "category": "Autonomous AI Copilot",
                "name": "Automated CloudTrail & Spend Spike Diagnosis",
                "method": "POST",
                "path": "/api/v2/copilot/diagnose-spike",
                "body": {
                    "service": "Amazon EC2",
                    "spike_date": "2026-09-18"
                },
                "expected_code": 200,
                "validator": lambda d: "forensics" in d
            },
            {
                "category": "Autonomous AI Copilot",
                "name": "Terraform / OpenTofu Remediation PR Generator",
                "method": "POST",
                "path": "/api/v2/copilot/generate-iac-pr",
                "body": {
                    "resource_id": "i-036358db85d245e3a",
                    "action": "rightsize",
                    "from_type": "m5.2xlarge",
                    "to_type": "m6g.xlarge"
                },
                "expected_code": 200,
                "validator": lambda d: "hcl_after" in d and "commit_title" in d
            },
            {
                "category": "Autonomous AI Copilot",
                "name": "Real-time AWS Pricing & Graviton RAG Catalog",
                "method": "GET",
                "path": "/api/v2/copilot/pricing?service=ec2&instance_type=t3.large",
                "body": None,
                "expected_code": 200,
                "validator": lambda d: d.get("found") is True or "hourly_rate" in d or "resource_type" in d
            },

            # 6. Core Inventory & Telemetry
            {
                "category": "Inventory & Telemetry",
                "name": "Compute Nodes Inventory",
                "method": "GET",
                "path": "/api/nodes",
                "body": None,
                "expected_code": 200,
                "validator": lambda d: isinstance(d, list)
            },
            {
                "category": "Inventory & Telemetry",
                "name": "Real-Time Telemetry Stream",
                "method": "GET",
                "path": "/api/telemetry",
                "body": None,
                "expected_code": 200,
                "validator": lambda d: isinstance(d, list)
            },
            {
                "category": "Inventory & Telemetry",
                "name": "Dashboard Aggregated Summary",
                "method": "GET",
                "path": "/api/v1/dashboard/summary",
                "body": None,
                "expected_code": 200,
                "validator": lambda d: "monthly_spend" in d and "wasted_monthly_spend" in d
            },
            {
                "category": "Inventory & Telemetry",
                "name": "Resource Inventory Deep Inspection",
                "method": "GET",
                "path": "/api/v1/resources/inventory",
                "body": None,
                "expected_code": 200,
                "validator": lambda d: "inventory" in d or "metadata" in d
            },

            # 7. FinOps Analytics Engines
            {
                "category": "FinOps Analytics",
                "name": "FinOps Health Score & Pillar Grading",
                "method": "GET",
                "path": "/api/v1/analytics/health-score",
                "body": None,
                "expected_code": 200,
                "validator": lambda d: "overall_health_score" in d and "pillars" in d
            },
            {
                "category": "FinOps Analytics",
                "name": "Predictive Spend Forecasting",
                "method": "GET",
                "path": "/api/v1/analytics/forecast",
                "body": None,
                "expected_code": 200,
                "validator": lambda d: "projected_month_end" in d and "monthly_budget" in d
            },
            {
                "category": "FinOps Analytics",
                "name": "Z-Score Cost Anomaly Detector",
                "method": "GET",
                "path": "/api/v1/analytics/anomalies",
                "body": None,
                "expected_code": 200,
                "validator": lambda d: "anomalies" in d and isinstance(d["anomalies"], list)
            },
            {
                "category": "FinOps Analytics",
                "name": "Active Waste & Optimization Recommendations",
                "method": "GET",
                "path": "/api/optimizations",
                "body": None,
                "expected_code": 200,
                "validator": lambda d: isinstance(d, list)
            },

            # 8. Remediation & Slash Commands
            {
                "category": "Remediation & Commands",
                "name": "Remediation Safety Audit Ledger",
                "method": "GET",
                "path": "/api/v1/remediate/audit",
                "body": None,
                "expected_code": 200,
                "validator": lambda d: "audit_logs" in d
            },
            {
                "category": "Remediation & Commands",
                "name": "Autonomous Slash Command: /optimize",
                "method": "POST",
                "path": "/api/v1/agent/chat",
                "body": {"query": "/optimize"},
                "expected_code": 200,
                "validator": lambda d: d.get("command") == "/optimize" and "quick_wins" in d
            },
            {
                "category": "Remediation & Commands",
                "name": "Autonomous Slash Command: /health",
                "method": "POST",
                "path": "/api/v1/agent/chat",
                "body": {"query": "/health"},
                "expected_code": 200,
                "validator": lambda d: d.get("command") == "/health" and "data" in d
            }
        ]

        results: List[TestResult] = []
        latencies: List[float] = []
        suite_start = time.perf_counter()

        for tc in test_cases:
            res = self._execute_request(tc["method"], tc["path"], tc["body"])
            code = res["code"]
            elapsed = res["elapsed_ms"]
            latencies.append(elapsed)

            data = res["data"]
            is_code_ok = (code == tc["expected_code"])
            custom_ok = True
            error_detail = res["error"]

            if is_code_ok:
                try:
                    custom_ok = tc["validator"](data)
                    if not custom_ok:
                        error_detail = "Response JSON did not satisfy schema validator"
                except Exception as e:
                    custom_ok = False
                    error_detail = f"Validator error: {e}"

            passed = is_code_ok and custom_ok

            raw_sample = str(data if data is not None else res["raw"])
            sample_clean = (raw_sample[:100] + "...") if len(raw_sample) > 100 else raw_sample

            summary = f"{code} OK" if passed else (error_detail or f"Expected {tc['expected_code']}, got {code}")

            result = TestResult(
                category=tc["category"],
                name=tc["name"],
                method=tc["method"],
                endpoint=tc["path"],
                status_code=code,
                expected_code=tc["expected_code"],
                elapsed_ms=round(elapsed, 2),
                passed=passed,
                summary=summary,
                error=error_detail if not passed else None,
                response_sample=sample_clean
            )
            results.append(result)

        total_duration_ms = (time.perf_counter() - suite_start) * 1000.0
        passed_count = sum(1 for r in results if r.passed)
        failed_count = len(results) - passed_count
        success_rate = (passed_count / len(results) * 100.0) if results else 0.0

        latencies_sorted = sorted(latencies)
        p95_idx = int(len(latencies_sorted) * 0.95)
        p95_latency = latencies_sorted[p95_idx] if latencies_sorted else 0.0
        avg_latency = (sum(latencies) / len(latencies)) if latencies else 0.0
        min_latency = latencies_sorted[0] if latencies_sorted else 0.0
        max_latency = latencies_sorted[-1] if latencies_sorted else 0.0

        return TestSuiteReport(
            base_url=self.base_url,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            total_tests=len(results),
            passed_tests=passed_count,
            failed_tests=failed_count,
            success_rate_percent=round(success_rate, 2),
            total_duration_ms=round(total_duration_ms, 2),
            avg_latency_ms=round(avg_latency, 2),
            p95_latency_ms=round(p95_latency, 2),
            min_latency_ms=round(min_latency, 2),
            max_latency_ms=round(max_latency, 2),
            results=results
        )

    def print_terminal_report(self, report: TestSuiteReport):
        """Renders an attractive, high-contrast terminal report."""
        print(f"\n{BOLD}{CYAN}{'=' * 80}{RESET}")
        print(f"{BOLD}{CYAN} 🚀 CLOUDPULSE BACKEND HEALTH & SYNTHETIC TEST SUITE{RESET}")
        print(f"{BOLD}{CYAN}{'=' * 80}{RESET}")
        print(f"  • Target Backend URL : {BOLD}{report.base_url}{RESET}")
        print(f"  • Run Timestamp      : {report.timestamp}")
        print(f"  • Latency Profile    : Avg {report.avg_latency_ms}ms | p95 {report.p95_latency_ms}ms | Min {report.min_latency_ms}ms | Max {report.max_latency_ms}ms")
        print(f"  • Total Duration     : {round(report.total_duration_ms / 1000.0, 2)}s")
        print("-" * 80)

        current_category = None
        for r in report.results:
            if r.category != current_category:
                current_category = r.category
                print(f"\n{BOLD}📂 {current_category.upper()}{RESET}")
                print(f"  {'STATUS':<7} {'METHOD':<6} {'LATENCY':<9} {'TEST NAME':<38} {'SUMMARY'}")
                print("  " + "-" * 76)

            badge = f"{GREEN}[PASS]{RESET}" if r.passed else f"{RED}[FAIL]{RESET}"
            method_badge = f"{CYAN}{r.method:<6}{RESET}"
            latency_str = f"{r.elapsed_ms:>6.1f}ms"
            test_name = (r.name[:36] + "..") if len(r.name) > 38 else r.name
            summary = r.summary[:30]
            print(f"  {badge}  {method_badge} {latency_str:<9} {test_name:<38} {summary}")

        print("\n" + "=" * 80)
        status_color = GREEN if report.failed_tests == 0 else RED
        print(f"{BOLD}📊 TEST SUITE SUMMARY: {status_color}{report.passed_tests}/{report.total_tests} PASSED ({report.success_rate_percent}%){RESET}")
        if report.failed_tests > 0:
            print(f"{RED}⚠️  {report.failed_tests} tests failed. Check endpoint logs for details.{RESET}")
        else:
            print(f"{GREEN}🎉 All backend endpoints, databases, and AI engines verified healthy!{RESET}")
        print("=" * 80 + "\n")

    def generate_html_report(self, report: TestSuiteReport, output_path: str):
        """Generates a standalone, beautiful HTML dashboard report."""
        rows_html = []
        for r in report.results:
            badge_class = "badge-pass" if r.passed else "badge-fail"
            badge_text = "PASSED" if r.passed else "FAILED"
            sample_escaped = (r.response_sample or "").replace("<", "&lt;").replace(">", "&gt;")
            rows_html.append(f"""
            <tr>
                <td><span class="badge {badge_class}">{badge_text}</span></td>
                <td><span class="category-tag">{r.category}</span></td>
                <td><strong>{r.name}</strong><br/><small class="text-muted">{r.endpoint}</small></td>
                <td><code>{r.method}</code></td>
                <td>{r.elapsed_ms} ms</td>
                <td>{r.status_code}</td>
                <td><div class="sample-box">{sample_escaped}</div></td>
            </tr>
            """)

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CloudPulse Backend Test Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #0f172a;
            color: #f8fafc;
            margin: 0;
            padding: 30px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #334155;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        h1 {{
            margin: 0;
            font-size: 26px;
            color: #38bdf8;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .metric-card {{
            background: #1e293b;
            border-radius: 8px;
            padding: 20px;
            border: 1px solid #334155;
        }}
        .metric-value {{
            font-size: 30px;
            font-weight: bold;
            color: #f8fafc;
            margin-top: 5px;
        }}
        .metric-label {{
            font-size: 13px;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: #1e293b;
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid #334155;
        }}
        th, td {{
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid #334155;
            font-size: 14px;
        }}
        th {{
            background: #0f172a;
            color: #94a3b8;
            font-weight: 600;
        }}
        tr:hover {{
            background: #253349;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 700;
        }}
        .badge-pass {{
            background: #065f46;
            color: #34d399;
        }}
        .badge-fail {{
            background: #881337;
            color: #f87171;
        }}
        .category-tag {{
            background: #334155;
            color: #93c5fd;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 12px;
        }}
        .sample-box {{
            max-width: 320px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            font-family: monospace;
            font-size: 12px;
            color: #cbd5e1;
        }}
        .text-muted {{
            color: #64748b;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>CloudPulse Production Health & Test Suite</h1>
                <p class="text-muted" style="margin: 5px 0 0 0;">Target: {report.base_url} • {report.timestamp}</p>
            </div>
            <div>
                <span class="badge {'badge-pass' if report.failed_tests == 0 else 'badge-fail'}" style="font-size: 16px; padding: 8px 16px;">
                    {report.passed_tests} / {report.total_tests} PASSED ({report.success_rate_percent}%)
                </span>
            </div>
        </div>

        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">Pass Rate</div>
                <div class="metric-value" style="color: {'#34d399' if report.failed_tests == 0 else '#f87171'};">{report.success_rate_percent}%</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Avg Response Time</div>
                <div class="metric-value">{report.avg_latency_ms} ms</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">95th Percentile (p95)</div>
                <div class="metric-value">{report.p95_latency_ms} ms</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Total Suite Duration</div>
                <div class="metric-value">{round(report.total_duration_ms / 1000.0, 2)} s</div>
            </div>
        </div>

        <table>
            <thead>
                <tr>
                    <th>Status</th>
                    <th>Category</th>
                    <th>Test Name & Endpoint</th>
                    <th>Method</th>
                    <th>Latency</th>
                    <th>HTTP Code</th>
                    <th>Response Sample</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows_html)}
            </tbody>
        </table>
    </div>
</body>
</html>
"""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"📄 HTML test report successfully saved to: {output_path}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="CloudPulse Automated Backend Testing & Diagnostics Tool")
    parser.add_argument("url", nargs="?", default=None, help="Backend URL (default: Render production or local)")
    parser.add_argument("--json", dest="json_file", default=None, help="Export results to a JSON file")
    parser.add_argument("--html", dest="html_file", default=None, help="Export results to an interactive HTML report")
    parser.add_argument("--timeout", type=float, default=20.0, help="Per-request timeout in seconds (default: 20)")
    parser.add_argument("--verbose", action="store_true", help="Print verbose logs")
    args = parser.parse_args()

    runner = CloudPulseTestRunner(base_url=args.url, timeout=args.timeout, verbose=args.verbose)
    report = runner.run_all_tests()
    runner.print_terminal_report(report)

    if args.json_file:
        with open(args.json_file, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)
        print(f"📄 JSON report saved to: {args.json_file}")

    if args.html_file:
        runner.generate_html_report(report, args.html_file)

    if report.failed_tests > 0:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
