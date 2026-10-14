"""Trending transitions and aesthetic looks (0.9.4-beta.8): whip pan, spin, zoom punch, glitch,
cinematic zoom fade, before & after; Y2K, Cozy and Clean & bright looks.

Real exports through the API (two 2-second parts, 0.6 s transition): exact length, the
transition's picture checked at its middle, no black corners, plus a 1080p timing for each
transition built directly with FFmpeg. No providers."""
import io, os, pathlib, subprocess, sys, tempfile, time
import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[2]
work = tempfile.TemporaryDirectory(); os.environ['SCENEFORGE_DATA_DIR'] = work.name
sys.path.insert(0, str(ROOT / 'backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import SessionLocal
from app.db.models import Project
from app.render.ffmpeg_utils import probe
from app.render.trend_transitions import NAMES, native_graph

n = 0


def check(name, ok):
    global n
    assert ok, name; n += 1; print('PASS ' + name, flush=True)


W, H, FPS = 320, 180, 25


def frame_at(path, t):
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-ss', f'{t:.3f}', '-i', str(path), '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])
    return np.frombuffer(raw, np.uint8).reshape(H, W, 3).astype(int)


RED, BLUE = np.array([220, 40, 40]), np.array([40, 60, 220])
near = lambda px, c: np.abs(px - c).sum(axis=-1) < 90

with TestClient(app) as c:
    p = c.post('/api/projects', json={'title': 'Trend transitions', 'aspect': '16:9', 'fps': FPS}).json(); pid = p['id']
    with SessionLocal() as db:
        pr = db.get(Project, pid); pr.width = W; pr.height = H; db.commit()
    scenes = c.get(f'/api/projects/{pid}').json()['scenes'][:2]
    for s in c.get(f'/api/projects/{pid}').json()['scenes'][2:]:
        c.delete(f"/api/scenes/{s['id']}")
    for scene, colour in zip(scenes, ('#DC2828', '#283CDC')):
        img = Image.new('RGB', (W, H), colour); buf = io.BytesIO(); img.save(buf, format='PNG')
        a = c.post(f'/api/assets/upload?project_id={pid}', files={'file': (f'{colour[1:]}.png', buf.getvalue(), 'image/png')}).json()
        c.post(f"/api/scenes/{scene['id']}/shots", json={'asset_id': a['id']})
        c.patch(f"/api/scenes/{scene['id']}", json={'timing_mode': 'fixed', 'requested_duration_ms': 2000, 'lead_ms': 0, 'trail_ms': 0})
    for kind in NAMES:
        r = c.patch(f"/api/scenes/{scenes[1]['id']}", json={'transition_in': {'type': kind, 'duration_ms': 600}})
        check(f'{kind}: accepted as a transition', r.status_code == 200 and r.json()['transition_in_json']['type'] == kind)
        t0 = time.monotonic(); job = c.post(f'/api/projects/{pid}/export?skip_empty=true', json={'settings': {}}).json()
        for _ in range(3000):
            j = c.get('/api/jobs/' + job['job_id']).json()
            if j['status'] in ('succeeded', 'failed', 'cancelled'): break
            time.sleep(.1)
        assert j['status'] == 'succeeded', (kind, j.get('error'))
        out = pathlib.Path(work.name) / f'{kind}.mp4'; out.write_bytes(c.get('/api/assets/' + j['artifact_asset_id'] + '/stream').content)
        dur = probe(str(out)).duration_ms / 1000
        check(f'{kind}: exports with the exact length ({dur:.2f}s for 3.40s, {time.monotonic() - t0:.1f}s)', abs(dur - 3.4) < 0.1)
        before, after = frame_at(out, 1.0), frame_at(out, 2.6)
        check(f'{kind}: the first part before and the second part after are untouched',
              near(before, RED).mean() > .97 and near(after, BLUE).mean() > .97)
        frames = [frame_at(out, 1.42 + k * 0.05) for k in range(11)]
        dark = max((f.sum(axis=-1) < 60).mean() for f in frames)
        check(f'{kind}: no black corners or gaps during the transition (max {dark * 100:.1f}% dark)', dark < .02)
        mid = frames[5]
        red, blue = near(mid, RED).mean(), near(mid, BLUE).mean()
        if kind in ('whip_left', 'before_after'):
            ok = blue > .1 and red > .1 and (near(mid[:, :W // 3], BLUE if kind == 'before_after' else RED).mean() > .5)
        elif kind == 'whip_right':
            ok = blue > .1 and red > .1 and near(mid[:, :W // 3], BLUE).mean() > .5
        elif kind == 'zoom_fade':
            ok = red < .5 and blue < .5      # both blended mid-way
        else:
            ok = red + blue > .3             # spin / punch / glitch show one of the pictures, transformed
        check(f'{kind}: the middle of the transition shows the expected picture', ok)
        if kind == 'before_after':
            whites = [(f.min(axis=-1) > 225).any(axis=0).nonzero()[0] for f in frames[1:-1]]
            xs = [int(w.mean()) for w in whites if len(w)]
            check('before & after: a white divider line sweeps from left to right', len(xs) >= 6 and all(b >= a for a, b in zip(xs, xs[1:])))

    # aesthetic looks
    for look in ('y2k', 'cozy', 'clean_girl'):
        r = c.patch(f"/api/scenes/{scenes[0]['id']}", json={'effect_preset': look})
        job = c.post(f"/api/scenes/{scenes[0]['id']}/render").json()
        for _ in range(600):
            j = c.get('/api/jobs/' + job['job_id']).json()
            if j['status'] in ('succeeded', 'failed', 'cancelled'): break
            time.sleep(.1)
        out = pathlib.Path(work.name) / f'{look}.mp4'; out.write_bytes(c.get('/api/assets/' + j['artifact_asset_id'] + '/stream').content)
        px = frame_at(out, 1.0).reshape(-1, 3).mean(axis=0)
        check(f'look {look}: accepted, renders and changes the colour ({px.round().tolist()} vs [220, 40, 40])',
              r.status_code == 200 and j['status'] == 'succeeded' and np.abs(px - RED).sum() > 12)

# 1080p cost of each transition (FFmpeg only)
for kind in NAMES:
    g = native_graph(kind, '0:v', '1:v', 'v', 1.4, 0.6, 1920, 1080, 30, 'p')
    t0 = time.monotonic()
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=1920x1080:r=30:d=2', '-f', 'lavfi', '-i', 'smptebars=s=1920x1080:r=30:d=2',
                    '-filter_complex', ';'.join(g), '-map', '[v]', '-f', 'null', '-'], check=True)
    dt = time.monotonic() - t0
    check(f'{kind}: 1080p30, 3.4 s with the transition, built in {dt:.1f}s (limit 15 s)', dt < 15)

print(f'{n} trending transition and look checks passed')
