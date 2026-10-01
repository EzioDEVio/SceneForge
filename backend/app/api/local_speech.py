"""Local speech components; fixed loopback endpoints, no cloud credentials."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import ProviderProfile
from app.api.providers import _to_out
from app.providers.speech_http import list_voices

router = APIRouter(prefix='/api/local-speech', tags=['local speech'])
ENGINES = {'kokoro': ('http://127.0.0.1:8880', 'kokoro'),
           'chatterbox': ('http://127.0.0.1:8881', 'chatterbox')}

@router.post('/{engine}/connect')
def connect(engine: str, db: Session = Depends(get_db)):
    if engine not in ENGINES: raise HTTPException(404, 'Unknown local engine')
    url, model = ENGINES[engine]
    profile = db.query(ProviderProfile).filter_by(capability='speech', name=engine).first()
    if profile is None:
        profile = ProviderProfile(capability='speech',name=engine,base_url=url,model=model,secret_ref='')
    try: voices = list_voices(profile)
    except ValueError:
        raise HTTPException(503, f'{engine.title()} is unavailable at {url}. Start your installed voice service, then retry. If you use Docker, check that its engine and voice container are running.')
    if not voices: raise HTTPException(503, 'The speech service has no available voices.')
    db.add(profile);db.commit();db.refresh(profile)
    return {'profile': _to_out(profile), 'voices': voices, 'status': 'service_reachable',
            'message': 'Service connected. Run a short audition to verify model readiness.'}


# ---------------------------------------------------------------------------------------
# Local Whisper diagnostics, and starting the Docker voice engines from inside the app.
# ---------------------------------------------------------------------------------------
import os as _os
import shutil as _shutil
import subprocess as _subprocess
import threading as _threading
from pathlib import Path as _Path

_START_STATE: dict = {}
_START_LOCK = _threading.Lock()


@router.get('/whisper/check')
def whisper_check():
    from app.providers import transcribe
    return transcribe.diagnose()


@router.post('/whisper/reset')
def whisper_reset():
    from app.providers import transcribe
    removed = transcribe.reset_model_cache()
    return {'removed': removed, 'model_dir': str(transcribe.model_dir()),
            'message': 'The local Whisper model was removed. The next caption run downloads it again.' if removed else 'No downloaded model was found.'}


def _services_dir() -> _Path | None:
    from app.config import RESOURCE_DIR
    for base in (RESOURCE_DIR / 'services', _Path(__file__).resolve().parents[3] / 'services'):
        if (base / 'compose.yaml').exists():
            return base
    return None


def _docker(args: list[str], timeout: int = 20):
    flags = _subprocess.CREATE_NO_WINDOW if _os.name == 'nt' else 0  # type: ignore[attr-defined]
    return _subprocess.run(['docker', *args], capture_output=True, text=True, timeout=timeout, creationflags=flags)


def _docker_state() -> dict:
    if not _shutil.which('docker'):
        return {'docker': 'missing', 'message': 'Docker Desktop is not installed. Install Docker Desktop (Linux containers), start it, then click Start again.'}
    try:
        info = _docker(['info', '--format', '{{.OSType}}'])
    except Exception as e:  # noqa: BLE001
        return {'docker': 'not_running', 'message': f'Docker did not respond ({e}). Start Docker Desktop and wait until it says it is running.'}
    if info.returncode != 0:
        return {'docker': 'not_running', 'message': 'Docker Desktop is installed but its engine is not running. Start Docker Desktop, wait for "Engine running", then click Start again.'}
    if info.stdout.strip() and info.stdout.strip() != 'linux':
        return {'docker': 'wrong_mode', 'message': 'Docker is in Windows-containers mode. Right-click the Docker tray icon → "Switch to Linux containers…", then click Start again.'}
    return {'docker': 'ready', 'message': 'Docker is ready.'}


@router.get('/{engine}/status')
def engine_status(engine: str):
    if engine not in ENGINES: raise HTTPException(404, 'Unknown local engine')
    url, _ = ENGINES[engine]
    import requests
    try:
        reachable = requests.get(url + '/v1/audio/voices', timeout=2).ok
    except Exception:  # noqa: BLE001
        reachable = False
    state = dict(_START_STATE.get(engine, {'state': 'idle', 'log': ''}))
    if reachable:
        state['state'] = 'running'
    return {'engine': engine, 'url': url, 'reachable': reachable, 'services_bundled': _services_dir() is not None, **_docker_state(), **state}


@router.post('/{engine}/start')
def engine_start(engine: str):
    """Build/start the engine's container with Docker Compose in the background.
    The first Chatterbox start downloads several GB and can take 10–30 minutes."""
    if engine not in ENGINES: raise HTTPException(404, 'Unknown local engine')
    docker = _docker_state()
    if docker['docker'] != 'ready':
        raise HTTPException(503, docker['message'])
    services = _services_dir()
    if not services:
        raise HTTPException(503, 'The voice service files are missing from this installation. Reinstall SceneForge.')
    with _START_LOCK:
        if _START_STATE.get(engine, {}).get('state') == 'starting':
            return {'engine': engine, 'state': 'starting'}
        _START_STATE[engine] = {'state': 'starting', 'log': 'Starting…\n'}
    args = ['compose', '-f', str(services / 'compose.yaml')]
    args += ['--profile', 'arabic', 'up', '-d', '--build', 'chatterbox'] if engine == 'chatterbox' else ['up', '-d', 'kokoro']

    def run():
        flags = _subprocess.CREATE_NO_WINDOW if _os.name == 'nt' else 0  # type: ignore[attr-defined]
        try:
            proc = _subprocess.Popen(['docker', *args], cwd=str(services), stdout=_subprocess.PIPE, stderr=_subprocess.STDOUT,
                                     text=True, errors='replace', creationflags=flags)
            for line in proc.stdout:  # type: ignore[union-attr]
                with _START_LOCK:
                    _START_STATE[engine]['log'] = (_START_STATE[engine]['log'] + line)[-6000:]
            code = proc.wait()
            with _START_LOCK:
                _START_STATE[engine]['state'] = 'started' if code == 0 else 'failed'
                if code:
                    _START_STATE[engine]['log'] += f'\nDocker exited with code {code}.'
        except Exception as e:  # noqa: BLE001
            with _START_LOCK:
                _START_STATE[engine] = {'state': 'failed', 'log': f'{type(e).__name__}: {e}'}
    _threading.Thread(target=run, daemon=True).start()
    return {'engine': engine, 'state': 'starting'}
