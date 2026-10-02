"""0.9.0: auto-ducking for A3-A8 clips, typewriter sound preview, restore points, sample project,
caption translation plumbing and title-template layers."""
import os, pathlib, subprocess, sys, tempfile, time
import numpy as np
ROOT = pathlib.Path(__file__).resolve().parents[2]
tmp = tempfile.TemporaryDirectory(); os.environ['SCENEFORGE_DATA_DIR'] = tmp.name
sys.path.insert(0, str(ROOT / 'backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import SessionLocal
from app.db.models import Project
from app.providers import transcribe as tr
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
img = t / 'p.png'; ff('-f', 'lavfi', '-i', 'color=c=gray:s=320x180', '-frames:v', '1', str(img))
music = t / 'music.wav'; ff('-f', 'lavfi', '-i', 'sine=f=440:d=6:r=48000', str(music))
# "narration": loud 1 kHz tone from 3.0 s to 5.0 s only (silence before) — the key that should duck the music
voice = t / 'voice.wav'; ff('-f', 'lavfi', '-i', "aevalsrc='0.7*sin(2*PI*1000*t)*between(t,3,5)':s=48000:d=6", str(voice))

with TestClient(app) as c:
    pid = c.post('/api/projects', json={'title': '090', 'aspect': '16:9', 'fps': 25}).json()['id']
    with SessionLocal() as db:
        row = db.get(Project, pid); row.width, row.height = 320, 180; db.commit()
    up = lambda p, m: c.post(f'/api/assets/upload?project_id={pid}', files={'file': (p.name, p.read_bytes(), m)}).json()
    a_img, a_music, a_voice = up(img, 'image/png'), up(music, 'audio/wav'), up(voice, 'audio/wav')
    sid = c.get(f'/api/projects/{pid}').json()['scenes'][0]['id']
    c.post(f'/api/scenes/{sid}/shots', json={'asset_id': a_img['id']})
    c.patch(f'/api/scenes/{sid}', json={'timing_mode': 'fixed', 'requested_duration_ms': 6000})

    # ---- auto-ducking -------------------------------------------------------------------------
    base_clip = {'id': 'm', 'asset_id': a_music['id'], 'name': 'music', 'start_ms': 0, 'source_in_ms': 0, 'source_out_ms': 6000, 'track': 'A4'}
    r = c.patch(f'/api/projects/{pid}', json={'finishing': {'audio_clips': [{**base_clip, 'duck': 80}]}})
    check('a timeline clip saves an auto-ducking amount', r.status_code == 200 and r.json()['finishing_json']['audio_clips'][0]['duck'] == 80)
    bad = [c.patch(f'/api/projects/{pid}', json={'finishing': {'audio_clips': [{**base_clip, 'duck': v}]}}).status_code for v in (101, -1, True, 'x')]
    check('invalid ducking amounts are rejected', bad == [400] * 4)
    r = c.patch(f'/api/projects/{pid}', json={'finishing': {'audio_clips': [{**base_clip, 'duck': 0}]}})
    check('ducking 0 is stored as off', 'duck' not in r.json()['finishing_json']['audio_clips'][0])
    # narration lives on A1 (scene audio): import the voice file as the scene's narration
    r = c.post(f'/api/scenes/{sid}/voice-takes/from-asset', json={'asset_id': a_voice['id']})
    check('narration attached for the ducking test', r.status_code < 400)
    c.patch(f'/api/scenes/{sid}', json={'timing_mode': 'fixed', 'requested_duration_ms': 6000, 'lead_ms': 0, 'trail_ms': 0})

    def export_levels(duck):
        clip = {**base_clip, **({'duck': duck} if duck else {})}
        c.patch(f'/api/projects/{pid}', json={'finishing': {'audio_clips': [clip]}})
        j = wait(c, c.post(f'/api/scenes/{sid}/render').json()['job_id'])
        assert j['status'] == 'succeeded', j
        ej = wait(c, c.post(f'/api/projects/{pid}/export?skip_empty=true', json={'settings': {}}).json()['job_id'])
        assert ej['status'] == 'succeeded', ej
        a = pcm(c.get(f"/api/assets/{ej['artifact_asset_id']}/stream").content)
        # isolate the 440 Hz music: band-pass in the FFT domain around 440 Hz
        spec = np.fft.rfft(a); f = np.fft.rfftfreq(a.size, 1 / 8000); spec[(f < 380) | (f > 500)] = 0
        m = np.fft.irfft(spec, a.size)
        return rms(m, 0.5, 2.5), rms(m, 3.4, 4.6)
    plain_before, plain_during = export_levels(0)
    duck_before, duck_during = export_levels(90)
    check('without ducking the music keeps its level under the voice', plain_during > plain_before * 0.8)
    check('with ducking the music drops while the voice plays', duck_during < plain_during * 0.6 and duck_before > plain_before * 0.8)

    # ---- typewriter sound preview -------------------------------------------------------------
    c.patch(f'/api/scenes/{sid}', json={'subtitle_text': 'Hello typing', 'font': {'typewriter': True, 'typewriter_sound': True, 'typewriter_volume': 60}})
    r = c.get(f'/api/scenes/{sid}/typewriter-preview')
    wav = t / 'tw.wav'; wav.write_bytes(r.content)
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(wav), '-ac', '1', '-ar', '8000', '-f', 's16le', '-'])
    s = np.frombuffer(raw, np.int16).astype(float) / 32768
    check('typewriter preview returns audible keystrokes as WAV', r.status_code == 200 and r.headers['content-type'] == 'audio/wav' and s.size > 4000 and np.abs(s).max() > 0.05)
    bad_patch = c.patch(f'/api/scenes/{sid}', json={'font': {'typewriter_sound_asset_id': a_img['id']}})
    r = c.get(f'/api/scenes/{sid}/typewriter-preview')
    check('a non-audio typewriter sound is refused with a clear message', bad_patch.status_code == 400 or (r.status_code == 409 and 'sound' in r.json()['detail'].lower()))
    c.patch(f'/api/scenes/{sid}', json={'font': {'typewriter_sound_asset_id': None}})
    check('typewriter preview 404s for an unknown scene', c.get('/api/scenes/nope/typewriter-preview').status_code == 404)

    # ---- restore points -----------------------------------------------------------------------
    r = c.post(f'/api/projects/{pid}/snapshots', json={'auto': True})
    check('first automatic restore point is saved', r.json()['saved'] is True)
    check('an unchanged project does not make another automatic one', c.post(f'/api/projects/{pid}/snapshots', json={'auto': True}).json()['saved'] is False)
    first = r.json()['snapshot']['id']
    c.patch(f'/api/scenes/{sid}', json={'title': 'Edited later'})
    r = c.post(f'/api/projects/{pid}/snapshots', json={'label': 'After edit'})
    check('a named manual restore point is saved', r.json()['saved'] and r.json()['snapshot']['label'] == 'After edit' and r.json()['snapshot']['reason'] == 'manual')
    snaps = c.get(f'/api/projects/{pid}/snapshots').json()['snapshots']
    check('restore points list newest first without internal fields', [x['id'] for x in snaps][-1] == first and 'hash' not in snaps[0] and 'seq' not in snaps[0])
    r = c.post(f'/api/projects/{pid}/snapshots/{first}/restore')
    rid = r.json()['id']
    rp = c.get(f'/api/projects/{rid}').json()
    orig = c.get(f'/api/projects/{pid}').json()
    check('restoring opens a NEW project with the old content', r.status_code == 200 and rid != pid and '(restored' in rp['title'] and rp['scenes'][0]['title'] != 'Edited later')
    check('the current project is untouched by a restore', orig['scenes'][0]['title'] == 'Edited later')
    check('restored shots point at the copied media', rp['scenes'][0]['shots'][0]['asset_id'] != orig['scenes'][0]['shots'][0]['asset_id'] and c.get(f"/api/assets/{rp['scenes'][0]['shots'][0]['asset_id']}/stream").content == c.get(f"/api/assets/{orig['scenes'][0]['shots'][0]['asset_id']}/stream").content)
    check('restored timeline clips are remapped to the copy', rp['finishing_json']['audio_clips'][0]['asset_id'] != orig['finishing_json']['audio_clips'][0]['asset_id'])
    check('deleting a restore point works and unknown ones 404', c.delete(f'/api/projects/{pid}/snapshots/{first}').status_code == 204 and c.delete(f'/api/projects/{pid}/snapshots/{first}').status_code == 404)
    check('path tricks never reach a file', c.post(f'/api/projects/{pid}/snapshots/..%2F..%2Fx/restore').status_code in (404, 405) and c.post(f'/api/projects/{pid}/snapshots/..\\x/restore').status_code == 404)
    c.delete(f'/api/projects/{rid}')
    snapdir = pathlib.Path(tmp.name) / 'snapshots' / rid
    check('deleting a project removes its restore points', not any(snapdir.glob('*.json')) if snapdir.exists() else True)

    # ---- title templates (frontend inserts plain layers; the backend must accept them) --------
    layers = [{'id': 'lt1', 'kind': 'text_plus', 'text': 'Your Name', 'x': 7, 'y': 79, 'size': 64, 'family': 'Poppins', 'align': 'left', 'bold': True,
               'color': '#FFFFFF', 'shadow': 4, 'outline_width': 0, 'spacing': 0, 'animation': 'slide', 'animation_ms': 900, 'exit_ms': 400, 'start_ms': 300, 'end_ms': 5000},
              {'id': 'lt2', 'kind': 'text_box', 'text': 'Quote', 'x': 50, 'y': 45, 'size': 58, 'family': 'Amiri', 'box_width': 70, 'bold': False, 'color': '#FFFFFF',
               'shadow': 4, 'outline_width': 0, 'spacing': 0, 'animation': 'words-fade', 'animation_ms': 1600, 'exit_ms': 400, 'start_ms': 0, 'end_ms': 0}]
    r = c.patch(f'/api/scenes/{sid}', json={'font': {'layers': layers}})
    print(r.status_code, r.text[:300]) if r.status_code != 200 else None
    check('template layers save', r.status_code == 200 and len(r.json()['font_json']['layers']) == 2)
    j = wait(c, c.post(f'/api/scenes/{sid}/render').json()['job_id'])
    check('a scene with template layers renders', j['status'] == 'succeeded')

    # ---- caption translation (Whisper is replaced by a stub: no model download in CI) ----------
    calls = []
    def fake_local(path, language, task='transcribe'):
        calls.append(task)
        if task == 'translate':
            return {'language': 'en', 'text': 'hello world friends', 'provider': 'local', 'word_timing': 'whisper',
                    'words': [['hello', 3000, 3300], ['world', 3300, 3700], ['friends', 4400, 4800]]}
        return {'language': 'ar', 'text': 'مرحبا يا عالم يا اصدقاء', 'provider': 'local', 'word_timing': 'whisper',
                'words': [['مرحبا', 3000, 3300], ['يا', 3300, 3400], ['عالم', 3400, 3700], ['يا', 4300, 4400], ['اصدقاء', 4400, 4800]]}
    real = tr._local
    tr._local = fake_local
    try:
        r = c.post(f'/api/scenes/{sid}/auto-captions', json={'provider': 'local', 'translate': 'english', 'phrase_words': 3})
        check('English captions use Whisper translate', r.status_code == 200 and calls == ['translate'] and r.json()['subtitle_text'] == 'hello world friends' and r.json()['font_json']['transcript']['translated'] == 'english')
        calls.clear()
        r = c.post(f'/api/scenes/{sid}/auto-captions', json={'provider': 'local', 'translate': 'bilingual', 'phrase_words': 3})
        segs = r.json()['font_json']['caption_segments']
        check('bilingual captions listen twice', calls == ['transcribe', 'translate'])
        check('bilingual captions put English under each spoken line', len(segs) == 2 and segs[0]['text'] == 'مرحبا يا عالم\nhello world' and segs[1]['text'] == 'يا اصدقاء\nfriends')
        calls.clear()
        r = c.post(f'/api/scenes/{sid}/auto-captions', json={'provider': 'openai', 'translate': 'english'})
        check('translation always runs on Local Whisper (no cloud cost)', r.status_code == 200 and calls == ['translate'])
        check('an unknown translate value is rejected', c.post(f'/api/scenes/{sid}/auto-captions', json={'translate': 'klingon'}).status_code == 400)
        j = wait(c, c.post(f'/api/scenes/{sid}/render').json()['job_id'])
        check('a scene with two-line bilingual captions renders', j['status'] == 'succeeded')
    finally:
        tr._local = real

    # ---- sample project ------------------------------------------------------------------------
    r = c.post('/api/sample-project')
    sp = c.get(f"/api/projects/{r.json()['id']}").json()
    check('the sample project is created with three ready scenes', r.status_code == 200 and len(sp['scenes']) == 3 and all(s['shots'] for s in sp['scenes']))
    check('the sample shows captions, a typewriter, effects, music and timeline sounds',
          any(s['font_json'].get('typewriter') for s in sp['scenes']) and all(s['effect_preset'] != 'original' for s in sp['scenes'])
          and sp['finishing_json']['music'] and len(sp['finishing_json']['audio_clips']) == 2 and sp['finishing_json']['timeline']['markers'])
    j = wait(c, c.post(f"/api/scenes/{sp['scenes'][2]['id']}/render").json()['job_id'])
    check('a sample scene renders (typewriter with sound)', j['status'] == 'succeeded')
print(f'{n} checks passed')
