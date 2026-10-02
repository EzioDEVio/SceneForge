"""Keyframe animation (overlays and text layers) on real FFmpeg renders, plus the
per-scene preview media that live timeline playback streams."""
import importlib.util,os,pathlib,subprocess,sys,tempfile,time,types
import numpy as np
from PIL import Image
root=pathlib.Path(__file__).resolve().parents[2]
tmp=tempfile.TemporaryDirectory();os.environ['SCENEFORGE_DATA_DIR']=tmp.name
t=pathlib.Path(tmp.name)
sys.path.insert(0,str(root/'backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.render import keyframes as kf
from app.render.overlays import build_overlay_pass
from app.render.subtitles import write_ass_file
n=0
def check(name,ok):
 global n
 assert ok,name
 n+=1;print('PASS '+name,flush=True)

# --- pure interpolation ---------------------------------------------------------------
K=[{'t_ms':0,'x':10,'ease':'linear'},{'t_ms':1000,'x':30,'ease':'ease_in'},{'t_ms':2000,'x':50}]
check('value holds before the first and after the last keyframe',kf.value_at(K,'x',0,-500)==10 and kf.value_at(K,'x',0,9000)==50)
check('linear and eased segments interpolate',abs(kf.value_at(K,'x',0,500)-20)<1e-9 and abs(kf.value_at(K,'x',0,1500)-35)<1e-9)
check('missing values fall back to the layer value',kf.value_at([{'t_ms':0},{'t_ms':1000,'y':80}],'y',40,500)==60)
expr=kf.piecewise_expr(K,'x',0,1.0)
ev=lambda e,tt:eval(e.replace('clip','_c').replace('pow','_p').replace('PI','3.141592653589793').replace('cos','_cos').replace('t',str(tt)),{'_c':lambda v,a,b:min(b,max(a,v)),'_p':pow,'_cos':__import__('math').cos})
check('FFmpeg expression matches the Python interpolation',all(abs(ev(expr,1.0+ms/1000)-kf.value_at(K,'x',0,ms))<1e-3 for ms in (0,250,500,1200,1700,2500)))

# --- byte identity for layers without keyframes ------------------------------------------
def baseline(rel):
 """The module as released in 0.7.1 (fallback: HEAD) to prove unchanged output."""
 for ref in ('7cb2b31','HEAD'):
  r=subprocess.run(['git','-C',str(root),'show',f'{ref}:{rel}'],capture_output=True,text=True)
  if r.returncode==0:
   src=r.stdout;break
 else:
  return None
 mod=types.ModuleType('baseline_'+rel.replace('/','_'));exec(compile(src,rel,'exec'),mod.__dict__);return mod
asset=types.SimpleNamespace(width=400,height=300,type='image',path=str(t/'a.png'))
Image.new('RGB',(400,300),(200,0,0)).save(t/'a.png')
base_ov={'asset_id':'a','kind':'sticker','x':40,'y':55,'width':30,'rotation':12,'opacity':70,'radius':8,'border':4,'border_color':'#FFFFFF','shadow':40,
         'start_ms':200,'end_ms':2600,'anim_in':'zoom','anim_out':'slide_left','anim_ms':500,'x2':None,'y2':None,'chroma':None,'chroma_similarity':30,'feather':10,
         'loop':'none','loop_amount':30,'loop_period_ms':2000,'above_text':False,'id':'o1'}
variants=[base_ov,{**base_ov,'x2':70,'y2':20,'anim_in':'slide_up','anim_out':'zoom'},{**base_ov,'loop':'pendulum','rotation':-20},{**base_ov,'loop':'float','chroma':'#00FF00','opacity':100,'rotation':0}]
old=baseline('backend/app/render/overlays.py')
cache=t/'cache'
new_out=[build_overlay_pass([v],{'a':asset},1280,720,30,3000,cache) for v in variants]+[build_overlay_pass(variants,{'a':asset},1280,720,30,3000,cache)]
if old:
 old_out=[old.build_overlay_pass([v],{'a':asset},1280,720,30,3000,cache) for v in variants]+[old.build_overlay_pass(variants,{'a':asset},1280,720,30,3000,cache)]
 check('overlays without keyframes build a byte-identical filter graph (vs 0.7.1)',new_out==old_out)
check('a keyframe-free overlay passes through split_overlay untouched',kf.split_overlay(base_ov) is base_ov and kf.overlay_filters(base_ov,0)==[])
keyed=build_overlay_pass([{**base_ov,'keyframes':[{'t_ms':0,'x':10,'opacity':0,'width':10,'rotation':0},{'t_ms':1000,'x':90,'opacity':100,'width':40,'rotation':90,'ease':'ease_in_out'}]}],{'a':asset},1280,720,30,3000,cache)[1]
check('keyframed overlays get per-frame position, rotation, opacity and scale',"overlay=x='(" in keyed and "rotate=a='(" in keyed and 'geq=' in keyed and 'eval=frame' in keyed and 'colorchannelmixer=aa=0.700' not in keyed)
layers=[{'id':'l1','text':'Hello','x':30,'y':40,'size':60,'color':'#FFEEDD','start_ms':0,'end_ms':0,'bold':True,'animation':a,'animation_ms':700,'exit_ms':300,'kind':'text_plus','family':'Noto Sans','align':'center','outline_width':2,'shadow':1,'spacing':0,'highlight':'#FFD84D','box_width':80}
        for a in ('none','fade','slide','zoom','letters-pop','typewriter','neon','reveal-clock')]
sub_old=baseline('backend/app/render/subtitles.py')
font={'captions_enabled':False,'layers':layers}
a_new=pathlib.Path(write_ass_file('s','',3000,font,1280,720,out_path=str(t/'new.ass'))).read_bytes()
if sub_old:
 a_old=pathlib.Path(sub_old.write_ass_file('s','',3000,font,1280,720,out_path=str(t/'old.ass'))).read_bytes()
 check('text layers without keyframes write byte-identical ASS (vs 0.7.1)',a_new==a_old)
kass=pathlib.Path(write_ass_file('s','',3000,{'captions_enabled':False,'layers':[{**layers[0],'exit_ms':0,'keyframes':[{'t_ms':0,'x':10,'rotation':0},{'t_ms':1000,'x':90,'rotation':45,'size':120,'opacity':50}]}]},1280,720,out_path=str(t/'k.ass'))).read_text('utf-8-sig')
ev_lines=[l for l in kass.splitlines() if l.startswith('Dialogue: 1,')]
check('keyframed text is stepped (~33 events per second while moving) with \\pos/\\frz/\\fscx/\\alpha',25<=len(ev_lines)<=40 and all('\\pos(' in l and '\\frz' in l and '\\fscx' in l and '\\alpha&H' in l for l in ev_lines))
check('keyframed text holds as one event after the last keyframe',ev_lines[-1].split(',')[2]=='0:00:03.00' and '\\pos(1152.0,288.0)' in ev_lines[-1] and '\\frz-45.00' in ev_lines[-1] and '\\fscx200.0' in ev_lines[-1] and '\\alpha&H80&' in ev_lines[-1])

# --- API validation -----------------------------------------------------------------
def ff(*a):subprocess.run(['ffmpeg','-v','error','-y',*a],check=True,capture_output=True)
client=TestClient(app).__enter__()
p=client.post('/api/projects',json={'title':'Keyframes','aspect':'16:9'}).json();pid=p['id']
Image.fromarray(np.full((360,640,3),(20,40,90),np.uint8)).save(t/'bg.png')
Image.fromarray(np.full((200,200,3),(230,40,40),np.uint8)).save(t/'red.png')
up=lambda f:client.post('/api/assets/upload',params={'project_id':pid},files={'file':(f,open(t/f,'rb'))}).json()
bg,red=up('bg.png'),up('red.png')
sid=client.get(f'/api/projects/{pid}').json()['scenes'][0]['id']
check('preview media for a scene that was never rendered asks for a render (404)',client.get(f'/api/scenes/{sid}/preview-media').status_code==404)
client.post(f'/api/scenes/{sid}/shots',json={'asset_id':bg['id']})
client.patch(f'/api/scenes/{sid}',json={'timing_mode':'fixed','requested_duration_ms':3000,'font':{'captions_enabled':False}})
ov={'asset_id':red['id'],'kind':'sticker','x':50,'y':50,'width':15,'border':0,'radius':0,'shadow':0,'anim_in':'none','anim_out':'none'}
K2=lambda **k:{'t_ms':0,'x':20,**k}
bad=[([K2()]*33,'more than 32 keyframes'),([K2(ease='bounce')],'unknown ease'),([K2(x=200)],'x out of range'),([K2(glow=1)],'unknown keyframe setting'),
     ([K2(),K2()],'two keyframes at one time'),('left','keyframes that are not a list'),([{'x':10}],'a keyframe without a time'),([K2(opacity=150)],'opacity over 100'),([K2(width=1)],'width under 3')]
for kfs,why in bad:
 r=client.patch(f'/api/scenes/{sid}',json={'overlays':[{**ov,'keyframes':kfs}]})
 check('overlay keyframes reject '+why,r.status_code==400 and 'eyframe' in r.json()['detail'])
L=lambda **k:{'id':'t1','text':'MOVE','x':50,'y':50,'size':90,'color':'#FFFFFF','start_ms':0,'end_ms':0,'bold':True,'family':'Noto Sans',**k}
for kfs,why in [([{'t_ms':0,'size':500}],'size over 200'),([{'t_ms':0,'ease':'spring'}],'unknown ease'),([{'t_ms':0,'x':101}],'x over 100'),([{'t_ms':0}]*33,'more than 32 keyframes')]:
 r=client.patch(f'/api/scenes/{sid}',json={'font':{'layers':[L(keyframes=kfs)]}})
 check('text keyframes reject '+why,r.status_code==400 and 'eyframe' in r.json()['detail'])
r=client.patch(f'/api/scenes/{sid}',json={'overlays':[{**ov,'keyframes':[]}],'font':{'layers':[L()]}})
check('empty keyframes are dropped and plain layers carry no keyframes key',r.status_code==200 and 'keyframes' not in r.json()['overlays_json'][0] and 'keyframes' not in r.json()['font_json']['layers'][0])

def render():
 j=client.post(f'/api/scenes/{sid}/render').json()
 while (s:=client.get(f"/api/jobs/{j['job_id']}").json())['status'] not in('succeeded','failed','cancelled'):time.sleep(.3)
 assert s['status']=='succeeded',s
 aid=client.get(f'/api/projects/{pid}').json()['scenes'][0]['rendered_asset_id']
 path=t/f'r{time.time_ns()}.mp4';path.write_bytes(client.get(f'/api/assets/{aid}/stream').content)
 raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-vf','scale=640:360','-f','rawvideo','-pix_fmt','rgb24','-'])
 return np.frombuffer(raw,np.uint8).reshape(-1,360,640,3).astype(int)
diff=lambda f:np.abs(f-np.array([20,40,90])).sum(axis=-1)>45

# sticker glides left -> right while fading in (opacity 0 -> 100 over 2 s, then holds)
r=client.patch(f'/api/scenes/{sid}',json={'font':{'layers':[]},'overlays':[{**ov,'keyframes':[{'t_ms':0,'x':20,'y':50,'opacity':0},{'t_ms':2000,'x':80,'y':50,'opacity':100}]}]})
check('overlay keyframes save sorted and normalised',r.status_code==200 and [k['t_ms'] for k in r.json()['overlays_json'][0]['keyframes']]==[0,2000] and r.json()['overlays_json'][0]['keyframes'][0]['ease']=='linear')
fr=render()
def centre(f):
 ys,xs=np.nonzero(diff(f));return xs.mean(),ys.mean()
for idx,(xp,alpha) in {15:(35,.25),30:(50,.5),75:(80,1.0)}.items():
 cx,cy=centre(fr[idx]);px=fr[idx][int(round(cy)),int(round(cx))]
 check(f'sticker at {idx/30:.1f}s sits at {xp}% across',abs(cx-640*xp/100)<8 and abs(cy-180)<6)
 check(f'sticker at {idx/30:.1f}s is {int(alpha*100)}% opaque',abs(px[0]-(20+210*alpha))<28)

# size and rotation keyframes on the same sticker
client.patch(f'/api/scenes/{sid}',json={'overlays':[{**ov,'keyframes':[{'t_ms':0,'width':10,'rotation':0},{'t_ms':2000,'width':30,'rotation':45,'ease':'ease_in_out'}]}]})
fr=render()
w0=np.ptp(np.nonzero(diff(fr[2]))[1]);w1=np.ptp(np.nonzero(diff(fr[80]))[1])
ys,xs=np.nonzero(diff(fr[80]));top=xs[ys==ys.min()].mean()
check('width keyframes scale the sticker over time',abs(w0-64)<8 and w1>w0*2.5)
check('rotation keyframes turn the sticker (45 degrees: a corner points up)',abs(top-xs.mean())<10 and ys.max()-ys.min()>w0*2.5)

# text layer moved with keyframes
r=client.patch(f'/api/scenes/{sid}',json={'overlays':[],'font':{'captions_enabled':False,'layers':[L(keyframes=[{'t_ms':0,'x':20},{'t_ms':2000,'x':80}])]}})
check('text keyframes save on the layer',r.status_code==200 and r.json()['font_json']['layers'][0]['keyframes'][1]['x']==80)
fr=render()
white=lambda f:(f.min(axis=-1)>200)
for idx,xp in {15:35,30:50,75:80}.items():
 xs=np.nonzero(white(fr[idx]))[1]
 check(f'text at {idx/30:.1f}s is centred at {xp}% across',len(xs)>200 and abs(xs.mean()-640*xp/100)<10)

# preview media that live playback streams scene by scene
r=client.get(f'/api/scenes/{sid}/preview-media',follow_redirects=False)
check('a rendered scene serves its preview media for live playback',r.status_code in (200,307))
client.patch(f'/api/scenes/{sid}',json={'requested_duration_ms':2500})
sc=client.get(f'/api/projects/{pid}').json()['scenes'][0]
check('editing a rendered scene marks it stale (live playback shows its still until re-rendered)',sc['is_stale'] and sc['rendered_asset_id'])
print(f'{n} keyframe and playback checks passed')
