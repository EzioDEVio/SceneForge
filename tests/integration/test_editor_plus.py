"""New provider contracts and deletion safeguards. No hosted account is charged."""
import base64, io, os, pathlib, sys, tempfile
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image
ROOT=pathlib.Path(__file__).resolve().parents[2]
tmp=tempfile.TemporaryDirectory();os.environ['SCENEFORGE_DATA_DIR']=tmp.name
sys.path.insert(0,str(ROOT/'backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import SessionLocal
from app.db.models import RenderJob
from app.providers.image_options import generate, local_url
from app.providers.openai_image import ImageProviderError
n=0
def check(name,ok):
 global n
 assert ok,name
 n+=1;print('PASS '+name,flush=True)
buf=io.BytesIO();Image.new('RGB',(64,64),'red').save(buf,'JPEG');jpg=buf.getvalue()
def response(data,code=200):return SimpleNamespace(ok=code==200,is_redirect=False,status_code=code,json=lambda:data)
with TestClient(app) as client:
 p=client.post('/api/projects',json={'title':'Delete check'}).json()
 scene=client.get('/api/projects/'+p['id']).json()['scenes'][0]['id']
 cf=client.post('/api/providers',json={'capability':'image','name':'cloudflare','api_key':'test-secret','base_url':'a'*32}).json()
 with patch('app.providers.image_options.requests.post',return_value=response({'result':{'image':base64.b64encode(jpg).decode()}})) as post:
  r=client.post(f'/api/scenes/{scene}/generate-image',json={'prompt':'red scene','provider_id':cf['id']})
  check('Cloudflare JPEG persists with correct MIME and extension',r.status_code==200 and r.json()['mime']=='image/jpeg' and r.json()['original_filename'].endswith('.jpg'))
  check('Cloudflare token is a header and account endpoint is fixed',post.call_args.kwargs['headers']['Authorization']=='Bearer test-secret' and post.call_args.args[0].startswith('https://api.cloudflare.com/'))
  check('Unsupported Cloudflare dimensions are not sent', 'width' not in post.call_args.kwargs['json'])
 with patch('app.providers.image_options.requests.post',return_value=response({},429)):
  r=client.post(f'/api/scenes/{scene}/generate-image',json={'prompt':'red scene','provider_id':cf['id']})
  check('Quota failure is actionable without leaking token',r.status_code==502 and 'limit' in r.text and 'test-secret' not in r.text)
 r=client.post('/api/providers',json={'capability':'image','name':'local_sd','api_key':'','base_url':'http://127.0.0.1:7860','model':'current'})
 check('Local provider saves without API key',r.status_code==200)
 local=r.json()
 with patch('app.providers.image_options.requests.Session') as sess:
  sess.return_value.post.return_value=response({'images':[base64.b64encode(jpg).decode()]})
  r=client.post(f'/api/scenes/{scene}/generate-image',json={'prompt':'a garden','provider_id':local['id'],'size':'1536x1024'})
  check('Local image routing uses requested composition',r.status_code==200 and sess.return_value.post.call_args.kwargs['json']['width']==1536)
  check('Local connection bypasses corporate proxies',sess.return_value.trust_env is False)
 r=client.post('/api/providers',json={'capability':'image','name':'local_sd','api_key':'','base_url':'https://example.com'})
 check('Local engine cannot silently route to a remote host',r.status_code==400)
 with patch('huggingface_hub.InferenceClient') as hf:
  hf.return_value.text_to_image.return_value=Image.new('RGB',(64,64))
  data=generate(SimpleNamespace(name='huggingface',model='test/image'), 'hf_fixture','test','1024x1024')
  check('HF SDK routes requested model and returns PNG',data.startswith(b'\x89PNG') and hf.return_value.text_to_image.call_args.kwargs['model']=='test/image')
 with SessionLocal() as db:
  job=RenderJob(project_id=p['id'],scene_id=scene,scope='part',status='running');db.add(job);db.commit();jid=job.id
 check('Cannot delete project during an active render',client.delete('/api/projects/'+p['id']).status_code==409)
 with SessionLocal() as db:
  db.get(RenderJob,jid).status='succeeded';db.commit()
 check('Can delete project after render completes',client.delete('/api/projects/'+p['id']).status_code==200)
 check('Deleting project preserves provider settings',len(client.get('/api/providers').json())==2)
 check('Missing project reports 404',client.delete('/api/projects/'+p['id']).status_code==404)
print(f'{n} editor-plus checks passed')
