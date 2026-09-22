"""Manage only the existing, loopback AUTOMATIC1111 installation."""
import os, socket, subprocess, threading, time
from pathlib import Path
from app.config import LOGS_DIR
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
    return {'state':'failed' if _process else 'stopped','ready':False,'message':'Stable Diffusion API is unavailable. Start the engine or inspect the startup log.'}

def start():
    global _process,_started
    with _lock:
        state=status()
        if state['ready'] or (_process and _process.poll() is None): return state
        if os.name!='nt': return {'state':'failed','ready':False,'message':'Automatic launch is available on Windows. Start your local API manually on this platform.'}
        root=Path(os.environ.get('SCENEFORGE_SD_DIR',str(Path.home()/'stable-diffusion-webui')))
        if not (root/'webui-user.bat').is_file():
            return {'state':'failed','ready':False,'message':f'webui-user.bat not found in {root}. Set SCENEFORGE_SD_DIR to your installation folder and restart SceneForge.'}
        try:
            with socket.create_connection(('127.0.0.1',7860),timeout=1):
                return {'state':'starting','ready':False,'message':'Port 7860 is occupied but the API is not ready. Check that the existing WebUI uses --api.'}
        except OSError: pass
        try:
            with (LOGS_DIR/'stable-diffusion.log').open('a',encoding='utf-8') as log:
                _process=subprocess.Popen(['cmd.exe','/d','/c','webui-user.bat'],cwd=str(root),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            _started=time.time()
            return {'state':'starting','ready':False,'message':'Starting your existing WebUI. Model loading may take several minutes.'}
        except OSError as e:return {'state':'failed','ready':False,'message':str(e)}
