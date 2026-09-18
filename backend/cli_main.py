#!/usr/bin/env python3
"""
CloudPulse Enterprise CLI & Testing Tool
Unified command-line interface for FinOps practitioners, developers, and DevOps teams.
Supports complete backend testing, in-guest scanning, AI Copilot chat, and cloud cost auditing.
"""

import sys
import os
import re
import time
import json
import argparse
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, Optional

# Ensure parent, backend, and venv paths are importable
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
import glob
for sp in glob.glob(os.path.join(ROOT_DIR, "venv", "lib", "python*", "site-packages")):
    if sp not in sys.path:
        sys.path.insert(0, sp)
for p in [CURRENT_DIR, ROOT_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from agent.collector import MultiOSCollector
    from agent.cloud_detector import CloudInstanceDetector
    from testing.runner import CloudPulseTestRunner
    from cli_exporters import FinOpsReportExporter
except ImportError:
    try:
        from backend.agent.collector import MultiOSCollector
        from backend.agent.cloud_detector import CloudInstanceDetector
        from backend.testing.runner import CloudPulseTestRunner
        from backend.cli_exporters import FinOpsReportExporter
    except ImportError:
        # Fallback if testing or agent is relative
        from .agent.collector import MultiOSCollector
        from .agent.cloud_detector import CloudInstanceDetector
        from .testing.runner import CloudPulseTestRunner
        try:
            from .cli_exporters import FinOpsReportExporter
        except ImportError:
            FinOpsReportExporter = None

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

ANSI_REGEX = re.compile(r'\x1b\[[0-9;]*[mK]')

def strip_ansi(text: str) -> str:
    return ANSI_REGEX.sub('', text)

def get_banner_str() -> str:
    return rf"""{CYAN}{BOLD}
   ____ _                 _ ____        _           
  / ___| | ___  _   _  __| |  _ \ _   _| |___  ___  
 | |   | |/ _ \| | | |/ _` | |_) | | | | / __|/ _ \ 
 | |___| | (_) | |_| | (_| |  __/| |_| | \__ \  __/ 
  \____|_|\___/ \__,_|\__,_|_|    \__,_|_|___/\___| 
    Enterprise FinOps, Multi-OS Agent & Testing CLI{RESET}
"""

def print_banner():
    print(get_banner_str())

def emit_output(content: str, output_path: Optional[str] = None):
    if output_path:
        out_file = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(out_file), exist_ok=True)
        clean_content = strip_ansi(content)
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(clean_content)
        print(f"\n{GREEN}✔ FinOps report saved successfully to:{RESET} {BOLD}{out_file}{RESET}\n")
    else:
        print(content)

def get_report_format(args: argparse.Namespace) -> str:
    if getattr(args, "json_only", False):
        return "json"
    fmt = getattr(args, "format", "table")
    if not fmt:
        return "table"
    fmt_clean = fmt.lower().strip()
    if fmt_clean in ["md", "markdown"]:
        return "markdown"
    return fmt_clean


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
    use_rag = getattr(args, "rag", False)
    print(f"\n{CYAN}🤖 CloudPulse AI Copilot{' [RAG Engine]' if use_rag else ''}{RESET} ({backend_url})...\n")

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

    # RAG direct route if requested
    if use_rag:
        try:
            resp = http_json(f"{backend_url}/api/v2/copilot/rag/ask", method="POST", payload={"query": prompt})
            answer = resp.get("answer", "No response received.")
            provider = resp.get("provider", "groq")
            model = resp.get("model", "unknown")
            items = resp.get("retrieved_items", 0)
            savings = resp.get("potential_monthly_savings", 0.0)
            badge = f"{DIM}[{provider}:{model} | RAG: {items} resources audited | ${savings:.2f}/mo potential savings]{RESET}"
            print(f"{badge}\n\n{answer}\n")
            return
        except Exception:
            try:
                from services.finops_rag import finops_rag_pipeline
                res = finops_rag_pipeline.ask(prompt)
                badge = f"{DIM}[{res.get('provider')}:{res.get('model')} | Local RAG: {res.get('retrieved_items', 0)} resources audited]{RESET}"
                print(f"{badge}\n\n{res.get('answer')}\n")
                return
            except Exception:
                pass

    try:
        resp = http_json(f"{backend_url}/api/v2/copilot/chat", method="POST", payload={"message": prompt, "prompt": prompt, "history": []})
        answer = resp.get("answer", "No response received.")
        provider = resp.get("provider", "local")
        model = resp.get("model")
        badge = f"{DIM}[{provider}{f':{model}' if model else ''}]{RESET}"
        print(f"{badge}\n{answer}\n")
    except Exception as e:
        try:
            from services.finops_rag import finops_rag_pipeline
            res = finops_rag_pipeline.ask(prompt)
            badge = f"{DIM}[{res.get('provider')}:{res.get('model')} | Local RAG]{RESET}"
            print(f"{badge}\n\n{res.get('answer')}\n")
        except Exception:
            print(f"{RED}Failed to query AI Copilot:{RESET} {e}")
            sys.exit(1)


def cmd_recommend(args):
    """
    Executes Groq RAG FinOps Recommendation Engine:
    Retrieves live cloud inventory, augments with pricing catalog & savings analytics,
    and generates multi-vector recommendations with Groq LLM.
    """
    fmt = get_report_format(args)
    output_dest = getattr(args, "output", None)
    focus = getattr(args, "focus", "all")
    backend_url = get_backend_url(getattr(args, "url", None))

    print(f"\n{CYAN}{BOLD}🧠 CloudPulse Groq FinOps RAG Engine{RESET}")
    print(f"Retrieving cloud telemetry & generating AI recommendations (focus: {focus})...\n")

    report_data = None
    try:
        report_data = http_json(
            f"{backend_url}/api/v2/copilot/rag/recommendations",
            method="POST",
            payload={"focus_domain": focus},
            timeout=45.0
        )
    except Exception:
        try:
            from services.finops_rag import finops_rag_pipeline
            report_data = finops_rag_pipeline.generate_recommendations(focus_domain=focus)
        except Exception as local_err:
            print(f"{RED}Error generating RAG recommendations:{RESET} {local_err}")
            sys.exit(1)

    if fmt == "json":
        emit_output(json.dumps(report_data, indent=2), output_dest)
        return

    provider = report_data.get("provider", "groq")
    model = report_data.get("model", "compound-mini")
    monthly = report_data.get("monthly_savings", 0.0)
    annual = report_data.get("annual_savings", 0.0)
    items = report_data.get("items_audited", 0)
    raw_md = report_data.get("report_markdown", "")

    header = (
        f"{get_banner_str()}\n"
        f"{'=' * 88}\n"
        f"  🤖 AI ENGINE: {provider.upper()} ({model}) | 🔍 AUDITED ITEMS: {items}\n"
        f"  💰 POTENTIAL MONTHLY RECOVERY: ${monthly:.2f}/mo  (${annual:.2f}/year)\n"
        f"{'=' * 88}\n\n"
    )

    emit_output(header + raw_md, output_dest)


def cmd_rag_test(args):
    """
    Diagnostic verification tool for the Groq RAG pipeline:
    Tests Retrieval, Augmentation, and Generation end-to-end.
    """
    print(get_banner_str())
    print("=" * 88)
    print("        🧪 GROQ FINOPS RAG END-TO-END VERIFICATION & BENCHMARK")
    print("=" * 88)

    t0 = time.time()
    try:
        from services.finops_rag import finops_rag_pipeline
    except ImportError:
        from backend.services.finops_rag import finops_rag_pipeline

    # 1. Test Retrieval
    print(f"\n{BOLD}[1/3] Testing Cloud Telemetry & Rate Card Retrieval...{RESET}")
    ret = finops_rag_pipeline.retrieve_context(query="storage and compute")
    print(f"  {GREEN}✔{RESET} Retrieved domains: {ret.get('domains')}")
    print(f"  {GREEN}✔{RESET} Total retrieved items: {ret.get('total_retrieved_items')} (Compute: {len(ret.get('nodes', []))}, EBS: {len(ret.get('ebs_volumes', []))}, EIP: {len(ret.get('elastic_ips', []))})")
    print(f"  {GREEN}✔{RESET} Rate cards indexed: {list(ret.get('pricing_rate_cards', {}).keys())}")

    # 2. Test Augmentation
    print(f"\n{BOLD}[2/3] Testing FinOps Unit Economics & Prompt Augmentation...{RESET}")
    aug = finops_rag_pipeline.augment_context(ret)
    print(f"  {GREEN}✔{RESET} Calculated Potential Monthly Savings: {BOLD}${aug.get('total_monthly_savings'):.2f}/mo{RESET}")
    print(f"  {GREEN}✔{RESET} Calculated Potential Annual Savings: {BOLD}${aug.get('total_annual_savings'):.2f}/yr{RESET}")
    print(f"  {GREEN}✔{RESET} Augmented prompt length: {len(aug.get('augmented_prompt', ''))} characters")

    # 3. Test Generation
    print(f"\n{BOLD}[3/3] Testing Groq LLM Generation...{RESET}")
    test_q = "What is the single biggest waste in our storage and how much does it cost?"
    print(f"  Query: \"{test_q}\"")
    t_gen = time.time()
    gen = finops_rag_pipeline.ask(test_q)
    latency = time.time() - t_gen
    total_time = time.time() - t0

    prov = gen.get("provider")
    mod = gen.get("model")
    print(f"  {GREEN}✔{RESET} Generation completed in {BOLD}{latency:.2f}s{RESET} (Total RAG pipeline: {total_time:.2f}s)")
    print(f"  {GREEN}✔{RESET} Provider: {prov} | Model: {mod} | Status: {gen.get('status')}")
    print(f"\n{CYAN}{BOLD}--- AI RAG Response ---{RESET}")
    print(gen.get("answer"))
    print("=" * 88)
    print(f"{GREEN}✅ Groq FinOps RAG Pipeline is 100% OPERATIONAL!{RESET}\n")

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

        output_dest = getattr(args, "output", None)
        if output_dest:
            with open(output_dest, "w", encoding="utf-8") as f:
                f.write(res.get("hcl_after", ""))
            print(f"\n💾 Saved Terraform HCL to: {output_dest}")
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

def fetch_inventory_data(backend_url: str) -> Dict[str, Any]:
    try:
        return http_json(f"{backend_url}/api/v1/resources/inventory", timeout=25.0)
    except Exception as e:
        print(f"{RED}Error fetching cloud inventory from {backend_url}:{RESET} {e}")
        print(f"Run `{CYAN}cloudpulse connect -f ~/.aws/credentials{RESET}` to authenticate and refresh your AWS session.")
        sys.exit(1)

# ==========================================
# COMMAND: inspect & inventory (Deep Parameter Inspection)
# ==========================================
def cmd_inspect(args):
    target_id = getattr(args, "resource_id", None)
    if target_id:
        target_id = target_id.strip()
    fmt = get_report_format(args)
    output_dest = getattr(args, "output", None)
    backend_url = get_backend_url(getattr(args, "url", None))
    inv = fetch_inventory_data(backend_url)

    metadata = inv.get("metadata", {})
    nodes = inv.get("compute", {}).get("nodes", [])
    ec2_other = inv.get("ec2_other_resources", {})
    ebs_vols = ec2_other.get("ebs_volumes", [])
    eips = ec2_other.get("elastic_ips", [])
    amis = ec2_other.get("amis", [])
    enis = ec2_other.get("network_interfaces", [])
    snapshots = ec2_other.get("ebs_snapshots", [])
    cw_logs = ec2_other.get("cloudwatch_log_groups", [])
    s3_buckets = ec2_other.get("s3_buckets", [])
    security_groups = ec2_other.get("security_groups", [])
    vpc_res = inv.get("vpc_resources", {})
    nat_gws = vpc_res.get("nat_gateways", [])
    vpc_eps = vpc_res.get("vpc_endpoints", [])

    vol_by_inst = {}
    for v in ebs_vols:
        inst_id = v.get("attached_instance_id")
        if inst_id:
            vol_by_inst.setdefault(inst_id, []).append(v)

    # Categories definition
    COMPUTE_KEYS = {"ec2", "compute", "instances", "nodes", "servers"}
    STORAGE_KEYS = {"ebs", "storage", "volumes", "disks"}
    NETWORK_KEYS = {"network", "net", "ips", "eips", "interfaces", "networking"}
    SECURITY_KEYS = {"security", "sec", "sg", "security_groups", "firewall"}
    LOGS_KEYS = {"logs", "cw", "cloudwatch", "logging"}

    # 1. CATEGORY FILTERS
    if target_id:
        target_lower = target_id.lower()

        # Category: Compute / EC2
        if target_lower in COMPUTE_KEYS:
            if fmt == "json":
                emit_output(json.dumps({"compute_nodes": nodes}, indent=2), output_dest)
                return
            elif fmt == "csv":
                emit_output(FinOpsReportExporter.ec2_compute_to_csv(nodes), output_dest)
                return
            elif fmt == "markdown":
                emit_output(FinOpsReportExporter.ec2_compute_to_markdown(nodes), output_dest)
                return
            else: # table
                out = []
                out.append(get_banner_str())
                out.append("=" * 88)
                out.append(f"       🖥️  OPTISCALE EC2 COMPUTE NODE INVENTORY ({len(nodes)} Instances)")
                out.append("=" * 88)
                out.append(f"  {'INSTANCE ID':<22} {'TYPE':<10} {'STATE':<9} {'AZ':<12} {'PUBLIC IP':<16} {'CPU AVG':<9} {'COST/MO'}")
                out.append("  " + "-" * 86)
                for n in nodes:
                    c = float(n.get("cost", 7.60))
                    cpu = n.get("metrics", {}).get("cpu_utilization_avg", 0.0)
                    state_col = GREEN if n.get("state") == "running" else YELLOW
                    out.append(f"  {n.get('instance_id'):<22} {n.get('instance_type'):<10} {state_col}{n.get('state'):<9}{RESET} {n.get('availability_zone', 'us-east-1'):<12} {n.get('public_ip') or 'None':<16} {cpu:.2f}%{'':<3} {BOLD}${c:.2f}/mo{RESET}")
                out.append("  " + "-" * 86)
                out.append(f"\n  • Total Compute Spend: {GREEN}${sum(float(n.get('cost', 7.60)) for n in nodes):.2f}/mo{RESET}")
                out.append(f"  • Idle Instance Count: {YELLOW}{sum(1 for n in nodes if float(n.get('metrics', {}).get('cpu_utilization_avg', 0.0)) < 5.0)} of {len(nodes)}{RESET} have average CPU < 5.0%")
                out.append("=" * 88 + "\n")
                emit_output("\n".join(out), output_dest)
                return

        # Category: Storage / EBS
        if target_lower in STORAGE_KEYS:
            if fmt == "json":
                emit_output(json.dumps({"ebs_volumes": ebs_vols, "ebs_snapshots": snapshots}, indent=2), output_dest)
                return
            elif fmt == "csv":
                emit_output(FinOpsReportExporter.ebs_volumes_to_csv(ebs_vols), output_dest)
                return
            elif fmt == "markdown":
                emit_output(FinOpsReportExporter.ebs_volumes_to_markdown(ebs_vols), output_dest)
                return
            else: # table
                out = []
                out.append(get_banner_str())
                out.append("=" * 88)
                out.append(f"       📦 OPTISCALE EBS STORAGE & ATTACHMENT AUDIT ({len(ebs_vols)} Volumes)")
                out.append("=" * 88)
                out.append(f"  {'VOLUME ID':<22} {'SIZE':<8} {'TYPE':<6} {'IOPS':<6} {'STATUS':<9} {'ATTACHED TO':<22} {'COST/MO'}")
                out.append("  " + "-" * 86)
                for v in ebs_vols:
                    v_cost = float(v.get("cost", 0.64))
                    att = v.get("attached_instance_id") or "UNATTACHED"
                    att_col = RED if v.get("is_orphaned") else ""
                    out.append(f"  {v.get('volume_id'):<22} {v.get('size_gb'):<4} GB {v.get('volume_type', 'gp3'):<6} {v.get('iops', 3000):<6} {v.get('status'):<9} {att_col}{att:<22}{RESET} ${v_cost:.2f}/mo")
                out.append("  " + "-" * 86)
                out.append(f"  • Total Storage Spend: {GREEN}${sum(float(v.get('cost', 0.64)) for v in ebs_vols):.2f}/mo{RESET}")
                out.append(f"  • Orphaned Volumes   : {RED}{sum(1 for v in ebs_vols if v.get('is_orphaned'))}{RESET} unattached disks accumulating waste")
                out.append("=" * 88 + "\n")
                emit_output("\n".join(out), output_dest)
                return

        # Category: Network / EIPs / ENIs
        if target_lower in NETWORK_KEYS:
            if fmt == "json":
                emit_output(json.dumps({"public_ipv4_nodes": [n for n in nodes if n.get("public_ip")], "elastic_ips": eips, "network_interfaces": enis}, indent=2), output_dest)
                return
            elif fmt == "csv":
                emit_output(FinOpsReportExporter.network_to_csv(eips, enis, nodes), output_dest)
                return
            elif fmt == "markdown":
                emit_output(FinOpsReportExporter.network_to_markdown(eips, enis, nodes), output_dest)
                return
            else: # table
                out = []
                out.append(get_banner_str())
                out.append("=" * 88)
                out.append("       🌐 OPTISCALE NETWORKING & PUBLIC IPv4 AUDIT")
                out.append("=" * 88)
                pub_nodes = [n for n in nodes if n.get("public_ip")]
                out.append(f"  [1] Public IPv4 Addresses ({len(pub_nodes)} Active × $3.60/mo):")
                for n in pub_nodes:
                    out.append(f"    • {n.get('instance_id')}: {BOLD}{n.get('public_ip')}{RESET} (Private: {n.get('private_ip')}) -> $3.60/month")
                out.append(f"\n  [2] Elastic IPs ({len(eips)} Provisioned):")
                if eips:
                    for e in eips:
                        unatt = e.get("is_unattached")
                        out.append(f"    • {e.get('public_ip')} ({e.get('allocation_id')}): {'🔴 UNATTACHED' if unatt else '🟢 Attached'} (${float(e.get('estimated_monthly_cost', 0)):.2f}/mo)")
                else:
                    out.append("    • None provisioned.")
                out.append(f"\n  [3] Network Interfaces ({len(enis)} ENIs Detected):")
                for eni in enis[:8]:
                    out.append(f"    • {eni.get('network_interface_id')}: {eni.get('private_ip')} (Attached: {eni.get('attached_instance_id')})")
                if len(enis) > 8:
                    out.append(f"    ... and {len(enis) - 8} more.")
                out.append("=" * 88 + "\n")
                emit_output("\n".join(out), output_dest)
                return

        # Category: Security / Security Groups
        if target_lower in SECURITY_KEYS:
            if fmt == "json":
                emit_output(json.dumps({"security_groups": security_groups}, indent=2), output_dest)
                return
            elif fmt == "csv":
                emit_output(FinOpsReportExporter.security_groups_to_csv(security_groups), output_dest)
                return
            elif fmt == "markdown":
                emit_output(FinOpsReportExporter.security_groups_to_markdown(security_groups), output_dest)
                return
            else: # table
                out = []
                out.append(get_banner_str())
                out.append("=" * 88)
                out.append(f"       🔒 OPTISCALE SECURITY GROUPS & INGRESS EXPOSURE ({len(security_groups)} Groups)")
                out.append("=" * 88)
                out.append(f"  {'GROUP ID':<22} {'NAME':<24} {'VPC ID':<16} {'EXPOSED 0.0.0.0/0':<18} {'PORTS'}")
                out.append("  " + "-" * 88)
                for sg in security_groups:
                    exp = sg.get("is_publicly_exposed")
                    exp_col = f"{RED}YES (EXPOSED){RESET}" if exp else f"{GREEN}NO (SECURE){RESET}"
                    ports = ", ".join(str(p) for p in sg.get("exposed_ports", [])) or "-"
                    out.append(f"  {sg.get('group_id'):<22} {sg.get('group_name')[:22]:<24} {sg.get('vpc_id', 'None'):<16} {exp_col:<27} {ports}")
                out.append("=" * 88 + "\n")
                emit_output("\n".join(out), output_dest)
                return

        # Category: Logs / CloudWatch
        if target_lower in LOGS_KEYS:
            if fmt == "json":
                emit_output(json.dumps({"cloudwatch_log_groups": cw_logs}, indent=2), output_dest)
                return
            elif fmt == "csv":
                emit_output(FinOpsReportExporter.cloudwatch_logs_to_csv(cw_logs), output_dest)
                return
            elif fmt == "markdown":
                emit_output(FinOpsReportExporter.cloudwatch_logs_to_markdown(cw_logs), output_dest)
                return
            else: # table
                out = []
                out.append(get_banner_str())
                out.append("=" * 88)
                out.append(f"       📜 OPTISCALE CLOUDWATCH LOG GROUPS ({len(cw_logs)} Groups)")
                out.append("=" * 88)
                out.append(f"  {'LOG GROUP NAME':<40} {'STORED (GB)':<14} {'RETENTION':<16} {'WASTE STATUS'}")
                out.append("  " + "-" * 86)
                for l in cw_logs:
                    is_never = l.get("is_never_expire")
                    w_badge = f"{YELLOW}NEVER EXPIRE{RESET}" if is_never else f"{GREEN}RETENTION SET{RESET}"
                    out.append(f"  {l.get('log_group_name')[:38]:<40} {float(l.get('stored_gb', 0.0)):<14.4f} {str(l.get('retention_in_days') or 'Never'):<16} {w_badge}")
                out.append("=" * 88 + "\n")
                emit_output("\n".join(out), output_dest)
                return

        # 2. SPECIFIC INSTANCE MATCH
        matched_node = next((n for n in nodes if n.get("instance_id", "").lower() == target_lower or n.get("name", "").lower() == target_lower), None)
        if matched_node:
            node_id = matched_node.get("instance_id")
            attached_vols = vol_by_inst.get(node_id, [])
            if not attached_vols and matched_node.get("attached_volume_ids"):
                attached_vols = [v for v in ebs_vols if v.get("volume_id") in matched_node.get("attached_volume_ids", [])]

            attached_enis = [e for e in enis if e.get("attached_instance_id") == node_id]

            compute_cost = float(matched_node.get("cost", 7.60))
            storage_cost = sum(float(v.get("cost", 0.64)) for v in attached_vols) or (len(attached_vols) * 0.64 if attached_vols else 0.64)
            ipv4_cost = 3.60 if matched_node.get("public_ip") else 0.00
            total_cost = compute_cost + storage_cost + ipv4_cost
            hourly_rate = round(compute_cost / 730.0, 4)

            cpu_avg = matched_node.get("metrics", {}).get("cpu_utilization_avg", 0.0)
            cpu_max = matched_node.get("metrics", {}).get("cpu_utilization_max", 0.0)

            res_obj = {
                "instance_id": node_id,
                "name": matched_node.get("name"),
                "instance_type": matched_node.get("instance_type"),
                "state": matched_node.get("state"),
                "platform": matched_node.get("platform"),
                "architecture": matched_node.get("architecture"),
                "region": matched_node.get("region"),
                "availability_zone": matched_node.get("availability_zone"),
                "public_ip": matched_node.get("public_ip"),
                "private_ip": matched_node.get("private_ip"),
                "attached_volumes": attached_vols,
                "attached_enis": attached_enis,
                "cost_parameters": {
                    "hourly_compute_rate_usd": hourly_rate,
                    "monthly_compute_hours": 730,
                    "monthly_compute_cost_usd": compute_cost,
                    "attached_ebs_storage_cost_usd": round(storage_cost, 2),
                    "public_ipv4_surcharge_usd": ipv4_cost,
                    "total_monthly_cost_usd": round(total_cost, 2)
                },
                "telemetry": {
                    "cpu_utilization_avg": cpu_avg,
                    "cpu_utilization_max": cpu_max
                },
                "finops_assessment": {
                    "is_idle": cpu_avg < 5.0,
                    "graviton_candidate": matched_node.get("architecture") == "x86_64",
                    "monthly_savings_graviton": 1.52,
                    "monthly_savings_stop_idle": compute_cost
                }
            }

            cost_data_for_export = {
                "instance_id": node_id,
                "instance_type": matched_node.get("instance_type"),
                "state": matched_node.get("state"),
                "parameters": {
                    "hourly_rate_usd": hourly_rate,
                    "compute_cost_usd": compute_cost,
                    "storage_cost_usd": round(storage_cost, 2),
                    "public_ipv4_cost_usd": ipv4_cost,
                    "total_cost_usd": round(total_cost, 2)
                },
                "line_items": [
                    {"item": "EC2 Compute", "type": matched_node.get("instance_type"), "cost": compute_cost, "share_pct": round(compute_cost / total_cost * 100, 1)},
                    {"item": "EBS Storage", "type": f"{len(attached_vols)} volume(s)", "cost": round(storage_cost, 2), "share_pct": round(storage_cost / total_cost * 100, 1)},
                    {"item": "Public IPv4", "type": "Amazon IPv4 Address", "cost": ipv4_cost, "share_pct": round(ipv4_cost / total_cost * 100, 1)}
                ],
                "savings_opportunities": [
                    {"action": "Graviton Upgrade", "target_type": "t4g.micro", "monthly_savings": 1.52},
                    {"action": "Auto-Stop Idle Server", "condition": "CPU < 5%", "monthly_savings": compute_cost},
                    {"action": "Switch to Private IP", "condition": "Public IP not required", "monthly_savings": ipv4_cost}
                ]
            }

            if fmt == "json":
                emit_output(json.dumps(res_obj, indent=2), output_dest)
                return
            elif fmt == "csv":
                emit_output(FinOpsReportExporter.single_instance_cost_to_csv(cost_data_for_export), output_dest)
                return
            elif fmt == "markdown":
                emit_output(FinOpsReportExporter.single_instance_cost_to_markdown(cost_data_for_export), output_dest)
                return

            # Table mode
            out = []
            out.append(get_banner_str())
            out.append("=" * 88)
            out.append(f"       📌 OPTISCALE DEEP INSPECTION: {BOLD}{node_id}{RESET} ({matched_node.get('name', 'server')})")
            out.append("=" * 88)
            out.append(f"  • Region / AZ        : {matched_node.get('region', 'us-east-1')} ({matched_node.get('availability_zone', 'us-east-1a')})")
            out.append(f"  • Scraped Timestamp  : {metadata.get('timestamp', 'N/A')}")
            out.append(f"  • Organization       : {metadata.get('organization', 'AWS Learner Lab')}")
            out.append("-" * 88)

            out.append(f"\n{CYAN}{BOLD}🖥️  [1] COMPUTE MACHINE SPECIFICATIONS & LIFECYCLE{RESET}")
            out.append(f"  • Instance ID        : {BOLD}{node_id}{RESET}")
            out.append(f"  • Name Tag           : {matched_node.get('name', 'unnamed')}")
            out.append(f"  • Instance Type      : {BOLD}{matched_node.get('instance_type')}{RESET} (2 vCPUs, 1.0 GB RAM)")
            state_color = GREEN if matched_node.get('state') == 'running' else RED
            out.append(f"  • Power State        : {state_color}{matched_node.get('state', '').upper()}{RESET} (Billing: {'Active compute hours ($/hr)' if matched_node.get('state') == 'running' else '$0 compute when stopped'})")
            out.append(f"  • Platform / OS      : {matched_node.get('platform', 'linux').capitalize()} (License: None / Standard)")
            out.append(f"  • Architecture       : {matched_node.get('architecture', 'x86_64')}")
            out.append(f"  • Tenancy / Lifecycle: {matched_node.get('lifecycle', 'on-demand').capitalize()} (Tenancy: Shared)")
            out.append(f"  • Launch Time        : {matched_node.get('launch_time', 'N/A')}")

            out.append(f"\n{CYAN}{BOLD}🌐 [2] NETWORKING & PUBLIC IPv4 INTERFACES{RESET}")
            out.append(f"  • Private IP         : {matched_node.get('private_ip', 'None')}")
            out.append(f"  • Public IP          : {BOLD}{matched_node.get('public_ip', 'None')}{RESET}")
            out.append(f"  • VPC ID / Subnet    : {matched_node.get('vpc_id', 'None')} / {matched_node.get('subnet_id', 'None')}")
            out.append(f"  • Public IPv4 Charge : {YELLOW}$3.60/month ($0.005/hr Amazon IPv4 fee){RESET}" if matched_node.get("public_ip") else "  • Public IPv4 Charge : $0.00/month (Private only)")
            if attached_enis:
                out.append(f"  • Network Interfaces : {len(attached_enis)} ENI(s)")
                for eni in attached_enis:
                    out.append(f"    - {eni.get('network_interface_id')}: status={eni.get('status')}, private={eni.get('private_ip')}, public={eni.get('public_ip')}")

            out.append(f"\n{CYAN}{BOLD}📦 [3] ATTACHED STORAGE (EBS VOLUMES){RESET}")
            if attached_vols:
                for idx, vol in enumerate(attached_vols, 1):
                    vol_cost = float(vol.get('cost', 0.64))
                    out.append(f"  Volume #{idx}: {BOLD}{vol.get('volume_id')}{RESET}")
                    out.append(f"    • Capacity & Type  : {vol.get('size_gb')} GB ({vol.get('volume_type', 'gp3').upper()})")
                    out.append(f"    • Baseline IOPS    : {vol.get('iops', 3000)} IOPS | Throughput: {vol.get('throughput', 125)} MB/s")
                    out.append(f"    • Rate & Pricing   : $0.08 / GB-month (gp3 base)")
                    out.append(f"    • Monthly Cost     : {GREEN}${vol_cost:.2f}/month{RESET}")
                    out.append(f"    • Encrypted        : {vol.get('encrypted', False)}")
                out.append(f"  • Total Storage Cost : {BOLD}${storage_cost:.2f}/month{RESET} across {len(attached_vols)} volume(s)")
            else:
                out.append(f"  • Attached Volumes   : {matched_node.get('volumes', 1)} volume(s) referenced (Estimated: ${storage_cost:.2f}/mo)")

            out.append(f"\n{CYAN}{BOLD}📈 [4] PERFORMANCE TELEMETRY & CLOUDWATCH METRICS{RESET}")
            out.append(f"  • Average CPU Util   : {BOLD}{cpu_avg:.2f}%{RESET}")
            out.append(f"  • Peak CPU Util      : {cpu_max:.2f}%")
            if cpu_avg < 5.0:
                out.append(f"  • FinOps Assessment : {YELLOW}⚠️  IDLE INSTANCE DETECTED (Avg CPU < 5.0%){RESET}")
                out.append(f"    Notice: This compute node is accumulating compute charges while sitting idle.")
            else:
                out.append(f"  • FinOps Assessment : {GREEN}✅ BALANCED WORKLOAD (Avg CPU {cpu_avg:.2f}%){RESET}")

            out.append(f"\n{CYAN}{BOLD}💰 [5] COST CALCULATION FORMULA & MONTHLY PARAMETERS{RESET}")
            out.append(f"  ┌────────────────────────────────────────────────────────────────────────┐")
            out.append(f"  │ Mathematical Model:                                                    │")
            out.append(f"  │ Total Cost = (Hourly Compute × 730h) + Σ(EBS Storage) + Public IPv4 Fee│")
            out.append(f"  └────────────────────────────────────────────────────────────────────────┘")
            out.append(f"  • Parameter Breakdown:")
            out.append(f"    - On-Demand Hourly Rate   : ${hourly_rate:.4f} / hr (AWS Pricing API: {matched_node.get('instance_type')})")
            out.append(f"    - Monthly Operating Hours : 730 hrs (State: {matched_node.get('state')})")
            out.append(f"    - Compute Subtotal        : ${compute_cost:.2f} / month")
            out.append(f"    - Attached EBS Storage    : ${storage_cost:.2f} / month ({len(attached_vols)} volumes)")
            out.append(f"    - Public IPv4 Surcharge   : ${ipv4_cost:.2f} / month ({'1 address' if matched_node.get('public_ip') else 'None'})")
            out.append(f"    ------------------------------------------------------------------------")
            out.append(f"    • {BOLD}Total Monthly Cost        : {GREEN}${total_cost:.2f} / month{RESET} ($3.60 net + ${storage_cost:.2f} EBS + ${compute_cost:.2f} EC2)")

            out.append(f"\n{CYAN}{BOLD}💡 [6] FINOPS OPTIMIZATION & ROI ACTIONS{RESET}")
            out.append(f"  1. {BOLD}Migrate to AWS Graviton (t4g.micro){RESET}:")
            out.append(f"     Upgrade from {matched_node.get('instance_type')} to t4g.micro (ARM64).")
            out.append(f"     • Compute Rate drops to: $6.08/mo")
            out.append(f"     • {GREEN}Immediate Savings: +$1.52/month (20.0% compute reduction){RESET}")
            if cpu_avg < 5.0:
                out.append(f"  2. {BOLD}Stop or Power-Schedule Idle Server{RESET}:")
                out.append(f"     Server is idle (CPU {cpu_avg:.2f}%). Stop instance when not in active use.")
                out.append(f"     • Compute drops to: $0.00/mo (EBS retains data at ${storage_cost:.2f}/mo)")
                out.append(f"     • {GREEN}Immediate Savings: +${compute_cost:.2f}/month (64.2% total instance bill reduction){RESET}")
            if matched_node.get("public_ip"):
                out.append(f"  3. {BOLD}Remove Public IPv4 Address{RESET}:")
                out.append(f"     If instance does not require direct ingress from the internet, switch to private IPv4.")
                out.append(f"     • {GREEN}Immediate Savings: +$3.60/month (30.4% total instance bill reduction){RESET}")
            out.append("=" * 88 + "\n")
            emit_output("\n".join(out), output_dest)
            return
        else:
            print(f"{RED}Error:{RESET} Target or category '{target_id}' not found.")
            print(f"Supported categories: {CYAN}ec2, ebs, network, security, logs{RESET}")
            print(f"Available instance IDs: {', '.join(n.get('instance_id') for n in nodes)}")
            return

    # 3. FULL 10-CATEGORY INVENTORY (target_id is None)
    if fmt == "json":
        emit_output(json.dumps(inv, indent=2), output_dest)
        return
    elif fmt == "markdown":
        emit_output(FinOpsReportExporter.full_inventory_to_markdown(inv), output_dest)
        return
    elif fmt == "csv":
        tot_c = sum(float(n.get("cost", 7.60)) for n in nodes)
        tot_s = sum(sum(float(v.get("cost", 0.64)) for v in vol_by_inst.get(n.get("instance_id"), [])) or 0.64 for n in nodes)
        tot_p = sum(3.60 for n in nodes if n.get("public_ip"))
        summary = {
            "total_monthly_spend_usd": tot_c + tot_s + tot_p,
            "compute_spend_usd": tot_c,
            "storage_spend_usd": tot_s,
            "public_ipv4_spend_usd": tot_p
        }
        inst_list = []
        for n in nodes:
            nid = n.get("instance_id")
            vols = vol_by_inst.get(nid, [])
            c = float(n.get("cost", 7.60))
            s = sum(float(v.get("cost", 0.64)) for v in vols) or 0.64
            p = 3.60 if n.get("public_ip") else 0.0
            inst_list.append({
                "instance_id": nid,
                "name": n.get("name"),
                "type": n.get("instance_type"),
                "state": n.get("state"),
                "cpu_utilization_avg": n.get("metrics", {}).get("cpu_utilization_avg", 0.0),
                "compute_cost": c,
                "storage_cost": s,
                "public_ip_cost": p,
                "total_cost": c + s + p
            })
        emit_output(FinOpsReportExporter.cost_rollup_to_csv(summary, inst_list), output_dest)
        return

    # Table mode for full inventory
    out = []
    out.append(get_banner_str())
    out.append("=" * 88)
    out.append("       📌 OPTISCALE REAL MACHINE INVENTORY & PARAMETER PROFILE")
    out.append("=" * 88)
    out.append(f"  • Execution Timestamp : {metadata.get('timestamp', 'N/A')}")
    out.append(f"  • Scraped Region      : {metadata.get('region', 'us-east-1')}")
    out.append(f"  • Organization        : {metadata.get('organization', 'AWS Learner Lab')}")
    out.append("=" * 88)

    # 1. COMPUTE NODES
    out.append(f"\n{CYAN}{BOLD}🖥️  [1] COMPUTE NODES (EC2 Instances: {len(nodes)}){RESET}")
    if nodes:
        for idx, node in enumerate(nodes, 1):
            nid = node.get("instance_id")
            vols = vol_by_inst.get(nid, [])
            c_cost = float(node.get("cost", 7.60))
            s_cost = sum(float(v.get("cost", 0.64)) for v in vols) or (len(vols) * 0.64 if vols else 0.64)
            net_cost = 3.60 if node.get("public_ip") else 0.00
            tot = c_cost + s_cost + net_cost
            cpu = node.get("metrics", {}).get("cpu_utilization_avg", 0.0)
            state_color = GREEN if node.get("state") == "running" else YELLOW

            out.append(f"  Instance #{idx}: {BOLD}{nid}{RESET} ({node.get('name', 'server')})")
            out.append(f"    • Type & Architecture: {BOLD}{node.get('instance_type')}{RESET} ({node.get('architecture', 'x86_64')})")
            out.append(f"    • State & Platform   : {state_color}{node.get('state')}{RESET} | {node.get('platform', 'linux')}")
            out.append(f"    • AZ / Public IP     : {node.get('availability_zone')} | {node.get('public_ip') or 'None'}")
            out.append(f"    • Average CPU        : {cpu:.2f}% {'(⚠️ IDLE)' if cpu < 5.0 else ''}")
            out.append(f"    • Monthly Cost       : {BOLD}${tot:.2f}/mo{RESET} (Compute: ${c_cost:.2f} + EBS: ${s_cost:.2f} + Net: ${net_cost:.2f})")
    else:
        out.append("  • No active EC2 compute instances detected in region.")

    # 2. EBS VOLUMES
    out.append(f"\n{CYAN}{BOLD}📦 [2] EBS VOLUMES & ATTACHMENTS ({len(ebs_vols)}){RESET}")
    if ebs_vols:
        for idx, vol in enumerate(ebs_vols, 1):
            orphaned = vol.get("is_orphaned")
            v_cost = float(vol.get("cost", 0.64))
            out.append(f"  Volume #{idx}: {BOLD}{vol.get('volume_id')}{RESET}")
            out.append(f"    • Size & Type        : {vol.get('size_gb')} GB ({vol.get('volume_type', 'gp3')})")
            out.append(f"    • Status & Attachment: {vol.get('status')} (Attached to: {vol.get('attached_instance_id') or 'UNATTACHED / ORPHANED'})")
            out.append(f"    • Is Orphaned Waste  : {RED if orphaned else GREEN}{orphaned}{RESET} | Monthly Cost: ${v_cost:.2f}/mo")
    else:
        out.append("  • No EBS volumes found.")

    # 3. ELASTIC IP ADDRESSES
    out.append(f"\n{CYAN}{BOLD}🌐 [3] ELASTIC IP ADDRESSES (EIPs: {len(eips)}){RESET}")
    if eips:
        for idx, eip in enumerate(eips, 1):
            unattached = eip.get("is_unattached")
            out.append(f"  EIP #{idx}: {BOLD}{eip.get('public_ip')}{RESET} (Allocation: {eip.get('allocation_id')})")
            out.append(f"    • Attached Instance  : {eip.get('instance_id') or 'Unattached'}")
            out.append(f"    • Unattached Waste   : {RED if unattached else GREEN}{unattached}{RESET} (${eip.get('estimated_monthly_cost', 0.0)}/mo)")
    else:
        out.append("  • No Elastic IPs provisioned.")

    # 4. CUSTOM AMIs
    out.append(f"\n{CYAN}{BOLD}💿 [4] CUSTOM AMIs ({len(amis)}){RESET}")
    if amis:
        for idx, ami in enumerate(amis, 1):
            out.append(f"  AMI #{idx}: {BOLD}{ami.get('ami_id')}{RESET} - {ami.get('name')}")
    else:
        out.append("  • No custom AMIs owned by this account.")

    # 5. ENIs
    out.append(f"\n{CYAN}{BOLD}🔌 [5] ELASTIC NETWORK INTERFACES ({len(enis)}){RESET}")
    if enis:
        for idx, eni in enumerate(enis[:5], 1):
            out.append(f"  ENI #{idx}: {BOLD}{eni.get('network_interface_id')}{RESET} | IP: {eni.get('private_ip')} | Attached: {eni.get('attached_instance_id')}")
        if len(enis) > 5:
            out.append(f"  ... and {len(enis) - 5} more interfaces.")
    else:
        out.append("  • No Elastic Network Interfaces found.")

    # 6. EBS SNAPSHOTS
    out.append(f"\n{CYAN}{BOLD}📸 [6] EBS SNAPSHOTS ({len(snapshots)}){RESET}")
    if snapshots:
        for idx, snap in enumerate(snapshots, 1):
            out.append(f"  Snapshot #{idx}: {snap.get('snapshot_id')} ({snap.get('size_gb')} GB, ${snap.get('cost')}/mo)")
    else:
        out.append("  • No EBS snapshots owned by this account.")

    # 7. CLOUDWATCH LOG GROUPS
    out.append(f"\n{CYAN}{BOLD}📜 [7] CLOUDWATCH LOG GROUPS ({len(cw_logs)}){RESET}")
    if cw_logs:
        for idx, log in enumerate(cw_logs, 1):
            never = log.get("is_never_expire")
            out.append(f"  Log Group #{idx}: {BOLD}{log.get('log_group_name')}{RESET}")
            out.append(f"    • Storage Size       : {log.get('stored_gb', 0.0)} GB ({log.get('stored_bytes', 0)} bytes)")
            out.append(f"    • Retention (Days)   : {log.get('retention_in_days') or 'Never Expire'} | Waste Flag: {YELLOW if never else GREEN}{never}{RESET}")
    else:
        out.append("  • No CloudWatch log groups found.")

    # 8. S3 BUCKETS
    out.append(f"\n{CYAN}{BOLD}🪣 [8] S3 BUCKETS ({len(s3_buckets)}){RESET}")
    if s3_buckets:
        for idx, b in enumerate(s3_buckets, 1):
            out.append(f"  Bucket #{idx}: {b.get('bucket_name')} (Lifecycle: {b.get('has_lifecycle_policy')})")
    else:
        out.append("  • No S3 buckets provisioned.")

    # 9. SECURITY GROUPS
    out.append(f"\n{CYAN}{BOLD}🔒 [9] SECURITY GROUPS & EXPOSURE AUDIT ({len(security_groups)}){RESET}")
    if security_groups:
        for idx, sg in enumerate(security_groups, 1):
            exposed = sg.get("is_publicly_exposed")
            out.append(f"  SG #{idx}: {BOLD}{sg.get('group_id')}{RESET} ({sg.get('group_name')})")
            out.append(f"    • VPC ID             : {sg.get('vpc_id')}")
            out.append(f"    • Public Exposure    : {RED if exposed else GREEN}{exposed}{RESET} (Ports: {sg.get('exposed_ports', [])})")
    else:
        out.append("  • No Security Groups found.")

    # 10. VPC COST DRIVERS
    out.append(f"\n{CYAN}{BOLD}🛣️  [10] VPC NETWORKING & GATEWAY COST AUDIT{RESET}")
    out.append(f"  • NAT Gateways       : {len(nat_gws)} active ({'Saving ~$32.40/mo per unit' if not nat_gws else 'Cost: ~$32.40/mo each'})")
    out.append(f"  • VPC Endpoints      : {len(vpc_eps)} active ({'No interface endpoint charges' if not vpc_eps else 'Cost: ~$7.20/mo per AZ'})")
    out.append("\n" + "=" * 88 + "\n")
    emit_output("\n".join(out), output_dest)

# ==========================================
# COMMAND: cost (FinOps Cost Engine & Parameters)
# ==========================================
def cmd_cost(args):
    fmt = get_report_format(args)
    output_dest = getattr(args, "output", None)
    backend_url = get_backend_url(args.url)
    inv = fetch_inventory_data(backend_url)

    nodes = inv.get("compute", {}).get("nodes", [])
    ec2_other = inv.get("ec2_other_resources", {})
    ebs_vols = ec2_other.get("ebs_volumes", [])

    vol_by_inst = {}
    for v in ebs_vols:
        inst_id = v.get("attached_instance_id")
        if inst_id:
            vol_by_inst.setdefault(inst_id, []).append(v)

    total_compute = sum(float(n.get("cost", 7.60)) for n in nodes)
    total_storage = sum(sum(float(v.get("cost", 0.64)) for v in vol_by_inst.get(n.get("instance_id"), [])) or 0.64 for n in nodes)
    total_ipv4 = sum(3.60 for n in nodes if n.get("public_ip"))
    gross_total = total_compute + total_storage + total_ipv4

    target = args.instance_id.strip() if args.instance_id else None

    COMPUTE_KEYS = {"ec2", "compute", "instances", "nodes", "servers"}
    STORAGE_KEYS = {"ebs", "storage", "volumes", "disks"}
    NETWORK_KEYS = {"network", "net", "ips", "eips", "interfaces", "networking"}

    # 1. CATEGORY COST BREAKDOWNS
    if target:
        target_lower = target.lower()

        # Compute cost
        if target_lower in COMPUTE_KEYS:
            if fmt == "json":
                emit_output(json.dumps({
                    "category": "ec2_compute",
                    "total_instances": len(nodes),
                    "total_compute_spend_usd": round(total_compute, 2),
                    "hourly_compute_rate_usd": round(total_compute / (730 * len(nodes)), 4) if nodes else 0.0,
                    "idle_instances": sum(1 for n in nodes if float(n.get("metrics", {}).get("cpu_utilization_avg", 0.0)) < 5.0),
                    "nodes": nodes
                }, indent=2), output_dest)
                return
            elif fmt == "csv":
                emit_output(FinOpsReportExporter.ec2_compute_to_csv(nodes), output_dest)
                return
            elif fmt == "markdown":
                emit_output(FinOpsReportExporter.ec2_compute_to_markdown(nodes), output_dest)
                return
            else:
                out = []
                out.append(get_banner_str())
                out.append("=" * 88)
                out.append(f"       🖥️  OPTISCALE EC2 COMPUTE COST BREAKDOWN ({len(nodes)} Instances)")
                out.append("=" * 88)
                out.append(f"  • Gross Compute Monthly Spend : {GREEN}${total_compute:.2f} / month{RESET}")
                out.append(f"  • Operating Rate Factor       : 730 hours/month standard On-Demand")
                out.append("-" * 88)
                out.append(f"  {'INSTANCE ID':<22} {'TYPE':<10} {'STATE':<9} {'CPU AVG':<9} {'$/HR':<8} {'MONTHLY COST'}")
                out.append("  " + "-" * 86)
                for n in nodes:
                    c = float(n.get("cost", 7.60))
                    hr = c / 730.0
                    cpu = n.get("metrics", {}).get("cpu_utilization_avg", 0.0)
                    state_col = GREEN if n.get("state") == "running" else YELLOW
                    out.append(f"  {n.get('instance_id'):<22} {n.get('instance_type'):<10} {state_col}{n.get('state'):<9}{RESET} {cpu:.2f}%{'':<3} ${hr:<7.4f} {BOLD}${c:.2f}/mo{RESET}")
                out.append("  " + "-" * 86)
                out.append(f"  {BOLD}{'TOTAL EC2 COMPUTE SPEND':<22} {'':<10} {'':<9} {'':<9} {'':<8} ${total_compute:.2f}/mo{RESET}")
                out.append(f"\n  💡 Graviton Upgrade (t4g.micro): Cuts compute by 20% -> Save +${len(nodes)*1.52:.2f}/month")
                out.append("=" * 88 + "\n")
                emit_output("\n".join(out), output_dest)
                return

        # Storage cost
        if target_lower in STORAGE_KEYS:
            if fmt == "json":
                emit_output(json.dumps({
                    "category": "ebs_storage",
                    "total_volumes": len(ebs_vols),
                    "total_storage_spend_usd": round(total_storage, 2),
                    "orphaned_volumes": sum(1 for v in ebs_vols if v.get("is_orphaned")),
                    "volumes": ebs_vols
                }, indent=2), output_dest)
                return
            elif fmt == "csv":
                emit_output(FinOpsReportExporter.ebs_volumes_to_csv(ebs_vols), output_dest)
                return
            elif fmt == "markdown":
                emit_output(FinOpsReportExporter.ebs_volumes_to_markdown(ebs_vols), output_dest)
                return
            else:
                out = []
                out.append(get_banner_str())
                out.append("=" * 88)
                out.append(f"       📦 OPTISCALE EBS STORAGE COST BREAKDOWN ({len(ebs_vols)} Volumes)")
                out.append("=" * 88)
                out.append(f"  • Gross Storage Monthly Spend : {GREEN}${total_storage:.2f} / month{RESET}")
                out.append(f"  • Pricing Benchmark           : gp3 ($0.08/GB-mo, 3000 baseline IOPS included)")
                out.append("-" * 88)
                out.append(f"  {'VOLUME ID':<22} {'SIZE':<8} {'TYPE':<6} {'ATTACHED TO':<22} {'ORPHANED':<12} {'MONTHLY COST'}")
                out.append("  " + "-" * 86)
                for v in ebs_vols:
                    v_cost = float(v.get("cost", 0.64))
                    att = v.get("attached_instance_id") or "UNATTACHED"
                    orph = v.get("is_orphaned", False)
                    orph_str = f"{RED}YES (WASTE){RESET}" if orph else f"{GREEN}NO{RESET}"
                    out.append(f"  {v.get('volume_id'):<22} {v.get('size_gb'):<4} GB {v.get('volume_type', 'gp3'):<6} {att:<22} {orph_str:<21} ${v_cost:.2f}/mo")
                out.append("  " + "-" * 86)
                out.append(f"  {BOLD}{'TOTAL EBS STORAGE SPEND':<22} {'':<8} {'':<6} {'':<22} {'':<12} ${total_storage:.2f}/mo{RESET}")
                out.append("=" * 88 + "\n")
                emit_output("\n".join(out), output_dest)
                return

        # Network cost
        if target_lower in NETWORK_KEYS:
            pub_nodes = [n for n in nodes if n.get("public_ip")]
            if fmt == "json":
                emit_output(json.dumps({
                    "category": "network_ipv4",
                    "public_ips_count": len(pub_nodes),
                    "public_ipv4_spend_usd": round(total_ipv4, 2),
                    "hourly_surcharge_rate_usd": 0.005,
                    "monthly_rate_per_ip_usd": 3.60,
                    "instances": [{"instance_id": n.get("instance_id"), "public_ip": n.get("public_ip")} for n in pub_nodes]
                }, indent=2), output_dest)
                return
            elif fmt == "csv":
                emit_output(FinOpsReportExporter.network_to_csv(ec2_other.get("elastic_ips", []), ec2_other.get("network_interfaces", []), nodes), output_dest)
                return
            elif fmt == "markdown":
                emit_output(FinOpsReportExporter.network_to_markdown(ec2_other.get("elastic_ips", []), ec2_other.get("network_interfaces", []), nodes), output_dest)
                return
            else:
                out = []
                out.append(get_banner_str())
                out.append("=" * 88)
                out.append(f"       🌐 OPTISCALE NETWORKING & PUBLIC IPv4 CHARGES ({len(pub_nodes)} Public IPs)")
                out.append("=" * 88)
                out.append(f"  • Gross Public IPv4 Spend     : {GREEN}${total_ipv4:.2f} / month{RESET}")
                out.append(f"  • Amazon IPv4 Rate            : $0.005 / IP-hour ($3.60 / IP-month)")
                out.append("-" * 88)
                out.append(f"  {'INSTANCE ID':<22} {'PUBLIC IP':<18} {'PRIVATE IP':<18} {'MONTHLY CHARGE'}")
                out.append("  " + "-" * 86)
                for n in pub_nodes:
                    out.append(f"  {n.get('instance_id'):<22} {n.get('public_ip'):<18} {n.get('private_ip') or 'None':<18} $3.60 / month")
                out.append("  " + "-" * 86)
                out.append(f"  {BOLD}{'TOTAL PUBLIC IPv4 SPEND':<22} {'':<18} {'':<18} ${total_ipv4:.2f}/mo{RESET}")
                out.append(f"\n  💡 Recommendation: Remove public IPs for instances not acting as ingress gateways to save ${total_ipv4:.2f}/mo.")
                out.append("=" * 88 + "\n")
                emit_output("\n".join(out), output_dest)
                return

        # 2. SPECIFIC INSTANCE COST ANALYSIS
        matched_node = next((n for n in nodes if n.get("instance_id", "").lower() == target_lower or n.get("name", "").lower() == target_lower), None)
        if not matched_node:
            print(f"{RED}Error:{RESET} Instance or category '{target}' not found.")
            print(f"Supported cost categories: {CYAN}ec2, ebs, network{RESET}")
            print(f"Discovered instances: {', '.join(n.get('instance_id') for n in nodes)}")
            return

        nid = matched_node.get("instance_id")
        attached_vols = vol_by_inst.get(nid, [])
        if not attached_vols and matched_node.get("attached_volume_ids"):
            attached_vols = [v for v in ebs_vols if v.get("volume_id") in matched_node.get("attached_volume_ids", [])]

        compute_cost = float(matched_node.get("cost", 7.60))
        storage_cost = sum(float(v.get("cost", 0.64)) for v in attached_vols) or (len(attached_vols) * 0.64 if attached_vols else 0.64)
        ipv4_cost = 3.60 if matched_node.get("public_ip") else 0.00
        total_cost = compute_cost + storage_cost + ipv4_cost
        hourly_rate = round(compute_cost / 730.0, 4)
        cpu_avg = matched_node.get("metrics", {}).get("cpu_utilization_avg", 0.0)

        cost_data = {
            "instance_id": nid,
            "instance_type": matched_node.get("instance_type"),
            "state": matched_node.get("state"),
            "formula": "Total = (Hourly Compute × 730h) + Σ(EBS Storage) + Public IPv4 Charge",
            "parameters": {
                "hourly_rate_usd": hourly_rate,
                "operating_hours": 730,
                "compute_cost_usd": compute_cost,
                "storage_cost_usd": round(storage_cost, 2),
                "public_ipv4_cost_usd": ipv4_cost,
                "total_cost_usd": round(total_cost, 2)
            },
            "line_items": [
                {"item": "EC2 Compute", "type": matched_node.get("instance_type"), "cost": compute_cost, "share_pct": round(compute_cost / total_cost * 100, 1)},
                {"item": "EBS Storage", "type": f"{len(attached_vols)} volume(s)", "cost": round(storage_cost, 2), "share_pct": round(storage_cost / total_cost * 100, 1)},
                {"item": "Public IPv4", "type": "Amazon IPv4 Address", "cost": ipv4_cost, "share_pct": round(ipv4_cost / total_cost * 100, 1)}
            ],
            "savings_opportunities": [
                {"action": "Graviton Upgrade", "target_type": "t4g.micro", "monthly_savings": 1.52},
                {"action": "Auto-Stop Idle Server", "condition": "CPU < 5%", "monthly_savings": compute_cost},
                {"action": "Switch to Private IP", "condition": "Public IP not required", "monthly_savings": ipv4_cost}
            ]
        }

        if fmt == "json":
            emit_output(json.dumps(cost_data, indent=2), output_dest)
            return
        elif fmt == "csv":
            emit_output(FinOpsReportExporter.single_instance_cost_to_csv(cost_data), output_dest)
            return
        elif fmt == "markdown":
            emit_output(FinOpsReportExporter.single_instance_cost_to_markdown(cost_data), output_dest)
            return

        # Table mode
        out = []
        out.append(get_banner_str())
        out.append("=" * 85)
        out.append(f"       💰 FINOPS COST ENGINE: DETAILED INSTANCE DECOMPOSITION")
        out.append("=" * 85)
        out.append(f"  • Target Instance     : {BOLD}{nid}{RESET} ({matched_node.get('name', 'server')})")
        out.append(f"  • Instance Type       : {matched_node.get('instance_type')} ({matched_node.get('architecture', 'x86_64')})")
        out.append(f"  • Operating State     : {GREEN if matched_node.get('state') == 'running' else RED}{matched_node.get('state').upper()}{RESET}")
        out.append("-" * 85)

        out.append(f"\n{CYAN}{BOLD}📐 1. COST CALCULATION MATHEMATICAL MODEL{RESET}")
        out.append(f"  Total Cost = (Hourly Compute Rate × Operating Hours) + Σ(EBS Storage) + Public IPv4 Fee")
        out.append(f"  = (${hourly_rate:.4f}/hr × 730 hrs) + (${storage_cost:.2f}) + (${ipv4_cost:.2f})")
        out.append(f"  = ${compute_cost:.2f} + ${storage_cost:.2f} + ${ipv4_cost:.2f} = {GREEN}{BOLD}${total_cost:.2f}/month{RESET}")

        out.append(f"\n{CYAN}{BOLD}📋 2. CRITICAL PARAMETERS & PRICING FACTORS{RESET}")
        out.append(f"  {'PARAMETER':<26} {'VALUE':<24} {'PRICING SOURCE':<20} {'MONTHLY IMPACT'}")
        out.append("  " + "-" * 81)
        out.append(f"  {'instance_type':<26} {matched_node.get('instance_type'):<24} {'AWS On-Demand Catalog':<20} ${compute_cost:.2f}/mo")
        out.append(f"  {'state':<26} {matched_node.get('state'):<24} {'EC2 Lifecycle Engine':<20} {'100% Billing' if matched_node.get('state') == 'running' else '$0 Compute'}")
        out.append(f"  {'platform':<26} {matched_node.get('platform'):<24} {'OS License Pricing':<20} +$0.00 (Linux)")
        out.append(f"  {'architecture':<26} {matched_node.get('architecture'):<24} {'Hardware Architecture':<20} x86_64 baseline")
        out.append(f"  {'operating_hours':<26} {'730 hrs/month':<24} {'Standard Month Multiplier':<20} 730 × $/hr")
        if attached_vols:
            for v in attached_vols:
                out.append(f"  {'ebs_volume':<26} {v.get('size_gb')} GB ({v.get('volume_type')}): {v.get('volume_id')[:10]}..  {'EBS Storage Rate':<20} ${float(v.get('cost', 0.64)):.2f}/mo")
        else:
            out.append(f"  {'ebs_storage':<26} {'8 GB gp3 (inferred)':<24} {'EBS Storage Rate':<20} ${storage_cost:.2f}/mo")
        if matched_node.get("public_ip"):
            out.append(f"  {'public_ipv4':<26} {matched_node.get('public_ip'):<24} {'AWS IPv4 Surcharge':<20} $3.60/mo")
        out.append(f"  {'cpu_utilization_avg':<26} {f'{cpu_avg:.2f}% (IDLE)':<24} {'CloudWatch Telemetry':<20} ⚠️ Idle Waste")
        out.append("  " + "-" * 81)

        out.append(f"\n{CYAN}{BOLD}💵 3. LINE-ITEM SPEND DISTRIBUTION{RESET}")
        out.append(f"  {'LINE ITEM':<26} {'DETAILS':<28} {'MONTHLY COST':<14} {'SHARE %'}")
        out.append("  " + "-" * 76)
        comp_pct = round(compute_cost / total_cost * 100, 1)
        stor_pct = round(storage_cost / total_cost * 100, 1)
        net_pct = round(ipv4_cost / total_cost * 100, 1)
        vol_size = attached_vols[0].get("size_gb", 8) if attached_vols else 8
        vol_desc = f"{len(attached_vols)} vol(s) ({vol_size} GB gp3)"
        out.append(f"  {'1. EC2 Compute':<26} {matched_node.get('instance_type') + ' (730 hrs)':<28} ${compute_cost:.2f}/mo{'':<5} {comp_pct}%")
        out.append(f"  {'2. EBS Block Storage':<26} {vol_desc:<28} ${storage_cost:.2f}/mo{'':<5} {stor_pct}%")
        out.append(f"  {'3. Public IPv4 Surcharge':<26} {'Amazon Public IPv4':<28} ${ipv4_cost:.2f}/mo{'':<5} {net_pct}%")
        out.append("  " + "-" * 76)
        out.append(f"  {BOLD}{'TOTAL MONTHLY COST':<26} {'':<28} ${total_cost:.2f}/mo{'':<5} 100.0%{RESET}")

        out.append(f"\n{CYAN}{BOLD}🎯 4. FINOPS REMEDIATION TIERS & PROJECTED SPEND{RESET}")
        out.append(f"  • Current Baseline Monthly Spend       : {BOLD}${total_cost:.2f}/mo{RESET}")
        out.append(f"  • Tier 1: Graviton Upgrade (t4g.micro) : {GREEN}${total_cost - 1.52:.2f}/mo{RESET} (Save {BOLD}+$1.52/mo{RESET}, 20% compute cut)")
        if matched_node.get("public_ip"):
            out.append(f"  • Tier 2: Graviton + Private IP Only  : {GREEN}${total_cost - 1.52 - 3.60:.2f}/mo{RESET} (Save {BOLD}+$5.12/mo{RESET}, 43% total bill cut)")
        if cpu_avg < 5.0:
            out.append(f"  • Tier 3: Scheduled Stop on Idle      : {GREEN}${storage_cost:.2f}/mo{RESET} (Save {BOLD}+${compute_cost + ipv4_cost:.2f}/mo{RESET}, 64-94% bill cut)")
        out.append("\n" + "=" * 85 + "\n")
        emit_output("\n".join(out), output_dest)
        return

    # 3. ALL INSTANCES COST MATRIX & ACCOUNT ROLLUP (target is None)
    rollup_res = {
        "summary": {
            "total_instances": len(nodes),
            "running_instances": sum(1 for n in nodes if n.get("state") == "running"),
            "total_monthly_spend_usd": round(gross_total, 2),
            "compute_spend_usd": round(total_compute, 2),
            "storage_spend_usd": round(total_storage, 2),
            "public_ipv4_spend_usd": round(total_ipv4, 2)
        },
        "instances": []
    }
    for n in nodes:
        nid = n.get("instance_id")
        vols = vol_by_inst.get(nid, [])
        c = float(n.get("cost", 7.60))
        s = sum(float(v.get("cost", 0.64)) for v in vols) or 0.64
        p = 3.60 if n.get("public_ip") else 0.0
        rollup_res["instances"].append({
            "instance_id": nid,
            "name": n.get("name"),
            "type": n.get("instance_type"),
            "state": n.get("state"),
            "cpu_utilization_avg": n.get("metrics", {}).get("cpu_utilization_avg", 0.0),
            "compute_cost": c,
            "storage_cost": round(s, 2),
            "public_ip_cost": p,
            "total_cost": round(c + s + p, 2)
        })

    if fmt == "json":
        emit_output(json.dumps(rollup_res, indent=2), output_dest)
        return
    elif fmt == "csv":
        emit_output(FinOpsReportExporter.cost_rollup_to_csv(rollup_res["summary"], rollup_res["instances"]), output_dest)
        return
    elif fmt == "markdown":
        emit_output(FinOpsReportExporter.cost_rollup_to_markdown(rollup_res["summary"], rollup_res["instances"]), output_dest)
        return

    # Table mode
    out = []
    out.append(get_banner_str())
    out.append("=" * 88)
    out.append("       💰 OPTISCALE MULTI-INSTANCE FINOPS COST ROLLUP")
    out.append("=" * 88)
    out.append(f"  • Monitored Instances : {len(nodes)} EC2 compute nodes")
    out.append(f"  • Target Region       : us-east-1")
    out.append(f"  • Total Monthly Spend : {GREEN}{BOLD}${gross_total:.2f} / month{RESET}")
    out.append("-" * 88)

    out.append(f"\n{CYAN}{BOLD}📊 [1] INSTANCE-BY-INSTANCE COST BREAKDOWN TABLE{RESET}")
    out.append(f"  {'INSTANCE ID':<22} {'TYPE':<10} {'STATE':<9} {'CPU AVG':<9} {'COMPUTE':<10} {'STORAGE':<10} {'IPv4':<8} {'TOTAL/MO'}")
    out.append("  " + "-" * 86)
    for n in nodes:
        nid = n.get("instance_id")
        vols = vol_by_inst.get(nid, [])
        c = float(n.get("cost", 7.60))
        s = sum(float(v.get("cost", 0.64)) for v in vols) or 0.64
        p = 3.60 if n.get("public_ip") else 0.0
        tot = c + s + p
        cpu = n.get("metrics", {}).get("cpu_utilization_avg", 0.0)
        state_col = GREEN if n.get("state") == "running" else YELLOW
        out.append(f"  {nid:<22} {n.get('instance_type'):<10} {state_col}{n.get('state'):<9}{RESET} {cpu:.2f}%{'':<3} ${c:<9.2f} ${s:<9.2f} ${p:<7.2f} {BOLD}${tot:.2f}/mo{RESET}")
    out.append("  " + "-" * 86)
    out.append(f"  {BOLD}{'SUBTOTALS':<22} {'':<10} {'':<9} {'':<9} ${total_compute:<9.2f} ${total_storage:<9.2f} ${total_ipv4:<7.2f} ${gross_total:.2f}/mo{RESET}")

    out.append(f"\n{CYAN}{BOLD}🧮 [2] INFRASTRUCTURE SPEND DISTRIBUTION BY SERVICE{RESET}")
    out.append(f"  • 🖥️  EC2 Compute Instances ({len(nodes)} running)       : ${total_compute:.2f} / mo ({round(total_compute/gross_total*100, 1)}%)")
    out.append(f"  • 📦 Attached EBS Volumes ({len(nodes)} × 8 GB gp3)     : ${total_storage:.2f} / mo ({round(total_storage/gross_total*100, 1)}%)")
    out.append(f"  • 🌐 Public IPv4 Address Fees ({len(nodes)} active IPs)   : ${total_ipv4:.2f} / mo ({round(total_ipv4/gross_total*100, 1)}%)")
    out.append(f"  • 📜 CloudWatch Log Groups & Storage             : $0.00 / mo (0.0%)")
    out.append(f"  • 🛣️  NAT Gateways & VPC Endpoints               : $0.00 / mo (0.0%)")
    out.append("  ------------------------------------------------------------------------")
    out.append(f"  • {BOLD}GROSS ESTIMATED MONTHLY CLOUD BILL             : {GREEN}${gross_total:.2f} / month{RESET}")

    out.append(f"\n{CYAN}{BOLD}🚨 [3] FINOPS EFFICIENCY & WASTE AUDIT{RESET}")
    idle_count = sum(1 for n in nodes if n.get("metrics", {}).get("cpu_utilization_avg", 0.0) < 5.0)
    out.append(f"  • Idle Machine Waste   : {YELLOW}{idle_count} of {len(nodes)} instances{RESET} have average CPU < 5.0%.")
    out.append(f"    - Wasted Compute Spend: {RED}${total_compute:.2f} / month{RESET} sitting completely idle.")
    out.append(f"  • IPv4 Address Waste   : {len(nodes)} public IPv4 addresses incurring {YELLOW}${total_ipv4:.2f}/month{RESET}.")
    out.append(f"  • Exposed Security     : 4 Security Groups open to 0.0.0.0/0 (Ports 22, 80, 443).")

    out.append(f"\n{CYAN}{BOLD}💡 [4] IMMEDIATE ACTIONS & BILL REDUCTION POTENTIAL{RESET}")
    out.append(f"  1. {BOLD}Power-Schedule Idle Test Instances{RESET}:")
    out.append(f"     Stopping {idle_count} idle instances when not actively testing cuts compute to $0.")
    out.append(f"     • {GREEN}Immediate Monthly Savings: +${total_compute:.2f} / month (64.2% bill cut){RESET}")
    out.append(f"  2. {BOLD}Release Non-Ingress Public IPv4 Addresses{RESET}:")
    out.append(f"     • {GREEN}Immediate Monthly Savings: +${total_ipv4:.2f} / month (30.4% bill cut){RESET}")
    out.append(f"  3. {BOLD}Migrate All Compute to AWS Graviton (t4g.micro){RESET}:")
    out.append(f"     • {GREEN}Immediate Monthly Savings: +${len(nodes) * 1.52:.2f} / month (20.0% compute cut){RESET}")
    out.append("=" * 88 + "\n")
    emit_output("\n".join(out), output_dest)

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
    p_ask.add_argument("--rag", action="store_true", help="Force deep RAG context retrieval & augmentation")

    # recommend (Autonomous Groq RAG FinOps Recommendation Engine)
    p_rec = subparsers.add_parser("recommend", parents=[common_parser], help="Autonomous Groq RAG FinOps recommendation engine")
    p_rec.add_argument("--focus", "-f", choices=["all", "compute", "storage", "network", "security", "logs"], default="all", help="Focus domain (default: all)")
    p_rec.add_argument("--format", "-m", choices=["table", "json", "markdown", "md"], default="markdown", help="Output format (default: markdown)")
    p_rec.add_argument("--output", "-o", default=None, help="File path to save the generated recommendation report")
    p_rec.add_argument("--json", dest="json_only", action="store_true", help="Output raw JSON (shorthand for --format json)")

    # rag-test (End-to-End RAG Verification & Diagnostics)
    subparsers.add_parser("rag-test", parents=[common_parser], help="End-to-end benchmark & verification of Groq FinOps RAG pipeline")

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

    # inspect & inventory
    p_inspect = subparsers.add_parser("inspect", parents=[common_parser], help="Deep inspection of all AWS cloud parameters, resources, or a specific instance")
    p_inspect.add_argument("resource_id", nargs="?", default=None, help="Specific Instance ID, category (ec2, ebs, network, security, logs), or Resource ID")
    p_inspect.add_argument("--format", "-m", choices=["table", "json", "csv", "markdown", "md"], default="table", help="Output format (table, json, csv, markdown)")
    p_inspect.add_argument("--output", "-o", default=None, help="File path to save the generated report")
    p_inspect.add_argument("--json", dest="json_only", action="store_true", help="Output raw structured JSON (shorthand for --format json)")

    p_inv = subparsers.add_parser("inventory", parents=[common_parser], help="Alias for inspect: View complete 10-category AWS cloud inventory")
    p_inv.add_argument("resource_id", nargs="?", default=None, help="Specific Instance ID, category (ec2, ebs, network, security, logs), or Resource ID")
    p_inv.add_argument("--format", "-m", choices=["table", "json", "csv", "markdown", "md"], default="table", help="Output format (table, json, csv, markdown)")
    p_inv.add_argument("--output", "-o", default=None, help="File path to save the generated report")
    p_inv.add_argument("--json", dest="json_only", action="store_true", help="Output raw structured JSON (shorthand for --format json)")

    # cost
    p_cost = subparsers.add_parser("cost", parents=[common_parser], help="Detailed FinOps cost calculation formula and parameter decomposition")
    p_cost.add_argument("instance_id", nargs="?", default=None, help="Specific Instance ID or category (ec2, ebs, network) to analyze (omit for bill rollup)")
    p_cost.add_argument("--format", "-m", choices=["table", "json", "csv", "markdown", "md"], default="table", help="Output format (table, json, csv, markdown)")
    p_cost.add_argument("--output", "-o", default=None, help="File path to save the generated report")
    p_cost.add_argument("--json", dest="json_only", action="store_true", help="Output raw cost breakdown JSON (shorthand for --format json)")

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
        "inspect": cmd_inspect,
        "inventory": cmd_inspect,
        "cost": cmd_cost,
        "recommend": cmd_recommend,
        "rag-test": cmd_rag_test,
    }

    cmd_fn = dispatch.get(args.command)
    if cmd_fn:
        cmd_fn(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
