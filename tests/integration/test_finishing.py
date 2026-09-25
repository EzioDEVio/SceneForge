"""Transitions, motion easing, word-by-word captions, projector sound,
countdown leader, background music ducking and YouTube loudness."""
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
from app.render.filters import ease_expr
from app.domain.constants import TransitionType
from app.render.subtitles import write_ass_file
n=0
def check(name,ok):
 global n
 assert ok,name
 n+=1;print('PASS '+name,flush=True)
def ff(*a):subprocess.run(['ffmpeg','-v','error','-y',*a],check=True,capture_output=True)
client=TestClient(app).__enter__()

# --- every transition type renders -----------------------------------------
types=[x.value for x in TransitionType if x.value!='cut']
check('every transition type maps to an FFmpeg xfade',all(tt in XFADE_NAMES for tt in types) and len(types)>=19)
failed=[]
for tt in types:
 r=subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=red:s=320x180:d=2:r=30','-f','lavfi','-i','color=c=blue:s=320x180:d=2:r=30','-filter_complex',f"[0][1]xfade=transition={XFADE_NAMES[tt]}:duration=1:offset=0.5,format=yuv420p",'-f','null','-'],capture_output=True)
 if r.returncode:failed.append(tt)
check('all transitions render, including film burn: '+(','.join(failed) or 'none failed'),not failed)
ff('-f','lavfi','-i','color=c=0x303030:s=320x180:d=2:r=30','-f','lavfi','-i','color=c=0x303030:s=320x180:d=2:r=30','-filter_complex',f"[0][1]xfade=transition={XFADE_NAMES['film_burn']}:duration=1:offset=0.5,format=rgb24",str(t/'burn.mp4'))
raw=subprocess.check_output(['ffmpeg','-v','error','-ss','1.0','-i',str(t/'burn.mp4'),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'])
mid=np.frombuffer(raw,np.uint8).reshape(180,320,3).astype(float).reshape(-1,3).max(axis=0)
check('film burn flares hot orange mid-transition',mid[0]>200 and mid[0]>mid[2]+60)

# --- easing ----------------------------------------------------------------
def ev(expr,x):return eval(expr.replace('(n/99)',str(x)).replace('PI','np.pi').replace('cos','np.cos'))
check('ease-in-out starts and ends gently, linear does not',abs(ev(ease_expr('(n/99)','ease_in_out'),0.1)-0.0245)<0.002 and ev(ease_expr('(n/99)','linear'),0.1)==0.1 and abs(ev(ease_expr('(n/99)','ease_in_out'),0.5)-0.5)<1e-9)

# --- word-by-word captions ---------------------------------------------------
ass=write_ass_file('s','In the year 711 a small force crossed',6000,{'karaoke':True,'highlight_color':'#FF0000','color':'#FFFFFF','size':40},640,360,out_path=str(t/'k.ass'),speech_start_ms=1000,speech_ms=4000)
body=pathlib.Path(ass).read_text(encoding='utf-8-sig').split('[Events]')[1]
ks=[int(x) for x in re.findall(r'\\k(\d+)',body)]
check('captions get one timed \\k per word after the lead-in',ks[0]==100 and len(ks)==1+8 and abs(sum(ks[1:])-400)<=8)
def cap(t_):
 raw=subprocess.check_output(['ffmpeg','-v','error','-f','lavfi','-i','color=c=black:s=640x360:d=6','-vf',f"ass={ass}:fontsdir={root/'assets'/'fonts'}",'-ss',str(t_),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'])
 a=np.frombuffer(raw,np.uint8).reshape(360,640,3).astype(int);ink=a.max(axis=2)>150
 return (np.sum((a[...,0]>150)&(a[...,1]<90)&ink),np.sum((a[...,1]>150)&ink))
early,late=cap(0.5),cap(4.8)
check('spoken words turn to the highlight colour over time',early[0]==0 and early[1]>0 and late[0]>early[0]+200)

# measured word timing: speech 1.5 s, pause 1 s, speech 1.5 s inside a 9.8 s fixed scene
from app.render.word_timing import voiced_segments
import itertools
ff('-f','lavfi','-i','sine=f=300:d=1.5','-f','lavfi','-i','anullsrc=r=44100:cl=mono:d=1','-f','lavfi','-i','sine=f=300:d=1.5','-filter_complex','[0][1][2]concat=n=3:v=0:a=1',str(t/'sp.wav'))
segs=voiced_segments(str(t/'sp.wav'))
check('speech and pauses are found in the narration audio',len(segs)==2 and abs(segs[0][1]-1500)<=40 and abs(segs[1][0]-2500)<=40)
write_ass_file('w','one two three four five six',9800,{'karaoke':True},640,360,out_path=str(t/'w.ass'),speech_start_ms=250,speech_ms=4000,speech_segments=[(a+250,b+250) for a,b in segs])
st=list(itertools.accumulate(int(x) for x in re.findall(r'\\k(\d+)',(t/'w.ass').read_text(encoding='utf-8-sig'))))
check('highlight waits through the pause and ends with the voice, not the 9.8 s scene',abs(st[3]-275)<=3 and abs(st[-1]-425)<=3)

# --- project with narration for export checks --------------------------------
p=client.post('/api/projects',json={'title':'Finish','aspect':'16:9'}).json();pid=p['id']
ff('-f','lavfi','-i','testsrc2=s=640x360','-frames:v','1',str(t/'a.png'))
img=client.post('/api/assets/upload',params={'project_id':pid},files={'file':('a.png',open(t/'a.png','rb'))}).json()
ff('-f','lavfi','-i','sine=f=500:d=2','-af','volume=0.3','-ar','48000',str(t/'voice.wav'))           # narration 2 s
ff('-f','lavfi','-i','sine=f=220:d=3','-ar','48000','-ac','2',str(t/'music.wav'))                      # music bed
music=client.post('/api/assets/upload',params={'project_id':pid},files={'file':('music.wav',open(t/'music.wav','rb'))}).json()
sc=client.get(f'/api/projects/{pid}').json()['scenes']
s1,s2=sc[0]['id'],sc[1]['id']
for s in (s1,s2):client.post(f'/api/scenes/{s}/shots',json={'asset_id':img['id']})
take=client.post(f'/api/scenes/{s1}/voice-takes/upload',files={'file':('voice.wav',open(t/'voice.wav','rb'))}).json()
client.post(f"/api/voice-takes/{take['id']}/select")
client.patch(f'/api/scenes/{s1}',json={'timing_mode':'audio_driven','lead_ms':0,'trail_ms':0})
client.patch(f'/api/scenes/{s2}',json={'timing_mode':'fixed','requested_duration_ms':3000,'transition_in':{'type':'film_burn','duration_ms':600}})
for s in sc[2:]:client.delete(f"/api/scenes/{s['id']}")
shot=client.get(f'/api/projects/{pid}').json()['scenes'][0]['shots'][0]['id']
check('motion easing is validated',client.patch(f'/api/scenes/shots/{shot}',json={'motion':{'type':'zoom_in','easing':'bouncy'}}).status_code==400 and client.patch(f'/api/scenes/shots/{shot}',json={'motion':{'type':'zoom_in','easing':'ease_in'}}).status_code==200)
def export():
 j=client.post(f'/api/projects/{pid}/export',params={'skip_empty':'true'}).json()
 while (s:=client.get(f"/api/jobs/{j['job_id']}").json())['status'] not in('succeeded','failed','cancelled'):time.sleep(.3)
 assert s['status']=='succeeded',s
 path=t/f'export_{time.time_ns()}.mp4';path.write_bytes(client.get(f"/api/assets/{s['artifact_asset_id']}/stream").content);return path
def audio(path):return np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-ac','1','-ar','8000','-f','s16le','-']),np.int16).astype(float)/32768
def rms(a,s,e):return float(np.sqrt(np.mean(a[int(s*8000):int(e*8000)]**2)))
def dur(path):return float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(path)]))
base=export();d0=dur(base)
check('export with a film burn transition succeeds (2 s + 3 s - 0.6 s)',abs(d0-4.4)<0.15)
# settings validation
for bad in ({'music':{'asset_id':img['id']}},{'leader':'yes'},{'extra':1}):
 check('finishing rejects '+str(bad)[:30],client.patch(f'/api/projects/{pid}',json={'finishing':bad}).status_code==400)
r=client.patch(f'/api/projects/{pid}',json={'finishing':{'music':{'asset_id':music['id'],'volume':60,'duck':90,'fade_in_ms':0,'fade_out_ms':0}}})
check('music settings save on the project',r.status_code==200 and r.json()['finishing_json']['music']['duck']==90)
mixed=audio(export())
check('music plays under the whole video (loops past its 3 s length)',rms(mixed,3.6,4.2)>0.02 and rms(audio(base),3.6,4.2)<0.005)
check('music ducks under narration',rms(mixed,0.5,1.5)<rms(mixed,3.0,4.0))
client.patch(f'/api/projects/{pid}',json={'finishing':{'music':{'asset_id':music['id'],'volume':60,'duck':90,'fade_in_ms':0,'fade_out_ms':0},'loudnorm':True}})
lvl=export()
out=subprocess.run(['ffmpeg','-hide_banner','-i',str(lvl),'-af','ebur128','-f','null','-'],capture_output=True,text=True).stderr
I=float(re.findall(r'I:\s+(-?[\d.]+) LUFS',out)[-1])
check(f'loudness levelled for YouTube (measured {I:.1f} LUFS, target -14)',abs(I+14)<2.0)
client.patch(f'/api/projects/{pid}',json={'finishing':{'leader':True}})
led=export()
check('countdown leader adds 5 s at the start',abs(dur(led)-d0-5)<0.15)
fr=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-ss','0.5','-i',str(led),'-frames:v','1','-vf','scale=320:180','-f','rawvideo','-pix_fmt','gray','-']),np.uint8)
la=audio(led);beep=rms(la,3.0,3.04)
check('leader shows the countdown and has the 2-pop beep at 3 s',80<fr.mean()<200 and beep>0.05 and rms(la,1.0,2.9)<0.01)
# projector sound on an Old film scene
client.patch(f'/api/projects/{pid}',json={'finishing':{}})
client.patch(f'/api/scenes/{s2}',json={'look':{'film':{'scratches':0,'dust':0,'flicker':0,'weave':0,'sound':80,'fps':18,'tone':'color'}}})
pa=audio(export())
seg=pa[int(2.6*8000):int(4.2*8000)];env=np.convolve(np.abs(seg),np.ones(80)/80,'same')   # 10 ms loudness envelope
spec=np.abs(np.fft.rfft(env-env.mean()));fq=np.fft.rfftfreq(env.size,1/8000)
band=(fq>5)&(fq<45)
check('projector sound clatters at the film frame rate (18 per second)',rms(pa,2.6,4.2)>0.02 and abs(fq[band][spec[band].argmax()]-18)<1.5)
print(f'{n} finishing checks passed')
