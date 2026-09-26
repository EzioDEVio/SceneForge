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
print(f'{n} text motion checks passed')
