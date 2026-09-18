import boto3
from botocore.exceptions import BotoCoreError, ClientError
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from data.finops_database import record_remediation_audit

class AutoRemediator:
    """
    Executes automated FinOps fixes and security hardenings with dry-run safety and audit logging.
    """

    def __init__(self, region: str = "us-east-1", dry_run: bool = True, session: Optional[boto3.Session] = None):
        self.region = region
        self.dry_run = dry_run
        self.session = session
        if session:
            self.ec2 = session.client("ec2", region_name=region)
            self.logs = session.client("logs", region_name=region)
        else:
            self.ec2 = None
            self.logs = None

    def release_unattached_eip(self, public_ip: str) -> Dict[str, Any]:
        """Releases an unattached Elastic IP to stop idle public IPv4 charges ($3.60/mo)."""
        action = "release_eip"
        if self.dry_run or not self.ec2:
            msg = f"[DRY RUN] Would release unattached Elastic IP: {public_ip}"
            record_remediation_audit(action, public_ip, dry_run=True, status="simulated", details={"message": msg})
            return {"status": "success", "dry_run": True, "action": action, "resource_id": public_ip, "message": msg}

        try:
            # Look up allocation ID
            addresses = self.ec2.describe_addresses(PublicIps=[public_ip]).get("Addresses", [])
            if not addresses:
                return {"status": "error", "message": f"IP {public_ip} not found"}
            alloc_id = addresses[0].get("AllocationId")
            if alloc_id:
                self.ec2.release_address(AllocationId=alloc_id)
            else:
                self.ec2.release_address(PublicIp=public_ip)

            record_remediation_audit(action, public_ip, dry_run=False, status="executed", details={"allocation_id": alloc_id})
            return {"status": "success", "dry_run": False, "action": action, "resource_id": public_ip}
        except (ClientError, BotoCoreError, Exception) as e:
            record_remediation_audit(action, public_ip, dry_run=False, status="failed", details={"error": str(e)})
            return {"status": "error", "error": str(e)}

    def delete_unattached_volume(self, volume_id: str, snapshot_first: bool = True) -> Dict[str, Any]:
        """Safely snapshots and deletes an orphaned EBS volume."""
        action = "delete_volume"
        if self.dry_run or not self.ec2:
            msg = f"[DRY RUN] Would snapshot and delete unattached EBS volume: {volume_id}"
            record_remediation_audit(action, volume_id, dry_run=True, status="simulated", details={"message": msg})
            return {"status": "success", "dry_run": True, "action": action, "resource_id": volume_id, "message": msg}

        try:
            snapshot_id = None
            if snapshot_first:
                desc = f"Safety backup before deletion by FinOps AutoRemediator on {datetime.now(timezone.utc).isoformat()}"
                snap_resp = self.ec2.create_snapshot(VolumeId=volume_id, Description=desc)
                snapshot_id = snap_resp.get("SnapshotId")

            self.ec2.delete_volume(VolumeId=volume_id)
            record_remediation_audit(action, volume_id, dry_run=False, status="executed", details={"snapshot_created": snapshot_id})
            return {"status": "success", "dry_run": False, "action": action, "resource_id": volume_id, "snapshot_id": snapshot_id}
        except (ClientError, BotoCoreError, Exception) as e:
            record_remediation_audit(action, volume_id, dry_run=False, status="failed", details={"error": str(e)})
            return {"status": "error", "error": str(e)}

    def upgrade_volume_to_gp3(self, volume_id: str) -> Dict[str, Any]:
        """Modifies volume from gp2 to gp3 for 20% savings and improved baseline performance."""
        action = "upgrade_gp3"
        if self.dry_run or not self.ec2:
            msg = f"[DRY RUN] Would modify EBS volume {volume_id} to gp3"
            record_remediation_audit(action, volume_id, dry_run=True, status="simulated", details={"message": msg})
            return {"status": "success", "dry_run": True, "action": action, "resource_id": volume_id, "message": msg}

        try:
            self.ec2.modify_volume(VolumeId=volume_id, VolumeType="gp3")
            record_remediation_audit(action, volume_id, dry_run=False, status="executed", details={"new_type": "gp3"})
            return {"status": "success", "dry_run": False, "action": action, "resource_id": volume_id}
        except (ClientError, BotoCoreError, Exception) as e:
            record_remediation_audit(action, volume_id, dry_run=False, status="failed", details={"error": str(e)})
            return {"status": "error", "error": str(e)}

    def stop_idle_instance(self, instance_id: str) -> Dict[str, Any]:
        """Stops an idle running EC2 instance to halt compute billing."""
        action = "stop_instance"
        if self.dry_run or not self.ec2:
            msg = f"[DRY RUN] Would stop idle EC2 instance: {instance_id}"
            record_remediation_audit(action, instance_id, dry_run=True, status="simulated", details={"message": msg})
            return {"status": "success", "dry_run": True, "action": action, "resource_id": instance_id, "message": msg}

        try:
            self.ec2.stop_instances(InstanceIds=[instance_id])
            record_remediation_audit(action, instance_id, dry_run=False, status="executed", details={"state": "stopping"})
            return {"status": "success", "dry_run": False, "action": action, "resource_id": instance_id}
        except (ClientError, BotoCoreError, Exception) as e:
            record_remediation_audit(action, instance_id, dry_run=False, status="failed", details={"error": str(e)})
            return {"status": "error", "error": str(e)}

    def set_log_group_retention(self, log_group_name: str, retention_days: int = 30) -> Dict[str, Any]:
        """Sets retention policy on CloudWatch Log Groups to avoid uncapped storage billing."""
        action = "set_log_retention"
        if self.dry_run or not self.logs:
            msg = f"[DRY RUN] Would set log group '{log_group_name}' retention to {retention_days} days"
            record_remediation_audit(action, log_group_name, dry_run=True, status="simulated", details={"message": msg})
            return {"status": "success", "dry_run": True, "action": action, "resource_id": log_group_name, "message": msg}

        try:
            self.logs.put_retention_policy(logGroupName=log_group_name, retentionInDays=retention_days)
            record_remediation_audit(action, log_group_name, dry_run=False, status="executed", details={"retention_days": retention_days})
            return {"status": "success", "dry_run": False, "action": action, "resource_id": log_group_name}
        except (ClientError, BotoCoreError, Exception) as e:
            record_remediation_audit(action, log_group_name, dry_run=False, status="failed", details={"error": str(e)})
            return {"status": "error", "error": str(e)}

    def revoke_security_group_ingress(self, group_id: str, port: int) -> Dict[str, Any]:
        """Removes open 0.0.0.0/0 ingress rule on specified port."""
        action = "revoke_sg_ingress"
        if self.dry_run or not self.ec2:
            msg = f"[DRY RUN] Would revoke 0.0.0.0/0 access on port {port} for security group {group_id}"
            record_remediation_audit(action, group_id, dry_run=True, status="simulated", details={"port": port})
            return {"status": "success", "dry_run": True, "action": action, "resource_id": group_id, "message": msg}

        try:
            self.ec2.revoke_security_group_ingress(
                GroupId=group_id,
                IpPermissions=[{
                    "IpProtocol": "tcp",
                    "FromPort": port,
                    "ToPort": port,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0"}]
                }]
            )
            record_remediation_audit(action, group_id, dry_run=False, status="executed", details={"port": port})
            return {"status": "success", "dry_run": False, "action": action, "resource_id": group_id}
        except (ClientError, BotoCoreError, Exception) as e:
            record_remediation_audit(action, group_id, dry_run=False, status="failed", details={"error": str(e)})
            return {"status": "error", "error": str(e)}
