"""Trending effects in More effects (0.9.4-beta.7): beat zoom, flash, motion trails, mirror.
Real FFmpeg filter graphs (pixel checks) and real scene renders through the API, for a
picture and a video clip, plus validation. No providers, no downloads."""
import io, os, pathlib, sys, tempfile, time
import subprocess
import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[2]
work = tempfile.TemporaryDirectory(); os.environ['SCENEFORGE_DATA_DIR'] = work.name
sys.path.insert(0, str(ROOT / 'backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import SessionLocal
from app.db.models import Project
from app.render.fx_stack import stack_graph, active_stages
n = 0


def check(name, ok):
    global n
    assert ok, name; n += 1; print('PASS ' + name, flush=True)


W, H, FPS = 160, 96, 25   # even halves (yuv420 chroma)


def frames(look, src='testsrc2', d=1.0, count=25):
    graph, label = stack_graph('0:v', look, W, H, FPS, d, pathlib.Path(work.name) / 'fx-cache')
    fc = ';'.join([*graph, f'[{label}]format=rgb24[v]'])
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', (f'{src}s={W}x{H}:r={FPS}:d={d}' if src.endswith(':') else f'{src}=s={W}x{H}:r={FPS}:d={d}'), '-filter_complex', fc,
                                   '-map', '[v]', '-frames:v', str(count), '-f', 'rawvideo', '-'])
    return np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3).astype(float)


orig = frames({})
diff = lambda a, b: np.abs(a - b).mean()

# Beat zoom: frame 0 is punched in, half a beat later it has eased back almost to normal.
pz = frames({'pulse': {'amount': 100, 'bpm': 60}})
check('beat zoom punches in on the beat', diff(pz[0], orig[0]) > 5)
check('beat zoom eases back between beats', diff(pz[20], orig[20]) < diff(pz[0], orig[0]) / 2)
check('beat zoom keeps the frame size', pz.shape == orig.shape)

# Flash: intro is bright at the start and gone after half a second; strobe repeats on the beat.
fi = frames({'flash': {'amount': 100, 'mode': 'intro', 'bpm': 120}})
check('intro flash brightens the first frame', fi[0].mean() > orig[0].mean() + 40)
check('intro flash fades out', abs(fi[15].mean() - orig[15].mean()) < 3)
fb = frames({'flash': {'amount': 100, 'mode': 'beats', 'bpm': 120}})
check('strobe flashes again on the next beat (0.5 s at 120 bpm)', fb[13].mean() > orig[13].mean() + 15 and fb[10].mean() < fb[13].mean() - 10)

# Motion trails: a moving picture is blended with earlier frames; a still picture is unchanged.
tr = frames({'trails': {'amount': 100}})
check('motion trails blend moving content with earlier frames', diff(tr[10], orig[10]) > 3)
still = frames({'trails': {'amount': 100}}, src='color=c=0x808080:')
check('motion trails leave a still picture unchanged', diff(still[10], frames({}, src='color=c=0x808080:')[10]) < 1)

# Mirror: the left half reflected onto the right; four corners for kaleidoscope.
for mode in ('left', 'right', 'top', 'bottom', 'quad'):
    m = frames({'mirror': {'mode': mode}}, count=1)[0]
    if mode == 'left':
        ok = np.allclose(m[:, :W // 2], orig[0][:, :W // 2], atol=8) and np.allclose(m[:, W // 2:], m[:, :W // 2][:, ::-1], atol=8)
    elif mode == 'right':
        ok = np.allclose(m[:, W // 2:], orig[0][:, W // 2:], atol=8) and np.allclose(m[:, :W // 2], m[:, W // 2:][:, ::-1], atol=8)
    elif mode == 'top':
        ok = np.allclose(m[:H // 2], orig[0][:H // 2], atol=8) and np.allclose(m[H // 2:], m[:H // 2][::-1], atol=8)
    elif mode == 'bottom':
        ok = np.allclose(m[H // 2:], orig[0][H // 2:], atol=8) and np.allclose(m[:H // 2], m[H // 2:][::-1], atol=8)
    else:
        ok = np.allclose(m[:H // 2, W // 2:], m[:H // 2, :W // 2][:, ::-1], atol=8) and np.allclose(m[H // 2:], m[:H // 2][::-1], atol=8)
    check(f'mirror {mode} reflects the picture exactly', m.shape == (H, W, 3) and ok)

all4 = {'pulse': {'amount': 50, 'bpm': 120}, 'flash': {'amount': 60, 'mode': 'both', 'bpm': 120}, 'trails': {'amount': 40}, 'mirror': {'mode': 'quad'}}
check('all four stack in the default order (mirror, trails … beat zoom, flash)', active_stages(all4) == ['mirror', 'trails', 'pulse', 'flash'])
check('bypassing all four gives back the original picture',
      np.array_equal(frames({**all4, 'fx_bypass': ['mirror', 'trails', 'pulse', 'flash']}, count=3), orig[:3]))

with TestClient(app) as c:
    p = c.post('/api/projects', json={'title': 'Trending effects', 'aspect': '16:9', 'fps': 25}).json(); pid = p['id']
    with SessionLocal() as db:
        pr = db.get(Project, pid); pr.width = 320; pr.height = 180; db.commit()
    scenes = c.get('/api/projects/' + pid).json()['scenes']
    img = Image.new('RGB', (320, 180), '#305070'); buf = io.BytesIO(); img.save(buf, format='PNG')
    picture = c.post('/api/assets/upload?project_id=' + pid, files={'file': ('base.png', buf.getvalue(), 'image/png')}).json()
    clip = c.post('/api/assets/upload?project_id=' + pid, files={'file': ('clip.mp4', (ROOT / 'examples/fixture_assets/clip1.mp4').read_bytes(), 'video/mp4')}).json()
    for bad in [{'pulse': {'amount': 101}}, {'pulse': {'bpm': 20}}, {'flash': {'mode': 'sometimes'}}, {'trails': {'amount': -1}},
                {'mirror': {'mode': 'diagonal'}}, {'mirror': {'mode': 'left', 'extra': 1}}]:
        check(f'invalid setting refused: {bad}', c.patch('/api/scenes/' + scenes[0]['id'], json={'look': bad}).status_code == 400)
    for sid, asset in ((scenes[0]['id'], picture), (scenes[1]['id'], clip)):
        c.post('/api/scenes/' + sid + '/shots', json={'asset_id': asset['id']})
        r = c.patch('/api/scenes/' + sid, json={'timing_mode': 'fixed', 'requested_duration_ms': 2000, 'lead_ms': 0, 'trail_ms': 0, 'look': all4})
        check('all four trending effects saved through the API', r.status_code == 200 and all(k in r.json()['look_json'] for k in all4))
        t0 = time.time(); job = c.post('/api/scenes/' + sid + '/render').json()
        for _ in range(900):
            j = c.get('/api/jobs/' + job['job_id']).json()
            if j['status'] in ('succeeded', 'failed', 'cancelled'): break
            time.sleep(.1)
        check(f"{'picture' if asset is picture else 'video'} scene with all four renders ({time.time() - t0:.1f} s)", j['status'] == 'succeeded')
    pr = c.post('/api/look-presets', json={'preset': {'name': 'Trend pack', 'look': all4}})
    check('trending effects can be saved in a look preset and are kept', pr.status_code in (200, 201) and all(k in pr.json()['added'][0]['look'] for k in all4))

print(f'{n} trending effect checks passed')
