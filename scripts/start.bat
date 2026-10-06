@echo off
REM SceneForge Studio - start script. Launches the FastAPI backend, which
REM also serves the built frontend (frontend\dist) from the same origin
REM at http://127.0.0.1:8000. Binds loopback only.
setlocal

cd /d "%~dp0..\backend"
if not exist "..\frontend\dist\index.html" goto :warn_no_dist
goto :run

:warn_no_dist
echo [WARN] frontend\dist not found - the app UI will not be served.
echo        Run scripts\setup.bat first, or "npm run build" in frontend\.
goto :run

:run
echo Starting SceneForge Studio at http://127.0.0.1:8000 ...
echo Press Ctrl+C to stop.
python "%~dp0windows_runtime.py" start
set "SF_START_EXIT=%errorlevel%"
if not "%SF_START_EXIT%"=="0" pause
exit /b %SF_START_EXIT%
