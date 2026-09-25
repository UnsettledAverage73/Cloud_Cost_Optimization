def generate_linux_install_script(backend_url: str, token: str, interval: int = 2) -> str:
    """Generates an enterprise-ready POSIX/Linux bash installation script with IMDSv2 auto-detection."""
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

# 3. Create standalone agent script with IMDSv2 auto-detection
sudo cat << 'EOF' > "$INSTALL_DIR/agent.py"
# Embedded CloudPulse Standalone High-Speed In-Guest Agent
import sys, os, urllib.request, json, time, shutil, socket, platform
from datetime import datetime, timezone

def get_cloud_metadata():
    host = socket.gethostname()
    cloud = {{"provider": "linux-host", "instance_id": f"host-{{host}}", "region": "local", "availability_zone": "local"}}
    try:
        token_req = urllib.request.Request(
            "http://169.254.169.254/latest/api/token",
            headers={{"X-aws-ec2-metadata-token-ttl-seconds": "60"}},
            method="PUT"
        )
        with urllib.request.urlopen(token_req, timeout=0.8) as r:
            imds_tok = r.read().decode().strip()
        auth_h = {{"X-aws-ec2-metadata-token": imds_tok}}
        
        id_req = urllib.request.Request("http://169.254.169.254/latest/meta-data/instance-id", headers=auth_h)
        with urllib.request.urlopen(id_req, timeout=0.8) as r:
            inst_id = r.read().decode().strip()
            
        az_req = urllib.request.Request("http://169.254.169.254/latest/meta-data/placement/availability-zone", headers=auth_h)
        with urllib.request.urlopen(az_req, timeout=0.8) as r:
            az = r.read().decode().strip()
            reg = az[:-1] if az else "us-east-1"
            
        cloud = {{
            "provider": "aws",
            "instance_id": inst_id,
            "region": reg,
            "availability_zone": az
        }}
    except Exception:
        pass
    return cloud

cached_cloud = None
prev_net = None
prev_cpu_time = None

def get_cpu_pct():
    global prev_cpu_time
    try:
        with open("/proc/stat", "r") as f:
            line = f.readline()
        fields = [float(x) for x in line.strip().split()[1:8]]
        idle_time = fields[3] + fields[4]
        total_time = sum(fields)
        if prev_cpu_time is None:
            prev_cpu_time = (idle_time, total_time)
            cores = os.cpu_count() or 1
            load = os.getloadavg()[0] if hasattr(os, "getloadavg") else 0.0
            return min(round((load / cores) * 100, 1), 100.0)
        prev_idle, prev_total = prev_cpu_time
        prev_cpu_time = (idle_time, total_time)
        diff_total = total_time - prev_total
        diff_idle = idle_time - prev_idle
        if diff_total > 0:
            return max(0.0, min(100.0, round(((diff_total - diff_idle) / diff_total) * 100, 1)))
    except Exception:
        pass
    cores = os.cpu_count() or 1
    load = os.getloadavg()[0] if hasattr(os, "getloadavg") else 0.0
    return min(round((load / cores) * 100, 1), 100.0)

def collect():
    global cached_cloud, prev_net
    if cached_cloud is None:
        cached_cloud = get_cloud_metadata()
        
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
    cpu_pct = get_cpu_pct()
    host = socket.gethostname()

    # Network delta
    net_in_b = 0
    net_out_b = 0
    try:
        cur_rx, cur_tx = 0, 0
        if os.path.exists("/proc/net/dev"):
            for line in open("/proc/net/dev"):
                if ":" in line:
                    iface, stats = line.split(":", 1)
                    if "lo" not in iface:
                        cols = stats.split()
                        cur_rx += int(cols[0])
                        cur_tx += int(cols[8])
        if prev_net is not None:
            t_diff = max(time.time() - prev_net[0], 0.1)
            net_in_b = int(max(0, cur_rx - prev_net[1]) / t_diff)
            net_out_b = int(max(0, cur_tx - prev_net[2]) / t_diff)
        prev_net = (time.time(), cur_rx, cur_tx)
    except Exception:
        pass

    return {{
        "token": "{token}",
        "cloud": cached_cloud,
        "telemetry": {{
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "os": {{"os_type": "linux", "hostname": host, "architecture": platform.machine()}},
            "cpu": {{"utilization_percent": cpu_pct, "logical_cores": cores}},
            "memory": {{"total_mb": round(mem_total/1024, 1), "percent_used": round((mem_used/mem_total)*100, 1)}},
            "disk": {{"total_gb": round(usage.total/(1024**3), 2), "percent_used": round((usage.used/usage.total)*100, 1)}},
            "network": {{
                "bytes_recv": net_in_b,
                "bytes_sent": net_out_b,
                "packets_recv": int(net_in_b / 140) if net_in_b else 0,
                "packets_sent": int(net_out_b / 140) if net_out_b else 0
            }}
        }}
    }}

def main():
    while True:
        try:
            payload = collect()
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request("{backend_url}/api/v2/agent/ingest", data=data, headers={{"Content-Type": "application/json"}})
            urllib.request.urlopen(req, timeout=4)
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
Description=CloudPulse Multi-OS In-Guest Telemetry Daemon
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=$(which python3) -u $INSTALL_DIR/agent.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    sudo systemctl daemon-reload
    sudo systemctl enable cloudpulse-agent
    sudo systemctl restart cloudpulse-agent
    echo "✅ CloudPulse Agent installed and streaming live via systemd!"
else
    echo "Starting agent in background..."
    nohup python3 -u "$INSTALL_DIR/agent.py" > /dev/null 2>&1 &
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
