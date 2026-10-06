"""Real API, FFmpeg sample checks and timed colour-emoji rendering. No providers."""
import io,os,pathlib,sys,tempfile,subprocess,time
import numpy as np
from PIL import Image
ROOT=pathlib.Path(__file__).resolve().parents[2]
work=tempfile.TemporaryDirectory();os.environ['SCENEFORGE_DATA_DIR']=work.name
sys.path.insert(0,str(ROOT/'backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import SessionLocal
from app.db.models import Project
from app.render.audio_edit import clean_edit,narration_filter
from app.render.censor import clean_ranges
from app.render.fx_stack import stack_graph
n=0

def check(name,ok):
 global n
 assert ok,name;n+=1;print('PASS '+name,flush=True)

def wav(samples,name):
 p=pathlib.Path(work.name)/name
 subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=300:sample_rate=48000:duration=2',*samples,str(p)],check=True)
 return p

def pcm(p):
 return np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(p),'-f','f32le','-ac','1','-ar','48000','-']),dtype=np.float32)

def effect_frame(look):
 graph,label=stack_graph('0:v',look,160,90,25,.1,pathlib.Path(work.name)/'fx-cache')
 fc=';'.join([*graph,f'[{label}]format=rgb24[v]'])
 raw=subprocess.check_output(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=s=160x90:r=25:d=0.1','-filter_complex',fc,'-map','[v]','-frames:v','1','-f','rawvideo','-'])
 return np.frombuffer(raw,np.uint8).reshape(90,160,3)
original=effect_frame({})
for fx in ['vignette','letterbox','sharpen']:
 look={fx:{'amount':70}}
 check(f'{fx} changes rendered pixels',np.abs(effect_frame(look).astype(float)-original).mean()>.2)
 check(f'{fx} bypass preserves original pixels',np.array_equal(effect_frame({**look,'fx_bypass':[fx]}),original))

ranges=[{'start_ms':500,'end_ms':800,'mode':'bleep'},{'start_ms':1000,'end_ms':1300,'mode':'mute'}]
src=wav([],'source.wav');processed=wav(['-af',narration_filter(clean_edit({'censor':ranges},2000),2000)],'censored.wav')
a,b=pcm(src),pcm(processed)
check('outside ranges leaves original samples unchanged',np.max(np.abs(a[:23000]-b[:23000]))<.0001)
check('mute replaces original voice with silence',np.max(np.abs(b[49000:62000]))<.0001)
part=b[25000:37000];freq=np.fft.rfftfreq(len(part),1/48000);sp=np.abs(np.fft.rfft(part));check('bleep is 1000 Hz and original 300 Hz removed',abs(freq[np.argmax(sp)]-1000)<5 and sp[np.argmin(abs(freq-300))]<sp.max()*.01)
trimmed=wav(['-af',narration_filter(clean_edit({'in_ms':400,'censor':ranges},2000),1600)],'trim.wav');x=pcm(trimmed)
check('trim keeps censor ranges attached to source',np.max(np.abs(x[30000:42000]))<.0001)
for value in [[{'start_ms':-1,'end_ms':30}], [{'start_ms':100,'end_ms':110}], [{'start_ms':500,'end_ms':2100}], [{'start_ms':100,'end_ms':300},{'start_ms':200,'end_ms':400}], [{'start_ms':float('nan'),'end_ms':100}]]:
 try:clean_ranges(value,2000);ok=False
 except ValueError:ok=True
 check('invalid/overlapping censor range rejected',ok)
with TestClient(app) as c:
 p=c.post('/api/projects',json={'title':'Censor and emoji','aspect':'16:9','fps':25}).json();pid=p['id']
 with SessionLocal() as db:
  p=db.get(Project,pid);p.width=320;p.height=180;db.commit()
 sid=c.get('/api/projects/'+pid).json()['scenes'][0]['id'];img=Image.new('RGB',(320,180),'#809090');buf=io.BytesIO();img.save(buf,format='PNG')
 asset=c.post('/api/assets/upload?project_id='+pid,files={'file':('base.png',buf.getvalue(),'image/png')}).json();c.post('/api/scenes/'+sid+'/shots',json={'asset_id':asset['id']})
 take=c.post('/api/scenes/'+sid+'/voice-takes/upload',files={'file':('source.wav',src.read_bytes(),'audio/wav')}).json()
 r=c.patch('/api/voice-takes/'+take['id']+'/edit',json={'censor':ranges});check('narration censor saved by real API',r.status_code==200 and r.json()['edit_json']['censor']==ranges)
 clip={'id':'sound','asset_id':take['audio_asset_id'],'start_ms':0,'source_in_ms':0,'source_out_ms':2000,'volume':100,'fade_in_ms':0,'fade_out_ms':0,'censor':ranges}
 r=c.patch('/api/projects/'+pid,json={'finishing':{'audio_clips':[clip]}});check('timeline censor persists',r.status_code==200 and r.json()['finishing_json']['audio_clips'][0]['censor']==ranges)
 from app.render.caption_emoji import EMOJI_IDS,emoji_overlays
 from app.api.stickers import sticker,sticker_file
 check('all 322 bundled emoji are supported and files exist',len(EMOJI_IDS)==322 and all(sticker_file(sticker(key)).is_file() for key in EMOJI_IDS))
 expanded={'captions_enabled':True,'size':44,'caption_segments':[{'id':'expanded','text':'Smile','start_ms':0,'end_ms':500,'emoji':'grinning-face'}]}
 check('emoji beyond the original eight accepted by API',c.patch('/api/scenes/'+sid,json={'font':expanded}).status_code==200)
 overlays,emoji_assets=emoji_overlays(expanded,320,180,2000);check('expanded emoji supplies real render artwork',len(overlays)==1 and pathlib.Path(emoji_assets['grinning-face'].path).is_file())
 font={'captions_enabled':True,'size':44,'position':'middle','caption_segments':[{'id':'cap','text':'Hello','start_ms':500,'end_ms':1000,'emoji':'fire'}]}
 r=c.patch('/api/scenes/'+sid,json={'timing_mode':'fixed','requested_duration_ms':2000,'lead_ms':0,'trail_ms':0,'subtitle_text':'Hello','font':font,'look':{'vignette':{'amount':50},'letterbox':{'amount':50},'sharpen':{'amount':40}}});check('emoji and finishing effects accepted',r.status_code==200)
 for bad in ['../fire','unknown']:
  f={**font,'caption_segments':[{**font['caption_segments'][0],'emoji':bad}]};check('unknown emoji rejected',c.patch('/api/scenes/'+sid,json={'font':f}).status_code==400)
 for fx in ['vignette','letterbox','sharpen']:
  check('invalid effect amount rejected',c.patch('/api/scenes/'+sid,json={'look':{fx:{'amount':101}}}).status_code==400)
 job=c.post('/api/scenes/'+sid+'/render').json();jid=job['job_id']
 for _ in range(600):
  j=c.get('/api/jobs/'+jid).json()
  if j['status'] in ('succeeded','failed','cancelled'):break
  time.sleep(.1)
 check('scene with colour emoji, censor and new effects renders',j['status']=='succeeded')
 path=pathlib.Path(work.name)/'scene.mp4';path.write_bytes(c.get('/api/assets/'+j['artifact_asset_id']+'/stream').content)
 def frame(t):return np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-ss',str(t),'-i',str(path),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-']),np.uint8).reshape(180,320,3)
 before,during,after=frame(.2),frame(.7),frame(1.2)
 check('emoji appears only in its caption span',np.count_nonzero((during[:,:,0].astype(float)>during[:,:,1]*1.3)&(during[:,:,0].astype(float)>during[:,:,2]*1.6)&(during[:,:,0]>100))>15 and np.abs(after.astype(float)-before).mean()<3)
 check('cinema bars render black within unchanged dimensions',before[:14].mean()<3 and before.shape==(180,320,3))
 audio=pcm(path);check('scene rendered censorship mutes narration interval',np.max(np.abs(audio[51000:59000]))<.005)

 # Full export checks the project audio path, including source trim.
 c.post('/api/scenes/'+sid+'/voice-takes/clear-selection')
 r=c.patch('/api/projects/'+pid,json={'finishing':{'audio_clips':[{**clip,'source_in_ms':400,'source_out_ms':1800}]}})
 check('trimmed timeline censorship accepted',r.status_code==200)
 job=c.post('/api/projects/'+pid+'/export?skip_empty=true').json();jid=job['job_id']
 for _ in range(600):
  j=c.get('/api/jobs/'+jid).json()
  if j['status'] in ('succeeded','failed','cancelled'):break
  time.sleep(.1)
 check('full export with censored timeline audio succeeds',j['status']=='succeeded')
 export=pathlib.Path(work.name)/'export.mp4';export.write_bytes(c.get('/api/assets/'+j['artifact_asset_id']+'/stream').content)
 signal=pcm(export);check('timeline export mutes original source-clock interval after trim',np.max(np.abs(signal[30000:41000]))<.005)
 # Video sound is censored before speed conversion.
 movie=pathlib.Path(work.name)/'video.mp4'
 subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=blue:s=160x90:r=25:d=2','-i',str(src),'-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(movie)],check=True)
 video=c.post('/api/assets/upload?project_id='+pid,files={'file':('video.mp4',movie.read_bytes(),'video/mp4')}).json()
 sid2=c.get('/api/projects/'+pid).json()['scenes'][1]['id'];shot=c.post('/api/scenes/'+sid2+'/shots',json={'asset_id':video['id']}).json()
 c.patch('/api/scenes/'+sid2,json={'timing_mode':'fixed','requested_duration_ms':2000,'font':{'captions_enabled':False}})
 r=c.patch('/api/scenes/shots/'+shot['id'],json={'audio':{'censor':ranges,'duck':False}});check('video sound censorship saved',r.status_code==200 and r.json()['audio_json']['censor']==ranges)
 check('invalid video censor rejected',c.patch('/api/scenes/shots/'+shot['id'],json={'audio':{'censor':[{'start_ms':0,'end_ms':2500}]}}).status_code==400)
 jid=c.post('/api/scenes/'+sid2+'/render').json()['job_id']
 for _ in range(600):
  j=c.get('/api/jobs/'+jid).json()
  if j['status'] in ('succeeded','failed','cancelled'):break
  time.sleep(.1)
 check('video sound censorship renders',j['status']=='succeeded')
 videoout=pathlib.Path(work.name)/'videoout.mp4';videoout.write_bytes(c.get('/api/assets/'+j['artifact_asset_id']+'/stream').content)
 check('video embedded sound mute is silent',np.max(np.abs(pcm(videoout)[51000:59000]))<.005)

 det=c.post('/api/scenes/'+sid2+'/detach-audio',json={'source':'shot','shot_id':shot['id'],'duration_ms':2000});assert det.status_code==200,det.json();check('detaching censored video sound succeeds',True)
 detached=pathlib.Path(work.name)/'detached.wav';detached.write_bytes(c.get('/api/assets/'+det.json()['asset']['id']+'/stream').content);check('detached video sound retains censorship',np.max(np.abs(pcm(detached)[51000:59000]))<.005)
print(n,'censor, caption emoji and effect checks passed')
