"""Local AI installation shared by NSIS and the editor. No paid calls.

Progress is per completed stage; downloads expose their actual tool output,
never a made-up byte percentage. Existing external engines are reused.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import requests
from app.config import DATA_DIR, RESOURCE_DIR

COMPONENTS = ('whisper', 'kokoro', 'stable_diffusion', 'chatterbox')
_lock = threading.RLock()
_running = False
_state = {'status':'idle', 'completed':0, 'total':0, 'current':'', 'part':0.0, 'step':'', 'log':[], 'error':''}
try:
    _state.update(json.loads((DATA_DIR/'ai-install-status.json').read_text()))
    if _state['status']=='running':
        _state.update(status='error',error='Setup was interrupted. Retry resumes installed components and cached downloads.')
except (OSError,ValueError):pass

def engine_root():
    return Path(os.environ.get('LOCALAPPDATA', Path.home()/'.sceneforge'))/'SceneForge'/'engines'

def preferences():
    try:
        prefs=json.loads((DATA_DIR/'managed-ai.json').read_text())
    except (OSError, ValueError):
        prefs={'components':[], 'autostart':True}
    if 'gpu' not in prefs:
        # Nobody chose yet: use the graphics card when an NVIDIA driver is installed (the
        # Docker engines always used the CUDA build; the processor is many times slower).
        from app.native_engines import nvidia_present
        prefs['gpu']=nvidia_present()
    return prefs

def save_preferences(value):
    p = DATA_DIR/'managed-ai.json'
    tmp = p.with_suffix('.tmp')
    tmp.write_text(json.dumps(value), encoding='utf-8')
    tmp.replace(p)

def running():
    """Which installed engines answer right now (quick loopback checks)."""
    from app.providers import kokoro_builtin
    ok=lambda c:bool(health(c)) and not (health(c) or {}).get('last_error')   # a failed model is not "Ready"
    return {'stable_diffusion': image_ready() or ok('stable_diffusion'),
            'chatterbox': ok('chatterbox'), 'kokoro': kokoro_builtin.installed()}

def set_runtime(component, runtime):
    prefs=preferences();prefs.setdefault('runtime',{})[component]=runtime;save_preferences(prefs)

def state():
    with _lock:
        import platform
        from app.native_engines import UV_ASSETS, build, nvidia_present
        return {**_state, 'log':list(_state['log']), 'settings':preferences(), 'supported':(platform.system(),platform.machine()) in UV_ASSETS,
                'builds':{c:build(c) for c in ('stable_diffusion','chatterbox') if build(c)}, 'nvidia':nvidia_present()}

def report(message, **patch):
    with _lock:
        _state.update(patch)
        _state['log'] = (_state['log'] + [message[:1000]])[-80:]
        tmp = DATA_DIR/'ai-install-status.tmp'
        tmp.write_text(json.dumps(_state), encoding='utf-8')
        tmp.replace(DATA_DIR/'ai-install-status.json')
    line = '[Local AI] ' + message
    try:
        print(line, flush=True)
    except UnicodeEncodeError:
        # Frozen Windows installers may have a legacy console encoding. Docker
        # progress contains Unicode; displaying it must never abort installation.
        encoding = getattr(sys.stdout, 'encoding', None) or 'utf-8'
        print(line.encode(encoding, errors='backslashreplace').decode(encoding), flush=True)

def run(args, timeout=3600, env=None):
    # A timed command cannot leave its installers/children running unseen.
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
                          text=True, encoding='utf-8', errors='replace', creationflags=flags) as p:
        def expire():
            if p.poll() is None:
                if os.name=='nt':
                    subprocess.run(['taskkill.exe','/PID',str(p.pid),'/T','/F'], capture_output=True, timeout=15)
                else:
                    p.kill()
        timer=threading.Timer(timeout,expire);timer.daemon=True;timer.start()
        try:
            for line in p.stdout:
                if line.strip():report(line.strip())
            code=p.wait()
            if code:raise RuntimeError(f'Installation command failed ({code}). See progress log; Retry resumes existing downloads.')
        finally:
            timer.cancel()

def docker_path():
    found=shutil.which('docker')
    if found:return found
    p=Path(os.environ.get('ProgramFiles',r'C:\Program Files'))/'Docker/Docker/resources/bin/docker.exe'
    return str(p) if p.is_file() else None

def docker_ready(docker):
    try:
        return subprocess.run([docker,'info','--format','{{.ServerVersion}}'],capture_output=True,timeout=5,
                              creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)).returncode==0
    except (OSError,subprocess.TimeoutExpired):return False

def ensure_docker():
    docker=docker_path()
    if not docker:
        winget=shutil.which('winget')
        if not winget:raise RuntimeError('Windows App Installer is unavailable. Install Docker Desktop, then click Retry. Your other components remain installed.')
        report('Installing Docker Desktop. Windows may ask for administrator approval or a restart.')
        run([winget,'install','--exact','--id','Docker.DockerDesktop','--accept-package-agreements','--accept-source-agreements'])
        docker=docker_path()
        if not docker:raise RuntimeError('Docker installation requires a Windows restart. Restart, open SceneForge, and click Retry.')
    if not docker_ready(docker):
        desktop=Path(os.environ.get('ProgramFiles',r'C:\Program Files'))/'Docker/Docker/Docker Desktop.exe'
        if desktop.is_file():subprocess.Popen([str(desktop)],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        report('Waiting for Docker Desktop. Complete its first-run setup if shown.')
        for _ in range(30):
            if docker_ready(docker):return docker
            time.sleep(2)
        raise RuntimeError('Finish Docker Desktop setup, enable Linux containers/WSL if requested, then click Retry. A Windows restart may be needed.')
    return docker

def compose(docker, gpu=False):
    root=engine_root();root.mkdir(parents=True,exist_ok=True)
    # Fixed project identity survives app updates; model volumes stay intact.
    source=Path(RESOURCE_DIR)/'services'
    if not source.is_dir():source=Path(__file__).resolve().parents[2]/'services'
    shutil.copytree(source,root/'services',dirs_exist_ok=True)
    args=[docker,'compose','-p','sceneforge-managed-ai','-f',str(root/'services/compose.yaml')]
    if gpu:
        override=root/'gpu.yaml'
        override.write_text('services:\n  stable_diffusion:\n    gpus: all\n',encoding='utf-8')
        args+=['-f',str(override)]
    return args

def session():
    s=requests.Session();s.trust_env=False;return s

def health(component):
    port=7860 if component=='stable_diffusion' else 8881
    try:
        with session() as s:
            r=s.get(f'http://127.0.0.1:{port}/health',timeout=3,allow_redirects=False)
            r.raise_for_status();data=r.json()
            return data if isinstance(data,dict) and data.get('service')==component else None
    except (requests.RequestException,ValueError):return None

def image_ready():
    try:
        with session() as s:
            r=s.get('http://127.0.0.1:7860/sdapi/v1/options',timeout=3,allow_redirects=False)
            return r.status_code==200 and isinstance(r.json(),dict) and isinstance(r.json().get('sd_model_checkpoint'),str)
    except (requests.RequestException,ValueError):return False

class _EngineMismatch(Exception):
    def __init__(self, status_code):
        super().__init__(f'HTTP {status_code}');self.status_code=status_code


def warmup(component,args):
    port=7860 if component=='stable_diffusion' else 8881
    errors=[]
    def load():
        try:
            with session() as s:
                r=s.post(f'http://127.0.0.1:{port}/warmup',timeout=(5,3600),allow_redirects=False)
                if r.status_code in (404, 405):
                    errors.append(_EngineMismatch(r.status_code));return
                r.raise_for_status()
        except Exception as exc:errors.append(exc)
    worker=threading.Thread(target=load,daemon=True);worker.start()
    cache='/models' if component=='stable_diffusion' else '/root/.cache/huggingface'
    last_mb,still=-1.0,0
    while worker.is_alive():
        worker.join(5)
        if worker.is_alive():
            try:
                if not args:
                    from app import native_engines
                    mb=native_engines.model_cache_mb(component);expected=native_engines.MODEL_REPOS.get(component,('',0))[1]
                    still=still+1 if mb<=last_mb+1 else 0;last_mb=mb
                    label='Stable Diffusion' if component=='stable_diffusion' else 'Chatterbox'
                    if still>=3 and mb>0:
                        report(f'{label}: model downloaded ({mb:.0f} MB); loading it into memory. On the processor this can take several minutes.',step='Loading the model',part=0.95)
                    else:
                        report(f'{label}: {mb:.0f} MB of about {expected} MB downloaded.',step='Downloading the model',part=0.75+0.2*min(1.0,mb/max(1,expected)))
                    continue
                result=subprocess.run(args+['exec','-T',component,'du','-sb',cache],capture_output=True,text=True,timeout=5,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                if result.returncode==0:
                    size=int(result.stdout.split()[0]);report(f'{component}: {size/1_000_000:.1f} MB cached; downloading/loading model.')
            except (ValueError,IndexError,OSError,subprocess.TimeoutExpired):pass
    if errors:
        # HTTP 404/405 from /warmup means the process on this port is an older or
        # different engine (owner log 2026-10-06), not a failed model download. Say so
        # directly, do not blame the model, and do not let warmup_with_retry retry it.
        response = getattr(errors[0], 'response', None)
        code = errors[0].status_code if isinstance(errors[0], _EngineMismatch) else getattr(response, 'status_code', None)
        if code in (404, 405):
            detail = (f'{component} service on port {port} does not support the required '
                      f'POST /warmup endpoint (HTTP {code}). '
                      'An older or different engine is probably using that port. Stop the older engine '
                      'in Docker Desktop, then click Retry to start the bundled engine. '
                      'Cached models are retained.')
            report(detail)
            raise RuntimeError(detail) from errors[0]
        detail = str((health(component) or {}).get('last_error') or errors[0])[:600]
        report(component + ' warmup failed: ' + detail)
        raise RuntimeError(component + ' model loading failed: ' + detail + '. Retry resumes cached downloads.') from errors[0]


def warmup_with_retry(component, args):
    """Retry one transient download/startup failure; retain meaningful engine errors."""
    try:
        warmup(component, args)
    except RuntimeError as exc:
        detail = str(exc).lower()
        transient = any(word in detail for word in ('timeout', 'timed out', 'connection', 'temporar', 'incomplete', 'chunked', '502', '503', '504', 'remoteprotocol'))
        fatal = any(word in detail for word in ('out of memory', 'no space', '401', '403', 'permission denied'))
        if not transient or fatal: raise
        report(component + ': temporary download/startup failure; retrying once with cached files.')
        time.sleep(2)
        warmup(component, args)

def register(component):
    from app.db.database import SessionLocal
    from app.db.models import ProviderProfile
    name,capability,port=('local_sd','image',7860) if component=='stable_diffusion' else ('chatterbox','speech',8881)
    with SessionLocal() as db:
        # Keep owner-selected external connections intact.
        if not db.query(ProviderProfile).filter_by(name=name,capability=capability).first():
            db.add(ProviderProfile(name=name,capability=capability,model='current' if capability=='image' else 'chatterbox-multilingual',base_url=f'http://127.0.0.1:{port}',secret_ref=''))
            db.commit()

def install(components, gpu=False):
    global _running
    with _lock:
        if _running:raise RuntimeError('Local AI installation is already running.')
        if not components or any(c not in COMPONENTS for c in components):raise ValueError('Choose known local AI components.')
        _running=True
        _state.update(status='running',completed=0,total=len(components),current='',log=[],error='',queue=list(components),part=0.0,step='')
    try:
        root=engine_root();root.mkdir(parents=True,exist_ok=True)
        minimum=500_000_000 if set(components)<={'whisper','kokoro'} else 15_000_000_000
        if shutil.disk_usage(root).free<minimum:raise RuntimeError('Not enough free space for selected local AI. Free space, then Retry.')
        prior=preferences()
        value={**prior,'components':list(prior['components']),'autostart':prior.get('autostart',True),'gpu':bool(gpu)}
        save_preferences(value)
        for component in components:
            report('Preparing '+component, current=component, part=0.0, step='Preparing')
            if component=='kokoro':
                from app.providers import kokoro_builtin
                report('Downloading the Kokoro voices.',step='Downloading voices',part=0.1)
                kokoro_builtin.download(report)
                from app.db.database import SessionLocal
                from app.db.models import ProviderProfile
                with SessionLocal() as db:
                    if not db.query(ProviderProfile).filter_by(capability='speech',name='kokoro_builtin').first():
                        db.add(ProviderProfile(capability='speech',name='kokoro_builtin',base_url='builtin://kokoro',model='kokoro-82m',secret_ref=''));db.commit()
            elif component=='whisper':
                report('Downloading/checking Whisper multilingual base model (about 145 MB).')
                from faster_whisper import WhisperModel
                from app.providers.transcribe import _load_local_model
                report('Downloading the Whisper model.',step='Downloading the captions model',part=0.1)
                model=_load_local_model(WhisperModel)
                del model
            else:
                from app import native_engines
                wanted='gpu' if gpu else 'cpu'
                failed=native_engines.installed(component) and bool((health(component) or {}).get('last_error'))
                if native_engines.build(component) not in (None,wanted) or native_engines.stale(component) or failed:
                    # Switch between the CPU and NVIDIA builds, update packages from an older
                    # SceneForge, or restart an engine whose model failed to load (Retry).
                    report(f"Switching {component} to the {'NVIDIA graphics card' if gpu else 'CPU'} build." if native_engines.build(component) not in (None,wanted)
                           else f'Updating and restarting {component}.',step='Updating the engine',part=0.05)
                    native_engines.stop(component)
                    for _ in range(30):
                        if not health(component):break
                        time.sleep(1)
                ready=(native_engines.build(component) in (None,wanted)) and not native_engines.stale(component) and (image_ready() if component=='stable_diffusion' else bool((health(component) or {}).get('model_ready')))
                if not ready:
                    port=7860 if component=='stable_diffusion' else 8881
                    import socket
                    try:
                        with socket.create_connection(('127.0.0.1',port),timeout=1):pass
                    except OSError:pass
                    else:
                        if not health(component):raise RuntimeError(f'Port {port} is used by another service. Stop it or use your existing engine connection; Retry will not replace it.')
                    if not health(component):
                        # Native engine: private Python + packages, no Docker (0.9.4-beta.3).
                        from app import native_engines
                        report('Setting up a private Python for this engine.',step='Installing the engine (largest download)',part=0.1)
                        native_engines.install(component,gpu,run=lambda a,e:run(a,env=e),report=report)
                        report('Engine installed.',step='Starting the engine',part=0.6)
                        native_engines.start(component,gpu)
                        set_runtime(component,'native')
                        report('Starting '+component+'. The first start loads PyTorch and can take a few minutes.')
                        for _ in range(300):
                            if health(component):break
                            if not native_engines.running(component):raise RuntimeError(component+' stopped while starting. Open the engine log in AI Engines and Retry.')
                            time.sleep(2)
                        else:raise RuntimeError(component+' did not start within 10 minutes. Retry; downloads already made are kept.')
                    else:
                        report('Using the '+component+' engine that is already running on this computer.')
                    report('Downloading/loading '+component+' models. First setup can take many minutes; progress is shown below.')
                    report('Engine running.',step='Downloading and loading the model',part=0.75)
                    warmup_with_retry(component,None)
                    if not (health(component) or {}).get('model_ready'):raise RuntimeError(component+' model did not become ready.')
                register(component)
            value={**preferences(),'gpu':bool(gpu)}   # keep what steps saved (e.g. runtime)
            value['components']=list(dict.fromkeys(value.get('components',[])+[component]))
            save_preferences(value)
            report(component+' ready',completed=_state['completed']+1,part=0.0,step='')
        report('Selected local AI components are ready.',status='done',current='')
        return True
    except Exception as exc:
        report(str(exc),status='error',error=str(exc),current=_state['current'])
        return False
    finally:
        with _lock:_running=False

def autostart(force=False, services=None):
    prefs=preferences()
    if not force and not prefs.get('autostart',True):return
    services=services if services is not None else [c for c in prefs.get('components',[]) if c!='whisper']
    if not services:return
    try:
        # Startup never installs software or builds images. Installation is explicit.
        from app import native_engines
        runtime=prefs.get('runtime',{})
        native=[c for c in services if runtime.get(c)=='native' or native_engines.installed(c)]
        docker_services=[c for c in services if c not in native]
        for c in native:
            h=health(c)
            if h and (h.get('last_error') or native_engines.stale(c)) and native_engines.running(c):
                native_engines.stop(c);h=None   # Start = repair: restart an engine whose model failed or whose packages changed
            if not h:native_engines.start(c,prefs.get('gpu',False))
        if docker_services and os.name=='nt':
            # Engines installed by 0.9.4-beta.2 and earlier ran in Docker Desktop.
            docker=docker_path()
            if docker:
                if not docker_ready(docker):
                    desktop=Path(os.environ.get('ProgramFiles',r'C:\Program Files'))/'Docker/Docker/Docker Desktop.exe'
                    if desktop.is_file():subprocess.Popen([str(desktop)])
                    for _ in range(30):
                        if docker_ready(docker):break
                        time.sleep(2)
                if docker_ready(docker):
                    run(compose(docker,prefs.get('gpu',False))+['--profile','images','--profile','arabic','start']+docker_services,timeout=120)
        # Reuse installed model caches, without downloading on every app launch.
        for c in services:
            port=7860 if c=='stable_diffusion' else 8881
            for _ in range(150 if c in native else 30):
                if health(c):break
                time.sleep(2)
            else:continue
            with session() as s:s.post(f'http://127.0.0.1:{port}/warmup',timeout=(5,600))
    except Exception as exc:report('Automatic startup needs attention: '+str(exc))


def start_pending_setup() -> bool:
    """Install the AI tools chosen in the Windows installer (terms were accepted there).
    Returns True when an installation was started."""
    pending=DATA_DIR/'ai-setup-pending.json'
    try:
        value=json.loads(pending.read_text(encoding='utf-8'))
    except (OSError,ValueError):
        return False
    pending.unlink(missing_ok=True)
    components=[c for c in value.get('components',[]) if c in COMPONENTS]
    if not components or not value.get('accepted_terms'):
        return False
    with _lock:
        if _running:return False
        _state.update(status='running',error='')
    # Ticked in the installer: graphics card. Not ticked: detect (an NVIDIA driver means graphics card).
    gpu=bool(value.get('gpu')) or bool(preferences().get('gpu'))
    threading.Thread(target=install,args=(components,gpu),daemon=True).start()
    return True
