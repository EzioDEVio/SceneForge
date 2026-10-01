"""Subject cutout (beta): real u2netp model, cutout asset, and "text behind subject" render order.

Downloads u2netp (4.6 MB) from GitHub releases on first run into SCENEFORGE_CUTOUT_MODEL_DIR
(or a temp folder). Skips with a message only when github.com is unreachable."""
import os,pathlib,sys,tempfile,subprocess,time
import numpy as np
from PIL import Image,ImageDraw
root=pathlib.Path(__file__).resolve().parents[2]
tmp=tempfile.TemporaryDirectory();os.environ['SCENEFORGE_DATA_DIR']=tmp.name
t=pathlib.Path(tmp.name)
os.environ.setdefault('SCENEFORGE_CUTOUT_MODEL_DIR',str(t/'models'))
sys.path.insert(0,str(root/'backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.render import cutout
n=0
def check(name,ok):
 global n
 assert ok,name
 n+=1;print('PASS '+name,flush=True)

try:
 cutout.ensure_model('u2netp')
except cutout.CutoutError as e:
 import requests
 try:requests.head('https://github.com',timeout=10);reachable=True
 except Exception:reachable=False
 if not reachable:
  print(f'SKIP test_cutout: github.com is unreachable, so the u2netp model cannot be downloaded ({e})');sys.exit(0)
 raise
check('u2netp model is present after first use (atomic download, no .partial left)',cutout.model_path('u2netp').stat().st_size>1_000_000 and not list(cutout.model_dir().glob('*.partial')))

client=TestClient(app).__enter__()
st=client.get('/api/cutout/status').json()
check('status reports the models folder and which models are downloaded',st['folder']==str(cutout.model_dir()) and next(m for m in st['models'] if m['id']=='u2netp')['downloaded'] and st['default']=='isnet')

# A person-like subject: head + torso on a contrasting flat background.
im=Image.new('RGB',(640,480),(30,110,50));d=ImageDraw.Draw(im)
d.ellipse([260,70,380,190],fill=(235,190,150));d.rounded_rectangle([220,180,420,480],50,fill=(200,40,60))
im.save(t/'person.png')
ff=lambda *a:subprocess.run(['ffmpeg','-v','error','-y',*a],check=True,capture_output=True)
ff('-f','lavfi','-i','color=c=0x405060:s=320x180:d=1:r=30','-pix_fmt','yuv420p',str(t/'clip.mp4'))
p=client.post('/api/projects',json={'title':'Cutout','aspect':'16:9'}).json();pid=p['id']
up=lambda f:client.post('/api/assets/upload',params={'project_id':pid},files={'file':(f,open(t/f,'rb'))}).json()
person,clip=up('person.png'),up('clip.mp4')

# Download failure gives a clear message (folder + github.com) and leaves no partial file.
saved_dir,saved_url=os.environ['SCENEFORGE_CUTOUT_MODEL_DIR'],cutout.MODELS['isnet']['url']
os.environ['SCENEFORGE_CUTOUT_MODEL_DIR']=str(t/'empty-models');cutout.MODELS['isnet']['url']='http://127.0.0.1:9/isnet-general-use.onnx'
r=client.post(f"/api/assets/{person['id']}/cutout",json={'model':'isnet'})
check('offline download fails with a clear message naming github.com and the folder',r.status_code==503 and 'github.com' in r.json()['detail'] and str(t/'empty-models') in r.json()['detail'])
check('failed download leaves no partial or model file',not list((t/'empty-models').glob('*')))
os.environ['SCENEFORGE_CUTOUT_MODEL_DIR']=saved_dir;cutout.MODELS['isnet']['url']=saved_url

check('unknown model is rejected',client.post(f"/api/assets/{person['id']}/cutout",json={'model':'sam'}).status_code==422)
check('videos are rejected with a clear message',client.post(f"/api/assets/{clip['id']}/cutout",json={'model':'u2netp'}).status_code==400)
r=client.post(f"/api/assets/{person['id']}/cutout",json={'model':'u2netp'})
check('cutout creates a new image asset',r.status_code==200 and r.json()['id']!=person['id'] and r.json()['type']=='image' and '(cutout)' in r.json()['original_filename'])
cut=r.json()
png=Image.open(__import__('io').BytesIO(client.get(f"/api/assets/{cut['id']}/stream").content))
a=np.asarray(png.convert('RGBA'))[...,3].astype(int)
check('cutout PNG has an alpha channel at source size',png.mode=='RGBA' and png.size==(640,480))
check('subject centre is opaque',a[260:400,260:380].mean()>200 and a[100:160,290:350].mean()>200)
check('background corners are transparent',max(a[:60,:60].mean(),a[:60,-60:].mean(),a[-60:,:60].mean(),a[-60:,-60:].mean())<30)
check('original image is kept',client.get(f"/api/assets/{person['id']}").status_code==200)
check('repeating the cutout reuses the cached asset',client.post(f"/api/assets/{person['id']}/cutout",json={'model':'u2netp'}).json()['id']==cut['id'])
check('cutout appears in the Media Pool',any(x['id']==cut['id'] for x in client.get('/api/assets',params={'project_id':pid}).json()))

# --- text behind subject ---------------------------------------------------------------
sid=client.get(f'/api/projects/{pid}').json()['scenes'][0]['id']
check('subject layer needs media',client.post(f'/api/scenes/{sid}/subject-layer',json={'model':'u2netp'}).status_code==400)
vshot=client.post(f'/api/scenes/{sid}/shots',json={'asset_id':clip['id']}).json()
r=client.post(f'/api/scenes/{sid}/subject-layer',json={'model':'u2netp'})
check('subject layer rejects video with a clear message',r.status_code==400 and 'still image' in r.json()['detail'])
client.delete(f"/api/scenes/shots/{vshot['id']}")
shot=client.post(f'/api/scenes/{sid}/shots',json={'asset_id':person['id']}).json()
client.patch(f"/api/scenes/shots/{shot['id']}",json={'motion':{'type':'zoom_in'}})
r=client.post(f'/api/scenes/{sid}/subject-layer',json={'model':'u2netp'})
check('subject layer rejects camera movement (static cutout would drift)',r.status_code==400 and 'Static' in r.json()['detail'])
client.patch(f"/api/scenes/shots/{shot['id']}",json={'motion':{'type':'static'}})
client.patch(f'/api/scenes/{sid}',json={'timing_mode':'fixed','requested_duration_ms':1000,
  'font':{'captions_enabled':False,'layers':[{'id':'t1','kind':'text','text':'HHHHHHHHHHHHHHHHHHHHHHHH','family':'Anton','size':200,'color':'#FFFF00','x':50,'y':50,'box_width':100,'animation':'none'}]}})
def render():
 j=client.post(f'/api/scenes/{sid}/render').json()
 while (s:=client.get(f"/api/jobs/{j['job_id']}").json())['status'] not in('succeeded','failed','cancelled'):time.sleep(.2)
 assert s['status']=='succeeded',s
 aid=client.get(f'/api/projects/{pid}').json()['scenes'][0]['rendered_asset_id']
 path=t/f'r{time.time_ns()}.mp4';path.write_bytes(client.get(f'/api/assets/{aid}/stream').content)
 raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-vf','scale=640:360','-f','rawvideo','-pix_fmt','rgb24','-'])
 return np.frombuffer(raw,np.uint8).reshape(-1,360,640,3).astype(int)
yellow=lambda f:(f[...,0]>200)&(f[...,1]>200)&(f[...,2]<110)
# 640x480 source, cover-fitted to 16:9 and shown at 640x360: torso spans x 220..420, from y 120 down.
inside,outside=(slice(150,210),slice(250,390)),(slice(150,210),np.r_[20:190,450:620])
f=render()[15]
check('control: without a cutout the title is drawn over the subject',yellow(f[inside]).sum()>500 and yellow(f[150:210][:,outside[1]]).sum()>500)
r=client.post(f'/api/scenes/{sid}/subject-layer',json={'model':'u2netp'})
check('subject-layer adds a full-frame subject overlay above text',r.status_code==200 and r.json()['overlay']['kind']=='subject' and r.json()['overlay']['above_text'] is True and r.json()['overlay']['width']==100)
ovs=r.json()['scene']['overlays_json']
check('subject overlay is the top layer and the scene needs re-render',ovs[-1]['kind']=='subject' and r.json()['scene']['is_stale'])
r2=client.post(f'/api/scenes/{sid}/subject-layer',json={'model':'u2netp'})
check('running it again replaces the subject layer instead of stacking',r2.status_code==200 and sum(o['kind']=='subject' for o in r2.json()['scene']['overlays_json'])==1)
f=render()[15]
check('text stays visible outside the subject',yellow(f[150:210][:,outside[1]]).sum()>500)
check('subject renders above the text (no title pixels inside it)',yellow(f[inside]).sum()<40)
red=(f[...,0]>150)&(f[...,1]<90)&(f[...,2]<110)
check('subject pixels line up with the picture underneath',red[inside].mean()>0.9)
check('overlay patch keeps above_text and kind through validation',client.patch(f'/api/scenes/{sid}',json={'overlays':ovs}).json()['overlays_json'][-1]['above_text'] is True)
check('invalid above_text is rejected',client.patch(f'/api/scenes/{sid}',json={'overlays':[{**ovs[-1],'above_text':'yes'}]}).status_code==400)
print(f'{n} checks passed')
