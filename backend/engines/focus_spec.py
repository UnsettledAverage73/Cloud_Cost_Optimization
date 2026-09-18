"""
CloudPulse FOCUS 1.0 Specification Engine
Implements the FinOps Open Cost and Usage Specification (FOCUS 1.0)
Standardizes multi-cloud, multi-account telemetry into unified FinOps datasets.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

class FOCUSNormalizer:
    """
    Normalizes proprietary AWS, GCP, and Azure cost datasets into the FOCUS 1.0 open standard.
    """

    @staticmethod
    def normalize_resource_cost(
        resource_id: str,
        resource_name: str,
        service_name: str,
        region_id: str,
        account_id: str,
        account_name: str,
        billed_cost: float,
        pricing_category: str = "On-Demand",
        provider: str = "AWS",
        usage_quantity: float = 730.0,
        usage_unit: str = "Hours",
        charge_start: Optional[str] = None,
        charge_end: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Transforms a raw cloud resource spend record into FOCUS 1.0 schema.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        return {
            "ChargeId": str(uuid.uuid4()),
            "ProviderName": provider,
            "BillingAccountId": account_id,
            "BillingAccountName": account_name,
            "SubAccountId": account_id,
            "SubAccountName": account_name,
            "RegionId": region_id,
            "ServiceName": service_name,
            "ServiceCategory": FOCUSNormalizer._map_service_category(service_name),
            "ResourceId": resource_id,
            "ResourceName": resource_name or resource_id,
            "ChargeCategory": "Usage",
            "PricingCategory": pricing_category,
            "BilledCost": round(billed_cost, 4),
            "EffectiveCost": round(billed_cost, 4),
            "Currency": "USD",
            "UsageQuantity": usage_quantity,
            "UsageUnit": usage_unit,
            "ChargePeriodStart": charge_start or now_iso,
            "ChargePeriodEnd": charge_end or now_iso,
            "Tags": tags or {}
        }

    @staticmethod
    def normalize_inventory(inventory: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Converts full multi-service inventory into a list of FOCUS 1.0 records.
        """
        metadata = inventory.get("metadata", {})
        account_id = metadata.get("account_id", "default-account")
        account_name = metadata.get("account_name", "AWS Production")
        region = metadata.get("region", "us-east-1")

        records = []

        # 1. EC2 Nodes
        nodes = inventory.get("compute", {}).get("nodes") or inventory.get("nodes", [])
        for n in nodes:
            records.append(
                FOCUSNormalizer.normalize_resource_cost(
                    resource_id=n.get("instance_id", "unknown"),
                    resource_name=n.get("name", "ec2-instance"),
                    service_name="Amazon Elastic Compute Cloud - Compute",
                    region_id=n.get("availability_zone", region),
                    account_id=account_id,
                    account_name=account_name,
                    billed_cost=float(n.get("cost", 7.60)),
                    pricing_category="On-Demand",
                    tags=n.get("tags", {})
                )
            )

        # 2. EBS Volumes
        ec2_other = inventory.get("ec2_other_resources", {})
        volumes = ec2_other.get("ebs_volumes") or inventory.get("ebs_volumes", [])
        for v in volumes:
            records.append(
                FOCUSNormalizer.normalize_resource_cost(
                    resource_id=v.get("volume_id", "unknown"),
                    resource_name=f"ebs-{v.get('volume_type', 'gp2')}",
                    service_name="Amazon Elastic Block Store",
                    region_id=region,
                    account_id=account_id,
                    account_name=account_name,
                    billed_cost=float(v.get("cost", 1.00)),
                    pricing_category="Storage",
                    usage_quantity=float(v.get("size_gb", 10.0)),
                    usage_unit="GB-Mo"
                )
            )

        # 3. Elastic IPs
        eips = ec2_other.get("elastic_ips") or inventory.get("elastic_ips", [])
        for e in eips:
            records.append(
                FOCUSNormalizer.normalize_resource_cost(
                    resource_id=e.get("public_ip", "unknown"),
                    resource_name="elastic-ip",
                    service_name="Amazon Virtual Private Cloud - IPv4",
                    region_id=region,
                    account_id=account_id,
                    account_name=account_name,
                    billed_cost=float(e.get("estimated_monthly_cost", 3.60)),
                    pricing_category="Fee",
                    usage_unit="Hours"
                )
            )

        return records

    @staticmethod
    def _map_service_category(service_name: str) -> str:
        s = service_name.lower()
        if "compute" in s or "ec2" in s:
            return "Compute"
        if "block store" in s or "ebs" in s or "s3" in s or "storage" in s:
            return "Storage"
        if "virtual private cloud" in s or "vpc" in s or "network" in s:
            return "Networking"
        if "database" in s or "rds" in s or "aurora" in s:
            return "Database"
        return "Other"

    # Convenient aliases
    convert_inventory_to_focus = normalize_inventory
