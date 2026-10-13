"""Native engines without Docker (0.9.4-beta.3), for real: downloads the pinned uv, lets uv
fetch a private Python 3.11, installs packages into a private environment, starts a service
on the engine port, warms it up through SceneForge's installer and stops it on shutdown.

The service is a stand-in with the same endpoints as services/chatterbox/server.py and only
FastAPI/uvicorn as packages, so the test does not download PyTorch or voice models (those run
in the installed app). Needs internet access to GitHub and PyPI; takes a minute or two."""
import os, pathlib, sys, tempfile, time
from unittest.mock import patch

root = pathlib.Path(__file__).resolve().parents[2]
tmp = tempfile.TemporaryDirectory(prefix='sf-native-')
os.environ['SCENEFORGE_DATA_DIR'] = str(pathlib.Path(tmp.name) / 'data')
os.environ['SCENEFORGE_NATIVE_ENGINES'] = str(pathlib.Path(tmp.name) / 'engines')
sys.path.insert(0, str(root / 'backend'))
from app import native_engines as ne, managed_ai as m

checks = 0
def check(name, ok):
    global checks
    assert ok, name
    checks += 1
    print('PASS ' + name, flush=True)

service = pathlib.Path(tmp.name) / 'service' / 'chatterbox'
service.mkdir(parents=True)
(service / 'requirements.txt').write_text('fastapi\nuvicorn\n')
(service / 'server.py').write_text('''
import os
from fastapi import FastAPI, Response
app = FastAPI()
state = {"ready": False}
@app.get("/health")
def health(): return {"service": "chatterbox", "model_ready": state["ready"], "loading": False, "last_error": None, "device": os.environ.get("CHATTERBOX_DEVICE"), "hf": os.environ.get("HF_HOME")}
@app.post("/warmup")
def warmup(): state["ready"] = True; return {"service": "chatterbox", "model_ready": True}
@app.get("/v1/audio/voices")
def voices(): return {"voices": [{"id": "default"}]}
''')

with patch.object(ne, '_service_source', return_value=service):
    uv = ne.ensure_uv(report=print)
    check('pinned uv downloads and passes its checksum', uv.is_file() and os.access(uv, os.X_OK))
    m.save_preferences({'components': [], 'autostart': True, 'gpu': False})
    ne.install('chatterbox', gpu=False, run=lambda a, e: m.run(a, env=e), report=m.report, packages=['fastapi', 'uvicorn'])
    check('a private Python 3.11 environment is created inside the engines folder',
          ne.installed('chatterbox') and str(ne.venv_python('chatterbox')).startswith(os.environ['SCENEFORGE_NATIVE_ENGINES']))
    import subprocess
    version = subprocess.run([str(ne.venv_python('chatterbox')), '-c', 'import sys;print(sys.version_info[:2])'], capture_output=True, text=True).stdout
    check('the environment runs Python 3.11 regardless of the system Python', '(3, 11)' in version)
    assert ne.start('chatterbox', gpu=False)
    for _ in range(60):
        if m.health('chatterbox'):
            break
        time.sleep(1)
    h = m.health('chatterbox')
    check('the engine answers on its usual port without Docker', h and h['device'] == 'cpu' and h['hf'].startswith(os.environ['SCENEFORGE_NATIVE_ENGINES']))
    m.warmup_with_retry('chatterbox', None)
    check('SceneForge warms the model through the same endpoint as before', m.health('chatterbox')['model_ready'] is True)
    from app.providers import speech_http
    from types import SimpleNamespace
    check('voice list works through the existing Chatterbox connection', speech_http.list_voices(SimpleNamespace(name='chatterbox', base_url='http://127.0.0.1:8881', secret_ref='', model='chatterbox')) == ['default'])
    ne.stop_all()
    for _ in range(20):
        if not m.health('chatterbox'):
            break
        time.sleep(.5)
    check('the engine stops when SceneForge closes', not m.health('chatterbox'))

    # 0.9.4-beta.7 (owner's PC): an engine left running by an earlier SceneForge kept the
    # port, so a new version reused an old, broken Chatterbox. Simulate a restart: the engine
    # keeps running but this SceneForge did not start it.
    assert ne.start('chatterbox', gpu=False)
    for _ in range(60):
        if m.health('chatterbox'): break
        time.sleep(1)
    old_pid = ne.port_owner(8881)['pid']
    ne._processes.clear()
    owner = ne.port_owner(8881)
    check('a leftover engine on the port is recognised as SceneForge\'s own', owner and owner['ours'] and owner['leftover'])
    m.save_preferences({'components': ['chatterbox'], 'autostart': True, 'gpu': False, 'runtime': {'chatterbox': 'native'}})
    m.autostart(force=True, services=['chatterbox'])
    for _ in range(60):
        if m.health('chatterbox') and ne.port_owner(8881) and ne.port_owner(8881)['pid'] != old_pid: break
        time.sleep(1)
    new_owner = ne.port_owner(8881)
    import psutil
    check('starting replaces the leftover engine with a fresh one from this version',
          new_owner and new_owner['pid'] != old_pid and not new_owner['leftover'] and not psutil.pid_exists(old_pid))
    ne.stop_all()
    for _ in range(20):
        if not ne.port_owner(8881): break
        time.sleep(.5)
    other = subprocess.Popen(['python3', '-m', 'http.server', '8881', '--bind', '127.0.0.1'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(20):
        if ne.port_owner(8881): break
        time.sleep(.5)
    freed, why = ne.free_port('chatterbox', report=lambda *a: None)
    check('a program that is not part of SceneForge is never closed; the message names it',
          not freed and other.poll() is None and 'Close that program' in why and str(other.pid) in why)
    other.kill()
print(f'{checks} native engine checks passed')
