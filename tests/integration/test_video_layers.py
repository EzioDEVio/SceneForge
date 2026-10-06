"""Real moving overlays, delayed audio, source bounds and save/restore. No providers."""
import io, os, pathlib, subprocess, sys, tempfile, time
import numpy as np
from PIL import Image
ROOT=pathlib.Path(__file__).resolve().parents[2]
work=tempfile.TemporaryDirectory();os.environ['SCENEFORGE_DATA_DIR']=work.name
sys.path.insert(0,str(ROOT/'backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import SessionLocal
from app.db.models import Project
from app.render.ffmpeg_utils import probe
n=0

def check(name,ok):
 global n
 assert ok,name;n+=1;print('PASS '+name,flush=True)

def wait(c,jid):
 for _ in range(600):
  job=c.get('/api/jobs/'+jid).json()
  if job['status'] in ('failed','succeeded','cancelled'):
   assert job['status']=='succeeded',job;return job
  time.sleep(.1)
 raise AssertionError('Render timed out')

def make(name,color):
 file=pathlib.Path(work.name)/name
 subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',f'color={color}:s=80x80:r=25:d=4','-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=4','-vf',"drawbox=x=0:y=0:w=iw:h=ih:color=green:t=fill:enable='gte(t,2)'" if color=='red' else 'null','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(file)],check=True)
 return file

with TestClient(app) as c:
 p=c.post('/api/projects',json={'title':'Video stack','aspect':'16:9','fps':25}).json();pid=p['id']
 with SessionLocal() as db:
  p=db.get(Project,pid);p.width=160;p.height=90;db.commit()
 scenes=c.get('/api/projects/'+pid).json()['scenes'];sid=scenes[0]['id']
 image=Image.new('RGB',(160,90),'blue');buff=io.BytesIO();image.save(buff,format='PNG')
 base=c.post('/api/assets/upload?project_id='+pid,files={'file':('base.png',buff.getvalue(),'image/png')}).json()
 c.post('/api/scenes/'+sid+'/shots',json={'asset_id':base['id']});c.patch('/api/scenes/'+sid,json={'timing_mode':'fixed','requested_duration_ms':5000,'font':{'captions_enabled':False}})
 assets=[]
 for name,color in [('changing.mp4','red'),('upper.mp4','yellow')]:
  f=make(name,color);assets.append(c.post('/api/assets/upload?project_id='+pid,files={'file':(name,f.read_bytes(),'video/mp4')}).json())
 layer={'id':'moving','kind':'video','asset_id':assets[0]['id'],'start_ms':1000,'duration_ms':2000,'source_in_ms':1000,'x':50,'y':50,'width':50,'track':1}
 def patch(clips):return c.patch('/api/projects/'+pid,json={'finishing':{'layer_clips':clips}})
 saved=patch([layer]);check('video layer accepted with muted default',saved.status_code==200 and saved.json()['finishing_json']['layer_clips'][0]['mute'] is True)
 for label,change in [('source beyond file',{'source_in_ms':3000}),('negative source',{'source_in_ms':-1}),('invalid mute',{'mute':1}),('bad volume',{'volume':201}),('wrong media kind',{'asset_id':base['id']}),('infinite source',{'source_in_ms':'NaN'})]:check('rejects '+label,patch([{**layer,**change}]).status_code==400)
 output=pathlib.Path(work.name)/'export.mp4'
 def export():
  job=wait(c,c.post('/api/projects/'+pid+'/export?skip_empty=true').json()['job_id']);output.write_bytes(c.get('/api/assets/'+job['artifact_asset_id']+'/stream').content)
 def frame(t):
  raw=subprocess.check_output(['ffmpeg','-v','error','-ss',str(t),'-i',str(output),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-']);return np.frombuffer(raw,np.uint8).reshape(90,160,3).astype(int)
 def sound(t):
  raw=subprocess.check_output(['ffmpeg','-v','error','-ss',str(t),'-i',str(output),'-t','0.3','-vn','-f','f32le','-ac','1','-ar','48000','-']);return np.sqrt(np.mean(np.frombuffer(raw,np.float32)**2))
 patch([layer]);export();check('stack export keeps base duration',abs(probe(str(output)).duration_ms-5000)<80)
 check('base visible before video layer',frame(.5)[45,80,2]>180)
 check('source in selects red before its change',frame(1.4)[45,80,0]>180)
 check('video layer plays into its green frames',frame(2.4)[45,80,1]>70 and frame(2.4)[45,80,0]<50)
 check('no held overlay frame after layer end',frame(3.3)[45,80,2]>180)
 check('muted video layer contributes no audio',sound(1.5)<.001)
 upper={**layer,'id':'upper','asset_id':assets[1]['id'],'track':0,'width':20,'source_in_ms':0}
 patch([{**layer,'mute':False,'volume':50},upper]);export()
 check('second video stacks above first video',frame(1.4)[45,80,0]>180 and frame(1.4)[45,80,1]>180)
 check('unmuted layer audio appears at authored time',sound(1.5)>.02 and sound(.5)<.001 and sound(3.5)<.001)
 snap=c.post('/api/projects/'+pid+'/snapshots',json={'label':'Stacked videos'}).json()['snapshot']['id'];restored=c.post(f'/api/projects/{pid}/snapshots/{snap}/restore').json()['id'];rp=c.get('/api/projects/'+restored).json()
 check('restore remaps both video assets and keeps source offsets',len(rp['finishing_json']['layer_clips'])==2 and rp['finishing_json']['layer_clips'][0]['source_in_ms']==1000 and rp['finishing_json']['layer_clips'][0]['asset_id']!=assets[0]['id'])
 check('remapped video is playable',c.get('/api/assets/'+rp['finishing_json']['layer_clips'][0]['asset_id']+'/stream').status_code==200)
 check('clearing and restoring layers preserves base scenes',patch([]).status_code==200 and patch([layer,upper]).status_code==200 and len(c.get('/api/projects/'+pid).json()['scenes'])==3)
 c.patch('/api/scenes/'+scenes[1]['id'],json={'timing_mode':'fixed','requested_duration_ms':1000})
 c.post('/api/scenes/'+scenes[2]['id']+'/shots',json={'asset_id':base['id']});c.patch('/api/scenes/'+scenes[2]['id'],json={'timing_mode':'fixed','requested_duration_ms':3000,'font':{'captions_enabled':False}})
 check('video layer spanning an empty scene is accepted',patch([{**layer,'start_ms':4500,'duration_ms':2500,'source_in_ms':500}]).status_code==200)
 export();check('skipped empty scene advances video source instead of restarting',frame(4.7)[45,80,0]>180 and frame(5.3)[45,80,1]>70 and frame(5.3)[45,80,0]<50)
print(f'{n} video layer checks passed')
