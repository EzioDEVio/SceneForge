"""RC8: volume envelopes on timeline audio clips (export + scene preview) and beat markers."""
import os, pathlib, subprocess, sys, tempfile, time
import numpy as np
ROOT = pathlib.Path(__file__).resolve().parents[2]
tmp = tempfile.TemporaryDirectory(); os.environ['SCENEFORGE_DATA_DIR'] = tmp.name
sys.path.insert(0, str(ROOT / 'backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import SessionLocal
from app.db.models import Project
from app.render.finishing import gain_filter
n = 0
def check(name, ok):
    global n
    assert ok, name
    n += 1; print('PASS ' + name, flush=True)
def ff(*a): subprocess.run(['ffmpeg', '-v', 'error', '-y', *a], check=True, capture_output=True)
def pcm(data):
    p = pathlib.Path(tmp.name) / f'p{time.time_ns()}.mp4'; p.write_bytes(data)
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(p), '-vn', '-ac', '1', '-ar', '8000', '-f', 's16le', '-'])
    return np.frombuffer(raw, np.int16).astype(float) / 32768
def rms(a, s, e): seg = a[int(s * 8000):int(e * 8000)]; return float(np.sqrt((seg ** 2).mean()))
def wait(c, jid):
    for _ in range(900):
        j = c.get(f'/api/jobs/{jid}').json()
        if j['status'] in ('succeeded', 'failed'): return j
        time.sleep(0.2)
t = pathlib.Path(tmp.name)
check('no envelope adds no filter', gain_filter(None, 0) is None and gain_filter([], 0) is None)
check('envelope filter evaluates per frame in dB', 'eval=frame' in gain_filter([[0, -60], [1000, 0]], 500) and 'pow(10' in gain_filter([[0, -6]], 0))
img = t / 'p.png'; ff('-f', 'lavfi', '-i', 'color=c=gray:s=320x180', '-frames:v', '1', str(img))
tone = t / 'tone.wav'; ff('-f', 'lavfi', '-i', 'sine=f=660:d=4:r=48000', str(tone))
click = t / 'beat.wav'
# 120 BPM click track (beats every 0.5 s) with a louder downbeat, 8 s
ff('-f', 'lavfi', '-i', "aevalsrc='if(lt(mod(t,0.5),0.03),sin(2*PI*1000*t)*(if(lt(mod(t,2),0.03),1,0.6)),0)':s=44100:d=8", str(click))
with TestClient(app) as c:
    pid = c.post('/api/projects', json={'title': 'RC8', 'aspect': '16:9', 'fps': 25}).json()['id']
    with SessionLocal() as db:
        row = db.get(Project, pid); row.width, row.height = 320, 180; db.commit()
    up = lambda p, m: c.post(f'/api/assets/upload?project_id={pid}', files={'file': (p.name, p.read_bytes(), m)}).json()
    a_img, a_tone, a_click = up(img, 'image/png'), up(tone, 'audio/wav'), up(click, 'audio/wav')
    sid = c.get(f'/api/projects/{pid}').json()['scenes'][0]['id']
    c.post(f'/api/scenes/{sid}/shots', json={'asset_id': a_img['id']})
    c.patch(f'/api/scenes/{sid}', json={'timing_mode': 'fixed', 'requested_duration_ms': 3000})
    clip = {'id': 'g', 'asset_id': a_tone['id'], 'name': 'tone', 'start_ms': 0, 'source_in_ms': 500, 'source_out_ms': 3500,
            'gain': [[500, -60], [1900, -60], [2100, 0]]}
    r = c.patch(f'/api/projects/{pid}', json={'finishing': {'audio_clips': [clip]}})
    check('an envelope saves sorted on the clip', r.status_code == 200 and r.json()['finishing_json']['audio_clips'][0]['gain'][0] == [500, -60.0])
    bad = [c.patch(f'/api/projects/{pid}', json={'finishing': {'audio_clips': [{**clip, 'gain': g}]}}).status_code
           for g in ([[0, 20]], [[99999, 0]], [[0]], [[i, 0] for i in range(33)], [[True, 0]])]
    check('invalid envelope points are rejected', bad == [400] * 5)
    j = wait(c, c.post(f'/api/scenes/{sid}/render').json()['job_id'])
    pv = pcm(c.get(f'/api/scenes/{sid}/preview-media').content)
    check('scene preview follows the envelope (silent, then full level)', j['status'] == 'succeeded' and rms(pv, 0.2, 1.2) < 0.01 and rms(pv, 1.8, 2.8) > 0.03)
    ej = wait(c, c.post(f'/api/projects/{pid}/export?skip_empty=true', json={'settings': {}}).json()['job_id'])
    ex = pcm(c.get(f"/api/assets/{ej['artifact_asset_id']}/stream").content)
    check('export follows the envelope in source time (trim kept it aligned)', ej['status'] == 'succeeded' and rms(ex, 0.2, 1.2) < 0.01 and rms(ex, 1.8, 2.8) > 0.03)
    # beat markers from a timeline clip, then from the music bed
    c.patch(f'/api/projects/{pid}', json={'finishing': {'audio_clips': [{'id': 'b', 'asset_id': a_click['id'], 'name': 'beat', 'start_ms': 1000, 'source_in_ms': 0, 'source_out_ms': 6000}]}})
    r = c.post(f'/api/projects/{pid}/beat-markers', json={'clip_id': 'b'})
    body = r.json()
    times = [m['time_ms'] for m in body.get('markers', [])]
    gaps = np.diff(times) if len(times) > 2 else np.array([0])
    check(f"beat markers find 120 BPM and sit at the clip's timeline position (bpm {body.get('bpm')})", r.status_code == 200 and abs(body['bpm'] - 120) < 3 and times[0] >= 1000 and abs(float(np.median(gaps)) - 500) < 40)
    bars = c.post(f'/api/projects/{pid}/beat-markers', json={'clip_id': 'b', 'every': 4}).json()['markers']
    check('every bar returns a quarter of the beats', 0 < len(bars) <= len(times) // 4 + 1)
    c.patch(f'/api/projects/{pid}', json={'finishing': {'music': {'asset_id': a_click['id'], 'volume': 50, 'duck': 0, 'fade_in_ms': 0, 'fade_out_ms': 0}}})
    mb = c.post(f'/api/projects/{pid}/beat-markers', json={}).json()
    total = sum(s['requested_duration_ms'] or 4000 for s in c.get(f'/api/projects/{pid}').json()['scenes'])
    check('music bed beats cover the project length and stop at its end', len(mb['markers']) >= 4 and mb['markers'][-1]['time_ms'] < total)
    c.patch(f'/api/projects/{pid}', json={'finishing': {}})
    check('beat markers explain when there is no music', c.post(f'/api/projects/{pid}/beat-markers', json={}).status_code == 400
          and c.post(f'/api/projects/{pid}/beat-markers', json={'every': 3}).status_code == 400)
print(f'{n} rc8 audio checks passed')
