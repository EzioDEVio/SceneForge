"""RC6: detach narration/clip sound to timeline audio, and scene renders that play the
timeline audio + music underneath them (without baking it into the export part)."""
import os, pathlib, subprocess, sys, tempfile, time
import numpy as np
ROOT = pathlib.Path(__file__).resolve().parents[2]
tmp = tempfile.TemporaryDirectory(); os.environ['SCENEFORGE_DATA_DIR'] = tmp.name
sys.path.insert(0, str(ROOT / 'backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import SessionLocal
from app.db.models import Project
n = 0
def check(name, ok):
    global n
    assert ok, name
    n += 1; print('PASS ' + name, flush=True)
def ff(*a): subprocess.run(['ffmpeg', '-v', 'error', '-y', *a], check=True, capture_output=True)
def pcm(data: bytes):
    p = pathlib.Path(tmp.name) / f'probe_{time.time_ns()}.mp4'; p.write_bytes(data)
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(p), '-vn', '-ac', '1', '-ar', '8000', '-f', 's16le', '-'])
    return np.frombuffer(raw, np.int16).astype(float) / 32768
def rms(a, s, e): seg = a[int(s * 8000):int(e * 8000)]; return float(np.sqrt((seg ** 2).mean())) if seg.size else 0.0
def wait(client, job_id):
    for _ in range(600):
        j = client.get(f'/api/jobs/{job_id}').json()
        if j['status'] in ('succeeded', 'failed', 'cancelled'): return j
        time.sleep(0.1)
    raise AssertionError('job timed out')

t = pathlib.Path(tmp.name)
video = t / 'talk.mp4'; tone = t / 'tone.wav'; music = t / 'music.wav'
ff('-f', 'lavfi', '-i', 'color=c=gray:s=320x180:d=2:r=25', '-f', 'lavfi', '-i', 'sine=f=440:d=2:r=48000', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', str(video))
ff('-f', 'lavfi', '-i', 'sine=f=880:d=3:r=48000', str(tone))
ff('-f', 'lavfi', '-i', 'sine=f=220:d=10:r=48000', str(music))

with TestClient(app) as client:
    p = client.post('/api/projects', json={'title': 'RC6 audio', 'aspect': '16:9', 'fps': 25}).json(); pid = p['id']
    with SessionLocal() as db:
        row = db.get(Project, pid); row.width, row.height = 320, 180; db.commit()
    up = lambda path, mime: client.post(f'/api/assets/upload?project_id={pid}', files={'file': (path.name, path.read_bytes(), mime)}).json()
    vid, tone_a, music_a = up(video, 'video/mp4'), up(tone, 'audio/wav'), up(music, 'audio/wav')
    scenes = client.get(f'/api/projects/{pid}').json()['scenes']
    s1, s2 = scenes[0]['id'], scenes[1]['id']
    shot = client.post(f'/api/scenes/{s1}/shots', json={'asset_id': vid['id']}).json()
    client.patch(f'/api/scenes/{s1}', json={'timing_mode': 'fixed', 'requested_duration_ms': 2000})

    # --- detach clip sound (A2) -------------------------------------------------------
    r = client.post(f'/api/scenes/{s1}/detach-audio', json={'source': 'shot', 'shot_id': shot['id'], 'duration_ms': 1500})
    check('clip sound detaches into a new project audio file', r.status_code == 200 and r.json()['asset']['type'] == 'audio' and 1400 <= r.json()['asset']['duration_ms'] <= 1600)
    detached = r.json()['asset']
    check('the detached file can be used as a timeline audio clip',
          client.patch(f'/api/projects/{pid}', json={'finishing': {'audio_clips': [{'id': 'd', 'asset_id': detached['id'], 'name': 'd', 'start_ms': 0, 'source_in_ms': 0, 'source_out_ms': detached['duration_ms']}]}}).status_code == 200)
    check('detach refuses a missing shot and unknown sources',
          client.post(f'/api/scenes/{s1}/detach-audio', json={'source': 'shot', 'shot_id': 'nope', 'duration_ms': 500}).status_code == 400
          and client.post(f'/api/scenes/{s1}/detach-audio', json={'source': 'other'}).status_code == 400)
    check('narration detach explains when a scene has no narration', client.post(f'/api/scenes/{s1}/detach-audio', json={'source': 'narration'}).status_code == 400)

    # --- scene render plays timeline audio + music under it ------------------------------
    shot2 = client.post(f'/api/scenes/{s2}/shots', json={'asset_id': vid['id']}).json()
    client.patch(f'/api/scenes/shots/{shot2["id"]}', json={'audio': {'volume': 100, 'mute': True, 'duck': True}})
    client.patch(f'/api/scenes/{s2}', json={'transition_in': {'type': 'cut', 'duration_ms': 0}})
    client.patch(f'/api/scenes/{s2}', json={'timing_mode': 'fixed', 'requested_duration_ms': 2000})
    client.patch(f'/api/scenes/shots/{shot["id"]}', json={'audio': {'volume': 100, 'mute': True, 'duck': True}})
    job = wait(client, client.post(f'/api/scenes/{s1}/render').json()['job_id'])
    check('scene renders', job['status'] == 'succeeded')
    client.patch(f'/api/projects/{pid}', json={'finishing': {}})
    plain = client.get(f'/api/scenes/{s1}/preview-media', follow_redirects=False)
    check('with no timeline audio the preview is the plain render', plain.status_code == 307 and '/stream' in plain.headers['location'])
    # A3 clip from 0.5–1.5 s of the timeline, plus a clip that starts in scene 2 only.
    clips = [{'id': 'a', 'asset_id': tone_a['id'], 'name': 'tone', 'start_ms': 500, 'source_in_ms': 0, 'source_out_ms': 1000},
             {'id': 'b', 'asset_id': tone_a['id'], 'name': 'later', 'start_ms': 2500, 'source_in_ms': 0, 'source_out_ms': 1000, 'track': 'A4'}]
    client.patch(f'/api/projects/{pid}', json={'finishing': {'audio_clips': clips}})
    mixed = client.get(f'/api/scenes/{s1}/preview-media')
    a = pcm(mixed.content)
    check('scene render preview includes the timeline audio clip at its time', mixed.status_code == 200 and rms(a, 0.7, 1.3) > 0.05 and rms(a, 1.6, 1.9) < 0.01 and rms(a, 0.05, 0.4) < 0.01)
    job2 = wait(client, client.post(f'/api/scenes/{s2}/render').json()['job_id'])
    b = pcm(client.get(f'/api/scenes/{s2}/preview-media').content)
    check('a clip that starts inside a later scene plays at its offset in that scene', job2['status'] == 'succeeded' and rms(b, 0.6, 1.4) > 0.05 and rms(b, 0.05, 0.4) < 0.01)
    part_audio = pcm(client.get(f"/api/assets/{client.get(f'/api/scenes/{s1}').json()['rendered_asset_id']}/stream").content)
    check('the rendered part itself stays clean, so full export does not mix it twice', rms(part_audio, 0.7, 1.3) < 0.01)
    client.patch(f'/api/projects/{pid}', json={'finishing': {'audio_clips': clips, 'music': {'asset_id': music_a['id'], 'volume': 60, 'duck': 0, 'fade_in_ms': 0, 'fade_out_ms': 0}}})
    m = pcm(client.get(f'/api/scenes/{s1}/preview-media').content)
    check('the music bed plays under the scene render', rms(m, 1.6, 1.9) > 0.02)
    client.patch(f'/api/projects/{pid}', json={'finishing': {'audio_clips': clips, 'timeline': {'tracks': {'A3': {'mute': True}}}}})
    muted = pcm(client.get(f'/api/scenes/{s1}/preview-media', follow_redirects=True).content)
    check('track mute also applies to the scene render preview', rms(muted, 0.7, 1.3) < 0.01)
    job = wait(client, client.post(f'/api/projects/{pid}/export?skip_empty=true', json={'settings': {}}).json()['job_id'])
    ex = pcm(client.get(f"/api/assets/{job['artifact_asset_id']}/stream").content)
    check('full export still mixes each unmuted clip exactly once', job['status'] == 'succeeded' and rms(ex, 2.6, 3.3) > 0.05 and rms(ex, 2.6, 3.3) < 0.6 and rms(ex, 0.7, 1.3) < 0.01)
print(f'{n} rc6 timeline audio checks passed')
