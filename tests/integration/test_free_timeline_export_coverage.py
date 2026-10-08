"""Owner report 2026-10-07: only the text exported, not the video or captions.

Free timeline was switched on before a scene had its video, so that scene was never
placed on it; export silently used the free timeline. Also covers deleted-scene
excerpts and the browser-mode "open file location" action.
"""
import os,pathlib,sys,tempfile,subprocess,time
from unittest.mock import patch
import numpy as np
root=pathlib.Path(__file__).resolve().parents[2];tmp=tempfile.TemporaryDirectory(prefix='sf-free-cover-');os.environ['SCENEFORGE_DATA_DIR']=tmp.name;sys.path.insert(0,str(root/'backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.config import RENDERS_DIR
from app.db.database import SessionLocal
from app.db.models import Asset
def wait(client,job):
 for _ in range(1200):
  j=client.get('/api/jobs/'+job).json()
  if j['status'] in ('succeeded','failed','cancelled'):return j
  time.sleep(.1)
 raise AssertionError('job did not finish')
def frame(path,at,w,h):
 raw=subprocess.check_output(['ffmpeg','-v','error','-ss',str(at),'-i',str(path),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-']);return np.frombuffer(raw,np.uint8).reshape(h,w,3)
with TestClient(app) as client:
 pid=client.post('/api/projects',json={'title':'Owner free timeline','aspect':'16:9','fps':25}).json()['id']
 p=client.get('/api/projects/'+pid).json();ids=[s['id'] for s in p['scenes']]
 with SessionLocal() as db:
  from app.db.models import Project
  row=db.get(Project,pid);row.width=320;row.height=180;db.commit()
 # Owner's order: scene 1 had an image and Free timeline was opened (seeded with scene 1 only).
 img=client.post('/api/assets/upload?project_id='+pid,files={'file':('i.png',(root/'examples/fixture_assets/image1.png').read_bytes(),'image/png')}).json()
 client.post('/api/scenes/'+ids[0]+'/shots',json={'asset_id':img['id']})
 seeded={'enabled':True,'clips':[{'id':'s1','scene_id':ids[0],'start_ms':0,'source_in_ms':0,'duration_ms':2000,'track':5}]}
 assert client.patch('/api/projects/'+pid,json={'finishing':{'free_timeline':seeded}}).status_code==200
 # ...then scene 1 was deleted: its excerpt must go with it.
 assert client.delete('/api/scenes/'+ids[0]).status_code==200
 fin=client.get('/api/projects/'+pid).json()['finishing_json']
 assert fin['free_timeline']=={'enabled':True,'clips':[]},fin
 print('PASS deleting a scene removes its free-timeline excerpts',flush=True)
 # Projects saved before that fix still carry the dead excerpt; saving must not be blocked.
 with SessionLocal() as db:
  row=db.get(Project,pid);row.finishing_json={'free_timeline':seeded};db.commit()
 r=client.patch('/api/projects/'+pid,json={'finishing':{'free_timeline':seeded,'layer_clips':[]}});assert r.status_code==200,r.text
 assert r.json()['finishing_json']['free_timeline']['clips']==[]
 bad=client.patch('/api/projects/'+pid,json={'finishing':{'free_timeline':{'enabled':True,'clips':[{**seeded['clips'][0],'id':'new','scene_id':'never-existed'}]}}})
 assert bad.status_code==400,bad.text
 print('PASS old dead excerpts are dropped on save; unknown new scene ids are still rejected',flush=True)
 # Scene 2 now gets a video with a caption, plus a text overlay — as in the owner's screenshot.
 vid=pathlib.Path(tmp.name)/'v.mp4';subprocess.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','color=c=green:s=320x180:r=25:d=3','-f','lavfi','-i','sine=frequency=660:duration=3','-c:v','libx264','-c:a','aac','-shortest',str(vid)],check=True)
 a=client.post('/api/assets/upload?project_id='+pid,files={'file':('v.mp4',vid.read_bytes(),'video/mp4')}).json()
 client.post('/api/scenes/'+ids[1]+'/shots',json={'asset_id':a['id']})
 client.patch('/api/scenes/'+ids[1],json={'timing_mode':'fixed','requested_duration_ms':3000,'subtitle_text':'Every single child','font':{'captions_enabled':True}})
 text={'id':'title','kind':'text','text':'ALL ABOUT AUTISM','start_ms':500,'duration_ms':1000,'track':0,'x':50,'y':20,'width':60,'opacity':100,'rotation':0}
 r=client.patch('/api/projects/'+pid,json={'finishing':{'free_timeline':{'enabled':True,'clips':[]},'layer_clips':[text]}})
 if r.status_code!=200:
  # Fill any required text-layer fields the server reports, using its own defaults.
  raise AssertionError(r.text)
 # The editor now offers "Add to the end and export"; this is the clip it adds.
 add={'id':'added','scene_id':ids[1],'start_ms':0,'source_in_ms':0,'duration_ms':3000,'track':5}
 assert client.patch('/api/projects/'+pid,json={'finishing':{'free_timeline':{'enabled':True,'clips':[add]},'layer_clips':[text]}}).status_code==200
 j=wait(client,client.post('/api/projects/'+pid+'/export?skip_empty=true').json()['job_id']);assert j['status']=='succeeded',j
 with SessionLocal() as db:out=pathlib.Path(RENDERS_DIR)/db.get(Asset,j['artifact_asset_id']).storage_key
 info=subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(out)]).decode()
 assert abs(float(info)-3.0)<.15,info
 f=frame(out,2.5,320,180);assert f[:120].mean(axis=(0,1))[1]>100,f.mean(axis=(0,1))   # green video, not black
 bottom=frame(out,2.5,320,180)[140:,:,:];assert (bottom.max(axis=2)>230).sum()>40         # white caption text drawn
 snd=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(out),'-f','f32le','-ac','1','-ar','16000','-']),np.float32)
 assert np.sqrt(np.mean(snd[16000:32000]**2))>.02
 print('PASS once placed, the export contains the video, its sound, the caption and the text overlay',flush=True)
 # Browser-mode "Open file location": guarded, and opens the folder on this computer.
 aid=j['artifact_asset_id']
 assert client.post(f'/api/assets/{aid}/reveal').status_code==403
 assert client.post(f'/api/assets/{aid}/reveal',headers={'X-SceneForge-Action':'reveal','Origin':'https://evil.example'}).status_code==403
 assert client.post(f'/api/assets/{img["id"]}/reveal',headers={'X-SceneForge-Action':'reveal'}).status_code==404
 with patch('subprocess.Popen') as popen:
  r=client.post(f'/api/assets/{aid}/reveal',headers={'X-SceneForge-Action':'reveal','Origin':'http://127.0.0.1:8000'})
  assert r.status_code==200 and r.json()['opened'],r.text
  cmd=popen.call_args[0][0];assert str(out.resolve().parent) in ' '.join(cmd) or str(out.resolve()) in ' '.join(cmd),cmd
 with patch('subprocess.Popen'):
  for ok_origin in ('http://localhost:8000','http://127.0.0.1:5173','http://127.0.0.1:8300'):
   assert client.post(f'/api/assets/{aid}/reveal',headers={'X-SceneForge-Action':'reveal','Origin':ok_origin}).status_code==200,ok_origin
  for bad_origin in ('http://127.0.0.1.evil.example','https://sceneforge.example','http://192.168.1.5:8000'):
   assert client.post(f'/api/assets/{aid}/reveal',headers={'X-SceneForge-Action':'reveal','Origin':bad_origin}).status_code==403,bad_origin
 loc=client.get(f'/api/assets/{aid}/location').json();assert pathlib.Path(loc['path']).is_file()
 print('PASS open file location works in browser mode, only for render outputs, same app and this computer',flush=True)
