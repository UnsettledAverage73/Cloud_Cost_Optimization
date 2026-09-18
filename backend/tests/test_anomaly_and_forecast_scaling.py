"""
Unit & Integration Tests for CloudPulse Cost Anomaly Detection & Spend Forecaster (Phase 4).
Verifies statistical Z-score/IQR anomaly detection, Holt-Winters trend forecasting, budget burn-rate,
FastAPI REST analytics endpoints, and CLI commands.
"""

import json
import pytest
import argparse
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from services.anomaly_detector import FinOpsAnomalyDetector, anomaly_detector
from services.spend_forecaster import FinOpsSpendForecaster, DoubleExponentialSmoothing, spend_forecaster
from cli_main import cmd_anomalies, cmd_forecast
from main import app


@pytest.fixture
def clean_anomaly_detector():
    detector = FinOpsAnomalyDetector()
    detector.cached_anomalies = []
    return detector


def test_stats_and_iqr_calculation():
    """Verifies standard deviation, mean, and IQR calculations."""
    series = [10.0, 12.0, 11.0, 15.0, 11.0, 14.0, 13.0]
    mean, std = FinOpsAnomalyDetector.calculate_stats(series)
    assert round(mean, 2) == 12.29
    assert std > 0.0

    q1, q3, iqr = FinOpsAnomalyDetector.calculate_iqr(series)
    assert q1 <= q3
    assert iqr >= 0.0


def test_z_score_anomaly_detection(clean_anomaly_detector):
    """Tests detecting cost spike using Z-Score threshold."""
    time_series = [
        {"day": 1, "cost": 10.0},
        {"day": 2, "cost": 10.5},
        {"day": 3, "cost": 9.8},
        {"day": 4, "cost": 10.2},
        {"day": 5, "cost": 10.1},
        {"day": 6, "cost": 10.3},
        {"day": 7, "cost": 55.0}  # Major 5.5x spike
    ]
    anomalies = clean_anomaly_detector.detect_z_score_anomalies(time_series, value_key="cost", threshold=2.0)
    assert len(anomalies) == 1
    assert anomalies[0]["observed_value"] == 55.0
    assert anomalies[0]["z_score"] >= 2.0
    assert anomalies[0]["algorithm"] == "Z-Score"


def test_inventory_anomaly_detection_compute(clean_anomaly_detector):
    """Verifies that idle instances with <1% CPU incurring significant cost are flagged."""
    inventory = {
        "metadata": {"account_id": "123456789012"},
        "compute": {
            "nodes": [
                {
                    "instance_id": "i-idle-01",
                    "instance_type": "t3.micro",
                    "cost": 7.60,
                    "cpu_avg": 0.15,
                    "state": "running",
                    "availability_zone": "us-east-1a"
                }
            ]
        }
    }
    anomalies = clean_anomaly_detector.scan_inventory_and_focus(inventory)
    assert len(anomalies) >= 1
    compute_anom = [a for a in anomalies if a["anomaly_type"] == "IDLE_RUNAWAY"][0]
    assert compute_anom["resource_id"] == "i-idle-01"
    assert compute_anom["severity"] in ["MEDIUM", "HIGH", "CRITICAL"]
    assert "negligible CPU activity" in compute_anom["root_cause"]


def test_inventory_anomaly_detection_storage(clean_anomaly_detector):
    """Verifies that unattached or orphaned EBS volumes are flagged."""
    inventory = {
        "metadata": {"account_id": "123456789012"},
        "ec2_other_resources": {
            "ebs_volumes": [
                {
                    "volume_id": "vol-orphan-01",
                    "volume_type": "gp2",
                    "size_gb": 100,
                    "cost": 10.00,
                    "status": "available",
                    "attached": False
                }
            ]
        }
    }
    anomalies = clean_anomaly_detector.scan_inventory_and_focus(inventory)
    storage_anom = [a for a in anomalies if a["anomaly_type"] == "ORPHANED_STORAGE"]
    assert len(storage_anom) == 1
    assert storage_anom[0]["resource_id"] == "vol-orphan-01"
    assert storage_anom[0]["financial_impact_monthly"] == 10.00


def test_inventory_anomaly_detection_eips(clean_anomaly_detector):
    """Verifies that unassociated Elastic IPs are detected."""
    inventory = {
        "metadata": {"account_id": "123456789012"},
        "ec2_other_resources": {
            "elastic_ips": [
                {
                    "public_ip": "54.210.10.99",
                    "instance_id": None,
                    "network_interface_id": None
                }
            ]
        }
    }
    anomalies = clean_anomaly_detector.scan_inventory_and_focus(inventory)
    eip_anom = [a for a in anomalies if a["anomaly_type"] == "IDLE_NETWORK_SURCHARGE"]
    assert len(eip_anom) == 1
    assert eip_anom[0]["resource_id"] == "54.210.10.99"
    assert eip_anom[0]["financial_impact_monthly"] == 3.65


def test_focus_concentration_risk(clean_anomaly_detector):
    """Verifies spend concentration risk detection across FOCUS records."""
    inventory = {"metadata": {"account_id": "123456789012"}}
    focus_records = [
        {"ServiceName": "Amazon EC2", "EffectiveCost": 90.00},
        {"ServiceName": "Amazon CloudWatch", "EffectiveCost": 5.00},
        {"ServiceName": "Amazon S3", "EffectiveCost": 3.00}
    ]
    anomalies = clean_anomaly_detector.scan_inventory_and_focus(inventory, focus_records)
    conc_anom = [a for a in anomalies if a["anomaly_type"] == "CONCENTRATION_RISK"]
    assert len(conc_anom) == 1
    assert conc_anom[0]["resource_id"] == "Amazon EC2"
    assert conc_anom[0]["severity"] == "HIGH"


def test_holt_winters_linear_trend_fitting():
    """Tests Holt's double exponential smoothing trend fitting."""
    model = DoubleExponentialSmoothing(alpha=0.4, beta=0.2)
    # Linearly growing spend: 2, 4, 6, 8, 10
    history = [2.0, 4.0, 6.0, 8.0, 10.0]
    fitted, forecasts, res_std = model.fit_predict(history, forecast_steps=5)
    assert len(forecasts) == 5
    # Forecasts should continue the upward trajectory
    assert forecasts[0] > 10.0
    assert forecasts[-1] > forecasts[0]
    assert all(f >= 0.0 for f in forecasts)


def test_spend_forecaster_burn_rate_and_breach():
    """Verifies budget burn rate and breach day detection."""
    forecaster = FinOpsSpendForecaster()
    # High daily spend: $10/day with 10 days MTD ($100), monthly budget $150
    daily_history = [10.0] * 10
    result = forecaster.forecast_spend(
        daily_history=daily_history,
        forecast_days=20,
        monthly_budget=150.0,
        mtd_spend=100.0
    )
    assert result["budget_breach_predicted"] is True
    assert result["predicted_breach_day"] is not None
    # Breach should happen around day 5 (100 + 5*10 = 150)
    assert result["predicted_breach_day"] <= 6
    assert result["budget_utilization_pct"] > 100.0


def test_api_anomalies_endpoints():
    """Verifies FastAPI GET and POST /api/v2/analytics/anomalies endpoints."""
    client = TestClient(app)

    # Scan endpoint
    res_scan = client.post("/api/v2/analytics/anomalies/scan")
    assert res_scan.status_code == 200
    data_scan = res_scan.json()
    assert data_scan["status"] == "scan_complete"
    assert "anomalies" in data_scan

    # Get endpoint
    res_get = client.get("/api/v2/analytics/anomalies?severity=all")
    assert res_get.status_code == 200
    data_get = res_get.json()
    assert "count" in data_get
    assert isinstance(data_get["anomalies"], list)


def test_api_forecast_endpoints():
    """Verifies FastAPI GET and POST /api/v2/analytics/forecast endpoints."""
    client = TestClient(app)

    # GET inventory forecast
    res_get = client.get("/api/v2/analytics/forecast?days=14&budget=50.0")
    assert res_get.status_code == 200
    data_get = res_get.json()
    assert data_get["forecast_days"] == 14
    assert "projected_monthly_spend" in data_get
    assert len(data_get["daily_trajectory"]) == 14

    # POST custom forecast
    payload = {
        "daily_history": [5.0, 5.2, 5.1, 5.3, 5.0],
        "forecast_days": 10,
        "monthly_budget": 100.0,
        "mtd_spend": 25.0
    }
    res_post = client.post("/api/v2/analytics/forecast", json=payload)
    assert res_post.status_code == 200
    data_post = res_post.json()
    assert data_post["forecast_days"] == 10
    assert data_post["current_daily_run_rate"] > 0.0


def test_cli_cmd_anomalies_table_and_json(capsys):
    """Verifies CLI cmd_anomalies execution."""
    args_table = argparse.Namespace(
        severity="all",
        format="table",
        json_only=False,
        output=None,
        url="http://localhost:8000"
    )
    cmd_anomalies(args_table)
    captured = capsys.readouterr().out
    assert "CLOUDPULSE FINOPS COST ANOMALY DETECTION" in captured

    args_json = argparse.Namespace(
        severity="all",
        format="json",
        json_only=True,
        output=None,
        url="http://localhost:8000"
    )
    cmd_anomalies(args_json)
    captured_json = capsys.readouterr().out
    data = json.loads(captured_json)
    assert "anomalies" in data
    assert "count" in data


def test_cli_cmd_forecast_table_and_json(capsys):
    """Verifies CLI cmd_forecast execution."""
    args_table = argparse.Namespace(
        days=15,
        budget=100.0,
        format="table",
        json_only=False,
        output=None,
        url="http://localhost:8000"
    )
    cmd_forecast(args_table)
    captured = capsys.readouterr().out
    assert "CLOUDPULSE PREDICTIVE SPEND FORECAST" in captured
    assert "Daily Spend Run-Rate" in captured

    args_json = argparse.Namespace(
        days=15,
        budget=100.0,
        format="json",
        json_only=True,
        output=None,
        url="http://localhost:8000"
    )
    cmd_forecast(args_json)
    captured_json = capsys.readouterr().out
    data = json.loads(captured_json)
    assert "projected_monthly_spend" in data
    assert "daily_trajectory" in data
    assert len(data["daily_trajectory"]) == 15
