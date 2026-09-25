"""
CloudPulse Global State & Active Inventory Management
Centralized shared store for live cloud inventory, telemetry, and fleet-wide caches.
"""

from typing import Dict, Any
from pathlib import Path

REALTIME_STORE: Dict[str, Any] = {
    "nodes": [],
    "ebs_volumes": [],
    "ebs_snapshots": [],
    "s3_buckets": [],
    "rds_instances": [],
    "rds_clusters": [],
    "rds_manual_snapshots": [],
    "elastic_ips": [],
    "nat_gateways": [],
    "vpc_endpoints": [],
    "network_interfaces": [],
    "load_balancers": [],
    "security_groups": [],
    "amis": [],
    "cloudwatch_log_groups": [],
    "daily_spend": [],
    "service_breakdown": [],
    "summary": {
        "monthly_spend": 0.0,
        "total_nodes": 0,
        "running_nodes": 0,
        "stopped_nodes": 0,
        "wasted_monthly_spend": 0.0,
        "critical_security_risks": 0,
        "last_synced": None,
    },
    "applied_optimizations": [],
    "telemetry": [],
    "metadata": {
        "region": "us-east-1",
        "timestamp": None,
        "organization": "CloudPulse Realtime",
    },
}


def get_realtime_store() -> Dict[str, Any]:
    """Returns the shared in-memory realtime inventory store."""
    return REALTIME_STORE


def resolve_active_inventory() -> dict:
    """
    Resolves active cloud inventory:
    Checks fleet_cache for live scanned inventory first, falls back to realtime store.
    """
    try:
        try:
            from collectors.fleet_cache import fleet_cache
        except ImportError:
            from backend.collectors.fleet_cache import fleet_cache

        cached = fleet_cache.get("fleet_summary")
        if cached and isinstance(cached, dict):
            for acc in cached.get("scanned_accounts", []):
                if acc.get("status") == "success" and acc.get("inventory"):
                    return acc["inventory"]
    except Exception:
        pass
    return get_realtime_store()
