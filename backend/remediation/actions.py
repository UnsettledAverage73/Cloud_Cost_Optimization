import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import boto3
from botocore.exceptions import BotoCoreError, ClientError

try:
    from data.finops_database import record_remediation_audit, get_remediation_audit_logs
except ImportError:
    from backend.data.finops_database import record_remediation_audit, get_remediation_audit_logs

try:
    from remediation.guardrails import RemediationGuardrails
except ImportError:
    from backend.remediation.guardrails import RemediationGuardrails

logger = logging.getLogger("finops.remediation.actions")


class SafeRemediationExecutor:
    """
    Executes FinOps remediations with dry-run protection, automated EBS safety snapshotting,
    remediation rollback metadata tagging, and audit ledger persistence.
    """

    def __init__(self, session: Optional[boto3.Session] = None, region: str = "us-east-1"):
        self.session = session
        self.region = region

    def _ensure_session(self) -> bool:
        if not self.session:
            try:
                self.session = boto3.Session(region_name=self.region)
            except Exception as e:
                logger.warning(f"Failed to initialize default boto3 session: {e}")
        return self.session is not None

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
        action_norm = action.lower().strip()
        force = extra.get("force", False)

        if extra.get("asg_name") and "aws:autoscaling:groupName" not in tags:
            tags["aws:autoscaling:groupName"] = extra["asg_name"]
        if extra.get("mem_max") is not None and "mem_max" not in tags:
            tags["mem_max"] = str(extra["mem_max"])

        # 1. Evaluate safety guardrails
        is_safe, reason = RemediationGuardrails.check_safe_to_remediate(
            resource_id, tags, action_norm, allow_production_override=force
        )
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
            is_snapshot_needed = action_norm in [
                "delete_volume", "stop", "stop_instance", "downsize", "resize", "resize_instance", "change_instance_type"
            ]
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
                    "safety_snapshot_required": is_snapshot_needed,
                },
            }
            record_remediation_audit(action, resource_id, True, "DRY_RUN", result)
            return result

        # 3. Live Execution (Requires valid AWS session)
        if not self._ensure_session():
            return {
                "success": False,
                "action": action,
                "resource_id": resource_id,
                "dry_run": False,
                "status": "NO_AWS_SESSION",
                "message": "Cannot execute live remediation without an active AWS session.",
            }

        try:
            if action_norm in ["release_eip", "release"]:
                res = self._release_eip(resource_id)
            elif action_norm in ["delete_volume"]:
                res = self._delete_ebs_volume_safely(resource_id)
            elif action_norm in ["upgrade_gp3", "modernize"]:
                res = self._upgrade_ebs_to_gp3(resource_id)
            elif action_norm in ["set_log_retention"]:
                res = self._set_log_retention(resource_id, extra.get("retention_days", 30))
            elif action_norm in ["stop_instance", "stop"]:
                res = self._stop_ec2_instance(resource_id)
            elif action_norm in ["start_instance", "start"]:
                res = self._start_ec2_instance(resource_id)
            elif action_norm in ["downsize", "resize", "resize_instance", "change_instance_type"]:
                target_type = extra.get("to_type") or extra.get("target_type") or "t3.medium"
                res = self._downsize_ec2_instance(resource_id, target_type)
            elif action_norm in ["rollback", "rollback_instance"]:
                res = self._rollback_instance(resource_id)
            elif action_norm in ["create_s3_endpoint", "s3_endpoint"]:
                res = self._create_s3_endpoint(resource_id)
            elif action_norm in ["configure_s3_lifecycle", "s3_lifecycle"]:
                res = self._configure_s3_lifecycle(resource_id)
            elif action_norm in ["delete_snapshot"]:
                res = self._delete_ebs_snapshot(resource_id)
            elif action_norm in ["revoke_open_port"]:
                res = self._revoke_security_group_port(resource_id, extra.get("port", 22))
            else:
                res = {
                    "success": False,
                    "status": "UNKNOWN_ACTION",
                    "message": f"Action '{action}' is not supported.",
                }

            record_remediation_audit(action, resource_id, False, "EXECUTED" if res.get("success") else "FAILED", res)
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

    def _create_instance_safety_snapshots(self, ec2, instance_id: str) -> List[str]:
        """Creates pre-remediation safety snapshots for attached EBS volumes."""
        snapshots = []
        try:
            resp = ec2.describe_instances(InstanceIds=[instance_id])
            reservations = resp.get("Reservations", [])
            if reservations and reservations[0].get("Instances"):
                inst = reservations[0]["Instances"][0]
                now_str = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
                for bd in inst.get("BlockDeviceMappings", []):
                    ebs = bd.get("Ebs")
                    if ebs and ebs.get("VolumeId"):
                        vol_id = ebs["VolumeId"]
                        try:
                            snap_desc = f"CloudPulse-SafetySnapshot-before-modifying-{instance_id}-{vol_id}-{now_str}"
                            snap_resp = ec2.create_snapshot(
                                VolumeId=vol_id,
                                Description=snap_desc,
                                TagSpecifications=[{
                                    "ResourceType": "snapshot",
                                    "Tags": [
                                        {"Key": "CreatedBy", "Value": "CloudPulse-SafetyProtocol"},
                                        {"Key": "SourceInstanceId", "Value": instance_id},
                                        {"Key": "SourceVolumeId", "Value": vol_id},
                                        {"Key": "FinOps:RollbackSnapshot", "Value": "true"},
                                    ],
                                }],
                            )
                            snap_id = snap_resp.get("SnapshotId")
                            if snap_id:
                                snapshots.append(snap_id)
                        except Exception as e:
                            logger.warning(f"Could not snapshot volume {vol_id}: {e}")
        except Exception as e:
            logger.warning(f"Could not inspect block devices on {instance_id}: {e}")
        return snapshots

    def _tag_remediation_metadata(self, ec2, instance_id: str, tags: Dict[str, str]):
        """Tags resource with FinOps audit and rollback metadata."""
        tag_list = [{"Key": k, "Value": str(v)} for k, v in tags.items()]
        try:
            ec2.create_tags(Resources=[instance_id], Tags=tag_list)
        except Exception as e:
            logger.warning(f"Could not tag remediation metadata on {instance_id}: {e}")

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
                    {"Key": "FinOps:RollbackSnapshot", "Value": "true"},
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
        resp = ec2.describe_instances(InstanceIds=[instance_id])
        inst = resp["Reservations"][0]["Instances"][0]
        cur_state = inst.get("State", {}).get("Name")
        cur_type = inst.get("InstanceType")

        if cur_state == "stopped":
            return {
                "success": True,
                "action": "stop_instance",
                "instance_id": instance_id,
                "previous_state": cur_state,
                "previous_type": cur_type,
                "safety_snapshots": [],
                "message": f"Instance {instance_id} is already stopped.",
            }

        # Step 1: Pre-flight safety snapshot
        snapshots = self._create_instance_safety_snapshots(ec2, instance_id)

        # Step 2: Tag metadata
        now_str = datetime.now(timezone.utc).isoformat()
        self._tag_remediation_metadata(ec2, instance_id, {
            "FinOps:RemediatedAt": now_str,
            "FinOps:PreviousState": cur_state,
            "FinOps:PreviousType": cur_type,
            "FinOps:LastAction": "stop_instance",
        })

        # Step 3: Stop instance
        stop_resp = ec2.stop_instances(InstanceIds=[instance_id])
        stopping = stop_resp.get("StoppingInstances", [])
        return {
            "success": True,
            "action": "stop_instance",
            "instance_id": instance_id,
            "previous_state": cur_state,
            "previous_type": cur_type,
            "safety_snapshots": snapshots,
            "message": f"Instance {instance_id} transitioning to stopped (safety snapshots: {len(snapshots)}).",
            "stopping_instances": stopping,
        }

    def _start_ec2_instance(self, instance_id: str) -> Dict[str, Any]:
        ec2 = self.session.client("ec2", region_name=self.region)
        resp = ec2.start_instances(InstanceIds=[instance_id])
        starting = resp.get("StartingInstances", [])
        self._tag_remediation_metadata(ec2, instance_id, {
            "FinOps:LastAction": "start_instance",
            "FinOps:RemediatedAt": datetime.now(timezone.utc).isoformat(),
        })
        return {
            "success": True,
            "action": "start_instance",
            "instance_id": instance_id,
            "message": f"Instance {instance_id} transitioning to running.",
            "starting_instances": starting,
        }

    def _downsize_ec2_instance(self, instance_id: str, target_type: str) -> Dict[str, Any]:
        ec2 = self.session.client("ec2", region_name=self.region)
        resp = ec2.describe_instances(InstanceIds=[instance_id])
        inst = resp["Reservations"][0]["Instances"][0]
        cur_type = inst.get("InstanceType")
        cur_state = inst.get("State", {}).get("Name")

        if cur_type == target_type:
            return {
                "success": True,
                "message": f"Instance {instance_id} is already type {target_type}.",
                "from_type": cur_type,
                "to_type": target_type,
            }

        snapshots = self._create_instance_safety_snapshots(ec2, instance_id)
        now_str = datetime.now(timezone.utc).isoformat()
        self._tag_remediation_metadata(ec2, instance_id, {
            "FinOps:RemediatedAt": now_str,
            "FinOps:PreviousType": cur_type,
            "FinOps:PreviousState": cur_state,
            "FinOps:TargetType": target_type,
            "FinOps:LastAction": "downsize",
        })

        was_running = (cur_state == "running")
        if was_running:
            ec2.stop_instances(InstanceIds=[instance_id])
            try:
                waiter = ec2.get_waiter("instance_stopped")
                waiter.wait(InstanceIds=[instance_id], WaiterConfig={"Delay": 5, "MaxAttempts": 30})
            except Exception as e:
                logger.warning(f"Wait for instance stop on {instance_id}: {e}")

        ec2.modify_instance_attribute(InstanceId=instance_id, InstanceType={"Value": target_type})

        if was_running:
            ec2.start_instances(InstanceIds=[instance_id])

        return {
            "success": True,
            "action": "downsize",
            "instance_id": instance_id,
            "from_type": cur_type,
            "to_type": target_type,
            "safety_snapshots": snapshots,
            "restarted": was_running,
            "message": f"Successfully downsized {instance_id} from {cur_type} to {target_type} (safety snapshots: {len(snapshots)}).",
        }

    def _rollback_instance(self, instance_id: str) -> Dict[str, Any]:
        ec2 = self.session.client("ec2", region_name=self.region)
        resp = ec2.describe_instances(InstanceIds=[instance_id])
        inst = resp["Reservations"][0]["Instances"][0]
        cur_state = inst.get("State", {}).get("Name")
        cur_type = inst.get("InstanceType")
        tags_dict = {t["Key"]: t["Value"] for t in inst.get("Tags", [])}

        prev_state = tags_dict.get("FinOps:PreviousState")
        prev_type = tags_dict.get("FinOps:PreviousType")
        last_action = tags_dict.get("FinOps:LastAction")

        # Fallback to audit ledger
        if not prev_state and not prev_type:
            try:
                logs = get_remediation_audit_logs(limit=50)
                for log in logs:
                    if log.get("resource_id") == instance_id and not log.get("dry_run"):
                        det = log.get("details", {})
                        prev_state = det.get("previous_state") or det.get("from_state") or prev_state
                        prev_type = det.get("previous_type") or det.get("from_type") or prev_type
                        last_action = log.get("action") or last_action
                        break
            except Exception:
                pass

        rolled_back_items = []

        # If previous type was different, restore instance type
        if prev_type and prev_type != cur_type:
            was_running = (cur_state == "running")
            if was_running:
                ec2.stop_instances(InstanceIds=[instance_id])
                try:
                    waiter = ec2.get_waiter("instance_stopped")
                    waiter.wait(InstanceIds=[instance_id], WaiterConfig={"Delay": 5, "MaxAttempts": 30})
                except Exception:
                    pass
            ec2.modify_instance_attribute(InstanceId=instance_id, InstanceType={"Value": prev_type})
            if was_running or prev_state == "running":
                ec2.start_instances(InstanceIds=[instance_id])
            rolled_back_items.append(f"restored instance type {cur_type} -> {prev_type}")

        # If previous state was running and instance is currently stopped
        elif (prev_state == "running" or last_action in ["stop", "stop_instance"]) and cur_state == "stopped":
            ec2.start_instances(InstanceIds=[instance_id])
            rolled_back_items.append("restarted instance from stopped to running")

        if not rolled_back_items:
            if cur_state == "stopped":
                ec2.start_instances(InstanceIds=[instance_id])
                rolled_back_items.append("restarted instance from stopped to running")
            else:
                return {
                    "success": False,
                    "action": "rollback",
                    "instance_id": instance_id,
                    "message": f"No previous rollback state found for {instance_id} (current state: {cur_state}, type: {cur_type}).",
                }

        self._tag_remediation_metadata(ec2, instance_id, {
            "FinOps:LastAction": "rollback",
            "FinOps:RollbackAt": datetime.now(timezone.utc).isoformat(),
        })

        return {
            "success": True,
            "action": "rollback",
            "instance_id": instance_id,
            "reverted_items": rolled_back_items,
            "message": f"Successfully rolled back {instance_id}: {'; '.join(rolled_back_items)}.",
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

    def _create_s3_endpoint(self, vpc_id: str) -> Dict[str, Any]:
        ec2 = self.session.client("ec2", region_name=self.region)
        rt_resp = ec2.describe_route_tables(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])
        route_tables = rt_resp.get("RouteTables", [])
        rt_ids = [rt["RouteTableId"] for rt in route_tables]

        ep_resp = ec2.describe_vpc_endpoints(
            Filters=[
                {"Name": "vpc-id", "Values": [vpc_id]},
                {"Name": "service-name", "Values": [f"com.amazonaws.{self.region}.s3"]}
            ]
        )
        if ep_resp.get("VpcEndpoints"):
            ep_id = ep_resp["VpcEndpoints"][0]["VpcEndpointId"]
            return {
                "success": True,
                "action": "create_s3_endpoint",
                "endpoint_id": ep_id,
                "vpc_id": vpc_id,
                "message": f"S3 Gateway Endpoint ({ep_id}) already active in VPC {vpc_id}.",
            }

        create_resp = ec2.create_vpc_endpoint(
            VpcId=vpc_id,
            ServiceName=f"com.amazonaws.{self.region}.s3",
            VpcEndpointType="Gateway",
            RouteTableIds=rt_ids,
            TagSpecifications=[{
                "ResourceType": "vpc-endpoint",
                "Tags": [
                    {"Key": "CreatedBy", "Value": "CloudPulse-FinOps"},
                    {"Key": "Purpose", "Value": "Bypass-NAT-Gateway-Charges"},
                ],
            }],
        )
        ep = create_resp.get("VpcEndpoint", {})
        ep_id = ep.get("VpcEndpointId")
        return {
            "success": True,
            "action": "create_s3_endpoint",
            "vpc_id": vpc_id,
            "endpoint_id": ep_id,
            "route_table_ids": rt_ids,
            "message": f"Successfully provisioned free S3 Gateway Endpoint ({ep_id}) in VPC {vpc_id} routed across {len(rt_ids)} route tables.",
        }

    def _configure_s3_lifecycle(self, bucket_name: str) -> Dict[str, Any]:
        s3 = self.session.client("s3", region_name=self.region)
        lifecycle_configuration = {
            "Rules": [
                {
                    "ID": "CloudPulse-IntelligentTiering-Transition",
                    "Status": "Enabled",
                    "Filter": {"Prefix": ""},
                    "Transitions": [
                        {
                            "Days": 0,
                            "StorageClass": "INTELLIGENT_TIERING"
                        }
                    ],
                    "AbortIncompleteMultipartUpload": {
                        "DaysAfterInitiation": 7
                    }
                }
            ]
        }
        s3.put_bucket_lifecycle_configuration(
            Bucket=bucket_name,
            LifecycleConfiguration=lifecycle_configuration
        )
        return {
            "success": True,
            "action": "configure_s3_lifecycle",
            "bucket_name": bucket_name,
            "message": f"Successfully configured Intelligent-Tiering transition and 7-day multipart upload cleanup on bucket '{bucket_name}'.",
        }
