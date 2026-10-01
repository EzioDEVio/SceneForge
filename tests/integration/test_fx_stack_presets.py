"""Effect stack (reorderable / bypassable scene FX) and look preset packs,
verified on real FFmpeg renders of tiny synthetic media.

1. The default stack order builds the exact same filter graph as the fixed order
   used before the stack existed (reference copied below), and a full scene render
   without fx_order is pixel-identical to one with fx_order = the default order.
2. [flare, shake] and [shake, flare] render different frames; bypass == removing.
3. fx_order / fx_bypass validation (unknown ids, duplicates).
4. Look packs: starter pack validates, export -> import round trip, invalid
   packs rejected with clear messages, applying a preset renders."""
import hashlib, json, os, pathlib, subprocess, sys, tempfile, time
import numpy as np
from PIL import Image, ImageDraw
root = pathlib.Path(__file__).resolve().parents[2]
tmp = tempfile.TemporaryDirectory(); os.environ['SCENEFORGE_DATA_DIR'] = tmp.name
t = pathlib.Path(tmp.name)
sys.path.insert(0, str(root / 'backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.render import scene_fx as fx
from app.render.fx_stack import DEFAULT_ORDER, active_stages, stack_graph

n = 0
def check(name, ok):
    global n
    assert ok, name
    n += 1; print('PASS ' + name, flush=True)
W, H, FPS, DUR = 320, 180, 15, 1.4
CACHE = t / 'cache'

def legacy_graph(base, look, w, h, fps, dur, cache):
    """The fixed scene-FX order from renderer._apply_overlays before the effect stack (0.7.0-rc5)."""
    parts = []
    if look.get("spotlight"):
        g, base = fx.spotlight_graph(base, look["spotlight"], fx.spotlight_png(look["spotlight"], w, h, cache), fps, dur); parts += g
    if look.get("leak") and look["leak"]["amount"] > 0:
        g, base = fx.leak_graph(base, look["leak"], fx.leak_clip(look["leak"]["color"], look["leak"]["speed"], cache), w, h, fps); parts += g
    if look.get("flare") and look["flare"]["amount"] > 0:
        png, drift = fx.flare_png(look["flare"], w, h, cache)
        g, base = fx.flare_graph(base, look["flare"], png, drift, w, h, fps, dur); parts += g
    if look.get("wiggle") and look["wiggle"]["amount"] > 0:
        g, base = fx.wiggle_graph(base, look["wiggle"], w, h, fps, dur); parts += g
    if look.get("shake") and (look["shake"]["amount"] > 0 or look["shake"]["impact"]):
        g, base = fx.shake_graph(base, look["shake"], w, h, fps); parts += g
    return parts, base

def frames(look, flat=False):
    g, lab = stack_graph('0:v', look, W, H, FPS, DUR, CACHE)
    graph = ';'.join(g + [f'[{lab}]format=rgb24[vout]'])
    src = ['-f', 'lavfi', '-i', f'color=c=0x303030:s={W}x{H}:r={FPS}:d={DUR}'] if flat else ['-loop', '1', '-framerate', str(FPS), '-t', str(DUR), '-i', str(t / 'tex.png')]
    raw = subprocess.run(['ffmpeg', '-v', 'error', *src,
                          '-filter_complex', graph, '-map', '[vout]', '-t', str(DUR), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True)
    assert raw.returncode == 0, raw.stderr.decode()[-600:]
    return np.frombuffer(raw.stdout, np.uint8).reshape(-1, H, W, 3).astype(float)

rng = np.random.default_rng(7)
tex = Image.fromarray(rng.integers(0, 255, (H // 6, W // 6, 3), dtype=np.uint8)).resize((W, H), Image.NEAREST)
d = ImageDraw.Draw(tex)
for k in range(10):
    x, y = int(rng.integers(0, W)), int(rng.integers(0, H))
    d.rectangle([x, y, x + 24, y + 16], fill=tuple(int(v) for v in rng.integers(0, 255, 3)))
tex.save(t / 'tex.png')

# --- 1. default order == the previous fixed order ---------------------------------------
ALL = {'spotlight': fx.clean_spotlight({}), 'leak': fx.clean_leak({}), 'flare': fx.clean_flare({'drift': 30}),
       'wiggle': fx.clean_wiggle({}), 'shake': fx.clean_shake({'preset': 'walk'})}
looks = [{}, ALL, {'flare': ALL['flare'], 'shake': ALL['shake']}, {'leak': ALL['leak'], 'wiggle': ALL['wiggle']},
         {'shake': fx.clean_shake({'amount': 0, 'impact': True})}, {'flare': fx.clean_flare({'amount': 0}), 'spotlight': ALL['spotlight']}]
same = all(stack_graph('0:v', lk, W, H, FPS, DUR, CACHE) == legacy_graph('0:v', lk, W, H, FPS, DUR, CACHE) for lk in looks)
check('without fx_order the stack builds the identical filter graph as the old fixed order (6 looks)', same)
check('explicit default fx_order builds the identical graph too',
      all(stack_graph('0:v', {**lk, 'fx_order': list(DEFAULT_ORDER)}, W, H, FPS, DUR, CACHE) == legacy_graph('0:v', lk, W, H, FPS, DUR, CACHE) for lk in looks))
check('unlisted effects run after the listed ones in default order', active_stages({**ALL, 'fx_order': ['shake', 'leak']}) == ['shake', 'leak', 'spotlight', 'flare', 'wiggle'])

# --- 2. order matters; bypass == removing ----------------------------------------------
FS = {'flare': fx.clean_flare({'x': 70, 'y': 30, 'amount': 90, 'color': '#FFFFFF'}), 'shake': fx.clean_shake({'preset': 'run', 'amount': 90, 'speed': 80})}
a = frames({**FS, 'fx_order': ['flare', 'shake']})
b = frames({**FS, 'fx_order': ['shake', 'flare']})
diff = np.abs(a - b).mean()
check(f'[flare, shake] and [shake, flare] render different frames (mean diff {diff:.1f})', a.shape == b.shape and diff > 2)
# with shake last the flare moves with the picture; with flare last its source stays put
# (on a flat grey picture the only thing shake can move is the flare)
def peak(fr): return np.array([np.unravel_index(np.argmax(f.mean(axis=2)), f.shape[:2]) for f in fr])
moved = peak(frames({**FS, 'fx_order': ['flare', 'shake']}, flat=True)).std(axis=0).sum()
steady = peak(frames({**FS, 'fx_order': ['shake', 'flare']}, flat=True)).std(axis=0).sum()
check(f'flare before shake moves the flare with the picture; shake before flare keeps it on the lens ({moved:.1f} vs {steady:.1f} px)', moved > 1 and steady < 0.5)
by = frames({**FS, 'fx_bypass': ['shake']})
only = frames({'flare': FS['flare']})
check('bypassing shake renders exactly like removing it', np.array_equal(by, only))
check('bypass keeps the graph identical to removal', stack_graph('0:v', {**FS, 'fx_bypass': ['shake']}, W, H, FPS, DUR, CACHE) == stack_graph('0:v', {'flare': FS['flare']}, W, H, FPS, DUR, CACHE))

# --- 3. validation through the scene API --------------------------------------------------
client = TestClient(app).__enter__()
pid = client.post('/api/projects', json={'title': 'stack', 'aspect': '16:9'}).json()['id']
sid = client.get(f'/api/projects/{pid}').json()['scenes'][0]['id']
look = lambda body: client.patch(f'/api/scenes/{sid}', json={'look': body})
for body, why in [({'fx_order': ['flare', 'blur']}, 'unknown id'), ({'fx_order': ['flare', 'flare']}, 'duplicate id'), ({'fx_order': 'flare'}, 'non-list'),
                  ({'fx_bypass': ['redact']}, 'non-stack id in bypass'), ({'fx_bypass': ['shake', 'shake']}, 'duplicate bypass'), ({'fx_order': ['overlays']}, 'overlays (fixed stage)')]:
    r = look(body)
    check(f'fx stack rejects {why} ({r.json().get("detail", "")[:60]})', r.status_code == 400)
r = look({'fx_order': ['shake', 'flare'], 'fx_bypass': ['leak']})
check('valid fx_order / fx_bypass save', r.status_code == 200 and r.json()['look_json']['fx_order'] == ['shake', 'flare'] and r.json()['look_json']['fx_bypass'] == ['leak'])
r = look({'fx_order': None, 'fx_bypass': []})
check('null / empty list resets the stack', r.status_code == 200 and 'fx_order' not in r.json()['look_json'] and 'fx_bypass' not in r.json()['look_json'])

# --- full scene renders: no fx_order vs default fx_order are pixel-identical ---------------
from app.db.database import SessionLocal
from app.db.models import Asset, Project
from app.render.renderer import _resolve_asset_path
with SessionLocal() as db:
    pr = db.get(Project, pid); pr.width, pr.height, pr.fps = W, H, FPS; db.commit()
img = client.post('/api/assets/upload', params={'project_id': pid}, files={'file': ('tex.png', open(t / 'tex.png', 'rb'))}).json()
client.post(f'/api/scenes/{sid}/shots', json={'asset_id': img['id']})
client.patch(f'/api/scenes/{sid}', json={'timing_mode': 'fixed', 'requested_duration_ms': 1200, 'subtitle_text': '',
                                         'look': {'flare': {'x': 70, 'y': 30, 'drift': 30}, 'shake': {'preset': 'walk', 'amount': 50}, 'leak': {'amount': 40}}})

def render_scene():
    j = client.post(f'/api/scenes/{sid}/render').json()
    while (s := client.get(f"/api/jobs/{j['job_id']}").json())['status'] not in ('succeeded', 'failed', 'cancelled'): time.sleep(.3)
    assert s['status'] == 'succeeded', s
    with SessionLocal() as db:
        from app.db.models import Scene
        path = _resolve_asset_path(db.get(Asset, db.get(Scene, sid).rendered_asset_id))
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-map', '0:v', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True).stdout
    return hashlib.sha256(raw).hexdigest(), len(raw)

h_default, size = render_scene()
look({'fx_order': list(DEFAULT_ORDER)})
h_explicit, _ = render_scene()
check(f'full scene render without fx_order is pixel-identical to the default order ({h_default[:12]}, {size} bytes)', h_default == h_explicit and size > 0)
look({'fx_order': ['shake', 'leak', 'flare']})
h_swapped, _ = render_scene()
check('reordering the stack changes the rendered scene', h_swapped != h_default)
look({'fx_order': None})

# --- 4. look preset packs ---------------------------------------------------------------
starter = json.loads((root / 'assets' / 'look-packs' / 'sceneforge-starter-pack.json').read_text(encoding='utf-8'))
r = client.post('/api/look-presets/validate', json=starter)
check(f'starter pack validates entirely ({len(starter["presets"])} presets)', r.status_code == 200 and len(r.json()['presets']) == len(starter['presets']) >= 8)
listing = client.get('/api/look-presets').json()
check('built-in starter presets are listed; no user presets yet', len(listing['builtin']) == len(starter['presets']) and listing['presets'] == [] and 'shake' in listing['look_keys'])
for p in starter['presets']:
    for k in p['look']:
        check(f'starter "{p["name"]}" uses a portable look key ({k})', k in listing['look_keys'])

def bad(pack, needle, why):
    r = client.post('/api/look-presets/validate', json=pack)
    detail = r.json().get('detail', '')
    check(f'invalid pack rejected: {why} -> "{detail[:90]}"', r.status_code == 400 and needle in detail)
    check(f'invalid pack is not stored: {why}', client.post('/api/look-presets', json=pack).status_code == 400)
P = lambda **kw: {'format': 'sceneforge-look-pack', 'version': 1, 'presets': [{'name': 'X', 'effect_preset': 'noir', 'effect_intensity': 80, 'look': {}, **kw}]}
bad({'presets': []}, 'not a SceneForge look pack', 'wrong format')
bad({**P(), 'version': 2}, 'Unsupported look pack version', 'future version')
bad({**P(), 'presets': []}, 'no presets', 'empty pack')
bad(P(look={'flare': {'amount': 150}}), 'Preset 1 (“X”): Lens flare amount', 'bad flare amount')
bad(P(look={'overlays': []}), 'specific to a scene', 'media-specific key (overlays)')
bad(P(look={'lut': {'asset_id': 'abc', 'strength': 50}}), 'specific to a scene', 'LUT asset id')
bad(P(look={'sparkles': {}}), 'unknown look setting', 'unknown look key')
bad(P(effect_preset='warp_speed'), "unknown effect preset 'warp_speed'", 'unknown effect preset')
bad(P(effect_intensity=101), 'between 0 and 100', 'intensity out of range')
bad(P(name=''), 'needs a name', 'missing name')
bad(P(look={'fx_order': ['flare', 'flare']}), 'listed twice', 'duplicate fx_order in preset')

# export the scene's look (portable keys only) -> import -> export again
client.patch(f'/api/scenes/{sid}', json={'effect_preset': 'teal_amber', 'effect_intensity': 70,
                                         'look': {'tone': {'amount': 30}, 'adjust': {'contrast': 12, 'grain': 10}, 'spotlight': {'dim': 40},
                                                  'redact': [{'x': 10, 'y': 10}], 'fx_order': ['shake', 'flare']}})
scene_look = client.get(f'/api/scenes/{sid}').json()['look_json']
exported = client.get(f'/api/look-presets/scene/{sid}', params={'name': 'My teal'}).json()
pre = exported['presets'][0]
check('scene look exports as a v1 pack', exported['format'] == 'sceneforge-look-pack' and exported['version'] == 1 and pre['name'] == 'My teal')
check('export drops media-specific keys (spotlight, redact) and keeps the look', not {'spotlight', 'redact'} & set(pre['look']) and pre['look']['tone'] == scene_look['tone']
      and pre['look']['fx_order'] == ['shake', 'flare'] and pre['effect_preset'] == 'teal_amber' and pre['effect_intensity'] == 70)
r = client.post('/api/look-presets', json=exported)
check('pack imports and is stored', r.status_code == 200 and len(r.json()['added']) == 1 and (t / 'look_presets.json').exists())
r2 = client.post('/api/look-presets', json=exported).json()
check('importing the same name again keeps both ("My teal (2)")', r2['added'][0]['name'] == 'My teal (2)')
client.post('/api/look-presets', json={'preset': {'name': 'Starter noir', **{k: starter['presets'][3][k] for k in ('effect_preset', 'effect_intensity', 'look')}}})
stored = client.get('/api/look-presets').json()['presets']
check('stored presets listed (3)', [p['name'] for p in stored] == ['My teal', 'My teal (2)', 'Starter noir'])
again = client.get('/api/look-presets/export').json()
check('export -> import -> export round trip is lossless', again['presets'][0] == pre and client.post('/api/look-presets/validate', json=again).status_code == 200)
check('delete removes a stored preset', client.delete(f"/api/look-presets/{stored[1]['id']}").status_code == 200 and len(client.get('/api/look-presets').json()['presets']) == 2)
check('delete of an unknown preset is a 404', client.delete('/api/look-presets/nope').status_code == 404)

# apply a preset the way the UI does: replace every portable key, keep media keys
keys = listing['look_keys']
summer = next(p for p in listing['builtin'] if p['name'] == 'Summer haze')
patch = {'effect_preset': summer['effect_preset'], 'effect_intensity': summer['effect_intensity'], 'look': {k: summer['look'].get(k) for k in keys}}
r = client.patch(f'/api/scenes/{sid}', json=patch)
lj = r.json()['look_json']
check('applying a preset sets its look and clears other portable settings',
      r.status_code == 200 and lj['flare'] == summer['look']['flare'] and lj['leak'] == summer['look']['leak'] and 'tone' not in lj and 'fx_order' not in lj)
check('applying a preset keeps media-specific settings (spotlight, redact)', 'spotlight' in lj and 'redact' in lj)
client.patch(f'/api/scenes/{sid}', json={'look': {'redact': None, 'spotlight': None}})
h_preset, _ = render_scene()
check('a scene with an applied starter preset (Summer haze) renders', bool(h_preset))
print(f'{n} checks passed')
