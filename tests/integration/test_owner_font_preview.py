"""Real title request validation and isolated knockout preview, with no provider calls."""
import io, os, sys, tempfile, time, subprocess
import numpy as np
from pathlib import Path
from PIL import Image
root = Path(__file__).resolve().parents[2]
temp = tempfile.TemporaryDirectory(prefix='sf-owner-preview-')
os.environ['SCENEFORGE_DATA_DIR'] = temp.name
sys.path.insert(0, str(root/'backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.domain.fonts import ALL_FAMILIES
from app.domain.schemas import TextLayer
from pydantic import ValidationError

with TestClient(app) as client:
    p = client.post('/api/projects',json={'title':'Owner fonts and video inside text','fps':25}).json()
    pid = p['id']; sid = client.get('/api/projects/'+pid).json()['scenes'][0]['id']
    for family in ALL_FAMILIES:
        layer = {'id':'owner','text':'Title مرحبا','family':family,'size':100}
        TextLayer.model_validate(layer)
        r = client.post('/api/title-preview',json={'text':'Title مرحبا','background':'#202838','duration':.5,'width':640,'height':360,'layer':layer})
        assert r.status_code == 200 and r.headers['content-type']=='video/mp4', (family,r.text[:500])
        # Actual scene save also uses TextLayer validation (the previously untested path).
        r = client.patch('/api/scenes/'+sid,json={'font':{'layers':[layer]}})
        assert r.status_code == 200, (family,r.text)
    try: TextLayer.model_validate({'id':'x','text':'x','family':'Injected|Font'})
    except ValidationError: pass
    else: raise AssertionError('Unknown fonts must remain rejected')
    print('PASS all 19 families through real title-preview and scene-save requests; unknown fonts rejected',flush=True)
    data=io.BytesIO();Image.new('RGB',(640,360),'#20B060').save(data,format='PNG')
    asset=client.post('/api/assets/upload?project_id='+pid,files={'file':('green.png',data.getvalue(),'image/png')}).json()
    assert client.post('/api/scenes/'+sid+'/shots',json={'asset_id':asset['id']}).status_code==200
    assert client.patch('/api/scenes/'+sid,json={'timing_mode':'fixed','requested_duration_ms':1000,'font':{'layers':[]}}).status_code==200
    original=client.get('/api/scenes/'+sid).json()
    bad=client.post('/api/scenes/'+sid+'/knockout-title/preview',json={'text':'PREVIEW','start_ms':500,'end_ms':200})
    assert bad.status_code==400
    r=client.post('/api/scenes/'+sid+'/knockout-title/preview',json={'text':'PREVIEW','font':'DejaVu Sans','background':'#002020'})
    assert r.status_code==200,r.text
    jid=r.json()['job_id']
    for _ in range(300):
        j=client.get('/api/jobs/'+jid).json()
        if j['status'] in ('succeeded','failed','cancelled'):break
        time.sleep(.2)
    assert j['status']=='succeeded',j
    media=client.get('/api/assets/'+j['artifact_asset_id']+'/stream')
    assert media.status_code==200
    path=Path(temp.name)/'preview.mp4';path.write_bytes(media.content)
    raw=subprocess.check_output(['ffmpeg','-v','error','-ss','0.6','-i',str(path),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'])
    frame=np.frombuffer(raw,np.uint8).reshape(-1,3).astype(int)
    assert (np.abs(frame-[0,32,32]).sum(1)<25).mean()>.7,'Preview must show the draft colour card'
    assert (np.abs(frame-[32,176,96]).sum(1)<40).mean()>.002,'Original scene must show through the letters'
    assert not any(a['original_filename']=='preview-video-inside-text.png' for a in client.get('/api/assets?project_id='+pid).json())

    assert client.get('/api/scenes/'+sid).json()==original,'Preview must not change saved overlays or revision'
    print('PASS real knockout preview job renders and streams; saved scene remains byte-for-byte unchanged',flush=True)
