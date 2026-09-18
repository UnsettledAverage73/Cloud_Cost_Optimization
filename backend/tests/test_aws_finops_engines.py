import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engines.waste_analyzer import WasteAnalyzer
from engines.rightsizing_engine import RightsizingEngine
from engines.storage_optimizer import StorageOptimizer
from engines.network_optimizer import NetworkOptimizer
from engines.database_optimizer import DatabaseOptimizer
from engines.finops_analyzer import FinOpsAnalyzer
from remediation.guardrails import RemediationGuardrails
from remediation.actions import SafeRemediationExecutor
from collectors.base import AWSBaseCollector
from collectors.ec2_collector import EC2Collector
from collectors.ebs_collector import EBSCollector
from collectors.s3_collector import S3Collector
from collectors.rds_collector import RDSCollector


# ==============================================================================
# 1. WASTE ANALYZER TESTS
# ==============================================================================

def test_waste_analyzer():
    inventory = {
        "elastic_ips": [
            {"public_ip": "54.210.12.3", "is_unattached": True, "estimated_monthly_cost": 3.60},
            {"public_ip": "54.210.12.4", "is_unattached": False, "estimated_monthly_cost": 0.0},
        ],
        "ebs_volumes": [
            {"volume_id": "vol-orphan123", "size_gb": 100, "cost": 10.0, "is_orphaned": True},
            {"volume_id": "vol-active123", "size_gb": 50, "cost": 5.0, "is_orphaned": False},
        ],
        "nodes": [
            {
                "instance_id": "i-idle01",
                "name": "idle-worker",
                "state": "running",
                "cost": 60.0,
                "metrics": {"cpu_utilization_avg": 2.1, "cpu_utilization_max": 4.5},
            },
            {
                "instance_id": "i-active01",
                "name": "prod-api",
                "state": "running",
                "cost": 60.0,
                "metrics": {"cpu_utilization_avg": 55.0, "cpu_utilization_max": 85.0},
            },
        ],
        "rds_instances": [
            {"db_instance_identifier": "dev-db-idle", "status": "available", "cost": 72.0, "zero_connections": True},
        ],
        "load_balancers": [
            {"name": "abandoned-alb", "state": "active", "is_idle": True, "estimated_monthly_cost": 22.50},
        ],
        "ebs_snapshots": [
            {"snapshot_id": "snap-stale1", "age_days": 120, "cost": 15.0, "is_stale": True},
        ],
        "cloudwatch_log_groups": [
            {"log_group_name": "/aws/lambda/abandoned", "is_never_expire": True, "estimated_monthly_cost": 5.0},
        ],
    }

    findings = WasteAnalyzer.analyze(inventory)
    assert len(findings) >= 6

    # Verify unattached EIP
    eip_rec = next(f for f in findings if f["resource_type"] == "Elastic IP")
    assert eip_rec["monthly_savings"] == 3.60
    assert eip_rec["effort"] == "Quick Win"

    # Verify orphaned EBS
    vol_rec = next(f for f in findings if f["resource_id"] == "vol-orphan123")
    assert vol_rec["monthly_savings"] == 10.0
    assert vol_rec["action"] == "delete_volume"

    # Verify idle EC2
    ec2_rec = next(f for f in findings if f["resource_id"] == "i-idle01")
    assert ec2_rec["monthly_savings"] > 0
    assert ec2_rec["severity"] == "HIGH"

    # Verify idle RDS
    rds_rec = next(f for f in findings if f["resource_id"] == "dev-db-idle")
    assert rds_rec["monthly_savings"] > 0

    # Verify idle ALB
    alb_rec = next(f for f in findings if f["resource_type"] == "Load Balancer")
    assert alb_rec["monthly_savings"] == 22.50


# ==============================================================================
# 2. RIGHTSIZING & GRAVITON ENGINE TESTS
# ==============================================================================

def test_rightsizing_engine():
    inventory = {
        "nodes": [
            {
                "instance_id": "i-oversized",
                "name": "reporting-node",
                "instance_type": "t3.large",
                "platform": "linux",
                "state": "running",
                "cost": 60.80,
                "metrics": {"cpu_utilization_avg": 12.0, "cpu_utilization_max": 28.0},
            }
        ]
    }

    recs = RightsizingEngine.analyze(inventory)
    assert len(recs) >= 1

    # Should recommend downsizing to t3.medium
    downsize = next((r for r in recs if r["type"] == "Downsizing"), None)
    assert downsize is not None
    assert downsize["target_type"] == "t3.medium"
    assert downsize["monthly_savings"] == 30.40

    # Should also recommend Graviton migration
    graviton = next((r for r in recs if r["type"] == "Graviton Migration"), None)
    assert graviton is not None
    assert graviton["target_type"] == "t4g.large"
    assert graviton["monthly_savings"] > 0


# ==============================================================================
# 3. STORAGE OPTIMIZER TESTS
# ==============================================================================

def test_storage_optimizer():
    inventory = {
        "ebs_volumes": [
            {
                "volume_id": "vol-gp2-modernize",
                "volume_type": "gp2",
                "size_gb": 500,
                "is_orphaned": False,
                "cost": 50.0,
            }
        ],
        "s3_buckets": [
            {
                "bucket_name": "data-archive-prod",
                "has_lifecycle_policy": False,
                "aborts_incomplete_multipart": False,
                "stored_gb": 1000.0,
            }
        ],
    }

    recs = StorageOptimizer.analyze(inventory)
    assert len(recs) >= 2

    # Verify gp2 -> gp3 savings (500GB * $0.02 = $10.00/mo)
    gp3_rec = next(r for r in recs if r["action"] == "upgrade_gp3")
    assert gp3_rec["monthly_savings"] == 10.00
    assert gp3_rec["effort"] == "Quick Win"

    # Verify S3 lifecycle recommendation
    s3_lifecycle = next(r for r in recs if r["action"] == "configure_s3_lifecycle")
    assert s3_lifecycle["monthly_savings"] > 0

    # Verify multipart cleanup
    s3_multipart = next(r for r in recs if r["action"] == "configure_multipart_cleanup")
    assert s3_multipart["monthly_savings"] == 2.00


# ==============================================================================
# 4. NETWORK & DATA TRANSFER OPTIMIZER TESTS
# ==============================================================================

def test_network_optimizer():
    inventory = {
        "nat_gateways": [
            {
                "nat_gateway_id": "nat-01abc",
                "vpc_id": "vpc-09876",
                "is_idle": True,
                "estimated_monthly_base_cost": 32.40,
            }
        ],
        "vpc_endpoints": [],  # No S3 gateway endpoint
    }

    recs = NetworkOptimizer.analyze(inventory)
    assert len(recs) >= 2

    # Verify missing S3 gateway endpoint
    s3_endpoint_rec = next(r for r in recs if r["action"] == "create_s3_endpoint")
    assert s3_endpoint_rec["resource_id"] == "vpc-09876"
    assert s3_endpoint_rec["monthly_savings"] == 25.00

    # Verify idle NAT Gateway
    nat_rec = next(r for r in recs if r["action"] == "delete_nat_gateway")
    assert nat_rec["monthly_savings"] == 32.40


# ==============================================================================
# 5. DATABASE OPTIMIZER TESTS
# ==============================================================================

def test_database_optimizer():
    inventory = {
        "rds_instances": [
            {
                "db_instance_identifier": "qa-postgres",
                "multi_az": True,
                "is_dev_environment": True,
                "cost": 140.0,
                "storage_type": "gp2",
                "allocated_storage_gb": 100,
            }
        ]
    }

    recs = DatabaseOptimizer.analyze(inventory)
    assert len(recs) >= 2

    # Dev Multi-AZ to Single-AZ
    multi_az_rec = next(r for r in recs if r["action"] == "convert_to_single_az")
    assert multi_az_rec["monthly_savings"] > 40.0

    # RDS gp2 -> gp3
    gp3_db_rec = next(r for r in recs if r["action"] == "upgrade_rds_gp3")
    assert gp3_db_rec["monthly_savings"] > 0


# ==============================================================================
# 6. MASTER FINOPS ANALYZER TESTS
# ==============================================================================

def test_finops_analyzer_master():
    inventory = {
        "summary": {"estimated_monthly_spend": 500.0},
        "nodes": [
            {"instance_id": "i-1", "name": "node-1", "state": "running", "cost": 40.0, "metrics": {"cpu_utilization_avg": 2.0}},
        ],
        "ebs_volumes": [
            {"volume_id": "vol-1", "size_gb": 100, "volume_type": "gp2", "is_orphaned": True, "cost": 10.0},
        ],
        "elastic_ips": [
            {"public_ip": "1.2.3.4", "is_unattached": True, "estimated_monthly_cost": 3.60},
        ],
        "security_groups": [
            {"group_id": "sg-open", "is_publicly_exposed": True, "exposed_ports": [22]},
        ],
    }

    res = FinOpsAnalyzer.evaluate(inventory)
    assert res["total_findings"] > 0
    assert res["total_potential_monthly_savings"] > 0.0
    assert len(res["quick_wins"]) > 0
    assert 0.0 <= res["health_score"] <= 100.0
    assert "forecast" in res
    assert res["forecast"]["annual_projected_savings"] > 0


# ==============================================================================
# 7. REMEDIATION GUARDRAILS TESTS
# ==============================================================================

def test_remediation_guardrails():
    # 1. Protected by tag
    safe, msg = RemediationGuardrails.check_safe_to_remediate(
        "vol-123", {"KeepAlive": "true"}, "delete_volume"
    )
    assert safe is False
    assert "protected by safety tag" in msg

    # 2. Protected by production environment
    safe_prod, msg_prod = RemediationGuardrails.check_safe_to_remediate(
        "vol-prod", {"Environment": "production"}, "delete_volume"
    )
    assert safe_prod is False
    assert "PRODUCTION" in msg_prod

    # 3. Safe dev resource
    safe_dev, msg_dev = RemediationGuardrails.check_safe_to_remediate(
        "vol-dev", {"Environment": "dev"}, "delete_volume"
    )
    assert safe_dev is True


# ==============================================================================
# 8. SAFE REMEDIATION EXECUTOR TESTS (DRY-RUN & GUARDRAILS)
# ==============================================================================

def test_safe_remediation_executor():
    executor = SafeRemediationExecutor()

    # Dry-run execution
    res = executor.execute("delete_volume", "vol-abc", dry_run=True)
    assert res["success"] is True
    assert res["dry_run"] is True
    assert res["status"] == "DRY_RUN_PASSED"

    # Guardrail block execution
    res_blocked = executor.execute(
        "delete_volume", "vol-blocked", dry_run=True, tags={"DoNotDelete": "true"}
    )
    assert res_blocked["success"] is False
    assert res_blocked["status"] == "BLOCKED_BY_GUARDRAIL"


# ==============================================================================
# 9. COLLECTOR ERROR HANDLING & PARSING TESTS
# ==============================================================================

def test_collector_permission_degradation():
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_client.get_paginator.side_effect = Exception("UnauthorizedOperation: You are not authorized to perform this operation.")
    mock_session.client.return_value = mock_client
    mock_session.region_name = "us-east-1"

    collector = AWSBaseCollector(mock_session)
    items = collector.paginate("ec2", "describe_instances", "Reservations")
    assert items == []  # Gracefully handles permission denials without crashing
