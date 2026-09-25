"""Picture-in-picture overlays verified on real renders through the API."""
import os,pathlib,sys,tempfile,subprocess,time
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
p=client.post('/api/projects',json={'title':'PiP','aspect':'16:9'}).json();pid=p['id']
Image.fromarray(np.full((360,640,3),(20,40,90),np.uint8)).save(t/'bg.png')            # dark blue background
Image.fromarray(np.full((300,400,3),(230,40,40),np.uint8)).save(t/'red.png')          # red 4:3 picture
ff('-f','lavfi','-i','color=c=0x20c020:s=320x180:d=1:r=30','-pix_fmt','yuv420p',str(t/'green.mp4'))  # 1 s green video
up=lambda f:client.post('/api/assets/upload',params={'project_id':pid},files={'file':(f,open(t/f,'rb'))}).json()
bg,red,green=up('bg.png'),up('red.png'),up('green.mp4')
sid=client.get(f'/api/projects/{pid}').json()['scenes'][0]['id']
client.post(f'/api/scenes/{sid}/shots',json={'asset_id':bg['id']})
client.patch(f'/api/scenes/{sid}',json={'timing_mode':'fixed','requested_duration_ms':3000})
bad=[({'asset_id':'nope'},'missing media'),({'asset_id':red['id'],'width':150},'width over 100'),({'asset_id':red['id'],'anim_in':'spin'},'unknown animation'),
     ({'asset_id':red['id'],'start_ms':2000,'end_ms':1000},'end before start'),({'asset_id':red['id'],'border_color':'red'},'bad colour'),({'asset_id':red['id'],'glow':1},'unknown setting')]
for body,why in bad:
 check('overlay rejects '+why,client.patch(f'/api/scenes/{sid}',json={'overlays':[body]}).status_code==400)
check('at most 8 overlays per scene',client.patch(f'/api/scenes/{sid}',json={'overlays':[{'asset_id':red['id']}]*9}).status_code==400)
def render():
 j=client.post(f'/api/scenes/{sid}/render').json()
 while (s:=client.get(f"/api/jobs/{j['job_id']}").json())['status'] not in('succeeded','failed','cancelled'):time.sleep(.2)
 assert s['status']=='succeeded',s
 aid=client.get(f'/api/projects/{pid}').json()['scenes'][0]['rendered_asset_id']
 path=t/f'r{time.time_ns()}.mp4';path.write_bytes(client.get(f'/api/assets/{aid}/stream').content)
 raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-vf','scale=640:360','-f','rawvideo','-pix_fmt','rgb24','-'])
 return np.frombuffer(raw,np.uint8).reshape(-1,360,640,3).astype(int)
def red_mask(f):return (f[...,0]>170)&(f[...,1]<90)&(f[...,2]<90)
def any_mask(f):return np.abs(f-np.array([20,40,90])).sum(axis=-1)>45   # anything that is not background (also mid-fade)
# static card: centre (50%,50%), 40% wide, white border, rounded, no animation
ov={'asset_id':red['id'],'x':50,'y':50,'width':40,'border':8,'border_color':'#FFFFFF','radius':20,'shadow':0,'anim_in':'none','anim_out':'none'}
r=client.patch(f'/api/scenes/{sid}',json={'overlays':[ov]})
check('overlay saves on the scene and marks it for re-render',r.status_code==200 and r.json()['overlays_json'][0]['width']==40 and r.json()['is_stale'])
f=render()[45]
ys,xs=np.nonzero(red_mask(f))
check('overlay is centred where placed',abs(xs.mean()-320)<4 and abs(ys.mean()-180)<4)
check('overlay width follows the setting (40% of frame, 4:3 aspect kept)',abs((xs.max()-xs.min())-256)<10 and abs((ys.max()-ys.min())-192)<10)
white=(f.min(axis=2)>215)
check('white border surrounds the picture',white[180,xs.min()-4:xs.min()].any() and white[180,xs.max()+1:xs.max()+5].any() and white[ys.min()-4:ys.min(),320].any() and not white[180,xs.min()-12])
corner=f[ys.min()+2,xs.min()+2];
check('corners are rounded (corner pixel is border, not picture)',not red_mask(corner[None,None,:])[0,0])
# rotation
client.patch(f'/api/scenes/{sid}',json={'overlays':[{**ov,'rotation':30,'border':0,'radius':0}]})
f=render()[45];ys,xs=np.nonzero(red_mask(f))
top=xs[ys==ys.min()].mean()
check('rotation tilts the picture',abs(top-320)>40)
# timing and fade animation
client.patch(f'/api/scenes/{sid}',json={'overlays':[{**ov,'start_ms':1000,'end_ms':2000,'anim_in':'fade','anim_out':'none','anim_ms':500}]})
fr=render()
check('overlay only appears inside its time span',red_mask(fr[15]).sum()==0 and red_mask(fr[75]).sum()==0 and red_mask(fr[55]).sum()>30000)
mid=fr[37][180,320];full=fr[55][180,320]
check('fade in: half way through the fade the picture is partly transparent',60<mid[0]<200 and full[0]>200)
# slide in from the right
client.patch(f'/api/scenes/{sid}',json={'overlays':[{**ov,'anim_in':'slide_left','anim_out':'none','anim_ms':1000}]})
fr=render();x1=np.nonzero(any_mask(fr[8]))[1].mean();x2=np.nonzero(red_mask(fr[45]))[1].mean()
check('slide in moves the picture into place from the right',x1>x2+40 and abs(x2-320)<5)
# zoom pop
client.patch(f'/api/scenes/{sid}',json={'overlays':[{**ov,'anim_in':'zoom','anim_out':'none','anim_ms':1000}]})
fr=render();w_early=np.ptp(np.nonzero(any_mask(fr[6]))[1]);w_late=np.ptp(np.nonzero(red_mask(fr[45]))[1])
check('zoom pop grows the picture to full size',w_early<w_late*0.85 and abs(w_late-256)<10)
# opacity + video overlay looping + stacking order
client.patch(f'/api/scenes/{sid}',json={'overlays':[{**ov,'opacity':50},{**ov,'asset_id':green['id'],'x':25,'y':30,'width':30,'border':0,'radius':0}]})
fr=render()
px=fr[45][180,320]
check('opacity 50% blends with the background',90<px[0]<170 and px[2]>40)
g=lambda f:((f[...,1]>150)&(f[...,0]<90)).sum()
check('video overlay plays and loops past its 1 s length',g(fr[10])>5000 and g(fr[80])>5000)
client.patch(f'/api/scenes/{sid}',json={'overlays':[{**ov,'asset_id':green['id'],'x':50,'y':50,'width':30,'border':0},{**ov,'border':0}]})
f=render()[45]
check('later overlays stack on top',red_mask(f)[180,320])
print(f'{n} overlay checks passed')
