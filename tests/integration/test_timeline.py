"""Real-render motion, whole-frame glitch, transition identity and API validation."""
import os,pathlib,sys,tempfile,subprocess
from types import SimpleNamespace
import numpy as np
from PIL import Image
root=pathlib.Path(__file__).resolve().parents[2]
tmp=tempfile.TemporaryDirectory();os.environ['SCENEFORGE_DATA_DIR']=tmp.name
sys.path.insert(0,str(root/'backend'))
from app.render.filters import build_shot_video_chain
from app.render.renderer import render_export,RenderContext
from app.render.ffmpeg_utils import probe
from fastapi.testclient import TestClient
from app.main import app
n=0
def check(name,ok):
 global n
 assert ok,name
 n+=1;print('PASS '+name,flush=True)
def run(args):subprocess.run(['ffmpeg','-v','error','-y',*args],check=True,capture_output=True)
def frame(path,t):
 return np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-ss',str(t),'-i',str(path),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-']),dtype=np.uint8).reshape(180,320,3).astype(float)
t=pathlib.Path(tmp.name)
y,x=np.indices((360,640));a=np.stack([(x%70)*3,(y%70)*3,((x+y)%80)*3],axis=2).astype('uint8');Image.fromarray(a).save(t/'input.png')
for motion in ['diagonal_up','diagonal_down','push_left','pull_right']:
 graph,_=build_shot_video_chain('cover',{'type':motion},320,180,30,36,'original',100)
 out=t/(motion+'.mp4');run(['-loop','1','-i',str(t/'input.png'),'-filter_complex_threads','1','-filter_complex',graph,'-map','[vout]','-t','1.2','-pix_fmt','yuv420p',str(out)])
 check(motion+' changes framing over time',np.abs(frame(out,.1)-frame(out,1)).mean()>4)
graph,_=build_shot_video_chain('cover',{'type':'static'},320,180,30,36,'glitch',100)
out=t/'glitch.mp4';run(['-loop','1','-i',str(t/'input.png'),'-filter_complex_threads','1','-filter_complex',graph,'-map','[vout]','-t','1.2','-pix_fmt','yuv420p',str(out)])
diff=np.abs(frame(out,.1)-frame(out,.5))
for label,band in [('top',diff[:60]),('middle',diff[60:120]),('bottom',diff[120:])]:check('glitch changes '+label+' of frame',band.mean()>5)
for color in ['red','blue']:
 run(['-f','lavfi','-i',f'color={color}:s=320x180:r=30','-f','lavfi','-i','anullsrc=r=48000:cl=stereo','-t','2','-c:v','libx264','-c:a','aac',str(t/(color+'.mp4'))])
project=SimpleNamespace(id='fixture',fps=30,width=320,height=180)
scenes=[SimpleNamespace(id='red'),SimpleNamespace(id='blue')]
for transition,bright in [('fade_through_black',False),('fade_white',True)]:
 result=render_export(project,scenes,{c:str(t/(c+'.mp4')) for c in ['red','blue']},[{'type':transition,'duration_ms':1000}],RenderContext())
 mean=frame(result,1.5).mean()
 check(transition+' has correct midpoint',mean>220 if bright else mean<25)
 check(transition+' has expected overlap duration',abs(probe(result).duration_ms-3000)<100)
with TestClient(app) as c:
 p=c.post('/api/projects',json={'title':'timeline fixture'}).json()
 sid=c.get('/api/projects/'+p['id']).json()['scenes'][0]['id']
 for value in [-1,3001,'500',True]:
  check('invalid transition duration rejected: '+str(value),c.patch('/api/scenes/'+sid,json={'transition_in':{'type':'dissolve','duration_ms':value}}).status_code==400)
 check('new transition persists',c.patch('/api/scenes/'+sid,json={'transition_in':{'type':'wipe_left','duration_ms':600}}).json()['transition_in_json']=={'type':'wipe_left','duration_ms':600})
print(f'{n} timeline checks passed')
