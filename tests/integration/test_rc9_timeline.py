"""RC9: clock/iris text reveals render, clip groups and clip-attached markers persist."""
import os, pathlib, subprocess, sys, tempfile, time
import numpy as np
ROOT = pathlib.Path(__file__).resolve().parents[2]
tmp = tempfile.TemporaryDirectory(); os.environ['SCENEFORGE_DATA_DIR'] = tmp.name
sys.path.insert(0, str(ROOT / 'backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import SessionLocal
from app.db.models import Project
from app.render.subtitles import _clock_steps
n = 0
def check(name, ok):
    global n
    assert ok, name
    n += 1; print('PASS ' + name, flush=True)
shapes = _clock_steps('reveal-clock', 160, 90, 320, 180)
check('clock reveal builds growing wedge clips', len(shapes) == 24 and shapes[0].count(' ') < shapes[-1].count(' ') and shapes[0].startswith('\\clip(m 160 90'))
check('iris reveal builds circles', _clock_steps('reveal-iris', 160, 90, 320, 180)[0].startswith('\\clip(m '))
t = pathlib.Path(tmp.name)
img = t / 'bg.png'; subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=0x102040:s=320x180', '-frames:v', '1', str(img)], check=True)
tone = t / 't.wav'; subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'sine=d=2', str(tone)], check=True)
def frame(c, aid, sec):
    v = t / f'v{time.time_ns()}.mp4'; v.write_bytes(c.get(f'/api/assets/{aid}/stream').content)
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-ss', str(sec), '-i', str(v), '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'gray', '-'])
    return np.frombuffer(raw, np.uint8).reshape(180, 320)
with TestClient(app) as c:
    pid = c.post('/api/projects', json={'title': 'RC9', 'aspect': '16:9', 'fps': 25}).json()['id']
    with SessionLocal() as db:
        row = db.get(Project, pid); row.width, row.height = 320, 180; db.commit()
    a = c.post(f'/api/assets/upload?project_id={pid}', files={'file': ('bg.png', img.read_bytes(), 'image/png')}).json()
    sid = c.get(f'/api/projects/{pid}').json()['scenes'][0]['id']
    c.post(f'/api/scenes/{sid}/shots', json={'asset_id': a['id']})
    for anim in ('reveal-clock', 'reveal-clock-ccw', 'reveal-iris'):
        r = c.patch(f'/api/scenes/{sid}', json={'timing_mode': 'fixed', 'requested_duration_ms': 2000, 'font': {'captions_enabled': False, 'layers': [
            {'id': 'L', 'kind': 'text_plus', 'text': 'CLOCK', 'x': 50, 'y': 50, 'size': 90, 'color': '#FFFFFF', 'animation': anim, 'animation_ms': 1200, 'start_ms': 0, 'end_ms': 2000}]}})
        assert r.status_code == 200, r.text
        jid = c.post(f'/api/scenes/{sid}/render').json()['job_id']
        for _ in range(600):
            j = c.get(f'/api/jobs/{jid}').json()
            if j['status'] in ('succeeded', 'failed'): break
            time.sleep(0.2)
        mid, done = frame(c, j['artifact_asset_id'], 0.45), frame(c, j['artifact_asset_id'], 1.6)
        check(f'{anim}: text is partly revealed mid-way and fully shown after', j['status'] == 'succeeded' and 0 < (mid > 200).sum() < (done > 200).sum() * 0.85 and (done > 200).sum() > 300)
    tone_a = c.post(f'/api/assets/upload?project_id={pid}', files={'file': ('t.wav', tone.read_bytes(), 'audio/wav')}).json()
    clips = [{'id': x, 'asset_id': tone_a['id'], 'name': x, 'start_ms': i * 1000, 'source_in_ms': 0, 'source_out_ms': 900, 'group': 'g1'} for i, x in enumerate('ab')]
    tl = {'version': 1, 'markers': [{'id': 'm', 'time_ms': 300, 'label': 'cue', 'color': 'green', 'clip_id': 'b', 'offset_ms': 300}]}
    r = c.patch(f'/api/projects/{pid}', json={'finishing': {'audio_clips': clips, 'timeline': tl}})
    fin = r.json()['finishing_json']
    check('clip groups and clip-attached markers are saved', r.status_code == 200 and all(x['group'] == 'g1' for x in fin['audio_clips']) and fin['timeline']['markers'][0]['clip_id'] == 'b')
    bad = [c.patch(f'/api/projects/{pid}', json={'finishing': {'audio_clips': [{**clips[0], 'group': ''}]}}).status_code,
           c.patch(f'/api/projects/{pid}', json={'finishing': {'timeline': {'markers': [{'time_ms': 0, 'clip_id': 'b', 'offset_ms': -5}]}}}).status_code]
    check('invalid group ids and marker attachments are rejected', bad == [400, 400])
print(f'{n} rc9 timeline checks passed')
