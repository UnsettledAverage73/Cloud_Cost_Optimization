import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_install_sh_endpoint():
    response = client.get("/install.sh")
    assert response.status_code == 200
    assert "CloudPulse CLI Universal Installer" in response.text
    assert "cloudpulse" in response.text

def test_install_ps1_endpoint():
    response = client.get("/install.ps1")
    assert response.status_code == 200
    assert "CloudPulse CLI Universal Installer for Windows PowerShell" in response.text
    assert "cloudpulse" in response.text

def test_cli_install_command_linux():
    response = client.get("/api/v2/cli/install-command", headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"})
    assert response.status_code == 200
    data = response.json()
    assert data["detected_os"] == "linux"
    assert "curl -fsSL" in data["command"]
    assert "/install.sh | bash" in data["command"]
    assert data["verify_command"] == "cloudpulse status"

def test_cli_install_command_macos():
    response = client.get("/api/v2/cli/install-command", headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})
    assert response.status_code == 200
    data = response.json()
    assert data["detected_os"] == "macos"
    assert "curl -fsSL" in data["command"]
    assert "/install.sh | bash" in data["command"]

def test_cli_install_command_windows():
    response = client.get("/api/v2/cli/install-command", headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    assert response.status_code == 200
    data = response.json()
    assert data["detected_os"] == "windows"
    assert "irm " in data["command"]
    assert "/install.ps1 | iex" in data["command"]
