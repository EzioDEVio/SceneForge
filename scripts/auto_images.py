"""Start an existing Windows AUTOMATIC1111 installation without a second terminal.
SCENEFORGE_SD_DIR overrides ~/stable-diffusion-webui; SCENEFORGE_SD_AUTOSTART=0 disables.
Never installs or edits the user's WebUI environment.
"""
import os
from pathlib import Path
import socket
import subprocess
import time
import urllib.request


def ready():
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open('http://127.0.0.1:7860/sdapi/v1/options', timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def main():
    if os.name != 'nt' or os.environ.get('SCENEFORGE_SD_AUTOSTART') == '0':
        return
    root = Path(os.environ.get('SCENEFORGE_SD_DIR', str(Path.home() / 'stable-diffusion-webui')))
    script = root / 'webui-user.bat'
    if not script.is_file() or ready():
        return
    # Do not start another process when the port is already occupied/loading.
    try:
        with socket.create_connection(('127.0.0.1', 7860), timeout=1):
            print('[Images] Port 7860 already occupied. Waiting for API readiness.', flush=True)
            return
    except OSError:
        pass
    logs = Path(__file__).resolve().parents[1] / 'backend' / 'data' / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    try:
        with (logs / 'stable-diffusion.log').open('a', encoding='utf-8') as log:
            # Fixed command; cwd holds the user-selected installation. Existing batch
            # preserves Python, xformers, medvram and dependency constraints.
            process = subprocess.Popen(['cmd.exe', '/d', '/c', 'webui-user.bat'], cwd=str(root),
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW)
        print('[Images] Starting Stable Diffusion in background.', flush=True)
        for _ in range(120):
            if ready():
                print('[Images] Stable Diffusion API ready on port 7860.', flush=True)
                return
            if process.poll() is not None:
                break
            time.sleep(2)
        print('[Images] API not ready. See backend/data/logs/stable-diffusion.log; ensure --api is enabled.', flush=True)
    except OSError as exc:
        print(f'[Images] Could not launch local images: {exc}', flush=True)


if __name__ == '__main__':
    main()
