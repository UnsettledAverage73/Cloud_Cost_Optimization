import requests
import json
import time

BASE_URL = "http://localhost:8000"

endpoints = [
    ("GET", "/api/v2/database/status", None),
    ("GET", "/api/v2/onboarding/cloudformation?allow_remediation=true", None),
    ("GET", "/api/v2/onboarding/accounts", None),
    ("POST", "/api/v2/onboarding/accounts", {
        "account_id": "112233445566",
        "account_name": "Analytics Cluster Prod",
        "role_arn": "arn:aws:iam::112233445566:role/CloudPulseAnalyticsRole",
        "external_id": "cp-ext-analytics-1122",
        "regions": ["us-east-1", "us-west-2"]
    }),
    ("GET", "/api/v2/telemetry/hypertable?limit=5", None),
    ("GET", "/api/v2/focus/spend?limit=5", None),
    ("POST", "/api/v2/copilot/chat", {"message": "Show spend breakdown by service"}),
    ("POST", "/api/v2/copilot/chat", {"message": "Compare m5.2xlarge with Graviton pricing"}),
    ("POST", "/api/v2/copilot/chat", {"message": "Why did we have a spike in cloud spend?"}),
    ("POST", "/api/v2/copilot/chat", {"message": "Generate a terraform pr to fix idle compute"}),
    ("POST", "/api/v2/copilot/diagnose-spike", {"service": "AmazonEC2"}),
    ("POST", "/api/v2/copilot/generate-iac-pr", {
        "finding_id": "find-m5-downsize",
        "resource_id": "i-09f81a2b3c4d5e6f7",
        "action_type": "downsize_ec2",
        "monthly_savings": 243.80
    }),
    ("GET", "/api/v2/copilot/pricing?resource_type=m5.2xlarge", None),
]

print("=" * 80)
print("🚀 TESTING LIVE CLOUDPULSE V2 ENTERPRISE API ENDPOINTS")
print("=" * 80)

all_passed = True
results = []

for method, path, payload in endpoints:
    url = f"{BASE_URL}{path}"
    start = time.perf_counter()
    try:
        if method == "GET":
            r = requests.get(url, timeout=5)
        else:
            r = requests.post(url, json=payload, timeout=5)
        latency_ms = (time.perf_counter() - start) * 1000
        status_ok = (r.status_code == 200)
        if not status_ok:
            all_passed = False
        
        status_str = "✅ PASS" if status_ok else f"❌ FAIL ({r.status_code})"
        print(f"{status_str} | {method:4} {path[:45]:45} | {r.status_code} | {latency_ms:.1f}ms")
        
        results.append({
            "method": method,
            "path": path,
            "status_code": r.status_code,
            "latency_ms": round(latency_ms, 2),
            "response_snippet": str(r.json())[:120] if status_ok else r.text[:120]
        })
    except Exception as e:
        all_passed = False
        print(f"❌ ERROR | {method:4} {path[:45]:45} | EXCEPTION: {e}")

print("=" * 80)
print(f"All V2 endpoints passed: {all_passed}")

with open("scratch/v2_test_results.json", "w") as f:
    json.dump(results, f, indent=2)
