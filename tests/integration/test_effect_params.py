"""Per-effect settings (look_json.fx_params, render/effect_params.py):

1. GET /api/effects/schema covers every EffectPreset except 'original';
   params are well formed (number: min <= default <= max; color: #RRGGBB).
2. Default params reproduce the existing filter strings byte-for-byte for
   every preset (absent, empty and explicit-default fx_params), so existing
   projects render exactly as before.
3. Changing any single parameter changes the filter string, and every
   parameter at its extremes builds a graph FFmpeg accepts.
4. Real FFmpeg renders on tiny lavfi media (~10 presets): defaults are
   pixel-identical to no settings; changed settings change the pixels in the
   expected direction.
5. Validation through PATCH /api/scenes/{id}: out-of-range, unknown params,
   unknown / managed presets and bad colours are rejected; null clears.
"""
import os, pathlib, subprocess, sys, tempfile
import numpy as np
root = pathlib.Path(__file__).resolve().parents[2]
tmp = tempfile.TemporaryDirectory(); os.environ['SCENEFORGE_DATA_DIR'] = tmp.name
sys.path.insert(0, str(root / 'backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.domain.constants import EffectPreset
from app.render.effect_params import PRESETS, MANAGED, defaults_for, effect_filter
from app.render.filters import _EFFECT_FILTERS, build_effect_chain, build_halation_chain, build_shot_video_chain

n = 0
def check(name, ok):
    global n
    assert ok, name
    n += 1; print('PASS ' + name, flush=True)

client = TestClient(app).__enter__()

# --- 1. schema ---------------------------------------------------------------------------
sch = client.get('/api/effects/schema').json()
presets = sch['presets']
every = {e.value for e in EffectPreset} - {'original'}
check('schema covers every effect preset except original', set(presets) == every)
check('schema stores settings under look.fx_params', sch['look_key'] == 'fx_params')
generic = {k for k, v in presets.items() if not v.get('managed_by')}
check('presets with their own panels are marked managed (glitch, focus, tilt-shift, mosaic, chromatic split)',
      {k for k in every - generic} == {'glitch', 'focus_blur', 'tilt_shift', 'mosaic', 'chromatic_split'})
check('every other preset has 2-4 settings', all(2 <= len(presets[k]['params']) <= 4 for k in generic))
ok = True
for k, v in presets.items():
    names = [q['name'] for q in v['params']]
    ok &= len(names) == len(set(names))
    for q in v['params']:
        ok &= bool(q['label']) and q['kind'] in ('number', 'color')
        if q['kind'] == 'number':
            ok &= q['min'] <= q['default'] <= q['max'] and q['step'] > 0
        else:
            ok &= isinstance(q['default'], str) and len(q['default']) == 7 and q['default'].startswith('#')
check('every param is well formed (unique names, labels, kind, range contains default)', ok)

# --- 2. defaults reproduce the current filter strings ------------------------------------
HALATION_1920 = ("format=gbrp,split[hlb][hlh];[hlh]colorchannelmixer=rr=0.30:rg=0.59:rb=0.11:gr=0.30:gg=0.59:gb=0.11:br=0.30:bg=0.59:bb=0.11,"
                 "lutrgb=r='clip((val-165)*2.6,0,255)':g='clip((val-165)*2.6,0,255)*0.38':b='clip((val-165)*2.6,0,255)*0.10',"
                 "gblur=sigma=23.04[hlg];[hlb][hlg]blend=all_mode=screen:all_opacity=0.9,format=yuv420p")
check('halation reference (pre-settings) string is unchanged', build_halation_chain(1920) == HALATION_1920)
for e in EffectPreset:
    if e.value not in generic:
        continue
    for w, h in ((1920, 1080), (320, 180)):
        ref = build_halation_chain(w) if e == EffectPreset.HALATION else _EFFECT_FILTERS[e]
        defaults = defaults_for(e)
        same = all(effect_filter(e, fx, w, h) == ref for fx in (None, {}, {e.value: {}}, {e.value: defaults}, {'warm' if e.value != 'warm' else 'cool': {'saturation': 150}}))
        assert same, (e.value, ref, effect_filter(e, {e.value: defaults}, w, h))
        for inten in (100, 60, 5):
            old = build_effect_chain(e.value, inten, None, w, {}, h)
            assert old == build_effect_chain(e.value, inten, None, w, {'fx_params': {e.value: defaults}}, h), (e.value, inten)
check(f'default settings reproduce the exact filter string for all {len(generic)} presets (absent / empty / explicit defaults / other preset)', True)
look0 = {'adjust': {'contrast': 10}}
check('whole shot graph is identical with default fx_params',
      all(build_shot_video_chain('cover', {'type': 'static'}, 320, 180, 15, 30, e, 70, look=look0)
          == build_shot_video_chain('cover', {'type': 'static'}, 320, 180, 15, 30, e, 70, look={**look0, 'fx_params': {e: defaults_for(e)}})
          for e in generic))

# --- 3. every param changes the string; extremes are valid FFmpeg --------------------------
unchanged = []
for e in generic:
    base = effect_filter(e, None, 320, 180)
    for q in presets[e]['params']:
        v = '#3366CC' if q['kind'] == 'color' else (q['max'] if q['default'] != q['max'] else q['min'])
        if effect_filter(e, {e: {q['name']: v}}, 320, 180) == base:
            unchanged.append(f'{e}.{q["name"]}')
check(f'changing any single setting changes the filter string ({sum(len(presets[e]["params"]) for e in generic)} settings)', not unchanged)


def ff_ok(chain):
    g = f'[0:v]format=yuv420p[a];[a]{chain},format=rgb24[vout]'
    r = subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=96x54:r=10:d=0.2', '-filter_complex', g,
                        '-map', '[vout]', '-f', 'null', '-'], capture_output=True)
    return r.returncode == 0 and not r.stderr.strip(), r.stderr.decode()[-300:]


bad = []
for e in generic:
    combos = [{q['name']: ('#000000' if q['kind'] == 'color' else q['min']) for q in presets[e]['params']},
              {q['name']: ('#FFFFFF' if q['kind'] == 'color' else q['max']) for q in presets[e]['params']}]
    for c in combos:
        good, err = ff_ok(build_effect_chain(e, 70, None, 96, {'fx_params': {e: c}}, 54))
        if not good:
            bad.append((e, c, err))
check('all settings at their minimum / maximum build a graph FFmpeg runs cleanly', not bad or print(bad))

# --- 4. real renders -----------------------------------------------------------------------
W, H = 160, 90


def frames(e, fx=None, inten=100, src='testsrc2', dur=0.6):
    chain = build_effect_chain(e, inten, None, W, {'fx_params': fx} if fx is not None else {}, H)
    g = f'[0:v]format=yuv420p[a];[a]{chain},format=rgb24[vout]'
    r = subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', f"{src}{':' if '=' in src else '='}s={W}x{H}:r=10:d={dur}", '-filter_complex', g,
                        '-map', '[vout]', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True)
    assert r.returncode == 0, r.stderr.decode()[-500:]
    return np.frombuffer(r.stdout, np.uint8).reshape(-1, H, W, 3).astype(float)


def sat(a):
    return (a.max(axis=-1) - a.min(axis=-1)).mean()


SAMPLE = ['warm', 'sepia', 'vignette', 'vhs', 'duotone', 'film_grain', 'motion_trail', 'halation', 'golden_hour', 'matte', 'glow', 'black_and_white']
for e in SAMPLE:
    a, b = frames(e), frames(e, {e: defaults_for(e)})
    check(f'{e}: default settings are pixel-identical to no settings', np.array_equal(a, b))

d = frames('warm', {'warm': {'warmth': 100}}) - frames('warm', {'warm': {'warmth': 0}})
check('warm: more warmth raises red and lowers blue', d[..., 0].mean() > 2 and d[..., 2].mean() < -1 and d[..., 0].mean() - d[..., 2].mean() > 4)
check('warm: saturation 40 % is less saturated than 180 %', sat(frames('warm', {'warm': {'saturation': 40}})) + 10 < sat(frames('warm', {'warm': {'saturation': 180}})))
sp = frames('sepia', {'sepia': {'color': '#80B0FF'}})
check('sepia: a blue tone colour gives a blue-toned picture', sp[..., 2].mean() > sp[..., 0].mean() + 10 > 10)
v_lo, v_hi = frames('vignette', {'vignette': {'vignette': 0}}), frames('vignette', {'vignette': {'vignette': 100}})
corner = lambda a: a[:, :12, :16].mean()
check('vignette: amount 100 darkens the corners more than 0', corner(v_hi) + 15 < corner(v_lo))
off = frames('vignette', {'vignette': {'x': 10, 'vignette': 90}})
check('vignette: moving the centre left keeps the left side brighter than the right', off[:, :, :20].mean() > off[:, :, -20:].mean() + 10)
s0, s1 = frames('vhs', {'vhs': {'scanlines': 0}}), frames('vhs', {'vhs': {'scanlines': 80}})
check('vhs: stronger scanlines darken the picture', s1.mean() + 5 < s0.mean())
du = frames('duotone', {'duotone': {'shadow': '#000000', 'highlight': '#FF0000'}})
check('duotone: custom colours map the picture to black→red', du[..., 0].mean() > 40 and du[..., 1].max() < 2 and du[..., 2].max() < 2)
flat = 'color=c=gray'
g0, g1 = frames('film_grain', {'film_grain': {'amount': 0}}, src=flat), frames('film_grain', {'film_grain': {'amount': 80}}, src=flat)
check('film grain: amount 80 is much noisier than 0', g1.std() > g0.std() + 10)
mono = frames('film_grain', {'film_grain': {'amount': 60, 'color': 0}}, src=flat)
check('film grain: colour grain 0 % gives monochrome grain', sat(mono) < 0.3 * sat(frames('film_grain', {'film_grain': {'amount': 60}}, src=flat)))
t2, t8 = frames('motion_trail', {'motion_trail': {'frames': 2}}, dur=1.2), frames('motion_trail', {'motion_trail': {'frames': 8, 'trail': 300}}, dur=1.2)
check('motion trail: a longer, stronger trail smears the moving picture more', np.abs(np.diff(t8, axis=0)).mean() < np.abs(np.diff(t2, axis=0)).mean())
h_hi, h_lo = frames('halation', {'halation': {'threshold': 240}}), frames('halation', {'halation': {'threshold': 100}})
check('halation: a lower threshold makes more of the picture glow', h_lo.mean() > h_hi.mean() + 5)
hb = frames('halation', {'halation': {'threshold': 100, 'color': '#0040FF'}}) - frames('halation', {'halation': {'threshold': 240}})
check('halation: a blue glow colour adds blue, not red', hb[..., 2].mean() > hb[..., 0].mean() + 3)
gh = frames('golden_hour', {'golden_hour': {'shadows': 200, 'highlights': 200}}) - frames('golden_hour', {'golden_hour': {'shadows': 0, 'highlights': 0}})
check('golden hour: stronger tints push red up and blue down', gh[..., 0].mean() > 3 and gh[..., 2].mean() < -3)
m = frames('matte', {'matte': {'lift': 30}}, src='color=c=black')
check('matte: black lift 30 % lifts pure black', m.mean() > frames('matte', src='color=c=black').mean() + 20)
gl0, gl1 = frames('glow', {'glow': {'amount': 0}}), frames('glow', {'glow': {'amount': 100}})
check('glow: amount 100 is brighter than 0', gl1.mean() > gl0.mean() + 5)
bw_r, bw_b = frames('black_and_white', {'black_and_white': {'filter': 100}}, src='color=c=blue'), frames('black_and_white', {'black_and_white': {'filter': -100}}, src='color=c=blue')
check('B&W: a red filter darkens blue skies, a blue filter lightens them', bw_r.mean() + 20 < bw_b.mean())

# --- 5. validation via the API ----------------------------------------------------------
p = client.post('/api/projects', json={'title': 'fx params', 'aspect': '16:9'}).json()
sid = client.get(f"/api/projects/{p['id']}").json()['scenes'][0]['id']
look = lambda body: client.patch(f'/api/scenes/{sid}', json={'look': body})
for body, why in [({'warm': {'warmth': 101}}, 'out-of-range value'), ({'warm': {'warmth': -1}}, 'below-minimum value'),
                  ({'warm': {'heat': 10}}, 'unknown setting'), ({'sparkle': {'x': 1}}, 'unknown effect'),
                  ({'mosaic': {'block': 10}}, 'managed effect (has its own look key)'), ({'sepia': {'color': 'brown'}}, 'bad colour'),
                  ({'warm': {'warmth': True}}, 'boolean value'), ({'warm': {'warmth': '50'}}, 'string number'),
                  ({'warm': 5}, 'non-object settings'), (['warm'], 'non-object fx_params')]:
    r = look({'fx_params': body})
    check(f'fx_params rejects {why}', r.status_code == 400)
r = look({'fx_params': {'warm': {'warmth': 80, 'saturation': 120.5}, 'sepia': {'color': '#80b0ff'}, 'vhs': {}}})
fxp = r.json()['look_json'].get('fx_params') if r.status_code == 200 else None
check('valid fx_params save per preset (colour upper-cased, empty entries dropped)',
      fxp == {'warm': {'warmth': 80, 'saturation': 120.5}, 'sepia': {'color': '#80B0FF'}})
r = client.patch(f'/api/scenes/{sid}', json={'effect_preset': 'cool'})
check('switching preset keeps other presets\' settings', r.json()['look_json']['fx_params']['warm'] == {'warmth': 80, 'saturation': 120.5})
check('null clears fx_params', 'fx_params' not in look({'fx_params': None}).json()['look_json'])
from app.api.look_presets import PRESET_LOOK_KEYS
check('fx_params is a portable look-preset key', 'fx_params' in PRESET_LOOK_KEYS)
print(f'{n} checks passed')
