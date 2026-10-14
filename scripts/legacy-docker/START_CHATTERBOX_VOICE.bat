@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\local-voice.ps1" -Engine chatterbox
pause
