@echo off
REM SceneForge Studio - Windows setup script
REM Installs backend (Python venv) and frontend (npm) dependencies, then
REM builds the production frontend bundle that the backend serves.
setlocal enabledelayedexpansion

echo ============================================
echo  SceneForge Studio - Setup
echo ============================================

where python >nul 2>nul
if errorlevel 1 goto :no_python

where node >nul 2>nul
if errorlevel 1 goto :no_node

where ffmpeg >nul 2>nul
if errorlevel 1 goto :no_ffmpeg

where ffprobe >nul 2>nul
if errorlevel 1 goto :no_ffprobe

echo [OK] python, node, ffmpeg, ffprobe all found on PATH.
echo.

echo Setting up backend (Python virtual environment)...
cd /d "%~dp0..\backend"
if not exist ".venv" python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 goto :pip_failed
echo [OK] Backend dependencies installed.
echo.

echo Setting up frontend (npm)...
cd /d "%~dp0..\frontend"
call npm install
if errorlevel 1 goto :npm_install_failed
call npm run build
if errorlevel 1 goto :npm_build_failed
echo [OK] Frontend built to frontend\dist.
echo.

echo ============================================
echo  Setup complete. Run scripts\start.bat to launch SceneForge Studio.
echo ============================================
pause
exit /b 0

:no_python
echo [ERROR] Python was not found on PATH. Install Python 3.11+ from
echo         https://www.python.org/downloads/ and re-run this script.
echo         IMPORTANT: check "Add python.exe to PATH" during install.
pause
exit /b 1

:no_node
echo [ERROR] Node.js was not found on PATH. Install Node 18+ LTS from
echo         https://nodejs.org/ and re-run this script.
pause
exit /b 1

:no_ffmpeg
echo [ERROR] ffmpeg was not found on PATH.
echo         Download a Windows build from https://www.gyan.dev/ffmpeg/builds/
echo         and add its bin folder to your PATH. Then re-run this script.
pause
exit /b 1

:no_ffprobe
echo [ERROR] ffprobe was not found on PATH ^(it ships alongside ffmpeg -
echo         check the same bin folder is on PATH^).
pause
exit /b 1

:pip_failed
echo [ERROR] Backend dependency install failed. See the error above.
pause
exit /b 1

:npm_install_failed
echo [ERROR] npm install failed. See the error above.
pause
exit /b 1

:npm_build_failed
echo [ERROR] Frontend build failed. See the error above.
pause
exit /b 1
