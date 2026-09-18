#!/usr/bin/env python3
import sys
import os
import time
import json
import argparse
import urllib.request
import urllib.error

# Ensure parent paths are available for zero-config CLI invocation
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
ROOT_DIR = os.path.abspath(os.path.join(BACKEND_DIR, ".."))
for p in [CURRENT_DIR, BACKEND_DIR, ROOT_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from collector import MultiOSCollector
    from cloud_detector import CloudInstanceDetector
except ImportError:
    try:
        from agent.collector import MultiOSCollector
        from agent.cloud_detector import CloudInstanceDetector
    except ImportError:
        from backend.agent.collector import MultiOSCollector
        from backend.agent.cloud_detector import CloudInstanceDetector

def print_banner():
    print(r"""
   ____ _                 _ ____        _           
  / ___| | ___  _   _  __| |  _ \ _   _| |___  ___  
 | |   | |/ _ \| | | |/ _` | |_) | | | | / __|/ _ \ 
 | |___| | (_) | |_| | (_| |  __/| |_| | \__ \  __/ 
  \____|_|\___/ \__,_|\__,_|_|    \__,_|_|___/\___| 
      Multi-OS In-Guest Telemetry & FinOps Agent    
""")

def cmd_status(args):
    print_banner()
    cloud_info = CloudInstanceDetector.detect()
    telemetry = MultiOSCollector.collect_full_telemetry()

    os_info = telemetry["os"]
    cpu = telemetry["cpu"]
    mem = telemetry["memory"]
    disk = telemetry["disk"]

    print("=" * 65)
    print(" 🌐 CLOUD INFRASTRUCTURE")
    print("=" * 65)
    print(f"  • Provider         : {cloud_info['provider'].upper()}")
    print(f"  • Instance ID      : {cloud_info['instance_id']}")
    print(f"  • Instance Type    : {cloud_info['instance_type']}")
    print(f"  • Region / Zone    : {cloud_info['region']} ({cloud_info['availability_zone']})")

    print("\n" + "=" * 65)
    print(" 🖥️  OPERATING SYSTEM & HARDWARE")
    print("=" * 65)
    print(f"  • OS Family        : {os_info['os_type'].upper()} ({os_info['system']} {os_info['release']})")
    print(f"  • Architecture     : {os_info['architecture']}")
    print(f"  • Hostname         : {os_info['hostname']}")
    print(f"  • Python Runtime   : {os_info['python_version']}")

    print("\n" + "=" * 65)
    print(" 📊 IN-GUEST RESOURCE TELEMETRY")
    print("=" * 65)
    print(f"  • CPU Utilization  : {cpu['utilization_percent']}% ({cpu['logical_cores']} Cores)")
    print(f"  • Memory (RAM)     : {mem['used_mb']} MB / {mem['total_mb']} MB ({mem['percent_used']}% used)")
    print(f"  • Available RAM    : {mem['available_mb']} MB")
    print(f"  • Root Disk Mount  : {disk['used_gb']} GB / {disk['total_gb']} GB ({disk['percent_used']}% used)")

    print("\n" + "=" * 65)
    print(" 🔍 TOP PROCESSES BY FOOTPRINT (UNIT COST FORENSICS)")
    print("=" * 65)
    print(f"  {'PID':<8} {'USER':<12} {'CPU%':<8} {'RAM%':<8} {'PROCESS NAME'}")
    print("  " + "-" * 55)
    for p in telemetry.get("top_processes", []):
        print(f"  {p['pid']:<8} {p['user']:<12} {p['cpu_percent']:<8} {p['memory_percent']:<8} {p['name']}")
    print("=" * 65)

def cmd_scan(args):
    cloud_info = CloudInstanceDetector.detect()
    telemetry = MultiOSCollector.collect_full_telemetry()
    payload = {
        "cloud": cloud_info,
        "telemetry": telemetry
    }
    print(json.dumps(payload, indent=2))

def push_telemetry(endpoint: str, token: str) -> bool:
    cloud_info = CloudInstanceDetector.detect()
    telemetry = MultiOSCollector.collect_full_telemetry()

    payload = {
        "token": token,
        "cloud": cloud_info,
        "telemetry": telemetry
    }
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=data_bytes,
        headers={"Content-Type": "application/json", "User-Agent": "CloudPulse-MultiOS-Agent/2.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            res = response.read().decode("utf-8")
            return response.status == 200
    except Exception as e:
        print(f"Failed to push telemetry to {endpoint}: {e}")
        return False

def cmd_push(args):
    print(f"Pushing host telemetry to {args.endpoint}...")
    success = push_telemetry(endpoint=args.endpoint, token=args.token)
    if success:
        print("✅ Host telemetry pushed successfully to TimescaleDB!")
    else:
        print("❌ Telemetry push failed.")
        sys.exit(1)

def cmd_daemon(args):
    print_banner()
    print(f"🚀 Starting CloudPulse Multi-OS Agent Daemon...")
    print(f"Target Endpoint : {args.endpoint}")
    print(f"Push Interval   : {args.interval} seconds")
    print("Press CTRL+C to terminate.\n")

    while True:
        try:
            t_now = time.strftime("%Y-%m-%d %H:%M:%S")
            success = push_telemetry(endpoint=args.endpoint, token=args.token)
            status_tag = "✅ PUSHED" if success else "❌ FAILED"
            print(f"[{t_now}] {status_tag} in-guest telemetry to {args.endpoint}")
            time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nShutting down CloudPulse agent gracefully.")
            break
        except Exception as e:
            print(f"Unexpected error in daemon loop: {e}")
            time.sleep(args.interval)

def main():
    parser = argparse.ArgumentParser(
        description="CloudPulse Multi-OS Host Telemetry & Optimization Agent CLI"
    )
    subparsers = parser.add_subparsers(dest="command", help="Agent command to execute")

    # Command: status
    subparsers.add_parser("status", help="Display real-time OS, cloud metadata, RAM, CPU, and process tables")

    # Command: scan
    subparsers.add_parser("scan", help="Output full JSON snapshot of host telemetry")

    # Command: push
    push_parser = subparsers.add_parser("push", help="Push single telemetry snapshot to CloudPulse backend")
    push_parser.add_argument("--endpoint", default="http://localhost:8000/api/v2/agent/ingest", help="Backend ingestion URL")
    push_parser.add_argument("--token", default="cp-agent-token-demo", help="CloudPulse Agent Authentication Token")

    # Command: daemon
    daemon_parser = subparsers.add_parser("daemon", help="Run in background daemon mode sending metrics on schedule")
    daemon_parser.add_argument("--endpoint", default="http://localhost:8000/api/v2/agent/ingest", help="Backend ingestion URL")
    daemon_parser.add_argument("--token", default="cp-agent-token-demo", help="CloudPulse Agent Authentication Token")
    daemon_parser.add_argument("--interval", type=int, default=60, help="Metric collection interval in seconds (default: 60)")

    args = parser.parse_args()
    if not args.command or args.command == "status":
        cmd_status(args)
    elif args.command == "scan":
        cmd_scan(args)
    elif args.command == "push":
        cmd_push(args)
    elif args.command == "daemon":
        cmd_daemon(args)

if __name__ == "__main__":
    main()
