import logging
from typing import Any, Dict, List

from engines.waste_analyzer import WasteAnalyzer
from engines.rightsizing_engine import RightsizingEngine
from engines.storage_optimizer import StorageOptimizer
from engines.network_optimizer import NetworkOptimizer
from engines.database_optimizer import DatabaseOptimizer
from engines.commitment_optimizer import CommitmentOptimizer

logger = logging.getLogger("finops.engines.analyzer")


class FinOpsAnalyzer:
    """
    Master FinOps intelligence orchestrator. Aggregates all specialized rule engines,
    computes the 4-Pillar Health Score, categorizes quick wins vs architectural changes,
    and projects month-end savings.
    """

    @classmethod
    def evaluate(cls, inventory: Dict[str, Any]) -> Dict[str, Any]:
        waste_findings = WasteAnalyzer.analyze(inventory)
        rightsizing_findings = RightsizingEngine.analyze(inventory)
        storage_findings = StorageOptimizer.analyze(inventory)
        network_findings = NetworkOptimizer.analyze(inventory)
        db_findings = DatabaseOptimizer.analyze(inventory)
        commitment_findings = CommitmentOptimizer.analyze(inventory)

        # Identify mutually exclusive items and tag alternative options
        # 1. Compute resource: Idle terminate/stop vs Graviton migration / downsizing
        idle_resource_ids = {
            item.get("resource_id"): item
            for item in waste_findings
            if item.get("action") in ("stop", "terminate") and item.get("resource_id")
        }

        for item in rightsizing_findings:
            res_id = item.get("resource_id")
            if res_id and res_id in idle_resource_ids:
                item["is_alternative"] = True
                item["alternative_to"] = idle_resource_ids[res_id].get("id")
                item["conflict_note"] = "Alternative strategy: apply only if workload must remain running and cannot be stopped."

        # 2. Commitment plans: 3-Year is primary (max savings), 1-Year is flexible alternative horizon
        has_3yr_plan = any(item.get("id") == "commitment-savings-plan-3yr" for item in commitment_findings)
        if has_3yr_plan:
            for item in commitment_findings:
                if item.get("id") == "commitment-savings-plan-1yr":
                    item["is_alternative"] = True
                    item["alternative_to"] = "commitment-savings-plan-3yr"
                    item["conflict_note"] = "Alternative 1-Year commitment horizon. Do not stack with 3-Year plan."

        # Merge and deduplicate by resource_id + action
        all_findings: List[Dict[str, Any]] = []
        seen_keys = set()

        for group in [waste_findings, rightsizing_findings, storage_findings, network_findings, db_findings, commitment_findings]:
            for item in group:
                key = (item.get("resource_id"), item.get("action"))
                if key not in seen_keys:
                    seen_keys.add(key)
                    all_findings.append(item)

        # Sort strictly by monthly savings descending
        all_findings.sort(key=lambda x: x.get("monthly_savings", 0.0), reverse=True)

        quick_wins = [f for f in all_findings if f.get("effort") == "Quick Win" or f.get("risk") == "NONE"]
        architectural = [f for f in all_findings if f not in quick_wins]

        # Calculate primary non-conflicting savings so alternative options are not double-counted
        primary_findings = [f for f in all_findings if not f.get("is_alternative")]
        total_potential_savings = round(sum(f.get("monthly_savings", 0.0) for f in primary_findings), 2)
        if total_potential_savings == 0.0 and all_findings:
            total_potential_savings = round(sum(f.get("monthly_savings", 0.0) for f in all_findings), 2)

        # Track applied status and realized vs pending savings
        applied_ids = set(inventory.get("applied_optimizations", []))
        for f in all_findings:
            f["is_applied"] = f["id"] in applied_ids

        applied_primary = [f for f in primary_findings if f["id"] in applied_ids]
        pending_primary = [f for f in primary_findings if f["id"] not in applied_ids]

        realized_monthly_savings = round(sum(f.get("monthly_savings", 0.0) for f in applied_primary), 2)
        pending_potential_savings = round(sum(f.get("monthly_savings", 0.0) for f in pending_primary), 2)

        total_monthly_spend = inventory.get("summary", {}).get("estimated_monthly_spend", 0.0)
        if total_monthly_spend == 0.0:
            total_monthly_spend = round(sum(n.get("cost", 0.0) for n in inventory.get("nodes", [])), 2) or 100.0

        savings_percentage = round((total_potential_savings / total_monthly_spend) * 100, 1) if total_monthly_spend > 0 else 0.0

        # Compute 4-Pillar Health Score
        health_breakdown = cls.calculate_health_score(inventory, all_findings)

        # Spend forecast
        forecast = cls.calculate_forecast(total_monthly_spend, total_potential_savings)

        return {
            "findings": all_findings,
            "total_findings": len(all_findings),
            "quick_wins": quick_wins,
            "architectural_improvements": architectural,
            "total_potential_monthly_savings": total_potential_savings,
            "pending_potential_savings": pending_potential_savings,
            "realized_monthly_savings": realized_monthly_savings,
            "applied_count": len([f for f in all_findings if f["id"] in applied_ids]),
            "pending_count": len([f for f in all_findings if f["id"] not in applied_ids]),
            "total_monthly_spend": total_monthly_spend,
            "savings_percentage": min(95.0, savings_percentage),
            "health_score": health_breakdown["overall_score"],
            "health_breakdown": health_breakdown,
            "forecast": forecast,
        }

    @staticmethod
    def calculate_health_score(inventory: Dict[str, Any], findings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Computes 4-Pillar FinOps Health Score (0 - 100):
        1. Compute Efficiency (25 pts)
        2. Storage Optimization (25 pts)
        3. Network & Cleanliness (25 pts)
        4. Security & Posture (25 pts)
        """
        compute_score = 25.0
        storage_score = 25.0
        network_score = 25.0
        security_score = 25.0

        # Compute deductions
        for node in inventory.get("nodes", []):
            if node.get("state") == "running":
                avg_cpu = node.get("metrics", {}).get("cpu_utilization_avg", 50.0)
                if avg_cpu < 5.0:
                    compute_score -= 5.0  # Idle instance
                elif avg_cpu < 20.0:
                    compute_score -= 2.0  # Underutilized

        # Storage deductions
        for vol in inventory.get("ebs_volumes", []):
            if vol.get("is_orphaned"):
                storage_score -= 6.0
            elif vol.get("volume_type") == "gp2":
                storage_score -= 2.0

        for snap in inventory.get("ebs_snapshots", []):
            if snap.get("is_stale"):
                storage_score -= 2.0

        for bucket in inventory.get("s3_buckets", []):
            if not bucket.get("has_lifecycle_policy"):
                storage_score -= 2.0

        # Network deductions
        for eip in inventory.get("elastic_ips", []):
            if eip.get("is_unattached"):
                network_score -= 6.0

        for nat in inventory.get("nat_gateways", []):
            if nat.get("is_idle"):
                network_score -= 6.0

        for lb in inventory.get("load_balancers", []):
            if lb.get("is_idle"):
                network_score -= 5.0

        # Security deductions
        open_ports_count = 0
        for sg in inventory.get("security_groups", []):
            if sg.get("is_publicly_exposed"):
                ports = sg.get("exposed_ports", [])
                critical_ports = {22, 3389, 5432, 3306, 27017, 6379}
                hit = any(p in critical_ports for p in ports)
                if hit:
                    security_score -= 8.0
                    open_ports_count += 1
                else:
                    security_score -= 3.0

        compute_score = max(0.0, min(25.0, round(compute_score, 1)))
        storage_score = max(0.0, min(25.0, round(storage_score, 1)))
        network_score = max(0.0, min(25.0, round(network_score, 1)))
        security_score = max(0.0, min(25.0, round(security_score, 1)))

        overall = round(compute_score + storage_score + network_score + security_score, 1)
        grade = "A" if overall >= 90 else "B" if overall >= 75 else "C" if overall >= 60 else "D" if overall >= 40 else "F"

        return {
            "overall_health_score": overall,
            "overall_score": overall,
            "grade": grade,
            "status": "Healthy" if overall >= 80 else "Needs Attention" if overall >= 60 else "Critical Waste",
            "pillars": {
                "compute_efficiency": {"score": compute_score, "max": 25.0},
                "storage_optimization": {"score": storage_score, "max": 25.0},
                "network_cleanliness": {"score": network_score, "max": 25.0},
                "security_posture": {"score": security_score, "max": 25.0},
            },
            "open_critical_ports": open_ports_count,
        }

    @staticmethod
    def calculate_forecast(monthly_spend: float, potential_savings: float) -> Dict[str, Any]:
        daily_burn_current = round(monthly_spend / 30.5, 2)
        optimized_monthly_spend = max(0.0, round(monthly_spend - potential_savings, 2))
        daily_burn_optimized = round(optimized_monthly_spend / 30.5, 2)

        return {
            "current_monthly_run_rate": monthly_spend,
            "daily_burn_current": daily_burn_current,
            "optimized_monthly_run_rate": optimized_monthly_spend,
            "daily_burn_optimized": daily_burn_optimized,
            "annual_projected_savings": round(potential_savings * 12, 2),
        }

    # Convenient aliases
    analyze = evaluate
    analyze_all = evaluate

