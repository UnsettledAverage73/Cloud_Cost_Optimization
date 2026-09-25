# ==============================================================================
# CloudPulse CLI Universal Installer for Windows PowerShell
# Automatically checks Python, creates standalone runner, and configures PATH
# ==============================================================================

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "   ____ _                 _ ____        _           " -ForegroundColor Cyan
Write-Host "  / ___| | ___  _   _  __| |  _ \ _   _| |___  ___  " -ForegroundColor Cyan
Write-Host " | |   | |/ _ \| | | |/ _` | |_) | | | | / __|/ _ \ " -ForegroundColor Cyan
Write-Host " | |___| | (_) | |_| | (_| |  __/| |_| | \__ \  __/ " -ForegroundColor Cyan
Write-Host "  \____|_|\___/ \__,_|\__,_|_|    \__,_|_|___/\___| " -ForegroundColor Cyan
Write-Host "    Enterprise Cloud Cost Optimization CLI Installer" -ForegroundColor Cyan
Write-Host ""

# 1. Detect System
Write-Host "Detecting Windows environment..." -ForegroundColor White
$is64Bit = [Environment]::Is64BitOperatingSystem
Write-Host "   • OS Architecture : $(if ($is64Bit) { '64-bit' } else { '32-bit' })" -ForegroundColor Gray

# 2. Check Python
Write-Host ""
Write-Host "Checking Python runtime..." -ForegroundColor White
$pythonCmd = $null
foreach ($cmd in @("python", "py", "python3")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($LASTEXITCODE -eq 0 -and $ver -match "Python 3") {
            $pythonCmd = $cmd
            Write-Host "   • Found Python     : $ver ($cmd)" -ForegroundColor Gray
            break
        }
    } catch {}
}

if (-not $pythonCmd) {
    Write-Host "Error: Python 3.8 or higher is required." -ForegroundColor Red
    Write-Host "Install it via winget: winget install Python.Python.3.12" -ForegroundColor Yellow
    Exit 1
}

# 3. Setup Install Directory
$installRoot = Join-Path $env:USERPROFILE ".cloudpulse"
$binDir = Join-Path $installRoot "bin"
$cliDir = Join-Path $installRoot "cli"

if (-not (Test-Path $binDir)) { New-Item -ItemType Directory -Path $binDir -Force | Out-Null }
if (-not (Test-Path $cliDir)) { New-Item -ItemType Directory -Path $cliDir -Force | Out-Null }

$repoUrl = "https://github.com/UnsettledAverage73/Cloud_Cost_Optimization.git"
$defaultBackend = "https://cloud-cost-optimization.onrender.com"

# 4. Download / Install CLI Runner
Write-Host ""
Write-Host "Installing CloudPulse CLI..." -ForegroundColor White

$rawCliUrl = "https://raw.githubusercontent.com/UnsettledAverage73/Cloud_Cost_Optimization/master/backend/cli_main.py"
$targetScript = Join-Path $cliDir "cli_main.py"

try {
    Invoke-WebRequest -Uri $rawCliUrl -OutFile $targetScript -UseBasicParsing
    Write-Host "   • Downloaded core CLI runtime" -ForegroundColor Gray
} catch {
    Write-Host "   • Fallback: Using pip install git repository..." -ForegroundColor Gray
    & $pythonCmd -m pip install "git+$repoUrl" -q
}

# 5. Create Batch & PowerShell Launchers
$batPath = Join-Path $binDir "cloudpulse.cmd"
"@echo off`r`n`"$pythonCmd`" `"$targetScript`" %*" | Out-File -FilePath $batPath -Encoding ascii

$ps1Path = Join-Path $binDir "cloudpulse.ps1"
"& `"$pythonCmd`" `"$targetScript`" `$args" | Out-File -FilePath $ps1Path -Encoding utf8

# 6. Initialize Config
$configFile = Join-Path $installRoot "config.json"
if (-not (Test-Path $configFile)) {
    @{
        backend_url = $defaultBackend
        currency = "USD"
        installed_at = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    } | ConvertTo-Json | Out-File -FilePath $configFile -Encoding utf8
}

# 7. Add to User PATH
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$binDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$binDir", "User")
    $env:Path = "$env:Path;$binDir"
    Write-Host "   • Added $binDir to user PATH" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================================================" -ForegroundColor Green
Write-Host "🎉 CloudPulse CLI installed successfully!" -ForegroundColor Green
Write-Host "========================================================================" -ForegroundColor Green
Write-Host "Executable location : $batPath" -ForegroundColor Cyan
Write-Host "Default backend     : $defaultBackend" -ForegroundColor Cyan
Write-Host ""
Write-Host "Try running these commands in a new terminal:" -ForegroundColor White
Write-Host "   cloudpulse status" -ForegroundColor Cyan
Write-Host "   cloudpulse audit" -ForegroundColor Cyan
Write-Host "   cloudpulse inspect" -ForegroundColor Cyan
Write-Host "   cloudpulse ask `"What are my highest cost drivers?`"" -ForegroundColor Cyan
Write-Host "   cloudpulse pov --format html --open" -ForegroundColor Cyan
Write-Host ""
