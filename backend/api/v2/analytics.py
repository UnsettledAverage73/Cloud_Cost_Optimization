"""
CloudPulse Real-Time Anomaly Detection & Spend Forecasting API Router
Statistical z-score outlier detection, multi-cloud anomaly scanning, and
Holt-Winters time-series predictive forecasting.
"""

from typing import Optional
from fastapi import APIRouter

try:
    from services.anomaly_detector import anomaly_detector
    from services.spend_forecaster import spend_forecaster
    from engines.focus_spec import FOCUSNormalizer
    from core.state import resolve_active_inventory
except ImportError:
    from backend.services.anomaly_detector import anomaly_detector
    from backend.services.spend_forecaster import spend_forecaster
    from backend.engines.focus_spec import FOCUSNormalizer
    from backend.core.state import resolve_active_inventory

router = APIRouter(prefix="/api/v2/analytics", tags=["Analytics, Anomalies & Forecasting"])


@router.get("/anomalies")
async def get_cost_anomalies(severity: Optional[str] = None):
    """Returns detected cost anomalies across multi-cloud inventory and FOCUS records."""
    if not anomaly_detector.cached_anomalies:
        inventory = resolve_active_inventory()
        focus_records = FOCUSNormalizer.convert_inventory_to_focus(inventory)
        anomaly_detector.scan_inventory_and_focus(inventory, focus_records)

    anomalies = anomaly_detector.get_anomalies(severity)
    return {
        "count": len(anomalies),
        "severity_filter": severity or "ALL",
        "anomalies": anomalies
    }


@router.post("/anomalies/scan")
async def trigger_anomaly_scan():
    """Triggers an on-demand statistical anomaly scan against live cloud inventory."""
    inventory = resolve_active_inventory()
    focus_records = FOCUSNormalizer.convert_inventory_to_focus(inventory)
    anomalies = anomaly_detector.scan_inventory_and_focus(inventory, focus_records)
    return {
        "status": "scan_complete",
        "anomalies_detected": len(anomalies),
        "anomalies": anomalies
    }


@router.get("/forecast")
async def get_spend_forecast(days: int = 30, budget: float = 100.0):
    """Calculates Holt-Winters linear trend spend forecast and budget burn-rate."""
    inventory = resolve_active_inventory()
    forecast = spend_forecaster.forecast_from_inventory(
        inventory=inventory,
        forecast_days=days,
        monthly_budget=budget
    )
    return forecast


@router.post("/forecast")
async def calculate_custom_forecast(payload: dict):
    """Calculates custom spend forecast from a user-supplied daily history time-series."""
    history = payload.get("daily_history", [])
    days = int(payload.get("forecast_days", 30))
    budget = float(payload.get("monthly_budget", 100.0))
    mtd = payload.get("mtd_spend")
    if mtd is not None:
        mtd = float(mtd)

    forecast = spend_forecaster.forecast_spend(
        daily_history=history,
        forecast_days=days,
        monthly_budget=budget,
        mtd_spend=mtd
    )
    return forecast
