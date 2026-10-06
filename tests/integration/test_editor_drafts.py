"""Recovery gate: actual renderer parity, atomic validation and exact history."""
import os, pathlib, sys, tempfile, time, subprocess
tmp = tempfile.TemporaryDirectory(prefix='sf-recovered-drafts-')
os.environ['SCENEFORGE_DATA_DIR'] = tmp.name
root = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import SessionLocal
from app.db.models import Project
from app.render.filters import resolve_motion

def terminal(c, jid):
    for _ in range(1200):
        job = c.get('/api/jobs/'+jid).json()
        if job['status'] in ('succeeded','failed','cancelled'):
            assert job['status'] == 'succeeded', job
            return job
        time.sleep(.05)
    raise AssertionError('Preview did not finish')

def pixels(c, aid):
    path = pathlib.Path(tmp.name)/(aid+'.mp4')
    path.write_bytes(c.get('/api/assets/'+aid+'/stream').content)
    return subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-f','framemd5','-'])

with TestClient(app) as c:
    p=c.post('/api/projects',json={'title':'Recovered draft','fps':25}).json()
    with SessionLocal() as db:
        row=db.get(Project,p['id']);row.width=320;row.height=180;db.commit()
    sid=c.get('/api/projects/'+p['id']).json()['scenes'][0]['id']
    asset=c.post('/api/assets/upload?project_id='+p['id'],files={'file':('image1.png',(root/'examples/fixture_assets/image1.png').read_bytes(),'image/png')}).json()
    shot=c.post('/api/scenes/'+sid+'/shots',json={'asset_id':asset['id']}).json()
    c.patch('/api/scenes/'+sid,json={'timing_mode':'fixed','requested_duration_ms':1000,'font':{'captions_enabled':False}})
    before=c.get('/api/scenes/'+sid).json()
    edit={'revision':before['revision'],'scene':{'effect_preset':'warm'},'shots':[{'id':shot['id'],'patch':{'motion':{'type':'push_right','easing':'linear'}}}]}
    preview=c.post('/api/scenes/'+sid+'/draft-preview',json=edit)
    assert preview.status_code==200,preview.text
    pj=terminal(c,preview.json()['job_id'])
    assert c.get('/api/scenes/'+sid).json()==before,'Preview mutated the saved scene'
    applied=c.post('/api/scenes/'+sid+'/editor-state',json=edit)
    assert applied.status_code==200,applied.text
    rendered=terminal(c,c.post('/api/scenes/'+sid+'/render').json()['job_id'])
    assert pixels(c,pj['artifact_asset_id'])==pixels(c,rendered['artifact_asset_id']),'Preview/applied frames differ'
    print('PASS isolated preview preserves saved scene and matches applied renderer',flush=True)
    current=c.get('/api/scenes/'+sid).json()
    invalid={'scene':{'effect_preset':'sepia'},'shots':[{'id':shot['id'],'patch':{'crop':{'x':0,'y':0,'width':2,'height':1}}}]}
    assert c.post('/api/scenes/'+sid+'/editor-state',json=invalid).status_code==400
    assert c.get('/api/scenes/'+sid).json()==current,'Invalid transaction partially saved'
    assert c.post('/api/scenes/'+sid+'/editor-state',json=edit).status_code==409
    print('PASS atomic rollback and stale revision rejection',flush=True)
    c.post('/api/scenes/'+sid+'/editor-state',json={'scene':{'font':{'captions_enabled':False,'typewriter':True},'look':{'vignette':{'amount':40}}},'replace':True})
    restore=c.post('/api/scenes/'+sid+'/editor-state',json={'scene':{'font':before['font_json'],'look':before['look_json']},'replace':True})
    assert restore.status_code==200,restore.text
    assert restore.json()['font_json']==before['font_json']
    assert restore.json()['look_json']==before['look_json']
    print('PASS exact style restoration removes newly added keys',flush=True)
    for kind in ('plane','ship','car','pin'):
        r=c.get('/api/route-icons/'+kind)
        assert r.status_code==200 and r.content==(root/'assets/route-icons'/(kind+'.png')).read_bytes()
    assert c.get('/api/route-icons/unknown').status_code==404
    for motion in ('push_right','pull_left','rise_left','drop_left'):
        assert resolve_motion({'type':motion})!=resolve_motion({'type':'static'})
    print('PASS shared artwork endpoint and four distinct motion plans',flush=True)
