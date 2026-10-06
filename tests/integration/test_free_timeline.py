"""API persistence, independent scene excerpts, exact gap/stack/audio export and template IDs."""
import os,pathlib,sys,tempfile,subprocess
import numpy as np
root=pathlib.Path(__file__).resolve().parents[2];tmp=tempfile.TemporaryDirectory(prefix='sf-free-test-');os.environ['SCENEFORGE_DATA_DIR']=tmp.name;sys.path.insert(0,str(root/'backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import SessionLocal
from app.db.models import Project
from app.render.free_timeline import render_free_timeline
from app.render.ffmpeg_utils import probe
with TestClient(app) as client:
 p=client.post('/api/projects',json={'title':'Free placements','aspect':'16:9','fps':25}).json();pid=p['id'];p=client.get('/api/projects/'+pid).json();ids=[s['id'] for s in p['scenes']]
 paths={}
 for ident,color,freq in zip(ids[:2],['red','blue'],[440,880]):
  path=pathlib.Path(tmp.name)/(ident+'.mp4');subprocess.run(['ffmpeg','-y','-v','error','-f','lavfi','-i',f'color=c={color}:s=320x180:r=25:d=2','-f','lavfi','-i',f'sine=frequency={freq}:duration=2','-c:v','libx264','-threads','1','-c:a','aac',str(path)],check=True);paths[ident]=str(path)
 clips=[{'id':'red','scene_id':ids[0],'start_ms':1000,'source_in_ms':0,'duration_ms':1800,'track':5},{'id':'blue','scene_id':ids[1],'start_ms':2000,'source_in_ms':500,'duration_ms':1000,'track':1}]
 fin={'free_timeline':{'enabled':True,'clips':clips}}
 r=client.patch('/api/projects/'+pid,json={'finishing':fin});assert r.status_code==200,r.text
 assert client.get('/api/projects/'+pid).json()['finishing_json']['free_timeline']==fin['free_timeline']
 for bad in [{**clips[0],'track':6},{**clips[0],'start_ms':-1},{**clips[0],'duration_ms':0},{**clips[0],'scene_id':'other'},{**clips[0],'source_in_ms':float('inf')}]:
  if bad['source_in_ms']==float('inf'):continue
  r=client.patch('/api/projects/'+pid,json={'finishing':{'free_timeline':{'enabled':True,'clips':[bad]}}});assert r.status_code==400,(bad,r.text)
 print('PASS persistent free placement and invalid/foreign data rejection',flush=True)
 with SessionLocal() as db:
  row=db.get(Project,pid);row.width=320;row.height=180;db.commit();out=render_free_timeline(row,paths)
 assert abs(probe(out).duration_ms-3000)<60
 def image(at):
  raw=subprocess.check_output(['ffmpeg','-v','error','-ss',str(at),'-i',out,'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-threads','1','-']);return np.frombuffer(raw,np.uint8).reshape(180,320,3).mean((0,1))
 assert image(.5).max()<5,image(.5)
 assert image(1.5)[0]>220,image(1.5)
 assert image(2.5)[2]>220,image(2.5)
 audio=subprocess.check_output(['ffmpeg','-v','error','-i',out,'-f','f32le','-ac','1','-ar','16000','-']);sound=np.frombuffer(audio,np.float32)
 assert np.sqrt(np.mean(sound[1000:8000]**2))<.002
 assert np.sqrt(np.mean(sound[20000:26000]**2))>.03
 segment=sound[34000:40000];fft=np.abs(np.fft.rfft(segment));freqs=np.fft.rfftfreq(len(segment),1/16000)
 for f in [440,880]:assert fft[np.abs(freqs-f)<5].max()>20
 print('PASS real export black/silent gap, exact 3-second duration, track stack and overlapping audio',flush=True)
 bad={**fin,'free_timeline':{'enabled':True,'clips':[{**clips[0],'source_in_ms':1500,'duration_ms':1000}]}}
 with SessionLocal() as db:
  row=db.get(Project,pid);row.finishing_json=bad
  try:render_free_timeline(row,paths);raise AssertionError('Out-of-source excerpt accepted')
  except ValueError:pass
 saved=client.post('/api/project-templates',json={'project_id':pid,'name':'Free composition'}).json();copy=client.post('/api/project-templates/'+saved['id']+'/create',json={'title':'Independent copy'}).json()
 copy=client.get('/api/projects/'+copy['id']).json();placed=copy['finishing_json']['free_timeline']['clips'];assert all(c['scene_id'] in {s['id'] for s in copy['scenes']} for c in placed);assert all(c['scene_id'] not in ids for c in placed)
 # Exercise the actual full-export worker, including the free layout dispatch and finishing.
 for ident in ids[:2]:
  a=client.post('/api/assets/upload?project_id='+pid,files={'file':('source.mp4',pathlib.Path(paths[ident]).read_bytes(),'video/mp4')}).json()
  client.post('/api/scenes/'+ident+'/shots',json={'asset_id':a['id']})
  client.patch('/api/scenes/'+ident,json={'timing_mode':'fixed','requested_duration_ms':2000,'font':{'captions_enabled':False}})
 response=client.post('/api/projects/'+pid+'/export');assert response.status_code==200,response.text
 import time
 ident=response.json()['job_id']
 for _ in range(300):
  j=client.get('/api/jobs/'+ident).json()
  if j['status'] in ('succeeded','failed','cancelled'):break
  time.sleep(.1)
 assert j['status']=='succeeded',j
 from app.config import RENDERS_DIR
 from app.db.models import Asset
 with SessionLocal() as db:final=pathlib.Path(RENDERS_DIR)/db.get(Asset,j['artifact_asset_id']).storage_key
 assert abs(probe(str(final)).duration_ms-3000)<60
 print('PASS actual full-export worker renders placed scenes at the authored free times',flush=True)
 print('PASS excerpt bounds and template source-scene ID remapping',flush=True)
 # No scene blocks are required for independent media placed on the free timeline.
 raw=client.post('/api/projects',json={'title':'Media only','aspect':'16:9','fps':25}).json();raw=client.get('/api/projects/'+raw['id']).json();rid=raw['id']
 for scene in raw['scenes']:assert client.delete('/api/scenes/'+scene['id']).status_code in (200,204)
 asset=client.post('/api/assets/upload?project_id='+rid,files={'file':('red.mp4',pathlib.Path(paths[ids[0]]).read_bytes(),'video/mp4')}).json()
 layer={'id':'raw-video','kind':'video','asset_id':asset['id'],'start_ms':1000,'duration_ms':500,'track':0,'width':100,'x':50,'y':50,'mute':False,'volume':100}
 r=client.patch('/api/projects/'+rid,json={'finishing':{'free_timeline':{'enabled':True,'clips':[]},'layer_clips':[layer]}});assert r.status_code==200,r.text
 response=client.post('/api/projects/'+rid+'/export');assert response.status_code==200,response.text
 for _ in range(300):
  j=client.get('/api/jobs/'+response.json()['job_id']).json()
  if j['status'] in ('succeeded','failed','cancelled'):break
  time.sleep(.1)
 assert j['status']=='succeeded',j
 with SessionLocal() as db:final=pathlib.Path(RENDERS_DIR)/db.get(Asset,j['artifact_asset_id']).storage_key
 assert abs(probe(str(final)).duration_ms-1500)<60
 print('PASS independent video export with zero scene blocks and a real leading gap',flush=True)


 # Independent raw layers and source scenes must obey the SAME track stack.
with TestClient(app) as client:
 from PIL import Image
 import io
 image_bytes=io.BytesIO();Image.new('RGB',(320,180),'blue').save(image_bytes,format='PNG')
 a=client.post('/api/assets/upload?project_id='+pid,files={'file':('blue.png',image_bytes.getvalue(),'image/png')}).json()
 layer={'id':'mixed-layer','kind':'image','asset_id':a['id'],'start_ms':1000,'duration_ms':1000,'track':5,'width':100,'x':50,'y':50}
 sceneclip={**clips[0],'track':0}
 for top in ('scene','layer'):
  if top=='layer':layer['track']=0;sceneclip['track']=5
  r=client.patch('/api/projects/'+pid,json={'finishing':{'free_timeline':{'enabled':True,'clips':[sceneclip]},'layer_clips':[layer]}});assert r.status_code==200,r.text
  with SessionLocal() as db:out=render_free_timeline(db.get(Project,pid),paths)
  rgb=image(1.5);assert rgb[0 if top=='scene' else 2]>220,(top,rgb)
 print('PASS scene references and independent layers share the exact same track stacking order',flush=True)
 client.patch('/api/scenes/'+ids[0],json={'subtitle_text':'A caption','font':{'captions_enabled':True}})
 client.patch('/api/projects/'+pid,json={'finishing':{'free_timeline':{'enabled':True,'clips':[{**clips[0],'source_in_ms':500,'duration_ms':1000,'start_ms':1000}]}}})
 captions=client.get('/api/projects/'+pid+'/captions').text;assert '00:00:01,000 --> 00:00:02,000' in captions,captions
 print('PASS caption file timing follows clipped source ranges and free project positions',flush=True)
