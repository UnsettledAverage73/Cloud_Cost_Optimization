import logging
from typing import Any, Dict, List

logger = logging.getLogger("finops.engines.database")


class DatabaseOptimizer:
    """
    Evaluates RDS and Aurora configurations to find dev/test Multi-AZ overprovisioning
    and storage modernization savings.
    """

    @staticmethod
    def analyze(inventory: Dict[str, Any]) -> List[Dict[str, Any]]:
        recommendations: List[Dict[str, Any]] = []

        for rds in inventory.get("rds_instances", []):
            db_id = rds.get("db_instance_identifier", "unknown")
            cost = rds.get("cost", 50.0)
            multi_az = rds.get("multi_az", False)
            is_dev = rds.get("is_dev_environment", False)
            storage_type = str(rds.get("storage_type", "gp3")).lower()
            storage_gb = rds.get("allocated_storage_gb", 20)

            # 1. Multi-AZ in non-production environments (saves ~50% of DB instance cost)
            if multi_az and is_dev:
                savings = round(cost * 0.45, 2)
                recommendations.append({
                    "id": f"db-multiaz-dev-{db_id}",
                    "resource_id": db_id,
                    "resource_type": "RDS Instance",
                    "category": "Database Architecture",
                    "type": "Multi-AZ Right-Sizing",
                    "title": f"Convert Dev/Test DB '{db_id}' from Multi-AZ to Single-AZ",
                    "description": (
                        "Instance is tagged for dev/test/staging but runs Multi-AZ high availability, "
                        "doubling compute and storage rates. Non-production environments should use Single-AZ."
                    ),
                    "monthly_savings": max(20.00, savings),
                    "savings": max(20.00, savings),
                    "effort": "Low",
                    "action": "convert_to_single_az",
                    "action_type": "convert_to_single_az",
                    "severity": "HIGH",
                    "risk": "LOW",
                })

            # 2. RDS gp2 -> gp3 Storage Upgrade
            if storage_type == "gp2":
                storage_savings = round(storage_gb * 0.023, 2)
                recommendations.append({
                    "id": f"db-gp3-{db_id}",
                    "resource_id": db_id,
                    "resource_type": "RDS Instance",
                    "category": "Storage Modernization",
                    "type": "Storage Upgrade",
                    "title": f"Upgrade RDS '{db_id}' Storage from gp2 to gp3",
                    "description": (
                        f"Upgrading {storage_gb} GB database storage from gp2 to gp3 provides "
                        f"lower cost per GB and guaranteed 3,000 IOPS baseline."
                    ),
                    "monthly_savings": max(2.00, storage_savings),
                    "savings": max(2.00, storage_savings),
                    "effort": "Quick Win",
                    "action": "upgrade_rds_gp3",
                    "action_type": "upgrade_rds_gp3",
                    "severity": "MEDIUM",
                    "risk": "NONE",
                })

        return sorted(recommendations, key=lambda r: r["monthly_savings"], reverse=True)
