#!/usr/bin/env python3
"""
CloudPulse Enterprise CLI & Testing Tool
Unified command-line interface for FinOps practitioners, developers, and DevOps teams.
Supports complete backend testing, in-guest scanning, AI Copilot chat, and cloud cost auditing.
"""

import sys
import os
import time
import json
import argparse
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, Optional

# Ensure parent and backend paths are importable
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
for p in [CURRENT_DIR, ROOT_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from agent.collector import MultiOSCollector
    from agent.cloud_detector import CloudInstanceDetector
    from testing.runner import CloudPulseTestRunner
except ImportError:
    try:
        from backend.agent.collector import MultiOSCollector
        from backend.agent.cloud_detector import CloudInstanceDetector
        from backend.testing.runner import CloudPulseTestRunner
    except ImportError:
        # Fallback if testing or agent is relative
        from .agent.collector import MultiOSCollector
        from .agent.cloud_detector import CloudInstanceDetector
        from .testing.runner import CloudPulseTestRunner

CONFIG_DIR = Path.home() / ".cloudpulse"
CONFIG_FILE = CONFIG_DIR / "config.json"
DEFAULT_BACKEND_URL = "https://cloud-cost-optimization.onrender.com"

# Terminal formatting
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
RESET = "\033[0m"

def load_config() -> Dict[str, Any]:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"backend_url": DEFAULT_BACKEND_URL}

def save_config(conf: Dict[str, Any]):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(conf, f, indent=2)

def get_backend_url(override: Optional[str] = None) -> str:
    if override:
        return override.rstrip("/")
    if os.getenv("CLOUDPULSE_API_URL"):
        return os.environ["CLOUDPULSE_API_URL"].rstrip("/")
    conf = load_config()
    return conf.get("backend_url", DEFAULT_BACKEND_URL).rstrip("/")

def print_banner():
    print(rf"""{CYAN}{BOLD}
   ____ _                 _ ____        _           
  / ___| | ___  _   _  __| |  _ \ _   _| |___  ___  
 | |   | |/ _ \| | | |/ _` | |_) | | | | / __|/ _ \ 
 | |___| | (_) | |_| | (_| |  __/| |_| | \__ \  __/ 
  \____|_|\___/ \__,_|\__,_|_|    \__,_|_|___/\___| 
    Enterprise FinOps, Multi-OS Agent & Testing CLI{RESET}
""")

def http_json(url: str, method: str = "GET", payload: Optional[Dict[str, Any]] = None, timeout: float = 15.0) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload else None
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "CloudPulse-CLI/2.0"
    }
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

# ==========================================
# COMMAND: test
# ==========================================
def cmd_test(args):
    target_url = get_backend_url(args.url)
    runner = CloudPulseTestRunner(base_url=target_url, timeout=args.timeout, verbose=args.verbose)
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

# ==========================================
# COMMAND: status
# ==========================================
def cmd_status(args):
    print_banner()
    backend_url = get_backend_url(args.url)
    print(f"🔗 Target Backend: {BOLD}{backend_url}{RESET}\n")

    # 1. Backend & Database Status
    try:
        db_status = http_json(f"{backend_url}/api/v2/database/status")
        pg_ver = db_status.get("postgres_version", "Unknown")[:40]
        ts_ver = db_status.get("timescaledb_version", "None")
        print(f"{GREEN}● Backend Connected:{RESET}")
        print(f"  • PostgreSQL       : {pg_ver}...")
        print(f"  • TimescaleDB      : {ts_ver}")
    except Exception as e:
        print(f"{RED}✖ Backend Connection Failed:{RESET} {e}")

    # 2. Connected Accounts
    try:
        acc_resp = http_json(f"{backend_url}/api/v2/onboarding/accounts")
        accounts = acc_resp.get("accounts", [])
        print(f"\n{BOLD}🏢 Connected Cloud Accounts ({len(accounts)}):{RESET}")
        for acc in accounts:
            print(f"  • {acc.get('account_name')} (ID: {acc.get('account_id')}) - Regions: {', '.join(acc.get('regions', []))}")
    except Exception:
        pass

    # 3. Local Machine & Cloud Host Detection
    cloud_info = CloudInstanceDetector.detect()
    telemetry = MultiOSCollector.collect_full_telemetry()
    os_info = telemetry["os"]
    cpu = telemetry["cpu"]
    mem = telemetry["memory"]

    print(f"\n{BOLD}🖥️ Local Host Specs:{RESET}")
    print(f"  • Provider         : {cloud_info['provider'].upper()} ({cloud_info['instance_type']})")
    print(f"  • OS / Arch        : {os_info['system']} {os_info['release']} ({os_info['architecture']})")
    print(f"  • Hostname         : {os_info['hostname']}")
    print(f"  • In-Guest CPU     : {cpu['utilization_percent']}% across {cpu['logical_cores']} cores")
    print(f"  • In-Guest Memory  : {mem['used_mb']} MB / {mem['total_mb']} MB ({mem['percent_used']}% used)")
    print()

# ==========================================
# COMMAND: audit
# ==========================================
def cmd_audit(args):
    print_banner()
    backend_url = get_backend_url(args.url)
    print(f"🔍 Executing CloudPulse FinOps Audit on {BOLD}{backend_url}{RESET}...\n")

    # Ensure demo mode is ready if needed
    try:
        http_json(f"{backend_url}/api/v1/demo/enable", method="POST")
    except Exception:
        pass

    # 1. Dashboard Summary
    try:
        summary = http_json(f"{backend_url}/api/v1/dashboard/summary")
        monthly_spend = summary.get("monthly_spend", 0)
        wasted_spend = summary.get("wasted_monthly_spend", 0)
        waste_percent = round((wasted_spend / monthly_spend * 100) if monthly_spend > 0 else 0, 1)

        print(f"{BOLD}💰 SPEND OVERVIEW{RESET}")
        print("-" * 55)
        print(f"  • Total Monthly Spend  : {BOLD}${monthly_spend:,.2f}{RESET}")
        print(f"  • Identifiable Waste   : {RED}${wasted_spend:,.2f} ({waste_percent}% of total bill){RESET}")
        print(f"  • Monitored Nodes      : {summary.get('total_nodes')} ({summary.get('running_nodes')} running)")
    except Exception as e:
        print(f"{YELLOW}Notice fetching summary:{RESET} {e}")

    # 2. Health Score
    try:
        health = http_json(f"{backend_url}/api/v1/analytics/health-score")
        score = health.get("overall_health_score", 0)
        grade = health.get("grade", "N/A")
        grade_color = GREEN if grade in ["A", "B"] else (YELLOW if grade == "C" else RED)

        print(f"\n{BOLD}🛡️ FINOPS HEALTH SCORE{RESET}")
        print("-" * 55)
        print(f"  • Overall Score        : {grade_color}{score}/100 (Grade: {grade}){RESET}")
        pillars = health.get("pillars", {})
        for p_name, p_info in pillars.items():
            if isinstance(p_info, dict):
                score_val = p_info.get("score", 0)
                max_val = p_info.get("max", 25)
                print(f"    - {p_name.replace('_', ' ').capitalize():<22}: {score_val}/{max_val}")
            else:
                print(f"    - {p_name.replace('_', ' ').capitalize():<22}: {p_info}/100")
    except Exception:
        pass

    # 3. Top Optimizations
    try:
        optimizations = http_json(f"{backend_url}/api/optimizations")
        print(f"\n{BOLD}⚡ TOP OPTIMIZATION FINDINGS ({len(optimizations)}){RESET}")
        print("-" * 75)
        print(f"  {'TYPE':<20} {'TITLE':<38} {'MONTHLY SAVINGS'}")
        print("  " + "-" * 71)
        total_potential = 0.0
        for opt in optimizations[:6]:
            savings = float(opt.get("savings") or 0.0)
            total_potential += savings
            title = (opt.get("title", "")[:36] + "..") if len(opt.get("title", "")) > 38 else opt.get("title", "")
            print(f"  {opt.get('type', ''):<20} {title:<38} {GREEN}+${savings:,.2f}/mo{RESET}")
        print("  " + "-" * 71)
        print(f"  {BOLD}Total Potential Monthly Savings:{RESET} {GREEN}{BOLD}+${total_potential:,.2f}/mo{RESET}")
    except Exception:
        pass

    # 4. Forecast & Anomalies
    try:
        anomalies_resp = http_json(f"{backend_url}/api/v1/analytics/anomalies")
        anomalies = anomalies_resp.get("anomalies", [])
        if anomalies:
            print(f"\n{BOLD}🚨 DETECTED COST ANOMALIES ({len(anomalies)}){RESET}")
            print("-" * 55)
            for a in anomalies[:3]:
                print(f"  • {a.get('day')}: ${a.get('cost')} (Spike: {RED}+{a.get('spike_percentage')}%{RESET} vs expected ${a.get('expected_mean')})")
    except Exception:
        pass
    print("\n" + "=" * 75 + "\n")

# ==========================================
# COMMAND: scan (In-Guest Machine Scan)
# ==========================================
def cmd_scan(args):
    if not args.json_only:
        print_banner()
        print(f"{BOLD}🔬 Scanning Local Host & In-Guest Telemetry...{RESET}\n")

    cloud_info = CloudInstanceDetector.detect()
    telemetry = MultiOSCollector.collect_full_telemetry()

    if args.json_only:
        print(json.dumps({"cloud": cloud_info, "telemetry": telemetry}, indent=2))
        return

    os_info = telemetry["os"]
    cpu = telemetry["cpu"]
    mem = telemetry["memory"]
    disk = telemetry["disk"]

    print(f"{CYAN}{BOLD}🌐 CLOUD & PLATFORM{RESET}")
    print(f"  • Provider         : {cloud_info['provider'].upper()}")
    print(f"  • Instance ID      : {cloud_info['instance_id']}")
    print(f"  • Instance Type    : {cloud_info['instance_type']}")
    print(f"  • Region / Zone    : {cloud_info['region']} ({cloud_info['availability_zone']})")

    print(f"\n{CYAN}{BOLD}📊 HARDWARE & IN-GUEST RESOURCES{RESET}")
    print(f"  • OS Family        : {os_info['os_type'].upper()} ({os_info['system']} {os_info['release']})")
    print(f"  • CPU Utilization  : {cpu['utilization_percent']}% ({cpu['logical_cores']} Cores)")
    print(f"  • Memory (RAM)     : {mem['used_mb']} MB / {mem['total_mb']} MB ({mem['percent_used']}% used)")
    print(f"  • Root Disk Mount  : {disk['used_gb']} GB / {disk['total_gb']} GB ({disk['percent_used']}% used)")

    # Instant local FinOps assessment
    print(f"\n{CYAN}{BOLD}💡 IN-GUEST FINOPS RIGHTSIZING ASSESSMENT{RESET}")
    if cpu['utilization_percent'] < 10.0 and mem['percent_used'] < 30.0:
        print(f"  {YELLOW}⚠️  UNDERUTILIZATION WARNING:{RESET} CPU average is {cpu['utilization_percent']}% and RAM is {mem['percent_used']}%.")
        print(f"  • Recommendation: Downsize this instance by at least 1 size to cut compute cost by ~50%.")
    elif cpu['utilization_percent'] > 85.0 or mem['percent_used'] > 90.0:
        print(f"  {RED}⚠️  SATURATION WARNING:{RESET} Resource utilization is near maximum capacity.")
        print(f"  • Recommendation: Scale horizontally or upgrade instance type to prevent throttling.")
    else:
        print(f"  {GREEN}✅ BALANCED FOOTPRINT:{RESET} Memory and CPU utilization are within healthy operational thresholds.")

    print(f"\n{CYAN}{BOLD}🔍 TOP 5 PROCESSES BY CONSUMPTION{RESET}")
    print(f"  {'PID':<8} {'USER':<12} {'CPU%':<8} {'RAM%':<8} {'COMMAND'}")
    print("  " + "-" * 55)
    for p in telemetry.get("top_processes", [])[:5]:
        print(f"  {p['pid']:<8} {p['user']:<12} {p['cpu_percent']:<8} {p['memory_percent']:<8} {p['name']}")
    print()

# ==========================================
# COMMAND: ask (AI Copilot Chat)
# ==========================================
def cmd_ask(args):
    prompt = " ".join(args.prompt)
    if not prompt:
        print(f"{RED}Error:{RESET} Please provide a question or slash command (e.g., `cloudpulse ask 'How can I reduce AWS spend?'`)")
        sys.exit(1)

    backend_url = get_backend_url(args.url)
    print(f"\n{CYAN}🤖 CloudPulse AI Copilot{RESET} ({backend_url})...\n")

    # If it's a slash command, try v1 agent chat
    if prompt.startswith("/"):
        try:
            resp = http_json(f"{backend_url}/api/v1/agent/chat", method="POST", payload={"query": prompt})
            if "data" in resp:
                print(json.dumps(resp["data"], indent=2))
            elif "response" in resp:
                print(resp["response"])
            else:
                print(json.dumps(resp, indent=2))
            return
        except Exception as e:
            print(f"Notice falling back to copilot v2: {e}")

    try:
        resp = http_json(f"{backend_url}/api/v2/copilot/chat", method="POST", payload={"message": prompt, "prompt": prompt, "history": []})
        answer = resp.get("answer", "No response received.")
        provider = resp.get("provider", "local")
        model = resp.get("model")
        badge = f"{DIM}[{provider}{f':{model}' if model else ''}]{RESET}"
        print(f"{badge}\n{answer}\n")
    except Exception as e:
        print(f"{RED}Failed to query AI Copilot:{RESET} {e}")
        sys.exit(1)

# ==========================================
# COMMAND: iac (Generate Terraform PR)
# ==========================================
def cmd_iac(args):
    backend_url = get_backend_url(args.url)
    payload = {
        "resource_id": args.resource_id,
        "action": args.action,
        "from_type": args.from_type,
        "to_type": args.to_type
    }
    print(f"Generating Terraform PR for {args.resource_id} on {backend_url}...")
    try:
        res = http_json(f"{backend_url}/api/v2/copilot/generate-iac-pr", method="POST", payload=payload)
        print(f"\n{GREEN}✅ Remediation PR Generated:{RESET}")
        print(f"  • Branch Name : {BOLD}{res.get('branch_name')}{RESET}")
        print(f"  • Commit Title: {res.get('commit_title')}")
        print(f"\n{BOLD}📄 Unified Diff:{RESET}\n")
        print(res.get("unified_diff", ""))

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(res.get("hcl_after", ""))
            print(f"\n💾 Saved Terraform HCL to: {args.output}")
    except Exception as e:
        print(f"{RED}Failed to generate IaC:{RESET} {e}")
        sys.exit(1)

# ==========================================
# COMMAND: onboard (Customer AWS Account Onboarding)
# ==========================================
def cmd_onboard(args):
    print_banner()
    backend_url = get_backend_url(args.url)
    print(f"☁️ Generating 1-Click AWS Onboarding Package on {BOLD}{backend_url}{RESET}...\n")
    try:
        pkg = http_json(f"{backend_url}/api/v2/onboarding/cloudformation?org_id={args.org_id}&allow_remediation={str(args.remediation).lower()}")
        print(f"{BOLD}🔐 AWS SECURITY & TRUST CONFIGURATION{RESET}")
        print("-" * 65)
        print(f"  • External ID        : {BOLD}{pkg.get('external_id')}{RESET}")
        print(f"  • SaaS Account ID    : {pkg.get('saas_account_id')}")
        print(f"\n{BOLD}🚀 1-CLICK AWS CONSOLE QUICK-CREATE LINK:{RESET}")
        print(f"{CYAN}{pkg.get('quick_create_url')}{RESET}\n")

        if args.save_yaml:
            with open(args.save_yaml, "w", encoding="utf-8") as f:
                f.write(pkg.get("template_yaml", ""))
            print(f"💾 CloudFormation template saved to: {args.save_yaml}")
    except Exception as e:
        print(f"{RED}Failed to generate onboarding package:{RESET} {e}")
        sys.exit(1)

# ==========================================
# COMMAND: push & daemon (In-Guest Telemetry)
# ==========================================
def cmd_push(args):
    backend_url = get_backend_url(args.url)
    print(f"Pushing host telemetry to {backend_url}...")
    cloud_info = CloudInstanceDetector.detect()
    telemetry = MultiOSCollector.collect_full_telemetry()
    payload = {
        "host_id": cloud_info.get("instance_id") or "host-" + telemetry["os"]["hostname"],
        "hostname": telemetry["os"]["hostname"],
        "os": telemetry["os"]["system"],
        "os_family": telemetry["os"]["os_type"],
        "metrics": {
            "cpu_percent": telemetry["cpu"]["utilization_percent"],
            "memory_percent": telemetry["memory"]["percent_used"],
            "memory_total_mb": telemetry["memory"]["total_mb"],
            "memory_used_mb": telemetry["memory"]["used_mb"],
            "disk_percent": telemetry["disk"]["percent_used"]
        },
        "cloud": cloud_info,
        "top_processes": telemetry.get("top_processes", [])
    }
    try:
        res = http_json(f"{backend_url}/api/v2/agent/ingest", method="POST", payload=payload)
        print(f"{GREEN}✅ Telemetry ingested successfully:{RESET} {res.get('status')}")
    except Exception as e:
        print(f"{RED}Failed to push telemetry:{RESET} {e}")
        sys.exit(1)

def cmd_daemon(args):
    print_banner()
    backend_url = get_backend_url(args.url)
    print(f"🚀 CloudPulse Telemetry Daemon Active")
    print(f"  • Target Backend : {backend_url}")
    print(f"  • Interval       : {args.interval}s")
    print("Press CTRL+C to terminate.\n")

    while True:
        try:
            t_now = time.strftime("%Y-%m-%d %H:%M:%S")
            cmd_push(args)
            time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nShutting down daemon gracefully.")
            break
        except Exception as e:
            print(f"Daemon notice: {e}")
            time.sleep(args.interval)

# ==========================================
# COMMAND: config
# ==========================================
def cmd_config(args):
    conf = load_config()
    if args.set_url:
        conf["backend_url"] = args.set_url.rstrip("/")
        save_config(conf)
        print(f"{GREEN}✅ Default backend URL set to:{RESET} {conf['backend_url']}")
    elif args.show:
        print(f"{BOLD}CloudPulse CLI Configuration ({CONFIG_FILE}):{RESET}")
        print(json.dumps(conf, indent=2))
# ==========================================
# COMMAND: connect (AWS / Learner Lab / Cloud)
# ==========================================
def cmd_connect(args):
    print_banner()
    backend_url = get_backend_url(args.url)
    print(f"🔗 Connecting Cloud Account to {BOLD}{backend_url}{RESET}...\n")

    access_key = args.access_key
    secret_key = args.secret_key
    session_token = args.session_token
    region = args.region or "us-east-1"
    account_name = args.account_name or "AWS Learner Lab"

    # Support reading from credentials block file if provided
    if args.credentials_file:
        try:
            expanded_path = os.path.expanduser(args.credentials_file)
            with open(expanded_path, "r", encoding="utf-8") as f:
                content = f.read()
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("aws_access_key_id"):
                    access_key = line.split("=", 1)[1].strip()
                elif line.startswith("aws_secret_access_key"):
                    secret_key = line.split("=", 1)[1].strip()
                elif line.startswith("aws_session_token"):
                    session_token = line.split("=", 1)[1].strip()
        except Exception as e:
            print(f"{RED}Error reading credentials file:{RESET} {e}")
            sys.exit(1)

    # Interactive prompt if keys not provided via args or file
    if not (access_key and secret_key):
        print(f"{CYAN}Please enter your AWS credentials (e.g., from AWS Learner Lab or IAM):{RESET}")
        try:
            access_key = input("  AWS Access Key ID: ").strip()
            secret_key = input("  AWS Secret Access Key: ").strip()
            session_token = input("  AWS Session Token (leave blank for IAM user): ").strip() or None
            region_in = input(f"  AWS Region [{region}]: ").strip()
            if region_in:
                region = region_in
            name_in = input(f"  Account Name [{account_name}]: ").strip()
            if name_in:
                account_name = name_in
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(0)

    auth_method = "learner_lab" if session_token else "keys"

    payload = {
        "provider": "AWS",
        "account_name": account_name,
        "auth_method": auth_method,
        "access_key": access_key,
        "secret_key": secret_key,
        "session_token": session_token,
        "region": region
    }

    print(f"Authenticating with AWS ({auth_method}) in region {region}...")
    try:
        res = http_json(f"{backend_url}/api/v1/connect-cloud", method="POST", payload=payload, timeout=30.0)
        print(f"\n{GREEN}✅ Successfully Connected to AWS!{RESET}")
        print(f"  • Account ID   : {BOLD}{res.get('account_id')}{RESET}")
        print(f"  • Caller ARN   : {res.get('arn')}")
        print(f"  • Access Mode  : {res.get('access_mode')}")
        if res.get('warning'):
            print(f"  • Warning      : {YELLOW}{res.get('warning')}{RESET}")

        # Fetch discovered nodes
        try:
            nodes = http_json(f"{backend_url}/api/nodes", timeout=30.0)
            print(f"\n{BOLD}📦 Discovered Live Compute Nodes ({len(nodes)}):{RESET}")
            print(f"  {'INSTANCE ID':<22} {'NAME':<16} {'TYPE':<12} {'STATE':<10} {'PUBLIC IP':<16} {'COST/MO'}")
            print("  " + "-" * 88)
            for n in nodes:
                state_color = GREEN if n.get('state') == 'running' else YELLOW
                print(f"  {n.get('instance_id'):<22} {n.get('name', 'unnamed'):<16} {n.get('type', ''):<12} {state_color}{n.get('state', ''):<10}{RESET} {n.get('public_ip') or 'None':<16} ${n.get('cost', 0):.2f}/mo")
            print()
        except Exception as err:
            print(f"\n{YELLOW}Note fetching initial node list:{RESET} {err}")
            print("Run `cloudpulse audit` to view discovered resources.")
    except Exception as e:
        print(f"{RED}✖ Failed to connect AWS account:{RESET} {e}")
        sys.exit(1)

def main():
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument("--url", default=None, help="CloudPulse backend URL (defaults to configured URL)")

    parser = argparse.ArgumentParser(
        prog="cloudpulse",
        description="CloudPulse FinOps Management, Multi-OS In-Guest Agent & Testing CLI",
        parents=[common_parser]
    )
    subparsers = parser.add_subparsers(dest="command", help="Available CloudPulse commands")

    # test
    p_test = subparsers.add_parser("test", parents=[common_parser], help="Run automated backend integration tests & health auditing")
    p_test.add_argument("--json", dest="json_file", default=None, help="Path to save JSON test report")
    p_test.add_argument("--html", dest="html_file", default=None, help="Path to save HTML dashboard report")
    p_test.add_argument("--timeout", type=float, default=20.0, help="Per-request timeout in seconds (default: 20)")
    p_test.add_argument("--verbose", action="store_true", help="Print verbose logs")

    # status
    subparsers.add_parser("status", parents=[common_parser], help="Check backend connection, database health, and host specs")

    # audit
    subparsers.add_parser("audit", parents=[common_parser], help="Run comprehensive FinOps audit (spend, waste, health score, savings)")

    # scan
    p_scan = subparsers.add_parser("scan", parents=[common_parser], help="Scan local in-guest CPU, RAM, disk, processes, and cloud provider")
    p_scan.add_argument("--json", dest="json_only", action="store_true", help="Output raw JSON payload only")

    # ask
    p_ask = subparsers.add_parser("ask", parents=[common_parser], help="Ask autonomous FinOps AI Copilot questions or execute slash commands")
    p_ask.add_argument("prompt", nargs="+", help="Your question or slash command (e.g. /optimize, /health)")

    # iac
    p_iac = subparsers.add_parser("iac", parents=[common_parser], help="Generate Terraform PR code to remediate a finding")
    p_iac.add_argument("resource_id", help="Resource ID (e.g., i-036358db85d245e3a)")
    p_iac.add_argument("--action", default="rightsize", help="Action (rightsize, stop, terminate)")
    p_iac.add_argument("--from-type", default="m5.2xlarge", help="Current instance type")
    p_iac.add_argument("--to-type", default="m6g.xlarge", help="Target instance type")
    p_iac.add_argument("--output", "-o", default=None, help="File to write Terraform HCL to")

    # onboard
    p_onboard = subparsers.add_parser("onboard", parents=[common_parser], help="Generate 1-click AWS CloudFormation onboarding package")
    p_onboard.add_argument("--org-id", default="default-org", help="Organization ID")
    p_onboard.add_argument("--remediation", action="store_true", help="Allow automated remediation actions")
    p_onboard.add_argument("--save-yaml", default=None, help="Save template to a YAML file")

    # connect (AWS / Learner Lab / Cloud)
    p_connect = subparsers.add_parser("connect", parents=[common_parser], help="Connect an AWS / Learner Lab account using access keys & session token")
    p_connect.add_argument("--access-key", "-k", default=None, help="AWS Access Key ID")
    p_connect.add_argument("--secret-key", "-s", default=None, help="AWS Secret Access Key")
    p_connect.add_argument("--session-token", "-t", default=None, help="AWS Session Token (for Learner Lab / STS)")
    p_connect.add_argument("--region", "-r", default="us-east-1", help="AWS Region (default: us-east-1)")
    p_connect.add_argument("--account-name", "-n", default="AWS Learner Lab", help="Display name for this account")
    p_connect.add_argument("--credentials-file", "-f", default=None, help="Path to credentials file (e.g. ~/.aws/credentials)")

    # push
    subparsers.add_parser("push", parents=[common_parser], help="Push current host metrics to backend")

    # daemon
    p_daemon = subparsers.add_parser("daemon", parents=[common_parser], help="Run background in-guest telemetry streaming daemon")
    p_daemon.add_argument("--interval", type=int, default=30, help="Push interval in seconds (default: 30)")

    # config
    p_config = subparsers.add_parser("config", parents=[common_parser], help="Manage CLI settings and backend URL")
    p_config.add_argument("--set-url", default=None, help="Set default backend URL")
    p_config.add_argument("--show", action="store_true", help="Show current configuration")

    args = parser.parse_args()

    if not args.command:
        print_banner()
        parser.print_help()
        sys.exit(0)

    dispatch = {
        "test": cmd_test,
        "status": cmd_status,
        "audit": cmd_audit,
        "scan": cmd_scan,
        "ask": cmd_ask,
        "iac": cmd_iac,
        "onboard": cmd_onboard,
        "connect": cmd_connect,
        "push": cmd_push,
        "daemon": cmd_daemon,
        "config": cmd_config,
    }

    cmd_fn = dispatch.get(args.command)
    if cmd_fn:
        cmd_fn(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
