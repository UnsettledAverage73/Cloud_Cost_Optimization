import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from botocore.exceptions import BotoCoreError, ClientError
from collectors.base import AWSBaseCollector

logger = logging.getLogger("finops.collectors.cost_explorer")


class CostExplorerCollector(AWSBaseCollector):
    """
    Collects actual unblended spend, daily burn rate, service breakdowns,
    and native rightsizing recommendations from AWS Cost Explorer.
    """

    def collect(self) -> Dict[str, Any]:
        daily_spend = self.collect_daily_spend(days=14)
        service_breakdown = self.collect_service_breakdown(days=30)
        rightsizing = self.collect_native_rightsizing()

        total_recent_spend = round(sum(d["amount"] for d in daily_spend), 2)
        burn_rate_daily = round(total_recent_spend / len(daily_spend), 2) if daily_spend else 0.0

        return {
            "daily_spend": daily_spend,
            "service_breakdown": service_breakdown,
            "native_rightsizing": rightsizing,
            "total_recent_spend": total_recent_spend,
            "burn_rate_daily": burn_rate_daily,
            "projected_monthly_spend": round(burn_rate_daily * 30.5, 2),
        }

    def collect_daily_spend(self, days: int = 14) -> List[Dict[str, Any]]:
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=days)

        resp = self.call(
            "ce",
            "get_cost_and_usage",
            {
                "TimePeriod": {
                    "Start": start_date.strftime("%Y-%m-%d"),
                    "End": end_date.strftime("%Y-%m-%d"),
                },
                "Granularity": "DAILY",
                "Metrics": ["UnblendedCost"],
            },
            default={"ResultsByTime": []},
            custom_region="us-east-1",  # Cost Explorer API is global in us-east-1
        )

        daily_spend: List[Dict[str, Any]] = []
        for period in resp.get("ResultsByTime", []):
            time_start = period.get("TimePeriod", {}).get("Start", "")
            cost_amount = float(
                period.get("Total", {}).get("UnblendedCost", {}).get("Amount", 0.0)
            )
            daily_spend.append({
                "date": time_start,
                "amount": round(cost_amount, 2),
                "unit": period.get("Total", {}).get("UnblendedCost", {}).get("Unit", "USD"),
            })

        return daily_spend

    def collect_service_breakdown(self, days: int = 30) -> List[Dict[str, Any]]:
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=days)

        resp = self.call(
            "ce",
            "get_cost_and_usage",
            {
                "TimePeriod": {
                    "Start": start_date.strftime("%Y-%m-%d"),
                    "End": end_date.strftime("%Y-%m-%d"),
                },
                "Granularity": "MONTHLY",
                "Metrics": ["UnblendedCost"],
                "GroupBy": [{"Type": "DIMENSION", "Key": "SERVICE"}],
            },
            default={"ResultsByTime": []},
            custom_region="us-east-1",
        )

        service_costs: List[Dict[str, Any]] = []
        for period in resp.get("ResultsByTime", []):
            for group in period.get("Groups", []):
                service_name = group.get("Keys", ["Other"])[0]
                amount = float(group.get("Metrics", {}).get("UnblendedCost", {}).get("Amount", 0.0))
                if amount > 0.01:
                    service_costs.append({
                        "service": service_name,
                        "amount": round(amount, 2),
                    })

        return sorted(service_costs, key=lambda s: s["amount"], reverse=True)

    def collect_native_rightsizing(self) -> List[Dict[str, Any]]:
        try:
            client = self.get_client("ce", "us-east-1")
            resp = client.get_rightsizing_recommendation(Service="AmazonEC2")
        except (ClientError, BotoCoreError) as err:
            logger.debug(f"Cost Explorer rightsizing opt-in notice: {err}")
            return []
        except Exception as ex:
            logger.debug(f"Cost Explorer rightsizing notice: {ex}")
            return []

        recommendations = []
        for rec in resp.get("RightsizingRecommendations", []):
            current = rec.get("CurrentInstance", {})
            action = rec.get("RightsizingType", "Modify")
            savings = float(
                rec.get("VolumeRecommendationDetail", {})
                .get("EstimatedMonthlySavings", 0.0)
            ) or 15.0

            recommendations.append({
                "resource_id": current.get("ResourceId", "unknown"),
                "instance_type": current.get("ResourceDetails", {}).get("EC2ResourceDetails", {}).get("InstanceType"),
                "action": action,
                "estimated_monthly_savings": round(savings, 2),
            })

        return recommendations
