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
print(f'{n} v0.6 checks passed')
