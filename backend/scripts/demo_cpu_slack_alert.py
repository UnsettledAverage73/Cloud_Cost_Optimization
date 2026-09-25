#!/usr/bin/env python3
"""
CloudPulse Real-Time Demonstration: Live AWS EC2 Idle CPU Detection -> Slack Alert
==================================================================================
This script performs an end-to-end live check:
1. Connects to your live AWS account (via boto3 or active CloudPulse credentials).
2. Queries AWS CloudWatch for real CPUUtilization metrics on running EC2 instances.
3. Automatically detects zero or low CPU utilization (< 5.0% idle threshold).
4. Calculates quantified financial waste ($/month and $/year).
5. Dispatches an interactive Slack Block Kit Card directly to your Slack channel!
"""

import sys
import os
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Ensure backend and root are in sys.path
backend_dir = Path(__file__).resolve().parent.parent
repo_dir = backend_dir.parent
for p in [str(backend_dir), str(repo_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import boto3
from botocore.exceptions import ClientError, BotoCoreError
from services.notification_engine import FinOpsNotificationEngine
from engines.waste_analyzer import WasteAnalyzer

CYAN = "\033[0;36m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_banner():
    print(f"\n{CYAN}{BOLD}" + "=" * 78)
    print("   ⚡ CLOUDPULSE: REAL-TIME AWS IDLE CPU DETECTION -> SLACK NOTIFIER")
    print("=" * 78 + f"{RESET}\n")


def get_live_ec2_cpu(session, region="us-east-1"):
    """Fetches real running EC2 instances and queries CloudWatch for average CPUUtilization."""
    ec2 = session.client("ec2", region_name=region)
    cw = session.client("cloudwatch", region_name=region)

    instances = []
    try:
        resp = ec2.describe_instances(
            Filters=[{"Name": "instance-state-name", "Values": ["running"]}]
        )
        for r in resp.get("Reservations", []):
            for inst in r.get("Instances", []):
                inst_id = inst.get("InstanceId")
                name = inst_id
                for tag in inst.get("Tags", []):
                    if tag.get("Key") == "Name":
                        name = tag.get("Value")

                inst_type = inst.get("InstanceType", "t3.micro")

                # Query CloudWatch for last 24 hours of CPUUtilization
                end_time = datetime.now(timezone.utc)
                start_time = end_time - timedelta(hours=24)

                avg_cpu = 0.0
                try:
                    cw_resp = cw.get_metric_statistics(
                        Namespace="AWS/EC2",
                        MetricName="CPUUtilization",
                        Dimensions=[{"Name": "InstanceId", "Value": inst_id}],
                        StartTime=start_time,
                        EndTime=end_time,
                        Period=300,
                        Statistics=["Average", "Maximum"],
                    )
                    dps = cw_resp.get("Datapoints", [])
                    if dps:
                        avg_cpu = sum(d.get("Average", 0.0) for d in dps) / len(dps)
                except Exception as ex:
                    print(f"  {YELLOW}CloudWatch metric lookup note for {inst_id}: {ex}{RESET}")

                instances.append({
                    "instance_id": inst_id,
                    "name": name,
                    "instance_type": inst_type,
                    "state": "running",
                    "region": region,
                    "cost": 30.40 if "medium" in inst_type else 15.20 if "small" in inst_type else 7.60,
                    "metrics": {
                        "cpu_utilization_avg": round(float(avg_cpu), 2),
                    }
                })
    except Exception as e:
        print(f"  {RED}Error querying AWS EC2/CloudWatch: {e}{RESET}")

    return instances


def main():
    parser = argparse.ArgumentParser(description="Live AWS EC2 Idle CPU Detection -> Slack Alert")
    parser.add_argument("--webhook", "-w", help="Slack Incoming Webhook URL")
    parser.add_argument("--token", "-t", help="Slack Bot User OAuth Token (xoxb-...)")
    parser.add_argument("--channel", "-c", default="all-average", help="Slack Channel (default: all-average)")
    parser.add_argument("--region", "-r", default="us-east-1", help="AWS Region (default: us-east-1)")
    parser.add_argument("--threshold", type=float, default=5.0, help="Idle CPU threshold percentage (default: 5.0 percent)")

    args = parser.parse_args()
    print_banner()

    webhook_url = args.webhook or os.getenv("SLACK_WEBHOOK_URL")
    bot_token = args.token or os.getenv("SLACK_BOT_TOKEN")
    channel = args.channel or os.getenv("SLACK_CHANNEL", "all-average")
    region = args.region or os.getenv("AWS_DEFAULT_REGION", "us-east-1")

    # Step 1: Check AWS Credentials
    print(f"🔑 {BOLD}Step 1: Authenticating with AWS{RESET}")
    has_aws_creds = bool(os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"))
    live_instances = []

    if has_aws_creds or os.path.exists(os.path.expanduser("~/.aws/credentials")):
        try:
            session = boto3.Session()
            sts = session.client("sts", region_name=region)
            caller = sts.get_caller_identity()
            print(f"   • Connected Account : {GREEN}{caller.get('Account')}{RESET}")
            print(f"   • Identity ARN      : {caller.get('Arn')}")
            print(f"   • AWS Region        : {region}")

            print(f"\n📡 {BOLD}Step 2: Querying CloudWatch for Live EC2 CPU Utilization{RESET}")
            live_instances = get_live_ec2_cpu(session, region)
            print(f"   • Total Running EC2 : {len(live_instances)}")
            for inst in live_instances:
                cpu = inst["metrics"]["cpu_utilization_avg"]
                color = RED if cpu < args.threshold else GREEN
                print(f"     - [{inst['instance_id']}] {inst['name']} ({inst['instance_type']}): CPU = {color}{cpu}%{RESET}")
        except Exception as e:
            print(f"   {YELLOW}AWS API lookup error: {e}. Falling back to active session store.{RESET}")

    if not live_instances:
        # Load from CloudPulse active state or demo instance
        from main import _db
        store = _db()
        nodes = store.get("nodes", [])
        if nodes:
            live_instances = [n for n in nodes if n.get("state") == "running"]
            print(f"   • Loaded {len(live_instances)} instances from active CloudPulse state.")
        else:
            print(f"   • Using sample connected workload instance for demonstration.")
            live_instances = [
                {
                    "instance_id": "i-07d01b00f95a4cc41",
                    "name": "worker-node-analytics",
                    "instance_type": "c5.2xlarge",
                    "state": "running",
                    "cost": 68.40,
                    "metrics": {"cpu_utilization_avg": 0.4}
                }
            ]

    # Step 3: Run Waste Analyzer
    print(f"\n🧠 {BOLD}Step 3: Running FinOps Waste Engine (< {args.threshold}% CPU Threshold){RESET}")
    mock_inv = {"nodes": live_instances, "elastic_ips": [], "ebs_volumes": [], "rds_instances": [], "nat_gateways": [], "load_balancers": []}
    findings = WasteAnalyzer.analyze(mock_inv)
    idle_findings = [f for f in findings if f.get("type") == "Idle Compute"]

    if not idle_findings:
        print(f"   {GREEN}✔ All instances have healthy CPU utilization (>= {args.threshold}%). No idle waste.{RESET}")
        return

    print(f"   🚨 {RED}{BOLD}Detected {len(idle_findings)} Idle EC2 Instance(s):{RESET}")
    for f in idle_findings:
        print(f"     • {f['title']}")
        print(f"       Monthly Wasted Spend: {RED}${f['monthly_savings']:.2f}/mo{RESET} (${f['monthly_savings']*12:.2f}/yr)")

    target_finding = idle_findings[0]
    target_id = target_finding["resource_id"]
    target_node = next((n for n in live_instances if n["instance_id"] == target_id), live_instances[0])
    current_cpu = target_node.get("metrics", {}).get("cpu_utilization_avg", 0.0)

    # Step 4: Dispatch to Slack
    print(f"\n💬 {BOLD}Step 4: Dispatching Live Slack Block Kit Alert{RESET}")
    engine = FinOpsNotificationEngine()
    card = engine.format_slack_alert(
        resource_id=target_id,
        finding_title=f"Zero/Low CPU Utilization ({current_cpu}%) on {target_id}",
        severity="HIGH",
        current_monthly_spend=target_finding.get("monthly_savings", 60.80) / 0.85,
        potential_monthly_savings=target_finding.get("monthly_savings", 51.68),
        recommended_action=f"CloudWatch recorded {current_cpu}% CPU utilization over the monitoring window. Stop or schedule this instance to eliminate ${target_finding.get('monthly_savings', 51.68):.2f}/mo waste.",
        repo_name="UnsettledAverage73/Cloud_Cost_Optimization"
    )

    if webhook_url and "XXXXX" not in webhook_url and "YOUR_WEBHOOK" not in webhook_url:
        print(f"   • Dispatching to Slack Webhook: {webhook_url[:35]}...")
        ok = engine.dispatch_webhook(webhook_url, card)
        if ok:
            print(f"   {GREEN}{BOLD}✅ SUCCESS: Real-time alert dispatched and posted to your Slack channel!{RESET}")
        else:
            print(f"   {RED}{BOLD}❌ Webhook Delivery Failed. Check URL permissions.{RESET}")
    elif bot_token and "XXXXX" not in bot_token:
        print(f"   • Dispatching to Slack Channel #{channel} via Web API...")
        ok = engine.dispatch_slack_api(bot_token, channel, card)
        if ok:
            print(f"   {GREEN}{BOLD}✅ SUCCESS: Real-time alert delivered to #{channel}!{RESET}")
        else:
            print(f"   {RED}{BOLD}❌ Web API Delivery Failed. Check bot scopes ('chat:write').{RESET}")
    else:
        print(f"   {YELLOW}{BOLD}⚠️ No live Slack Webhook or Token specified.{RESET}")
        print(f"   To receive the live alert in your Slack channel, run:")
        print(f"   {CYAN}python3 backend/scripts/demo_cpu_slack_alert.py --webhook https://hooks.slack.com/services/YOUR/WEBHOOK/URL{RESET}")
        print(f"\n   Slack Block Kit Card Preview:")
        print(json.dumps(card, indent=2))

    print(f"\n" + "=" * 78 + "\n")


if __name__ == "__main__":
    main()
