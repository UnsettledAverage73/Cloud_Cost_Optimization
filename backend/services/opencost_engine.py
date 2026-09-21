"""
CloudPulse OpenCost & Kubernetes FinOps Workload Engine
Standardizes Kubernetes pod and container resource allocations into FOCUS 1.0.
Calculates container efficiency, idle capacity waste, and provides 1-click YAML rightsizing diffs.
"""

import json
import logging
from typing import Dict, List, Any, Optional
try:
    from services.currency_converter import currency_converter
except ImportError:
    from backend.services.currency_converter import currency_converter

logger = logging.getLogger("cloudpulse.k8s.opencost")

# Standard AWS/GCP blended hourly resource rates (EKS m6i/c6i amortized)
HOURLY_CPU_CORE_RATE = 0.031611   # ~$23.08 / core-month
HOURLY_RAM_GIB_RATE = 0.004237    # ~$3.09 / GiB-month
MONTHLY_STORAGE_GB_RATE = 0.08    # gp3 baseline: $0.08 / GB-month
HOURS_PER_MONTH = 730.0

DEFAULT_K8S_WORKLOADS = [
    {
        "cluster": "eks-prod-us-east-1",
        "namespace": "production",
        "workload": "checkout-service",
        "kind": "Deployment",
        "replicas": 3,
        "container": "checkout",
        "requested_cpu_cores": 2.0,
        "utilized_cpu_cores": 0.25,
        "requested_ram_gib": 4.0,
        "utilized_ram_gib": 0.80,
        "storage_pvc_gib": 0.0,
        "labels": {"app": "checkout", "tier": "backend", "team": "ecommerce"}
    },
    {
        "cluster": "eks-prod-us-east-1",
        "namespace": "production",
        "workload": "search-indexer",
        "kind": "Deployment",
        "replicas": 2,
        "container": "indexer",
        "requested_cpu_cores": 4.0,
        "utilized_cpu_cores": 0.60,
        "requested_ram_gib": 8.0,
        "utilized_ram_gib": 1.80,
        "storage_pvc_gib": 20.0,
        "labels": {"app": "search", "tier": "indexer", "team": "core-platform"}
    },
    {
        "cluster": "eks-prod-us-east-1",
        "namespace": "production",
        "workload": "payment-gateway",
        "kind": "Deployment",
        "replicas": 2,
        "container": "gateway",
        "requested_cpu_cores": 1.0,
        "utilized_cpu_cores": 0.70,
        "requested_ram_gib": 2.0,
        "utilized_ram_gib": 1.45,
        "storage_pvc_gib": 0.0,
        "labels": {"app": "payment", "tier": "critical", "team": "finances"}
    },
    {
        "cluster": "eks-prod-us-east-1",
        "namespace": "staging",
        "workload": "staging-api",
        "kind": "Deployment",
        "replicas": 2,
        "container": "api",
        "requested_cpu_cores": 2.0,
        "utilized_cpu_cores": 0.10,
        "requested_ram_gib": 4.0,
        "utilized_ram_gib": 0.35,
        "storage_pvc_gib": 0.0,
        "labels": {"app": "api", "tier": "staging", "team": "devs"}
    },
    {
        "cluster": "eks-prod-us-east-1",
        "namespace": "staging",
        "workload": "staging-frontend",
        "kind": "Deployment",
        "replicas": 2,
        "container": "frontend",
        "requested_cpu_cores": 1.0,
        "utilized_cpu_cores": 0.06,
        "requested_ram_gib": 2.0,
        "utilized_ram_gib": 0.20,
        "storage_pvc_gib": 0.0,
        "labels": {"app": "frontend", "tier": "staging", "team": "devs"}
    },
    {
        "cluster": "eks-prod-us-east-1",
        "namespace": "monitoring",
        "workload": "prometheus-server",
        "kind": "StatefulSet",
        "replicas": 1,
        "container": "prometheus",
        "requested_cpu_cores": 2.0,
        "utilized_cpu_cores": 1.40,
        "requested_ram_gib": 8.0,
        "utilized_ram_gib": 6.20,
        "storage_pvc_gib": 50.0,
        "labels": {"app": "prometheus", "tier": "monitoring", "team": "sre"}
    },
    {
        "cluster": "eks-prod-us-east-1",
        "namespace": "kube-system",
        "workload": "fluentbit",
        "kind": "DaemonSet",
        "replicas": 4,
        "container": "fluentbit",
        "requested_cpu_cores": 0.20,
        "utilized_cpu_cores": 0.08,
        "requested_ram_gib": 0.25,
        "utilized_ram_gib": 0.15,
        "storage_pvc_gib": 0.0,
        "labels": {"app": "fluentbit", "tier": "logging", "team": "sre"}
    }
]


class KubernetesCostEngine:
    """
    Ingests and analyzes Kubernetes container costs, pod utilization, and namespace attribution.
    Generates FOCUS 1.0 records, cluster efficiency metrics, and 1-click YAML rightsizing diffs.
    """

    def __init__(self, workloads: Optional[List[Dict[str, Any]]] = None):
        self.workloads = list(workloads) if workloads is not None else list(DEFAULT_K8S_WORKLOADS)

    def set_workloads(self, workloads: List[Dict[str, Any]]):
        """Updates the active workload inventory."""
        self.workloads = list(workloads)

    def calculate_workload_cost(self, w: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculates requested vs utilized costs, idle waste, and efficiency score for a workload.
        """
        replicas = int(w.get("replicas", 1))
        req_cpu = float(w.get("requested_cpu_cores", 0.0)) * replicas
        ut_cpu = float(w.get("utilized_cpu_cores", 0.0)) * replicas
        req_ram = float(w.get("requested_ram_gib", 0.0)) * replicas
        ut_ram = float(w.get("utilized_ram_gib", 0.0)) * replicas
        pvc_gb = float(w.get("storage_pvc_gib", 0.0))

        # Monthly costs
        monthly_cpu_req_cost = req_cpu * HOURLY_CPU_CORE_RATE * HOURS_PER_MONTH
        monthly_cpu_ut_cost = ut_cpu * HOURLY_CPU_CORE_RATE * HOURS_PER_MONTH
        monthly_ram_req_cost = req_ram * HOURLY_RAM_GIB_RATE * HOURS_PER_MONTH
        monthly_ram_ut_cost = ut_ram * HOURLY_RAM_GIB_RATE * HOURS_PER_MONTH
        monthly_storage_cost = pvc_gb * MONTHLY_STORAGE_GB_RATE

        total_requested_cost = round(monthly_cpu_req_cost + monthly_ram_req_cost + monthly_storage_cost, 2)
        total_utilized_cost = round(monthly_cpu_ut_cost + monthly_ram_ut_cost + monthly_storage_cost, 2)
        idle_waste_cost = round(max(0.0, total_requested_cost - total_utilized_cost), 2)

        # Efficiency calculation
        cpu_eff = round((ut_cpu / req_cpu * 100), 1) if req_cpu > 0 else 100.0
        ram_eff = round((ut_ram / req_ram * 100), 1) if req_ram > 0 else 100.0
        overall_eff = round((cpu_eff + ram_eff) / 2.0, 1)

        return {
            "cluster": w.get("cluster", "k8s-cluster"),
            "namespace": w.get("namespace", "default"),
            "workload": w.get("workload", "unknown"),
            "kind": w.get("kind", "Deployment"),
            "container": w.get("container", "main"),
            "replicas": replicas,
            "requested_cpu_cores": req_cpu,
            "utilized_cpu_cores": ut_cpu,
            "requested_ram_gib": req_ram,
            "utilized_ram_gib": ut_ram,
            "storage_pvc_gib": pvc_gb,
            "monthly_requested_cost": total_requested_cost,
            "monthly_utilized_cost": total_utilized_cost,
            "monthly_idle_waste": idle_waste_cost,
            "cpu_efficiency_pct": cpu_eff,
            "ram_efficiency_pct": ram_eff,
            "overall_efficiency_pct": overall_eff,
            "labels": w.get("labels", {})
        }

    def get_cluster_efficiency(self, currency: str = "USD", rate: float = 84.0) -> Dict[str, Any]:
        """
        Aggregates fleet/cluster-wide efficiency, total container cost, and idle waste.
        """
        converter = currency_converter
        converter.usd_to_inr_rate = rate

        evaluated = [self.calculate_workload_cost(w) for w in self.workloads]
        total_req_cost = sum(item["monthly_requested_cost"] for item in evaluated)
        total_ut_cost = sum(item["monthly_utilized_cost"] for item in evaluated)
        total_idle_cost = sum(item["monthly_idle_waste"] for item in evaluated)
        annual_idle_cost = round(total_idle_cost * 12.0, 2)

        cluster_eff = round((total_ut_cost / total_req_cost * 100), 1) if total_req_cost > 0 else 100.0

        # Namespace aggregations
        namespaces: Dict[str, Dict[str, float]] = {}
        for item in evaluated:
            ns = item["namespace"]
            if ns not in namespaces:
                namespaces[ns] = {"requested_cost": 0.0, "utilized_cost": 0.0, "idle_cost": 0.0, "workload_count": 0}
            namespaces[ns]["requested_cost"] = round(namespaces[ns]["requested_cost"] + item["monthly_requested_cost"], 2)
            namespaces[ns]["utilized_cost"] = round(namespaces[ns]["utilized_cost"] + item["monthly_utilized_cost"], 2)
            namespaces[ns]["idle_cost"] = round(namespaces[ns]["idle_cost"] + item["monthly_idle_waste"], 2)
            namespaces[ns]["workload_count"] += 1

        ns_breakdown = []
        for ns, vals in sorted(namespaces.items(), key=lambda x: x[1]["requested_cost"], reverse=True):
            eff = round((vals["utilized_cost"] / vals["requested_cost"] * 100), 1) if vals["requested_cost"] > 0 else 100.0
            ns_breakdown.append({
                "namespace": ns,
                "workload_count": vals["workload_count"],
                "monthly_requested_cost": vals["requested_cost"],
                "monthly_utilized_cost": vals["utilized_cost"],
                "monthly_idle_cost": vals["idle_cost"],
                "efficiency_pct": eff,
                "cost_formatted": converter.format_dual(vals["requested_cost"], primary_currency=currency),
                "idle_formatted": converter.format_dual(vals["idle_cost"], primary_currency=currency)
            })

        return {
            "cluster_count": len(set(w.get("cluster", "default") for w in self.workloads)),
            "total_workloads": len(evaluated),
            "monthly_requested_cost": round(total_req_cost, 2),
            "monthly_utilized_cost": round(total_ut_cost, 2),
            "monthly_idle_waste": round(total_idle_cost, 2),
            "annual_idle_waste": annual_idle_cost,
            "overall_efficiency_pct": cluster_eff,
            "formatted_requested_cost": converter.format_dual(total_req_cost, primary_currency=currency),
            "formatted_utilized_cost": converter.format_dual(total_ut_cost, primary_currency=currency),
            "formatted_idle_waste": converter.format_dual(total_idle_cost, primary_currency=currency),
            "formatted_annual_idle_waste": converter.format_dual(annual_idle_cost, primary_currency=currency),
            "namespaces": ns_breakdown
        }

    def get_workload_allocations(self, namespace: Optional[str] = None, currency: str = "USD", rate: float = 84.0) -> List[Dict[str, Any]]:
        """
        Returns granular workload allocation list filtered by namespace if specified.
        """
        converter = currency_converter
        converter.usd_to_inr_rate = rate

        evaluated = [self.calculate_workload_cost(w) for w in self.workloads]
        if namespace:
            evaluated = [item for item in evaluated if item["namespace"].lower() == namespace.lower()]

        for item in evaluated:
            item["formatted_cost"] = converter.format_dual(item["monthly_requested_cost"], primary_currency=currency)
            item["formatted_idle"] = converter.format_dual(item["monthly_idle_waste"], primary_currency=currency)

        evaluated.sort(key=lambda x: x["monthly_idle_waste"], reverse=True)
        return evaluated

    def get_rightsizing_recommendations(
        self,
        efficiency_threshold: float = 40.0,
        currency: str = "USD",
        rate: float = 84.0
    ) -> List[Dict[str, Any]]:
        """
        Identifies over-provisioned Kubernetes workloads (efficiency < threshold)
        and generates safe rightsizing recommendations with YAML patch diffs.
        """
        converter = currency_converter
        converter.usd_to_inr_rate = rate

        recommendations = []
        for w in self.workloads:
            metrics = self.calculate_workload_cost(w)
            eff = metrics["overall_efficiency_pct"]
            if eff < efficiency_threshold:
                replicas = metrics["replicas"]
                single_req_cpu = float(w.get("requested_cpu_cores", 0.0))
                single_ut_cpu = float(w.get("utilized_cpu_cores", 0.0))
                single_req_ram = float(w.get("requested_ram_gib", 0.0))
                single_ut_ram = float(w.get("utilized_ram_gib", 0.0))

                # Safe rightsizing targets: 25% CPU headroom, 20% RAM headroom
                rec_single_cpu = max(round(single_ut_cpu * 1.25, 2), 0.10)
                rec_single_ram = max(round(single_ut_ram * 1.20, 2), 0.25)

                # Cost recalculation
                rec_total_cpu = rec_single_cpu * replicas
                rec_total_ram = rec_single_ram * replicas
                rec_monthly_cost = round(
                    (rec_total_cpu * HOURLY_CPU_CORE_RATE + rec_total_ram * HOURLY_RAM_GIB_RATE) * HOURS_PER_MONTH + (metrics["storage_pvc_gib"] * MONTHLY_STORAGE_GB_RATE),
                    2
                )
                monthly_savings = round(max(0.0, metrics["monthly_requested_cost"] - rec_monthly_cost), 2)
                annual_savings = round(monthly_savings * 12.0, 2)

                # Formatting Kubernetes millicores and MiB
                cur_cpu_str = f"{int(single_req_cpu * 1000)}m" if single_req_cpu < 1.0 else f"{single_req_cpu:.1f}"
                cur_ram_str = f"{int(single_req_ram * 1024)}Mi"
                rec_cpu_str = f"{int(rec_single_cpu * 1000)}m" if rec_single_cpu < 1.0 else f"{rec_single_cpu:.1f}"
                rec_ram_str = f"{int(rec_single_ram * 1024)}Mi"

                # YAML Manifest Patch Diff
                container_name = w.get("container", "main")
                yaml_diff = (
                    f"--- a/k8s/{metrics['namespace']}/{metrics['workload']}.yaml\n"
                    f"+++ b/k8s/{metrics['namespace']}/{metrics['workload']}.yaml\n"
                    f"@@ resources.requests @@\n"
                    f"       containers:\n"
                    f"       - name: {container_name}\n"
                    f"         resources:\n"
                    f"           requests:\n"
                    f"-            cpu: \"{cur_cpu_str}\"\n"
                    f"-            memory: \"{cur_ram_str}\"\n"
                    f"+            cpu: \"{rec_cpu_str}\"\n"
                    f"+            memory: \"{rec_ram_str}\"\n"
                )

                recommendations.append({
                    "cluster": metrics["cluster"],
                    "namespace": metrics["namespace"],
                    "workload": metrics["workload"],
                    "kind": metrics["kind"],
                    "container": container_name,
                    "replicas": replicas,
                    "current_efficiency_pct": eff,
                    "current_monthly_cost": metrics["monthly_requested_cost"],
                    "recommended_monthly_cost": rec_monthly_cost,
                    "monthly_savings": monthly_savings,
                    "annual_savings": annual_savings,
                    "formatted_monthly_savings": converter.format_dual(monthly_savings, primary_currency=currency),
                    "formatted_annual_savings": converter.format_dual(annual_savings, primary_currency=currency),
                    "current_cpu": cur_cpu_str,
                    "recommended_cpu": rec_cpu_str,
                    "current_memory": cur_ram_str,
                    "recommended_memory": rec_ram_str,
                    "yaml_diff": yaml_diff
                })

        recommendations.sort(key=lambda x: x["monthly_savings"], reverse=True)
        return recommendations

    def to_focus_records(self, account_id: str = "582812122408", region: str = "us-east-1") -> List[Dict[str, Any]]:
        """
        Maps Kubernetes container cost allocations directly into the FOCUS 1.0 specification schema.
        Enables cross-cloud DuckDB lakehouse queries across both infrastructure and container pods.
        """
        from datetime import datetime, timezone
        import uuid

        now_iso = datetime.now(timezone.utc).isoformat()
        records = []

        for w in self.workloads:
            m = self.calculate_workload_cost(w)
            cluster = m["cluster"]
            ns = m["namespace"]
            wk = m["workload"]
            kind = m["kind"]

            res_id = f"k8s/{cluster}/{ns}/{wk}"
            tags = {
                "k8s_cluster": cluster,
                "k8s_namespace": ns,
                "k8s_workload": wk,
                "k8s_kind": kind,
                **w.get("labels", {})
            }

            records.append({
                "ChargeId": str(uuid.uuid4()),
                "ProviderName": "AWS",
                "BillingAccountId": account_id,
                "BillingAccountName": "EKS Production Fleet",
                "SubAccountId": account_id,
                "SubAccountName": f"Namespace-{ns}",
                "RegionId": region,
                "RegionName": region,
                "ServiceName": "Amazon Elastic Kubernetes Service",
                "ServiceCategory": "Container",
                "ResourceId": res_id,
                "ResourceID": res_id,
                "ResourceName": wk,
                "ResourceType": kind,
                "ChargeCategory": "Usage",
                "PricingCategory": "Allocated",
                "BilledCost": m["monthly_requested_cost"],
                "EffectiveCost": m["monthly_requested_cost"],
                "ListCost": m["monthly_requested_cost"],
                "Currency": "USD",
                "UsageQuantity": m["requested_cpu_cores"] * HOURS_PER_MONTH,
                "UsageUnit": "Core-Hours",
                "PricingQuantity": m["requested_cpu_cores"] * HOURS_PER_MONTH,
                "PricingUnit": "Core-Hours",
                "ChargePeriodStart": now_iso,
                "ChargePeriodEnd": now_iso,
                "Tags": tags
            })

        return records

    def ingest_opencost_payload(self, payload: Dict[str, Any]) -> int:
        """
        Parses OpenCost allocation API JSON format and adds/updates workload items.
        OpenCost format: {"code": 200, "data": [{"default/pod-abc": {...}}]}
        """
        new_items = []
        data = payload.get("data", [])
        if isinstance(data, list):
            for entry in data:
                if isinstance(entry, dict):
                    for key, val in entry.items():
                        # key format: namespace/workload or cluster/namespace/workload
                        parts = key.split("/")
                        ns = parts[0] if len(parts) > 1 else "default"
                        name = parts[1] if len(parts) > 1 else parts[0]
                        cpu_req = float(val.get("cpuCoreRequestAverage", val.get("cpuCost", 0.5)))
                        cpu_ut = float(val.get("cpuCoreUsageAverage", cpu_req * 0.3))
                        ram_req = float(val.get("ramByteRequestAverage", 1024**3 * 2)) / (1024**3)
                        ram_ut = float(val.get("ramByteUsageAverage", ram_req * 0.4)) / (1024**3)

                        new_items.append({
                            "cluster": val.get("cluster", "eks-cluster"),
                            "namespace": ns,
                            "workload": name,
                            "kind": val.get("controllerKind", "Deployment"),
                            "replicas": int(val.get("replicas", 1)),
                            "container": val.get("container", "app"),
                            "requested_cpu_cores": round(cpu_req, 2),
                            "utilized_cpu_cores": round(cpu_ut, 2),
                            "requested_ram_gib": round(ram_req, 2),
                            "utilized_ram_gib": round(ram_ut, 2),
                            "storage_pvc_gib": 0.0,
                            "labels": val.get("labels", {})
                        })

        if new_items:
            self.workloads = new_items
            return len(new_items)
        return 0


# Global Singleton
opencost_engine = KubernetesCostEngine()
