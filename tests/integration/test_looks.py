"""Full-frame glitch controls, adjustment sliders, .cube LUT import and the
look_json database upgrade, verified through the API and real renders."""
import os,pathlib,sys,tempfile,subprocess,sqlite3,io
import numpy as np
from PIL import Image
root=pathlib.Path(__file__).resolve().parents[2]
tmp=tempfile.TemporaryDirectory();os.environ['SCENEFORGE_DATA_DIR']=tmp.name
t=pathlib.Path(tmp.name)
# --- an RC4-era database without scenes.look_json must upgrade in place ---
db=sqlite3.connect(t/'sceneforge.db')
db.executescript("""CREATE TABLE projects (id VARCHAR(36) PRIMARY KEY, title VARCHAR(255), language VARCHAR(8), aspect VARCHAR(8), fps INTEGER, width INTEGER, height INTEGER, revision INTEGER, default_font_json JSON, created_at DATETIME, updated_at DATETIME);
CREATE TABLE scenes (id VARCHAR(36) PRIMARY KEY, project_id VARCHAR(36) REFERENCES projects(id), order_index INTEGER, title VARCHAR(255), original_text TEXT, spoken_text TEXT, subtitle_text TEXT, source_refs_json JSON, timing_mode VARCHAR(16), requested_duration_ms INTEGER, lead_ms INTEGER, trail_ms INTEGER, effect_preset VARCHAR(32), effect_intensity INTEGER, transition_in_json JSON, font_json JSON, revision INTEGER, rendered_plan_hash VARCHAR(64), rendered_asset_id VARCHAR(36), measured_duration_ms INTEGER, created_at DATETIME, updated_at DATETIME);
INSERT INTO projects VALUES ('old','Old project','en','16:9',30,1920,1080,1,'{}','2026-01-01','2026-01-01');
INSERT INTO scenes VALUES ('olds','old',0,'Part-1','Kept text','','','[]','audio_driven',NULL,250,400,'sepia',80,'{"type":"cut","duration_ms":0}','{}',1,NULL,NULL,NULL,'2026-01-01','2026-01-01');""")
db.commit();db.close()
sys.path.insert(0,str(root/'backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.render.filters import build_shot_video_chain
from app.render.grade import parse_cube,CubeError,build_grade_lut
n=0
def check(name,ok):
 global n
 assert ok,name
 n+=1;print('PASS '+name,flush=True)
client=TestClient(app).__enter__()
old=client.get('/api/projects/old').json()
check('RC4 database upgrades: old scene keeps its data and gains an empty look',old['scenes'][0]['original_text']=='Kept text' and old['scenes'][0]['effect_preset']=='sepia' and old['scenes'][0]['look_json']=={})

def run(args):subprocess.run(['ffmpeg','-v','error','-y',*args],check=True,capture_output=True)
def frames(path,w,h):
 raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-f','rawvideo','-pix_fmt','rgb24','-'])
 return np.frombuffer(raw,dtype=np.uint8).reshape(-1,h,w,3).astype(float)

# --- glitch: full frame, strength and speed ---------------------------------
Image.fromarray(np.tile(np.linspace(40,220,640)[None,:,None],(360,1,3)).astype('uint8')).save(t/'ramp.png')
def glitch(strength,speed=1.0,block='medium',dur=2.4):
 g,_=build_shot_video_chain('cover',{'type':'static'},320,180,30,int(dur*30),'glitch',strength,look={'glitch':{'speed':speed,'block':block}})
 out=t/f'g_{strength}_{speed}_{block}.mp4';run(['-loop','1','-framerate','30','-t',str(dur),'-i',str(t/'ramp.png'),'-filter_complex',g,'-map','[vout]','-pix_fmt','yuv420p',str(out)])
 f=frames(out,320,180);clean=np.median(f,axis=0);return f,clean
for block in ['small','medium','large']:
 f,clean=glitch(100,block=block)
 rows=(np.abs(f[:12]-clean).mean(axis=(0,2,3))>0)|np.zeros(180,bool)
 rows=np.any(np.abs(f[:12]-clean).mean(axis=3)>3,axis=(0,2))
 check(f'glitch ({block} blocks) reaches every row of the frame',rows.mean()>0.97)
peaks=[np.abs(glitch(s)[0][:10]-glitch(s)[1]).mean(axis=(1,2,3)).max() for s in (20,60,100)]
check('glitch strength increases distortion',peaks[0]<peaks[1]<peaks[2])
def bursts(speed):
 f,clean=glitch(70,speed=speed,dur=4.8);act=np.abs(f-clean).mean(axis=(1,2,3))>1
 return sum(1 for i in range(len(act)) if act[i] and (i==0 or not act[i-1]))
b_slow,b_fast=bursts(0.5),bursts(2)
check('glitch speed changes how often bursts happen',b_slow<=3 and b_fast>=7)

# --- .cube parsing --------------------------------------------------------
def cube(fn,size=17,extra=''):
 g=np.linspace(0,1,size);b,gg,r=np.meshgrid(g,g,g,indexing='ij');rgb=np.stack([r,gg,b],-1).reshape(-1,3)
 buf=io.StringIO();buf.write(f'TITLE "test"\n{extra}LUT_3D_SIZE {size}\n');np.savetxt(buf,fn(rgb),fmt='%.6f');return buf.getvalue()
swap=cube(lambda c:c[:,[2,1,0]])                        # swaps red and blue
table,_,_=parse_cube(swap)
check('cube parser reads a valid 17-point LUT (red fastest)',table.shape==(17,17,17,3) and np.allclose(table[0,0,16],[0,0,1]))
for bad,why in [('LUT_1D_SIZE 1024\n0 0 0\n','1D'),('TITLE "x"\n','missing size'),('LUT_3D_SIZE 2\n0 0 0\n','too few rows'),('LUT_3D_SIZE 99\n','size range'),(swap.replace('0.000000 0.000000 0.000000','nan 0 0',1),'non-finite')]:
 try:parse_cube(bad);ok=False
 except CubeError:ok=True
 check('cube parser rejects '+why,ok)

# --- API: import LUT, set look, render ------------------------------------
p=client.post('/api/projects',json={'title':'Looks','aspect':'16:9'}).json();pid=p['id']
Image.fromarray(np.dstack([np.full((360,640),200),np.full((360,640),120),np.full((360,640),60)]).astype('uint8')).save(t/'warm.png')
img=client.post('/api/assets/upload',params={'project_id':pid},files={'file':('warm.png',open(t/'warm.png','rb'))}).json()
scene=client.post(f'/api/projects/{pid}/scenes',json={'title':'Graded'}).json()
check('audio/LUT cannot be put on the picture track',client.post(f"/api/scenes/{scene['id']}/shots",json={'asset_id':'missing'}).status_code==404)
client.post(f"/api/scenes/{scene['id']}/shots",json={'asset_id':img['id']})
client.patch(f"/api/scenes/{scene['id']}",json={'timing_mode':'fixed','requested_duration_ms':1000})
r=client.post('/api/assets/lut',params={'project_id':pid},files={'file':('swap.cube',swap.encode())})
lut=r.json()
check('LUT import stores a validated LUT asset',r.status_code==200 and lut['type']=='lut' and lut['width']==17)
check('same LUT imported twice is reused',client.post('/api/assets/lut',params={'project_id':pid},files={'file':('again.cube',swap.encode())}).json()['id']==lut['id'])
check('LUT import rejects a broken file with a reason',client.post('/api/assets/lut',params={'project_id':pid},files={'file':('bad.cube',b'LUT_3D_SIZE 2\n0 0 0\n')}).json()['detail'].startswith('This LUT could not be read'))
check('LUT import rejects other file types',client.post('/api/assets/lut',params={'project_id':pid},files={'file':('x.png',b'png')}).status_code==400)
check('LUTs are listed for the project but hidden from the media pool',[a['id'] for a in client.get('/api/assets/luts',params={'project_id':pid}).json()]==[lut['id']] and all(a['type']!='lut' for a in client.get('/api/assets',params={'project_id':pid}).json()))
check('LUT cannot be added to the picture track',client.post(f"/api/scenes/{scene['id']}/shots",json={'asset_id':lut['id']}).status_code==400)
for body,why in [({'adjust':{'exposure':200}},'out-of-range slider'),({'adjust':{'bogus':1}},'unknown slider'),({'glitch':{'speed':9}},'glitch speed'),({'glitch':{'block':'huge'}},'block size'),({'lut':{'asset_id':img['id']}},'non-LUT asset'),({'extra':{}},'unknown section')]:
 check('look rejects '+why,client.patch(f"/api/scenes/{scene['id']}",json={'look':body}).status_code==400)
def render_scene():
 j=client.post(f"/api/scenes/{scene['id']}/render").json()
 import time
 while (s:=client.get(f"/api/jobs/{j['job_id']}").json())['status'] not in('succeeded','failed','cancelled'):time.sleep(.2)
 assert s['status']=='succeeded',s
 aid=client.get(f"/api/projects/{pid}").json()['scenes'][-1]['rendered_asset_id']
 path=t/'out.mp4';path.write_bytes(client.get(f'/api/assets/{aid}/stream').content)
 return frames(path,1920,1080)[5].mean(axis=(0,1))
plain=render_scene()
s=client.patch(f"/api/scenes/{scene['id']}",json={'look':{'lut':{'asset_id':lut['id'],'strength':100}}}).json()
check('look saves and marks the scene stale',s['look_json']['lut']['strength']==100 and s['is_stale'])
swapped=render_scene()
check('LUT at 100% swaps red and blue in the render',abs(swapped[0]-plain[2])<8 and abs(swapped[2]-plain[0])<8)
client.patch(f"/api/scenes/{scene['id']}",json={'look':{'lut':{'asset_id':lut['id'],'strength':50}}})
half=render_scene()
check('LUT strength 50% lands halfway',abs(half[0]-(plain[0]+plain[2])/2)<8)
client.patch(f"/api/scenes/{scene['id']}",json={'look':{'lut':None,'adjust':{'saturation':-100}}})
grey=render_scene()
check('saturation -100 renders greyscale',np.ptp(grey)<6)
client.patch(f"/api/scenes/{scene['id']}",json={'look':{'adjust':{'temperature':-80}}})
cool=render_scene()
check('negative temperature cools the render',cool[2]-cool[0]>plain[2]-plain[0]+20)
client.patch(f"/api/scenes/{scene['id']}",json={'look':{'adjust':{'exposure':-60,'vignette':60,'grain':40,'sharpen':30}}})
dark=render_scene()
check('exposure, vignette, grain and sharpen render together',dark.mean()<plain.mean()-25)
s=client.patch(f"/api/scenes/{scene['id']}",json={'look':{'adjust':{'exposure':0,'vignette':0,'grain':0,'sharpen':0}}}).json()
check('all-zero sliders clear the adjustments',('adjust' not in s['look_json']))
g1=build_grade_lut({'contrast':20},None,100,t/'grades');g2=build_grade_lut({'contrast':20},None,100,t/'grades')
check('grade LUTs are cached by settings',g1==g2 and build_grade_lut({},None,100,t/'grades') is None)
print(f'{n} look checks passed')
