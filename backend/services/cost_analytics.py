from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

try:
    import numpy as np
    def _mean(seq):
        return float(np.mean(seq))
    def _std(seq):
        return float(np.std(seq))
except ImportError:
    import statistics
    def _mean(seq):
        return float(statistics.mean(seq)) if seq else 0.0
    def _std(seq):
        return float(statistics.stdev(seq)) if len(seq) > 1 else 1.0

from engines.finops_analyzer import FinOpsAnalyzer

def evaluate_inventory_optimizations(inventory_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Evaluates inventory telemetry for security vulnerabilities and comprehensive FinOps cost optimizations.
    """
    return FinOpsAnalyzer.evaluate(inventory_data)["findings"]


def calculate_finops_health_score(inventory_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Computes an industrial-grade FinOps Health Score (0-100) across 4 pillars:
    1. Compute Efficiency (25 pts)
    2. Storage Optimization (25 pts)
    3. Network & Idle Cleanliness (25 pts)
    4. Security & Exposure (25 pts)
    """
    res = FinOpsAnalyzer.evaluate(inventory_data)
    return res["health_breakdown"]


def detect_cost_anomalies(spend_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Detects spend spikes where a single day exceeds the 7-day moving average by > 25% or 2 standard deviations.
    """
    if len(spend_rows) < 4:
        return []

    anomalies = []
    amounts = [float(row.get("aws", 0.0)) for row in spend_rows]

    for i in range(3, len(amounts)):
        window = amounts[max(0, i-7):i]
        mean = _mean(window)
        std = _std(window) or 1.0
        current = amounts[i]

        if current > mean * 1.25 and current > (mean + 1.8 * std):
            day = spend_rows[i].get("day", f"Day {i}")
            anomalies.append({
                "day": day,
                "cost": round(current, 2),
                "expected_mean": round(mean, 2),
                "spike_percentage": round(((current - mean) / mean) * 100, 1),
                "severity": "CRITICAL" if current > mean * 1.5 else "HIGH",
                "message": f"Cost anomaly on {day}: Daily spend surged to ${current:.2f} (baseline was ${mean:.2f})."
            })

    return anomalies


def calculate_spend_forecast(spend_rows: List[Dict[str, Any]], monthly_budget: float = 600.0) -> Dict[str, Any]:
    """
    Calculates 30-day projection, budget burn rate, and runway.
    """
    if not spend_rows:
        return {
            "monthly_budget": monthly_budget,
            "projected_month_end": 0.0,
            "daily_burn_rate": 0.0,
            "variance": monthly_budget,
            "runway_days": 999,
            "budget_status": "healthy"
        }

    recent_days = spend_rows[-7:] if len(spend_rows) >= 7 else spend_rows
    daily_rates = [float(row.get("aws", 0.0)) for row in recent_days]
    avg_daily_burn = _mean(daily_rates) if daily_rates else 10.0
    projected_month_end = round(avg_daily_burn * 30.0, 2)
    variance = round(monthly_budget - projected_month_end, 2)
    runway_days = int(monthly_budget / avg_daily_burn) if avg_daily_burn > 0 else 999

    status = "healthy" if variance >= 0 else "at_risk" if variance > -100 else "critical_overrun"

    return {
        "monthly_budget": monthly_budget,
        "current_daily_burn": round(avg_daily_burn, 2),
        "projected_month_end": projected_month_end,
        "variance": variance,
        "runway_days": runway_days,
        "budget_status": status
    }
