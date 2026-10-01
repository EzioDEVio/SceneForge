"""Video subject cutout ("text behind a moving subject"): real u2netp model, real FFmpeg.

A synthetic clip (bright disc moving left -> right over a busy, slightly noisy
background) gets a title; after the cutout job + render the disc covers the title
where it is, the title stays visible elsewhere, and the layer's matte matches the
ground-truth disc (IoU). Also: rejections, estimate, cancel, cache reuse.

Uses SCENEFORGE_CUTOUT_MODEL_DIR when set (CI downloads u2netp from GitHub releases
on first use, like test_cutout.py); skips only when github.com is unreachable."""
import os,pathlib,subprocess,sys,tempfile,time
import numpy as np
root=pathlib.Path(__file__).resolve().parents[2]
tmp=tempfile.TemporaryDirectory();os.environ['SCENEFORGE_DATA_DIR']=tmp.name
t=pathlib.Path(tmp.name)
os.environ.setdefault('SCENEFORGE_CUTOUT_MODEL_DIR',str(t/'models'))
sys.path.insert(0,str(root/'backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.render import cutout, video_cutout
n=0
def check(name,ok,detail=''):
 global n
 assert ok,f'{name} {detail}'
 n+=1;print('PASS '+name+(f' ({detail})' if detail else ''),flush=True)

try:
 cutout.ensure_model('u2netp')
except cutout.CutoutError as e:
 import requests
 try:requests.head('https://github.com',timeout=10);reachable=True
 except Exception:reachable=False
 if not reachable:
  print(f'SKIP test_video_cutout: github.com is unreachable, so the u2netp model cannot be downloaded ({e})');sys.exit(0)
 raise

# --- synthetic clip: 640x360, 30 fps, 2 s; disc radius 60 moving x 150 -> 490 at y 180 ---------
W,H,FPS,N,R=640,360,30,60,60
rng=np.random.default_rng(7)
bg=np.zeros((H,W,3),np.uint8)
for _ in range(260):                      # busy background: random blocks, no yellow, not white
 x,y=rng.integers(0,W),rng.integers(0,H);w,h=rng.integers(10,70),rng.integers(10,50)
 c=rng.integers(20,170,3);c[2]=max(c[2],120) if c[0]>140 and c[1]>140 else c[2]
 bg[y:y+h,x:x+w]=c
cx=lambda i:150+340*i/(N-1)
yy,xx=np.mgrid[:H,:W]
def gt(i,scale=1):
 return ((xx*1.0-cx(i))**2+(yy-180.0)**2)<R*R
ff=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-',
                     '-c:v','libx264','-crf','14','-pix_fmt','yuv420p',str(t/'mover.mp4')],stdin=subprocess.PIPE)
for i in range(N):
 f=bg.astype(np.int16)+rng.integers(-6,7,(H,W,1))
 f[gt(i)]=(245,245,250)
 ff.stdin.write(np.clip(f,0,255).astype(np.uint8).tobytes())
ff.stdin.close();assert ff.wait()==0
sub=lambda *a:subprocess.run(['ffmpeg','-v','error','-y',*a],check=True,capture_output=True)
sub('-f','lavfi','-i','color=c=0x405060:s=64x36:d=21:r=30','-pix_fmt','yuv420p',str(t/'long.mp4'))
from PIL import Image;Image.fromarray(bg).save(t/'still.png')

client=TestClient(app).__enter__()
p=client.post('/api/projects',json={'title':'Video cutout','aspect':'16:9','fps':30}).json();pid=p['id']
up=lambda f:client.post('/api/assets/upload',params={'project_id':pid},files={'file':(f,open(t/f,'rb'))}).json()
mover,long_,still=up('mover.mp4'),up('long.mp4'),up('still.png')
sid=client.get(f'/api/projects/{pid}').json()['scenes'][0]['id']
proj=client.get(f'/api/projects/{pid}').json()
FW,FH=proj['width'],proj['height']
S=FW/W                                    # cover fit scale (16:9 clip on a 16:9 canvas)
url=f'/api/scenes/{sid}/subject-video-layer'

# --- rejections ------------------------------------------------------------------------------
r=client.post(url,json={'model':'u2netp'})
check('needs media',r.status_code==400 and 'video' in r.json()['detail'])
shot=client.post(f'/api/scenes/{sid}/shots',json={'asset_id':still['id']}).json()
r=client.post(url,json={'model':'u2netp'})
check('still image scene is sent to the still cutout',r.status_code==400 and 'still image' in r.json()['detail'])
client.delete(f"/api/scenes/shots/{shot['id']}")
lshot=client.post(f'/api/scenes/{sid}/shots',json={'asset_id':long_['id']}).json()
r=client.post(url,json={'model':'u2netp'})
check('clips longer than 20 s are rejected with a clear message',r.status_code==400 and '20 s' in r.json()['detail'] and '21.0 s' in r.json()['detail'],r.json()['detail'])
est=client.get(url).json()
check('estimate reports why a scene is not eligible',est['ok'] is False and '20 s' in est['reason'])
client.delete(f"/api/scenes/shots/{lshot['id']}")
shot=client.post(f'/api/scenes/{sid}/shots',json={'asset_id':mover['id']}).json()
s2=client.post(f'/api/scenes/{sid}/shots',json={'asset_id':mover['id']}).json()
r=client.post(url,json={'model':'u2netp'})
check('two media items are rejected',r.status_code==400 and 'one video' in r.json()['detail'])
client.delete(f"/api/scenes/shots/{s2['id']}")
for patch,word in (({'speed':{'speed':2}},'speed'),({'speed':{'speed':1,'ramp':'bullet'}},'speed'),({'speed':{'speed':1,'freeze_at_ms':500,'freeze_ms':500}},'freeze'),({'motion':{'type':'zoom_in'}},'Static')):
 client.patch(f"/api/scenes/shots/{shot['id']}",json=patch)
 r=client.post(url,json={'model':'u2netp'})
 check(f'rejects {list(patch)[0]} {list(patch.values())[0]}',r.status_code==400 and word in r.json()['detail'],r.json().get('detail'))
 client.patch(f"/api/scenes/shots/{shot['id']}",json={'speed':{'speed':1},'motion':{'type':'static'}})
r=client.patch(f'/api/scenes/{sid}',json={'look':{'shake':{'amount':40}}})
assert r.status_code==200,r.text
r=client.post(url,json={'model':'u2netp'})
check('rejects camera shake',r.status_code==400 and 'camera shake' in r.json()['detail'])
assert client.patch(f'/api/scenes/{sid}',json={'look':{'shake':None}}).json()['look_json'].get('shake') is None

# --- control render: title over the subject ---------------------------------------------------
client.patch(f'/api/scenes/{sid}',json={'timing_mode':'fixed','requested_duration_ms':2000,
  'font':{'captions_enabled':False,'layers':[{'id':'t1','kind':'text','text':'HHHHHHHHHHHHHHHHHHHHHHHH','family':'Anton','size':200,'color':'#FFFF00','x':50,'y':50,'box_width':100,'animation':'none'}]}})
def render():
 j=client.post(f'/api/scenes/{sid}/render').json()
 while (s:=client.get(f"/api/jobs/{j['job_id']}").json())['status'] not in('succeeded','failed','cancelled'):time.sleep(.2)
 assert s['status']=='succeeded',s
 aid=client.get(f'/api/projects/{pid}').json()['scenes'][0]['rendered_asset_id']
 path=t/f'r{time.time_ns()}.mp4';path.write_bytes(client.get(f'/api/assets/{aid}/stream').content)
 raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-vf',f'scale={W}:{H}','-f','rawvideo','-pix_fmt','rgb24','-'])
 return np.frombuffer(raw,np.uint8).reshape(-1,H,W,3).astype(int)
yellow=lambda f:(f[...,0]>200)&(f[...,1]>200)&(f[...,2]<110)
band=slice(152,208)                       # rows the title covers (at 640x360)
def inside(i):                            # columns well inside the disc, within the title band
 c=int(cx(i));return slice(c-35,c+35)
def outside(i):
 c=int(cx(i));return np.r_[10:max(11,c-R-15),min(W-11,c+R+15):W-10]
frames=render()
for i in (15,45):
 check(f'control frame {i}: title drawn over the subject without a cutout',yellow(frames[i][band,inside(i)]).sum()>400)

est=client.get(url,params={'model':'u2netp'}).json()
check('estimate: frames, ms/frame and total time for a 2 s clip',est['ok'] and est['frames']==N and est['ms_per_frame']>0 and est['estimate_s']>=1,est)
check('estimate for IS-Net is slower than u2netp',client.get(url,params={'model':'isnet'}).json()['ms_per_frame']>est['ms_per_frame'])

# --- cancel ---------------------------------------------------------------------------------------
media=pathlib.Path(tmp.name)
r=client.post(url,json={'model':'u2netp','edge':'crisp'}).json()
check('starts a background job',r['status']=='running' and r['job_id'] and r['frames']==N)
jid=r['job_id']
check('a second request for the same scene returns the running job',client.post(url,json={'model':'u2netp','edge':'crisp'}).json()['job_id']==jid)
deadline=time.time()+120
while (st:=client.get(f'/api/cutout/video-jobs/{jid}').json())['frames_done']<3 and st['status'] in('queued','running'):
 assert time.time()<deadline;time.sleep(.1)
check('progress reports frames done / total',st['frames_total']==N and 3<=st['frames_done']<N,st)
check('cancel accepted',client.post(f'/api/jobs/{jid}/cancel').status_code==200)
while (st:=client.get(f'/api/cutout/video-jobs/{jid}').json())['status'] in('queued','running','cancelling'):time.sleep(.1)
check('cancelled job ends as cancelled',st['status']=='cancelled' and client.get(f'/api/jobs/{jid}').json()['status']=='cancelled',st)
scene=client.get(f'/api/projects/{pid}').json()['scenes'][0]
check('cancel adds no overlay and leaves no partial layer file',not any(o['kind']=='subject' for o in scene['overlays_json'])
      and not list(media.rglob('subject_video_*')))

# --- full run ----------------------------------------------------------------------------------------
t0=time.time()
r=client.post(url,json={'model':'u2netp'}).json();jid=r['job_id']
while (st:=client.get(f'/api/cutout/video-jobs/{jid}').json())['status'] in('queued','running'):time.sleep(.2)
el=time.time()-t0
check('cutout job succeeds',st['status']=='succeeded' and st['frames_done']==N,st)
print(f'INFO u2netp {FW}x{FH}: {st["ms_per_frame"]} ms/frame, {N} frames in {el:.1f} s, codec {st.get("codec")}')
scene=client.get(f'/api/projects/{pid}').json()['scenes'][0]
ov=[o for o in scene['overlays_json'] if o['kind']=='subject']
check('subject overlay added above text, full frame, timed from scene start to the layer end',len(ov)==1 and ov[0]['above_text'] is True and ov[0]['width']==100
      and ov[0]['start_ms']==0 and ov[0]['end_ms']==2000 and scene['is_stale'])
layer=client.get(f"/api/assets/{ov[0]['asset_id']}").json()
check('layer is a hidden video asset at frame size',layer['type']=='video' and layer['width']==FW and layer['height']==FH
      and not any(a['id']==layer['id'] for a in client.get('/api/assets',params={'project_id':pid}).json()))
lp=t/'layer.webm';lp.write_bytes(client.get(f"/api/assets/{layer['id']}/stream").content)
dec=['-c:v','libvpx-vp9'] if layer['mime']=='video/webm' else []
raw=subprocess.check_output(['ffmpeg','-v','error',*dec,'-i',str(lp),'-vf',f'scale={W}:{H}:flags=area','-f','rawvideo','-pix_fmt','rgba','-'])
la=np.frombuffer(raw,np.uint8).reshape(-1,H,W,4)[...,3]
check('layer has one frame per scene frame and real transparency',la.shape[0]==N and la[0].min()==0 and la[0].max()==255,la.shape)
ious=[]
for i in range(N):
 m=la[i]>127;g=gt(i)
 ious.append((m&g).sum()/max(1,(m|g).sum()))
ious=np.array(ious)
check('matte IoU vs ground-truth disc > 0.85 (u2netp)',ious.mean()>0.85 and ious.min()>0.7,f'mean {ious.mean():.3f} min {ious.min():.3f}')
flick=np.mean([np.abs(la[i].astype(int)-la[i-1].astype(int))[~(gt(i)|gt(i-1))].mean() for i in range(1,N)])
check('background stays transparent and steady (low flicker)',flick<2.0,f'mean abs change {flick:.2f}/255')

frames=render();cent={}
for i in (15,45):
 f=frames[i]
 check(f'frame {i}: no title pixels inside the moving subject (subject on top)',yellow(f[band,inside(i)]).sum()<30,yellow(f[band,inside(i)]).sum())
 check(f'frame {i}: title visible outside the subject',yellow(f[band][:,outside(i)]).sum()>800)
 white=(f[band,:,0]>215)&(f[band,:,1]>215)&(f[band,:,2]>215)
 xs=np.nonzero(white)[1]
 check(f'frame {i}: subject drawn where the disc is (x ≈ {cx(i):.0f})',len(xs)>1000 and abs(xs.mean()-cx(i))<12,f'{xs.mean():.1f}')
 cent[i]=xs.mean()
check('subject moved between the two sample times and the layer followed it',cent[45]-cent[15]>150,cent)

# --- cache --------------------------------------------------------------------------------------------
r=client.post(url,json={'model':'u2netp'}).json()
check('same settings reuse the cached layer instantly',r['status']=='done' and r['cached'] and r['overlay']['asset_id']==layer['id'])
check('measured speed replaces the built-in estimate',client.get(url,params={'model':'u2netp'}).json()['measured'] is True)
print(f'{n} checks passed')
