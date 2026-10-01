"""rc6 effects pack, verified on real FFmpeg renders of tiny synthetic media:
camera shake presets, lens flare, wiggle (turbulent displace), focus blur /
tilt-shift, mosaic, RGB split amount, halation, film-style grades, text reveal
masks, overlay loop motion, speed ramp curves (+ smooth slow motion),
beat-aware music fit and dialogue cleanup. Plus validation rejections."""
import os, pathlib, subprocess, sys, tempfile, time
from types import SimpleNamespace
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
root = pathlib.Path(__file__).resolve().parents[2]
tmp = tempfile.TemporaryDirectory(); os.environ['SCENEFORGE_DATA_DIR'] = tmp.name
t = pathlib.Path(tmp.name)
sys.path.insert(0, str(root / 'backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.domain.constants import EffectPreset, FitMode
from app.render import scene_fx as fx
from app.render.filters import build_effect_chain, build_shot_video_chain
from app.render.overlays import build_overlay_pass
from app.render.speed import clean_speed, plan as speed_plan
from app.render.subtitles import write_ass_file
from app.render.audio_edit import AudioEditError, clean_edit, narration_filter
from app.render.music_fit import plan_segments

n = 0
def check(name, ok):
    global n
    assert ok, name
    n += 1; print('PASS ' + name, flush=True)
def ff(*a): subprocess.run(['ffmpeg', '-v', 'error', '-y', *a], check=True, capture_output=True)
W, H, FPS = 320, 180, 15
CACHE = t / 'cache'

def frames(inputs, graph, label='vout', w=W, h=H, dur=1.4):
    raw = subprocess.run(['ffmpeg', '-v', 'error', *inputs, '-filter_complex', graph, '-map', f'[{label}]', '-t', str(dur),
                          '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True)
    assert raw.returncode == 0, raw.stderr.decode()[-600:]
    return np.frombuffer(raw.stdout, np.uint8).reshape(-1, h, w, 3).astype(float)

# textured still (random blobs, blurred) — motion and blur are measurable on it
rng = np.random.default_rng(3)
tex = Image.fromarray(rng.integers(0, 255, (H // 4, W // 4, 3), dtype=np.uint8)).resize((W, H), Image.NEAREST)
d = ImageDraw.Draw(tex)
for k in range(12):
    x, y = rng.integers(0, W), rng.integers(0, H)
    d.rectangle([x, y, x + 20, y + 14], fill=tuple(int(v) for v in rng.integers(0, 255, 3)))
tex.save(t / 'tex.png')
still = ['-loop', '1', '-framerate', str(FPS), '-t', '1.4', '-i', str(t / 'tex.png')]

# --- 1. camera shake presets --------------------------------------------------
motion = {}
for preset in ('custom', 'handheld', 'walk', 'run', 'impact'):
    sk = fx.clean_shake({'preset': preset, 'amount': 70, 'speed': 60})
    g, lab = fx.shake_graph('0:v', sk, W, H, FPS)
    fr = frames(still, ';'.join(g) + f';[{lab}]format=rgb24[vout]')
    diffs = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2, 3))
    motion[preset] = diffs
    check(f'shake preset {preset} renders and moves the picture', fr.shape[0] >= 20 and diffs.mean() > 1.0)
check('handheld (subtle) moves less than running', motion['handheld'].mean() < motion['run'].mean())
check('impact shake is violent at the start and settles', motion['impact'][:5].mean() > 1.5 * motion['impact'][-5:].mean())
check('shake preset stored; custom preset omitted for old projects', fx.clean_shake({'preset': 'walk'})['preset'] == 'walk' and 'preset' not in fx.clean_shake({}))

# --- 2. lens flare --------------------------------------------------------------
gray = ['-f', 'lavfi', '-i', f'color=c=0x303030:s={W}x{H}:r={FPS}:d=1.4']
def flare_frames(**kw):
    f = fx.clean_flare(kw); png, drift = fx.flare_png(f, W, H, CACHE)
    g, lab = fx.flare_graph('0:v', f, png, drift, W, H, FPS, 1.4)
    return frames(gray, ';'.join(g) + f';[{lab}]format=rgb24[vout]')
scr = flare_frames(x=75, y=25, color='#FFA040', blend='screen', amount=80)
add = flare_frames(x=75, y=25, color='#FFA040', blend='add', amount=80)
spot = scr[3, 40:50, 235:245].mean()
check(f'lens flare brightens its source position ({spot:.0f} vs 48 background)', spot > 150)
check('flare tint colours the halo (warm: red > blue)', scr[3, 15:35, 190:220, 0].mean() > scr[3, 15:35, 190:220, 2].mean() + 5)
check('Add blend is brighter than Screen', add[3].mean() > scr[3].mean() + 1)
dr = flare_frames(x=50, y=50, color='#FFFFFF', blend='screen', amount=100, drift=80)
x0 = np.argmax(dr[0, 88:92].mean(axis=(0, 2))); x1 = np.argmax(dr[-1, 88:92].mean(axis=(0, 2)))
check(f'horizontal drift moves the flare across the scene ({x0} → {x1} px)', x0 - x1 > 30)

# --- 3. wiggle (turbulent displace) ---------------------------------------------
src = frames(still, '[0:v]format=rgb24[vout]')
wg = fx.clean_wiggle({'amount': 80, 'speed': 60, 'size': 50})
g, lab = fx.wiggle_graph('0:v', wg, W, H, FPS, 1.4)
wf = frames(still, ';'.join(g) + f';[{lab}]format=rgb24[vout]')
check('wiggle warps the picture', np.abs(wf[5] - src[5]).mean() > 8)
check('wiggle is animated (warp changes over time)', np.abs(wf[2] - wf[15]).mean() > 5)
g0, lab0 = fx.wiggle_graph('0:v', fx.clean_wiggle({'amount': 0}), W, H, FPS, 1.4)
w0 = frames(still, ';'.join(g0) + f';[{lab0}]format=rgb24[vout]')
yuv = frames(still, '[0:v]format=yuv420p,format=rgb24[vout]')   # same colour round trip as the scene FX pass
check('wiggle amount 0 leaves the picture in place', np.abs(w0[5] - yuv[5]).mean() < 3)

# --- 4. focus blur / tilt-shift, mosaic, RGB split --------------------------------
def effect(preset, look=None, inten=100, inputs=still):
    chain = build_effect_chain(preset, inten, None, W, look or {}, H)
    return frames(inputs, f'[0:v]{chain},format=rgb24[vout]')[3]
def detail(img): return np.abs(np.diff(img, axis=1)).mean() + np.abs(np.diff(img, axis=0)).mean()
orig = src[3]
fb = effect(EffectPreset.FOCUS_BLUR, {'focus': {'size': 40, 'blur': 80, 'x': 50, 'y': 50}})
c, e = (slice(70, 110), slice(140, 180)), (slice(0, 40), slice(0, 60))
check('focus blur keeps the centre sharp', detail(fb[c]) > 0.85 * detail(orig[c]))
check('focus blur softens the edges', detail(fb[e]) < 0.6 * detail(orig[e]))
ts = effect(EffectPreset.TILT_SHIFT, {'focus': {'size': 30, 'blur': 80, 'x': 50, 'y': 50}})
check('tilt-shift: sharp middle band, blurred top', detail(ts[80:100]) > 0.8 * detail(orig[80:100]) and detail(ts[0:30]) < 0.6 * detail(orig[0:30]))
tsrc = ['-f', 'lavfi', '-i', f'testsrc2=s={W}x{H}:r={FPS}:d=1.4']
mo = effect(EffectPreset.MOSAIC, {'mosaic': {'block': 60}}, inputs=tsrc)   # 60 px at 1080p = 10 px here
plain = frames(tsrc, '[0:v]format=rgb24[vout]')[3]
uniq = lambda img: len(np.unique(img.reshape(-1, 3).astype(np.uint8), axis=0))
check(f'mosaic reduces unique colours ({uniq(plain)} → {uniq(mo)})', uniq(mo) < uniq(plain) / 4)
check('mosaic blocks are flat (10 px at 180p for 60 px at 1080p)', np.abs(np.diff(mo[20:30, 30:40], axis=1)).mean() < 2)
bars = ['-f', 'lavfi', '-i', f'color=c=white:s={W}x{H}:r={FPS}:d=1.4', '-f', 'lavfi', '-i', f'color=c=black:s=40x{H}:r={FPS}:d=1.4']
barin = [*bars]
def rgbsplit(amount):
    chain = build_effect_chain(EffectPreset.CHROMATIC_SPLIT, 100, None, W, {'rgbsplit': {'amount': amount}}, H)
    f = frames(barin, f'[0:v][1:v]overlay=x=140:y=0,{chain},format=rgb24[vout]')[3]
    return int((np.abs(f[..., 0] - f[..., 2]) > 60).sum())
check('RGB split amount widens the colour fringes', rgbsplit(90) > 2 * rgbsplit(15) > 0)

# --- 5. halation and film-style grades ---------------------------------------------
hi_in = ['-f', 'lavfi', '-i', f'color=c=0x202020:s={W}x{H}:r={FPS}:d=1.4', '-f', 'lavfi', '-i', f'color=c=white:s=60x40:r={FPS}:d=1.4']
def hal(preset, inten=100):
    chain = build_effect_chain(preset, inten, None, W, {}, H)
    return frames(hi_in, f'[0:v][1:v]overlay=x=130:y=70{"," + chain if chain else ""},format=rgb24[vout]')[3]
base, ha = hal(EffectPreset.ORIGINAL), hal(EffectPreset.HALATION)
ring = (slice(60, 120), slice(118, 202))
red_gain, blue_gain = ha[ring][..., 0].mean() - base[ring][..., 0].mean(), ha[ring][..., 2].mean() - base[ring][..., 2].mean()
check(f'halation raises red around highlights (red +{red_gain:.1f}, blue +{blue_gain:.1f})', red_gain > 4 and red_gain > 3 * max(blue_gain, 0.1))
check('halation leaves dark areas alone', abs(ha[5:20, 5:40].mean() - base[5:20, 5:40].mean()) < 3)
gray_in = ['-f', 'lavfi', '-i', f'color=c=0x808080:s={W}x{H}:r={FPS}:d=1.4']
for p in (EffectPreset.PRINT_2383, EffectPreset.TUNGSTEN_NIGHT, EffectPreset.CROSS_PROCESS):
    img = effect(p, inputs=tsrc)
    check(f'{p.value} grade renders and changes the picture', np.abs(img - plain).mean() > 2)
tn = effect(EffectPreset.TUNGSTEN_NIGHT, inputs=gray_in)
check('tungsten night is blue and darker', tn[..., 2].mean() > tn[..., 0].mean() + 8 and tn.mean() < 125)
for p in ('focus_blur', 'tilt_shift', 'mosaic', 'halation', 'print_2383'):
    graph, _ = build_shot_video_chain(FitMode.COVER, {'type': 'zoom_in'}, W, H, FPS, 20, p, 70, look={})
    r = subprocess.run(['ffmpeg', '-v', 'error', *tsrc, '-filter_complex', graph, '-map', '[vout]', '-f', 'null', '-'], capture_output=True, text=True)
    check(f'{p} at 70% strength renders through the full shot graph', r.returncode == 0)

# --- 6. text reveal masks --------------------------------------------------------------
L = lambda **kw: {'id': 'a', 'text': 'REVEAL', 'x': 50, 'y': 50, 'size': 64, 'color': '#FFFFFF', 'start_ms': 0, 'end_ms': 3000, 'bold': True, 'animation_ms': 1000, **kw}
def ink(layer, at):
    path = write_ass_file('x', '', 3000, {'captions_enabled': False, 'layers': [layer]}, 640, 360, out_path=str(t / 'r.ass'))
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=black:s=640x360:d=3', '-vf', f"ass={path}:fontsdir={root / 'assets' / 'fonts'}",
                                   '-ss', str(at), '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'gray', '-'])
    return np.frombuffer(raw, np.uint8).reshape(360, 640) > 128
full = ink(L(animation='none'), 2.0)
fys, fxs = np.nonzero(full)
for anim, axis, sign in (('reveal-right', 1, +1), ('reveal-up', 0, +1), ('reveal-down', 0, -1), ('reveal-split', None, 0)):
    a, b, c = ink(L(animation=anim), 0.3), ink(L(animation=anim), 0.5), ink(L(animation=anim), 2.0)
    check(f'{anim}: text appears progressively and ends complete ({a.sum()} → {b.sum()} → {c.sum()})', a.sum() < b.sum() < c.sum() and c.sum() == full.sum())
    ys, xs = np.nonzero(a if axis is None else b)
    if axis == 1:
        ok = xs.mean() > fxs.mean() + 20
    elif axis == 0:
        ok = (ys.mean() - fys.mean()) * sign > 2
    else:
        ok = abs(xs.mean() - fxs.mean()) < 15 and xs.min() > fxs.min() + 20 and xs.max() < fxs.max() - 20
    where = {'reveal-right': 'shows the right side first', 'reveal-up': 'shows the bottom first', 'reveal-down': 'shows the top first', 'reveal-split': 'opens from the centre'}[anim]
    check(f'{anim}: the wipe {where}', ok)

# --- 7. overlay loop motion ------------------------------------------------------------
Image.fromarray(np.full((60, 80, 3), (230, 30, 30), np.uint8)).save(t / 'red.png')
assets = {'red': SimpleNamespace(type='image', width=80, height=60, path=str(t / 'red.png'))}
def ov_frames(**kw):
    o = {'asset_id': 'red', 'kind': 'media', 'x': 50, 'y': 50, 'width': 25, 'rotation': 0, 'opacity': 100, 'radius': 0, 'border': 0,
         'border_color': '#FFFFFF', 'shadow': 0, 'start_ms': 0, 'end_ms': None, 'anim_in': 'none', 'anim_out': 'none', 'anim_ms': 0,
         'x2': None, 'y2': None, 'chroma': None, 'chroma_similarity': 30, 'feather': 0, 'loop': 'none', 'loop_amount': 30, 'loop_period_ms': 2000, **kw}
    ins, g = build_overlay_pass([o], assets, W, H, FPS, 2000, CACHE, base='0:v', first_input=1, final='ovl')
    return frames(['-f', 'lavfi', '-i', f'color=c=0x103050:s={W}x{H}:r={FPS}:d=2', *ins], g + ';[ovl]format=rgb24[vout]', dur=2)
def red(f): return (f[..., 0] > 150) & (f[..., 1] < 100) & (f[..., 2] < 100)
def cent(f): ys, xs = np.nonzero(red(f)); return xs.mean(), ys.mean(), ys.min()
def spread(fr):
    cs = np.array([cent(f)[:2] for f in fr]); return np.ptp(cs[:, 0]), np.ptp(cs[:, 1])
sx, sy = spread(ov_frames(loop='float', loop_amount=80, loop_period_ms=1000))
check(f'float moves the overlay up/down and sideways over time (x range {sx:.1f}, y range {sy:.1f} px)', sy > 10 and sx > 3)
sx, sy = spread(ov_frames(loop='bob', loop_amount=80, loop_period_ms=1000))
check(f'bob moves the overlay vertically only (x range {sx:.1f}, y range {sy:.1f} px)', sy > 10 and sx < 1)
pe = ov_frames(loop='pendulum', loop_amount=100, loop_period_ms=2000)
(ax, ay, at), (bx, by, bt) = cent(pe[0]), cent(pe[8])
check(f'pendulum swings the card (centre x {ax:.1f}→{bx:.1f})', abs(bx - ax) > 5)
check('pendulum hinges at the top centre (the point just under it stays covered in every frame)', all(red(f)[63:66, 158:163].all() for f in pe))
check('pendulum swings both ways', max(cent(f)[0] for f in pe) > 165 and min(cent(f)[0] for f in pe) < 155)
static = ov_frames()
check('no loop: the overlay stays still', abs(cent(static[0])[1] - cent(static[10])[1]) < 0.5)

# --- 8. speed ramp curves -----------------------------------------------------------------
# a 4 px bar moving exactly 150 px per second across a 1280x40 strip: its x reveals the source time
ff('-f', 'lavfi', '-i', 'color=c=black:s=1280x40:d=8.5:r=30', '-f', 'lavfi', '-i', 'color=c=white:s=4x40:r=30', '-filter_complex',
   "[0][1]overlay=x='t*150':y=0:shortest=1", '-pix_fmt', 'yuv420p', str(t / 'mover.mp4'))
def src_times(sp, out_s=2.0, fps=30):
    src_s, pre, post = speed_plan(clean_speed(sp) if sp else {}, out_s, fps)
    chain = ','.join(x for x in (pre, f'fps={fps}', post) if x)
    fr = frames(['-i', str(t / 'mover.mp4')], f'[0:v]{chain},format=rgb24[vout]', w=1280, h=40, dur=out_s)
    out = []
    for f in fr:
        xs = np.nonzero(f[10:30].max(axis=0).max(axis=1) > 128)[0]
        out.append(xs.mean() / 150 if xs.size else None)
    return out, fr
def rates(ts, step=3):
    return [(ts[i + step] - ts[i]) * 30 / step for i in range(0, len(ts) - step) if ts[i] is not None and ts[i + step] is not None]
r_in = rates(src_times({'ramp': 'ease_in'})[0]); r_out = rates(src_times({'ramp': 'ease_out'})[0])
check(f'ease in: slow start, fast end ({r_in[0]:.2f}x → {r_in[-1]:.2f}x)', r_in[0] < 0.6 and r_in[-1] > 1.8)
check(f'ease out: fast start, slow end ({r_out[0]:.2f}x → {r_out[-1]:.2f}x)', r_out[0] > 1.8 and r_out[-1] < 0.6)
rb = rates(src_times({'ramp': 'bullet'})[0])
check(f'bullet time: fast, slow, fast ({rb[0]:.2f} / {min(rb):.2f} / {rb[-1]:.2f})', rb[0] > 2 and min(rb) < 0.45 and rb[-1] > 2)
rc = rates(src_times({'ramp': 'curve', 'curve': [0.5, 3, 0.5]})[0])
check(f'custom curve 0.5 → 3 → 0.5 plays slow, fast, slow ({rc[0]:.2f} / {max(rc):.2f} / {rc[-1]:.2f})', rc[0] < 0.8 and max(rc) > 2.2 and rc[-1] < 0.8)
check('old ramp values keep working', clean_speed({'ramp': 'slow_middle'})['ramp'] == 'slow_middle')
_, plain_slow = src_times({'speed': 0.4}, out_s=1.0)
_, smooth_slow = src_times({'speed': 0.4, 'smooth': True}, out_s=1.0)
dup = lambda fr: sum(np.abs(fr[i + 1] - fr[i]).max() < 1 for i in range(len(fr) - 1))
check(f'smooth slow motion interpolates new frames ({dup(plain_slow)} repeated frames → {dup(smooth_slow)})', dup(smooth_slow) < dup(plain_slow) / 3)

# --- 9. dialogue cleanup -------------------------------------------------------------------
check('dialogue voice effect is accepted', clean_edit({'voice_fx': 'dialogue'}, 5000)['voice_fx'] == 'dialogue')
try:
    clean_edit({'voice_fx': 'isolate_voice'}, 5000); ok = False
except AudioEditError:
    ok = True
check('unknown voice effects are rejected', ok)
ff('-f', 'lavfi', '-i', 'sine=f=440:d=3:sample_rate=48000', '-f', 'lavfi', '-i', 'anoisesrc=d=3:c=white:a=0.05:r=48000', '-filter_complex', '[0][1]amix=inputs=2:normalize=0', str(t / 'noisy.wav'))
def pcm(path, af=None):
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path), *(['-af', af] if af else []), '-ac', '1', '-ar', '48000', '-f', 's16le', '-'])
    return np.frombuffer(raw, np.int16).astype(float)
def snr(a):
    a = a[48000:48000 * 2]; spec = np.abs(np.fft.rfft(a)) ** 2; fr = np.fft.rfftfreq(a.size, 1 / 48000)
    return spec[(fr > 430) & (fr < 450)].sum() / spec[(fr > 1000) & (fr < 8000)].sum()
before, after = snr(pcm(t / 'noisy.wav')), snr(pcm(t / 'noisy.wav', narration_filter({'voice_fx': 'dialogue'}, 3000)))
check(f'dialogue cleanup reduces background noise (tone/noise ratio x{after / before:.1f})', after > 2 * before)

# --- 10. API: validation, music fit, end-to-end scene render -------------------------------------
client = TestClient(app).__enter__()
p = client.post('/api/projects', json={'title': 'rc6', 'aspect': '16:9'}).json(); pid = p['id']
up = lambda f: client.post('/api/assets/upload', params={'project_id': pid}, files={'file': (f, open(t / f, 'rb'))}).json()
sid = client.get(f'/api/projects/{pid}').json()['scenes'][0]['id']
look = lambda body: client.patch(f'/api/scenes/{sid}', json={'look': body}).status_code
for body, why in [({'flare': {'color': 'orange'}}, 'flare colour'), ({'flare': {'blend': 'multiply'}}, 'flare blend'), ({'flare': {'amount': 150}}, 'flare amount'),
                  ({'wiggle': {'amount': 101}}, 'wiggle amount'), ({'wiggle': {'twist': 1}}, 'wiggle unknown key'), ({'shake': {'preset': 'earthquake'}}, 'shake preset'),
                  ({'focus': {'size': 0}}, 'focus size'), ({'mosaic': {'block': 500}}, 'mosaic block'), ({'rgbsplit': {'amount': 0}}, 'RGB split amount')]:
    check(f'look rejects bad {why}', look(body) == 400)
check('valid pack settings save', look({'flare': {'x': 20, 'drift': 30}, 'wiggle': {'amount': 20}, 'shake': {'preset': 'run'}, 'focus': {'size': 50}, 'mosaic': {'block': 12}, 'rgbsplit': {'amount': 60}}) == 200)
check('effect presets are accepted', all(client.patch(f'/api/scenes/{sid}', json={'effect_preset': k}).status_code == 200 for k in ('focus_blur', 'tilt_shift', 'mosaic', 'halation', 'print_2383', 'tungsten_night', 'cross_process')))
TL = lambda a: {'font': {'layers': [L(animation=a)]}}
check('text reveal animations are accepted', all(client.patch(f'/api/scenes/{sid}', json=TL(a)).status_code == 200 for a in ('reveal-right', 'reveal-up', 'reveal-down', 'reveal-split')))
check('rotational wipe is not offered', client.patch(f'/api/scenes/{sid}', json=TL('reveal-clock')).status_code in (400, 422))
client.patch(f'/api/scenes/{sid}', json={'font': {'layers': []}})
tex_asset = up('tex.png'); red_asset = up('red.png')
client.post(f'/api/scenes/{sid}/shots', json={'asset_id': tex_asset['id']})
ovl = lambda **kw: client.patch(f'/api/scenes/{sid}', json={'overlays': [{'asset_id': red_asset['id'], **kw}]}).status_code
check('overlay rejects unknown loop motion', ovl(loop='spin') == 400)
check('overlay rejects too-short loop cycle', ovl(loop='float', loop_period_ms=100) == 400)
check('overlay rejects loop amount over 100', ovl(loop='bob', loop_amount=120) == 400)
mv = up('mover.mp4'); vshot = client.post(f'/api/scenes/{sid}/shots', json={'asset_id': mv['id']}).json()
spd = lambda body: client.patch(f"/api/scenes/shots/{vshot['id']}", json={'speed': body}).status_code
check('speed curve needs 3-5 points', spd({'ramp': 'curve', 'curve': [1, 2]}) == 400 and spd({'ramp': 'curve', 'curve': [1, 1, 1, 1, 1, 1]}) == 400)
check('speed curve points must be 0.25-4x', spd({'ramp': 'curve', 'curve': [1, 5, 1]}) == 400)
check('smooth must be true/false', spd({'smooth': 'yes'}) == 400)
check('valid curve with smooth saves', spd({'ramp': 'curve', 'curve': [1, 0.5, 2, 1], 'smooth': True}) == 200)
client.delete(f"/api/scenes/shots/{vshot['id']}")

# music: 16 s of kicks at 120 BPM with a changing melody
ff('-f', 'lavfi', '-i', "aevalsrc='0.8*sin(2*PI*55*t)*exp(-mod(t,0.5)*18)+0.15*sin(2*PI*(330+110*floor(mod(t,4)))*t)':s=44100:d=16", '-ac', '2', str(t / 'music.wav'))
music = up('music.wav')
check('music fit rejects a non-audio asset', client.post(f'/api/projects/{pid}/music-fit', json={'asset_id': tex_asset['id'], 'target_ms': 8000}).status_code == 400)
check('music fit rejects a too-short target', client.post(f'/api/projects/{pid}/music-fit', json={'asset_id': music['id'], 'target_ms': 500}).status_code == 400)
def probe_ms(asset_id):
    path = t / f'm{time.time_ns()}.wav'; path.write_bytes(client.get(f'/api/assets/{asset_id}/stream').content)
    return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(path)])) * 1000, path
for target in (9000, 27000):
    r = client.post(f'/api/projects/{pid}/music-fit', json={'asset_id': music['id'], 'target_ms': target})
    check(f'music fit to {target / 1000:.0f} s creates a new audio asset', r.status_code == 200 and r.json()['id'] != music['id'] and r.json()['type'] == 'audio')
    ms, path = probe_ms(r.json()['id'])
    check(f'music fit output is {ms:.0f} ms (target {target} ± 150)', abs(ms - target) <= 150)
    tail = pcm(path)[-4800:]
    check('music fit ends with a fade-out', np.abs(tail).max() < 2000)
check('original music is preserved', abs(probe_ms(music['id'])[0] - 16000) < 60)
from app.render.beats import detect_beats
bpm, beats = detect_beats(str(t / 'music.wav'))
segs = plan_segments(16.0, 9.0, beats)
gap = (segs[1][0] - segs[0][1]) / (60 / bpm)
check(f'shortening removes whole bars from the middle on the beat ({bpm} BPM, cut {segs[0][1]:.2f}→{segs[1][0]:.2f} s = {gap:.2f} beats)',
      len(segs) == 2 and min(abs(segs[0][1] - b) for b in beats) < 1e-6 and round(gap) >= 4 and abs(gap - 4 * round(gap / 4)) < 0.1 and 3 < segs[0][1] < 13)
client.patch(f'/api/scenes/{sid}', json={'timing_mode': 'fixed', 'requested_duration_ms': 6000})
r = client.post(f'/api/projects/{pid}/music-fit', json={'asset_id': music['id']})
check('music fit defaults to the video length', r.status_code == 200 and abs(probe_ms(r.json()['id'])[0] - 6000) <= 150)
check('the fitted track can be set as the music bed', client.patch(f'/api/projects/{pid}', json={'finishing': {'music': {'asset_id': r.json()['id'], 'volume': 35, 'duck': 70, 'fade_in_ms': 0, 'fade_out_ms': 1000}}}).status_code == 200)

# one end-to-end scene render through the real renderer at a tiny canvas (scene FX + overlay loop + preset)
from app.db.database import SessionLocal
from app.db.models import Project
with SessionLocal() as db:
    pr = db.get(Project, pid); pr.width, pr.height, pr.fps = W, H, FPS; db.commit()
client.patch(f'/api/scenes/{sid}', json={'requested_duration_ms': 1500, 'effect_preset': 'halation', 'effect_intensity': 80,
                                         'look': {'flare': {'x': 70, 'y': 30, 'drift': 40, 'blend': 'add'}, 'wiggle': {'amount': 30}, 'shake': {'preset': 'walk', 'amount': 40}},
                                         'overlays': [{'asset_id': red_asset['id'], 'width': 20, 'loop': 'pendulum', 'loop_amount': 60, 'loop_period_ms': 1000, 'anim_in': 'none', 'anim_out': 'none'}]})
j = client.post(f'/api/scenes/{sid}/render').json()
while (s := client.get(f"/api/jobs/{j['job_id']}").json())['status'] not in ('succeeded', 'failed', 'cancelled'): time.sleep(.3)
check(f"scene with halation, flare, wiggle, walk shake and a pendulum overlay renders ({s['status']})", s['status'] == 'succeeded')
print(f'{n} checks passed')
