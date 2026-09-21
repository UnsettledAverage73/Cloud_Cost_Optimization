import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from collectors.base import AWSBaseCollector

logger = logging.getLogger("finops.collectors.cloudwatch")

LOG_STORAGE_RATE_PER_GB = 0.03


class CloudWatchCollector(AWSBaseCollector):
    """
    Collects CloudWatch Log Groups (retention policies and storage bytes)
    and batch metric telemetry for EC2 instances and NAT Gateways.
    """

    def collect(self) -> Dict[str, Any]:
        log_groups = self.collect_log_groups()
        never_expire_count = sum(1 for lg in log_groups if lg["is_never_expire"])
        total_stored_gb = round(sum(lg["stored_gb"] for lg in log_groups), 2)
        total_monthly_cost = round(sum(lg["estimated_monthly_cost"] for lg in log_groups), 2)

        return {
            "log_groups": log_groups,
            "total_log_groups": len(log_groups),
            "never_expire_count": never_expire_count,
            "total_stored_gb": total_stored_gb,
            "total_log_storage_cost": total_monthly_cost,
        }

    def collect_log_groups(self) -> List[Dict[str, Any]]:
        raw_groups = self.paginate("logs", "describe_log_groups", "logGroups")
        log_groups: List[Dict[str, Any]] = []

        for lg in raw_groups:
            name = lg.get("logGroupName", "unknown")
            stored_bytes = lg.get("storedBytes", 0)
            stored_gb = round(stored_bytes / (1024 ** 3), 3)
            retention = lg.get("retentionInDays")
            is_never_expire = (retention is None)
            monthly_cost = round(stored_gb * LOG_STORAGE_RATE_PER_GB, 2)

            log_groups.append({
                "log_group_name": name,
                "stored_bytes": stored_bytes,
                "stored_gb": stored_gb,
                "retention_in_days": retention,
                "is_never_expire": is_never_expire,
                "arn": lg.get("arn"),
                "estimated_monthly_cost": monthly_cost,
            })

        return log_groups

    def enrich_instances_with_metrics(
        self, instances: List[Dict[str, Any]], days: int = 14
    ) -> List[Dict[str, Any]]:
        """
        Enriches running EC2 instances with 14-day average/peak CPU and CWAgent guest memory metrics.
        """
        cw = self.get_client("cloudwatch")
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=days)
        period = 86400

        for inst in instances:
            if inst.get("state") != "running":
                inst["metrics"] = {
                    "cpu_utilization_avg": 0.0,
                    "cpu_utilization_max": 0.0,
                    "mem_utilization_avg": 0.0,
                    "mem_utilization_max": 0.0,
                    "has_memory_metrics": False,
                    "observation_days": days,
                    "net_in_mb": 0.0,
                    "net_out_mb": 0.0,
                }
                continue

            inst_id = inst.get("instance_id")
            avg_cpu = 15.0
            max_cpu = 30.0
            try:
                cpu_resp = cw.get_metric_statistics(
                    Namespace="AWS/EC2",
                    MetricName="CPUUtilization",
                    Dimensions=[{"Name": "InstanceId", "Value": inst_id}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=period,
                    Statistics=["Average", "Maximum"],
                )
                datapoints = cpu_resp.get("Datapoints", [])
                if datapoints:
                    avg_cpu = sum(p.get("Average", 0) for p in datapoints) / len(datapoints)
                    max_cpu = max(p.get("Maximum", 0) for p in datapoints)
            except Exception as ex:
                logger.warning(f"Could not fetch CloudWatch CPU metrics for instance {inst_id}: {ex}")

            # Attempt to fetch in-guest Memory Utilization from CWAgent namespace
            avg_mem = None
            max_mem = None
            has_mem = False
            try:
                mem_resp = cw.get_metric_statistics(
                    Namespace="CWAgent",
                    MetricName="mem_used_percent",
                    Dimensions=[{"Name": "InstanceId", "Value": inst_id}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=period,
                    Statistics=["Average", "Maximum"],
                )
                mem_datapoints = mem_resp.get("Datapoints", [])
                if mem_datapoints:
                    avg_mem = sum(p.get("Average", 0) for p in mem_datapoints) / len(mem_datapoints)
                    max_mem = max(p.get("Maximum", 0) for p in mem_datapoints)
                    has_mem = True
            except Exception:
                pass

            inst["metrics"] = {
                "cpu_utilization_avg": round(float(avg_cpu), 2),
                "cpu_utilization_max": round(float(max_cpu), 2),
                "mem_utilization_avg": round(float(avg_mem), 2) if avg_mem is not None else None,
                "mem_utilization_max": round(float(max_mem), 2) if max_mem is not None else None,
                "has_memory_metrics": has_mem,
                "observation_days": days,
            }

        return instances

    def evaluate_nat_gateways_traffic(
        self, nat_gateways: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Checks 7-day byte transfer for NAT Gateways to identify completely idle ones.
        """
        cw = self.get_client("cloudwatch")
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=7)

        for nat in nat_gateways:
            nat_id = nat.get("nat_gateway_id")
            try:
                resp = cw.get_metric_statistics(
                    Namespace="AWS/NATGateway",
                    MetricName="BytesInFromDestination",
                    Dimensions=[{"Name": "NatGatewayId", "Value": nat_id}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=86400 * 7,
                    Statistics=["Sum"],
                )
                datapoints = resp.get("Datapoints", [])
                total_bytes = sum(p.get("Sum", 0) for p in datapoints) if datapoints else 0
                total_gb = round(total_bytes / (1024 ** 3), 2)

                nat["traffic_7d_gb"] = total_gb
                nat["is_idle"] = total_gb < 0.1  # Less than 100MB over a week
            except Exception:
                nat["traffic_7d_gb"] = 0.0
                nat["is_idle"] = False

        return nat_gateways
