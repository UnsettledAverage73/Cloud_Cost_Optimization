import logging
from typing import Any, Dict, List

logger = logging.getLogger("finops.engines.waste")


class WasteAnalyzer:
    """
    Detects immediate orphaned, idle, and abandoned AWS assets causing direct financial waste.
    """

    @staticmethod
    def analyze(inventory: Dict[str, Any]) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []

        # 1. Unattached Elastic IPs ($3.60/month per address)
        for eip in inventory.get("elastic_ips", []):
            if eip.get("is_unattached"):
                ip = eip.get("public_ip", "unknown")
                findings.append({
                    "id": f"waste-eip-{ip.replace('.', '-')}",
                    "resource_id": ip,
                    "resource_type": "Elastic IP",
                    "category": "Network Waste",
                    "type": "Orphaned Resource",
                    "title": f"Release Unattached Elastic IP ({ip})",
                    "description": "AWS charges $0.005/hr ($3.60/mo) for unassociated public IPv4 addresses.",
                    "monthly_savings": 3.60,
                    "savings": 3.60,
                    "effort": "Quick Win",
                    "action": "release_eip",
                    "action_type": "release_eip",
                    "severity": "MEDIUM",
                    "risk": "NONE",
                })

        # 2. Detached / Orphaned EBS Volumes
        for vol in inventory.get("ebs_volumes", []):
            if vol.get("is_orphaned"):
                vol_id = vol.get("volume_id", "unknown")
                size_gb = vol.get("size_gb", 0)
                cost = vol.get("cost", round(size_gb * 0.08, 2))
                findings.append({
                    "id": f"waste-vol-{vol_id}",
                    "resource_id": vol_id,
                    "resource_type": "EBS Volume",
                    "category": "Storage Waste",
                    "type": "Orphaned Storage",
                    "title": f"Delete Unattached EBS Volume ({vol_id})",
                    "description": f"Detached {size_gb} GB volume is incurring continuous monthly storage charges without active workload attachment.",
                    "monthly_savings": cost,
                    "savings": cost,
                    "effort": "Quick Win",
                    "action": "delete_volume",
                    "action_type": "delete_volume",
                    "severity": "HIGH",
                    "risk": "LOW",
                })

        # 3. Idle Running EC2 Instances (Average CPU < 5% over 7 days)
        for node in inventory.get("nodes", []):
            if node.get("state") == "running":
                metrics = node.get("metrics", {})
                avg_cpu = metrics.get("cpu_utilization_avg", 50.0)
                if avg_cpu < 5.0:
                    cost = node.get("cost", 30.0)
                    node_id = node.get("instance_id")
                    name = node.get("name", node_id)
                    findings.append({
                        "id": f"waste-ec2-idle-{node_id}",
                        "resource_id": node_id,
                        "resource_type": "EC2 Instance",
                        "category": "Compute Inefficiency",
                        "type": "Idle Compute",
                        "title": f"Stop or Terminate Idle Instance {name} ({node_id})",
                        "description": f"7-day average CPU utilization is {avg_cpu}% (< 5%). Stop instance when idle to eliminate hourly compute billing.",
                        "monthly_savings": round(cost * 0.85, 2),
                        "savings": round(cost * 0.85, 2),
                        "effort": "Low",
                        "action": "stop_instance",
                        "action_type": "stop_instance",
                        "severity": "HIGH",
                        "risk": "MEDIUM",
                    })

        # 4. Idle RDS Databases (0 Active Connections)
        for rds in inventory.get("rds_instances", []):
            if rds.get("zero_connections") and rds.get("status") == "available":
                db_id = rds.get("db_instance_identifier")
                cost = rds.get("cost", 50.0)
                findings.append({
                    "id": f"waste-rds-idle-{db_id}",
                    "resource_id": db_id,
                    "resource_type": "RDS Instance",
                    "category": "Database Waste",
                    "type": "Idle Database",
                    "title": f"Stop Idle RDS Database ({db_id})",
                    "description": "RDS instance recorded 0 client connections over the past 7 days while accumulating full hourly billing.",
                    "monthly_savings": round(cost * 0.80, 2),
                    "savings": round(cost * 0.80, 2),
                    "effort": "Medium",
                    "action": "stop_rds_instance",
                    "action_type": "stop_rds_instance",
                    "severity": "HIGH",
                    "risk": "MEDIUM",
                })

        # 5. Idle Application Load Balancers (0 Healthy Targets)
        for lb in inventory.get("load_balancers", []):
            if lb.get("is_idle") and lb.get("state") == "active":
                lb_arn = lb.get("load_balancer_arn", "")
                lb_name = lb.get("name", "unknown")
                cost = lb.get("estimated_monthly_cost", 22.50)
                findings.append({
                    "id": f"waste-alb-idle-{lb_name}",
                    "resource_id": lb_name,
                    "resource_type": "Load Balancer",
                    "category": "Network Waste",
                    "type": "Idle Load Balancer",
                    "title": f"Delete Unused Load Balancer ({lb_name})",
                    "description": "Load balancer has no registered healthy targets, incurring base hourly charges (~$22.50/mo) with zero traffic.",
                    "monthly_savings": cost,
                    "savings": cost,
                    "effort": "Low",
                    "action": "delete_load_balancer",
                    "action_type": "delete_load_balancer",
                    "severity": "MEDIUM",
                    "risk": "LOW",
                })

        # 6. Stale EBS Snapshots (> 90 Days Old)
        for snap in inventory.get("ebs_snapshots", []):
            if snap.get("is_stale"):
                snap_id = snap.get("snapshot_id")
                age_days = snap.get("age_days", 90)
                cost = snap.get("cost", 5.0)
                findings.append({
                    "id": f"waste-snap-stale-{snap_id}",
                    "resource_id": snap_id,
                    "resource_type": "EBS Snapshot",
                    "category": "Storage Waste",
                    "type": "Stale Snapshot",
                    "title": f"Prune Stale Snapshot ({snap_id})",
                    "description": f"Snapshot is {age_days} days old. Prune redundant snapshots exceeding standard backup retention windows.",
                    "monthly_savings": cost,
                    "savings": cost,
                    "effort": "Quick Win",
                    "action": "delete_snapshot",
                    "action_type": "delete_snapshot",
                    "severity": "LOW",
                    "risk": "LOW",
                })

        # 7. CloudWatch Log Groups with "Never Expire" Retention
        for lg in inventory.get("cloudwatch_log_groups", []):
            if lg.get("is_never_expire"):
                lg_name = lg.get("log_group_name")
                cost = lg.get("estimated_monthly_cost", 1.0)
                savings = max(1.50, round(cost * 0.60, 2))
                findings.append({
                    "id": f"waste-cw-log-{abs(hash(lg_name)) % 1000000}",
                    "resource_id": lg_name,
                    "resource_type": "CloudWatch Log Group",
                    "category": "Observability Waste",
                    "type": "Log Retention",
                    "title": f"Set 30-Day Retention on Log Group ({lg_name})",
                    "description": "Log group is set to Never Expire, continuously accumulating storage charges without automated pruning.",
                    "monthly_savings": savings,
                    "savings": savings,
                    "effort": "Quick Win",
                    "action": "set_log_retention",
                    "action_type": "set_log_retention",
                    "severity": "LOW",
                    "risk": "NONE",
                })

        return sorted(findings, key=lambda f: f["monthly_savings"], reverse=True)
