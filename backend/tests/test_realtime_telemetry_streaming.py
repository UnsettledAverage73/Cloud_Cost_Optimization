import pytest
from fastapi.testclient import TestClient
from main import app
from services.telemetry_streamer import telemetry_hub


def test_telemetry_hub_ring_buffer():
    """Verify that TelemetryHub maintains a ring buffer with maxlen=120 and seeds points."""
    instance_id = "i-unit-test-ring-01"
    telemetry_hub._seed_buffer_if_empty(instance_id)

    assert len(telemetry_hub.buffers[instance_id]) > 0
    assert len(telemetry_hub.buffers[instance_id]) <= 120

    # Add 150 ticks
    for i in range(150):
        tick = {
            "timestamp": "12:00:00",
            "cpu": 10.0 + (i % 50),
            "mem": 40.0,
            "disk": 30.0,
            "net_in_bytes": 1024,
            "net_out_bytes": 512,
            "packets_in": 10,
            "packets_out": 5,
            "cpu_credits": 140.0,
        }
        telemetry_hub.buffers[instance_id].append(tick)

    # Deque must strictly enforce maxlen=120
    assert len(telemetry_hub.buffers[instance_id]) == 120


def test_websocket_telemetry_streaming():
    """Verify live WebSocket endpoint connects, sends HISTORY, and streams metrics."""
    client = TestClient(app)
    instance_id = "i-unit-test-stream-02"

    with client.websocket_connect(f"/ws/telemetry/{instance_id}") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "HISTORY"
        assert msg["instance_id"] == instance_id
        assert isinstance(msg["datapoints"], list)
        assert len(msg["datapoints"]) > 0

        # Verify datapoint payload structure matches CP-ENG-SPEC-2026-04
        latest = msg["datapoints"][-1]
        assert "cpu" in latest
        assert "mem" in latest
        assert "disk" in latest
        assert "net_in_bytes" in latest
        assert "net_out_bytes" in latest
        assert "packets_in" in latest
        assert "packets_out" in latest
        assert "cpu_credits" in latest


def test_live_telemetry_rest_fallback():
    """Verify REST endpoint returns live ring buffer points for fallback polling."""
    client = TestClient(app)
    instance_id = "i-unit-test-rest-03"

    res = client.get(f"/api/v2/telemetry/{instance_id}/live")
    assert res.status_code == 200
    data = res.json()
    assert data["instance_id"] == instance_id
    assert "datapoints" in data
    assert len(data["datapoints"]) > 0
