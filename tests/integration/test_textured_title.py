"""Textured text titles: procedural presets, a Media Pool image as texture, and the prompt path
(mocked image provider, no paid call). Rendered through the real overlay pipeline."""
import os, pathlib, subprocess, sys, tempfile, time
import numpy as np
from unittest.mock import patch
from PIL import Image
ROOT = pathlib.Path(__file__).resolve().parents[2]
tmp = tempfile.TemporaryDirectory(); os.environ['SCENEFORGE_DATA_DIR'] = tmp.name
sys.path.insert(0, str(ROOT / 'backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.render.textured_text import PRESETS, render_textured_text, texture_preset
n = 0
def check(name, ok):
    global n
    assert ok, name
    n += 1; print('PASS ' + name, flush=True)
t = pathlib.Path(tmp.name)
for name in PRESETS:
    tex = texture_preset(name, 256, 128)
    arr = np.asarray(tex)
    assert tex.size == (256, 128) and arr.std() > 3, name
check(f'all {len(PRESETS)} procedural textures render with visible detail', True)
img = render_textured_text('LAVA', 'lava', 'Anton', 120)
a = np.asarray(img)
check('textured text is RGBA with transparent background and opaque letters', img.mode == 'RGBA' and a[0, 0, 3] == 0 and (a[..., 3] > 200).mean() > 0.05)
inside = a[a[..., 3] > 200][:, :3]
check('letters are filled with the texture (many colours, not a flat fill)', len({tuple(x // 16) for x in inside[::7]}) > 8)
arabic = render_textured_text('مرحبا', 'gold', 'Noto Naskh Arabic', 120)
check('Arabic text renders with the Arabic font', np.asarray(arabic)[..., 3].max() > 200)
with TestClient(app) as c:
    p = c.post('/api/projects', json={'title': 'Textured', 'aspect': '16:9', 'fps': 25}).json(); pid = p['id']
    src = t / 'bg.png'; Image.new('RGB', (640, 360), (20, 30, 60)).save(src)
    bg = c.post(f'/api/assets/upload?project_id={pid}', files={'file': ('bg.png', src.read_bytes(), 'image/png')}).json()
    sid = c.get(f'/api/projects/{pid}').json()['scenes'][0]['id']
    c.post(f'/api/scenes/{sid}/shots', json={'asset_id': bg['id']})
    c.patch(f'/api/scenes/{sid}', json={'timing_mode': 'fixed', 'requested_duration_ms': 1500})
    r = c.post(f'/api/scenes/{sid}/textured-title', json={'text': 'NEON', 'texture': {'preset': 'neon'}, 'glow': 60, 'y': 50})
    check('a textured title is added to the scene as a sticker overlay', r.status_code == 200 and r.json()['overlay']['kind'] == 'sticker' and r.json()['asset']['mime'] == 'image/png')
    texfile = t / 'stripes.png'; Image.fromarray(np.tile(np.array([[255, 0, 0], [0, 255, 0]], np.uint8)[:, None, :].repeat(8, 0), (8, 512, 1))[:256]).save(texfile)
    tex = c.post(f'/api/assets/upload?project_id={pid}', files={'file': ('stripes.png', texfile.read_bytes(), 'image/png')}).json()
    r2 = c.post(f'/api/scenes/{sid}/textured-title', json={'text': 'POOL', 'texture': {'asset_id': tex['id']}, 'y': 80})
    check('a Media Pool image can be the texture', r2.status_code == 200)
    bad = [c.post(f'/api/scenes/{sid}/textured-title', json={'text': 'X', 'texture': {}}).status_code,
           c.post(f'/api/scenes/{sid}/textured-title', json={'text': 'X', 'texture': {'preset': 'nope'}}).status_code,
           c.post(f'/api/scenes/{sid}/textured-title', json={'text': 'X', 'texture': {'preset': 'lava', 'prompt': 'y'}}).status_code]
    check('texture must be exactly one valid choice', bad == [400, 400, 400])
    fake = Image.new('RGB', (512, 512), (240, 120, 10)); fp = t / 'gen.png'; fake.save(fp)
    import app.api.images as images_api
    def fake_generate(scene_id, req, db):
        from app.db.models import Asset
        assert 'no text' in req.prompt and 'molten' in req.prompt
        return db.get(Asset, tex['id'])
    with patch.object(images_api, 'generate_image_for_scene', side_effect=fake_generate):
        r3 = c.post(f'/api/scenes/{sid}/textured-title', json={'text': 'AI', 'texture': {'prompt': 'molten copper'}, 'y': 20})
    check('a prompt generates the texture through the configured image engine (mocked here)', r3.status_code == 200 and r3.json()['texture_asset'] is not None)
    jid = c.post(f'/api/scenes/{sid}/render').json()['job_id']
    for _ in range(600):
        j = c.get(f'/api/jobs/{jid}').json()
        if j['status'] in ('succeeded', 'failed'): break
        time.sleep(0.2)
    check('the scene with textured titles renders', j['status'] == 'succeeded')
    vid = t / 'out.mp4'; vid.write_bytes(c.get(f"/api/assets/{j['artifact_asset_id']}/stream").content)
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-ss', '1.0', '-i', str(vid), '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])
    frame = np.frombuffer(raw, np.uint8).reshape(-1, 3)
    check('the rendered frame shows the titles over the background', (np.abs(frame.astype(int) - [20, 30, 60]).sum(1) > 120).mean() > 0.01)
print(f'{n} textured-title checks passed')
