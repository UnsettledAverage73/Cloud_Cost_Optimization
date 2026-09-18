import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from collectors.base import AWSBaseCollector

logger = logging.getLogger("finops.collectors.rds")

# Approximate On-Demand Monthly Base Rates for common RDS instances (Single-AZ, us-east-1)
RDS_INSTANCE_MONTHLY_RATES = {
    "db.t3.micro": 18.00,
    "db.t3.small": 36.00,
    "db.t3.medium": 72.00,
    "db.t4g.micro": 15.00,
    "db.t4g.small": 30.00,
    "db.t4g.medium": 60.00,
    "db.m5.large": 140.00,
    "db.m5.xlarge": 280.00,
    "db.r5.large": 180.00,
    "db.r5.xlarge": 360.00,
}


class RDSCollector(AWSBaseCollector):
    """
    Collects RDS DB Instances, Aurora DB Clusters, and manual DB snapshots,
    auditing connection metrics, Multi-AZ deployments, and storage types.
    """

    def collect(self) -> Dict[str, Any]:
        instances = self.collect_instances()
        clusters = self.collect_clusters()
        snapshots = self.collect_manual_snapshots()

        return {
            "instances": instances,
            "clusters": clusters,
            "manual_snapshots": snapshots,
            "total_instances": len(instances),
            "idle_instances_count": sum(1 for i in instances if i.get("zero_connections", False)),
            "multi_az_dev_count": sum(
                1 for i in instances if i.get("multi_az") and i.get("is_dev_environment")
            ),
            "total_clusters": len(clusters),
            "total_manual_snapshots": len(snapshots),
        }

    def collect_instances(self) -> List[Dict[str, Any]]:
        raw_instances = self.paginate("rds", "describe_db_instances", "DBInstances")
        instances: List[Dict[str, Any]] = []

        for inst in raw_instances:
            db_id = inst.get("DBInstanceIdentifier", "unknown")
            db_class = inst.get("DBInstanceClass", "db.t3.micro")
            engine = inst.get("Engine", "postgres")
            status = inst.get("DBInstanceStatus", "unknown")
            multi_az = inst.get("MultiAZ", False)
            allocated_gb = inst.get("AllocatedStorage", 20)
            storage_type = str(inst.get("StorageType", "gp3")).lower()
            create_time = inst.get("InstanceCreateTime")

            # Parse tags
            raw_tags = inst.get("TagList", [])
            tags = {t.get("Key"): t.get("Value") for t in raw_tags if t.get("Key")}

            # Evaluate dev/test environment
            env_tag = tags.get("Environment", tags.get("env", "")).lower()
            is_dev = any(env_name in env_tag for env_name in ["dev", "test", "stage", "staging", "uat"])

            # Cost estimation
            base_rate = RDS_INSTANCE_MONTHLY_RATES.get(db_class, 50.00)
            if multi_az:
                base_rate *= 2.0  # Multi-AZ is ~2x instance price
            storage_rate = 0.115 if storage_type == "gp3" else 0.138 if storage_type == "gp2" else 0.15
            storage_cost = allocated_gb * storage_rate
            total_monthly_cost = round(base_rate + storage_cost, 2)

            # Check CloudWatch connections (last 7 days average)
            connections_avg = self._get_db_connections_avg(db_id)
            zero_connections = (connections_avg == 0.0) if connections_avg is not None else False

            instances.append({
                "db_instance_identifier": db_id,
                "db_instance_class": db_class,
                "engine": engine,
                "status": status,
                "multi_az": multi_az,
                "allocated_storage_gb": allocated_gb,
                "storage_type": storage_type,
                "is_dev_environment": is_dev,
                "avg_connections_7d": connections_avg,
                "zero_connections": zero_connections,
                "create_time": create_time.isoformat() if create_time else None,
                "tags": tags,
                "cost": total_monthly_cost,
                "monthly_cost": total_monthly_cost,
            })

        return instances

    def collect_clusters(self) -> List[Dict[str, Any]]:
        raw_clusters = self.paginate("rds", "describe_db_clusters", "DBClusters")
        clusters: List[Dict[str, Any]] = []

        for cluster in raw_clusters:
            cluster_id = cluster.get("DBClusterIdentifier", "unknown")
            engine = cluster.get("Engine", "aurora-mysql")
            status = cluster.get("Status", "unknown")
            multi_az = cluster.get("MultiAZ", False)
            members = [m.get("DBInstanceIdentifier") for m in cluster.get("DBClusterMembers", [])]

            raw_tags = cluster.get("TagList", [])
            tags = {t.get("Key"): t.get("Value") for t in raw_tags if t.get("Key")}

            clusters.append({
                "cluster_identifier": cluster_id,
                "engine": engine,
                "status": status,
                "multi_az": multi_az,
                "cluster_members": members,
                "tags": tags,
            })

        return clusters

    def collect_manual_snapshots(self) -> List[Dict[str, Any]]:
        raw_snaps = self.paginate(
            "rds",
            "describe_db_snapshots",
            "DBSnapshots",
            paginate_kwargs={"SnapshotType": "manual"},
        )
        snapshots: List[Dict[str, Any]] = []
        now = datetime.now(timezone.utc)

        for snap in raw_snaps:
            snap_id = snap.get("DBSnapshotIdentifier", "unknown")
            inst_id = snap.get("DBInstanceIdentifier")
            size_gb = snap.get("AllocatedStorage", 0)
            create_time = snap.get("SnapshotCreateTime")

            age_days = 0
            if create_time:
                age_days = max(0, (now - create_time).days)

            snapshots.append({
                "snapshot_id": snap_id,
                "db_instance_identifier": inst_id,
                "size_gb": size_gb,
                "create_time": create_time.isoformat() if create_time else None,
                "age_days": age_days,
                "is_stale": age_days > 90,
                "estimated_monthly_cost": round(size_gb * 0.095, 2),
            })

        return snapshots

    def _get_db_connections_avg(self, db_instance_id: str) -> Optional[float]:
        try:
            cw = self.get_client("cloudwatch")
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(days=7)
            resp = cw.get_metric_statistics(
                Namespace="AWS/RDS",
                MetricName="DatabaseConnections",
                Dimensions=[{"Name": "DBInstanceIdentifier", "Value": db_instance_id}],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,
                Statistics=["Average", "Maximum"],
            )
            datapoints = resp.get("Datapoints", [])
            if datapoints:
                return round(float(sum(p.get("Average", 0) for p in datapoints) / len(datapoints)), 2)
        except Exception:
            pass
        return None
