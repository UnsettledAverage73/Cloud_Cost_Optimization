import random
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any

class CloudSimulator:
    """
    Generates realistic multi-cloud infrastructure, cost metrics, and diurnal telemetry.
    Supports injecting anomalies (idle nodes, cost spikes, open security ports).
    """

    INSTANCE_TYPES = {
        "t3.micro": 7.60,
        "t3.small": 15.20,
        "t3.medium": 30.40,
        "t3.large": 60.80,
        "c5.large": 62.05,
        "m5.large": 70.08,
        "r5.large": 91.98,
    }

    @classmethod
    def generate_full_environment(cls, org_name: str = "Acme Global Tech", region: str = "us-east-1") -> Dict[str, Any]:
        now = datetime.now(timezone.utc)

        # 1. Nodes (EC2 compute)
        nodes = [
            {
                "instance_id": "i-0a817b3c4d5e6f001",
                "name": "prod-api-gateway",
                "instance_type": "t3.medium",
                "state": "running",
                "platform": "linux",
                "availability_zone": f"{region}a",
                "region": region,
                "public_ip": "54.210.14.88",
                "volumes": 2,
                "cost": 30.40,
                "metrics": {"cpu_utilization_avg": 42.5, "mem_used_percent": 68.0}
            },
            {
                "instance_id": "i-0b928c4d5e6f7a002",
                "name": "prod-auth-service",
                "instance_type": "t3.small",
                "state": "running",
                "platform": "linux",
                "availability_zone": f"{region}b",
                "region": region,
                "public_ip": "54.210.15.12",
                "volumes": 1,
                "cost": 15.20,
                "metrics": {"cpu_utilization_avg": 28.3, "mem_used_percent": 54.0}
            },
            {
                "instance_id": "i-0c039d5e6f7a8b003",
                "name": "dev-analytics-worker",
                "instance_type": "m5.large",
                "state": "running",
                "platform": "linux",
                "availability_zone": f"{region}a",
                "region": region,
                "public_ip": "52.91.44.102",
                "volumes": 1,
                "cost": 70.08,
                "metrics": {"cpu_utilization_avg": 3.1, "mem_used_percent": 18.5}  # IDLE ANOMALY
            },
            {
                "instance_id": "i-0d140e6f7a8b9c004",
                "name": "staging-batch-crawler",
                "instance_type": "c5.large",
                "state": "running",
                "platform": "linux",
                "availability_zone": f"{region}c",
                "region": region,
                "public_ip": None,
                "volumes": 2,
                "cost": 62.05,
                "metrics": {"cpu_utilization_avg": 4.2, "mem_used_percent": 22.0}  # IDLE ANOMALY
            },
            {
                "instance_id": "i-0e251f7a8b9c0d005",
                "name": "legacy-reporting-cron",
                "instance_type": "t3.micro",
                "state": "stopped",
                "platform": "linux",
                "availability_zone": f"{region}a",
                "region": region,
                "public_ip": None,
                "volumes": 1,
                "cost": 7.60,
                "metrics": {"cpu_utilization_avg": 0.0, "mem_used_percent": 0.0}
            }
        ]

        # 2. EBS Volumes
        ebs_volumes = [
            {
                "volume_id": "vol-0a11223344556601",
                "size_gb": 100,
                "volume_type": "gp3",
                "iops": 3000,
                "status": "in-use",
                "is_orphaned": False,
                "attached_instance_id": "i-0a817b3c4d5e6f001",
                "attachments": [{"InstanceId": "i-0a817b3c4d5e6f001", "Device": "/dev/xvda"}],
                "cost": 8.00
            },
            {
                "volume_id": "vol-0b22334455667702",
                "size_gb": 250,
                "volume_type": "gp2",  # LEGACY GP2
                "iops": 750,
                "status": "available",
                "is_orphaned": True,   # ORPHANED SPEND
                "attached_instance_id": None,
                "attachments": [],
                "cost": 25.00
            },
            {
                "volume_id": "vol-0c33445566778803",
                "size_gb": 80,
                "volume_type": "gp3",
                "iops": 3000,
                "status": "available",
                "is_orphaned": True,   # ORPHANED SPEND
                "attached_instance_id": None,
                "attachments": [],
                "cost": 6.40
            }
        ]

        # 3. Elastic IPs
        elastic_ips = [
            {"public_ip": "54.210.14.88", "is_unattached": False, "instance_id": "i-0a817b3c4d5e6f001", "estimated_monthly_cost": 0.0},
            {"public_ip": "34.195.88.204", "is_unattached": True, "instance_id": None, "estimated_monthly_cost": 3.60},
            {"public_ip": "52.87.112.99", "is_unattached": True, "instance_id": None, "estimated_monthly_cost": 3.60}
        ]

        # 4. Security Groups
        security_groups = [
            {
                "group_id": "sg-0987654321fedcba",
                "group_name": "prod-public-web-sg",
                "is_publicly_exposed": True,
                "exposed_ports": [80, 443]
            },
            {
                "group_id": "sg-0123456789abcdef",
                "group_name": "dev-bastion-ssh-open",
                "is_publicly_exposed": True,
                "exposed_ports": [22]  # CRITICAL SECURITY RISK
            },
            {
                "group_id": "sg-0445566778899aabb",
                "group_name": "internal-db-postgres",
                "is_publicly_exposed": False,
                "exposed_ports": []
            }
        ]

        # 5. CloudWatch Log Groups
        cloudwatch_log_groups = [
            {"log_group_name": "/aws/ecs/prod-api", "stored_bytes": 12884901888, "stored_gb": 12.0, "retention_in_days": 30, "is_never_expire": False, "estimated_monthly_cost": 0.36},
            {"log_group_name": "/aws/lambda/image-resizer", "stored_bytes": 85899345920, "stored_gb": 80.0, "retention_in_days": None, "is_never_expire": True, "estimated_monthly_cost": 2.40}
        ]

        # 6. S3 Buckets
        s3_buckets = [
            {"bucket_name": "acme-prod-assets", "creation_date": (now - timedelta(days=200)).isoformat(), "has_lifecycle_policy": True},
            {"bucket_name": "acme-dev-raw-dumps", "creation_date": (now - timedelta(days=120)).isoformat(), "has_lifecycle_policy": False}
        ]

        # 7. Diurnal Telemetry (24 hours)
        telemetry = cls.generate_diurnal_telemetry(hours=24)

        # 8. Spend History (Past 30 days)
        spend = cls.generate_spend_history(days=30)

        return {
            "metadata": {
                "organization": org_name,
                "region": region,
                "timestamp": now.isoformat(),
                "environment": "Production-Simulation",
                "currency": "USD"
            },
            "nodes": nodes,
            "ebs_volumes": ebs_volumes,
            "elastic_ips": elastic_ips,
            "security_groups": security_groups,
            "cloudwatch_log_groups": cloudwatch_log_groups,
            "s3_buckets": s3_buckets,
            "telemetry": telemetry,
            "spend": spend,
            "applied_optimizations": []
        }

    @classmethod
    def generate_diurnal_telemetry(cls, hours: int = 24) -> List[Dict[str, Any]]:
        import math
        points = []
        now = datetime.now(timezone.utc)
        for i in range(hours):
            t = now - timedelta(hours=hours - 1 - i)
            hour_of_day = t.hour
            # Diurnal sine wave: peak at 14:00 (2 PM), low at 03:00 (3 AM)
            wave = (math.sin((hour_of_day - 8) / 24.0 * 2 * math.pi) + 1) / 2.0
            cpu = round(15 + wave * 45 + random.uniform(-3, 3), 1)
            mem = round(35 + wave * 30 + random.uniform(-2, 2), 1)
            net_in = round(100 + wave * 400 + random.uniform(-20, 20), 1)
            net_out = round(200 + wave * 800 + random.uniform(-40, 40), 1)

            points.append({
                "time": t.strftime("%H:00"),
                "timestamp": t.strftime("%H:00"),
                "cpu": max(1.0, min(100.0, cpu)),
                "cpu_utilization": max(1.0, min(100.0, cpu)),
                "mem": max(5.0, min(100.0, mem)),
                "mem_used_percent": max(5.0, min(100.0, mem)),
                "netIn": max(10.0, net_in),
                "netOut": max(20.0, net_out),
                "net_in_mb": max(10.0, net_in),
                "net_out_mb": max(20.0, net_out),
                "read": round(net_in * 0.08, 2),
                "write": round(net_out * 0.06, 2)
            })
        return points

    @classmethod
    def generate_spend_history(cls, days: int = 30) -> List[Dict[str, Any]]:
        points = []
        today = datetime.now(timezone.utc).date()
        base_aws = 14.50
        base_gcp = 4.20
        base_azure = 2.10

        for d in range(days):
            day_date = today - timedelta(days=days - 1 - d)
            # Add gradual upward drift and small random fluctuation
            drift = (d / float(days)) * 2.0
            # Inject a transient cost spike at day 22
            spike = 8.50 if d == 22 else 0.0

            points.append({
                "day": day_date.isoformat(),
                "aws": round(base_aws + drift + random.uniform(-0.8, 0.8) + spike, 2),
                "gcp": round(base_gcp + random.uniform(-0.3, 0.3), 2),
                "azure": round(base_azure + random.uniform(-0.2, 0.2), 2)
            })
        return points
