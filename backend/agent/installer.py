def generate_linux_install_script(backend_url: str, token: str, interval: int = 60) -> str:
    """Generates an enterprise-ready POSIX/Linux bash installation script."""
    return f"""#!/usr/bin/env bash
set -e

echo "🚀 Installing CloudPulse Multi-OS In-Guest Telemetry Agent..."
INSTALL_DIR="/opt/cloudpulse-agent"
BACKEND_URL="{backend_url}"
AGENT_TOKEN="{token}"
INTERVAL="{interval}"

# 1. Create installation directory
sudo mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# 2. Check Python 3
if ! command -v python3 &>/dev/null; then
    echo "Python 3 is required. Please install python3 and curl."
    exit 1
fi

# 3. Create standalone agent script
sudo cat << 'EOF' > "$INSTALL_DIR/agent.py"
# Embedded CloudPulse Standalone Agent
import sys, os, urllib.request, json, time, shutil, socket, platform
from datetime import datetime, timezone

def collect():
    usage = shutil.disk_usage("/")
    mem_used = 0
    mem_total = 1024
    if os.path.exists("/proc/meminfo"):
        m = {{}}
        for line in open("/proc/meminfo"):
            p = line.split(":")
            if len(p) == 2: m[p[0].strip()] = int(p[1].split()[0])
        mem_total = m.get("MemTotal", 1024)
        mem_used = mem_total - m.get("MemAvailable", m.get("MemFree", 0))

    cores = os.cpu_count() or 1
    load = os.getloadavg()[0] if hasattr(os, "getloadavg") else 0.0
    cpu_pct = min(round((load / cores) * 100, 2), 100.0)

    host = socket.gethostname()
    return {{
        "token": "{token}",
        "cloud": {{"provider": "linux-host", "instance_id": f"host-{{host}}", "region": "local"}},
        "telemetry": {{
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "os": {{"os_type": "linux", "hostname": host, "architecture": platform.machine()}},
            "cpu": {{"utilization_percent": cpu_pct, "logical_cores": cores}},
            "memory": {{"total_mb": round(mem_total/1024, 1), "percent_used": round((mem_used/mem_total)*100, 2)}},
            "disk": {{"total_gb": round(usage.total/(1024**3), 2), "percent_used": round((usage.used/usage.total)*100, 2)}}
        }}
    }}

def main():
    while True:
        try:
            payload = collect()
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request("{backend_url}/api/v2/agent/ingest", data=data, headers={{"Content-Type": "application/json"}})
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass
        time.sleep({interval})

if __name__ == "__main__":
    main()
EOF

# 4. Configure systemd service if available
if command -v systemctl &>/dev/null && [ -d /etc/systemd/system ]; then
    echo "Creating systemd service 'cloudpulse-agent'..."
    sudo cat << EOF > /etc/systemd/system/cloudpulse-agent.service
[Unit]
Description=CloudPulse Multi-OS Telemetry Daemon
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=$(which python3) $INSTALL_DIR/agent.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    sudo systemctl daemon-reload
    sudo systemctl enable cloudpulse-agent
    sudo systemctl restart cloudpulse-agent
    echo "✅ CloudPulse Agent installed and running via systemd!"
else
    echo "Starting agent in background..."
    nohup python3 "$INSTALL_DIR/agent.py" > /dev/null 2>&1 &
    echo "✅ CloudPulse Agent running in background (PID: $!)"
fi
"""

def generate_windows_install_script(backend_url: str, token: str, interval: int = 60) -> str:
    """Generates a PowerShell installation script for Windows Server / Windows 10/11."""
    return f"""# CloudPulse Multi-OS Windows Agent Installer
$ErrorActionPreference = "Stop"
Write-Host "🚀 Installing CloudPulse Multi-OS Telemetry Agent for Windows..." -ForegroundColor Cyan

$InstallDir = "C:\\Program Files\\CloudPulse"
$BackendUrl = "{backend_url}/api/v2/agent/ingest"
$Token = "{token}"
$Interval = {interval}

if (!(Test-Path $InstallDir)) {{
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
}}

$ScriptContent = @"
`$ErrorActionPreference = 'SilentlyContinue'
while (`$true) {{
    `$os = Get-CimInstance Win32_OperatingSystem
    `$totalRam = [math]::Round(`$os.TotalVisibleMemorySize / 1024, 1)
    `$freeRam = [math]::Round(`$os.FreePhysicalMemory / 1024, 1)
    `$usedRamPct = [math]::Round(((`$totalRam - `$freeRam) / `$totalRam) * 100, 2)
    `$cpu = (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
    `$disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
    `$diskPct = [math]::Round(((`$disk.Size - `$disk.FreeSpace) / `$disk.Size) * 100, 2)

    `$payload = @{{
        token = "$Token"
        cloud = @{{
            provider = "windows-host"
            instance_id = "win-" + `$env:COMPUTERNAME
            region = "local"
        }}
        telemetry = @{{
            timestamp = (Get-Date).ToUniversalTime().ToString("o")
            os = @{{
                os_type = "windows"
                hostname = `$env:COMPUTERNAME
                architecture = `$env:PROCESSOR_ARCHITECTURE
            }}
            cpu = @{{
                utilization_percent = `$cpu
                logical_cores = [Environment]::ProcessorCount
            }}
            memory = @{{
                total_mb = `$totalRam
                percent_used = `$usedRamPct
            }}
            disk = @{{
                total_gb = [math]::Round(`$disk.Size / 1GB, 2)
                percent_used = `$diskPct
            }}
        }}
    }} | ConvertTo-Json -Depth 5

    try {{
        Invoke-RestMethod -Uri "$BackendUrl" -Method Post -Body `$payload -ContentType "application/json" -TimeoutSec 5
    }} catch {{}}
    Start-Sleep -Seconds $Interval
}}
"@

Set-Content -Path "$InstallDir\\agent.ps1" -Value $ScriptContent -Force
Write-Host "Registering CloudPulse Scheduled Task..." -ForegroundColor Green
$Action = New-ScheduledTaskAction -Execute 'PowerShell.exe' -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$InstallDir\\agent.ps1`""
$Trigger = New-ScheduledTaskTrigger -AtStartup
$Principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName "CloudPulseAgent" -Action $Action -Trigger $Trigger -Principal $Principal -Force | Out-Null
Start-ScheduledTask -TaskName "CloudPulseAgent"
Write-Host "✅ CloudPulse Windows Agent installed and running!" -ForegroundColor Green
"""
