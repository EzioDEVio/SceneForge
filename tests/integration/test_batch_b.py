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

# --- split screen layouts ------------------------------------------------------
Image.fromarray(np.full((360,640,3),(220,30,30),np.uint8)).save(t/'red.png');Image.fromarray(np.full((360,640,3),(30,30,220),np.uint8)).save(t/'blue.png')
Image.fromarray(np.full((360,640,3),(30,200,30),np.uint8)).save(t/'green.png');Image.fromarray(np.full((360,640,3),(230,210,40),np.uint8)).save(t/'yellow.png')
ids=[up(f)['id'] for f in ('red.png','blue.png','green.png','yellow.png')]
for i in ids:client.post(f'/api/scenes/{sid}/shots',json={'asset_id':i})
check('layout settings are validated',client.patch(f'/api/scenes/{sid}',json={'look':{'layout':{'type':'grid9'}}}).status_code==400)
client.patch(f'/api/scenes/{sid}',json={'look':{'layout':{'type':'split2','gap':20,'bg':'#FFFFFF'}}})
f2=render()[30]
check('split screen shows two shots side by side with a gap',f2[90,60,0]>180 and f2[90,260,2]>180 and f2[90,160].min()>200)
client.patch(f'/api/scenes/{sid}',json={'look':{'layout':{'type':'grid4','gap':0,'bg':'#000000'}}})
f4=render()[30]
check('grid layout shows four shots in the four corners',f4[40,60,0]>180 and f4[40,260,2]>180 and f4[140,60,1]>150 and f4[140,260,0]>180 and f4[140,260,1]>150)
client.patch(f'/api/scenes/{sid}',json={'look':{'layout':None}})
for x in client.get(f'/api/projects/{pid}').json()['scenes'][0]['shots'][1:]:client.delete(f"/api/scenes/shots/{x['id']}")

# --- animated map route ------------------------------------------------------------
check('route settings are validated',client.patch(f'/api/scenes/{sid}',json={'look':{'route':{'points':[[10,10]]}}}).status_code==400)
client.patch(f'/api/scenes/{sid}',json={'look':{'route':{'points':[[10,50],[90,50]],'color':'#FFFFFF','width':12,'style':'solid','pins':True,'start_ms':0,'draw_ms':1500}}})
rt=render()
def line_extent(f):
 cols=np.nonzero((np.abs(f[88:93]-np.array([220,30,30])).sum(axis=-1)>150).any(axis=0))[0]
 return cols.max() if cols.size else 0
check('route line draws itself from start to end, then stays',line_extent(rt[8])<line_extent(rt[30])<line_extent(rt[50]) and line_extent(rt[50])>270 and line_extent(rt[59])>270)
client.patch(f'/api/scenes/{sid}',json={'look':{'route':None}})
for bad,why in [({'points':[[10,50],[90,50]],'marker':'rocket'},'unknown icon'),({'points':[[10,50],[90,50]],'labels':['x'*41]},'label over 40 characters'),({'points':[[10,50],[90,50]],'curve':'yes'},'curve not true/false')]:
 check('route extras validate '+why,client.patch(f'/api/scenes/{sid}',json={'look':{'route':bad}}).status_code==400)
from app.render.routes import clean_route,route_clip
rx=clean_route({'points':[[12,72],[38,40],[62,62],[86,28]],'color':'#E8413C','width':8,'arrow':True,'labels':['A','B','C','Toledo'],'curve':True,'draw_ms':1000})
rc=route_clip(rx,640,360,30,t/'routes')
end=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',rc,'-vf','select=eq(n\\,41)','-frames:v','1','-f','rawvideo','-pix_fmt','rgba','-']),np.uint8).reshape(360,640,4).astype(int)
lx,ly=int(0.86*640),int(0.28*360)
box=end[ly+8:ly+50,lx-60:lx+60]
check('the last stop gets its label once the route is finished',(box[...,3]>150).mean()>0.1 and ((box[...,:3].min(axis=-1)>220)&(box[...,3]>200)).sum()>20)
tipzone=end[ly-30:ly,lx:lx+30]
check('the arrowhead stays visible past the destination pin',((np.abs(tipzone[...,:3]-np.array([232,65,60])).sum(axis=-1)<60)&(tipzone[...,3]>200)).sum()>15)
from app.render.routes import _label_text,_label_font
shaped=_label_text('قرطبة')
check('Arabic stop labels are shaped (joined letter forms) and use the Arabic font',any('\ufe70'<=c<='\ufeff' for c in shaped) and 'Naskh' in _label_font('قرطبة',20).getname()[0] and _label_text('Toledo')=='Toledo')
pl=clean_route({'points':[[10,50],[90,50]],'marker':'plane','draw_ms':1000})
mid=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',route_clip(pl,640,360,30,t/'routes'),'-vf','select=eq(n\\,15)','-frames:v','1','-f','rawvideo','-pix_fmt','rgba','-']),np.uint8).reshape(360,640,4).astype(int)
check('a moving plane icon rides along the route',((mid[...,:3].min(axis=-1)>230)&(mid[...,3]>200)).sum()>150)

# --- beat sync ---------------------------------------------------------------------
ff('-f','lavfi','-i',"aevalsrc='0.8*sin(2*PI*60*t)*exp(-40*mod(t,0.5))':s=22050:d=12",str(t/'beat.wav'))   # 120 BPM kick
from app.render.beats import detect_beats,snap_durations
bpm,beats=detect_beats(str(t/'beat.wav'))
check(f'beat detection finds the tempo (found {bpm} BPM, expected 120)',abs(bpm-120)<3 and len(beats)>=20 and all(abs((b-beats[0])%0.5)<0.03 or abs((b-beats[0])%0.5-0.5)<0.03 for b in beats))
new=snap_durations([2300,3100,1700],[True,False,True],[i*0.5 for i in range(40)])
check('snapping puts every fixed-length cut on a beat and keeps narrated scenes',new[1]==3100 and abs((new[0]/1000)%0.5)<1e-6 and abs(((new[0]+new[1]+new[2])/1000)%0.5)<1e-6)
music=up('beat.wav')
check('beat sync needs background music first',client.post(f'/api/projects/{pid}/beat-sync').status_code==400)
client.patch(f'/api/projects/{pid}',json={'finishing':{'music':{'asset_id':music['id'],'volume':40,'duck':0,'fade_in_ms':0,'fade_out_ms':0}}})
client.patch(f'/api/scenes/{sid}',json={'timing_mode':'fixed','requested_duration_ms':2300})
r=client.post(f'/api/projects/{pid}/beat-sync').json()
d=client.get(f'/api/projects/{pid}').json()['scenes'][0]['requested_duration_ms']
check('beat sync moves the scene cut onto a beat',abs(r['bpm']-120)<3 and abs((d/1000-beats[0])%0.5)<0.03 or abs((d/1000-beats[0])%0.5-0.5)<0.03)
client.patch(f'/api/projects/{pid}',json={'finishing':{}})

# --- 2.5D parallax ------------------------------------------------------------------
yy,xx=np.mgrid[0:360,0:640];bgimg=np.dstack([(xx/640*200).astype(np.uint8),(yy/360*120+60).astype(np.uint8),np.full((360,640),120,np.uint8)])
bgimg[120:280,260:380]=[250,250,250]    # a bright "subject" in the middle
Image.fromarray(bgimg).save(t/'photo.png');photo=up('photo.png')
first=client.get(f'/api/projects/{pid}').json()['scenes'][0]['shots'][0]['id'];client.delete(f'/api/scenes/shots/{first}')
client.post(f'/api/scenes/{sid}/shots',json={'asset_id':photo['id']})
check('parallax settings are validated',client.patch(f'/api/scenes/{sid}',json={'look':{'parallax':{'direction':'up'}}}).status_code==400)
client.patch(f'/api/scenes/{sid}',json={'look':{'parallax':{'x':50,'y':55,'w':25,'h':50,'shape':'rect','direction':'in','amount':100}}})
px=render()
def subj_width(f):return np.ptp(np.nonzero((f.min(axis=2)>230).any(axis=0))[0])
def bg_shift(a,b):return np.abs(a[10:40,10:60]-b[10:40,10:60]).mean()
check('parallax: the subject grows much more than the background (depth)',subj_width(px[59])>subj_width(px[0])*1.15 and bg_shift(px[0],px[59])<25)
from app.render.photo import parallax_layers
import cv2
bgl,fgl=parallax_layers(str(t/'photo.png'),{'x':50,'y':55,'w':25,'h':50,'shape':'rect','direction':'in','amount':100},t/'plx')
bgarr=cv2.imread(bgl);fga=cv2.imread(fgl,cv2.IMREAD_UNCHANGED)
check('background layer has the subject filled in from its surroundings',bgarr[200,320].min()<220)
check('subject layer has a soft transparent edge',fga[200,320,3]>240 and fga[20,20,3]<5 and 5<fga[200,255,3]<250)
client.patch(f'/api/scenes/{sid}',json={'look':{'parallax':None}})

# --- photo restore ------------------------------------------------------------------------
# A textured black & white "photo": smooth sky on top, detailed ground below (like real war photos),
# with dust specks in the sky. Restore must remove the dust and keep the ground detail.
rng=np.random.default_rng(3)
yy,xx=np.mgrid[0:600,0:800]
sky=160+30*np.sin(xx/140.0)+rng.normal(0,4,(600,800))
ground=110+45*np.sign(np.sin(xx/3.1)*np.sin(yy/2.7))+rng.normal(0,6,(600,800))      # fine high-contrast texture
photo=np.where(yy<300,sky,ground)
dust=[(rng.integers(20,280),rng.integers(20,780)) for _ in range(40)]
for y,x in dust:photo[y-1:y+2,x-1:x+2]=250
Image.fromarray(np.clip(photo,0,255).astype(np.uint8)).convert('RGB').save(t/'old.jpg',quality=95);oldid=up('old.jpg')['id']
r=client.post(f'/api/assets/{oldid}/restore');rest=r.json()
check('restore creates a new photo and keeps the original',r.status_code==200 and rest['id']!=oldid and rest['original_filename']=='old (restored).png')
ra=np.asarray(Image.open(io.BytesIO(client.get(f"/api/assets/{rest['id']}/stream").content)).convert('RGB')).astype(float)
check('restore upscales small scans and keeps black & white as black & white',ra.shape[1]>=1200 and np.abs(ra[...,0]-ra[...,2]).mean()<1)
small=cv2.resize(ra,(800,600),interpolation=cv2.INTER_AREA).mean(axis=2)
check('restore removes the dust specks from the smooth sky',max(small[y,x]-np.median(small[y-6:y+7,x-6:x+7]) for y,x in dust)<40)
lap=lambda a:np.abs(cv2.Laplacian(a.astype(np.float32),cv2.CV_32F)).mean()
kept=lap(small[320:580,20:780])/lap(photo[320:580,20:780])
check(f'restore keeps the fine ground detail (kept {kept*100:.0f}%; the old method smeared textured areas)',kept>0.85)
from app.render.photo import dust_mask,_noise_sigma
g=np.clip(photo,0,255).astype(np.uint8)
check('dust detection never marks textured areas',(dust_mask(g,_noise_sigma(g))[300:]>0).mean()<0.001)
check('restore rejects non-photos',client.post(f"/api/assets/{music['id']}/restore").status_code==400)
print(f'{n} batch B/C checks passed')
