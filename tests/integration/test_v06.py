"""SceneForge 0.6 features: cinema countdown scenes (more added as 0.6 grows)."""
import os,pathlib,subprocess,sys,tempfile
import numpy as np
root=pathlib.Path(__file__).resolve().parents[2]
tmp=tempfile.TemporaryDirectory();os.environ['SCENEFORGE_DATA_DIR']=tmp.name;t=pathlib.Path(tmp.name)
os.environ.setdefault('SCENEFORGE_RESOURCE_DIR',str(root))
sys.path.insert(0,str(root/'backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.config import MEDIA_DIR
n=0
def check(name,ok):
 global n
 assert ok,name
 n+=1;print('PASS '+name,flush=True)
c=TestClient(app).__enter__()
p=c.post('/api/projects',json={'title':'V06','aspect':'16:9'}).json();pid=p['id']
c.patch(f"/api/projects/{pid}",json={'width':640,'height':360}) if False else None
first=c.get(f'/api/projects/{pid}').json()['scenes'][0]['id']
for bad in ({'style':'x'},{'seconds':2},{'seconds':11},{'beep':'loud'},{'tone':'red'}):
 check('countdown rejects '+str(bad),c.post(f'/api/projects/{pid}/insert-countdown',json=bad).status_code==400)
r=c.post(f'/api/projects/{pid}/insert-countdown',json={'style':'minimal','seconds':4,'beep':'two-pop'})
sc=r.json()
check('countdown inserts a scene at the start with its picture and its sound',r.status_code==200 and c.get(f'/api/projects/{pid}').json()['scenes'][0]['id']==sc['id'] and len(sc['shots'])==1 and sum(v['accepted'] for v in sc['voice_takes'])==1 and sc['requested_duration_ms']==4000)
r2=c.post(f'/api/projects/{pid}/insert-countdown',json={'style':'modern','seconds':3,'after_scene_id':first})
order=[s['id'] for s in c.get(f'/api/projects/{pid}').json()['scenes']]
check('countdown can be inserted after a chosen scene',order.index(r2.json()['id'])==order.index(first)+1)
video=sorted((pathlib.Path(MEDIA_DIR)/pid).glob('countdown_minimal_*.mp4'))[0]
pcm=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(video),'-ac','1','-ar','8000','-f','s16le','-']),np.int16).astype(float)
loud=np.nonzero(np.abs(pcm)>6000)[0]   # clearly audible (above about -15 dBFS)
check('the classic 2-pop sounds exactly 2 s before the picture (4 s leader → at 2.0 s)',len(loud)>0 and abs(loud[0]/8000-2.0)<0.05 and loud[-1]/8000<2.1)
def luma(at):
 raw=subprocess.check_output(['ffmpeg','-v','error','-ss',str(at),'-i',str(video),'-frames:v','1','-vf','scale=160:90','-f','rawvideo','-pix_fmt','gray','-'])
 return np.frombuffer(raw,np.uint8)
check('numbers show during the count and the last second is black',luma(0.5).max()>200 and luma(3.5).max()<25)
fl=c.post(f'/api/projects/{pid}/insert-countdown',json={'style':'film','seconds':3,'tone':'sepia','beep':'each'}).json()
fv=sorted((pathlib.Path(MEDIA_DIR)/pid).glob('countdown_film_*.mp4'))[0]
rgb=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-ss','0.5','-i',str(fv),'-frames:v','1','-vf','scale=160:90','-f','rawvideo','-pix_fmt','rgb24','-']),np.uint8).reshape(-1,3).astype(int)
check('sepia film leader is warm-toned',rgb[:,0].mean()>rgb[:,2].mean()+15)

# --- 9:16 videos with sound: length follows the videos, their sound is kept -----------------
import time
v=c.post('/api/projects',json={'title':'Vertical','aspect':'9:16'}).json();vid=v['id']
clips=[]
for i,(col,freq) in enumerate((('red',440),('green',660),('blue',880))):
 f=t/f'v{i}.mp4'
 subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',f'color=c={col}:s=360x640:d=3:r=30','-f','lavfi','-i',f'sine=frequency={freq}:d=3','-c:v','libx264','-c:a','aac','-shortest',str(f)],check=True)
 clips.append(c.post('/api/assets/upload',params={'project_id':vid},files={'file':(f'clip{i}.mp4',open(f,'rb'),'video/mp4')}).json())
vs=c.get(f'/api/projects/{vid}').json()['scenes']
for s,a in zip(vs,clips): c.post(f"/api/scenes/{s['id']}/shots",json={'asset_id':a['id']})
vs=c.get(f'/api/projects/{vid}').json()['scenes']
check('a scene without narration reports its video length to the timeline',all(abs((s['natural_duration_ms'] or 0)-3000)<120 for s in vs))
def export_of(pid_):
 j=c.post(f'/api/projects/{pid_}/export',json={}).json()
 while (st:=c.get(f"/api/jobs/{j['job_id']}").json())['status'] not in ('succeeded','failed'):time.sleep(0.5)
 assert st['status']=='succeeded',st
 out=t/f'exp_{time.time()}.mp4';out.write_bytes(c.get(f"/api/assets/{st['artifact_asset_id']}/stream").content);return out
out=export_of(vid)
dur=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(out)]))
check(f'three 3 s 9:16 videos export as 9 s (got {dur:.2f} s), no looping or padding',abs(dur-9)<0.2)
pcm=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(out),'-ac','1','-ar','8000','-f','s16le','-']),np.int16).astype(float)
def tone(a,b):
 seg=pcm[int(a*8000):int(b*8000)];sp=np.abs(np.fft.rfft(seg));fr=np.fft.rfftfreq(len(seg),1/8000);return fr[sp.argmax()]
check('each part plays its own sound at the right time (440, 660, 880 Hz)',abs(tone(0.5,2.5)-440)<15 and abs(tone(3.5,5.5)-660)<15 and abs(tone(6.5,8.5)-880)<15)
sh=vs[1]['shots'][0]['id']
check('clip sound settings are validated',c.patch(f'/api/scenes/shots/{sh}',json={'audio':{'volume':500}}).status_code==400)
c.patch(f'/api/scenes/shots/{sh}',json={'audio':{'mute':True}})
out2=export_of(vid);pcm=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(out2),'-ac','1','-ar','8000','-f','s16le','-']),np.int16).astype(float)
rms=lambda a,b:float(np.sqrt((pcm[int(a*8000):int(b*8000)]**2).mean()))
check('muting one clip silences only that part',rms(3.5,5.5)<30 and rms(0.5,2.5)>300 and rms(6.5,8.5)>300)
# --- countdown intro effect ------------------------------------------------------------------
check('countdown intro settings are validated',c.patch(f"/api/scenes/{vs[0]['id']}",json={'look':{'countdown':{'seconds':30}}}).status_code==400)
c.patch(f"/api/scenes/{vs[0]['id']}",json={'look':{'countdown':{'style':'minimal','seconds':3,'beep':'two-pop'}}})
out3=export_of(vid)
d3=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(out3)]))
check(f'countdown intro plays before the scene and adds its length ({d3:.2f} s)',abs(d3-12)<0.25)
print(f'{n} v0.6 checks passed')
