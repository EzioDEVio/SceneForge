"""Trending effects, part 2 (0.9.4-beta.9), in More effects -> Trending: RGB split, cinematic
fade & zoom, intro move, before & after, speed blur (after CapCut's 2026 trend list).

Real FFmpeg filter graphs checked frame by frame (length kept, effect where and when it should
be, untouched elsewhere), validation, real part renders and an export through the API, look
presets, the effect stack order, and a 1080p timing for each. No providers, no downloads."""
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
from app.render.fx_stack import stack_graph, active_stages
from app.render.ffmpeg_utils import probe
n = 0


def check(name, ok):
    global n
    assert ok, name; n += 1; print('PASS ' + name, flush=True)


W, H, FPS, D = 160, 96, 25, 2.0
CACHE = pathlib.Path(work.name) / 'fx-cache'


def frames(look, src='testsrc2', w=W, h=H):
    graph, label = stack_graph('0:v', look, w, h, FPS, D, CACHE)
    fc = ';'.join([*graph, f'[{label}]format=rgb24[v]'])
    inp = f'{src}=s={w}x{h}:r={FPS}:d={D}' if '=' not in src else f'{src}:s={w}x{h}:r={FPS}:d={D}'
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', inp, '-filter_complex', fc, '-map', '[v]', '-f', 'rawvideo', '-'])
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3).astype(float)


orig = frames({})
total = len(orig)
diff = lambda a, b: np.abs(a - b).mean()
grey = lambda f: np.abs(f - f.mean(axis=-1, keepdims=True)).mean()      # 0 for a black & white picture
sharp = lambda f: np.abs(np.diff(f.mean(axis=-1), axis=1)).mean()      # horizontal detail

# ---- RGB split ---------------------------------------------------------------------------
cs = frames({'colorsplit': {'amount': 100, 'mode': 'beats', 'bpm': 60}})
check('RGB split keeps every frame', len(cs) == total)
check('RGB split snaps apart on the beat', diff(cs[0], orig[0]) > 8)
check('RGB split settles back between beats', diff(cs[20], orig[20]) < diff(cs[0], orig[0]) / 3)
check('RGB split moves red and blue far more than green',
      diff(cs[0][..., 1], orig[0][..., 1]) * 3 < min(diff(cs[0][..., 0], orig[0][..., 0]), diff(cs[0][..., 2], orig[0][..., 2])) and diff(cs[0][..., 2], orig[0][..., 2]) > 8)
st = frames({'colorsplit': {'amount': 60, 'mode': 'steady', 'bpm': 120}})
check('steady RGB split stays split', min(diff(st[k], orig[k]) for k in (0, 12, 30, 45)) > 4)
check('RGB split at 0 % changes nothing', np.array_equal(frames({'colorsplit': {'amount': 0, 'mode': 'steady', 'bpm': 120}}), orig))

# ---- Cinematic fade & zoom ----------------------------------------------------------------
co = frames({'cineopen': {'amount': 100, 'zoom': 'in', 'fade': 'both', 'seconds': 0.6}})
check('cinematic: keeps every frame', len(co) == total)
check('cinematic: starts black and fades in', co[0].mean() < 6 and co[7].mean() > co[3].mean() > co[0].mean())
check('cinematic: full brightness in the middle', abs(co[25].mean() - orig[25].mean()) < 12)
check('cinematic: fades out at the end', co[-1].mean() < orig[-1].mean() * 0.25)
check('cinematic: the picture is pushed in by the end (zoom)', diff(co[-17], orig[-17]) > diff(co[16], orig[16]))
co_none = frames({'cineopen': {'amount': 0, 'zoom': 'none', 'fade': 'none', 'seconds': 1}})
check('cinematic with no zoom and no fade changes nothing', diff(co_none, orig) < 0.5)

# ---- Intro move -----------------------------------------------------------------------------
for style in ('swipe_left', 'swipe_right', 'swipe_up', 'spin', 'zoom'):
    it = frames({'intro': {'style': style, 'seconds': 0.6}})
    dark = max((f.sum(axis=-1) < 30).mean() for f in it[:15])
    check(f'intro {style}: keeps every frame, moves at the start, untouched after 0.6 s, no black gaps ({dark * 100:.1f}% dark)',
          len(it) == total and diff(it[2], orig[2]) > 10 and diff(it[20:], orig[20:]) < 1.5 and dark < .03)

# ---- Before & after -------------------------------------------------------------------------
ba = frames({'beforeafter': {'before': 'bw', 'start': 25, 'seconds': 1.0}})
check('before & after: keeps every frame', len(ba) == total)
check('before & after: black & white before the sweep', grey(ba[5]) < 2 and grey(orig[5]) > 20)
mid = ba[25]                                                   # halfway through the sweep (0.5 s .. 1.5 s)
check('before & after: halfway, colour on the left and black & white on the right',
      grey(mid[:, :W // 3]) > 15 and grey(mid[:, -W // 3:]) < 3)
whites = [(f.min(axis=-1) > 235).all(axis=0).nonzero()[0] for f in ba[14:37:4]]
xs = [int(w.mean()) for w in whites if len(w)]
check(f'before & after: a white line sweeps left to right {xs}', len(xs) >= 5 and all(b > a for a, b in zip(xs, xs[1:])))
check('before & after: the real picture after the sweep', diff(ba[42:], orig[42:]) < 1.5)
for style in ('faded', 'dark'):
    b2 = frames({'beforeafter': {'before': style, 'start': 0, 'seconds': 0.3}})
    check(f'before & after ({style}): a different "before" picture, then the original', diff(b2[0], orig[0]) > 8 and diff(b2[20:], orig[20:]) < 1.5)

# ---- Speed blur -----------------------------------------------------------------------------
sb = frames({'speedblur': {'amount': 80, 'direction': 'horizontal', 'when': 'whole'}})
check('speed blur: keeps every frame and blurs sideways', len(sb) == total and sharp(sb[10]) < sharp(orig[10]) * 0.7)
sv = frames({'speedblur': {'amount': 80, 'direction': 'vertical', 'when': 'whole'}})
vert = lambda f: np.abs(np.diff(f.mean(axis=-1), axis=0)).mean()
check('speed blur up and down blurs vertical detail more than sideways', vert(sv[10]) / vert(orig[10]) < sharp(sv[10]) / sharp(orig[10]))
ss = frames({'speedblur': {'amount': 100, 'direction': 'horizontal', 'when': 'start'}})
check('speed blur whoosh: blurred at the start, clears up, untouched after half a second',
      len(ss) == total and sharp(ss[0]) < sharp(orig[0]) * 0.7 and sharp(ss[9]) > sharp(ss[1]) and diff(ss[14:], orig[14:]) < 1.5)

# ---- all five together, and a still picture -----------------------------------------------
all5 = {'colorsplit': {'amount': 50, 'mode': 'beats', 'bpm': 120}, 'cineopen': {'amount': 40, 'zoom': 'in', 'fade': 'in', 'seconds': 0.5},
        'intro': {'style': 'spin', 'seconds': 0.5}, 'beforeafter': {'before': 'faded', 'start': 30, 'seconds': 0.8},
        'speedblur': {'amount': 30, 'direction': 'horizontal', 'when': 'start'}}
check('all five stack in the default order', active_stages(all5) == ['speedblur', 'colorsplit', 'beforeafter', 'intro', 'cineopen'])
check('all five together keep every frame', len(frames(all5)) == total)
check('all five on a still picture keep every frame', len(frames(all5, src='color=c=0x406080')) == total)
check('bypassing all five gives back the original picture',
      np.array_equal(frames({**all5, 'fx_bypass': list(all5)}), orig))

with TestClient(app) as c:
    p = c.post('/api/projects', json={'title': 'Trending effects 2', 'aspect': '16:9', 'fps': 25}).json(); pid = p['id']
    with SessionLocal() as db:
        pr = db.get(Project, pid); pr.width = 320; pr.height = 180; db.commit()
    scenes = c.get('/api/projects/' + pid).json()['scenes']
    img = Image.new('RGB', (320, 180), '#C05030'); buf = io.BytesIO(); img.save(buf, format='PNG')
    picture = c.post('/api/assets/upload?project_id=' + pid, files={'file': ('base.png', buf.getvalue(), 'image/png')}).json()
    clip = c.post('/api/assets/upload?project_id=' + pid, files={'file': ('clip.mp4', (ROOT / 'examples/fixture_assets/clip1.mp4').read_bytes(), 'video/mp4')}).json()
    for bad in [{'colorsplit': {'amount': 101}}, {'colorsplit': {'mode': 'sometimes'}}, {'cineopen': {'zoom': 'sideways'}}, {'cineopen': {'seconds': 9}},
                {'intro': {'style': 'flip'}}, {'intro': {'seconds': 3}}, {'beforeafter': {'before': 'sepia'}}, {'beforeafter': {'start': 95}},
                {'speedblur': {'direction': 'diagonal'}}, {'speedblur': {'when': 'end'}}, {'speedblur': {'amount': 50, 'extra': 1}}]:
        check(f'invalid setting refused: {bad}', c.patch('/api/scenes/' + scenes[0]['id'], json={'look': bad}).status_code == 400)
    r = c.patch('/api/scenes/' + scenes[0]['id'], json={'look': {'intro': {}}})
    check('defaults are filled in when only the effect is switched on', r.status_code == 200 and r.json()['look_json']['intro'] == {'style': 'swipe_left', 'seconds': 0.5})
    order = ['cineopen', 'intro', 'beforeafter', 'colorsplit', 'speedblur']
    for sid, asset in ((scenes[0]['id'], picture), (scenes[1]['id'], clip)):
        c.post('/api/scenes/' + sid + '/shots', json={'asset_id': asset['id']})
        r = c.patch('/api/scenes/' + sid, json={'timing_mode': 'fixed', 'requested_duration_ms': 2000, 'lead_ms': 0, 'trail_ms': 0, 'look': {**all5, 'fx_order': order}})
        check('all five saved through the API with a custom order', r.status_code == 200 and all(k in r.json()['look_json'] for k in all5))
        t0 = time.time(); job = c.post('/api/scenes/' + sid + '/render').json()
        for _ in range(900):
            j = c.get('/api/jobs/' + job['job_id']).json()
            if j['status'] in ('succeeded', 'failed', 'cancelled'): break
            time.sleep(.1)
        check(f"{'picture' if asset is picture else 'video'} part with all five renders ({time.time() - t0:.1f} s)", j['status'] == 'succeeded')
    for s in scenes[2:]:
        c.delete('/api/scenes/' + s['id'])
    job = c.post(f'/api/projects/{pid}/export?skip_empty=true', json={'settings': {}}).json()
    for _ in range(1500):
        j = c.get('/api/jobs/' + job['job_id']).json()
        if j['status'] in ('succeeded', 'failed', 'cancelled'): break
        time.sleep(.1)
    out = pathlib.Path(work.name) / 'export.mp4'; out.write_bytes(c.get('/api/assets/' + j['artifact_asset_id'] + '/stream').content)
    dur = probe(str(out)).duration_ms / 1000
    check(f'the project exports with the exact length ({dur:.2f}s for 4 s)', j['status'] == 'succeeded' and abs(dur - 4) < 0.15)
    pr = c.post('/api/look-presets', json={'preset': {'name': 'Trend pack 2', 'look': all5}})
    check('the new effects can be saved in a look preset and are kept', pr.status_code in (200, 201) and all(k in pr.json()['added'][0]['look'] for k in all5))

# ---- 1080p cost (FFmpeg only), 5 s of moving picture ----------------------------------------
base = None
for name, look in [('none', {})] + [(k, {k: v}) for k, v in {**all5, 'speedblur': {'amount': 60, 'direction': 'horizontal', 'when': 'whole'},
                                                              'colorsplit': {'amount': 60, 'mode': 'beats', 'bpm': 120}}.items()]:
    graph, label = stack_graph('0:v', look, 1920, 1080, 30, 5.0, CACHE)
    t0 = time.monotonic()
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=1920x1080:r=30:d=5', '-filter_complex', ';'.join([*graph, f'[{label}]null[v]']),
                    '-map', '[v]', '-f', 'null', '-'], check=True)
    dt = time.monotonic() - t0
    base = base or dt
    check(f'{name}: 5 s at 1080p30 in {dt:.1f}s (no effects {base:.1f}s; limit 20 s)', dt < 20)

print(f'{n} trending effect (part 2) checks passed')
