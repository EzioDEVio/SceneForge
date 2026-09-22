# SceneForge Studio - start script (PowerShell)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

$listener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    Write-Host "Port 8000 is already in use by PID $($listener.OwningProcess -join ', '). Stop the previous SceneForge server with Ctrl+C before restarting." -ForegroundColor Red
    exit 1
}
Write-Host "Backend folder: $root\backend"
Set-Location "$root\backend"
if (-not (Test-Path ".venv\Scripts\Activate.ps1")) {
    Write-Host "[ERROR] Backend virtual environment not found. Run scripts\setup.ps1 first." -ForegroundColor Red
    exit 1
}
& ".venv\Scripts\Activate.ps1"

if (-not (Test-Path "$root\frontend\dist\index.html")) {
    Write-Host "[WARN] frontend\dist not found - the app UI will not be served." -ForegroundColor Yellow
    Write-Host "       Run scripts\setup.ps1 (or 'npm run build' in frontend\) first." -ForegroundColor Yellow
}

Write-Host "Starting SceneForge Studio at http://127.0.0.1:8000 ..."
Write-Host "Press Ctrl+C to stop."
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
