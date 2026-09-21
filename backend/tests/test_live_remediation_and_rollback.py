import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from remediation.actions import SafeRemediationExecutor
from remediation.guardrails import RemediationGuardrails
from cli_main import cmd_apply, cmd_rollback
import argparse


# ==============================================================================
# 1. DRY-RUN AND GUARDRAILS TESTS
# ==============================================================================

def test_safe_remediation_executor_dry_runs():
    executor = SafeRemediationExecutor(region="us-east-1")

    # Dry run stop
    res_stop = executor.execute("stop", "i-dry123", dry_run=True)
    assert res_stop["success"] is True
    assert res_stop["dry_run"] is True
    assert res_stop["status"] == "DRY_RUN_PASSED"
    assert res_stop["details"]["safety_snapshot_required"] is True

    # Dry run downsize
    res_downsize = executor.execute("downsize", "i-dry123", dry_run=True, extra_params={"to_type": "t3.medium"})
    assert res_downsize["success"] is True
    assert res_downsize["status"] == "DRY_RUN_PASSED"
    assert res_downsize["details"]["safety_snapshot_required"] is True

    # Dry run rollback
    res_rollback = executor.execute("rollback", "i-dry123", dry_run=True)
    assert res_rollback["success"] is True
    assert res_rollback["status"] == "DRY_RUN_PASSED"


def test_guardrails_production_override():
    # Production without force
    safe, msg = RemediationGuardrails.check_safe_to_remediate(
        "i-prod1", {"Environment": "production"}, "stop_instance", allow_production_override=False
    )
    assert safe is False
    assert "PRODUCTION" in msg

    # Production with force override
    safe_override, msg_override = RemediationGuardrails.check_safe_to_remediate(
        "i-prod1", {"Environment": "production"}, "stop_instance", allow_production_override=True
    )
    assert safe_override is True
    assert "passed" in msg_override.lower()


# ==============================================================================
# 2. MOCKED LIVE EXECUTION TESTS
# ==============================================================================

def test_stop_instance_with_snapshot_and_tagging():
    mock_session = MagicMock()
    mock_ec2 = MagicMock()
    mock_session.client.return_value = mock_ec2

    # Mock describe_instances
    mock_ec2.describe_instances.return_value = {
        "Reservations": [{
            "Instances": [{
                "InstanceId": "i-stoptest",
                "InstanceType": "t3.large",
                "State": {"Name": "running"},
                "BlockDeviceMappings": [{
                    "Ebs": {"VolumeId": "vol-snap123"}
                }],
                "Tags": [{"Key": "Name", "Value": "TestNode"}]
            }]
        }]
    }
    mock_ec2.create_snapshot.return_value = {"SnapshotId": "snap-test001"}
    mock_ec2.stop_instances.return_value = {
        "StoppingInstances": [{"InstanceId": "i-stoptest", "CurrentState": {"Name": "stopping"}}]
    }

    executor = SafeRemediationExecutor(session=mock_session, region="us-east-1")
    res = executor.execute("stop", "i-stoptest", dry_run=False)

    assert res["success"] is True
    assert res["action"] == "stop_instance"
    assert "snap-test001" in res["safety_snapshots"]
    assert mock_ec2.create_snapshot.called
    assert mock_ec2.create_tags.called
    assert mock_ec2.stop_instances.called


def test_start_instance_live():
    mock_session = MagicMock()
    mock_ec2 = MagicMock()
    mock_session.client.return_value = mock_ec2
    mock_ec2.start_instances.return_value = {
        "StartingInstances": [{"InstanceId": "i-starttest", "CurrentState": {"Name": "pending"}}]
    }

    executor = SafeRemediationExecutor(session=mock_session, region="us-east-1")
    res = executor.execute("start", "i-starttest", dry_run=False)

    assert res["success"] is True
    assert res["action"] == "start_instance"
    assert mock_ec2.start_instances.called


def test_downsize_ec2_instance_live():
    mock_session = MagicMock()
    mock_ec2 = MagicMock()
    mock_session.client.return_value = mock_ec2

    mock_ec2.describe_instances.return_value = {
        "Reservations": [{
            "Instances": [{
                "InstanceId": "i-downsize1",
                "InstanceType": "t3.large",
                "State": {"Name": "running"},
                "BlockDeviceMappings": [{"Ebs": {"VolumeId": "vol-d1"}}],
                "Tags": []
            }]
        }]
    }
    mock_ec2.create_snapshot.return_value = {"SnapshotId": "snap-downsize01"}
    mock_waiter = MagicMock()
    mock_ec2.get_waiter.return_value = mock_waiter

    executor = SafeRemediationExecutor(session=mock_session, region="us-east-1")
    res = executor.execute("downsize", "i-downsize1", dry_run=False, extra_params={"to_type": "t3.medium"})

    assert res["success"] is True
    assert res["from_type"] == "t3.large"
    assert res["to_type"] == "t3.medium"
    assert mock_ec2.stop_instances.called
    assert mock_ec2.modify_instance_attribute.called
    assert mock_ec2.start_instances.called


def test_rollback_ec2_instance_live():
    mock_session = MagicMock()
    mock_ec2 = MagicMock()
    mock_session.client.return_value = mock_ec2

    # Instance currently t3.medium with tag FinOps:PreviousType = t3.large
    mock_ec2.describe_instances.return_value = {
        "Reservations": [{
            "Instances": [{
                "InstanceId": "i-rolltest",
                "InstanceType": "t3.medium",
                "State": {"Name": "running"},
                "Tags": [
                    {"Key": "FinOps:PreviousType", "Value": "t3.large"},
                    {"Key": "FinOps:PreviousState", "Value": "running"},
                    {"Key": "FinOps:LastAction", "Value": "downsize"}
                ]
            }]
        }]
    }
    mock_waiter = MagicMock()
    mock_ec2.get_waiter.return_value = mock_waiter

    executor = SafeRemediationExecutor(session=mock_session, region="us-east-1")
    res = executor.execute("rollback", "i-rolltest", dry_run=False)

    assert res["success"] is True
    assert res["action"] == "rollback"
    assert any("t3.large" in item for item in res["reverted_items"])
    assert mock_ec2.modify_instance_attribute.called


# ==============================================================================
# 3. CLI INTEGRATION TESTS
# ==============================================================================

def test_cli_apply_live_dry_run_invocation(capsys):
    args = argparse.Namespace(
        resource_id="i-cli-test",
        live=True,
        dry_run=True,
        action="downsize",
        from_type="t3.large",
        to_type="t3.medium",
        environment="staging",
        savings=30.40,
        currency="USD",
        slack=None,
        teams=None,
        format="table",
        output=None,
        url=None,
        yes=True,
        force=False,
        region="us-east-1",
        batch=False,
        demo=False
    )
    cmd_apply(args)
    captured = capsys.readouterr().out
    assert "CLOUDPULSE LIVE REMEDIATION PRE-FLIGHT (DRY-RUN SIMULATION)" in captured
    assert "i-cli-test" in captured
    assert "DOWNSIZE" in captured
    assert "t3.large -> t3.medium" in captured


def test_cli_rollback_dry_run_invocation(capsys):
    args = argparse.Namespace(
        resource_id="i-cli-test",
        dry_run=True,
        region="us-east-1",
        yes=True,
        format="table",
        output=None,
        json_only=False,
        url=None
    )
    cmd_rollback(args)
    captured = capsys.readouterr().out
    assert "CLOUDPULSE ROLLBACK PRE-FLIGHT (DRY-RUN SIMULATION)" in captured
    assert "i-cli-test" in captured
    assert "DRY-RUN PASSED" in captured


# ==============================================================================
# 4. MEMORY-AWARE & ASG GUARDRAILS TESTS
# ==============================================================================

def test_rightsizing_memory_saturation_guardrail():
    from engines.rightsizing_engine import RightsizingEngine
    inventory = {
        "nodes": [
            {
                "instance_id": "i-mem-heavy",
                "name": "jvm-indexer",
                "instance_type": "t3.large",
                "platform": "linux",
                "state": "running",
                "cost": 60.80,
                "metrics": {
                    "cpu_utilization_avg": 10.0,
                    "cpu_utilization_max": 25.0,
                    "mem_utilization_avg": 75.0,
                    "mem_utilization_max": 92.0,
                    "has_memory_metrics": True,
                },
            }
        ]
    }
    recs = RightsizingEngine.analyze(inventory)
    # Downsizing to smaller instance MUST be blocked due to 92% memory
    downsizing_recs = [r for r in recs if r["type"] == "Downsizing"]
    assert len(downsizing_recs) == 0

    mem_guardrail_recs = [r for r in recs if r["type"] == "Memory-Constrained Guardrail"]
    assert len(mem_guardrail_recs) == 1
    assert "OOM Prevention" in mem_guardrail_recs[0]["title"]
    assert mem_guardrail_recs[0]["memory_guardrail_status"] == "BLOCKED_HIGH_MEMORY"


def test_rightsizing_asg_launch_template_awareness():
    from engines.rightsizing_engine import RightsizingEngine
    inventory = {
        "nodes": [
            {
                "instance_id": "i-asg-node1",
                "name": "web-asg-node",
                "instance_type": "t3.large",
                "platform": "linux",
                "state": "running",
                "asg_name": "production-api-asg",
                "is_asg": True,
                "cost": 60.80,
                "metrics": {
                    "cpu_utilization_avg": 12.0,
                    "cpu_utilization_max": 25.0,
                },
            }
        ]
    }
    recs = RightsizingEngine.analyze(inventory)
    downsize = next((r for r in recs if r["type"] == "Downsizing"), None)
    assert downsize is not None
    assert downsize["is_asg"] is True
    assert downsize["asg_name"] == "production-api-asg"
    assert downsize["action"] == "update_launch_template"
    assert "Launch Template" in downsize["title"]


def test_remediation_asg_blocked_without_force():
    executor = SafeRemediationExecutor(region="us-east-1")
    res_blocked = executor.execute(
        action="downsize",
        resource_id="i-asg-node1",
        dry_run=True,
        tags={"aws:autoscaling:groupName": "web-prod-asg"},
        extra_params={"to_type": "t3.medium", "force": False}
    )
    assert res_blocked["success"] is False
    assert res_blocked["status"] == "BLOCKED_BY_GUARDRAIL"
    assert "Auto Scaling Group" in res_blocked["message"]

    # When force override is passed
    res_forced = executor.execute(
        action="downsize",
        resource_id="i-asg-node1",
        dry_run=True,
        tags={"aws:autoscaling:groupName": "web-prod-asg"},
        extra_params={"to_type": "t3.medium", "force": True}
    )
    assert res_forced["success"] is True
    assert res_forced["status"] == "DRY_RUN_PASSED"


def test_remediation_create_s3_endpoint_live():
    mock_session = MagicMock()
    mock_ec2 = MagicMock()
    mock_session.client.return_value = mock_ec2
    mock_ec2.describe_route_tables.return_value = {
        "RouteTables": [{"RouteTableId": "rtb-01a2b3c4"}]
    }
    mock_ec2.describe_vpc_endpoints.return_value = {"VpcEndpoints": []}
    mock_ec2.create_vpc_endpoint.return_value = {
        "VpcEndpoint": {"VpcEndpointId": "vpce-s3-test01"}
    }

    executor = SafeRemediationExecutor(session=mock_session, region="us-east-1")
    res = executor.execute("create_s3_endpoint", "vpc-12345", dry_run=False)
    assert res["success"] is True
    assert res["endpoint_id"] == "vpce-s3-test01"
    assert mock_ec2.create_vpc_endpoint.called


def test_remediation_configure_s3_lifecycle_live():
    mock_session = MagicMock()
    mock_s3 = MagicMock()
    mock_session.client.return_value = mock_s3

    executor = SafeRemediationExecutor(session=mock_session, region="us-east-1")
    res = executor.execute("configure_s3_lifecycle", "my-data-bucket", dry_run=False)
    assert res["success"] is True
    assert res["bucket_name"] == "my-data-bucket"
    assert mock_s3.put_bucket_lifecycle_configuration.called

