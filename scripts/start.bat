@echo off
REM SceneForge Studio - start script. Launches the FastAPI backend, which
REM also serves the built frontend (frontend\dist) from the same origin
REM at http://127.0.0.1:8000. Binds loopback only.
setlocal

cd /d "%~dp0..\backend"
if not exist ".venv\Scripts\activate.bat" goto :no_venv
call .venv\Scripts\activate.bat

if not exist "..\frontend\dist\index.html" goto :warn_no_dist
goto :run

:warn_no_dist
echo [WARN] frontend\dist not found - the app UI will not be served.
echo        Run scripts\setup.bat first, or "npm run build" in frontend\.
goto :run

:run
REM Background startup never blocks the editor; only existing containers are started.
start "SceneForge voice startup" /b python "%~dp0auto_voice.py"
echo Starting SceneForge Studio at http://127.0.0.1:8000 ...
echo Press Ctrl+C to stop.
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
exit /b 0

:no_venv
echo [ERROR] Backend virtual environment not found. Run scripts\setup.bat first.
pause
exit /b 1
