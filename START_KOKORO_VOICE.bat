@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\local-voice.ps1" -Engine kokoro
pause
