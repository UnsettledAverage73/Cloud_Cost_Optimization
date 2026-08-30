from datetime import datetime, timezone

DB = {
    "metadata": {
        "organization": "Acme Corp",
        "region": "us-east-1",
        "timestamp": datetime.now(timezone.utc).isoformat()
    },
    "nodes": [
        {
            "instance_id": "i-036358db85d245e3a",
            "name": "api-gateway-prod",
            "instance_type": "t3.micro",
            "state": "running",
            "platform": "linux",
            "availability_zone": "us-east-1a",
            "public_ip": "18.212.92.205",
            "cost": 12.40
        },
        {
            "instance_id": "i-09f81a2b3c4d5e6f7",
            "name": "worker-node-01",
            "instance_type": "t3.medium",
            "state": "running",
            "platform": "linux",
            "availability_zone": "us-east-1b",
            "public_ip": "54.198.11.42",
            "cost": 34.80
        }
    ],
    "ebs_volumes": [
        {
            "volume_id": "vol-0c3a8b442db94e6ab",
            "size_gb": 8,
            "volume_type": "gp3",
            "iops": 3000,
            "status": "in-use",
            "is_orphaned": False,
            "cost": 8.00
        },
        {
            "volume_id": "vol-0992817361abce",
            "size_gb": 100,
            "volume_type": "gp2",
            "iops": 300,
            "status": "available",
            "is_orphaned": True,
            "cost": 10.00
        }
    ],
    "elastic_ips": [
        {"public_ip": "54.210.12.3", "is_unattached": True, "estimated_monthly_cost": 3.60}
    ],
    "security_groups": [
        {
            "group_id": "sg-01234567",
            "group_name": "web-public-sg",
            "is_publicly_exposed": True,
            "exposed_ports": [22, 80, 443]
        }
    ],
    "applied_optimizations": [],
    "telemetry": [
        {"timestamp": "00:00", "cpu_utilization": 4.2, "mem_used_percent": 32.1, "net_in_mb": 120, "net_out_mb": 340},
        {"timestamp": "04:00", "cpu_utilization": 6.8, "mem_used_percent": 34.5, "net_in_mb": 180, "net_out_mb": 410},
        {"timestamp": "08:00", "cpu_utilization": 15.4, "mem_used_percent": 42.0, "net_in_mb": 450, "net_out_mb": 890},
        {"timestamp": "12:00", "cpu_utilization": 12.1, "mem_used_percent": 38.5, "net_in_mb": 380, "net_out_mb": 720},
        {"timestamp": "16:00", "cpu_utilization": 8.7, "mem_used_percent": 35.0, "net_in_mb": 210, "net_out_mb": 510}
    ]
}
