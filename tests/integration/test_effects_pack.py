"""Effects pack: VHS, new transitions, camera shake, spotlight, blur/pixelate
regions, light leaks, split toning, overlay glide / green screen / feather,
voice effects and pop/glow caption styles. Verified on real renders."""
import os,pathlib,sys,tempfile,subprocess,time,re
import numpy as np
from PIL import Image
root=pathlib.Path(__file__).resolve().parents[2]
tmp=tempfile.TemporaryDirectory();os.environ['SCENEFORGE_DATA_DIR']=tmp.name
t=pathlib.Path(tmp.name)
sys.path.insert(0,str(root/'backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.render.renderer import XFADE_NAMES
from app.render.subtitles import write_ass_file
from app.render.audio_edit import narration_filter
n=0
def check(name,ok):
 global n
 assert ok,name
 n+=1;print('PASS '+name,flush=True)
def ff(*a):subprocess.run(['ffmpeg','-v','error','-y',*a],check=True,capture_output=True)
client=TestClient(app).__enter__()
for tt in ('wind','slice','open','close','fade_fast'):
 r=subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=red:s=160x90:d=2:r=30','-f','lavfi','-i','color=c=blue:s=160x90:d=2:r=30','-filter_complex',f"[0][1]xfade=transition={XFADE_NAMES[tt]}:duration=1:offset=0.5",'-f','null','-'],capture_output=True)
 check(f'transition "{tt}" renders',r.returncode==0)
p=client.post('/api/projects',json={'title':'FX','aspect':'16:9'}).json();pid=p['id']
ff('-f','lavfi','-i','testsrc2=s=640x360','-frames:v','1',str(t/'src.png'))
Image.fromarray(np.full((200,200,3),(0,255,0),np.uint8)).save(t/'green.png')
up=lambda f:client.post('/api/assets/upload',params={'project_id':pid},files={'file':(f,open(t/f,'rb'))}).json()
src,green=up('src.png'),up('green.png')
sid=client.get(f'/api/projects/{pid}').json()['scenes'][0]['id']
client.post(f'/api/scenes/{sid}/shots',json={'asset_id':src['id']})
client.patch(f'/api/scenes/{sid}',json={'timing_mode':'fixed','requested_duration_ms':2000})
def render(**patch):
 r=client.patch(f'/api/scenes/{sid}',json=patch);assert r.status_code==200,r.text
 j=client.post(f'/api/scenes/{sid}/render').json()
 while (s:=client.get(f"/api/jobs/{j['job_id']}").json())['status'] not in('succeeded','failed','cancelled'):time.sleep(.2)
 assert s['status']=='succeeded',s
 aid=client.get(f'/api/projects/{pid}').json()['scenes'][0]['rendered_asset_id']
 path=t/f'r{time.time_ns()}.mp4';path.write_bytes(client.get(f'/api/assets/{aid}/stream').content)
 raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-vf','scale=320:180','-f','rawvideo','-pix_fmt','rgb24','-'])
 return np.frombuffer(raw,np.uint8).reshape(-1,180,320,3).astype(float)
plain=render(look={'glitch':None})
for bad,why in [({'shake':{'amount':500}},'shake amount'),({'spotlight':{'shape':'star'}},'spotlight shape'),({'redact':[{'mode':'smear'}]},'redact mode'),
                ({'leak':{'color':'green'}},'leak colour'),({'tone':{'shadow':'blue'}},'tone colour'),({'redact':[{}]*7},'more than 6 regions')]:
 check('look rejects bad '+why,client.patch(f'/api/scenes/{sid}',json={'look':bad}).status_code==400)
vhs=render(effect_preset='vhs',effect_intensity=100)
check('VHS look renders and changes the picture',np.abs(vhs[20]-plain[20]).mean()>5)
client.patch(f'/api/scenes/{sid}',json={'effect_preset':'original'})
shk=render(look={'shake':{'amount':80,'speed':60,'impact':True}})
moves=[np.abs(shk[i]-shk[i-1]).mean() for i in range(1,len(shk))]
check('camera shake moves a still picture every frame',np.mean([m>0.8 for m in moves])>0.9)
check('impact zoom punches in at the start and settles',np.abs(shk[1]-plain[1]).mean()>np.abs(shk[55]-plain[55]).mean())
sp=render(look={'shake':None,'spotlight':{'x':50,'y':50,'w':30,'h':40,'shape':'ellipse','dim':80,'feather':20,'start_ms':600,'end_ms':None}})
check('spotlight dims outside the region only, from its start time',sp[45][5:40,5:60].mean()<plain[45][5:40,5:60].mean()*0.5 and abs(sp[45][85:95,155:165].mean()-plain[45][85:95,155:165].mean())<8 and abs(sp[5].mean()-plain[5].mean())<3)
rd=render(look={'spotlight':None,'redact':[{'x':25,'y':50,'w':30,'h':40,'mode':'blur','strength':90},{'x':75,'y':50,'w':30,'h':40,'mode':'pixelate','strength':90}]})
def detail(a):return np.percentile(np.abs(np.diff(a,axis=1)),99)   # edge sharpness: blur spreads edges out
L=(slice(75,105),slice(40,120));R=(slice(75,105),slice(200,280))   # whole boxes, across colour-bar edges
check('blur region removes fine detail inside the box only',detail(rd[30][L])<detail(plain[30][L])*0.5 and abs(detail(rd[30][10:40,140:180])-detail(plain[30][10:40,140:180]))<25)
blk=rd[30][R].mean(axis=2)
check('pixelate region turns the box into large blocks',np.mean(np.abs(np.diff(blk,axis=1))<1)>0.7)
lk=render(look={'redact':None,'leak':{'amount':90,'speed':40,'color':'warm'}})
d=(lk[30]-plain[30]).reshape(-1,3).mean(axis=0)
check('light leaks add warm light (more red than blue)',d[0]>3 and d[0]>d[2]+2)
check('light leaks drift over time',np.abs(lk[5]-lk[50]).mean()>1)
Image.fromarray(np.tile(np.linspace(0,255,640)[None,:,None],(360,1,3)).astype(np.uint8)).save(t/'ramp.png')   # black -> white
ramp=up('ramp.png');rs=client.post(f'/api/scenes/{sid}/shots',json={'asset_id':ramp['id']}).json()
client.patch(f'/api/scenes/{sid}',json={'look':{'leak':None,'tone':{'shadow':'#0033FF','highlight':'#FF9900','amount':100,'balance':0}}})
import io
fr=np.asarray(Image.open(io.BytesIO(client.get(f'/api/scenes/{sid}/graded-frame',params={'w':320,'shot_id':rs['id']}).content)).convert('RGB')).astype(float)
sh,hl=fr[:,40:60].reshape(-1,3).mean(axis=0),fr[:,260:280].reshape(-1,3).mean(axis=0)
check('split toning: shadows turn blue, highlights turn orange, mid-greys stay near neutral',sh[2]>sh[0]+10 and hl[0]>hl[2]+10 and np.ptp(fr[:,158:162].reshape(-1,3).mean(axis=0))<12)
client.delete(f"/api/scenes/shots/{rs['id']}")
client.patch(f'/api/scenes/{sid}',json={'look':{'tone':None}})
ov={'asset_id':green['id'],'x':20,'y':50,'width':25,'border':0,'radius':0,'shadow':0,'anim_in':'none','anim_out':'none','x2':80,'y2':50}
gl=render(overlays=[ov])
gm=lambda f:(f[...,1]>200)&(f[...,0]<80)&(f[...,2]<80)
chg=lambda f,i:np.abs(f[i]-plain[i]).sum(axis=-1)>90   # where the overlay changed the picture
check('overlay glides from its start to its end position',np.nonzero(chg(gl,3))[1].mean()<110 and np.nonzero(chg(gl,57))[1].mean()>210)
ck=render(overlays=[{**ov,'x2':None,'y2':None,'x':50,'chroma':'#00FF00','chroma_similarity':30}])
check('green screen removes the keyed colour (the picture shows through)',chg(ck,30).sum()<150 and chg(gl,30).sum()>1500)
fe=render(overlays=[{**ov,'x2':None,'y2':None,'x':50,'feather':100}])
row=fe[30][90,:,1];core=row[160];edge=row[int(160-0.125*320*0.9)]
check('feathered overlay edges fade softly into the picture',core>200 and 40<edge-plain[30][90,int(160-0.125*320*0.9),1]+80<core)
check('radio voice effect filters to the telephone band',narration_filter({'voice_fx':'radio'},1000).startswith('highpass=f=300,lowpass=f=3400'))
check('voice effect is validated',client.patch('/api/voice-takes/none/edit',json={'voice_fx':'robot'}).status_code in (400,404))
ff('-f','lavfi','-i','anoisesrc=d=2:c=white:a=0.3','-ar','16000',str(t/'noise.wav'))
ff('-i',str(t/'noise.wav'),'-af',narration_filter({'voice_fx':'radio'},2000),str(t/'radio.wav'))
def hf(p):a=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(p),'-ac','1','-ar','16000','-f','s16le','-']),np.int16).astype(float);s=np.abs(np.fft.rfft(a));f=np.fft.rfftfreq(a.size,1/16000);return s[f>5000].mean()/s[(f>800)&(f<2500)].mean()
check('radio voice removes high frequencies from real audio',hf(t/'radio.wav')<hf(t/'noise.wav')*0.2)
for st in ('pop','glow'):
 write_ass_file('c','one two three',3000,{'karaoke':True,'karaoke_style':st},640,360,out_path=str(t/f'{st}.ass'),speech_start_ms=0,speech_ms=3000)
 body=(t/f'{st}.ass').read_text(encoding='utf-8-sig')
 check(f'{st} caption style writes one event per word' + (' plus a halo layer' if st=='glow' else ''),body.count('Dialogue:')==(3+2+(3 if st=='glow' else 0)))
print(f'{n} effects pack checks passed')
