import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import boto3
from collectors.base import AWSBaseCollector

logger = logging.getLogger("finops.collectors.ec2")

# Common On-Demand Monthly Base Rates (us-east-1, Linux)
INSTANCE_MONTHLY_RATES = {
    "t3.nano": 3.80,
    "t3.micro": 7.60,
    "t3.small": 15.20,
    "t3.medium": 30.40,
    "t3.large": 60.80,
    "t3.xlarge": 121.60,
    "t3.2xlarge": 243.20,
    "t4g.nano": 3.04,
    "t4g.micro": 6.08,
    "t4g.small": 12.16,
    "t4g.medium": 24.32,
    "t4g.large": 48.64,
    "t4g.xlarge": 97.28,
    "c5.large": 61.20,
    "c5.xlarge": 122.40,
    "c5.2xlarge": 244.80,
    "m5.large": 69.12,
    "m5.xlarge": 138.24,
    "m5.2xlarge": 276.48,
    "r5.large": 90.72,
    "r5.xlarge": 181.44,
}


class EC2Collector(AWSBaseCollector):
    """
    Collects complete EC2 compute instances, AMIs, and configurations.
    """

    def collect(self) -> Dict[str, Any]:
        instances = self.collect_instances()
        amis = self.collect_amis()
        return {
            "instances": instances,
            "amis": amis,
            "total_instances": len(instances),
            "running_count": sum(1 for i in instances if i["state"] == "running"),
            "stopped_count": sum(1 for i in instances if i["state"] == "stopped"),
        }

    def collect_instances(self) -> List[Dict[str, Any]]:
        reservations = self.paginate("ec2", "describe_instances", "Reservations")
        instances: List[Dict[str, Any]] = []

        for res in reservations:
            for inst in res.get("Instances", []):
                inst_id = inst.get("InstanceId", "unknown")
                tags = self.parse_tags(inst.get("Tags"))
                name = tags.get("Name") or inst_id
                inst_type = inst.get("InstanceType", "t3.micro")
                state = inst.get("State", {}).get("Name", "unknown")
                platform = "windows" if inst.get("Platform") == "windows" else "linux"
                arch = inst.get("Architecture", "x86_64")
                lifecycle = "spot" if inst.get("InstanceLifecycle") == "spot" else "on-demand"
                launch_time = inst.get("LaunchTime")
                az = inst.get("Placement", {}).get("AvailabilityZone", self.region)

                block_mappings = inst.get("BlockDeviceMappings", [])
                attached_vol_ids = [
                    mapping["Ebs"]["VolumeId"]
                    for mapping in block_mappings
                    if mapping.get("Ebs", {}).get("VolumeId")
                ]

                # Base cost estimation
                base_rate = INSTANCE_MONTHLY_RATES.get(inst_type, 25.00)
                if platform == "windows":
                    base_rate *= 1.45  # OS license surcharge
                if lifecycle == "spot":
                    base_rate *= 0.35  # ~65-70% Spot discount

                monthly_cost = round(base_rate, 2)

                instances.append({
                    "instance_id": inst_id,
                    "name": name,
                    "instance_type": inst_type,
                    "state": state,
                    "platform": platform,
                    "architecture": arch,
                    "lifecycle": lifecycle,
                    "launch_time": launch_time.isoformat() if launch_time else None,
                    "availability_zone": az,
                    "region": self.region,
                    "public_ip": inst.get("PublicIpAddress"),
                    "private_ip": inst.get("PrivateIpAddress"),
                    "vpc_id": inst.get("VpcId"),
                    "subnet_id": inst.get("SubnetId"),
                    "volumes": len(block_mappings),
                    "attached_volume_ids": attached_vol_ids,
                    "tags": tags,
                    "cost": monthly_cost,
                    "monthly_cost": monthly_cost,
                })

        return instances

    def collect_amis(self) -> List[Dict[str, Any]]:
        raw_images = self.call("ec2", "describe_images", {"Owners": ["self"]}, default={"Images": []})
        images = raw_images.get("Images", []) if isinstance(raw_images, dict) else []
        amis: List[Dict[str, Any]] = []

        for img in images:
            image_id = img.get("ImageId", "unknown")
            snapshots = [
                mapping["Ebs"]["SnapshotId"]
                for mapping in img.get("BlockDeviceMappings", [])
                if mapping.get("Ebs", {}).get("SnapshotId")
            ]
            amis.append({
                "ami_id": image_id,
                "name": img.get("Name", image_id),
                "creation_date": img.get("CreationDate"),
                "state": img.get("State", "available"),
                "architecture": img.get("Architecture", "x86_64"),
                "snapshot_ids": snapshots,
                "tags": self.parse_tags(img.get("Tags")),
            })

        return amis
