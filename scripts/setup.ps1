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
    Write-Host "[ERROR] Python was not found on PATH. Install Python 3.12 from https://www.python.org/downloads/" -ForegroundColor Red
    Write-Host "        and check 'Add python.exe to PATH' during install." -ForegroundColor Red
    exit 1
}
if (-not (Test-Command "node")) {
    Write-Host "[ERROR] Node.js was not found on PATH. Install Node 22.12+ LTS from https://nodejs.org/" -ForegroundColor Red
    exit 1
}
$localFfmpeg = Join-Path $PSScriptRoot "..\tools\ffmpeg"
if ((-not (Test-Command "ffmpeg") -or -not (Test-Command "ffprobe")) -and -not (Test-Path (Join-Path $localFfmpeg "bin\ffmpeg.exe"))) {
    Write-Host "FFmpeg was not found. Downloading a verified copy into tools\ffmpeg (about 100 MB)..."
    & python "$PSScriptRoot\..\desktop\scripts\fetch_ffmpeg.py" --target $localFfmpeg
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] FFmpeg could not be downloaded. Check the internet connection and run setup again." -ForegroundColor Red
        exit 1
    }
}
Write-Host "[OK] python, node and FFmpeg are ready."

Write-Host "`nSetting up backend (Python virtual environment)..."
& python "$PSScriptRoot\windows_runtime.py" setup
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "[OK] Backend dependencies installed."

Write-Host "`nSetting up frontend (npm)..."
Set-Location "$root\frontend"
npm install
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
npm run build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "[OK] Frontend built to frontend\dist."

Write-Host "`n============================================"
Write-Host " Setup complete. Run scripts\start.ps1 (or start.bat) to launch SceneForge Studio."
Write-Host "============================================"
