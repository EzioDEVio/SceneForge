"""Source-checkpoint launcher: isolated short-path Windows venv and real font preflight."""
from __future__ import annotations
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def runtime_dir(root=ROOT, local_app_data=None):
    base = Path(local_app_data or os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local'))
    # Copies keep their dependency versions independent; no global shared venv.
    ident = hashlib.sha256(str(root.resolve()).casefold().encode()).hexdigest()[:12]
    return base / 'SceneForge' / 'runtimes' / ident


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['setup', 'start', 'dev'])
    args = parser.parse_args()
    if os.name != 'nt':
        parser.error('This launcher is for Windows source checkpoints.')
    target = runtime_dir()
    python = target / 'Scripts/python.exe'
    try:
        if args.action == 'setup':
            if not python.is_file():
                subprocess.run([sys.executable, '-m', 'venv', str(target)], check=True)
            subprocess.run([str(python), '-m', 'pip', 'install', '--upgrade', 'pip'], check=True)
            subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(ROOT / 'backend/requirements.txt')], check=True)
        elif not python.is_file():
            print('[ERROR] Run scripts/setup.bat or scripts/setup.ps1 first.', file=sys.stderr)
            return 1
        subprocess.run([str(python), '-c', 'from app.render.font_runtime import check_font_runtime; check_font_runtime(); print("[OK] Latin and Arabic font rendering")'], cwd=ROOT / 'backend', check=True)
        if args.action == 'setup':
            print('[OK] Backend runtime ready. Project data has not been moved.')
            return 0
        if args.action == 'start':
            # Preserve the existing best-effort voice container startup.
            subprocess.Popen([str(python), str(ROOT / 'scripts/auto_voice.py')], cwd=ROOT)
        cmd = [str(python), '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000']
        if args.action == 'dev':
            cmd.append('--reload')
        return subprocess.call(cmd, cwd=ROOT / 'backend')
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f'[ERROR] Runtime check/setup failed: {exc}. Close the server and rerun setup. If needed, extract to C:\\SceneForge first.', file=sys.stderr)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
