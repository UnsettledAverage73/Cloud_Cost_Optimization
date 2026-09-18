import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import boto3

from collectors.ec2_collector import EC2Collector
from collectors.ebs_collector import EBSCollector
from collectors.s3_collector import S3Collector
from collectors.rds_collector import RDSCollector
from collectors.network_collector import NetworkCollector
from collectors.cloudwatch_collector import CloudWatchCollector
from collectors.cost_explorer_collector import CostExplorerCollector

logger = logging.getLogger("finops.orchestrator")


class AWSDataIngestionOrchestrator:
    """
    Coordinates and executes multi-service AWS telemetry collection,
    enriches resources with CloudWatch performance statistics, and
    compiles a unified FinOps inventory.
    """

    def __init__(self, session: boto3.Session, region: Optional[str] = None):
        self.session = session
        self.region = region or session.region_name or "us-east-1"

        self.ec2 = EC2Collector(session, self.region)
        self.ebs = EBSCollector(session, self.region)
        self.s3 = S3Collector(session, self.region)
        self.rds = RDSCollector(session, self.region)
        self.network = NetworkCollector(session, self.region)
        self.cloudwatch = CloudWatchCollector(session, self.region)
        self.cost_explorer = CostExplorerCollector(session, self.region)

    def execute_full_pipeline(self) -> Dict[str, Any]:
        start_time = time.time()
        logger.info(f"Initiating full AWS FinOps data collection in {self.region}...")

        # 1. Collect Compute & AMIs
        ec2_data = self.ec2.collect()
        instances = ec2_data.get("instances", [])
        amis = ec2_data.get("amis", [])

        # 2. Enrich running EC2 instances with CloudWatch CPU metrics
        instances = self.cloudwatch.enrich_instances_with_metrics(instances, days=7)

        # 3. Collect Storage & Snapshots
        ebs_data = self.ebs.collect()
        volumes = ebs_data.get("volumes", [])
        snapshots = ebs_data.get("snapshots", [])

        # 4. Collect S3 Buckets & Lifecycles
        s3_data = self.s3.collect()
        buckets = s3_data.get("buckets", [])

        # 5. Collect RDS Databases & Aurora Clusters
        rds_data = self.rds.collect()
        db_instances = rds_data.get("instances", [])
        db_clusters = rds_data.get("clusters", [])
        db_manual_snapshots = rds_data.get("manual_snapshots", [])

        # 6. Collect Networking & Security
        network_data = self.network.collect()
        elastic_ips = network_data.get("elastic_ips", [])
        nat_gateways = network_data.get("nat_gateways", [])
        vpc_endpoints = network_data.get("vpc_endpoints", [])
        network_interfaces = network_data.get("network_interfaces", [])
        load_balancers = network_data.get("load_balancers", [])
        security_groups = network_data.get("security_groups", [])

        # 7. Enrich NAT Gateways with data transfer metrics
        nat_gateways = self.cloudwatch.evaluate_nat_gateways_traffic(nat_gateways)

        # 8. Collect CloudWatch Log Groups
        cw_data = self.cloudwatch.collect()
        log_groups = cw_data.get("log_groups", [])

        # 9. Collect Cost Explorer spend data
        ce_data = self.cost_explorer.collect()
        daily_spend = ce_data.get("daily_spend", [])
        service_breakdown = ce_data.get("service_breakdown", [])

        elapsed = round(time.time() - start_time, 2)
        logger.info(f"AWS FinOps collection completed in {elapsed}s.")

        # Compute estimated monthly baseline
        total_monthly_spend = sum(i["cost"] for i in instances)
        total_monthly_spend += sum(v["cost"] for v in volumes)
        total_monthly_spend += sum(s["cost"] for s in snapshots)
        total_monthly_spend += sum(b["estimated_monthly_cost"] for b in buckets)
        total_monthly_spend += sum(d["cost"] for d in db_instances)
        total_monthly_spend += sum(eip["estimated_monthly_cost"] for eip in elastic_ips)
        total_monthly_spend += sum(n["estimated_monthly_base_cost"] for n in nat_gateways)
        total_monthly_spend += sum(lb["estimated_monthly_cost"] for lb in load_balancers)
        total_monthly_spend += sum(lg["estimated_monthly_cost"] for lg in log_groups)

        # Fallback to Cost Explorer if inventory base is small but historical spend exists
        if ce_data.get("projected_monthly_spend", 0.0) > total_monthly_spend:
            display_spend = ce_data["projected_monthly_spend"]
        else:
            display_spend = round(total_monthly_spend, 2)

        return {
            "metadata": {
                "region": self.region,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": elapsed,
            },
            "nodes": instances,
            "instances": instances,
            "amis": amis,
            "ebs_volumes": volumes,
            "ebs_snapshots": snapshots,
            "s3_buckets": buckets,
            "rds_instances": db_instances,
            "rds_clusters": db_clusters,
            "rds_manual_snapshots": db_manual_snapshots,
            "elastic_ips": elastic_ips,
            "nat_gateways": nat_gateways,
            "vpc_endpoints": vpc_endpoints,
            "network_interfaces": network_interfaces,
            "load_balancers": load_balancers,
            "security_groups": security_groups,
            "cloudwatch_log_groups": log_groups,
            "daily_spend": daily_spend,
            "service_breakdown": service_breakdown,
            "summary": {
                "total_instances": len(instances),
                "running_instances": sum(1 for i in instances if i["state"] == "running"),
                "stopped_instances": sum(1 for i in instances if i["state"] == "stopped"),
                "total_volumes": len(volumes),
                "orphaned_volumes": sum(1 for v in volumes if v["is_orphaned"]),
                "gp2_volumes": sum(1 for v in volumes if v["volume_type"] == "gp2"),
                "unattached_eips": sum(1 for ip in elastic_ips if ip["is_unattached"]),
                "idle_rds_instances": sum(1 for d in db_instances if d.get("zero_connections")),
                "idle_load_balancers": sum(1 for lb in load_balancers if lb.get("is_idle")),
                "never_expire_logs": sum(1 for lg in log_groups if lg.get("is_never_expire")),
                "open_security_ports": sum(1 for sg in security_groups if sg["is_publicly_exposed"]),
                "estimated_monthly_spend": round(display_spend, 2),
            },
        }
