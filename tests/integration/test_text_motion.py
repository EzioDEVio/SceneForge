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

# --- caption animations ---------------------------------------------------------
check('caption animation is accepted',client.patch(f'/api/scenes/{sid}',json={'font':{'caption_animation':'letters-pop','caption_animation_ms':1200}}).status_code==200)
check('unknown caption animation is rejected',client.patch(f'/api/scenes/{sid}',json={'font':{'caption_animation':'explode'}}).status_code==400)
def cap_ass(font,text='THE BATTLE'):
 path=write_ass_file('c',text,3000,{'size':48,**font},640,360,out_path=str(t/'c.ass'))
 return [x for x in pathlib.Path(path).read_text(encoding='utf-8-sig').splitlines() if x.startswith('Dialogue')]
ev=cap_ass({'caption_animation':'letters-pop','caption_animation_ms':1200})
check('caption letters get per-letter animation',len(re.findall(r'\\fscx40',ev[0]))==9)
check('Arabic captions animate by word',len(re.findall(r'\\alpha&HFF&',cap_ass({'caption_animation':'words-fade'},'قرطبة الأندلس')[0]))==2)
check('caption animation is skipped when typewriter or word-by-word is on',r'\fscx40' not in ''.join(cap_ass({'caption_animation':'letters-pop','typewriter':True})) and r'\fscx40' not in ''.join(cap_ass({'caption_animation':'letters-pop','karaoke':True})))
check('neon captions draw a glow layer',len(cap_ass({'caption_animation':'neon'}))==2)
def cap_ink(at):
 path=write_ass_file('c','THE BATTLE',3000,{'size':48,'caption_animation':'letters-fade','caption_animation_ms':1200},640,360,out_path=str(t/'cr.ass'))
 raw=subprocess.check_output(['ffmpeg','-v','error','-f','lavfi','-i','color=c=black:s=640x360:d=3','-vf',f"ass={path}:fontsdir={root/'assets'/'fonts'}",'-ss',str(at),'-frames:v','1','-f','rawvideo','-pix_fmt','gray','-'])
 return int((np.frombuffer(raw,np.uint8)>128).sum())
x1,x2,x3=cap_ink(0.1),cap_ink(0.7),cap_ink(2.0)
check(f'caption letters appear progressively on screen ({x1} → {x2} → {x3})',x1<x2<x3)

# --- Captions Pro: style engine and phrase captions -------------------------------------
for bad in ({'bold':'yes'},{'case':'shout'},{'position':'side'},{'box_opacity':150},{'phrase_words':12},{'shadow_color':'black'},{'karaoke_style':'sparkle'}):
 check('caption style rejects '+str(bad)[:30],client.patch(f'/api/scenes/{sid}',json={'font':bad}).status_code==400)
check('caption style saves',client.patch(f'/api/scenes/{sid}',json={'font':{'family':'Poppins','bold':True,'italic':True,'case':'upper','background':'box','split':'phrases','phrase_words':3,'karaoke':True,'karaoke_style':'box'}}).status_code==200)
def style_line(font,text='Hello world'):
 path=write_ass_file('s',text,3000,font,640,360,out_path=str(t/'s.ass'))
 return [x for x in pathlib.Path(path).read_text(encoding='utf-8-sig').splitlines() if x.startswith('Style:')][0].split(',')
st=style_line({'family':'Noto Sans','bold':True,'italic':True,'underline':True,'spacing':3,'shadow':2})
check('bold, italic, underline, spacing and shadow go into the caption style',st[7]=='-1' and st[8]=='-1' and st[9]=='-1' and float(st[13])==3 and float(st[17])==2)
bx=style_line({'family':'Noto Sans','background':'box','box_color':'#FF0000','box_opacity':100,'box_padding':14})
check('background box uses the chosen colour, opacity and padding',bx[15]=='3' and bx[5].upper()=='&H000000FF' and bx[16]=='14')
check('position top-right sets the right alignment',style_line({'position':'top','halign':'right'})[18]=='9')
up=pathlib.Path(write_ass_file('u','hello world',3000,{'case':'upper'},640,360,out_path=str(t/'u.ass'))).read_text(encoding='utf-8-sig')
check('UPPERCASE transforms the caption text','HELLO WORLD' in up)
words='one two three four five six seven'.split()
wt=[(i*500,i*500+400) for i in range(7)]
ph=pathlib.Path(write_ass_file('p',' '.join(words),5000,{'split':'phrases','phrase_words':3},640,360,out_path=str(t/'p.ass'),word_times=wt)).read_text(encoding='utf-8-sig')
evs=[x for x in ph.splitlines() if x.startswith('Dialogue: 0,')]
check('phrase captions: 7 words in phrases of 3 give 3 events, each starting with its first word',len(evs)==3 and [e.split(',')[1] for e in evs]==['0:00:00.00','0:00:01.50','0:00:03.00'])
hk=pathlib.Path(write_ass_file('h',' '.join(words),5000,{'split':'phrases','phrase_words':3,'karaoke':True,'karaoke_style':'box','highlight_color':'#00FF00'},640,360,out_path=str(t/'h.ass'),word_times=wt)).read_text(encoding='utf-8-sig')
check('box highlight inside phrases: one event per word, the spoken word gets the marker',len([x for x in hk.splitlines() if x.startswith('Dialogue: 0,')])==7 and hk.count(r'\3c&H0000FF00')>=7)
def ink_at(font,at,text='In the year 711 a small force crossed'):
 path=write_ass_file('i',text,5000,font,640,360,out_path=str(t/'i.ass'),speech_start_ms=0,speech_ms=4500)
 raw=subprocess.check_output(['ffmpeg','-v','error','-f','lavfi','-i','color=c=black:s=640x360:d=5','-vf',f"ass={path}:fontsdir={root/'assets'/'fonts'}",'-ss',str(at),'-frames:v','1','-f','rawvideo','-pix_fmt','gray','-'])
 return np.frombuffer(raw,np.uint8).reshape(360,640)
full,ph1=ink_at({'size':40},1.0),ink_at({'size':40,'split':'phrases','phrase_words':2},1.0)
check('phrase captions show only a few words at a time on screen',0<(ph1>128).sum()<(full>128).sum()*0.6)
top=ink_at({'size':40,'position':'top'},1.0)
check('top position draws the caption in the top of the frame',(top[:120]>128).sum()>100 and (top[240:]>128).sum()==0)
print(f'{n} text motion, annotation, look, caption and Captions Pro checks passed')
