"""0.7.0 RC9 libraries: the bundled sticker & emoji library (assets/stickers) and the caption styles.

Stickers: every library id resolves to a PNG that exists, decodes and has transparency; the
editor's copy of the manifest matches; the API lists, serves and imports stickers into a project;
emoji and graphic stickers (plus an RC8-style browser-drawn sticker asset) render as overlays
through the real FFmpeg pipeline.
Caption styles: all styles (the 31 RC8 styles kept by name + the new ones) use only properties the
renderer maps, produce a valid ASS style, and five new styles render through real FFmpeg.
"""
import json, os, pathlib, re, subprocess, sys, tempfile, time
import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[2]
tmp = tempfile.TemporaryDirectory(); os.environ['SCENEFORGE_DATA_DIR'] = tmp.name
sys.path.insert(0, str(ROOT / 'backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.render.fontruns import ALL_FAMILIES
from app.render.subtitles import _hex_to_ass_color, write_ass_file

n = 0
def check(name, ok):
    global n
    assert ok, name
    n += 1; print('PASS ' + name, flush=True)

t = pathlib.Path(tmp.name)
BG = (20, 30, 60)

# ------------------------------------------------------------------ sticker library files
lib_dir = ROOT / 'assets' / 'stickers'
lib = json.loads((lib_dir / 'library.json').read_text(encoding='utf-8'))
items = lib['items']
ids = [i['id'] for i in items]
CATS = ['Smileys', 'Gestures', 'Hearts', 'Animals & nature', 'Food', 'Travel & places', 'Objects', 'Symbols',
        'Arrows & callouts', 'Badges & labels', 'Social', 'Shapes', 'Speech bubbles', 'Seasonal']
check(f'the library has at least 250 stickers ({len(items)}) in all {len(CATS)} categories',
      len(items) >= 250 and lib['categories'] == CATS and all(any(i['category'] == c for i in items) for c in CATS))
check('sticker ids and names are unique', len(set(ids)) == len(ids) and len({i['name'] for i in items}) == len(items))
check('every sticker is searchable (name and tags)', all(i['name'].strip() and len(i['tags'].split()) >= 1 for i in items))
front = json.loads((ROOT / 'frontend' / 'src' / 'stickerLibrary.json').read_text(encoding='utf-8'))
check("the editor's manifest copy is identical to assets/stickers/library.json", front == lib)

overlays_src = (ROOT / 'frontend' / 'src' / 'Overlays.tsx').read_text(encoding='utf-8')
legacy_block = overlays_src.split('const STICKERS')[1].split('function useProjectMedia')[0]
legacy = re.findall(r"\['[^']+','([^']+)'", legacy_block) + re.findall(r"name:'([^']+)'", legacy_block)
check('all 66 RC8 sticker names are kept in the library', len(legacy) == 66 and set(legacy) <= {i['name'] for i in items})

bad = []
for it in items:
    p = lib_dir / it['file']
    try:
        with Image.open(p) as im:
            im.load()
            a = np.asarray(im.convert('RGBA'))[..., 3]
            ok = im.format == 'PNG' and 60 <= min(im.size) and max(im.size) <= 1024 and a.min() == 0 and a.max() == 255 and (a > 128).mean() > 0.04
            if it['source'] == 'twemoji':
                ok = ok and im.size == (320, 320) and 'emoji' in it
    except Exception:
        ok = False
    if not ok:
        bad.append(it['id'])
check(f'all {len(items)} sticker PNGs exist, decode, and have transparent backgrounds with visible artwork', not bad)
total = sum(p.stat().st_size for p in lib_dir.rglob('*') if p.is_file())
check(f'the sticker library stays small ({total / 1e6:.1f} MB < 15 MB)', total < 15e6)
third = (ROOT / 'desktop' / 'THIRD_PARTY.md').read_text(encoding='utf-8')
check('Twemoji CC-BY 4.0 licence text and attribution are bundled',
      'Attribution 4.0 International' in (lib_dir / 'LICENSE-TWEMOJI-GRAPHICS.txt').read_text(encoding='utf-8')
      and 'Twemoji' in third and 'CC-BY 4.0' in third and 'CC-BY 4.0' in lib['attribution']['twemoji'])
pkg = json.loads((ROOT / 'desktop' / 'package.json').read_text(encoding='utf-8'))
check('the desktop package ships ../assets (and so assets/stickers) as app resources',
      any(r.get('from') == '../assets' and r.get('to') == 'app-resources/assets' for r in pkg['build']['extraResources']))


# ------------------------------------------------------------------ caption styles
def legacy_caption_presets() -> list[dict]:
    src = (ROOT / 'frontend' / 'src' / 'CaptionsPro.tsx').read_text(encoding='utf-8')
    block = src.split('export const CAPTION_PRESETS')[1].split('= [', 1)[1].split('...EXTRA_CAPTION_PRESETS')[0]
    js = re.sub(r'([{,]\s*)([A-Za-z_]+)\s*:', r'\1"\2":', block.replace("'", '"'))
    return json.loads('[' + re.sub(r',\s*$', '', js.strip()) + ']')

LEGACY_NAMES = ['Classic', 'YouTube box', 'Viral bold', 'Karaoke', 'Neon', 'Cinematic', 'Documentary', 'Underline', 'Arabic modern',
                'Bold outline', 'Yellow box', 'Red highlight', 'Green karaoke', 'Blue glow', 'Handwritten', 'News lower third', 'Elegant serif',
                'Creator punch', 'Soft subtitle', 'Glass panel', 'Pastel pop', 'Cyber cyan', 'Clean white', 'Pulse', 'TikTok word pop',
                'Reels minimal', 'Yellow marker', 'Blue subtitle bar', 'Creator highlight', 'Arabic clean', 'Neon lime karaoke']
cap = json.loads((ROOT / 'frontend' / 'src' / 'captionStyles.json').read_text(encoding='utf-8'))
old = legacy_caption_presets()
styles = old + cap['styles']
names = [s['name'] for s in styles]
check(f'{len(styles)} caption styles (>= 60): the 31 RC8 styles keep their names and order', len(styles) >= 60 and [s['name'] for s in old] == LEGACY_NAMES)
check('caption style names are unique and every style has a picker group',
      len(set(names)) == len(names) and set(cap['legacy_groups']) == set(LEGACY_NAMES)
      and all(s['group'] in cap['groups'] for s in cap['styles']) and set(cap['legacy_groups'].values()) <= set(cap['groups'])
      and cap['groups'] == ['Social', 'Cinematic', 'Karaoke', 'Fun', 'Minimal', 'Arabic'])

entrance = re.findall(r"'([a-z-]+)'", (ROOT / 'frontend' / 'src' / 'CaptionsPro.tsx').read_text(encoding='utf-8').split('const ENTRANCE = [')[1].split(']')[0])
HEX = re.compile(r'^#[0-9A-Fa-f]{6}$')
ENUMS = {'case': {'none', 'upper', 'lower', 'title'}, 'background': {'none', 'box'}, 'split': {'full', 'phrases'},
         'karaoke_style': {'fill', 'color', 'box', 'underline', 'pop', 'glow'}, 'caption_animation': set(entrance),
         'exit_animation': {'none', 'fade', 'pop'}, 'loop': {'none', 'pulse'}, 'position': {'top', 'middle', 'bottom'},
         'halign': {'left', 'center', 'right'}}
NUM = {'size': (16, 120), 'outline_width': (0, 12), 'shadow': (0, 10), 'shadow_opacity': (0, 100), 'box_opacity': (0, 100),
       'box_padding': (0, 40), 'phrase_words': (1, 8), 'caption_animation_ms': (100, 10000), 'exit_ms': (50, 3000),
       'spacing': (-5, 40), 'offset_y': (-40, 40), 'max_width': (30, 100)}
BOOL = {'bold', 'italic', 'underline', 'karaoke'}
COLORS = {'color', 'outline_color', 'shadow_color', 'box_color', 'highlight_color'}
problems = []
for s in styles:
    v = s['values']
    for k, val in v.items():
        ok = (k == 'family' and val in ALL_FAMILIES) or (k in ENUMS and val in ENUMS[k]) or (k in BOOL and isinstance(val, bool)) \
            or (k in COLORS and HEX.match(val)) or (k in NUM and NUM[k][0] <= val <= NUM[k][1])
        if not ok:
            problems.append(f"{s['name']}.{k}={val!r}")
check('every caption style uses only renderer-supported properties, bundled fonts and valid values', not problems)

bad_ass = []
for i, s in enumerate(styles):
    v = s['values']
    text = 'مرحبا بكم في هذا العالم' if s['name'].startswith('Arabic') else 'Hello there caption world'
    out = write_ass_file(f'style{i}', text, 3000, {**v, 'captions_enabled': True}, 1920, 1080, out_path=str(t / f'style{i}.ass'))
    ass = pathlib.Path(out).read_text(encoding='utf-8')
    style = [ln for ln in ass.splitlines() if ln.startswith('Style: Default,')]
    f = style[0][len('Style: '):].split(',') if style else []
    ok = len(f) == 23 and f[1] == v['family'] and f[15] == ('3' if v.get('background') == 'box' else '1') \
        and all(re.match(r'^&H[0-9A-F]{8}$', c) for c in f[3:7]) and ass.count('Dialogue:') >= 1
    if v.get('karaoke'):
        ok = ok and _hex_to_ass_color(v['highlight_color'], alpha=0) in ass
    if v.get('background') == 'box':
        ok = ok and f[5].endswith(_hex_to_ass_color(v['box_color'])[-6:])
    if not ok:
        bad_ass.append(s['name'])
check(f'all {len(styles)} caption styles map to a valid ASS style (font, colours, box border style, highlight)', not bad_ass)


# ------------------------------------------------------------------ API + real FFmpeg renders
def render(c, sid) -> np.ndarray:
    jid = c.post(f'/api/scenes/{sid}/render').json()['job_id']
    for _ in range(900):
        j = c.get(f'/api/jobs/{jid}').json()
        if j['status'] in ('succeeded', 'failed'):
            break
        time.sleep(0.2)
    assert j['status'] == 'succeeded', j
    vid = t / f'{sid}.mp4'; vid.write_bytes(c.get(f"/api/assets/{j['artifact_asset_id']}/stream").content)
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-ss', '1.2', '-i', str(vid), '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])
    return np.frombuffer(raw, np.uint8).reshape(-1, 1920 if len(raw) == 1920 * 1080 * 3 else 1280, 3)

with TestClient(app) as c:
    r = c.get('/api/stickers').json()
    check('GET /api/stickers lists the library with categories and attribution (no file paths)',
          len(r['items']) == len(items) and r['categories'] == CATS and 'file' not in r['items'][0] and 'Twemoji' in r['attribution']['twemoji'])
    img = c.get('/api/stickers/heart-eyes/image')
    check('a sticker image is served as PNG for picker thumbnails', img.status_code == 200 and img.headers['content-type'] == 'image/png' and img.content[:4] == b'\x89PNG')
    check('unknown stickers and path tricks are rejected', c.get('/api/stickers/nope/image').status_code == 404
          and c.get('/api/stickers/..%2Flibrary.json/image').status_code == 404)

    p = c.post('/api/projects', json={'title': 'Library', 'aspect': '16:9', 'fps': 25}).json(); pid = p['id']
    src = t / 'bg.png'; Image.new('RGB', (640, 360), BG).save(src)
    bg = c.post(f'/api/assets/upload?project_id={pid}', files={'file': ('bg.png', src.read_bytes(), 'image/png')}).json()
    a1 = c.post(f'/api/projects/{pid}/stickers/fire')
    a2 = c.post(f'/api/projects/{pid}/stickers/fire')
    check('importing a sticker adds a PNG to the Media Pool with its licence, and re-uses it on the next import',
          a1.status_code == 200 and a1.json()['id'] == a2.json()['id'] and a1.json()['original_filename'] == 'sticker-fire.png'
          and 'CC-BY 4.0' in a1.json()['license_note'] and a1.json()['width'] == 320)
    check('importing an unknown sticker or into an unknown project fails cleanly',
          c.post(f'/api/projects/{pid}/stickers/nope').status_code == 404 and c.post('/api/projects/nope/stickers/fire').status_code == 404)
    chosen = ['fire', 'party', 'subscribe-pill', 'speech-bubble-round', 'bold-arrow-right', 'breaking-news']
    assets = [c.post(f'/api/projects/{pid}/stickers/{s}').json() for s in chosen]
    check('graphic stickers import with the SceneForge licence note', all(a['license_note'] for a in assets) and 'GPL' in assets[2]['license_note'])
    # An RC8 sticker was drawn in the browser and uploaded as sticker-<name>.png: it must keep working.
    rc8 = Image.new('RGBA', (512, 512), (0, 0, 0, 0)); Image.Image.paste(rc8, (255, 60, 90, 255), (156, 156, 356, 356))
    rc8p = t / 'sticker-heart.png'; rc8.save(rc8p)
    old_asset = c.post(f'/api/assets/upload?project_id={pid}', files={'file': ('sticker-heart.png', rc8p.read_bytes(), 'image/png')}).json()
    sid = c.get(f'/api/projects/{pid}').json()['scenes'][0]['id']
    c.post(f'/api/scenes/{sid}/shots', json={'asset_id': bg['id']})
    spots = [(15, 25), (38, 25), (62, 25), (85, 25), (15, 70), (50, 70), (85, 70)]
    ovs = [{'id': f'st{i}', 'asset_id': a['id'], 'kind': 'sticker', 'x': x, 'y': y, 'width': 14, 'border': 0, 'radius': 0, 'shadow': 0,
            'anim_in': 'none', 'anim_out': 'none'} for i, (a, (x, y)) in enumerate(zip(assets + [old_asset], spots))]
    pr = c.patch(f'/api/scenes/{sid}', json={'timing_mode': 'fixed', 'requested_duration_ms': 2000, 'overlays': ovs, 'subtitle_text': '',
                                            'font': {'captions_enabled': False}})
    check('six library stickers and an RC8 sticker are placed as overlays', pr.status_code == 200 and len(pr.json()['overlays_json']) == 7)
    frame = render(c, sid)
    h, w = frame.shape[:2]
    changed = []
    for x, y in spots:
        cx, cy = int(w * x / 100), int(h * y / 100)
        patch = frame[cy - 30:cy + 30, cx - 30:cx + 30].reshape(-1, 3).astype(int)
        changed.append((np.abs(patch - BG).sum(1) > 90).mean())
    corner = frame[5:40, 900:1000].reshape(-1, 3).astype(int)  # empty area keeps the background
    check(f'every sticker overlay renders over the background (real FFmpeg; coverage {[float(round(v, 2)) for v in changed]})', min(changed) > 0.2 and (np.abs(corner - BG).sum(1) < 20).mean() > 0.95)

    # five new caption styles, each rendered through the real scene pipeline
    new = {s['name']: s for s in cap['styles']}
    picks = ['Comic pop', 'Cinematic letterbox', 'Karaoke pink box', 'Neon green', 'Arabic Lalezar bold']
    results = {}
    for name in picks:
        sc = c.post(f'/api/projects/{pid}/scenes', json={}).json()
        c.post(f"/api/scenes/{sc['id']}/shots", json={'asset_id': bg['id']})
        text = 'مرحبا بكم في هذا العالم الجميل' if name.startswith('Arabic') else 'Captions look great in this style'
        r = c.patch(f"/api/scenes/{sc['id']}", json={'timing_mode': 'fixed', 'requested_duration_ms': 2400, 'subtitle_text': text,
                                                    'font': {**new[name]['values'], 'captions_enabled': True, 'typewriter': False}})
        assert r.status_code == 200, r.text
        fr = render(c, sc['id'])
        lower = fr[fr.shape[0] // 2:].reshape(-1, 3).astype(int)
        results[name] = (np.abs(lower - BG).sum(1) > 120).mean()
        if name == 'Cinematic letterbox':   # opaque black box behind the text
            results[name + ' box'] = (lower.sum(1) < 25).mean()
        if name == 'Comic pop':             # yellow text
            results[name + ' yellow'] = ((lower[:, 0] > 200) & (lower[:, 1] > 180) & (lower[:, 2] < 90)).mean()
    check(f'five new caption styles render captions through real FFmpeg ({ {k: float(round(v, 3)) for k, v in results.items()} })',
          all(results[nm] > 0.001 for nm in picks) and results['Cinematic letterbox box'] > 0.01 and results['Comic pop yellow'] > 0.0003)

print(f'{n} library checks passed')
