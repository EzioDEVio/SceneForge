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

# --- automatic captions from speech ----------------------------------------------------------
from app.providers import transcribe as tr
sc0=c.get(f'/api/projects/{vid}').json()['scenes'][1]
r=c.post(f"/api/scenes/{sc0['id']}/auto-captions",json={})
check('without an ElevenLabs/OpenAI key, auto captions explain what is needed',r.status_code==400 and 'key' in r.json()['detail'])
seen={}
def fake(db,path,provider='auto',language=None):
 seen['dur']=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',path]));seen['lang']=language
 return {'language':'ar','text':'مرحبا بكم في الأندلس','words':[['مرحبا',200,700],['بكم',800,1100],['في',1200,1400],['الأندلس',1500,2400]],'provider':'elevenlabs'}
tr.transcribe=fake
r=c.post(f"/api/scenes/{sc0['id']}/auto-captions",json={'language':'ar'})
j=r.json()
check('auto captions transcribe the video clip sound and save text + word timing',r.status_code==200 and j['subtitle_text']=='مرحبا بكم في الأندلس' and j['font_json']['transcript']['source']=='clips' and j['font_json']['captions_enabled'] and abs(seen['dur']-3)<0.3 and seen['lang']=='ar')
from app.db.database import SessionLocal
from app.db.models import Scene as _S
from app.render.renderer import _caption_word_times
c.patch(f"/api/scenes/{sc0['id']}",json={'font':{'split':'phrases','phrase_words':2}})
with SessionLocal() as db:
 wt=_caption_word_times(db.get(_S,sc0['id']),0,None)
check('phrase captions use the transcript word times exactly',wt==[(200,700),(800,1100),(1200,1400),(1500,2400)])

# --- 9:16 polish -----------------------------------------------------------------------------
land=t/'land.mp4';subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=s=640x360:d=1:r=30','-c:v','libx264',str(land)],check=True)
la=c.post('/api/assets/upload',params={'project_id':vid},files={'file':('land.mp4',open(land,'rb'),'video/mp4')}).json()
tgt=c.get(f'/api/projects/{vid}').json()['scenes'][2]['id']
auto=c.post(f'/api/scenes/{tgt}/shots',json={'asset_id':la['id']}).json()
check('a landscape clip added to a 9:16 project keeps the whole picture over a blurred background',auto['fit']=='contain_blur')
explicit=c.post(f'/api/scenes/{tgt}/shots',json={'asset_id':la['id'],'fit':'cover'}).json()
check('an explicitly chosen fit is respected',explicit['fit']=='cover')
check('a portrait clip in a 9:16 project still fills the frame',c.get(f'/api/projects/{vid}').json()['scenes'][0]['shots'][0]['fit']=='cover')
from app.render.subtitles import write_ass_file
def mv(w,h):
 path=write_ass_file('m','hello',2000,{},w,h,out_path=str(t/'m.ass'))
 return int([x for x in pathlib.Path(path).read_text(encoding='utf-8-sig').splitlines() if x.startswith('Style:')][0].split(',')[21])
check('vertical captions sit above the TikTok/Reels/Shorts buttons (about 20 % up); landscape keeps 5.5 %',mv(1080,1920)==384 and mv(1920,1080)==59)
from app.render.filters import build_contain_chain
check('the blurred background is strong enough at 1080×1920',"gblur=sigma=48" in build_contain_chain(1080,1920,True))

# --- exports open everywhere (Windows Photos / Media Player) -----------------------------------
def probe_v(path):
 out=subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=profile,pix_fmt','-of','default=nw=1',str(path)],text=True)
 return dict(l.split('=',1) for l in out.strip().splitlines())
vs=c.get(f'/api/projects/{vid}').json()['scenes']
c.patch(f"/api/scenes/{vs[1]['id']}",json={'transition_in':{'type':'film_burn','duration_ms':500}})
check('the transition was applied for this check',c.get(f'/api/projects/{vid}').json()['scenes'][1]['transition_in_json']['type']=='film_burn')
for label,path in (('with a film burn transition',export_of(vid)),):
 info=probe_v(path);raw=open(path,'rb').read()
 check(f'export {label} is 4:2:0, not High 4:4:4, with fast start',info['pix_fmt']=='yuv420p' and '4:4:4' not in info['profile'] and raw.find(b'moov')<raw.find(b'mdat'))
c.patch(f"/api/scenes/{vs[1]['id']}",json={'transition_in':{'type':'cut','duration_ms':0}})
info=probe_v(out:=export_of(vid));raw=open(out,'rb').read()
check('export with plain cuts is 4:2:0 with fast start',info['pix_fmt']=='yuv420p' and raw.find(b'moov')<raw.find(b'mdat'))

# --- new transitions render in a real export --------------------------------------------------
from app.render.renderer import XFADE_NAMES
new=['slide_up','slide_down','smooth_up','smooth_down','wipe_up','wipe_down','cover_left','cover_right','reveal_left','reveal_right','vert_open','vert_close','diagonal_tr','rect_crop','distance','slice_vertical','wind_up','squeeze_v']
check('18 new transitions are mapped to FFmpeg',all(k in XFADE_NAMES for k in new))
bad=[]
for k in new:
 xf=XFADE_NAMES[k]
 r=subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=red:s=160x90:d=1:r=30','-f','lavfi','-i','color=blue:s=160x90:d=1:r=30','-filter_complex',f'[0][1]xfade=transition={xf}:duration=0.5:offset=0.4','-f','null','-'],capture_output=True,text=True)
 if r.returncode: bad.append(k)
check(f'every new transition renders with the bundled FFmpeg {bad or ""}',not bad)
c.patch(f"/api/scenes/{vs[1]['id']}",json={'transition_in':{'type':'cover_left','duration_ms':500}})
out=export_of(vid)
dur_ct=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(out)]))
# scenes: 3 s countdown + 3 s clip, 3 s clip, 3 s + 2×1 s clips; minus 0.5 s transition overlap
check(f'an export with a new transition (Cover left) has the right length ({dur_ct:.2f} s = 13.5 s)',abs(dur_ct-13.5)<0.3)

# --- multi-select: copy settings to several scenes --------------------------------------------
vs=c.get(f'/api/projects/{vid}').json()['scenes']
src,t1,t2=vs[0]['id'],vs[1]['id'],vs[2]['id']
c.patch(f'/api/scenes/{t1}',json={'subtitle_text':'target one text','look':{'annotations':[{'type':'box'}]}})
c.patch(f'/api/scenes/{src}',json={'effect_preset':'glow','look':{'film':{'scratches':40},'annotations':[{'type':'circle'},{'type':'arrow'}]},
 'font':{'family':'Anton','case':'upper','split':'phrases','layers':[{'id':'t','text':'TITLE','x':50,'y':20,'size':60,'color':'#FFFFFF','start_ms':0,'end_ms':0,'animation':'letters-pop'}]},
 'transition_in':{'type':'dissolve','duration_ms':400}})
check('apply-to validates its request',c.post(f'/api/scenes/{src}/apply-to',json={'targets':[t1],'parts':['everything']}).status_code==400)
r=c.post(f'/api/scenes/{src}/apply-to',json={'targets':[t1,t2],'parts':['effects','captions','titles','transition']}).json()
after={x['id']:x for x in c.get(f'/api/projects/{vid}').json()['scenes']}
a1=after[t1]
check('effects and look copy to the selected scenes, position-specific effects stay their own',r['changed']==2 and a1['effect_preset']=='glow' and a1['look_json']['film']['scratches']==40 and len(a1['look_json']['annotations'])==1 and a1['look_json']['annotations'][0]['type']=='box')
check('caption style copies but each scene keeps its own caption text',a1['font_json']['family']=='Anton' and a1['font_json']['case']=='upper' and a1['subtitle_text']=='target one text')
check('text overlays and transition copy too',a1['font_json']['layers'][0]['text']=='TITLE' and a1['transition_in_json']['type']=='dissolve' and after[t2]['font_json']['layers'][0]['animation']=='letters-pop')

# --- export settings (delivery) and caption files ----------------------------------------------
def export_with(settings):
 j=c.post(f'/api/projects/{vid}/export',json={'settings':settings}).json()
 assert 'job_id' in j,j
 while (st:=c.get(f"/api/jobs/{j['job_id']}").json())['status'] not in ('succeeded','failed'):time.sleep(0.5)
 assert st['status']=='succeeded',st.get('error','')[-600:]
 a=[x for x in c.get(f'/api/assets?project_id={vid}').json() if x['id']==st['artifact_asset_id']] if False else None
 out=t/f"dl_{time.time()}";data=c.get(f"/api/assets/{st['artifact_asset_id']}/stream");out.write_bytes(data.content);return out,data.headers.get('content-type','')
def vinfo(path):
 o=subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=codec_name,codec_tag_string,width,height,r_frame_rate,pix_fmt','-of','default=nw=1',str(path)],text=True)
 return dict(l.split('=',1) for l in o.strip().splitlines())
check('export settings are validated',c.post(f'/api/projects/{vid}/export',json={'settings':{'resolution':'8k'}}).status_code==400)
o,ct=export_with({'resolution':'720p','fps':24,'format':'mp4_h264','quality':'draft'});i=vinfo(o)
check('720p keeps the 9:16 shape (720×1280) at 24 fps, H.264 4:2:0',i['width']=='720' and i['height']=='1280' and i['r_frame_rate']=='24/1' and i['pix_fmt']=='yuv420p' and 'mp4' in ct)
o,_=export_with({'resolution':'720p','format':'mp4_h265','quality':'draft'});i=vinfo(o)
check('H.265 is tagged hvc1 so Apple and Windows players accept it',i['codec_name']=='hevc' and i['codec_tag_string']=='hvc1')
o,ct=export_with({'resolution':'720p','format':'webm','quality':'draft'});i=vinfo(o)
check('WebM uses VP9',i['codec_name']=='vp9' and 'webm' in ct)
o,_=export_with({'resolution':'720p','format':'mov_prores','quality':'draft'});i=vinfo(o)
check('MOV uses ProRes for further editing',i['codec_name']=='prores')
o,ct=export_with({'format':'gif','quality':'draft'})
check('animated GIF export',open(o,'rb').read(6) in (b'GIF89a',b'GIF87a') and 'gif' in ct)
o,ct=export_with({'format':'mp3','quality':'standard'})
check('audio-only MP3 export',subprocess.check_output(['ffprobe','-v','error','-select_streams','a:0','-show_entries','stream=codec_name','-of','csv=p=0',str(o)],text=True).strip()=='mp3' and 'audio' in ct)
srt=c.get(f'/api/projects/{vid}/captions?format=srt')
vtt=c.get(f'/api/projects/{vid}/captions?format=vtt')
check('caption files for the whole video (SRT and VTT)',srt.status_code==200 and '-->' in srt.text and srt.text.startswith('1\n') and vtt.text.startswith('WEBVTT') and 'attachment' in srt.headers.get('content-disposition',''))
print(f'{n} v0.6 checks passed')
