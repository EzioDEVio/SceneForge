"""Route and format regression checks without paid provider calls."""
import base64, io, os, pathlib, sys, tempfile
from types import SimpleNamespace
from unittest.mock import patch
root=pathlib.Path(__file__).resolve().parents[2]
tmp=tempfile.TemporaryDirectory();os.environ['SCENEFORGE_DATA_DIR']=tmp.name;os.environ['SCENEFORGE_SD_AUTOSTART']='0'
sys.path.insert(0,str(root/'backend'))
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import SessionLocal,engine
from app.db.models import ProviderProfile
from app.providers import image_options,speech_http
buf=io.BytesIO();Image.new('RGB',(32,32),'green').save(buf,format='PNG');png=buf.getvalue()
with TestClient(app) as c:
    project=c.post('/api/projects',json={'title':'Hosted adapters'}).json()
    sid=c.get('/api/projects/'+project['id']).json()['scenes'][0]['id']
    with SessionLocal() as db:
        p=ProviderProfile(name='together',capability='image',model='fixture-model',secret_ref='');db.add(p);db.commit();pid=p.id
    with patch.object(image_options.requests,'post') as post,patch.object(image_options,'local_url',side_effect=AssertionError('Hosted request routed locally')):
        post.return_value=SimpleNamespace(ok=True,is_redirect=False,json=lambda:{'data':[{'b64_json':base64.b64encode(png).decode()}]})
        r=c.post('/api/scenes/'+sid+'/generate-image',json={'provider_id':pid,'prompt':'fixture','size':'1024x1024'})
        assert r.status_code==200,r.text
        assert post.call_args.args[0]=='https://api.together.xyz/v1/images/generations'
        assert post.call_count==1
    profile=SimpleNamespace(name='elevenlabs',base_url='https://untrusted.example',secret_ref='',model='eleven_multilingual_v2')
    with patch.object(speech_http.requests,'post') as post:
        post.return_value=SimpleNamespace(ok=True,content=b'fixture-mp3')
        assert speech_http.synthesize(profile,'Hello','Voice123','en',1)==b'fixture-mp3'
        assert post.call_args.args[0].startswith('https://api.elevenlabs.io/')
        assert post.call_args.kwargs['params']['output_format']=='mp3_44100_128'
        assert post.call_args.kwargs['allow_redirects'] is False
        try:speech_http.synthesize(profile,'Hello','../escape','en',1)
        except ValueError:pass
        else:raise AssertionError('Invalid voice accepted')
engine.dispose();tmp.cleanup()
print('PASS Together API route, no local fallback, ElevenLabs fixed host, format and voice validation')
