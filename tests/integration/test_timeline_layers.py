"""Real export checks for independent image/Text/Text box/Text+ clips. No providers."""
import os, pathlib, subprocess, sys, tempfile, time, io
import numpy as np
from PIL import Image
ROOT = pathlib.Path(__file__).resolve().parents[2]
tmp = tempfile.TemporaryDirectory(); os.environ['SCENEFORGE_DATA_DIR'] = tmp.name
sys.path.insert(0, str(ROOT / 'backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import SessionLocal
from app.db.models import Project
from app.render.layer_clips import text_raster
from app.render.ffmpeg_utils import probe
n = 0

def check(name, ok):
    global n
    assert ok, name
    n += 1; print('PASS ' + name, flush=True)

def wait(c, jid):
    for _ in range(900):
        job = c.get('/api/jobs/' + jid).json()
        if job['status'] in ('failed', 'succeeded', 'cancelled'):
            assert job['status'] == 'succeeded', job
            return job
        time.sleep(.1)
    raise AssertionError('Render timed out')

with TestClient(app) as c:
    pid = c.post('/api/projects', json={'title':'Timeline layers','aspect':'16:9','fps':25}).json()['id']
    with SessionLocal() as db:
        p=db.get(Project,pid);p.width=320;p.height=180;db.commit()
    scenes=c.get('/api/projects/'+pid).json()['scenes']
    for index, scene in enumerate(scenes[:2]):
        im=Image.new('RGB',(320,180),'#111111' if index==0 else '#151515');b=io.BytesIO();im.save(b,format='PNG')
        a=c.post('/api/assets/upload?project_id='+pid,files={'file':(f'base{index}.png',b.getvalue(),'image/png')}).json()
        c.post('/api/scenes/'+scene['id']+'/shots',json={'asset_id':a['id']})
        c.patch('/api/scenes/'+scene['id'],json={'timing_mode':'fixed','requested_duration_ms':10000,'font':{'captions_enabled':False}})
    red=Image.new('RGBA',(100,100),'red');b=io.BytesIO();red.save(b,format='PNG')
    asset=c.post('/api/assets/upload?project_id='+pid,files={'file':('overlay.png',b.getvalue(),'image/png')}).json()
    foreign=c.post('/api/projects',json={'title':'Other project'}).json()['id']
    fa=c.post('/api/assets/upload?project_id='+foreign,files={'file':('foreign.png',b.getvalue(),'image/png')}).json()
    base=dict(id='image',kind='image',asset_id=asset['id'],start_ms=5000,duration_ms=8000,track=1,x=25,y=50,width=20)
    title=dict(id='text',kind='text',text='PARIS 1969',start_ms=5000,duration_ms=3000,x=65,y=25,width=60,size=120,color='#ffffff')
    box=dict(id='box',kind='text_box',text='Your paragraph',start_ms=9000,duration_ms=2000,x=70,y=50,width=45,size=100)
    plus=dict(id='plus',kind='text_plus',text='بغداد',start_ms=14000,duration_ms=2000,x=50,y=50,width=80,size=180,family='Tajawal')
    clips=[base,title,box,plus]
    def patch(v):return c.patch('/api/projects/'+pid,json={'finishing':{'layer_clips':v}})
    r=patch(clips);check('image and three text types persist independently',r.status_code==200 and len(r.json()['finishing_json']['layer_clips'])==4)
    saved=r.json()['finishing_json']['layer_clips']
    check('image spans a scene boundary without splitting video',saved[0]['start_ms']==5000 and saved[0]['duration_ms']==8000 and len(c.get('/api/projects/'+pid).json()['scenes'])==3)
    for name,change in [('foreign image',{'asset_id':fa['id']}),('image used as video',{'kind':'video'}),('negative time',{'start_ms':-1}),('too short',{'duration_ms':0}),('bad colour',{'color':'red'}),('huge text',{'kind':'text','text':'a'*501}),('invalid track',{'track':6}),('fractional track',{'track':.5}),('unknown font',{'family':'Missing Font'}),('unsupported field',{'fake':True})]:
        check('rejects '+name,patch([{**base,**change}]).status_code==400)
    check('rejects duplicate clip ids',patch([base,base]).status_code==400)
    for clip in saved[1:]:
        r=c.get('/api/projects/'+pid+'/layer-preview',params={'style':__import__('json').dumps(clip)})
        with SessionLocal() as db:
            p=db.get(Project,pid);expected=text_raster(clip,p.width,p.height).read_bytes()
        check(clip['kind']+' preview uses the export raster',r.status_code==200 and r.content==expected and Image.open(io.BytesIO(r.content)).mode=='RGBA')
    snap=c.post('/api/projects/'+pid+'/snapshots',json={'label':'Layer clips'}).json()['snapshot']['id']
    restored=c.post(f'/api/projects/{pid}/snapshots/{snap}/restore').json()['id']
    rp=c.get('/api/projects/'+restored).json();rclips=rp['finishing_json']['layer_clips']
    check('restore points retain and remap overlay image assets',len(rclips)==4 and rclips[0]['asset_id']!=asset['id'] and c.get('/api/assets/'+rclips[0]['asset_id']+'/stream').status_code==200)
    job=wait(c,c.post('/api/projects/'+pid+'/export?skip_empty=true').json()['job_id'])
    out=pathlib.Path(tmp.name)/'layers-export.mp4';out.write_bytes(c.get('/api/assets/'+job['artifact_asset_id']+'/stream').content)
    check('full export preserves video length',abs(probe(str(out)).duration_ms-20000)<100)
    def frame(sec):
        raw=subprocess.check_output(['ffmpeg','-v','error','-ss',str(sec),'-i',str(out),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'])
        return np.frombuffer(raw,np.uint8).reshape(180,320,3).astype(int)
    check('image absent before its start',frame(4)[90,80].max()<30)
    check('image appears at five seconds',frame(5.2)[90,80,0]>200 and frame(5.2)[90,80,1]<40)
    check('image continues over the next scene',frame(11)[90,80,0]>200)
    check('image disappears at its end',frame(13.2)[90,80].max()<40)
    check('plain title is actually burned into export',((frame(6)[20:70,110:] > 180).all(2)).sum()>100)
    check('title disappears at its own end',((frame(8.2)[20:70,110:] > 180).all(2)).sum()==0)
    check('text box is actually burned into export',((frame(10)[50:130,150:] > 150).all(2)).sum()>20)
    check('Arabic Text+ is actually burned into export',((frame(15)>150).all(2)).sum()>100)
    # Same-position clips stack by track number, with O1 above O2.
    upper={**base,'id':'upper','track':0,'color':'#fff000','kind':'text_box','asset_id':None,'text':'ON TOP','width':30,'size':100,'start_ms':0,'duration_ms':2000}
    lower={**base,'id':'lower','track':1,'start_ms':0,'duration_ms':2000}
    check('overlapping clips on separate tracks are accepted',patch([lower,upper]).status_code==200)
    job=wait(c,c.post('/api/projects/'+pid+'/export?skip_empty=true').json()['job_id']);out.write_bytes(c.get('/api/assets/'+job['artifact_asset_id']+'/stream').content)
    check('upper track covers lower track in export',frame(1)[90,80,0]<180)
    # Put the unused starter scene between the two video scenes. It occupies 4s in the editor.
    response=c.put('/api/projects/'+pid+'/scene-order', json={'scene_ids':[scenes[0]['id'],scenes[2]['id'],scenes[1]['id']]})
    check('an empty starter scene can sit between footage',response.status_code==200)
    check('overlay after empty gap is saved',patch([{**base,'start_ms':15000,'duration_ms':2000}]).status_code==200)
    job=wait(c,c.post('/api/projects/'+pid+'/export?skip_empty=true').json()['job_id']);out.write_bytes(c.get('/api/assets/'+job['artifact_asset_id']+'/stream').content)
    check('skipping empty scenes keeps overlays over the intended footage',frame(11.5)[90,80,0]>200 and frame(10.5)[90,80,0]<40)

print(f'{n} independent timeline overlay checks passed')
