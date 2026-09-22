# SceneForge Studio - Windows setup script (PowerShell)
# Equivalent to setup.bat, for users who prefer PowerShell. Run with:
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

function Test-Command($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

Write-Host "============================================"
Write-Host " SceneForge Studio - Setup"
Write-Host "============================================"

if (-not (Test-Command "python")) {
    Write-Host "[ERROR] Python was not found on PATH. Install Python 3.11+ from https://www.python.org/downloads/" -ForegroundColor Red
    Write-Host "        and check 'Add python.exe to PATH' during install." -ForegroundColor Red
    exit 1
}
if (-not (Test-Command "node")) {
    Write-Host "[ERROR] Node.js was not found on PATH. Install Node 18+ LTS from https://nodejs.org/" -ForegroundColor Red
    exit 1
}
if (-not (Test-Command "ffmpeg") -or -not (Test-Command "ffprobe")) {
    Write-Host "[ERROR] ffmpeg/ffprobe were not found on PATH." -ForegroundColor Red
    Write-Host "        Download a build from https://www.gyan.dev/ffmpeg/builds/, extract it," -ForegroundColor Red
    Write-Host "        and add its bin\ folder to PATH." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] python, node, ffmpeg, ffprobe all found on PATH."

Write-Host "`nSetting up backend (Python virtual environment)..."
Set-Location "$root\backend"
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
& ".venv\Scripts\Activate.ps1"
python -m pip install --upgrade pip
pip install -r requirements.txt
Write-Host "[OK] Backend dependencies installed."

Write-Host "`nSetting up frontend (npm)..."
Set-Location "$root\frontend"
npm install
npm run build
Write-Host "[OK] Frontend built to frontend\dist."

Write-Host "`n============================================"
Write-Host " Setup complete. Run scripts\start.ps1 (or start.bat) to launch SceneForge Studio."
Write-Host "============================================"
