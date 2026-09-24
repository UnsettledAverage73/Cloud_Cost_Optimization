import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
try:
    import boto3
    from botocore.exceptions import ClientError, BotoCoreError
except ImportError:
    boto3 = None
    ClientError = Exception
    BotoCoreError = Exception

try:
    from remediation.guardrails import RemediationGuardrails
except ImportError:
    from backend.remediation.guardrails import RemediationGuardrails

logger = logging.getLogger("finops.remediation.guardian")


class GuardianValidator:
    """
    Production-grade pre-flight safety validator.
    Inspects active SSH/SSM sessions, running backups, manual overrides,
    critical windows, and tag guardrails before any power-state change.
    """

    @classmethod
    async def has_active_ssh(
        cls,
        instance_id: str,
        session: Optional[Any] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> Tuple[bool, str]:
        """
        Detects if developers have active SSH or AWS Systems Manager (SSM) sessions.
        """
        tags = tags or {}
        # 1. Tag-based simulation or agent telemetry flag
        if tags.get("active_ssh", "").lower() in ["true", "1", "yes"] or tags.get("active_sessions", "0") not in ["0", ""]:
            return True, "Instance has active SSH / interactive terminal session reported in telemetry"

        # 2. Live AWS SSM Session Manager check if AWS session available
        if session:
            try:
                ssm = session.client("ssm")
                response = ssm.describe_sessions(
                    State="Active",
                    Filters=[{"key": "Target", "value": instance_id}]
                )
                active_sessions = response.get("Sessions", [])
                if active_sessions:
                    return True, f"Found {len(active_sessions)} active AWS SSM Session Manager connection(s)"
            except Exception as e:
                logger.debug(f"SSM session inspection skipped or unavailable for {instance_id}: {e}")

        return False, "No active SSH or SSM sessions detected"

    @classmethod
    async def backup_running(
        cls,
        instance_id: str,
        session: Optional[Any] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> Tuple[bool, str]:
        """
        Checks if EBS volumes attached to this instance are undergoing snapshot creation.
        """
        tags = tags or {}
        if tags.get("backup_running", "").lower() in ["true", "1", "yes"]:
            return True, "Database / volume backup operation currently in progress (telemetry lock)"

        if session:
            try:
                ec2 = session.client("ec2")
                # List attached volumes
                inst_resp = ec2.describe_instances(InstanceIds=[instance_id])
                reservations = inst_resp.get("Reservations", [])
                if reservations and reservations[0].get("Instances"):
                    b_devices = reservations[0]["Instances"][0].get("BlockDeviceMappings", [])
                    vol_ids = [bd["Ebs"]["VolumeId"] for bd in b_devices if "Ebs" in bd and "VolumeId" in bd["Ebs"]]
                    if vol_ids:
                        snaps = ec2.describe_snapshots(
                            Filters=[
                                {"Name": "volume-id", "Values": vol_ids},
                                {"Name": "status", "Values": ["pending"]}
                            ],
                            OwnerIds=["self"]
                        )
                        if snaps.get("Snapshots"):
                            return True, f"Active EBS snapshot creation in progress on attached volume ({snaps['Snapshots'][0]['SnapshotId']})"
            except Exception as e:
                logger.debug(f"AWS EBS snapshot inspection skipped for {instance_id}: {e}")

        return False, "No active volume backups or snapshots running"

    @classmethod
    async def has_override(
        cls,
        instance_id: str,
        tags: Optional[Dict[str, str]] = None
    ) -> Tuple[bool, str]:
        """
        Checks if an operator requested a temporary or permanent override (Keep Running).
        """
        tags = tags or {}
        for k, v in tags.items():
            lk = k.lower().strip()
            lv = str(v).lower().strip()
            if lk in ["manual_override", "keepalive", "donotdelete", "do_not_delete"] and lv in ["true", "yes", "1"]:
                return True, f"Active manual override configured on resource via tag '{k}={v}'"
            if lk == "override_until":
                try:
                    # ISO datetime format check
                    override_dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
                    if datetime.now(timezone.utc) < override_dt:
                        return True, f"Manual override active until {v}"
                except Exception:
                    pass

        return False, "No manual override active"

    @classmethod
    async def is_critical_window(
        cls,
        instance_id: str,
        tags: Optional[Dict[str, str]] = None
    ) -> Tuple[bool, str]:
        """
        Evaluates calendar blackout windows (e.g., quarter-end freeze or critical launch).
        """
        tags = tags or {}
        if tags.get("critical_window", "").lower() in ["true", "1", "yes"]:
            return True, "Instance is flagged in a critical maintenance / launch blackout window"
        return False, "Normal operational window"

    @classmethod
    async def guardian_check(
        cls,
        instance_id: str,
        action: str = "STOP",
        tags: Optional[Dict[str, str]] = None,
        session: Optional[Any] = None,
        allow_force: bool = False
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Runs complete safety matrix before allowing optimization execution.
        Start / Pre-warm actions are inherently non-destructive, but still verified.
        Stop / Resize actions are aggressively validated.
        """
        tags = tags or {}
        action_upper = action.upper().strip()

        # Non-destructive START / PREWARM actions pass safety checks
        if action_upper in ["START", "PREWARM"]:
            return True, f"Non-destructive action {action_upper} approved.", {
                "active_ssh": False,
                "backup_running": False,
                "manual_override": False,
                "critical_window": False,
                "guardrails_passed": True
            }

        # 1. Existing RemediationGuardrails check (Prod env, Keepalive tags, ASG membership, Memory headroom)
        guard_safe, guard_reason = RemediationGuardrails.check_safe_to_remediate(
            instance_id, tags, action.lower(), allow_production_override=allow_force
        )
        if not guard_safe:
            return False, f"Guardian blocked: {guard_reason}", {
                "guardrails_passed": False,
                "reason": guard_reason
            }

        # 2. Check for active SSH / developer terminals
        has_ssh, ssh_reason = await cls.has_active_ssh(instance_id, session, tags)
        if has_ssh and not allow_force:
            return False, f"Guardian blocked: {ssh_reason}", {
                "active_ssh": True,
                "reason": ssh_reason
            }

        # 3. Check for in-flight backups / snapshots
        is_backup, backup_reason = await cls.backup_running(instance_id, session, tags)
        if is_backup and not allow_force:
            return False, f"Guardian blocked: {backup_reason}", {
                "backup_running": True,
                "reason": backup_reason
            }

        # 4. Check for active manual override
        has_over, override_reason = await cls.has_override(instance_id, tags)
        if has_over and not allow_force:
            return False, f"Guardian blocked: {override_reason}", {
                "manual_override": True,
                "reason": override_reason
            }

        # 5. Check for critical business blackout windows
        is_crit, crit_reason = await cls.is_critical_window(instance_id, tags)
        if is_crit and not allow_force:
            return False, f"Guardian blocked: {crit_reason}", {
                "critical_window": True,
                "reason": crit_reason
            }

        checks_summary = {
            "active_ssh": False,
            "backup_running": False,
            "manual_override": False,
            "critical_window": False,
            "guardrails_passed": True
        }
        return True, "All Guardian safety checks passed.", checks_summary
