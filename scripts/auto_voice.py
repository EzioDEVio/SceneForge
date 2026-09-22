"""Start installed local voice containers without installing models or rebuilding images."""
from pathlib import Path
import os
import shutil
import subprocess
import time


def command(args, timeout=8):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                          creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def main():
    docker = shutil.which('docker')
    if not docker:
        print('Voice: Docker is not installed. The editor will start without local speech.'); return
    try:
        ready = command([docker, 'info', '--format', '{{.ServerVersion}}']).returncode == 0
        if not ready and os.name == 'nt':
            desktop = Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'Docker/Docker/Docker Desktop.exe'
            if desktop.exists():
                print('Voice: starting Docker Desktop...')
                subprocess.Popen([str(desktop)])
                for _ in range(15):
                    time.sleep(2)
                    try:
                        if command([docker, 'info', '--format', '{{.ServerVersion}}'], timeout=3).returncode == 0:
                            ready = True; break
                    except subprocess.TimeoutExpired:
                        continue
        if not ready:
            print('Voice: Docker is not ready. Start Docker Desktop, then run START_CHATTERBOX_VOICE.bat.'); return
        compose = str(Path(__file__).resolve().parents[1] / 'services/compose.yaml')
        for engine in ('chatterbox', 'kokoro'):
            result = command([docker, 'compose', '-f', compose, 'ps', '-a', '-q', engine])
            ids = result.stdout.split() if result.returncode == 0 else []
            if not ids:
                print(f'Voice: {engine} is not installed for this Compose project; use its START launcher once.'); continue
            for container_id in ids:
                result = command([docker, 'start', container_id], timeout=15)
                print(f'Voice: {engine} container started.' if result.returncode == 0 else f'Voice: {engine} startup failed. Run DIAGNOSE_VOICE.bat.')
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f'Voice auto-start could not finish ({type(exc).__name__}). The editor remains available.')


if __name__ == '__main__':
    main()
