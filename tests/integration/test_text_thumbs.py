"""Per-script caption fonts, whole-line bidi, and media thumbnails."""
import os,pathlib,sys,tempfile,subprocess
import numpy as np
from PIL import Image
root=pathlib.Path(__file__).resolve().parents[2]
tmp=tempfile.TemporaryDirectory();os.environ['SCENEFORGE_DATA_DIR']=tmp.name
sys.path.insert(0,str(root/'backend'))
from app.render.fontruns import script_runs,tag_runs,font_pair
from app.render.subtitles import write_ass_file
from fastapi.testclient import TestClient
from app.main import app
n=0
def check(name,ok):
 global n
 assert ok,name
 n+=1;print('PASS '+name,flush=True)
t=pathlib.Path(tmp.name);fonts=root/'assets'/'fonts'
esc=lambda v:v.replace('\\','＼').replace('{','｛').replace('}','｝')

# --- script runs ---------------------------------------------------------
check('pure Latin is one Latin run',script_runs('In the year 711, a force.')==[('la','In the year 711, a force.')])
runs=script_runs('فتح الأندلس عام 711 م')
check('Arabic, Latin digits and Arabic alternate as three runs',[r[0] for r in runs]==['ar','la','ar'] and ''.join(c for _,c in runs)=='فتح الأندلس عام 711 م')
check('Arabic combining marks stay in the Arabic run',[r[0] for r in script_runs('مُحَمَّد')]==['ar'])
check('leading punctuation joins the first real run',script_runs('«مرحبا»')[0]==('ar','«مرحبا»'))
check('Arabic-Indic digits are Arabic script',[r[0] for r in script_runs('عام ٧١١')]==['ar'])
first,tagged=tag_runs('Year {\\b1}711 عام',"Noto Naskh Arabic",esc)
check('user braces cannot open an override block',first=='Noto Sans' and '{\\b1}' not in tagged and '｛' in tagged and '{\\fnNoto Naskh Arabic}' in tagged)
check('Latin families keep an Arabic companion',font_pair('Arial')==('Noto Sans Arabic','Arial') and font_pair('Georgia')[0]=='Noto Naskh Arabic')
check('bundled Latin font files exist',(fonts/'NotoSans-Regular.ttf').exists() and (fonts/'NotoSans-Bold.ttf').exists())

# --- ASS output and real libass rendering --------------------------------
ass=write_ass_file('s','In the year 711, a small force.',2000,{'family':'Noto Naskh Arabic','size':48},640,360,out_path=str(t/'a.ass'))
body=pathlib.Path(ass).read_text(encoding='utf-8-sig')
check('caption style enables whole-line bidi (Encoding -1)',',-1\n' in body.split('[Events]')[0])
check('Latin caption is drawn with the bundled Latin font',',,{\\fnNoto Sans}In the year 711' in body)
def render(ass_path):
 out=subprocess.check_output(['ffmpeg','-v','error','-f','lavfi','-i','color=c=black:s=640x360','-vf',f"ass={ass_path}:fontsdir={fonts}",'-frames:v','1','-f','rawvideo','-pix_fmt','gray','-'])
 return np.frombuffer(out,dtype=np.uint8).reshape(360,640).astype(float)
# Reference: same text with Noto Sans as the style font and no run tags.
ref=body.replace('Style: Default,Noto Naskh Arabic','Style: Default,Noto Sans').replace('{\\fnNoto Sans}','')
(t/'ref.ass').write_text(ref,encoding='utf-8-sig')
got,want=render(ass),render(t/'ref.ass')
check('English caption renders identically to a pure Noto Sans caption',want.max()>200 and np.abs(got-want).mean()<0.5)
mixed=write_ass_file('m','فتح الأندلس عام 711 م — Al-Andalus',2000,{'family':'Noto Naskh Arabic','size':40},640,360,out_path=str(t/'m.ass'))
img=render(mixed);cols=np.where(img.max(axis=0)>128)[0]
# RTL paragraph: the Latin tail "Al-Andalus" ends up at the LEFT edge.
alone=render(write_ass_file('l','Al-Andalus',2000,{'family':'Noto Naskh Arabic','size':40},640,360,out_path=str(t/'l.ass')))
lc=np.where(alone.max(axis=0)>128)[0];w=lc.max()-lc.min()
seg=img[:,cols.min():cols.min()+w+1];ref_seg=alone[:,lc.min():lc.min()+w+1]
rows=np.where(ref_seg.max(axis=1)>128)[0];mrows=np.where(seg.max(axis=1)>128)[0]
shift=mrows.max()-rows.max()
aligned=np.roll(ref_seg,shift,axis=0);ink=(aligned>64)|(seg>64)
# Masked difference over inked pixels: ~60 when the Latin word is there
# (anti-aliasing), ~170 when Arabic glyphs occupy the left edge instead.
check('Arabic-first mixed caption is RTL: its Latin tail sits at the left edge',np.abs(aligned-seg)[ink].mean()<110)

# --- thumbnails ------------------------------------------------------------
client=TestClient(app).__enter__()  # runs startup (creates tables)
p=client.post('/api/projects',json={'title':'Thumbs','aspect':'16:9'}).json()
Image.fromarray(np.full((900,1600,3),(40,120,200),dtype='uint8')).save(t/'wide.png')
subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=red:s=640x360:d=1.5','-f','lavfi','-i','color=c=green:s=640x360:d=1.5','-filter_complex','[0][1]concat=n=2:v=1','-pix_fmt','yuv420p',str(t/'clip.mp4')],check=True)
subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=d=1','-c:a','pcm_s16le',str(t/'tone.wav')],check=True)
up=lambda f:client.post('/api/assets/upload',params={'project_id':p['id']},files={'file':(f,open(t/f,'rb'))}).json()
img_a,vid_a,aud_a=up('wide.png'),up('clip.mp4'),up('tone.wav')
r=client.get(f"/api/assets/{img_a['id']}/thumbnail?w=320")
im=Image.open(__import__('io').BytesIO(r.content))
check('image thumbnail is a small JPEG with the source aspect',r.status_code==200 and r.headers['content-type']=='image/jpeg' and im.size==(320,180))
r=client.get(f"/api/assets/{vid_a['id']}/thumbnail?w=160")
px=np.asarray(Image.open(__import__('io').BytesIO(r.content)).convert('RGB')).mean(axis=(0,1))
check('video thumbnail is a real poster frame',r.status_code==200 and px[0]>150 and px[1]<80)
check('thumbnail is cached on disk',any((t/'proxies'/'thumbs').glob(vid_a['id']+'_160.jpg')))
check('odd widths snap to an allowed size',client.get(f"/api/assets/{img_a['id']}/thumbnail?w=9999").status_code==200 and (t/'proxies'/'thumbs'/(img_a['id']+'_1280.jpg')).exists())
check('audio has no thumbnail',client.get(f"/api/assets/{aud_a['id']}/thumbnail").status_code==415)
check('unknown asset is 404',client.get('/api/assets/nope/thumbnail').status_code==404)
print(f'{n} text and thumbnail checks passed')
