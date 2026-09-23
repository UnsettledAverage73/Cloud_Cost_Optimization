import pytest
from fastapi.testclient import TestClient
from main import app
from engines.focus_lakehouse import FOCUSLakehouse, focus_lakehouse
from engines.focus_spec import FOCUSNormalizer


@pytest.fixture
def sample_focus_records():
    return [
        {
            "ChargePeriodStart": "2026-09-01T00:00:00Z",
            "ChargePeriodEnd": "2026-09-30T23:59:59Z",
            "BillingAccountId": "111122223333",
            "SubAccountId": "111122223333",
            "ProviderName": "AWS",
            "RegionName": "us-east-1",
            "ServiceName": "Amazon Elastic Compute Cloud - Compute",
            "ResourceID": "i-test01",
            "ResourceType": "Instance",
            "EffectiveCost": 120.50,
            "ListCost": 120.50,
            "BilledCost": 120.50,
            "UsageQuantity": 730.0,
            "UsageUnit": "Hours",
            "PricingQuantity": 730.0,
            "PricingUnit": "Hours",
            "Currency": "USD"
        },
        {
            "ChargePeriodStart": "2026-09-01T00:00:00Z",
            "ChargePeriodEnd": "2026-09-30T23:59:59Z",
            "BillingAccountId": "111122223333",
            "SubAccountId": "111122223333",
            "ProviderName": "AWS",
            "RegionName": "us-east-1",
            "ServiceName": "Amazon Elastic Block Store",
            "ResourceID": "vol-test01",
            "ResourceType": "Volume",
            "EffectiveCost": 45.00,
            "ListCost": 45.00,
            "BilledCost": 45.00,
            "UsageQuantity": 500.0,
            "UsageUnit": "GB-Mo",
            "PricingQuantity": 500.0,
            "PricingUnit": "GB-Mo",
            "Currency": "USD"
        },
        {
            "ChargePeriodStart": "2026-09-01T00:00:00Z",
            "ChargePeriodEnd": "2026-09-30T23:59:59Z",
            "BillingAccountId": "999988887777",
            "SubAccountId": "999988887777",
            "ProviderName": "GCP",
            "RegionName": "us-central1",
            "ServiceName": "Compute Engine",
            "ResourceID": "gcp-vm-01",
            "ResourceType": "Instance",
            "EffectiveCost": 80.00,
            "ListCost": 80.00,
            "BilledCost": 80.00,
            "UsageQuantity": 730.0,
            "UsageUnit": "Hours",
            "PricingQuantity": 730.0,
            "PricingUnit": "Hours",
            "Currency": "USD"
        }
    ]


def test_focus_lakehouse_load_and_query(sample_focus_records):
    lakehouse = FOCUSLakehouse()
    lakehouse.load_focus_records(sample_focus_records)

    result = lakehouse.execute_query("SELECT COUNT(*) as total_records FROM focus_costs")
    assert result["row_count"] == 1
    assert result["rows"][0]["total_records"] == 3
    assert result["execution_time_ms"] >= 0


def test_focus_lakehouse_presets(sample_focus_records):
    lakehouse = FOCUSLakehouse()
    lakehouse.load_focus_records(sample_focus_records)

    # Spend by service
    by_service = lakehouse.get_spend_by_service()
    assert len(by_service) == 3
    assert by_service[0]["ServiceName"] == "Amazon Elastic Compute Cloud - Compute"
    assert by_service[0]["TotalEffectiveCost"] == 120.50

    # Spend by account
    by_account = lakehouse.get_spend_by_account()
    assert len(by_account) == 2
    # 111122223333 has 120.50 + 45.00 = 165.50
    assert by_account[0]["BillingAccountId"] == "111122223333"
    assert by_account[0]["TotalSpend"] == 165.50

    # Top cost drivers
    top_drivers = lakehouse.get_top_cost_drivers(limit=2)
    assert len(top_drivers) == 2
    assert top_drivers[0]["ResourceID"] == "i-test01"
    assert top_drivers[0]["MonthlySpend"] == 120.50


def test_focus_lakehouse_read_only_enforcement():
    lakehouse = FOCUSLakehouse()
    with pytest.raises(ValueError, match="Only SELECT or WITH queries are permitted"):
        lakehouse.execute_query("DROP TABLE focus_costs")

    with pytest.raises(ValueError, match="Only SELECT or WITH queries are permitted"):
        lakehouse.execute_query("DELETE FROM focus_costs")

    with pytest.raises(ValueError, match="Only SELECT or WITH queries are permitted"):
        lakehouse.execute_query("INSERT INTO focus_costs (ServiceName) VALUES ('hacked')")


def test_api_focus_query_endpoint():
    from main import _db
    _db()["nodes"] = [{"instance_id": "i-test1", "cost": 25.0, "state": "running", "type": "t3.micro"}]
    client = TestClient(app)
    payload = {
        "query": "SELECT ServiceName, SUM(EffectiveCost) as Total FROM focus_costs GROUP BY ServiceName"
    }
    response = client.post("/api/v2/focus/query", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "result" in data
    assert "rows" in data["result"]
    assert len(data["result"]["rows"]) > 0


def test_api_focus_query_invalid_sql():
    client = TestClient(app)
    response = client.post("/api/v2/focus/query", json={"query": "DELETE FROM focus_costs"})
    assert response.status_code == 400


def test_api_focus_analytics_endpoint():
    from main import _db
    _db()["nodes"] = [{"instance_id": "i-test1", "cost": 25.0, "state": "running", "type": "t3.micro"}]
    client = TestClient(app)
    response = client.get("/api/v2/focus/analytics")
    assert response.status_code == 200
    data = response.json()
    assert "status" == "status" in data or data.get("status") == "success"
    assert "spend_by_service" in data
    assert "spend_by_account" in data
    assert "top_cost_drivers" in data
    assert len(data["spend_by_service"]) > 0


def test_focus_lakehouse_parquet_ingestion(tmp_path):
    import duckdb
    parquet_path = tmp_path / "focus_sample.parquet"
    conn = duckdb.connect(":memory:")
    conn.execute('''
        CREATE TABLE sample AS SELECT 
            '2026-09-01' as ChargePeriodStart,
            '2026-09-30' as ChargePeriodEnd,
            '333344445555' as BillingAccountId,
            '333344445555' as SubAccountId,
            'AWS' as ProviderName,
            'us-east-1' as RegionName,
            'Amazon DynamoDB' as ServiceName,
            'table-orders' as ResourceID,
            'Database' as ResourceType,
            75.25 as EffectiveCost,
            75.25 as ListCost,
            75.25 as BilledCost,
            100.0 as UsageQuantity,
            'GB-Mo' as UsageUnit,
            100.0 as PricingQuantity,
            'GB-Mo' as PricingUnit,
            'USD' as Currency
    ''')
    conn.execute(f"COPY sample TO '{parquet_path}' (FORMAT PARQUET)")

    lakehouse = FOCUSLakehouse()
    loaded_count = lakehouse.load_parquet(parquet_path)
    assert loaded_count == 1

    res = lakehouse.execute_query("SELECT ServiceName, EffectiveCost FROM focus_costs")
    assert res["row_count"] == 1
    assert res["rows"][0]["ServiceName"] == "Amazon DynamoDB"
    assert res["rows"][0]["EffectiveCost"] == 75.25

