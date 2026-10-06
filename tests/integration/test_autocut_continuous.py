"""Continuous AutoCut advances picture and embedded sound ranges; no provider calls."""
import os,pathlib,sys,tempfile,subprocess,time
import numpy as np
root=pathlib.Path(__file__).resolve().parents[2];tmp=tempfile.TemporaryDirectory(prefix='sf-cut-continuous-');os.environ['SCENEFORGE_DATA_DIR']=tmp.name;sys.path.insert(0,str(root/'backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import SessionLocal
from app.db.models import Project
clip=pathlib.Path(tmp.name)/'source.mp4'
subprocess.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','testsrc2=s=320x180:r=25:d=5','-f','lavfi','-i','sine=frequency=440:duration=5','-c:v','libx264','-preset','ultrafast','-c:a','aac','-threads','1',str(clip)],check=True)
with TestClient(app) as c:
 p=c.post('/api/projects',json={'title':'Continuous cuts','aspect':'16:9','fps':25}).json()
 with SessionLocal() as db:
  row=db.get(Project,p['id']);row.width=320;row.height=180;db.commit()
 sid=c.get('/api/projects/'+p['id']).json()['scenes'][0]['id']
 c.patch('/api/scenes/'+sid,json={'timing_mode':'fixed','requested_duration_ms':3000,'font':{'captions_enabled':False}})
 a=c.post('/api/assets/upload?project_id='+p['id'],files={'file':('source.mp4',clip.read_bytes(),'video/mp4')}).json()
 sh=c.post('/api/scenes/'+sid+'/shots',json={'asset_id':a['id'],'motion':{'type':'static'}}).json()
 r=c.patch('/api/scenes/shots/'+sh['id'],json={'source_in_ms':1000,'source_out_ms':4000});assert r.status_code==200,r.text
 before=c.get('/api/scenes/'+sid).json();body={'times_ms':[1000,2000],'video_mode':'continuous'}
 r=c.post('/api/scenes/'+sid+'/autocut/preview',json=body);assert r.status_code==200,r.text;plan=r.json()
 assert [(s['source_in_ms'],s['source_out_ms']) for s in plan['shots']]==[(1000,2000),(2000,3000),(3000,4000)]
 assert c.get('/api/scenes/'+sid).json()['shots']==before['shots'];print('PASS continuous preview creates contiguous source ranges without editing',flush=True)
 apply={**body,'revision':plan['revision'],'preview_token':plan['preview_token']}
 assert c.post('/api/scenes/'+sid+'/autocut',json={**apply,'video_mode':'repeat'}).status_code==409
 r=c.post('/api/scenes/'+sid+'/autocut',json=apply);assert r.status_code==200,r.text;after=r.json();assert sum(s['duration_ms'] for s in after['shots'])==3000
 assert after['font_json']==before['font_json'] and after['spoken_text']==before['spoken_text'];print('PASS mode is bound to preview token; Apply preserves scene duration and text',flush=True)
 assert c.post('/api/scenes/'+sid+'/restore',json=before).status_code==200
 assert c.get('/api/scenes/'+sid).json()['shots']==before['shots']
 assert c.post('/api/scenes/'+sid+'/restore',json=after).status_code==200
 assert c.get('/api/scenes/'+sid).json()['shots']==after['shots'];print('PASS exact continuous cut snapshots restore for Undo and Redo',flush=True)
 jid=c.post('/api/scenes/'+sid+'/render').json()['job_id']
 for _ in range(1200):
  j=c.get('/api/jobs/'+jid).json()
  if j['status'] in ('succeeded','failed','cancelled'):break
  time.sleep(.05)
 assert j['status']=='succeeded',j
 out=pathlib.Path(tmp.name)/'rendered.mp4';out.write_bytes(c.get('/api/assets/'+j['artifact_asset_id']+'/stream').content)
 def frame(path,sec):
  raw=subprocess.check_output(['ffmpeg','-v','error','-ss',str(sec),'-i',str(path),'-frames:v','1','-threads','1','-pix_fmt','rgb24','-f','rawvideo','-']);return np.frombuffer(raw,np.uint8).reshape(180,320,3).astype(float)
 for sec in (.2,1.2,2.2):
  rendered=frame(out,sec);expected=frame(clip,sec+1);assert np.abs(rendered-expected).mean()<8,(sec,np.abs(rendered-expected).mean())
 assert np.abs(frame(out,2.2)-frame(clip,1.2)).mean()>12;print('PASS rendered pictures advance across every beat rather than restarting the excerpt',flush=True)
 c.post('/api/scenes/'+sid+'/restore',json=before)
 c.patch('/api/scenes/shots/'+sh['id'],json={'source_out_ms':2000})
 assert c.post('/api/scenes/'+sid+'/autocut/preview',json=body).status_code==400
 a2=c.post('/api/scenes/'+sid+'/shots',json={'asset_id':a['id']})
 assert c.post('/api/scenes/'+sid+'/autocut/preview',json=body).status_code==400
 assert c.post('/api/scenes/'+sid+'/autocut/preview',json={**body,'video_mode':'invalid'}).status_code==422
 print('PASS short excerpts, multiple sources and invalid modes are rejected')
