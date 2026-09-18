import boto3
from typing import Dict, Any, Optional
from botocore.exceptions import BotoCoreError, ClientError

class AWSPricingClient:
    """
    Fetches On-Demand pricing dynamically via AWS Pricing API or fallback catalog.
    """

    PRICING_REGION = "us-east-1"

    REGION_LOCATION_MAP = {
        "us-east-1": "US East (N. Virginia)",
        "us-east-2": "US East (Ohio)",
        "us-west-1": "US West (N. California)",
        "us-west-2": "US West (Oregon)",
        "eu-central-1": "Europe (Frankfurt)",
        "eu-west-1": "Europe (Ireland)",
        "ap-south-1": "Asia Pacific (Mumbai)",
        "ap-southeast-1": "Asia Pacific (Singapore)",
    }

    # Baseline On-Demand hourly / monthly catalog (us-east-1)
    CATALOG = {
        "t3.nano": {"hourly": 0.0052, "monthly": 3.80},
        "t3.micro": {"hourly": 0.0104, "monthly": 7.60},
        "t3.small": {"hourly": 0.0208, "monthly": 15.20},
        "t3.medium": {"hourly": 0.0416, "monthly": 30.40},
        "t3.large": {"hourly": 0.0832, "monthly": 60.80},
        "t3.xlarge": {"hourly": 0.1664, "monthly": 121.47},
        "t4g.nano": {"hourly": 0.0042, "monthly": 3.07},
        "t4g.micro": {"hourly": 0.0084, "monthly": 6.13},
        "t4g.small": {"hourly": 0.0168, "monthly": 12.26},
        "t4g.medium": {"hourly": 0.0336, "monthly": 24.53},
        "c5.large": {"hourly": 0.085, "monthly": 62.05},
        "c5.xlarge": {"hourly": 0.17, "monthly": 124.10},
        "m5.large": {"hourly": 0.096, "monthly": 70.08},
        "m5.xlarge": {"hourly": 0.192, "monthly": 140.16},
        "r5.large": {"hourly": 0.126, "monthly": 91.98},
        "r5.xlarge": {"hourly": 0.252, "monthly": 183.96},
    }

    STORAGE_RATES = {
        "ebs_gp3": 0.08,    # $0.08 / GB-mo
        "ebs_gp2": 0.10,    # $0.10 / GB-mo
        "ebs_io2": 0.125,   # $0.125 / GB-mo
        "ebs_snapshot": 0.05, # $0.05 / GB-mo
        "eip_unattached": 3.60, # $3.60 / mo
        "nat_gateway_base": 32.40, # $32.40 / mo base
        "cw_logs_gb": 0.03,  # $0.03 / GB-mo
        "s3_standard_gb": 0.023, # $0.023 / GB-mo
        "s3_glacier_gb": 0.0036, # $0.0036 / GB-mo
    }

    def __init__(self, session: Optional[boto3.Session] = None):
        self._price_cache: Dict[str, float] = {}
        self.client = None
        try:
            if session:
                self.client = session.client("pricing", region_name=self.PRICING_REGION)
        except Exception:
            self.client = None

    def get_instance_monthly_cost(self, instance_type: str, region: str = "us-east-1") -> float:
        cache_key = f"{region}:{instance_type}"
        if cache_key in self._price_cache:
            return self._price_cache[cache_key]

        # 1. Try real AWS pricing API if client available
        if self.client:
            location = self.REGION_LOCATION_MAP.get(region, "US East (N. Virginia)")
            try:
                filters = [
                    {"Type": "TERM_MATCH", "Field": "ServiceCode", "Value": "AmazonEC2"},
                    {"Type": "TERM_MATCH", "Field": "location", "Value": location},
                    {"Type": "TERM_MATCH", "Field": "instanceType", "Value": instance_type},
                    {"Type": "TERM_MATCH", "Field": "operatingSystem", "Value": "Linux"},
                    {"Type": "TERM_MATCH", "Field": "preInstalledSw", "Value": "NA"},
                    {"Type": "TERM_MATCH", "Field": "capacitystatus", "Value": "Used"},
                ]
                resp = self.client.get_products(ServiceCode="AmazonEC2", Filters=filters, MaxResults=1)
                for price_item_raw in resp.get("PriceList", []):
                    import json
                    price_item = json.loads(price_item_raw)
                    terms = price_item.get("terms", {}).get("OnDemand", {})
                    for term_val in terms.values():
                        for dim_val in term_val.get("priceDimensions", {}).values():
                            hourly = float(dim_val.get("pricePerUnit", {}).get("USD", 0.0))
                            if hourly > 0:
                                monthly = round(hourly * 730, 2)
                                self._price_cache[cache_key] = monthly
                                return monthly
            except (ClientError, BotoCoreError, Exception):
                pass

        # 2. Fallback to catalog
        entry = self.CATALOG.get(instance_type)
        cost = entry["monthly"] if entry else 25.00
        self._price_cache[cache_key] = cost
        return cost

    def get_ebs_monthly_cost(self, volume_type: str, size_gb: float) -> float:
        v_type = volume_type.lower()
        rate = self.STORAGE_RATES.get(f"ebs_{v_type}", 0.08)
        return round(float(size_gb) * rate, 2)

    def calculate_gp2_to_gp3_savings(self, size_gb: float) -> float:
        """Migrating gp2 ($0.10/GB) to gp3 ($0.08/GB) saves 20%"""
        gp2_cost = size_gb * self.STORAGE_RATES["ebs_gp2"]
        gp3_cost = size_gb * self.STORAGE_RATES["ebs_gp3"]
        return round(gp2_cost - gp3_cost, 2)
