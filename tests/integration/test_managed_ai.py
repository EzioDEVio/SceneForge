"""Installation contracts, with mocked tools/downloads. No paid/network/model calls."""
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
root=Path(__file__).resolve().parents[2]
temp=tempfile.TemporaryDirectory()
os.environ['SCENEFORGE_DATA_DIR']=temp.name
sys.path.insert(0,str(root/'backend'))
from app import managed_ai as m
from app.db.database import init_db,SessionLocal
from app.db.models import ProviderProfile
from fastapi.testclient import TestClient
from app.main import app
init_db()
fakeos=SimpleNamespace(name='nt',environ=os.environ)
with TestClient(app) as client:
    r=client.post('/api/local-ai/setup',json={'components':['not-an-engine'],'accept_terms':True})
    assert r.status_code==422
    with patch('platform.system',return_value='Plan9'):
        assert client.get('/api/local-ai/setup').json()['supported'] is False
        assert client.post('/api/local-ai/setup',json={'components':['whisper'],'accept_terms':True}).status_code==400
print('PASS unknown components and unsupported platform rejected before installation')
with patch.object(m,'os',fakeos),patch.object(m,'engine_root',return_value=Path(temp.name)),patch.object(m.shutil,'disk_usage',return_value=SimpleNamespace(free=20_000_000_000)),patch('app.providers.transcribe._load_local_model',return_value=object()),patch.object(m,'ensure_docker') as docker,patch.object(m,'image_ready',return_value=False),patch.object(m,'warmup') as warm,patch('socket.create_connection',side_effect=OSError),\
     patch('app.native_engines.install') as native_install,patch('app.native_engines.start',return_value=True) as native_start,patch('app.native_engines.running',return_value=True),\
     patch.object(m,'health',side_effect=[None,{'service':'stable_diffusion','model_ready':False},{'service':'stable_diffusion','model_ready':True},
                                         {'service':'chatterbox','model_ready':False},{'service':'chatterbox','model_ready':True},{'service':'chatterbox','model_ready':True}]):
    assert m.install(['whisper','stable_diffusion','chatterbox']),m.state()['error']
    assert m.state()['completed']==3 and m.state()['status']=='done'
    # Stable Diffusion was not running: installed natively and started. Chatterbox already answered: reused.
    assert [c.args[0] for c in native_install.call_args_list]==['stable_diffusion'] and native_start.call_count==1 and warm.call_count==2
    docker.assert_not_called()
    assert m.preferences()['runtime']=={'stable_diffusion':'native'}
with SessionLocal() as db:
    assert {p.name for p in db.query(ProviderProfile)}=={'local_sd','chatterbox'}
    p=db.query(ProviderProfile).filter_by(name='local_sd').one();p.base_url='http://127.0.0.1:9999';db.commit()
m.register('stable_diffusion')
with SessionLocal() as db:assert db.query(ProviderProfile).filter_by(name='local_sd').one().base_url.endswith(':9999')
print('PASS ordered installation without Docker, actual stage completion, model checks, profile registration and existing connection preservation')
with patch.object(m,'os',fakeos),patch.object(m,'engine_root',return_value=Path(temp.name)),patch.object(m.shutil,'disk_usage',return_value=SimpleNamespace(free=0)),patch.object(m,'run') as commands:
    assert not m.install(['whisper']);assert 'free space' in m.state()['error'];commands.assert_not_called()
with patch.object(m,'os',fakeos),patch.object(m,'engine_root',return_value=Path(temp.name)),patch.object(m.shutil,'disk_usage',return_value=SimpleNamespace(free=20_000_000_000)),patch.object(m,'image_ready',return_value=False),patch('socket.create_connection',return_value=MagicMock()),patch.object(m,'health',return_value=None),patch('app.native_engines.install') as docker:
    assert not m.install(['stable_diffusion']);assert 'another service' in m.state()['error'];docker.assert_not_called()
print('PASS insufficient space and occupied ports fail clearly without installing or replacing services')
with patch.object(m,'os',fakeos),patch.object(m,'engine_root',return_value=Path(temp.name)),patch.object(m.shutil,'disk_usage',return_value=SimpleNamespace(free=20_000_000_000)),patch('app.providers.transcribe._load_local_model',return_value=object()):
    assert m.install(['whisper']);assert m.state()['status']=='done'
    assert {'whisper','stable_diffusion','chatterbox'}==set(m.preferences()['components'])
m.save_preferences({**m.preferences(),'autostart':False})
with patch.object(m,'os',fakeos),patch.object(m,'docker_path') as docker:
    m.autostart();docker.assert_not_called()
with patch.object(m,'os',fakeos),patch('app.native_engines.installed',side_effect=lambda c:c=='stable_diffusion'),patch('app.native_engines.start') as native_start,patch.object(m,'docker_path') as docker,patch.object(m,'health',side_effect=[None,{'model_ready':True}]),patch.object(m,'session'):
    m.autostart(force=True,services=['stable_diffusion'])
    native_start.assert_called_once();docker.assert_not_called()
m.save_preferences({**m.preferences(),'runtime':{}})
with patch.object(m,'os',fakeos),patch('app.native_engines.installed',return_value=False),patch.object(m,'docker_path',return_value='docker.exe'),patch.object(m,'docker_ready',return_value=True),patch.object(m,'compose',return_value=['docker.exe','compose']),patch.object(m,'run') as commands,patch.object(m,'health',return_value={'model_ready':True}),patch.object(m,'session') as session:
    m.autostart(force=True,services=['chatterbox'])
    args=commands.call_args.args[0];assert 'start' in args and '--build' not in args and 'install' not in args
print('PASS Retry preserves installed components, startup choice is honored, native engines start without Docker, older Docker installs still start, manual start never builds or installs')
m._state['status']='running'
with TestClient(app) as client:assert client.get('/api/close-status').json()['ready'] is False
m._state['status']='done'
print('PASS active AI installation prevents desktop close; mocked contracts only, Windows/model testing pending')

with patch.object(m,'warmup',side_effect=[RuntimeError('Connection timeout downloading cached model'),None]) as warm,patch.object(m.time,'sleep'):
    m.warmup_with_retry('chatterbox',['docker','compose']);assert warm.call_count==2
for error in ['CUDA out of memory','HTTP 403 forbidden','weights shape mismatch']:
    with patch.object(m,'warmup',side_effect=RuntimeError(error)) as warm:
        try:m.warmup_with_retry('chatterbox',['docker','compose'])
        except RuntimeError as exc:assert str(exc)==error
        else:raise AssertionError('Non-transient failure should remain visible')
        assert warm.call_count==1
print('PASS one transient retry; memory, permissions and model errors retain exact cause without repeat')

# The owner's frozen Windows log recorded a charmap failure while printing
# Docker download progress. Persist Unicode losslessly and print safely.
import io
encoded_output=io.BytesIO()
legacy_console=io.TextIOWrapper(encoded_output,encoding='cp1252',errors='strict')
with patch.object(m.sys,'stdout',legacy_console):
    m.report('Downloading ███ voice نموذج')
assert m.state()['log'][-1]=='Downloading ███ voice نموذج'
assert b'Downloading' in encoded_output.getvalue()
print('PASS Unicode download output cannot abort setup on a legacy Windows console')
with patch.object(m,'session') as session,patch.object(m,'health',return_value={'service':'chatterbox','model_ready':False}):
    session.return_value.__enter__.return_value.post.return_value.status_code=404
    try:m.warmup('chatterbox',['docker','compose'])
    except RuntimeError as error:
        assert 'Stop the older engine' in str(error) and 'port 8881' in str(error)
    else:raise AssertionError('An incompatible engine must not be reported ready')
print('PASS incompatible older engine gives a recovery action and cannot be reported ready')

# 0.9.4-beta.3: the Windows installer only queues the chosen tools; the app installs them on start.
import json
pending=Path(temp.name)/'ai-setup-pending.json'
pending.write_text(json.dumps({'components':['whisper','kokoro','not-real'],'gpu':True,'accepted_terms':True}))
m._state['status']='idle'
with patch.object(m,'install') as inst,patch.object(m.threading,'Thread',side_effect=lambda target,args,daemon:SimpleNamespace(start=lambda:target(*args))):
    assert m.start_pending_setup() is True
    inst.assert_called_once_with(['whisper','kokoro'],True)
assert not pending.exists() and m.start_pending_setup() is False
pending.write_text(json.dumps({'components':['whisper'],'accepted_terms':False}))
with patch.object(m,'install') as inst:
    assert m.start_pending_setup() is False;inst.assert_not_called()
import subprocess as _sp
ws=Path(temp.name)/'queued';r=_sp.run([sys.executable,str(root/'backend/desktop_entry.py'),'--queue-local-ai','whisper,kokoro,chatterbox',str(ws),'1'],capture_output=True,text=True)
assert r.returncode==0,r.stderr
assert json.loads((ws/'ai-setup-pending.json').read_text())=={'components':['whisper','kokoro','chatterbox'],'gpu':True,'accepted_terms':True}
print('PASS installer choices are queued quickly and installed by the app on first start; unknown tools and unaccepted terms are ignored')

# 0.9.4-beta.4: the NVIDIA option is saved, and switching it changes the installed PyTorch build.
with TestClient(app) as client:
    before=client.get('/api/local-ai/setup').json()['settings']
    saved=client.put('/api/local-ai/startup',json={'gpu':True}).json()
    after=client.get('/api/local-ai/setup').json()
    assert saved['gpu'] is True and after['settings']['gpu'] is True and after['settings'].get('autostart')==before.get('autostart')
    assert client.put('/api/local-ai/startup',json={'autostart':False}).json()['gpu'] is True
    assert client.put('/api/local-ai/startup',json={'gpu':False}).json()['gpu'] is False
print('PASS the NVIDIA graphics card option stays ticked after saving (and other options are kept)')
from app import native_engines as ne
engines=Path(temp.name)/'engines-gpu'
with patch.dict(os.environ,{'SCENEFORGE_NATIVE_ENGINES':str(engines)}),patch.object(ne,'ensure_uv',return_value=Path('uv')),patch.object(ne.shutil,'copy2'):
    py=ne.venv_python('chatterbox');py.parent.mkdir(parents=True);py.write_text('')
    (engines/'chatterbox'/'installed.json').write_text(json.dumps({'gpu':False}))
    assert ne.build('chatterbox')=='cpu'
    calls=[];ne.install('chatterbox',gpu=True,run=lambda a,e:calls.append(a),report=lambda *a,**k:None)
    torch_call=next(c for c in calls if 'torch==2.6.0' in c)
    assert '--reinstall-package' in torch_call and 'https://download.pytorch.org/whl/cu124' in torch_call,torch_call
    assert ne.build('chatterbox')=='gpu'
    calls=[];ne.install('chatterbox',gpu=True,run=lambda a,e:calls.append(a),report=lambda *a,**k:None)
    assert '--reinstall-package' not in next(c for c in calls if 'torch==2.6.0' in c)
    (engines/'chatterbox'/'installed.json').write_text(json.dumps({'gpu':False}))
    with patch.object(ne.subprocess,'Popen') as popen,patch.object(ne,'_service_source',return_value=engines):
        ne._processes.clear();assert ne.start('chatterbox',gpu=True)
        assert popen.call_args.kwargs['env']['CHATTERBOX_DEVICE']=='cpu'
    ne._processes.clear()
    with patch.object(m,'health',return_value=None),patch.object(m,'image_ready',return_value=False):
        st=m.state();assert st['builds']=={'chatterbox':'cpu'} and isinstance(st['nvidia'],bool)
print('PASS switching to the graphics card reinstalls PyTorch with the NVIDIA build; a CPU build never starts on the GPU')
