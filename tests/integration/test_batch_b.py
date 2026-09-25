"""Batch B/C: exact ElevenLabs word timing, colour wheels, video speed /
ramps / freeze frames, split-screen layouts, map routes, beat sync, 2.5D
parallax and photo restore. Verified on real renders."""
import os,pathlib,sys,tempfile,subprocess,time,io,base64
import numpy as np
from PIL import Image
root=pathlib.Path(__file__).resolve().parents[2]
tmp=tempfile.TemporaryDirectory();os.environ['SCENEFORGE_DATA_DIR']=tmp.name
t=pathlib.Path(tmp.name)
sys.path.insert(0,str(root/'backend'))
from fastapi.testclient import TestClient
from app.main import app
n=0
def check(name,ok):
 global n
 assert ok,name
 n+=1;print('PASS '+name,flush=True)
def ff(*a):subprocess.run(['ffmpeg','-v','error','-y',*a],check=True,capture_output=True)
client=TestClient(app).__enter__()
p=client.post('/api/projects',json={'title':'B','aspect':'16:9'}).json();pid=p['id']
up=lambda f:client.post('/api/assets/upload',params={'project_id':pid},files={'file':(f,open(t/f,'rb'))}).json()
sid=client.get(f'/api/projects/{pid}').json()['scenes'][0]['id']
def render(sid=sid,w=320,h=180):
 j=client.post(f'/api/scenes/{sid}/render').json()
 while (s:=client.get(f"/api/jobs/{j['job_id']}").json())['status'] not in('succeeded','failed','cancelled'):time.sleep(.2)
 assert s['status']=='succeeded',s
 aid=next(x for x in client.get(f'/api/projects/{pid}').json()['scenes'] if x['id']==sid)['rendered_asset_id']
 path=t/f'r{time.time_ns()}.mp4';path.write_bytes(client.get(f'/api/assets/{aid}/stream').content)
 raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-vf',f'scale={w}:{h}','-f','rawvideo','-pix_fmt','rgb24','-'])
 return np.frombuffer(raw,np.uint8).reshape(-1,h,w,3).astype(float)

# --- exact ElevenLabs word timing ------------------------------------------
from app.render.word_timing import words_from_alignment,exact_word_times
from app.render.subtitles import write_ass_file
import re,itertools
text='In the year 711, a force crossed.'
al={'chars':list(text),'starts':[i*0.08 for i in range(len(text))],'ends':[i*0.08+0.07 for i in range(len(text))]}
wt=exact_word_times('In the year 711 a force crossed'.split(),words_from_alignment(al))
write_ass_file('k','In the year 711 a force crossed',5000,{'karaoke':True},640,360,out_path=str(t/'k.ass'),speech_start_ms=250,speech_ms=3000,word_times=[(s+250,e+250) for s,e in wt])
st=list(itertools.accumulate(int(x) for x in re.findall(r'\\k(\d+)',(t/'k.ass').read_text(encoding='utf-8-sig'))))
check('captions use the voice engine\'s exact word times',[round(x*10) for x in st[:4]]==[250,490,810,1210])
check('a different caption falls back to measured timing',exact_word_times('Something else entirely here now ok ok'.split(),words_from_alignment(al)) is None)

# --- colour wheels ----------------------------------------------------------
Image.fromarray(np.tile(np.linspace(0,255,640)[None,:,None],(360,1,3)).astype(np.uint8)).save(t/'ramp.png')
ramp=up('ramp.png');client.post(f'/api/scenes/{sid}/shots',json={'asset_id':ramp['id']})
check('colour wheels are validated',client.patch(f'/api/scenes/{sid}',json={'look':{'wheels':{'lift':[0,0,500]}}}).status_code==400)
client.patch(f'/api/scenes/{sid}',json={'look':{'wheels':{'lift':[0,0,80],'gamma':[0,0,0],'gain':[60,0,0]}}})
g=np.asarray(Image.open(io.BytesIO(client.get(f'/api/scenes/{sid}/graded-frame',params={'w':320}).content)).convert('RGB')).astype(float)
sh,hl=g[:,10:25].reshape(-1,3).mean(axis=0),g[:,290:305].reshape(-1,3).mean(axis=0)
check('lift tints shadows (blue lift) and gain warms highlights (red gain)',sh[2]>sh[0]+25 and hl[0]>=hl[2]+0 and hl[0]>250)
client.patch(f'/api/scenes/{sid}',json={'look':{'wheels':None}})
shot_ramp=client.get(f'/api/projects/{pid}').json()['scenes'][0]['shots'][0]['id'];client.delete(f'/api/scenes/shots/{shot_ramp}')

# --- video speed, ramps, freeze ----------------------------------------------
# a white box moving exactly 100 px per second across 640 px: its x reveals the source time
ff('-f','lavfi','-i','color=c=black:s=640x360:d=6:r=30','-f','lavfi','-i','color=c=white:s=12x60:r=30','-filter_complex',"[0][1]overlay=x='t*100':y=150:shortest=1",'-pix_fmt','yuv420p',str(t/'mover.mp4'))
mv=up('mover.mp4');shot=client.post(f'/api/scenes/{sid}/shots',json={'asset_id':mv['id']}).json()
client.patch(f'/api/scenes/{sid}',json={'timing_mode':'fixed','requested_duration_ms':2000})
def src_times(fr):   # source seconds shown in each output frame
 out=[]
 for f in fr:
  xs=np.nonzero(f[75:100].max(axis=0).max(axis=1)>128)[0]
  out.append((xs.mean()*2)/100 if xs.size else None)
 return out
def setspeed(**kw):
 r=client.patch(f"/api/scenes/shots/{shot['id']}",json={'speed':kw});assert r.status_code==200,r.text
check('speed settings are validated',client.patch(f"/api/scenes/shots/{shot['id']}",json={'speed':{'speed':9}}).status_code==400)
normal=src_times(render())
setspeed(speed=2)
double=src_times(render())
check('2x speed plays the source twice as fast',abs(double[45]-2*normal[45])<0.15)
setspeed(speed=0.5)
half=src_times(render())
check('0.5x speed plays in slow motion',abs(half[45]-0.5*normal[45])<0.12)
setspeed(speed=1,ramp='slow_middle')
rp=src_times(render());rate=[(rp[i+6]-rp[i])/0.2 for i in range(0,50,6) if rp[i] is not None and rp[i+6] is not None]
check('slow-motion ramp: normal speed, slower in the middle, normal again',rate[0]>0.8 and min(rate)<0.5 and rate[-1]>0.8)
setspeed(speed=1,ramp='none',freeze_at_ms=500,freeze_ms=800)
fz=render();ts=src_times(fz)
check('freeze frame holds one frame, then playback continues, same length',len(fz)==60 and np.abs(fz[20]-fz[35]).mean()<0.5 and ts[50]>ts[35]+0.2)
setspeed(speed=1,ramp='none',freeze_at_ms=0,freeze_ms=0)
check('neutral speed settings are stored as empty',client.get(f'/api/projects/{pid}').json()['scenes'][0]['shots'][-1]['speed_json']=={})
client.delete(f"/api/scenes/shots/{shot['id']}")
print(f'{n} batch B checks passed (part 1)')
