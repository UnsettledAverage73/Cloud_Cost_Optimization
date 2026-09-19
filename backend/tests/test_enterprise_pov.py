import pytest
import json
import argparse
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

from services.currency_converter import CurrencyConverter, currency_converter
from collectors.offline_ingest import OfflineIngestionCollector
from services.pov_reporter import PoVReporter
from cli_main import cmd_pov
from main import app


# =====================================================================
# 1. CURRENCY CONVERTER & FINANCIAL LOCALIZATION TESTS
# =====================================================================

def test_currency_converter_calculations():
    converter = CurrencyConverter(usd_to_inr_rate=84.0)

    # Conversion
    assert converter.to_inr(100.0) == 8400.0
    assert converter.to_usd(8400.0) == 100.0

    # US formatting
    assert converter.format_usd(1234.50) == "$1,234.50"
    assert converter.format_usd(1_500_000.0) == "$1.50M"

    # Indian notation
    assert converter.format_inr(50_000.0) == "₹50,000.00"
    assert converter.format_inr(150_000.0) == "₹1.50 L"
    assert converter.format_inr(15_000_000.0) == "₹1.50 Cr"
    assert converter.format_inr(100_000_000.0) == "₹10.00 Cr"

    # Dual formatting
    dual_usd = converter.format_dual(100.0, primary_currency="USD")
    assert "$100.00" in dual_usd
    assert "₹8,400.00" in dual_usd

    dual_inr = converter.format_dual(100.0, primary_currency="INR")
    assert "₹8,400.00" in dual_inr


# =====================================================================
# 2. OFFLINE INGESTION COLLECTOR TESTS
# =====================================================================

def test_offline_ingest_json_files(tmp_path):
    # Create sample instance json
    inst_file = tmp_path / "instances.json"
    inst_data = {
        "Reservations": [
            {
                "Instances": [
                    {
                        "InstanceId": "i-offline-test-1",
                        "InstanceType": "t3.micro",
                        "State": {"Name": "running"},
                        "Tags": [{"Key": "Name", "Value": "web-prod"}],
                        "metrics": {"cpu_utilization_avg": 0.4}
                    }
                ]
            }
        ]
    }
    inst_file.write_text(json.dumps(inst_data))

    # Create sample volumes json
    vol_file = tmp_path / "volumes.json"
    vol_data = {
        "Volumes": [
            {
                "VolumeId": "vol-offline-01",
                "VolumeType": "gp2",
                "Size": 100,
                "State": "available",
                "Attachments": []
            }
        ]
    }
    vol_file.write_text(json.dumps(vol_data))

    collector = OfflineIngestionCollector(tmp_path)
    inv = collector.load_inventory()

    assert inv["metadata"]["ingestion_mode"] == "offline_directory"
    assert len(inv["compute"]["nodes"]) == 1
    assert inv["compute"]["nodes"][0]["instance_id"] == "i-offline-test-1"
    assert len(inv["ec2_other_resources"]["ebs_volumes"]) == 1
    assert inv["ec2_other_resources"]["ebs_volumes"][0]["is_orphaned"] is True
    assert inv["summary"]["estimated_monthly_spend"] > 0


def test_offline_ingest_cur_csv(tmp_path):
    csv_file = tmp_path / "sample_cur.csv"
    csv_content = """lineItem/ResourceId,lineItem/ProductCode,lineItem/UnblendedCost,product/instanceType
i-cur-node-1,AmazonEC2,25.50,t3.medium
vol-cur-disk-1,AmazonEC2,10.00,gp2
"""
    csv_file.write_text(csv_content)

    collector = OfflineIngestionCollector(csv_file)
    inv = collector.load_inventory()

    assert inv["metadata"]["ingestion_mode"] == "offline_csv"
    assert len(inv["compute"]["nodes"]) == 1
    assert inv["compute"]["nodes"][0]["instance_id"] == "i-cur-node-1"
    assert len(inv["ec2_other_resources"]["ebs_volumes"]) == 1
    assert inv["summary"]["estimated_monthly_spend"] == 35.50


def test_offline_ingest_cur_parquet(tmp_path):
    import duckdb
    parquet_file = tmp_path / "sample_cur.parquet"
    conn = duckdb.connect(":memory:")
    conn.execute('''
        CREATE TABLE sample_cur AS SELECT 
            'i-parquet-node-1' as "ResourceId",
            'AmazonEC2' as "ServiceName",
            't3.large' as "ResourceType",
            60.50 as "EffectiveCost"
        UNION ALL SELECT
            'vol-parquet-disk-1' as "ResourceId",
            'AmazonEBS' as "ServiceName",
            'gp3' as "ResourceType",
            20.00 as "EffectiveCost"
    ''')
    conn.execute(f"COPY sample_cur TO '{parquet_file}' (FORMAT PARQUET)")

    collector = OfflineIngestionCollector(parquet_file)
    inv = collector.load_inventory()

    assert inv["metadata"]["ingestion_mode"] == "offline_parquet"
    assert len(inv["compute"]["nodes"]) == 1
    assert inv["compute"]["nodes"][0]["instance_id"] == "i-parquet-node-1"
    assert len(inv["ec2_other_resources"]["ebs_volumes"]) == 1
    assert inv["summary"]["estimated_monthly_spend"] == 80.50



# =====================================================================
# 3. EXECUTIVE POV REPORTER TESTS
# =====================================================================

def test_pov_reporter_html_and_markdown():
    reporter = PoVReporter(currency="INR", usd_to_inr_rate=84.0)
    inventory = {
        "metadata": {"account_id": "112233445566", "region": "us-east-1"},
        "compute": {
            "nodes": [
                {
                    "instance_id": "i-pov-node",
                    "instance_type": "t3.micro",
                    "cost": 7.60,
                    "metrics": {"cpu_utilization_avg": 0.2}
                }
            ]
        },
        "ec2_other_resources": {
            "ebs_volumes": [
                {
                    "volume_id": "vol-pov-storage",
                    "volume_type": "gp2",
                    "cost": 10.00,
                    "is_orphaned": False
                }
            ],
            "elastic_ips": [],
            "security_groups": []
        },
        "summary": {"estimated_monthly_spend": 17.60}
    }

    # 1. HTML generation
    html = reporter.generate_html_report(inventory, account_name="TestCorp Enterprise")
    assert "<!DOCTYPE html>" in html
    assert "CloudPulse Autopilot" in html
    assert "TestCorp Enterprise" in html
    assert "112233445566" in html
    assert "i-pov-node" in html
    assert "vol-pov-storage" in html
    assert "₹" in html  # Currency symbol included

    # 2. Markdown generation
    md = reporter.generate_markdown_report(inventory, account_name="TestCorp Enterprise")
    assert "# 🚀 CloudPulse Enterprise FinOps" in md
    assert "TestCorp Enterprise" in md
    assert "₹" in md


# =====================================================================
# 4. CLI COMMAND POV TESTS
# =====================================================================

def test_cli_cmd_pov(tmp_path):
    report_file = tmp_path / "Executive_Audit.html"
    args = argparse.Namespace(
        format="html",
        currency="INR",
        rate=84.0,
        output=str(report_file),
        offline_dir=None,
        offline_file=None,
        account_name="Acme Corp",
        open_browser=False
    )
    cmd_pov(args)
    assert report_file.exists()
    content = report_file.read_text()
    assert "CloudPulse Autopilot" in content
    assert "Acme Corp" in content


# =====================================================================
# 5. FASTAPI POV ENDPOINTS TESTS
# =====================================================================

def test_fastapi_pov_endpoints():
    client = TestClient(app)

    # 1. GET /api/v2/analytics/pov/summary
    res_summary = client.get("/api/v2/analytics/pov/summary?currency=INR&rate=84.0")
    assert res_summary.status_code == 200
    data = res_summary.json()
    assert "gross_monthly_spend_formatted" in data
    assert "recoverable_annual_savings_formatted" in data
    assert "₹" in data["gross_monthly_spend_formatted"]
    assert data["currency"] == "INR"

    # 2. GET /api/v2/analytics/pov/report.html
    res_html = client.get("/api/v2/analytics/pov/report.html?currency=USD")
    assert res_html.status_code == 200
    assert "text/html" in res_html.headers["content-type"]
    assert "CloudPulse Autopilot" in res_html.text
