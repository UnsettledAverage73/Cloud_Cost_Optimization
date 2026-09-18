import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("cloudpulse.copilot.tools.pricing")

# Comprehensive AWS instance pricing matrix (Hourly On-Demand, Spot, and 1-Yr Savings Plan rates for us-east-1)
AWS_INSTANCE_PRICING_TABLE = {
    # General Purpose x86
    "t3.nano": {"on_demand": 0.0052, "spot": 0.0016, "sp_1yr": 0.0034, "vcpu": 2, "ram_gb": 0.5, "arch": "x86_64"},
    "t3.micro": {"on_demand": 0.0104, "spot": 0.0031, "sp_1yr": 0.0069, "vcpu": 2, "ram_gb": 1.0, "arch": "x86_64"},
    "t3.small": {"on_demand": 0.0208, "spot": 0.0062, "sp_1yr": 0.0137, "vcpu": 2, "ram_gb": 2.0, "arch": "x86_64"},
    "t3.medium": {"on_demand": 0.0416, "spot": 0.0125, "sp_1yr": 0.0275, "vcpu": 2, "ram_gb": 4.0, "arch": "x86_64"},
    "t3.large": {"on_demand": 0.0832, "spot": 0.0250, "sp_1yr": 0.0549, "vcpu": 2, "ram_gb": 8.0, "arch": "x86_64"},
    "t3.xlarge": {"on_demand": 0.1664, "spot": 0.0499, "sp_1yr": 0.1098, "vcpu": 4, "ram_gb": 16.0, "arch": "x86_64"},
    "m5.large": {"on_demand": 0.096, "spot": 0.0384, "sp_1yr": 0.063, "vcpu": 2, "ram_gb": 8.0, "arch": "x86_64"},
    "m5.xlarge": {"on_demand": 0.192, "spot": 0.0768, "sp_1yr": 0.127, "vcpu": 4, "ram_gb": 16.0, "arch": "x86_64"},
    "m5.2xlarge": {"on_demand": 0.384, "spot": 0.1536, "sp_1yr": 0.253, "vcpu": 8, "ram_gb": 32.0, "arch": "x86_64"},
    "c5.xlarge": {"on_demand": 0.170, "spot": 0.0680, "sp_1yr": 0.112, "vcpu": 4, "ram_gb": 8.0, "arch": "x86_64"},
    "c5.2xlarge": {"on_demand": 0.340, "spot": 0.1360, "sp_1yr": 0.224, "vcpu": 8, "ram_gb": 16.0, "arch": "x86_64"},

    # AWS Graviton (ARM64) Modernized Equivalents (~20% cheaper + 40% higher perf)
    "t4g.nano": {"on_demand": 0.0042, "spot": 0.0013, "sp_1yr": 0.0028, "vcpu": 2, "ram_gb": 0.5, "arch": "arm64"},
    "t4g.micro": {"on_demand": 0.0084, "spot": 0.0025, "sp_1yr": 0.0055, "vcpu": 2, "ram_gb": 1.0, "arch": "arm64"},
    "t4g.small": {"on_demand": 0.0168, "spot": 0.0050, "sp_1yr": 0.0111, "vcpu": 2, "ram_gb": 2.0, "arch": "arm64"},
    "t4g.medium": {"on_demand": 0.0336, "spot": 0.0101, "sp_1yr": 0.0222, "vcpu": 2, "ram_gb": 4.0, "arch": "arm64"},
    "t4g.large": {"on_demand": 0.0672, "spot": 0.0202, "sp_1yr": 0.0444, "vcpu": 2, "ram_gb": 8.0, "arch": "arm64"},
    "m6g.large": {"on_demand": 0.077, "spot": 0.0308, "sp_1yr": 0.051, "vcpu": 2, "ram_gb": 8.0, "arch": "arm64"},
    "m6g.xlarge": {"on_demand": 0.154, "spot": 0.0616, "sp_1yr": 0.102, "vcpu": 4, "ram_gb": 16.0, "arch": "arm64"},
    "m6g.2xlarge": {"on_demand": 0.308, "spot": 0.1232, "sp_1yr": 0.204, "vcpu": 8, "ram_gb": 32.0, "arch": "arm64"},
    "c7g.xlarge": {"on_demand": 0.145, "spot": 0.0580, "sp_1yr": 0.096, "vcpu": 4, "ram_gb": 8.0, "arch": "arm64"},
    "c7g.2xlarge": {"on_demand": 0.290, "spot": 0.1160, "sp_1yr": 0.192, "vcpu": 8, "ram_gb": 16.0, "arch": "arm64"}
}

STORAGE_PRICING_TABLE = {
    "gp2": {"per_gb_month": 0.10, "baseline_iops": 3, "min_iops": 100},
    "gp3": {"per_gb_month": 0.08, "baseline_iops": 3000, "free_throughput_mbps": 125},
    "io1": {"per_gb_month": 0.125, "per_iops_month": 0.065},
    "eip_unattached": {"per_hour": 0.005, "monthly": 3.60},
    "nat_gateway": {"hourly": 0.045, "monthly_base": 32.40, "per_gb_processed": 0.045}
}

def lookup_aws_pricing(resource_type: str, region: str = "us-east-1") -> Dict[str, Any]:
    """
    RAG-ready tool: returns hourly and monthly pricing for instance types or storage,
    including Graviton recommendations and commitment discounts.
    """
    clean_type = resource_type.strip().lower()

    if clean_type in AWS_INSTANCE_PRICING_TABLE:
        data = AWS_INSTANCE_PRICING_TABLE[clean_type]
        monthly_on_demand = round(data["on_demand"] * 730, 2)
        monthly_spot = round(data["spot"] * 730, 2)
        monthly_savings_plan = round(data["sp_1yr"] * 730, 2)

        # Look up Graviton recommendation if this is x86
        graviton_alt = None
        graviton_savings = None
        if data["arch"] == "x86_64":
            alt_name = None
            if clean_type.startswith("t3."):
                alt_name = clean_type.replace("t3.", "t4g.")
            elif clean_type.startswith("m5."):
                alt_name = clean_type.replace("m5.", "m6g.")
            elif clean_type.startswith("c5."):
                alt_name = clean_type.replace("c5.", "c7g.")

            if alt_name and alt_name in AWS_INSTANCE_PRICING_TABLE:
                alt_data = AWS_INSTANCE_PRICING_TABLE[alt_name]
                alt_monthly = round(alt_data["on_demand"] * 730, 2)
                savings_pct = round((1 - alt_monthly / monthly_on_demand) * 100, 1)
                graviton_alt = {
                    "instance_type": alt_name,
                    "architecture": "arm64 (AWS Graviton)",
                    "monthly_cost": alt_monthly,
                    "monthly_savings": round(monthly_on_demand - alt_monthly, 2),
                    "savings_percentage": f"{savings_pct}%"
                }

        return {
            "found": True,
            "resource_type": clean_type,
            "region": region,
            "architecture": data["arch"],
            "vcpu": data["vcpu"],
            "ram_gb": data["ram_gb"],
            "hourly_on_demand": f"${data['on_demand']:.4f}",
            "monthly_on_demand": f"${monthly_on_demand:.2f}",
            "monthly_spot": f"${monthly_spot:.2f}",
            "monthly_1yr_savings_plan": f"${monthly_savings_plan:.2f}",
            "graviton_recommendation": graviton_alt
        }

    # Storage lookup
    if clean_type in STORAGE_PRICING_TABLE:
        return {
            "found": True,
            "storage_type": clean_type,
            "details": STORAGE_PRICING_TABLE[clean_type]
        }

    return {
        "found": False,
        "message": f"Resource type '{clean_type}' not found in local catalog. In production, queries AWS Pricing Catalog API via boto3."
    }
