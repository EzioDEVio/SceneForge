@echo off
REM SceneForge Studio - developer mode: runs the backend API (port 8000)
REM and the Vite frontend dev server (port 5173, with hot reload) side by
REM side. Use this while working on the frontend; use start.bat for the
REM normal "just run the app" experience.
setlocal

cd /d "%~dp0..\backend"
if not exist ".venv\Scripts\activate.bat" goto :no_venv

start "SceneForge backend" cmd /k "call .venv\Scripts\activate.bat && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
start "SceneForge frontend (dev)" cmd /k "cd /d %~dp0..\frontend && npm run dev"

echo Backend:  http://127.0.0.1:8000
echo Frontend: http://127.0.0.1:5173  (proxies /api to the backend)
exit /b 0

:no_venv
echo [ERROR] Backend virtual environment not found. Run scripts\setup.bat first.
pause
exit /b 1
