import logging
from typing import Any, Dict, List

logger = logging.getLogger("finops.engines.rightsizing")

# Downsizing target mapping: current -> recommended smaller tier
DOWNSIZING_MAP = {
    "t3.2xlarge": ("t3.xlarge", 121.60),
    "t3.xlarge": ("t3.large", 60.80),
    "t3.large": ("t3.medium", 30.40),
    "t3.medium": ("t3.small", 15.20),
    "t3.small": ("t3.micro", 7.60),
    "c5.2xlarge": ("c5.xlarge", 122.40),
    "c5.xlarge": ("c5.large", 61.20),
    "m5.2xlarge": ("m5.xlarge", 138.24),
    "m5.xlarge": ("m5.large", 69.12),
    "r5.2xlarge": ("r5.xlarge", 181.44),
    "r5.xlarge": ("r5.large", 90.72),
}

# Graviton equivalent mapping: x86 -> arm64 target and approximate % savings
GRAVITON_MAP = {
    "t3.nano": ("t4g.nano", 0.20),
    "t3.micro": ("t4g.micro", 0.20),
    "t3.small": ("t4g.small", 0.20),
    "t3.medium": ("t4g.medium", 0.20),
    "t3.large": ("t4g.large", 0.20),
    "t3.xlarge": ("t4g.xlarge", 0.20),
    "t3.2xlarge": ("t4g.2xlarge", 0.20),
    "c5.large": ("c7g.large", 0.20),
    "c5.xlarge": ("c7g.xlarge", 0.20),
    "c5.2xlarge": ("c7g.2xlarge", 0.20),
    "m5.large": ("m7g.large", 0.20),
    "m5.xlarge": ("m7g.xlarge", 0.20),
    "m5.2xlarge": ("m7g.2xlarge", 0.20),
}


class RightsizingEngine:
    """
    Evaluates compute rightsizing opportunities based on CloudWatch CPU metrics,
    recommending instance downsizing and ARM64 Graviton migrations.
    """

    @staticmethod
    def analyze(inventory: Dict[str, Any]) -> List[Dict[str, Any]]:
        recommendations: List[Dict[str, Any]] = []

        for node in inventory.get("nodes", []):
            if node.get("state") != "running":
                continue

            inst_id = node.get("instance_id", "unknown")
            name = node.get("name", inst_id)
            current_type = node.get("instance_type", "")
            current_cost = node.get("cost", 30.0)
            platform = node.get("platform", "linux")
            metrics = node.get("metrics", {})
            avg_cpu = metrics.get("cpu_utilization_avg", 50.0)
            max_cpu = metrics.get("cpu_utilization_max", 70.0)

            # 1. Tier Downsizing for underutilized instances (5% <= avg CPU < 25%, max CPU < 40%)
            if 5.0 <= avg_cpu < 25.0 and max_cpu < 40.0:
                if current_type in DOWNSIZING_MAP:
                    target_type, monthly_savings = DOWNSIZING_MAP[current_type]
                    recommendations.append({
                        "id": f"rightsize-downsize-{inst_id}",
                        "resource_id": inst_id,
                        "resource_type": "EC2 Instance",
                        "category": "Compute Rightsizing",
                        "type": "Downsizing",
                        "title": f"Rightsize {name} from {current_type} to {target_type}",
                        "description": (
                            f"Average CPU is {avg_cpu}% (Peak {max_cpu}%). Downsizing to "
                            f"{target_type} matches actual workload requirements and cuts compute cost."
                        ),
                        "monthly_savings": monthly_savings,
                        "savings": monthly_savings,
                        "effort": "Medium",
                        "action": "modify_instance_type",
                        "action_type": "modify_instance_type",
                        "target_type": target_type,
                        "severity": "HIGH",
                        "risk": "LOW",
                    })

            # 2. Graviton Migration (Linux x86 -> ARM64 Graviton)
            if platform == "linux" and current_type in GRAVITON_MAP:
                target_graviton, pct_savings = GRAVITON_MAP[current_type]
                graviton_savings = round(current_cost * pct_savings, 2)
                if graviton_savings > 1.0:
                    recommendations.append({
                        "id": f"rightsize-graviton-{inst_id}",
                        "resource_id": inst_id,
                        "resource_type": "EC2 Instance",
                        "category": "Compute Modernization",
                        "type": "Graviton Migration",
                        "title": f"Migrate {name} ({current_type}) to AWS Graviton ({target_graviton})",
                        "description": (
                            f"AWS Graviton ({target_graviton}) provides up to 20% lower cost and "
                            f"40% higher price-performance for Linux workloads."
                        ),
                        "monthly_savings": graviton_savings,
                        "savings": graviton_savings,
                        "effort": "Medium",
                        "action": "migrate_graviton",
                        "action_type": "migrate_graviton",
                        "target_type": target_graviton,
                        "severity": "MEDIUM",
                        "risk": "LOW",
                    })

        return sorted(recommendations, key=lambda r: r["monthly_savings"], reverse=True)
