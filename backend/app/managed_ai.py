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
import threading
import time
import requests
from app.config import DATA_DIR, RESOURCE_DIR

COMPONENTS = ('whisper', 'stable_diffusion', 'chatterbox')
_lock = threading.RLock()
_running = False
_state = {'status':'idle', 'completed':0, 'total':0, 'current':'', 'log':[], 'error':''}
try:
    _state.update(json.loads((DATA_DIR/'ai-install-status.json').read_text()))
    if _state['status']=='running':
        _state.update(status='error',error='Setup was interrupted. Retry resumes installed components and cached downloads.')
except (OSError,ValueError):pass

def engine_root():
    return Path(os.environ.get('LOCALAPPDATA', Path.home()/'.sceneforge'))/'SceneForge'/'engines'

def preferences():
    try:
        return json.loads((DATA_DIR/'managed-ai.json').read_text())
    except (OSError, ValueError):
        return {'components':[], 'autostart':True, 'gpu':False}

def save_preferences(value):
    p = DATA_DIR/'managed-ai.json'
    tmp = p.with_suffix('.tmp')
    tmp.write_text(json.dumps(value), encoding='utf-8')
    tmp.replace(p)

def state():
    with _lock:
        return {**_state, 'log':list(_state['log']), 'settings':preferences(), 'supported':os.name=='nt'}

def report(message, **patch):
    with _lock:
        _state.update(patch)
        _state['log'] = (_state['log'] + [message[:1000]])[-80:]
        tmp = DATA_DIR/'ai-install-status.tmp'
        tmp.write_text(json.dumps(_state), encoding='utf-8')
        tmp.replace(DATA_DIR/'ai-install-status.json')
    print('[Local AI] ' + message, flush=True)

def run(args, timeout=3600):
    # A timed command cannot leave its installers/children running unseen.
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
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

def warmup(component,args):
    port=7860 if component=='stable_diffusion' else 8881
    errors=[]
    def load():
        try:
            with session() as s:
                r=s.post(f'http://127.0.0.1:{port}/warmup',timeout=(5,3600),allow_redirects=False)
                r.raise_for_status()
        except Exception as exc:errors.append(exc)
    worker=threading.Thread(target=load,daemon=True);worker.start()
    cache='/models' if component=='stable_diffusion' else '/root/.cache/huggingface'
    while worker.is_alive():
        worker.join(5)
        if worker.is_alive():
            try:
                result=subprocess.run(args+['exec','-T',component,'du','-sb',cache],capture_output=True,text=True,timeout=5,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                if result.returncode==0:
                    size=int(result.stdout.split()[0]);report(f'{component}: {size/1_000_000:.1f} MB cached; downloading/loading model.')
            except (ValueError,IndexError,OSError,subprocess.TimeoutExpired):pass
    if errors:
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
        _state.update(status='running',completed=0,total=len(components),current='',log=[],error='')
    try:
        if os.name!='nt':raise RuntimeError('This automatic installer is for Windows. Existing local APIs remain available on other systems.')
        root=engine_root();root.mkdir(parents=True,exist_ok=True)
        minimum=500_000_000 if components==['whisper'] else 15_000_000_000
        if shutil.disk_usage(root).free<minimum:raise RuntimeError('Not enough free space for selected local AI. Free space, then Retry.')
        prior=preferences()
        value={**prior,'components':list(prior['components']),'autostart':prior.get('autostart',True),'gpu':bool(gpu)}
        save_preferences(value)
        for component in components:
            report('Preparing '+component, current=component)
            if component=='whisper':
                report('Downloading/checking Whisper multilingual base model (about 145 MB).')
                from faster_whisper import WhisperModel
                from app.providers.transcribe import _load_local_model
                model=_load_local_model(WhisperModel)
                del model
            else:
                ready=image_ready() if component=='stable_diffusion' else bool((health(component) or {}).get('model_ready'))
                if not ready:
                    port=7860 if component=='stable_diffusion' else 8881
                    import socket
                    try:
                        with socket.create_connection(('127.0.0.1',port),timeout=1):pass
                    except OSError:pass
                    else:
                        if not health(component):raise RuntimeError(f'Port {port} is used by another service. Stop it or use your existing engine connection; Retry will not replace it.')
                    docker=ensure_docker();args=compose(docker,gpu)
                    profile='images' if component=='stable_diffusion' else 'arabic'
                    run(args+['--profile',profile,'up','-d','--build',component])
                    report('Downloading/loading '+component+' models. First setup can take many minutes; progress is shown below.')
                    port=7860 if component=='stable_diffusion' else 8881
                    for _ in range(90):
                        if health(component):break
                        time.sleep(2)
                    else:raise RuntimeError(component+' service did not start. Check Docker Desktop and Retry.')
                    warmup_with_retry(component,args)
                    if not (health(component) or {}).get('model_ready'):raise RuntimeError(component+' model did not become ready.')
                register(component)
            value['components']=list(dict.fromkeys(value['components']+[component]))
            save_preferences(value)
            report(component+' ready',completed=_state['completed']+1)
        report('Selected local AI components are ready.',status='done',current='')
        return True
    except Exception as exc:
        report(str(exc),status='error',error=str(exc),current=_state['current'])
        return False
    finally:
        with _lock:_running=False

def autostart(force=False, services=None):
    prefs=preferences()
    if (not force and not prefs.get('autostart',True)) or os.name!='nt':return
    services=services if services is not None else [c for c in prefs.get('components',[]) if c!='whisper']
    if not services:return
    try:
        # Startup never installs software or builds images. Installation is explicit.
        docker=docker_path()
        if not docker:return
        if not docker_ready(docker):
            desktop=Path(os.environ.get('ProgramFiles',r'C:\Program Files'))/'Docker/Docker/Docker Desktop.exe'
            if desktop.is_file():subprocess.Popen([str(desktop)])
            for _ in range(30):
                if docker_ready(docker):break
                time.sleep(2)
            else:return
        run(compose(docker,prefs.get('gpu',False))+['--profile','images','--profile','arabic','start']+services,timeout=120)
        # Reuse installed model caches, without downloading on every app launch.
        for c in services:
            port=7860 if c=='stable_diffusion' else 8881
            for _ in range(30):
                if health(c):break
                time.sleep(2)
            with session() as s:s.post(f'http://127.0.0.1:{port}/warmup',timeout=(5,600))
    except Exception as exc:report('Automatic startup needs attention: '+str(exc))
