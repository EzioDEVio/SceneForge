"""Regression for the owner's Windows _imagingft failure; no network/provider calls."""
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
tmp = tempfile.TemporaryDirectory(prefix='sf-font-runtime-')
os.environ['SCENEFORGE_DATA_DIR'] = tmp.name
sys.path.insert(0, str(ROOT / 'backend'))
from fastapi.testclient import TestClient
from PIL import Image, ImageFont
from app.main import app
from app.render.font_runtime import check_font_runtime, load_font, FontRuntimeError
from app.render.textured_text import FONTS, _font_path

spec = importlib.util.spec_from_file_location('windows_runtime', ROOT / 'scripts/windows_runtime.py')
launcher = importlib.util.module_from_spec(spec); spec.loader.exec_module(launcher)
a = launcher.runtime_dir(ROOT, 'C:/Users/test/AppData/Local')
b = launcher.runtime_dir(ROOT.parent / 'other', 'C:/Users/test/AppData/Local')
assert a != b and len(a.name) == 12 and 'runtimes' in a.parts
with patch.object(launcher, 'os', __import__('types').SimpleNamespace(name='nt')), patch.object(launcher, 'runtime_dir', return_value=Path(tmp.name)), patch.object(launcher.subprocess, 'run', side_effect=__import__('subprocess').CalledProcessError(1, ['preflight'])), patch.object(launcher.subprocess, 'call') as serve, patch.object(launcher.subprocess, 'Popen') as voice, patch.object(sys, 'argv', ['windows_runtime.py','setup']):
    assert launcher.main() == 1
    serve.assert_not_called(); voice.assert_not_called()
runtime=Path(tmp.name)/'runtime'
(runtime/'Scripts').mkdir(parents=True)
(runtime/'Scripts/python.exe').touch()
for action in ['setup','start','dev']:
    with patch.object(launcher, 'os', __import__('types').SimpleNamespace(name='nt')), patch.object(launcher, 'runtime_dir', return_value=runtime), patch.object(launcher.subprocess, 'run') as run, patch.object(launcher.subprocess, 'call', return_value=0) as serve, patch.object(launcher.subprocess, 'Popen') as voice, patch.object(sys, 'argv', ['windows_runtime.py',action]):
        assert launcher.main()==0
        assert run.call_args.kwargs['cwd']==ROOT/'backend'
        assert run.call_args.args[0][0]==str(runtime/'Scripts/python.exe')
        if action=='setup':
            assert run.call_count==3
            serve.assert_not_called();voice.assert_not_called()
        else:
            assert serve.call_args.kwargs['cwd']==ROOT/'backend'
            assert ('--reload' in serve.call_args.args[0]) == (action=='dev')
            assert voice.call_count==(1 if action=='start' else 0)
print('PASS per-copy short runtime, checked setup/start/dev commands and failed preflight blocks startup', flush=True)

check_font_runtime()
# Open font files as bytes, including a deep path and a non-ASCII filename.
path = Path(tmp.name) / ('deep-folder-' * 10) / ('nested-' * 20) / 'خط.ttf'
path.parent.mkdir(parents=True)
path.write_bytes(_font_path('Noto Sans', False).read_bytes())
assert load_font(path, 32).getbbox('Visible')[2] > 0
print('PASS real Latin/Arabic preflight and deep Unicode font path', flush=True)

with TestClient(app, raise_server_exceptions=False) as client:
    p = client.post('/api/projects', json={'title':'Runtime rollback'}).json()
    pid = p['id']; sid = client.get('/api/projects/'+pid).json()['scenes'][0]['id']
    original = client.get('/api/scenes/'+sid).json()
    for error in [ImportError('DLL load failed while importing _imagingft: The filename or extension is too long.'), OSError('cannot open resource')]:
        with patch.object(ImageFont, 'truetype', side_effect=error):
            for suffix, body in [('knockout-title',{'text':'MATRIX'}), ('textured-title',{'text':'MATRIX','texture':{'preset':'gold'}})]:
                r = client.post(f'/api/scenes/{sid}/{suffix}', json=body)
                assert r.status_code == 503, r.text
                assert 'scripts/setup.bat' in r.json()['detail']
            for kind in ['text','text_box','text_plus']:
                r = client.get('/api/projects/'+pid+'/layer-preview', params={'style':json.dumps({'id':'test','kind':kind,'text':'Your title'})})
                assert r.status_code == 503, r.text
            assert client.get('/api/scenes/'+sid).json() == original
            assert client.get('/api/health').status_code == 200
    print('PASS DLL/missing-font failures return recovery instructions, no saved mutation, server remains healthy', flush=True)
    for repeat in range(3):
        for family in FONTS:
            for kind in ['text','text_box','text_plus']:
                r = client.get('/api/projects/'+pid+'/layer-preview', params={'style':json.dumps({'id':'test','kind':kind,'family':family,'text':f'مرحبا SceneForge {repeat}'})})
                assert r.status_code == 200, r.text
                image = Image.open(io.BytesIO(r.content))
                assert image.mode == 'RGBA' and image.getbbox() is not None
    for family in FONTS:
        assert _font_path(family, False).is_file()
        r = client.get('/api/projects/'+pid+'/layer-preview',params={'style':json.dumps({'id':'latin','kind':'text','family':family,'text':'Heading 1969'})})
        assert r.status_code==200,r.text
        assert Image.open(io.BytesIO(r.content)).getbbox() is not None
    for suffix, body in [('knockout-title',{'text':'MATRIX'}), ('textured-title',{'text':'مرحبا','texture':{'preset':'gold'}})]:
        r = client.post(f'/api/scenes/{sid}/{suffix}', json=body)
        assert r.status_code == 200, r.text
    assert len(client.get('/api/scenes/'+sid).json()['overlays_json']) == 2
    print(f'PASS recovery without restart, {len(FONTS)*10} real text previews, both title APIs', flush=True)
