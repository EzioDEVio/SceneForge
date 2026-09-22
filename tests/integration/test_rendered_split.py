"""Actual FFmpeg round trip: animated/text/narrated scene -> rendered split -> export."""
import io, os, pathlib, sys, tempfile, time, wave, math, struct
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
tmp=tempfile.TemporaryDirectory();os.environ['SCENEFORGE_DATA_DIR']=tmp.name
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import SessionLocal
from app.db.models import Project
from app.render.ffmpeg_utils import probe
from app.config import RENDERS_DIR

def job(client,id):
    for _ in range(600):
        j=client.get('/api/jobs/'+id).json()
        if j['status']=='failed':raise AssertionError(j['error'])
        if j['status']=='succeeded':return j
        time.sleep(.1)
    raise AssertionError('render timeout')

with TestClient(app) as c:
    p=c.post('/api/projects',json={'title':'Split regression','aspect':'16:9'}).json()
    with SessionLocal() as db:
        obj=db.get(Project,p['id']);obj.width=320;obj.height=180;db.commit()
    p=c.get('/api/projects/'+p['id']).json();sid=p['scenes'][0]['id']
    with open(ROOT/'examples/fixture_assets/image1.png','rb') as f:
        asset=c.post('/api/assets/upload?project_id='+p['id'],files={'file':('image.png',f,'image/png')}).json()
    c.post(f'/api/scenes/{sid}/shots',json={'asset_id':asset['id'],'motion':{'type':'zoom_in'}}).raise_for_status()
    wav=io.BytesIO()
    with wave.open(wav,'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(48000)
        w.writeframes(b''.join(struct.pack('<h',int(6000*math.sin(i*.07))) for i in range(96000)))
    c.post(f'/api/scenes/{sid}/voice-takes/upload',files={'file':('tone.wav',wav.getvalue(),'audio/wav')}).raise_for_status()
    c.patch(f'/api/scenes/{sid}',json={'timing_mode':'fixed','requested_duration_ms':2000,'subtitle_text':'Test split','font':{'captions_enabled':True,'typewriter':True}}).raise_for_status()
    assert c.post(f'/api/scenes/{sid}/split',json={'at_ms':1000,'baked':True}).status_code==409
    job(c,c.post(f'/api/scenes/{sid}/render').json()['job_id'])
    result=c.post(f'/api/scenes/{sid}/split',json={'at_ms':1000,'baked':True});assert result.status_code==200,result.text
    right=result.json();left=c.get(f'/api/scenes/{sid}').json()
    assert left['requested_duration_ms']==right['requested_duration_ms']==1000
    assert left['shots'][0]['source_in_ms']==0 and right['shots'][0]['source_in_ms']==1000
    assert left['shots'][0]['asset_id']==right['shots'][0]['asset_id']
    for scene in (left,right):
        assert scene['font_json']['captions_enabled'] is False
        assert len([t for t in scene['voice_takes'] if t['accepted']])==1
        assert scene['lead_ms']==scene['trail_ms']==0
    exported=job(c,c.post('/api/projects/'+p['id']+'/export?skip_empty=true').json()['job_id'])
    video=c.get('/api/assets/'+exported['artifact_asset_id']+'/stream').content
    path=pathlib.Path(tmp.name)/'verify.mp4';path.write_bytes(video);info=probe(str(path))
    assert info.has_audio and abs(info.duration_ms-2000)<100,info
    print('PASS rendered split preserves two video segments, sound, baked text/motion, and total export duration')
