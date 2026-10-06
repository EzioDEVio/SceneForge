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
    assert client.get('/api/local-ai/setup').json()['supported'] is False
    assert client.post('/api/local-ai/setup',json={'components':['whisper'],'accept_terms':True}).status_code==400
print('PASS unknown components and unsupported platform rejected before installation')
with patch.object(m,'os',fakeos),patch.object(m,'engine_root',return_value=Path(temp.name)),patch.object(m.shutil,'disk_usage',return_value=SimpleNamespace(free=20_000_000_000)),patch('app.providers.transcribe._load_local_model',return_value=object()),patch.object(m,'ensure_docker',return_value='docker.exe'),patch.object(m,'compose',return_value=['docker.exe','compose','-p','sceneforge-managed-ai']),patch.object(m,'run') as commands,patch.object(m,'image_ready',return_value=False),patch.object(m,'warmup') as warm,patch('socket.create_connection',side_effect=OSError),patch.object(m,'health',side_effect=[{'service':'stable_diffusion','model_ready':True},{'service':'stable_diffusion','model_ready':True},{'service':'chatterbox','model_ready':False},{'service':'chatterbox','model_ready':True},{'service':'chatterbox','model_ready':True}]):
    assert m.install(['whisper','stable_diffusion','chatterbox'])
    assert m.state()['completed']==3 and m.state()['status']=='done'
    assert commands.call_count==2 and warm.call_count==2
    for call in commands.call_args_list:assert '--build' in call.args[0]
with SessionLocal() as db:
    assert {p.name for p in db.query(ProviderProfile)}=={'local_sd','chatterbox'}
    p=db.query(ProviderProfile).filter_by(name='local_sd').one();p.base_url='http://127.0.0.1:9999';db.commit()
m.register('stable_diffusion')
with SessionLocal() as db:assert db.query(ProviderProfile).filter_by(name='local_sd').one().base_url.endswith(':9999')
print('PASS ordered installation, actual stage completion, model checks, profile registration and existing connection preservation')
with patch.object(m,'os',fakeos),patch.object(m,'engine_root',return_value=Path(temp.name)),patch.object(m.shutil,'disk_usage',return_value=SimpleNamespace(free=0)),patch.object(m,'run') as commands:
    assert not m.install(['whisper']);assert 'free space' in m.state()['error'];commands.assert_not_called()
with patch.object(m,'os',fakeos),patch.object(m,'engine_root',return_value=Path(temp.name)),patch.object(m.shutil,'disk_usage',return_value=SimpleNamespace(free=20_000_000_000)),patch.object(m,'image_ready',return_value=False),patch('socket.create_connection',return_value=MagicMock()),patch.object(m,'health',return_value=None),patch.object(m,'ensure_docker') as docker:
    assert not m.install(['stable_diffusion']);assert 'another service' in m.state()['error'];docker.assert_not_called()
print('PASS insufficient space and occupied ports fail clearly without installing or replacing services')
with patch.object(m,'os',fakeos),patch.object(m,'engine_root',return_value=Path(temp.name)),patch.object(m.shutil,'disk_usage',return_value=SimpleNamespace(free=20_000_000_000)),patch('app.providers.transcribe._load_local_model',return_value=object()):
    assert m.install(['whisper']);assert m.state()['status']=='done'
    assert {'whisper','stable_diffusion','chatterbox'}==set(m.preferences()['components'])
m.save_preferences({**m.preferences(),'autostart':False})
with patch.object(m,'os',fakeos),patch.object(m,'docker_path') as docker:
    m.autostart();docker.assert_not_called()
with patch.object(m,'os',fakeos),patch.object(m,'docker_path',return_value='docker.exe'),patch.object(m,'docker_ready',return_value=True),patch.object(m,'compose',return_value=['docker.exe','compose']),patch.object(m,'run') as commands,patch.object(m,'health',return_value={'model_ready':True}),patch.object(m,'session') as session:
    m.autostart(force=True,services=['stable_diffusion'])
    args=commands.call_args.args[0];assert 'start' in args and '--build' not in args and 'install' not in args
print('PASS Retry preserves installed components, startup choice is honored, manual start never builds or installs')
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
