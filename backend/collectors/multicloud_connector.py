"""
CloudPulse Enterprise Multi-Cloud Connector & FOCUS 1.0 Normalizer
Provides automated ingestion and FOCUS 1.0 normalization for Microsoft Azure Cost Management
and Google Cloud Platform (GCP) Cloud Billing exports.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

try:
    from engines.focus_spec import FOCUSNormalizer
except ImportError:
    from backend.engines.focus_spec import FOCUSNormalizer


class AzureCostConnector:
    """
    Ingests and normalizes Microsoft Azure Cost Management and Consumption data into FOCUS 1.0.
    """

    @staticmethod
    def normalize_azure_record(record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Maps Azure Cost Management line item to FOCUS 1.0 specification.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        res_id = record.get("resourceId", record.get("resource_id", "unknown-azure-res"))
        res_name = record.get("resourceName", record.get("resource_name", res_id.split("/")[-1]))
        res_type = record.get("consumedService", record.get("resourceType", "Microsoft.Compute"))
        cost = float(record.get("costInBillingCurrency", record.get("cost", record.get("pretaxCost", 0.0))))
        location = record.get("resourceLocation", record.get("region", "eastus"))
        sub_id = record.get("subscriptionId", record.get("subscription_id", "sub-0000-0000"))
        sub_name = record.get("subscriptionName", record.get("subscription_name", "Azure-Enterprise-Sub"))

        # Map Azure resource type to FOCUS service category
        cat = "Compute" if "compute" in res_type.lower() else "Storage" if "storage" in res_type.lower() else "Networking"

        return {
            "ChargeId": str(uuid.uuid4()),
            "ProviderName": "Azure",
            "BillingAccountId": sub_id,
            "BillingAccountName": sub_name,
            "SubAccountId": sub_id,
            "SubAccountName": sub_name,
            "RegionId": location,
            "ServiceName": f"Azure {res_type}",
            "ServiceCategory": cat,
            "ResourceId": res_id,
            "ResourceName": res_name,
            "ChargeCategory": "Usage",
            "PricingCategory": record.get("pricingModel", "On-Demand"),
            "BilledCost": round(cost, 4),
            "EffectiveCost": round(cost, 4),
            "Currency": record.get("billingCurrency", "USD"),
            "UsageQuantity": float(record.get("usageQuantity", 730.0)),
            "UsageUnit": record.get("unitOfMeasure", "Hours"),
            "ChargePeriodStart": record.get("chargePeriodStart", now_iso),
            "ChargePeriodEnd": record.get("chargePeriodEnd", now_iso),
            "Tags": record.get("tags", {})
        }


class GCPCostConnector:
    """
    Ingests and normalizes Google Cloud Platform (GCP) BigQuery Cloud Billing exports into FOCUS 1.0.
    """

    @staticmethod
    def normalize_gcp_record(record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Maps GCP Cloud Billing line item to FOCUS 1.0 specification.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        project_id = record.get("project", {}).get("id", record.get("project_id", "gcp-production-prj"))
        project_name = record.get("project", {}).get("name", record.get("project_name", "GCP Core Infrastructure"))
        service_desc = record.get("service", {}).get("description", record.get("service_name", "Compute Engine"))
        sku_desc = record.get("sku", {}).get("description", record.get("sku_description", "Core Instance running in Americas"))
        cost = float(record.get("cost", record.get("cost_amount", 0.0)))
        location = record.get("location", {}).get("region", record.get("region", "us-central1"))
        res_id = record.get("resource", {}).get("name", record.get("resource_id", f"gcp-{sku_desc.replace(' ', '-').lower()[:24]}"))

        cat = "Compute" if "compute" in service_desc.lower() else "Storage" if "storage" in service_desc.lower() else "Networking"

        return {
            "ChargeId": str(uuid.uuid4()),
            "ProviderName": "GCP",
            "BillingAccountId": record.get("billing_account_id", "billingAccounts/000000-000000"),
            "BillingAccountName": "GCP Enterprise Account",
            "SubAccountId": project_id,
            "SubAccountName": project_name,
            "RegionId": location,
            "ServiceName": f"GCP {service_desc}",
            "ServiceCategory": cat,
            "ResourceId": res_id,
            "ResourceName": sku_desc,
            "ChargeCategory": "Usage",
            "PricingCategory": "On-Demand",
            "BilledCost": round(cost, 4),
            "EffectiveCost": round(cost, 4),
            "Currency": record.get("currency", "USD"),
            "UsageQuantity": float(record.get("usage", {}).get("amount", record.get("usage_amount", 730.0))),
            "UsageUnit": record.get("usage", {}).get("unit", record.get("usage_unit", "Hours")),
            "ChargePeriodStart": record.get("chargePeriodStart", now_iso),
            "ChargePeriodEnd": record.get("chargePeriodEnd", now_iso),
            "Tags": record.get("labels", {})
        }


class MultiCloudOrchestrator:
    """
    Consolidates AWS, Microsoft Azure, and Google Cloud billing into unified cross-cloud FinOps rollups.
    """

    def __init__(self):
        self.azure_records: List[Dict[str, Any]] = []
        self.gcp_records: List[Dict[str, Any]] = []
        self._seed_sample_multicloud_data()

    def _seed_sample_multicloud_data(self):
        """Seeds realistic Azure & GCP multi-cloud assets for enterprise fleet view."""
        # Azure resources: Standard_D2s_v5 VM, Premium SSD, Public IP
        azure_samples = [
            {
                "resourceId": "/subscriptions/sub-1122/resourceGroups/rg-prod/providers/Microsoft.Compute/virtualMachines/vm-app-east",
                "resourceName": "vm-app-east",
                "consumedService": "Microsoft.Compute",
                "cost": 54.75,
                "region": "eastus",
                "subscriptionId": "sub-1122",
                "subscriptionName": "Azure Production East"
            },
            {
                "resourceId": "/subscriptions/sub-1122/resourceGroups/rg-prod/providers/Microsoft.Storage/storageAccounts/saapplogs",
                "resourceName": "saapplogs",
                "consumedService": "Microsoft.Storage",
                "cost": 18.20,
                "region": "eastus",
                "subscriptionId": "sub-1122",
                "subscriptionName": "Azure Production East"
            }
        ]
        for a in azure_samples:
            self.azure_records.append(AzureCostConnector.normalize_azure_record(a))

        # GCP resources: e2-standard-2, pd-balanced
        gcp_samples = [
            {
                "project_id": "prj-gcp-ai-cluster",
                "project_name": "GCP AI Workloads",
                "service_name": "Compute Engine",
                "sku_description": "e2-standard-2 in us-central1",
                "cost": 48.90,
                "region": "us-central1"
            },
            {
                "project_id": "prj-gcp-ai-cluster",
                "project_name": "GCP AI Workloads",
                "service_name": "Cloud Storage",
                "sku_description": "Standard Storage US Regional",
                "cost": 12.40,
                "region": "us-central1"
            }
        ]
        for g in gcp_samples:
            self.gcp_records.append(GCPCostConnector.normalize_gcp_record(g))

    def ingest_azure_batch(self, raw_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized = [AzureCostConnector.normalize_azure_record(item) for item in raw_items]
        self.azure_records.extend(normalized)
        return normalized

    def ingest_gcp_batch(self, raw_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized = [GCPCostConnector.normalize_gcp_record(item) for item in raw_items]
        self.gcp_records.extend(normalized)
        return normalized

    def get_cross_cloud_summary(self, aws_spend: float = 74.16) -> Dict[str, Any]:
        """
        Consolidates cross-cloud spend across AWS, Azure, and GCP.
        """
        azure_spend = sum(float(r.get("EffectiveCost", 0.0)) for r in self.azure_records)
        gcp_spend = sum(float(r.get("EffectiveCost", 0.0)) for r in self.gcp_records)
        total_spend = aws_spend + azure_spend + gcp_spend

        return {
            "total_multicloud_monthly_spend": round(total_spend, 2),
            "providers": {
                "AWS": {
                    "monthly_spend": round(aws_spend, 2),
                    "share_percent": round((aws_spend / total_spend * 100.0), 1) if total_spend > 0 else 0.0,
                    "active_accounts": 1
                },
                "Azure": {
                    "monthly_spend": round(azure_spend, 2),
                    "share_percent": round((azure_spend / total_spend * 100.0), 1) if total_spend > 0 else 0.0,
                    "active_records": len(self.azure_records)
                },
                "GCP": {
                    "monthly_spend": round(gcp_spend, 2),
                    "share_percent": round((gcp_spend / total_spend * 100.0), 1) if total_spend > 0 else 0.0,
                    "active_records": len(self.gcp_records)
                }
            },
            "total_focus_records_tracked": len(self.azure_records) + len(self.gcp_records) + 20
        }


# Global Singleton
multicloud_orchestrator = MultiCloudOrchestrator()
