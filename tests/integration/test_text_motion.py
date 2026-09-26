"""Text animation engine: letter/word animations, shine, bounce, neon, wobble, spacing, styles."""
import os,pathlib,re,subprocess,sys,tempfile
import numpy as np
root=pathlib.Path(__file__).resolve().parents[2]
tmp=tempfile.TemporaryDirectory();os.environ['SCENEFORGE_DATA_DIR']=tmp.name;t=pathlib.Path(tmp.name)
sys.path.insert(0,str(root/'backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.render.subtitles import write_ass_file
n=0
def check(name,ok):
 global n
 assert ok,name
 n+=1;print('PASS '+name,flush=True)
client=TestClient(app).__enter__()
p=client.post('/api/projects',json={'title':'T','aspect':'16:9'}).json();sid=client.get(f"/api/projects/{p['id']}").json()['scenes'][0]['id']
L=lambda **kw:{'id':'a','text':'THE BATTLE','x':50,'y':50,'size':64,'color':'#FFFFFF','start_ms':0,'end_ms':3000,'bold':True,'animation':'letters-pop','animation_ms':1200,**kw}
check('new text animations are accepted',client.patch(f'/api/scenes/{sid}',json={'font':{'layers':[L(animation=a) for a in ('letters-pop','words-fade','shine','neon','wobble')]}}).status_code==200)
check('unknown animations are rejected',client.patch(f'/api/scenes/{sid}',json={'font':{'layers':[L(animation='explode')]}}).status_code==422 or client.patch(f'/api/scenes/{sid}',json={'font':{'layers':[L(animation='explode')]}}).status_code==400)
check('letter spacing is validated',client.patch(f'/api/scenes/{sid}',json={'font':{'layers':[L(spacing=99)]}}).status_code in (400,422))
def ass(layer):
 path=write_ass_file('x','',3000,{'captions_enabled':False,'layers':[layer]},640,360,out_path=str(t/'x.ass'))
 return pathlib.Path(path).read_text(encoding='utf-8-sig').split('[Events]')[1]
ev=ass(L(animation='letters-pop'))
check('letters pop: one timed tag group per letter (9 letters, space attached)',len(re.findall(r'\\fscx40',ev))==9)
ar=ass(L(text='قرطبة الأندلس',animation='letters-pop',family='Noto Naskh Arabic'))
line=[x for x in ar.splitlines() if x.startswith('Dialogue: 1,')][0]   # the title layer (line 0 is the empty caption)
check('Arabic animates by word: 2 units, no tags inside a word',len(re.findall(r'\\fscx40',line))==2 and 'قرطبة' in line and 'الأندلس' in line)
check('letter spacing is written to the title',r'\fsp12.0' in ass(L(spacing=12)))
check('neon draws a glow layer under the text',len([x for x in ass(L(animation='neon')).splitlines() if x.startswith('Dialogue: 1,')])==2)
def ink(layer,at):
 path=write_ass_file('x','',3000,{'captions_enabled':False,'layers':[layer]},640,360,out_path=str(t/'r.ass'))
 raw=subprocess.check_output(['ffmpeg','-v','error','-f','lavfi','-i','color=c=black:s=640x360:d=3','-vf',f"ass={path}:fontsdir={root/'assets'/'fonts'}",'-ss',str(at),'-frames:v','1','-f','rawvideo','-pix_fmt','gray','-'])
 return int((np.frombuffer(raw,np.uint8)>128).sum())
a,b,c=ink(L(animation='letters-fade'),0.15),ink(L(animation='letters-fade'),0.7),ink(L(animation='letters-fade'),2.0)
check(f'letters appear progressively on screen ({a} → {b} → {c} lit pixels)',a<b<c and c>1500)
wa,wb=ink(L(text='قرطبة الأندلس',animation='words-fade',family='Noto Naskh Arabic'),0.25),ink(L(text='قرطبة الأندلس',animation='words-fade',family='Noto Naskh Arabic'),2.0)
check('Arabic words appear one after another',0<wa<wb*0.7)

# --- annotations -------------------------------------------------------------
from app.render.annotations import clean_annotations,annotation_clip
bad=[{'type':'star'},{'type':'arrow','x':500},{'type':'circle','style':'curved'},{'type':'callout','text':'x'*81}]
check('annotation settings are validated',all(client.patch(f'/api/scenes/{sid}',json={'look':{'annotations':[b]}}).status_code==400 for b in bad) and client.patch(f'/api/scenes/{sid}',json={'look':{'annotations':[{'type':'arrow'}]*11}}).status_code==400)
check('annotations save on the scene',client.patch(f'/api/scenes/{sid}',json={'look':{'annotations':[{'type':'circle','style':'hand'},{'type':'callout','text':'قرطبة'}]}}).json()['look_json']['annotations'][1]['text']=='قرطبة')
def frame(a,dur,at):
 c=annotation_clip(clean_annotations([a])[0],640,360,30,dur,t/'an')
 raw=subprocess.check_output(['ffmpeg','-v','error','-i',c,'-vf',f'select=eq(n\\,{at})','-frames:v','1','-f','rawvideo','-pix_fmt','rgba','-'])
 return np.frombuffer(raw,np.uint8).reshape(360,640,4).astype(int)
arrow={'type':'arrow','style':'straight','x':10,'y':50,'x2':90,'y2':50,'width':10,'draw_ms':1000}
early,late=frame(arrow,3000,6),frame(arrow,3000,40)
reach=lambda f:np.nonzero((f[...,3]>200).any(axis=0))[0]
check('arrow grows from start to target, then its head appears',reach(early).max()<320 and reach(late).max()>570 and (late[140:220,560:600,3]>200).sum()>(late[170:190,300:340,3]>200).sum()//2)
circ=frame({'type':'circle','style':'neat','x':30,'y':20,'x2':70,'y2':80,'width':8,'draw_ms':1000},3000,15)
circ_end=frame({'type':'circle','style':'neat','x':30,'y':20,'x2':70,'y2':80,'width':8,'draw_ms':1000},3000,40)
check('circle sweeps clockwise from the top: right half at mid-draw, complete at the end',(circ[:,330:,3]>200).sum()>300 and (circ[:,:310,3]>200).sum()<50 and (circ_end[:,:310,3]>200).sum()>300)
hl=frame({'type':'underline','style':'highlighter','x':10,'y':50,'x2':90,'width':10,'draw_ms':300},3000,40)
check('highlighter is translucent',0<hl[180,320,3]<160)
fade=frame({'type':'box','x':20,'y':20,'x2':80,'y2':80,'width':8,'draw_ms':300,'end_ms':2000},3000,58)
full=frame({'type':'box','x':20,'y':20,'x2':80,'y2':80,'width':8,'draw_ms':300,'end_ms':2000},3000,40)
check('annotations fade out before their end time',0<fade[...,3].max()<full[...,3].max())

# --- new looks ------------------------------------------------------------------
from app.render.filters import _EFFECT_FILTERS
from app.domain.constants import EffectPreset
subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=s=320x180','-frames:v','1',str(t/'src.png')],check=True)
src=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(t/'src.png'),'-f','rawvideo','-pix_fmt','rgb24','-']),np.uint8).astype(int)
for look in ('glow','duotone','newsprint'):
 ok=client.patch(f'/api/scenes/{sid}',json={'effect_preset':look}).status_code==200
 out=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(t/'src.png'),'-filter_complex',f'[0]{_EFFECT_FILTERS[EffectPreset(look)]}[o]','-map','[o]','-f','rawvideo','-pix_fmt','rgb24','-']),np.uint8).astype(int)
 check(f'{look} look is accepted and changes the picture',ok and np.abs(out-src).mean()>8)
print(f'{n} text motion, annotation and look checks passed')
