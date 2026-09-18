import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import boto3
from botocore.exceptions import BotoCoreError, ClientError

from data.finops_database import record_remediation_audit
from remediation.guardrails import RemediationGuardrails

logger = logging.getLogger("finops.remediation.actions")


class SafeRemediationExecutor:
    """
    Executes FinOps remediations with dry-run protection, automated EBS safety snapshotting,
    and audit ledger persistence.
    """

    def __init__(self, session: Optional[boto3.Session] = None, region: str = "us-east-1"):
        self.session = session
        self.region = region

    def execute(
        self,
        action: str,
        resource_id: str,
        dry_run: bool = True,
        tags: Optional[Dict[str, str]] = None,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        tags = tags or {}
        extra = extra_params or {}

        # 1. Evaluate safety guardrails
        is_safe, reason = RemediationGuardrails.check_safe_to_remediate(resource_id, tags, action)
        if not is_safe:
            result = {
                "success": False,
                "action": action,
                "resource_id": resource_id,
                "dry_run": dry_run,
                "status": "BLOCKED_BY_GUARDRAIL",
                "message": reason,
            }
            record_remediation_audit(action, resource_id, dry_run, "BLOCKED", result)
            return result

        # 2. Dry-Run Evaluation
        if dry_run:
            result = {
                "success": True,
                "action": action,
                "resource_id": resource_id,
                "dry_run": True,
                "status": "DRY_RUN_PASSED",
                "message": f"Dry-run simulation succeeded for {action} on {resource_id}.",
                "details": {
                    "action": action,
                    "target": resource_id,
                    "safety_snapshot_required": action == "delete_volume",
                },
            }
            record_remediation_audit(action, resource_id, True, "DRY_RUN", result)
            return result

        # 3. Live Execution (Requires valid AWS session)
        if not self.session:
            return {
                "success": False,
                "action": action,
                "resource_id": resource_id,
                "dry_run": False,
                "status": "NO_AWS_SESSION",
                "message": "Cannot execute live remediation without an active AWS session.",
            }

        try:
            if action == "release_eip":
                res = self._release_eip(resource_id)
            elif action == "delete_volume":
                res = self._delete_ebs_volume_safely(resource_id)
            elif action == "upgrade_gp3":
                res = self._upgrade_ebs_to_gp3(resource_id)
            elif action == "set_log_retention":
                res = self._set_log_retention(resource_id, extra.get("retention_days", 30))
            elif action == "stop_instance":
                res = self._stop_ec2_instance(resource_id)
            elif action == "delete_snapshot":
                res = self._delete_ebs_snapshot(resource_id)
            elif action == "revoke_open_port":
                res = self._revoke_security_group_port(resource_id, extra.get("port", 22))
            else:
                res = {
                    "success": False,
                    "status": "UNKNOWN_ACTION",
                    "message": f"Action '{action}' is not supported.",
                }

            record_remediation_audit(action, resource_id, False, "EXECUTED" if res["success"] else "FAILED", res)
            return res
        except (ClientError, BotoCoreError) as err:
            logger.error(f"AWS error executing {action} on {resource_id}: {err}")
            res = {
                "success": False,
                "action": action,
                "resource_id": resource_id,
                "dry_run": False,
                "status": "AWS_API_ERROR",
                "message": str(err),
            }
            record_remediation_audit(action, resource_id, False, "ERROR", res)
            return res

    def _release_eip(self, public_ip: str) -> Dict[str, Any]:
        ec2 = self.session.client("ec2", region_name=self.region)
        resp = ec2.describe_addresses(PublicIps=[public_ip])
        addresses = resp.get("Addresses", [])
        if not addresses:
            return {"success": False, "message": f"EIP {public_ip} not found."}

        alloc_id = addresses[0].get("AllocationId")
        if alloc_id:
            ec2.release_address(AllocationId=alloc_id)
        else:
            ec2.release_address(PublicIp=public_ip)

        return {"success": True, "message": f"Successfully released Elastic IP {public_ip}."}

    def _delete_ebs_volume_safely(self, volume_id: str) -> Dict[str, Any]:
        ec2 = self.session.client("ec2", region_name=self.region)

        # Step 1: Create Safety Snapshot
        now_str = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
        snap_desc = f"CloudPulse-SafetySnapshot-before-deleting-{volume_id}-{now_str}"
        snap_resp = ec2.create_snapshot(
            VolumeId=volume_id,
            Description=snap_desc,
            TagSpecifications=[{
                "ResourceType": "snapshot",
                "Tags": [
                    {"Key": "CreatedBy", "Value": "CloudPulse-SafetySnapshot"},
                    {"Key": "SourceVolumeId", "Value": volume_id},
                ],
            }],
        )
        safety_snap_id = snap_resp.get("SnapshotId")

        # Step 2: Delete Volume
        ec2.delete_volume(VolumeId=volume_id)

        return {
            "success": True,
            "safety_snapshot_id": safety_snap_id,
            "message": f"Successfully deleted EBS volume {volume_id} after creating safety snapshot {safety_snap_id}.",
        }

    def _upgrade_ebs_to_gp3(self, volume_id: str) -> Dict[str, Any]:
        ec2 = self.session.client("ec2", region_name=self.region)
        resp = ec2.modify_volume(VolumeId=volume_id, VolumeType="gp3")
        mod = resp.get("VolumeModification", {})
        return {
            "success": True,
            "modification_state": mod.get("ModificationState", "modifying"),
            "message": f"Volume {volume_id} successfully scheduled for gp3 upgrade.",
        }

    def _set_log_retention(self, log_group_name: str, retention_days: int = 30) -> Dict[str, Any]:
        logs = self.session.client("logs", region_name=self.region)
        logs.put_retention_policy(logGroupName=log_group_name, retentionInDays=retention_days)
        return {
            "success": True,
            "message": f"Successfully set retention to {retention_days} days on log group {log_group_name}.",
        }

    def _stop_ec2_instance(self, instance_id: str) -> Dict[str, Any]:
        ec2 = self.session.client("ec2", region_name=self.region)
        resp = ec2.stop_instances(InstanceIds=[instance_id])
        stopping = resp.get("StoppingInstances", [])
        return {
            "success": True,
            "message": f"Instance {instance_id} transitioning to stopped.",
            "stopping_instances": stopping,
        }

    def _delete_ebs_snapshot(self, snapshot_id: str) -> Dict[str, Any]:
        ec2 = self.session.client("ec2", region_name=self.region)
        ec2.delete_snapshot(SnapshotId=snapshot_id)
        return {
            "success": True,
            "message": f"Successfully deleted stale snapshot {snapshot_id}.",
        }

    def _revoke_security_group_port(self, group_id: str, port: int) -> Dict[str, Any]:
        ec2 = self.session.client("ec2", region_name=self.region)
        ec2.revoke_security_group_ingress(
            GroupId=group_id,
            IpPermissions=[{
                "IpProtocol": "tcp",
                "FromPort": port,
                "ToPort": port,
                "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
            }],
        )
        return {
            "success": True,
            "message": f"Revoked public 0.0.0.0/0 ingress on port {port} for security group {group_id}.",
        }
