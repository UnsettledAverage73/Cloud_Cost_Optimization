import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from collectors.base import AWSBaseCollector

logger = logging.getLogger("finops.collectors.ebs")

EBS_RATES_PER_GB = {
    "gp3": 0.08,
    "gp2": 0.10,
    "io1": 0.125,
    "io2": 0.125,
    "st1": 0.045,
    "sc1": 0.015,
    "standard": 0.05,
}
SNAPSHOT_RATE_PER_GB = 0.05


class EBSCollector(AWSBaseCollector):
    """
    Collects EBS Volumes and Snapshots with detailed attachment, tiering,
    and orphan status detection.
    """

    def collect(self) -> Dict[str, Any]:
        volumes = self.collect_volumes()
        snapshots = self.collect_snapshots()
        return {
            "volumes": volumes,
            "snapshots": snapshots,
            "total_volumes": len(volumes),
            "orphaned_volumes_count": sum(1 for v in volumes if v["is_orphaned"]),
            "gp2_volumes_count": sum(1 for v in volumes if v["volume_type"] == "gp2"),
            "total_snapshots": len(snapshots),
            "stale_snapshots_count": sum(1 for s in snapshots if s["is_stale"]),
        }

    def collect_volumes(self) -> List[Dict[str, Any]]:
        raw_volumes = self.paginate("ec2", "describe_volumes", "Volumes")
        volumes: List[Dict[str, Any]] = []

        for vol in raw_volumes:
            vol_id = vol.get("VolumeId", "unknown")
            size_gb = vol.get("Size", 0)
            vol_type = str(vol.get("VolumeType", "gp3")).lower()
            iops = vol.get("Iops", 3000)
            throughput = vol.get("Throughput", 125)
            state = vol.get("State", "unknown")
            attachments = vol.get("Attachments", [])
            is_orphaned = (state == "available") or (len(attachments) == 0)
            create_time = vol.get("CreateTime")

            # Calculate cost
            rate = EBS_RATES_PER_GB.get(vol_type, 0.08)
            storage_cost = size_gb * rate
            iops_cost = 0.0
            if vol_type in ["io1", "io2"]:
                iops_cost = iops * 0.065
            elif vol_type == "gp3" and iops > 3000:
                iops_cost = (iops - 3000) * 0.005

            monthly_cost = round(storage_cost + iops_cost, 2)

            attached_inst = attachments[0].get("InstanceId") if attachments else None
            attached_device = attachments[0].get("Device") if attachments else None
            delete_on_term = attachments[0].get("DeleteOnTermination", False) if attachments else False

            volumes.append({
                "volume_id": vol_id,
                "size_gb": size_gb,
                "volume_type": vol_type,
                "iops": iops,
                "throughput": throughput,
                "status": state,
                "is_orphaned": is_orphaned,
                "attached_instance_id": attached_inst,
                "device": attached_device,
                "delete_on_termination": delete_on_term,
                "encrypted": vol.get("Encrypted", False),
                "kms_key_id": vol.get("KmsKeyId"),
                "availability_zone": vol.get("AvailabilityZone", self.region),
                "create_time": create_time.isoformat() if create_time else None,
                "tags": self.parse_tags(vol.get("Tags")),
                "cost": monthly_cost,
                "monthly_cost": monthly_cost,
            })

        return volumes

    def collect_snapshots(self) -> List[Dict[str, Any]]:
        raw_snapshots = self.call(
            "ec2",
            "describe_snapshots",
            {"OwnerIds": ["self"]},
            default={"Snapshots": []},
        )
        snapshots_list = raw_snapshots.get("Snapshots", []) if isinstance(raw_snapshots, dict) else []
        snapshots: List[Dict[str, Any]] = []
        now = datetime.now(timezone.utc)

        for snap in snapshots_list:
            snap_id = snap.get("SnapshotId", "unknown")
            vol_id = snap.get("VolumeId")
            size_gb = snap.get("VolumeSize", 0)
            start_time = snap.get("StartTime")

            age_days = 0
            if start_time:
                age_days = max(0, (now - start_time).days)

            is_stale = age_days > 90
            monthly_cost = round(size_gb * SNAPSHOT_RATE_PER_GB, 2)

            snapshots.append({
                "snapshot_id": snap_id,
                "volume_id": vol_id,
                "size_gb": size_gb,
                "start_time": start_time.isoformat() if start_time else None,
                "age_days": age_days,
                "is_stale": is_stale,
                "description": snap.get("Description", ""),
                "state": snap.get("State", "completed"),
                "tags": self.parse_tags(snap.get("Tags")),
                "cost": monthly_cost,
                "monthly_cost": monthly_cost,
            })

        return snapshots
