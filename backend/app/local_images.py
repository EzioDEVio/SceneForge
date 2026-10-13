"""Manage only the existing, loopback AUTOMATIC1111 installation."""
import os, socket, subprocess, threading, time
from pathlib import Path
from app.config import LOGS_DIR, DATA_DIR
import json, sys

def settings():
    default = {"folder": os.environ.get("SCENEFORGE_SD_DIR", str(Path.home()/"stable-diffusion-webui")), "autostart": True}
    try:
        saved = json.loads((DATA_DIR/"local-images.json").read_text())
        default.update({k:saved[k] for k in default if k in saved})
    except (OSError, ValueError): pass
    # Only a folder that really holds AUTOMATIC1111 counts; the guessed default must not
    # read as "Folder set" or be auto-started (owner report 2026-10-12).
    default["found"] = (Path(default["folder"]).expanduser()/"webui-user.bat").is_file()
    if not default["found"]:
        default["autostart"] = False
    # Never start the user's own AUTOMATIC1111 just because it exists: it would compete with
    # SceneForge's Stable Diffusion for port 7860 and graphics memory (owner's PC, 2026-10-13:
    # a fresh SceneForge folder started it). Only an explicitly saved choice starts it.
    if not (DATA_DIR/"local-images.json").is_file():
        default["autostart"] = False
    return default

def save_settings(folder, autostart):
    root = Path(folder).expanduser().resolve()
    if not (root/"webui-user.bat").is_file():
        raise ValueError("Choose the Stable Diffusion folder containing webui-user.bat.")
    value = {"folder":str(root), "autostart":bool(autostart)}
    temp = DATA_DIR/"local-images.tmp"
    with _lock:
        temp.write_text(json.dumps(value), encoding="utf-8")
        temp.replace(DATA_DIR/"local-images.json")
    return {**value, "found": True}

def stop():
    if _process and _process.poll() is None and os.name == "nt":
        subprocess.run(["taskkill.exe", "/PID", str(_process.pid), "/T", "/F"], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)

_lock=threading.Lock()
_process=None
_started=0.0

def status():
    import requests
    try:
        with requests.Session() as s:
            s.trust_env=False
            r=s.get('http://127.0.0.1:7860/sdapi/v1/options',timeout=2,allow_redirects=False)
            r.raise_for_status()
            return {'state':'ready','ready':True,'model':r.json().get('sd_model_checkpoint','current')}
    except Exception: pass
    if _process and _process.poll() is None:
        return {'state':'starting' if time.time()-_started<300 else 'failed','ready':False,'message':'Loading model…' if time.time()-_started<300 else 'Startup exceeded five minutes. View the log; the process is still running.'}
    from app.managed_ai import preferences
    if _started and time.time()-_started<600 and 'stable_diffusion' in preferences().get('components',[]):
        return {'state':'starting','ready':False,'message':'Loading installed Stable Diffusion. Check AI Engines for setup progress.'}
    if not _process and 'stable_diffusion' not in preferences().get('components',[]) and not settings()['found']:
        return {'state':'not_installed','ready':False,'message':'Stable Diffusion is not installed yet. Click Install Stable Diffusion: it is free and sets itself up.'}
    return {'state':'failed' if _process else 'stopped','ready':False,'message':'Stable Diffusion is installed but not running. Click Start / retry engine.'}

def start():
    global _process,_started
    with _lock:
        state=status()
        if state['ready'] or state['state']=='starting' or (_process and _process.poll() is None): return state
        if os.name!='nt': return {'state':'failed','ready':False,'message':'Automatic launch is available on Windows. Start your local API manually on this platform.'}
        from app import managed_ai
        if 'stable_diffusion' in managed_ai.preferences().get('components',[]):
            _started=time.time()
            threading.Thread(target=managed_ai.autostart,kwargs={'force':True,'services':['stable_diffusion']},daemon=True).start()
            return {'state':'starting','ready':False,'message':'Starting installed Stable Diffusion. CPU model loading can take several minutes.'}
        root=Path(settings()['folder'])
        if not (root/'webui-user.bat').is_file():
            return {'state':'not_installed','ready':False,'message':'Stable Diffusion is not installed yet. Open AI Engines and click Install next to Stable Diffusion: it is free and sets everything up for you.'}
        try:
            with socket.create_connection(('127.0.0.1',7860),timeout=1):
                return {'state':'starting','ready':False,'message':'Port 7860 is occupied but the API is not ready. Check that the existing WebUI uses --api.'}
        except OSError: pass
        try:
            with (LOGS_DIR/'stable-diffusion.log').open('a',encoding='utf-8') as log:
                # A frozen Python process must not pass its private DLL search path to WebUI.
                env = dict(os.environ)
                for key in ('PYTHONHOME','PYTHONPATH'):
                    env.pop(key, None)
                if getattr(sys, 'frozen', False):
                    import ctypes
                    ctypes.windll.kernel32.SetDllDirectoryW(None)
                try:
                    _process=subprocess.Popen(['cmd.exe','/d','/c','webui-user.bat'],cwd=str(root),env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
                finally:
                    if getattr(sys, 'frozen', False):
                        ctypes.windll.kernel32.SetDllDirectoryW(sys._MEIPASS)
            _started=time.time()
            return {'state':'starting','ready':False,'message':'Starting your existing WebUI. Model loading may take several minutes.'}
        except OSError as e:return {'state':'failed','ready':False,'message':str(e)}
