"""Old-film look: scratches, dust, flicker, gate weave, projector frame rate
and tone, verified on real renders through the API."""
import os,pathlib,sys,tempfile,subprocess,time
import numpy as np
from PIL import Image
root=pathlib.Path(__file__).resolve().parents[2]
tmp=tempfile.TemporaryDirectory();os.environ['SCENEFORGE_DATA_DIR']=tmp.name
t=pathlib.Path(tmp.name)
sys.path.insert(0,str(root/'backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.render.film_damage import generate_frames
from app.render.filters import build_film_chain,clean_film
n=0
def check(name,ok):
 global n
 assert ok,name
 n+=1;print('PASS '+name,flush=True)
client=TestClient(app).__enter__()

# --- damage generator -------------------------------------------------------
a=generate_frames(320,180,18,0.8,0.7,seed=5);b=generate_frames(320,180,18,0.8,0.7,seed=5);c=generate_frames(320,180,18,0.8,0.7,seed=6)
check('damage clip is a 4 s loop at the film frame rate',a.shape==(72,180,320))
check('same seed gives identical damage; another seed differs',np.array_equal(a,b) and not np.array_equal(a,c))
none=generate_frames(320,180,18,0,0,seed=1)
check('no scratches and no dust means a neutral (all 128) clip',np.all(none==128))
col=np.abs(a.astype(float)-128).mean(axis=(0,1));row=np.abs(a.astype(float)-128).mean(axis=(0,2))
check('scratches are vertical: damage concentrates in columns, not rows',col.max()>4*np.median(col) and row.max()<2*np.median(row))
dust=generate_frames(320,180,18,0,0.8,seed=3)
check('dust changes every frame',np.mean([np.abs(dust[i].astype(float)-dust[i-1]).mean()>0 for i in range(1,72)])>0.95)

# --- settings validation ----------------------------------------------------
check('film settings fill in defaults and clamp',clean_film({'scratches':150,'fps':12,'tone':'x'})=={'scratches':100,'dust':50,'flicker':40,'weave':35,'sound':0,'fps':18,'tone':'bw'})
p=client.post('/api/projects',json={'title':'Film','aspect':'16:9'}).json();pid=p['id']
# detailed test picture with colour, so tone and weave are measurable
subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=s=640x360','-frames:v','1',str(t/'src.png')],check=True)
img=client.post('/api/assets/upload',params={'project_id':pid},files={'file':('src.png',open(t/'src.png','rb'))}).json()
sid=client.get(f'/api/projects/{pid}').json()['scenes'][0]['id']
client.post(f'/api/scenes/{sid}/shots',json={'asset_id':img['id']})
client.patch(f'/api/scenes/{sid}',json={'timing_mode':'fixed','requested_duration_ms':2000})
for body,why in [({'scratches':101},'amount above 100'),({'fps':12},'unsupported frame rate'),({'tone':'purple'},'unknown tone'),({'speed':3},'unknown setting')]:
 check('film settings reject '+why,client.patch(f'/api/scenes/{sid}',json={'look':{'film':body}}).status_code==400)
def render():
 j=client.post(f'/api/scenes/{sid}/render').json()
 while (s:=client.get(f"/api/jobs/{j['job_id']}").json())['status'] not in('succeeded','failed','cancelled'):time.sleep(.2)
 assert s['status']=='succeeded',s
 aid=client.get(f'/api/projects/{pid}').json()['scenes'][0]['rendered_asset_id']
 path=t/'part.mp4';path.write_bytes(client.get(f'/api/assets/{aid}/stream').content)
 raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-vf','scale=480:270','-f','rawvideo','-pix_fmt','rgb24','-'])
 return np.frombuffer(raw,np.uint8).reshape(-1,270,480,3).astype(float)
plain=render()
check('plain scene renders 60 frames',len(plain)==60)
def film(**kw):
 base={'scratches':0,'dust':0,'flicker':0,'weave':0,'fps':0,'tone':'color'};base.update(kw)
 r=client.patch(f'/api/scenes/{sid}',json={'look':{'film':base}});assert r.status_code==200,r.text
 return render()
bw=film(tone='bw')
check('B&W tone removes colour',np.abs(bw[10]-bw[10].mean(axis=2,keepdims=True)).mean()<2 and np.abs(plain[10]-plain[10].mean(axis=2,keepdims=True)).mean()>20)
sep=film(tone='sepia');m=sep[10].reshape(-1,3).mean(axis=0)
check('sepia tone is warm brown',m[0]>m[1]>m[2])
shot_id=client.get(f'/api/projects/{pid}').json()['scenes'][0]['shots'][0]['id']
client.patch(f'/api/scenes/shots/{shot_id}',json={'motion':{'type':'zoom_in'}})
def changes(frames):return sum(np.abs(frames[i]-frames[i-1]).mean()>0.3 for i in range(1,len(frames)))
smooth=film(fps=0);jerky=film(fps=16)
check('16 fps projector: moving picture updates about 16 times a second, length unchanged',len(jerky)==60 and changes(smooth)>=55 and 26<=changes(jerky)<=34)
client.patch(f'/api/scenes/shots/{shot_id}',json={'motion':{'type':'static'}})
still=film(weave=100)
moves=[np.abs(still[i]-still[i-1]).mean() for i in range(1,len(still))]
check('gate weave makes a still picture wobble',np.mean(moves)>1.0 and np.mean([mv>0.4 for mv in moves])>0.8 and max(np.abs(plain[i]-plain[i-1]).mean() for i in range(1,len(plain)))<0.2)
flick=film(flicker=100)
lum=[f.mean() for f in flick]
check('flicker varies the exposure from frame to frame',np.std(lum)>1.0 and np.std([f.mean() for f in plain])<0.2)
scr=film(scratches=100)
diff=np.abs(scr-plain).mean(axis=(0,3))
colprof=diff.mean(axis=0);rowprof=diff.mean(axis=1)
check('scratches show as vertical lines in the render',colprof.max()>3*np.median(colprof) and rowprof.max()<1.6*np.median(rowprof))
again=film(scratches=100)
check('renders are reproducible (same scene, same damage)',np.abs(again-scr).mean()<0.5)
check('the scene look saves the film settings',client.get(f'/api/projects/{pid}').json()['scenes'][0]['look_json']['film']['scratches']==100)
r=client.patch(f'/api/scenes/{sid}',json={'look':{'film':None}}).json()
check('turning old film off removes it',('film' not in r['look_json']))
print(f'{n} old film checks passed')
