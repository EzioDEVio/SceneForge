@echo off
cd /d "%~dp0"
echo === Docker engine ===
docker info --format "{{.ServerVersion}}"
echo === Voice containers ===
docker compose -f services\compose.yaml ps -a
echo === Chatterbox logs ===
docker compose -f services\compose.yaml logs --tail 100 chatterbox
echo === FFmpeg version ===
ffmpeg -version
echo Copy this window's output if voice or rendering still fails.
pause
