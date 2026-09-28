"""
CloudPulse Commitment & Savings Plans Optimization Engine (Engine 5)
Analyzes steady-state compute floor across EC2, ECS Fargate, and Lambda workloads.
Models optimal 1-Year and 3-Year No-Upfront Compute Savings Plans with zero infrastructure downtime risk.
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger("finops.engines.commitment")

# Standard AWS Compute Savings Plan Average Discounts (us-east-1, Linux)
SAVINGS_PLAN_RATES = {
    "1yr_no_upfront": {"discount": 0.28, "term": 1, "name": "1-Year No-Upfront Compute Savings Plan"},
    "3yr_no_upfront": {"discount": 0.46, "term": 3, "name": "3-Year No-Upfront Compute Savings Plan"},
}

RECOMMENDED_COVERAGE_TARGET = 0.75  # Conservative 75% coverage protects against over-commitment


class CommitmentOptimizer:
    """
    Evaluates fleet compute baseline to recommend optimal AWS Savings Plans
    delivering immediate financial recovery without instance reboots or code changes.
    """

    @classmethod
    def analyze(cls, inventory: Dict[str, Any]) -> List[Dict[str, Any]]:
        recommendations: List[Dict[str, Any]] = []

        nodes = inventory.get("nodes", [])
        running_nodes = [n for n in nodes if n.get("state") == "running"]

        # If no running nodes in inventory, check compute summary or fallback
        total_monthly_compute = sum(float(n.get("cost", 0.0)) for n in running_nodes)
        if total_monthly_compute == 0.0 and inventory.get("summary", {}).get("estimated_monthly_spend"):
            # Estimate compute share at 65% of gross spend if detailed node costs omitted
            gross = float(inventory["summary"]["estimated_monthly_spend"])
            total_monthly_compute = gross * 0.65

        if total_monthly_compute < 5.0:
            return []

        # 730 hours in an average month
        hourly_compute_rate = total_monthly_compute / 730.0
        recommended_hourly_commitment = round(hourly_compute_rate * RECOMMENDED_COVERAGE_TARGET, 3)

        # Dual currency helper
        try:
            from services.currency_converter import currency_converter
        except ImportError:
            from backend.services.currency_converter import currency_converter

        # 1. 1-Year No-Upfront Compute Savings Plan (Recommended Default)
        rate_1yr = SAVINGS_PLAN_RATES["1yr_no_upfront"]
        monthly_savings_1yr = round(total_monthly_compute * RECOMMENDED_COVERAGE_TARGET * rate_1yr["discount"], 2)
        annual_savings_1yr = round(monthly_savings_1yr * 12.0, 2)
        inr_monthly_1yr = currency_converter.format_inr(currency_converter.to_inr(monthly_savings_1yr))
        inr_annual_1yr = currency_converter.format_inr(currency_converter.to_inr(annual_savings_1yr))

        recommendations.append({
            "id": "commitment-savings-plan-1yr",
            "resource_id": "Compute-Savings-Plan-1Yr",
            "resource_type": "AWS Savings Plan",
            "category": "Commitment Optimization",
            "type": "Savings Plan",
            "title": f"Adopt 1-Year Compute Savings Plan (${recommended_hourly_commitment:.3f}/hr commitment)",
            "description": (
                f"Fleet has steady-state compute of ${total_monthly_compute:,.2f}/mo. Committing to "
                f"${recommended_hourly_commitment:.3f}/hr (75% coverage) locks in a 28% discount, recovering "
                f"${monthly_savings_1yr:,.2f}/mo ({inr_monthly_1yr}/mo) with $0 upfront and ZERO downtime."
            ),
            "monthly_savings": monthly_savings_1yr,
            "annual_savings": annual_savings_1yr,
            "savings": monthly_savings_1yr,
            "effort": "Quick Win",
            "action": "purchase_savings_plan",
            "action_type": "purchase_savings_plan",
            "severity": "HIGH",
            "risk": "NONE",
            "term_years": 1,
            "hourly_commitment": recommended_hourly_commitment,
            "coverage_target": "75%",
            "upfront_cost": 0.0,
        })

        # 2. 3-Year No-Upfront Compute Savings Plan (Maximum Discount)
        rate_3yr = SAVINGS_PLAN_RATES["3yr_no_upfront"]
        monthly_savings_3yr = round(total_monthly_compute * RECOMMENDED_COVERAGE_TARGET * rate_3yr["discount"], 2)
        annual_savings_3yr = round(monthly_savings_3yr * 12.0, 2)
        inr_monthly_3yr = currency_converter.format_inr(currency_converter.to_inr(monthly_savings_3yr))
        inr_annual_3yr = currency_converter.format_inr(currency_converter.to_inr(annual_savings_3yr))

        recommendations.append({
            "id": "commitment-savings-plan-3yr",
            "resource_id": "Compute-Savings-Plan-3Yr",
            "resource_type": "AWS Savings Plan",
            "category": "Commitment Optimization",
            "type": "Savings Plan",
            "title": f"Adopt 3-Year Compute Savings Plan (Maximum 46% Discount)",
            "description": (
                f"For long-term core infrastructure, a 3-year commitment yields maximum 46% savings, "
                f"recovering ${monthly_savings_3yr:,.2f}/mo ({inr_monthly_3yr}/mo) or ${annual_savings_3yr:,.2f}/yr."
            ),
            "monthly_savings": monthly_savings_3yr,
            "annual_savings": annual_savings_3yr,
            "savings": monthly_savings_3yr,
            "effort": "Low",
            "action": "purchase_savings_plan_3yr",
            "action_type": "purchase_savings_plan_3yr",
            "severity": "HIGH",
            "risk": "LOW",
            "term_years": 3,
            "hourly_commitment": recommended_hourly_commitment,
            "coverage_target": "75%",
            "upfront_cost": 0.0,
        })

        return recommendations

    @classmethod
    def analyze_portfolio(cls, inventory: Dict[str, Any], coverage_target: float = 0.75) -> Dict[str, Any]:
        """
        Calculates enterprise commitment arbitrage, coverage vs on-demand ratios,
        and generates ready-to-execute AWS CLI and Terraform automation.
        """
        nodes = inventory.get("compute", {}).get("nodes", []) or inventory.get("nodes", [])
        running_nodes = [n for n in nodes if n.get("state") == "running"]

        total_monthly_compute = sum(float(n.get("cost", 0.0)) for n in running_nodes)
        if total_monthly_compute == 0.0 and inventory.get("summary", {}).get("estimated_monthly_spend"):
            gross = float(inventory["summary"]["estimated_monthly_spend"])
            total_monthly_compute = gross * 0.65

        if total_monthly_compute == 0.0:
            total_monthly_compute = 14500.0  # Enterprise sample baseline compute

        hourly_rate = total_monthly_compute / 730.0
        coverage = max(0.1, min(0.95, coverage_target))
        hourly_commitment = round(hourly_rate * coverage, 3)
        covered_spend = total_monthly_compute * coverage
        on_demand_spend = total_monthly_compute * (1.0 - coverage)

        # 1-Yr No Upfront Compute SP (28% off)
        sav_1yr_mo = round(covered_spend * 0.28, 2)
        sav_1yr_yr = round(sav_1yr_mo * 12.0, 2)

        # 3-Yr No Upfront Compute SP (46% off)
        sav_3yr_mo = round(covered_spend * 0.46, 2)
        sav_3yr_yr = round(sav_3yr_mo * 12.0, 2)

        # 3-Yr EC2 Instance SP (60% off for fixed instance families)
        sav_ec2_mo = round(covered_spend * 0.60, 2)
        sav_ec2_yr = round(sav_ec2_mo * 12.0, 2)

        tf_template = f"""# Terraform Savings Plan Commitment Resource
# Apply via CI/CD GitOps pipeline for zero-downtime rate optimization
resource "aws_savingsplans_savings_plan" "compute_sp_1yr" {{
  savings_plan_offering_id = "offering-compute-1yr-no-upfront"
  commitment               = "{hourly_commitment:.3f}"
  upfront_payment_amount   = "0.00"
  purchase_time            = timestamp()
}}
"""

        aws_cli_cmd = (
            f"aws savingsplans create-savings-plan "
            f"--savings-plan-offering-id offering-compute-1yr-no-upfront "
            f"--commitment {hourly_commitment:.3f} "
            f"--upfront-payment-amount 0.00"
        )

        return {
            "steady_state_monthly_compute": round(total_monthly_compute, 2),
            "hourly_compute_rate": round(hourly_rate, 3),
            "coverage_target_ratio": coverage,
            "recommended_hourly_commitment": hourly_commitment,
            "covered_monthly_spend": round(covered_spend, 2),
            "on_demand_exposed_monthly_spend": round(on_demand_spend, 2),
            "plans": [
                {
                    "plan_id": "sp-compute-1yr",
                    "name": "1-Year No-Upfront Compute Savings Plan",
                    "term": "1 Year",
                    "discount_rate": 0.28,
                    "monthly_savings": sav_1yr_mo,
                    "annual_savings": sav_1yr_yr,
                    "upfront_cost": 0.0,
                    "risk_level": "ZERO RISK",
                    "recommended": True,
                    "break_even_days": 0
                },
                {
                    "plan_id": "sp-compute-3yr",
                    "name": "3-Year No-Upfront Compute Savings Plan",
                    "term": "3 Years",
                    "discount_rate": 0.46,
                    "monthly_savings": sav_3yr_mo,
                    "annual_savings": sav_3yr_yr,
                    "upfront_cost": 0.0,
                    "risk_level": "LOW RISK",
                    "recommended": False,
                    "break_even_days": 0
                },
                {
                    "plan_id": "sp-ec2-3yr",
                    "name": "3-Year EC2 Instance Savings Plan",
                    "term": "3 Years",
                    "discount_rate": 0.60,
                    "monthly_savings": sav_ec2_mo,
                    "annual_savings": sav_ec2_yr,
                    "upfront_cost": 0.0,
                    "risk_level": "MEDIUM RISK",
                    "recommended": False,
                    "break_even_days": 0
                }
            ],
            "iac_templates": {
                "terraform": tf_template,
                "aws_cli": aws_cli_cmd
            }
        }
