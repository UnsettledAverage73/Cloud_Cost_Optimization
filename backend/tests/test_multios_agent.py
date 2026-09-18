import sys
import os
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from main import app
    from agent.collector import MultiOSCollector
    from agent.cloud_detector import CloudInstanceDetector
    from agent.installer import generate_linux_install_script, generate_windows_install_script
    from database.connection import SyncSessionLocal
    from database.models import ResourceTelemetry, CloudResource
except ImportError:
    from backend.main import app
    from backend.agent.collector import MultiOSCollector
    from backend.agent.cloud_detector import CloudInstanceDetector
    from backend.agent.installer import generate_linux_install_script, generate_windows_install_script
    from backend.database.connection import SyncSessionLocal
    from backend.database.models import ResourceTelemetry, CloudResource

client = TestClient(app)

def test_collector_os_metadata():
    """Verify OS metadata collection returns valid fields."""
    metadata = MultiOSCollector.get_os_metadata()
    assert metadata["os_type"] in ["linux", "windows", "darwin"]
    assert len(metadata["architecture"]) > 0
    assert len(metadata["hostname"]) > 0
    assert len(metadata["system"]) > 0

def test_collector_cpu_metrics():
    """Verify in-guest CPU utilization and cores."""
    cpu = MultiOSCollector.get_cpu_metrics()
    assert "utilization_percent" in cpu
    assert 0.0 <= cpu["utilization_percent"] <= 100.0
    assert cpu["logical_cores"] >= 1

def test_collector_memory_metrics():
    """Verify in-guest RAM metrics (the hypervisor-blind metric)."""
    mem = MultiOSCollector.get_memory_metrics()
    assert mem["total_mb"] > 0
    assert mem["available_mb"] > 0
    assert 0.0 <= mem["percent_used"] <= 100.0

def test_collector_disk_metrics():
    """Verify root partition disk usage."""
    disk = MultiOSCollector.get_disk_metrics()
    assert disk["total_gb"] > 0
    assert 0.0 <= disk["percent_used"] <= 100.0

def test_collector_top_processes():
    """Verify process footprint discovery."""
    procs = MultiOSCollector.get_top_processes(limit=5)
    assert len(procs) > 0
    assert "name" in procs[0]
    assert "cpu_percent" in procs[0]
    assert "memory_percent" in procs[0]

def test_cloud_instance_detector():
    """Verify host environment detection."""
    detected = CloudInstanceDetector.detect()
    assert "provider" in detected
    assert "instance_id" in detected
    assert len(detected["instance_id"]) > 0

def test_installer_script_generators():
    """Verify dynamic script generation for Linux and Windows."""
    linux_sh = generate_linux_install_script(backend_url="http://localhost:8000", token="test-token")
    assert "#!/usr/bin/env bash" in linux_sh
    assert "cloudpulse-agent" in linux_sh
    assert "test-token" in linux_sh

    win_ps1 = generate_windows_install_script(backend_url="http://localhost:8000", token="test-token")
    assert "PowerShell" in win_ps1 or "Get-CimInstance" in win_ps1
    assert "CloudPulseAgent" in win_ps1
    assert "test-token" in win_ps1

def test_agent_ingest_api():
    """Verify end-to-end ingestion of in-guest agent telemetry into TimescaleDB."""
    payload = {
        "token": "test-token-123",
        "cloud": {
            "provider": "aws",
            "instance_id": "i-test-multios-agent",
            "instance_type": "t3.medium",
            "region": "us-east-1"
        },
        "telemetry": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "os": {
                "os_type": "linux",
                "hostname": "prod-app-01",
                "architecture": "x86_64",
                "release": "5.15.0-aws"
            },
            "cpu": {
                "utilization_percent": 18.5,
                "logical_cores": 2
            },
            "memory": {
                "total_mb": 4096.0,
                "percent_used": 62.4
            },
            "disk": {
                "total_gb": 50.0,
                "percent_used": 44.1
            },
            "top_processes": [
                {"pid": 1201, "name": "nginx", "cpu_percent": 3.2, "memory_percent": 8.5}
            ]
        }
    }

    r = client.post("/api/v2/agent/ingest", json=payload)
    assert r.status_code == 200
    res = r.json()
    assert res["status"] == "ingested"
    assert res["resource_id"] == "i-test-multios-agent"
    assert res["metrics_recorded"] == 3

    # Verify hypertable records in database
    session = SyncSessionLocal()
    try:
        mem_rec = session.query(ResourceTelemetry).filter_by(
            resource_id="i-test-multios-agent",
            metric_name="MemoryUtilization"
        ).first()
        assert mem_rec is not None
        assert mem_rec.val_avg == 62.4
    finally:
        session.close()

def test_agent_install_script_endpoint():
    """Verify API serves plain text installer scripts for Linux and Windows."""
    # Linux script
    r_sh = client.get("/api/v2/agent/install-script?os=linux")
    assert r_sh.status_code == 200
    assert "bash" in r_sh.text

    # Windows script
    r_ps1 = client.get("/api/v2/agent/install-script?os=windows")
    assert r_ps1.status_code == 200
    assert "CloudPulse" in r_ps1.text

def test_agent_hosts_endpoint():
    """Verify API lists live hosts monitored by the Multi-OS agent."""
    r = client.get("/api/v2/agent/hosts")
    assert r.status_code == 200
    data = r.json()
    assert "hosts" in data
    assert data["count"] >= 1
    sample = [h for h in data["hosts"] if h["resource_id"] == "i-test-multios-agent"]
    assert len(sample) == 1
    assert sample[0]["service"] == "host-agent"
