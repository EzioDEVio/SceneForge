"""Auto-reframe 16:9 -> 9:16 and GPU (NVENC) export with CPU fallback.

Reframe: a synthetic 16:9 clip with one bright subject moving left -> right and a still image with
the subject off-centre. POST /api/projects/{id}/reframe copies the project to 9:16 and stores a
smoothed subject path per shot (crop_json.reframe); the rendered 9:16 parts keep the subject in the
frame at start / middle / end (brightness centroid), while a plain centre crop loses it. The path
respects the pan-speed bound; the still image is centred on its subject. Shots without a reframe
produce the exact legacy crop filter string (default projects render byte-identically).
Project copy: every row copied, ids remapped (shots -> copied assets, overlays / music ids), media
files shared, rendered parts not copied, source untouched.
GPU: `ffmpeg -encoders` parsing and detection with a mocked ffmpeg; NVENC command construction
(preset/cq from quality, yuv420p, hvc1, faststart, no x264/x265 options); automatic CPU retry
when the GPU encoder fails (a fake encoder name, and real h264_nvenc on a machine without an NVIDIA
GPU) with a warning surfaced on the export job; a real CPU export still works.
NVENC itself is NOT exercised on real hardware here.

Needs the u2netp cutout model (4.6 MB): uses SCENEFORGE_CUTOUT_MODEL_DIR, downloading once if
missing; skips the reframe half with a message only when github.com is unreachable.
"""
import json, os, pathlib, subprocess, sys, tempfile, time

ROOT = pathlib.Path(__file__).resolve().parents[2]
tmp = tempfile.TemporaryDirectory()
T = pathlib.Path(tmp.name)
os.environ['SCENEFORGE_DATA_DIR'] = str(T / 'data')
os.environ['SCENEFORGE_SD_AUTOSTART'] = '0'
os.environ.setdefault('SCENEFORGE_CUTOUT_MODEL_DIR', str(T / 'models'))
sys.path.insert(0, str(ROOT / 'backend'))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from app.security import secrets  # noqa: E402
from app.main import app  # noqa: E402
from app.render import cutout, delivery, gpu, reframe as rf  # noqa: E402
from app.db.database import session_scope  # noqa: E402
from app.db.models import Asset, Project, Scene, Shot  # noqa: E402


class MemoryVault:
    def __init__(self): self.d = {}
    def set_password(self, s, k, v): self.d[(s, k)] = v
    def get_password(self, s, k): return self.d.get((s, k))
    def delete_password(self, s, k): self.d.pop((s, k), None)


_vault = MemoryVault()
secrets.vault = lambda: _vault

n = 0
def check(name, ok):
    global n
    assert ok, name
    n += 1
    print('PASS ' + name, flush=True)


def ff(*a):
    subprocess.run(['ffmpeg', '-v', 'error', '-y', *a], check=True, capture_output=True)


def frame_at(path, t, w=None):
    """RGB numpy frame of a video at t seconds."""
    out = T / f'frame_{time.time_ns()}.png'
    ff('-ss', f'{t:.3f}', '-i', str(path), '-frames:v', '1', str(out))
    return np.asarray(Image.open(out).convert('RGB')).astype(np.float32)


def bright_centroid(frame, thr=180):
    """(x fraction, fraction of pixels) of the bright subject."""
    lum = frame.mean(axis=2)
    m = lum > thr
    if m.sum() == 0:
        return None, 0.0
    xs = np.nonzero(m)[1]
    return float(xs.mean() / frame.shape[1]), float(m.mean())


def vinfo(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                        'stream=codec_name,width,height,pix_fmt,codec_tag_string', '-of', 'json', str(path)],
                       capture_output=True, text=True, check=True)
    return json.loads(r.stdout)['streams'][0]


# =============================================================================================
# 1. Filter strings: no reframe -> exactly the legacy crop filter
# =============================================================================================
LEGACY = lambda c: f"crop=w='max(2,trunc(iw*{c['width']}/2)*2)':h='max(2,trunc(ih*{c['height']}/2)*2)':x='iw*{c['x']}':y='ih*{c['y']}',"  # noqa: E731
rect = {'x': 0.1, 'y': 0.05, 'width': 0.8, 'height': 0.9}
check('no crop -> no pre-filter (default shots unchanged)', rf.shot_crop_prefilter(None, 1920, 1080, 30) == '' and rf.shot_crop_prefilter({}, 1920, 1080, 30) == '')
check('manual crop without reframe -> byte-identical legacy crop filter',
      rf.shot_crop_prefilter(rect, 1920, 1080, 30) == LEGACY(rect) and rf.shot_crop_prefilter({'x': 0, 'y': 0, 'width': 1, 'height': 1}, 1080, 1920, 30) == LEGACY({'x': 0, 'y': 0, 'width': 1, 'height': 1}))
check('reframe "center" on a full-frame rect adds nothing (cover already centres)',
      rf.shot_crop_prefilter({'x': 0, 'y': 0, 'width': 1, 'height': 1, 'reframe': {'mode': 'center'}}, 1080, 1920, 30) == '')
f = rf.shot_crop_prefilter({**rect, 'reframe': {'mode': 'follow', 'track': [[0, 0.2], [2000, 0.6], [4000, 0.8]]}}, 1080, 1920, 30)
check('follow: legacy crop first, then a 9:16 window whose x interpolates the track per frame',
      f.startswith(LEGACY(rect)) and 'ih*0.562500' in f and 'clip(n/30,0,4)' in f and "y='(ih-oh)/2'" in f and f.endswith(','))
m = rf.shot_crop_prefilter({'x': 0, 'y': 0, 'width': 1, 'height': 1, 'reframe': {'mode': 'manual', 'x': 0.25}}, 1080, 1920, 30)
check('manual x: constant window centre', m.startswith('crop=') and "x='clip((0.25)*iw-ow/2,0,iw-ow)'" in m)


def eval_track_expr(track, fps, n_frame):
    """Evaluate the FFmpeg expression in Python (same operators) to verify interpolation."""
    e = rf.track_x_expr(track, fps)
    env = {'n': n_frame, 'clip': lambda v, a, b: min(max(v, a), b), 'gte': lambda a, b: float(a >= b), 'lt': lambda a, b: float(a < b)}
    return eval(e, {}, env)  # noqa: S307 - test-only, expression built by our code


tr = [[0, 0.2], [2000, 0.6], [4000, 0.8]]
vals = [eval_track_expr(tr, 30, k) for k in (0, 30, 60, 90, 120, 200)]
check('track expression interpolates linearly and holds the ends',
      [round(v, 4) for v in vals] == [0.2, 0.4, 0.6, 0.7, 0.8, 0.8])
check('single-point track is a constant', rf.track_x_expr([[0, 0.7]], 30) == '0.7')

# --- validation and smoothing units --------------------------------------------------------
for bad in ({'mode': 'zoom'}, {'mode': 'manual', 'x': 2}, {'mode': 'follow', 'track': [[100, 0.5], [50, 0.4]]}, {'mode': 'follow', 'track': [[0, 'a']]}):
    try:
        rf.clean_reframe(bad); ok = False
    except rf.ReframeError:
        ok = True
    check(f'invalid reframe rejected: {bad}', ok)
times = [i / 4 for i in range(40)]
noisy = [0.5 + 0.25 * np.sin(i / 6) + (0.08 if i % 2 else -0.08) for i in range(40)]
sm = rf.smooth_path(times, noisy, 0.316)
steps = [abs(b - a) / 0.25 for a, b in zip(sm, sm[1:])]
flips = lambda v: sum(1 for a, b, c in zip(v, v[1:], v[2:]) if (b - a) * (c - b) < 0)  # noqa: E731
stored = [x for _, x in rf.build_track(times, noisy, 0.316)]
check('smoothing removes frame-to-frame jitter: only the 2 real turns of the path remain (raw: 38)',
      flips(noisy) == 38 and flips(sm) <= 2 and flips(stored) <= 2)
check('smoothed path respects the max pan speed', max(steps) <= rf.MAX_PAN_SPEED + 1e-6)
check('window is kept inside the frame', min(sm) >= 0.158 - 1e-6 and max(sm) <= 1 - 0.158 + 1e-6)
check('gaps (no detection) are filled from neighbours, all-missing stays centred',
      rf.smooth_path([0, 1, 2], [0.3, None, 0.3], 0.3) == [0.3, 0.3, 0.3] and rf.smooth_path([0, 1], [None, None], 0.3) == [0.5, 0.5])

# =============================================================================================
# 2. GPU encoder detection, command construction, CPU fallback
# =============================================================================================
ENCODERS_TXT = """Encoders:
 V..... = Video
 A..... = Audio
 ------
 V....D libx264              libx264 H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10 (codec h264)
 V....D h264_nvenc           NVIDIA NVENC H.264 encoder (codec h264)
 V....D hevc_nvenc           NVIDIA NVENC hevc encoder (codec hevc)
 V..... h264_qsv             H.264 / AVC (Intel Quick Sync Video acceleration) (codec h264)
 A....D aac                  AAC (Advanced Audio Coding)
"""
names = gpu.parse_encoders(ENCODERS_TXT)
check('ffmpeg -encoders parsing finds video encoders only', {'libx264', 'h264_nvenc', 'hevc_nvenc', 'h264_qsv'} <= names and 'aac' not in names and '=' not in names)


class FakeRun:
    def __init__(self, listing, working):
        self.listing, self.working, self.calls = listing, working, []

    def __call__(self, args, **kw):
        self.calls.append(args)
        R = type('R', (), {})
        r = R()
        if '-encoders' in args:
            r.returncode, r.stdout, r.stderr = 0, self.listing, ''
        else:
            enc = args[args.index('-c:v') + 1]
            ok = enc in self.working
            r.returncode, r.stdout, r.stderr = (0, '', '') if ok else (1, '', f'[{enc} @ 0x1] Cannot load libcuda.so.1')
        return r


fake = FakeRun(ENCODERS_TXT, {'h264_nvenc'})
info = gpu.detect('ffmpeg', refresh=True, run=fake)
check('detection test-encodes every listed candidate (1 frame) and only trusts the ones that work',
      info['encoders']['h264_nvenc']['works'] and not info['encoders']['hevc_nvenc']['works']
      and 'libcuda' in info['encoders']['hevc_nvenc']['error'] and not info['encoders']['h264_amf']['listed']
      and sum(1 for c in fake.calls if '-frames:v' in c) == 3)
check('GPU is available for H.264 only in that case', info['gpu']['available'] and info['gpu']['h264'] == 'h264_nvenc' and info['gpu']['hevc'] is None)
check('detection result is cached', gpu.detect() is info)
check('auto/gpu pick NVENC for MP4 when the test encode worked; cpu never does',
      gpu.resolve('auto', 'mp4_h264', info) == ('h264_nvenc', None) and gpu.resolve('gpu', 'mp4_h264', info)[0] == 'h264_nvenc'
      and gpu.resolve('cpu', 'mp4_h264', info) == (None, None))
w = gpu.resolve('gpu', 'mp4_h265', info)
check('gpu requested but no working encoder -> CPU with a warning; auto stays silent',
      w[0] is None and 'CPU' in w[1] and gpu.resolve('auto', 'mp4_h265', info) == (None, None))
check('non-MP4 formats stay on the CPU (warning only when GPU was asked for)',
      gpu.resolve('auto', 'webm', info) == (None, None) and gpu.resolve('gpu', 'gif', info)[0] is None)
none = gpu.detect('ffmpeg', refresh=True, run=FakeRun(ENCODERS_TXT, set()))
check('listed-but-unusable NVENC (no NVIDIA GPU/driver) is reported as not available', not none['gpu']['available'] and none['encoders']['h264_nvenc']['listed'])

# command construction through the real delivery.deliver, with the encode step recorded
recorded = []
real_encode = delivery._encode
def rec_encode(args, out, cancel_check=None):
    recorded.append(list(args)); pathlib.Path(out).write_bytes(b'x'); return out
delivery._encode = rec_encode
avail = {'encoders': {'h264_nvenc': {'works': True}, 'hevc_nvenc': {'works': True}}, 'gpu': {'available': True}}
gpu.set_cache(avail)
master = T / 'master.mp4'
ff('-f', 'lavfi', '-i', 'testsrc2=s=320x180:r=25:d=1', '-f', 'lavfi', '-i', 'sine=f=440:d=1', '-shortest', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(master))
outdir = T / 'out'; outdir.mkdir()
for fmt, quality, enc, preset, cq in (('mp4_h264', 'standard', 'h264_nvenc', 'p5', '23'), ('mp4_h264', 'high', 'h264_nvenc', 'p6', '20'), ('mp4_h265', 'standard', 'hevc_nvenc', 'p5', '26')):
    recorded.clear()
    delivery.deliver(str(master), {'format': fmt, 'quality': quality, 'encoder': 'auto'}, 320, 180, 25, str(outdir), 'ffmpeg')
    a = recorded[0]
    check(f'{fmt}/{quality} on GPU: {enc} preset {preset} cq {cq}, yuv420p + faststart kept, no CPU codec options',
          a[a.index('-c:v') + 1] == enc and a[a.index('-preset') + 1] == preset and a[a.index('-cq') + 1] == cq
          and a[a.index('-pix_fmt') + 1] == 'yuv420p' and '+faststart' in a and '-crf' not in a and 'libx264' not in a
          and 'libx265' not in a and '-x265-params' not in a and a[a.index('-c:a') + 1] == 'aac'
          and (('-tag:v' in a and a[a.index('-tag:v') + 1] == 'hvc1') if fmt == 'mp4_h265' else a[a.index('-profile:v') + 1] == 'high'))
recorded.clear()
delivery.deliver(str(master), {'format': 'mp4_h264', 'quality': 'standard', 'encoder': 'cpu'}, 320, 180, 25, str(outdir), 'ffmpeg')
check('encoder "cpu" keeps the unchanged libx264 command', recorded[0][recorded[0].index('-c:v') + 1] == 'libx264' and '-crf' in recorded[0])
delivery._encode = real_encode

check('export settings accept encoder auto|cpu|gpu (default auto) and reject others',
      delivery.clean({})['encoder'] == 'auto' and delivery.clean({'encoder': 'gpu'})['encoder'] == 'gpu')
try:
    delivery.clean({'encoder': 'cuda'}); ok = False
except delivery.DeliveryError:
    ok = True
check('unknown encoder value is rejected', ok)

# Automatic CPU retry with a GPU encoder that fails at runtime (a fake encoder name).
saved_formats = dict(gpu.GPU_FORMATS)
gpu.GPU_FORMATS['mp4_h264'] = 'h264_fake_gpu'
gpu.set_cache({'encoders': {'h264_fake_gpu': {'works': True}}, 'gpu': {'available': True}})
warns = []
out = delivery.deliver(str(master), {'format': 'mp4_h264', 'quality': 'draft', 'encoder': 'gpu'}, 320, 180, 25, str(outdir), 'ffmpeg', warnings=warns)
i = vinfo(out)
check('failing GPU encoder -> export retried on CPU, valid H.264 yuv420p file', i['codec_name'] == 'h264' and i['pix_fmt'] == 'yuv420p')
check('... and a warning names the failed GPU encoder', len(warns) == 1 and 'h264_fake_gpu' in warns[0] and 'CPU' in warns[0])
gpu.GPU_FORMATS.clear(); gpu.GPU_FORMATS.update(saved_formats)
# Real NVENC on this machine (FFmpeg lists it, but there is no NVIDIA GPU here): also falls back.
gpu.set_cache({'encoders': {'hevc_nvenc': {'works': True}}, 'gpu': {'available': True}})
warns = []
out = delivery.deliver(str(master), {'format': 'mp4_h265', 'quality': 'draft', 'encoder': 'auto'}, 320, 180, 25, str(outdir), 'ffmpeg', warnings=warns)
i = vinfo(out)
real_gpu = not warns
check('H.265 export with NVENC either works (real GPU) or falls back to libx265 with hvc1 kept',
      i['codec_name'] == 'hevc' and i['codec_tag_string'] == 'hvc1' and (real_gpu or 'hevc_nvenc' in warns[0]))
gpu.set_cache(None)
warns = []
out = delivery.deliver(str(master), {'format': 'mp4_h264', 'quality': 'draft', 'encoder': 'cpu'}, 320, 180, 25, str(outdir), 'ffmpeg', warnings=warns)
check('real CPU export still works without warnings', vinfo(out)['codec_name'] == 'h264' and not warns)

# =============================================================================================
# 3. Project copy + auto-reframe (API)
# =============================================================================================
try:
    cutout.ensure_model('u2netp')
except cutout.CutoutError as e:
    import requests
    try:
        requests.head('https://github.com', timeout=10); reachable = True
    except Exception:
        reachable = False
    if not reachable:
        print(f'SKIP reframe half: github.com is unreachable, so the u2netp model cannot be downloaded ({e})')
        print(f'{n} reframe/GPU checks passed (reframe skipped).')
        sys.exit(0)
    raise

client = TestClient(app).__enter__()
W, H, FPS, DUR = 640, 360, 25, 4.0
frames_dir = T / 'synth'; frames_dir.mkdir()
for k in range(int(DUR * FPS)):
    im = Image.new('RGB', (W, H), (28, 34, 40)); d = ImageDraw.Draw(im)
    cx = int(70 + (W - 140) * k / (DUR * FPS - 1))     # subject moves from 11 % to 89 % of the width
    d.ellipse([cx - 40, 120, cx + 40, 300], fill=(245, 235, 225)); d.ellipse([cx - 22, 70, cx + 22, 124], fill=(250, 240, 230))
    im.save(frames_dir / f'f{k:04d}.png')
ff('-framerate', str(FPS), '-i', str(frames_dir / 'f%04d.png'), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(T / 'moving.mp4'))
im = Image.new('RGB', (1280, 720), (28, 34, 40)); d = ImageDraw.Draw(im)
d.ellipse([900, 260, 1060, 620], fill=(245, 235, 225)); d.ellipse([935, 160, 1025, 266], fill=(250, 240, 230))
im.save(T / 'still.png')                        # subject centre at x = 980 / 1280 = 0.766

pid = client.post('/api/projects', json={'title': 'Wide doc', 'aspect': '16:9'}).json()['id']
up = lambda f: client.post('/api/assets/upload', params={'project_id': pid}, files={'file': (f, open(T / f, 'rb'))}).json()  # noqa: E731
vid, still = up('moving.mp4'), up('still.png')
scenes = client.get(f'/api/projects/{pid}').json()['scenes']
s1, s2 = scenes[0]['id'], scenes[1]['id']
client.post(f'/api/scenes/{s1}/shots', json={'asset_id': vid['id']})
client.post(f'/api/scenes/{s2}/shots', json={'asset_id': still['id'], 'crop': {'x': 0, 'y': 0, 'width': 1, 'height': 1}})
# JSON references to assets that a copy must remap: an overlay (via the API) and project music
assert client.patch(f'/api/scenes/{s1}', json={'overlays': [{'asset_id': still['id']}]}).status_code == 200
with session_scope() as db:
    db.get(Project, pid).finishing_json = {'music': {'asset_id': vid['id'], 'volume': 30}, 'loudnorm': True}

r = client.post(f'/api/projects/{pid}/duplicate', json={'title': 'Wide doc copy'})
check('POST /duplicate copies the project', r.status_code == 200 and r.json()['title'] == 'Wide doc copy' and r.json()['id'] != pid)
cid = r.json()['id']
with session_scope() as db:
    src, cp = db.get(Project, pid), db.get(Project, cid)
    src_assets = {a.id: a for a in db.query(Asset).filter(Asset.project_id == pid)}
    cp_assets = {a.id: a for a in db.query(Asset).filter(Asset.project_id == cid)}
    cp_shots = [sh for s in cp.scenes for sh in s.shots]
    check('copy has the same scenes, shots and asset rows with new ids',
          len(cp.scenes) == len(src.scenes) and len(cp_shots) == 2 and len(cp_assets) == len(src_assets)
          and not set(cp_assets) & set(src_assets) and not {s.id for s in cp.scenes} & {s.id for s in src.scenes})
    check('copied shots use the copy\'s own asset rows (assets are project-scoped)', all(sh.asset_id in cp_assets for sh in cp_shots))
    check('asset rows share the media files (same storage key and hash)',
          sorted((a.storage_key, a.content_hash) for a in cp_assets.values()) == sorted((a.storage_key, a.content_hash) for a in src_assets.values()))
    check('ids inside JSON (overlays, music) are remapped to the copy',
          cp.scenes[0].overlays_json[0]['asset_id'] in cp_assets and cp.finishing_json['music']['asset_id'] in cp_assets
          and cp.finishing_json['loudnorm'] is True and len(cp.scenes[0].overlays_json) == 1
          and {k: v for k, v in cp.scenes[0].overlays_json[0].items() if k != 'asset_id'} == {k: v for k, v in src.scenes[0].overlays_json[0].items() if k != 'asset_id'})
    check('rendered parts are not carried over; source project untouched',
          all(s.rendered_asset_id is None for s in cp.scenes) and src.scenes[0].overlays_json[0]['asset_id'] == still['id']
          and all(sh.asset_id in src_assets for s in src.scenes for sh in s.shots))
check('deleting the copy keeps the source project and its media working',
      client.delete(f'/api/projects/{cid}').status_code == 200 and client.get(f'/api/assets/{vid["id"]}/stream').status_code == 200)

# The brightness measurements below need a clean frame: drop the overlay and music again.
client.patch(f'/api/scenes/{s1}', json={'overlays': []})
with session_scope() as db:
    db.get(Project, pid).finishing_json = {}
t0 = time.time()
r = client.post(f'/api/projects/{pid}/reframe', json={'aspect': '9:16'})
check('POST /reframe starts a job and returns the new project id', r.status_code == 200 and r.json()['total'] == 2)
job, vp = r.json()['job_id'], r.json()['project_id']
while (st := client.get(f'/api/reframe/jobs/{job}').json())['status'] == 'running':
    time.sleep(0.5)
print(f'  reframe analysis took {time.time() - t0:.1f}s', flush=True)
check('reframe job succeeds with progress 100', st['status'] == 'succeeded' and st['progress'] == 100 and st['done'] == 2)
p = client.get(f'/api/projects/{vp}').json()
check('new project is 9:16 1080x1920, original stays 16:9',
      p['aspect'] == '9:16' and (p['width'], p['height']) == (1080, 1920) and client.get(f'/api/projects/{pid}').json()['aspect'] == '16:9')
vshot, sshot = p['scenes'][0]['shots'][0], p['scenes'][1]['shots'][0]
vr, sr = vshot['crop_json']['reframe'], sshot['crop_json']['reframe']
track = vr['track']
check('video shot gets a follow-subject track found with the cutout matte', vr['mode'] == 'follow' and vr['method'] == 'matte' and vshot['fit'] == 'cover' and len(track) >= 2)
check('track moves left -> right with the subject', track[0][1] < 0.3 and track[-1][1] > 0.7 and all(b[1] >= a[1] - 0.01 for a, b in zip(track, track[1:])))
check('track is smooth: no keyframe step faster than the pan-speed bound',
      all(abs(b[1] - a[1]) / max((b[0] - a[0]) / 1000, 1e-3) <= rf.MAX_PAN_SPEED + 0.01 for a, b in zip(track, track[1:])))
check('track is compact (simplified keyframes)', len(track) <= 17)
check('still image: one keyframe centred on the subject', len(sr['track']) == 1 and abs(sr['track'][0][1] - 0.766) < 0.05)

# Render the reframed parts and measure where the subject ends up.
def render(scene_id):
    j = client.post(f'/api/scenes/{scene_id}/render').json()
    while (s := client.get(f"/api/jobs/{j['job_id']}").json())['status'] not in ('succeeded', 'failed'):
        time.sleep(0.5)
    assert s['status'] == 'succeeded', s.get('error')
    with session_scope() as db:
        a = db.get(Asset, db.get(Scene, scene_id).rendered_asset_id)
        from app.config import RENDERS_DIR
        return pathlib.Path(RENDERS_DIR) / a.storage_key

t0 = time.time()
vpath = render(p['scenes'][0]['id'])
print(f'  9:16 part render took {time.time() - t0:.1f}s', flush=True)
info = vinfo(vpath)
check('reframed part renders at 1080x1920', (info['width'], info['height']) == (1080, 1920))
positions = []
for t in (0.15, DUR / 2, DUR - 0.2):
    x, cover = bright_centroid(frame_at(vpath, t))
    positions.append(x)
    check(f'subject inside the 9:16 frame at t={t:.2f}s (centroid {x if x is None else round(x, 2)}, {cover:.1%} of pixels)',
          x is not None and 0.12 < x < 0.88 and cover > 0.03)

# Control: a plain centre crop of the same clip loses the subject at the start and the end.
client.put(f"/api/shots/{vshot['id']}/reframe", json={'mode': 'center'})
cpath = render(p['scenes'][0]['id'])
lost = [bright_centroid(frame_at(cpath, t))[1] for t in (0.15, DUR - 0.2)]
check('control: centre crop (no follow) loses the subject at start and end', max(lost) < 0.01)

spath = render(p['scenes'][1]['id'])
x, cover = bright_centroid(frame_at(spath, 1.0))
check(f'static image reframe centres the subject (centroid {x and round(x, 2)})', x is not None and abs(x - 0.5) < 0.1 and cover > 0.05)

# Per-shot override API
r = client.put(f"/api/shots/{sshot['id']}/reframe", json={'mode': 'manual', 'x': 0.2})
check('manual override stores x and keeps the analysed track', r.status_code == 200 and r.json()['crop_json']['reframe']['mode'] == 'manual'
      and r.json()['crop_json']['reframe']['x'] == 0.2 and len(r.json()['crop_json']['reframe']['track']) == 1)
r = client.patch(f"/api/scenes/shots/{sshot['id']}", json={'crop': {'x': 0.1, 'y': 0, 'width': 0.9, 'height': 1}})
check('editing the manual crop rectangle keeps the reframe setting', r.status_code == 200 and r.json()['crop_json']['reframe']['mode'] == 'manual' and r.json()['crop_json']['width'] == 0.9)
check('invalid reframe values are rejected', client.put(f"/api/shots/{sshot['id']}/reframe", json={'mode': 'manual', 'x': 3}).status_code == 400
      and client.put(f"/api/shots/{sshot['id']}/reframe", json={'mode': 'spin'}).status_code == 400)
r = client.put(f"/api/shots/{vshot['id']}/reframe", json={'mode': 'follow'})
check('switching back to follow reuses the stored path', r.status_code == 200 and r.json()['crop_json']['reframe']['track'] == track)
r = client.put(f"/api/shots/{sshot['id']}/reframe", json={'mode': 'off'})
check('mode off removes the reframe but keeps the manual crop', r.json()['crop_json'] == {'x': 0.1, 'y': 0, 'width': 0.9, 'height': 1})

# End-to-end export of the vertical project with encoder "gpu": works, warns, never fails.
gpu.set_cache(None)
ex = client.post(f'/api/projects/{vp}/export', params={'skip_empty': True},
                 json={'settings': {'format': 'mp4_h264', 'quality': 'draft', 'encoder': 'gpu'}}).json()
while (s := client.get(f"/api/jobs/{ex['job_id']}").json())['status'] not in ('succeeded', 'failed'):
    time.sleep(0.5)
enc_info = client.get('/api/system/encoders').json()
check('GET /api/system/encoders reports detection with choices', enc_info['choices'] == ['auto', 'cpu', 'gpu'] and 'h264_nvenc' in enc_info['encoders'])
check('export with encoder "gpu" succeeds; without a working GPU the job carries a CPU warning',
      s['status'] == 'succeeded' and (enc_info['gpu']['available'] or any('CPU' in w for w in s['warnings'])))
with session_scope() as db:
    from app.config import RENDERS_DIR
    a = db.get(Asset, s['artifact_asset_id'])
    i = vinfo(pathlib.Path(RENDERS_DIR) / a.storage_key)
check('exported vertical video is 1080x1920 H.264 yuv420p', (i['width'], i['height'], i['codec_name'], i['pix_fmt']) == (1080, 1920, 'h264', 'yuv420p'))

print(f'{n} reframe/GPU checks passed (NVENC hardware not exercised unless a real NVIDIA GPU is present).')
