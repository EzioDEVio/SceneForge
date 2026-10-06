@echo off
REM SceneForge Studio - developer mode: runs the backend API (port 8000)
REM and the Vite frontend dev server (port 5173, with hot reload) side by
REM side. Use this while working on the frontend; use start.bat for the
REM normal "just run the app" experience.
setlocal

cd /d "%~dp0..\backend"
start "SceneForge backend" cmd /k python "%~dp0windows_runtime.py" dev
start "SceneForge frontend (dev)" cmd /k "cd /d %~dp0..\frontend && npm run dev"

echo Backend:  http://127.0.0.1:8000
echo Frontend: http://127.0.0.1:5173  (proxies /api to the backend)
exit /b 0
