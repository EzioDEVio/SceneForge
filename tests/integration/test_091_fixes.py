"""0.9.1: "video inside text" titles, safe clean-up after a cancelled video cutout, quieter hang log."""
import os, pathlib, subprocess, sys, tempfile, time
import numpy as np
ROOT = pathlib.Path(__file__).resolve().parents[2]
tmp = tempfile.TemporaryDirectory(); os.environ['SCENEFORGE_DATA_DIR'] = tmp.name
sys.path.insert(0, str(ROOT / 'backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import SessionLocal
from app.db.models import Project
from app.render.textured_text import render_knockout_card, TexturedTextError
from app.render import video_cutout
n = 0
def check(name, ok):
    global n
    assert ok, name
    n += 1; print('PASS ' + name, flush=True)
t = pathlib.Path(tmp.name)

# ---- the card itself ------------------------------------------------------------------------
card = np.asarray(render_knockout_card('NORWAY', 640, 360, 'Anton', 260, 50, 50, '#E10600', 100, 6, '#FFFFFF'))
check('the card is frame-sized RGBA', card.shape == (360, 640, 4))
check('outside the letters the card is solid red', tuple(card[10, 10]) == (225, 6, 0, 255))
check('inside the letters the card is see-through', (card[..., 3] == 0).sum() > 640 * 360 * 0.05)
check('the outline is solid white', ((card[..., 0] > 240) & (card[..., 1] > 240) & (card[..., 3] == 255)).sum() > 200)
half = np.asarray(render_knockout_card('A', 320, 180, opacity=50, outline=0))
check('card opacity is respected outside the letters', abs(int(half[5, 5, 3]) - 128) <= 1)
bad = 0
for kw in ({'text': ''}, {'text': 'x', 'size': 5}, {'text': 'x', 'outline': 99}, {'text': 'x', 'background': 'red'}):
    try: render_knockout_card(kw.pop('text'), 320, 180, **kw)
    except TexturedTextError: bad += 1
check('bad card settings give clear errors', bad == 4)
wide = np.asarray(render_knockout_card('THIS IS TEST OF THIS RELEASE', 1920, 1080, 'Anton', 600, 50, 35, '#E10600', 100, 2, '#FFFFFF'))
cols = np.where((wide[..., 3] < 255).any(0))[0]
check('0.9.2: a long title at a big size shrinks to fit inside the frame', cols.min() > 40 and cols.max() < 1880)
check('Arabic text is accepted', np.asarray(render_knockout_card('بغداد', 320, 180)).shape == (180, 320, 4))

# ---- endpoint + render ----------------------------------------------------------------------
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=0x00FF00:s=320x180:d=2', '-pix_fmt', 'yuv420p', str(t / 'green.mp4')], check=True)
with TestClient(app) as c:
    pid = c.post('/api/projects', json={'title': '091', 'aspect': '16:9', 'fps': 25}).json()['id']
    with SessionLocal() as db:
        row = db.get(Project, pid); row.width, row.height = 320, 180; db.commit()
    a = c.post(f'/api/assets/upload?project_id={pid}', files={'file': ('green.mp4', (t / 'green.mp4').read_bytes(), 'video/mp4')}).json()
    sid = c.get(f'/api/projects/{pid}').json()['scenes'][0]['id']
    c.post(f'/api/scenes/{sid}/shots', json={'asset_id': a['id']})
    r = c.post(f'/api/scenes/{sid}/knockout-title', json={'text': 'HI', 'font_size': 500, 'outline': 0})
    ov = r.json()['scene']['overlays_json'][-1] if r.status_code == 200 else {}
    check('the title is added as a full-screen overlay', r.status_code == 200 and ov.get('width') == 100 and ov.get('x') == 50 and ov.get('y') == 50)
    check('bad requests are refused', c.post(f'/api/scenes/{sid}/knockout-title', json={'text': ''}).status_code == 422
          and c.post(f'/api/scenes/{sid}/knockout-title', json={'text': 'x', 'background': 'red'}).status_code == 422
          and c.post(f'/api/scenes/nope/knockout-title', json={'text': 'x'}).status_code == 404)
    j = c.post(f'/api/scenes/{sid}/render').json()['job_id']
    for _ in range(600):
        s = c.get(f'/api/jobs/{j}').json()
        if s['status'] in ('succeeded', 'failed'): break
        time.sleep(0.2)
    check('a scene with a video-inside-text title renders', s['status'] == 'succeeded')
    vid = t / 'out.mp4'; vid.write_bytes(c.get(f"/api/assets/{c.get(f'/api/scenes/{sid}').json()['rendered_asset_id']}/stream").content)
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-ss', '1', '-i', str(vid), '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])
    f = np.frombuffer(raw, np.uint8).reshape(180, 320, 3).astype(int)
    green = ((f[..., 1] > 180) & (f[..., 0] < 90)).sum()
    red = ((f[..., 0] > 180) & (f[..., 1] < 60)).sum()
    check('the video shows through the letters and the card covers the rest', green > 1500 and red > 20000 and f[5, 5, 0] > 180)

# ---- safe clean-up --------------------------------------------------------------------------
p = t / 'x.tmp'; p.write_text('x')
video_cutout.safe_unlink(p); video_cutout.safe_unlink(p); video_cutout.safe_unlink(None)
check('safe_unlink deletes, and never raises for missing files', not p.exists())
calls = []
real = pathlib.Path.unlink
def flaky(self, missing_ok=False):
    calls.append(1)
    if len(calls) < 3:
        raise PermissionError(32, 'The process cannot access the file because it is being used by another process')
    return real(self, missing_ok=missing_ok)
p.write_text('x'); pathlib.Path.unlink = flaky
try:
    video_cutout.safe_unlink(p)
finally:
    pathlib.Path.unlink = real
check('safe_unlink retries while Windows still holds the file', not p.exists() and len(calls) == 3)
p.write_text('x'); pathlib.Path.unlink = lambda self, missing_ok=False: (_ for _ in ()).throw(PermissionError(32, 'busy'))
try:
    video_cutout.safe_unlink(p); ok = True
except Exception:
    ok = False
finally:
    pathlib.Path.unlink = real
check('a file that stays locked is left behind without crashing the job', ok)

# ---- hang watchdog ignores long streams -----------------------------------------------------
src = (ROOT / 'backend' / 'desktop_entry.py').read_text()
check('the hang watchdog skips event and media streams', 'path.endswith("/events")' in src and '"/preview-media" in path' in src)
print(f'{n} checks passed')
