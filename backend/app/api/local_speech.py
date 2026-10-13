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

def _built_in_profile(db, name, url, model):
    profile = db.query(ProviderProfile).filter_by(capability='speech', name=name).first()
    if profile is None:
        profile = ProviderProfile(capability='speech', name=name, base_url=url, model=model, secret_ref='')
        db.add(profile); db.commit(); db.refresh(profile)
    return profile


@router.get('/kokoro_builtin/status')
def kokoro_status():
    from app.providers import kokoro_builtin
    return kokoro_builtin.status()


@router.post('/kokoro_builtin/download')
def kokoro_download():
    """Download the built-in Kokoro voices (about 120 MB) in the background."""
    from app.providers import kokoro_builtin
    if kokoro_builtin.installed():
        return kokoro_builtin.status()
    if kokoro_builtin.status()['state'] != 'downloading':
        def run():
            try: kokoro_builtin.download()
            except ValueError: pass   # reported through status()
        _threading.Thread(target=run, daemon=True).start()
        kokoro_builtin._progress['state'] = 'downloading'
    return kokoro_builtin.status()


@router.get('/voicebox/status')
def voicebox_status():
    from app.providers import voicebox
    return voicebox.status()


@router.post('/{engine}/connect')
def connect(engine: str, db: Session = Depends(get_db)):
    if engine == 'kokoro_builtin':
        from app.providers import kokoro_builtin
        if not kokoro_builtin.installed():
            raise HTTPException(409, f'Download the built-in Kokoro voices first ({kokoro_builtin.DOWNLOAD_MB} MB, one time).')
        profile = _built_in_profile(db, 'kokoro_builtin', 'builtin://kokoro', 'kokoro-82m')
        voices = kokoro_builtin.voice_details()
        return {'profile': _to_out(profile), 'voices': [v['id'] for v in voices], 'status': 'ready',
                'message': 'Kokoro is built into SceneForge and ready. English, Spanish, French, Hindi, Italian and Portuguese.'}
    if engine == 'voicebox':
        from app.providers import voicebox
        if not voicebox.running():
            raise HTTPException(503, 'Voicebox is not running. Install it from voicebox.sh, open it, then click Connect Voicebox again.')
        profile = _built_in_profile(db, 'voicebox', voicebox.DEFAULT_URL, 'voicebox')
        try: voices = voicebox.voice_details(profile.base_url)
        except ValueError as e:
            # Connected, but nothing to speak with yet: keep the connection and say what to do in Voicebox.
            return {'profile': _to_out(profile), 'voices': [], 'status': 'needs_voices', 'message': str(e)}
        return {'profile': _to_out(profile), 'voices': [v['id'] for v in voices], 'status': 'service_reachable',
                'message': f'Voicebox connected with {len(voices)} voice{"s" if len(voices) != 1 else ""}. Pick one under Voice.'}
    if engine not in ENGINES: raise HTTPException(404, 'Unknown local engine')
    url, model = ENGINES[engine]
    profile = db.query(ProviderProfile).filter_by(capability='speech', name=engine).first()
    if profile is None:
        profile = ProviderProfile(capability='speech',name=engine,base_url=url,model=model,secret_ref='')
    try: voices = list_voices(profile)
    except ValueError as e:
        raise HTTPException(503, f'{e} If you use Docker, check that Docker Desktop and the {engine} container are running.')
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


def _docker_exe() -> str | None:
    # Docker Desktop installed after SceneForge started is not on this process's PATH yet.
    from app import managed_ai
    return managed_ai.docker_path()


def _docker(args: list[str], timeout: int = 20):
    flags = _subprocess.CREATE_NO_WINDOW if _os.name == 'nt' else 0  # type: ignore[attr-defined]
    return _subprocess.run([_docker_exe() or 'docker', *args], capture_output=True, text=True, timeout=timeout, creationflags=flags)


def _docker_state() -> dict:
    if not _docker_exe():
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
        with requests.Session() as http:
            http.trust_env = False  # never through a system proxy for this computer's own engine
            reachable = http.get(url + '/v1/audio/voices', timeout=2).ok
    except Exception:  # noqa: BLE001
        reachable = False
    state = dict(_START_STATE.get(engine, {'state': 'idle', 'log': ''}))
    if reachable:
        state['state'] = 'running'
    from app import native_engines
    if engine == 'chatterbox' and (native_engines.installed('chatterbox') or reachable):
        runtime = {'docker': 'ready', 'message': 'Runs on this computer without Docker.'}
    elif engine == 'chatterbox':
        runtime = {'docker': 'not_installed', 'message': 'Chatterbox is not installed yet. Open AI Engines and click Install next to Chatterbox: one click, no Docker.'}
    else:
        runtime = _docker_state()
    return {'engine': engine, 'url': url, 'reachable': reachable, 'services_bundled': _services_dir() is not None, **runtime, **state}


@router.post('/{engine}/start')
def engine_start(engine: str):
    """Build/start the engine's container with Docker Compose in the background.
    The first Chatterbox start downloads several GB and can take 10–30 minutes."""
    if engine not in ENGINES: raise HTTPException(404, 'Unknown local engine')
    if engine == 'chatterbox':
        # 0.9.4-beta.3: Chatterbox runs natively (no Docker). Start an installed copy, or
        # point to the one-click install.
        from app import native_engines, managed_ai
        if native_engines.installed('chatterbox'):
            native_engines.start('chatterbox', managed_ai.preferences().get('gpu', False))
            with _START_LOCK:
                _START_STATE[engine] = {'state': 'starting', 'log': 'Starting Chatterbox (no Docker)…\n'}
            return {'engine': engine, 'state': 'starting'}
        if managed_ai.preferences().get('runtime', {}).get('chatterbox') != 'docker' and 'chatterbox' not in managed_ai.preferences().get('components', []):
            raise HTTPException(409, 'Chatterbox is not installed yet. Open AI Engines and click Install next to Chatterbox: one click, no Docker.')
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
    # Same Compose project as the one-click installer, so both share one container
    # and one model cache instead of fighting over port 8881.
    from app import managed_ai
    base = managed_ai.compose(_docker_exe() or 'docker')
    args = base[1:] + (['--profile', 'arabic', 'up', '-d', '--build', 'chatterbox'] if engine == 'chatterbox' else ['up', '-d', 'kokoro'])

    def run():
        flags = _subprocess.CREATE_NO_WINDOW if _os.name == 'nt' else 0  # type: ignore[attr-defined]
        try:
            proc = _subprocess.Popen([base[0], *args], cwd=str(services), stdout=_subprocess.PIPE, stderr=_subprocess.STDOUT,
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
