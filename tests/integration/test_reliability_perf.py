"""Reliability, performance and stress (0.9.4-beta.7). Disposable data, generated media, no
providers. Prints timings so regressions are visible in CI logs.

1. Status endpoints stay quick while an engine port is a "black hole" (accepts connections,
   never answers): the editor polls these every few seconds and must never freeze.
2. 400 mixed requests from 16 concurrent clients: all succeed; p95 latency is reported/bounded.
3. A 24-part project where every part uses a different effect combination (including the
   new trending effects) renders and exports; exact duration; per-part timings reported.
4. 30 repeated part renders: the backend's memory does not keep growing.
"""
import concurrent.futures, io, os, pathlib, socket, statistics, sys, tempfile, threading, time

ROOT = pathlib.Path(__file__).resolve().parents[2]
temp = tempfile.TemporaryDirectory(prefix='sf-rel-')
os.environ['SCENEFORGE_DATA_DIR'] = temp.name
os.environ['SCENEFORGE_NATIVE_ENGINES'] = str(pathlib.Path(temp.name) / 'engines')
sys.path.insert(0, str(ROOT / 'backend'))
import psutil
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import SessionLocal
from app.db.models import Project
from app.render.ffmpeg_utils import probe

n = 0


def check(name, ok):
    global n
    assert ok, name; n += 1; print('PASS ' + name, flush=True)


def hole(port):
    """Accept connections on a port and never answer (a hung engine)."""
    srv = socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); srv.bind(('127.0.0.1', port)); srv.listen(64)
    keep = []
    def run():
        while True:
            try: conn, _ = srv.accept(); keep.append(conn)
            except OSError: return
    threading.Thread(target=run, daemon=True).start()
    return srv


def wait_job(c, jid, limit=600):
    for _ in range(limit * 10):
        j = c.get('/api/jobs/' + jid).json()
        if j['status'] in ('succeeded', 'failed', 'cancelled'): return j
        time.sleep(.1)
    return j


with TestClient(app) as c:
    # ---- 1. hung engines must not freeze the status endpoints -------------------------
    holes = [hole(8881), hole(7860)]
    try:
        for path in ('/api/local-ai/setup', '/api/local-speech/chatterbox/status', '/api/local-speech/kokoro_builtin/status',
                     '/api/local-speech/voicebox/status', '/api/health'):
            t0 = time.monotonic(); r = c.get(path); dt = time.monotonic() - t0
            check(f'{path} answers in {dt:.1f}s while engines hang (limit 3 s)', r.status_code == 200 and dt < 3)
    finally:
        for h in holes: h.close()

    # ---- 2. concurrent mixed load -----------------------------------------------------
    p = c.post('/api/projects', json={'title': 'Reliability', 'aspect': '16:9', 'fps': 25}).json(); pid = p['id']
    with SessionLocal() as db:
        pr = db.get(Project, pid); pr.width = 320; pr.height = 180; db.commit()
    paths = ['/api/projects', f'/api/projects/{pid}', '/api/providers', '/api/local-ai/setup', '/api/health',
             '/api/local-speech/kokoro_builtin/status', '/api/effects/schema', '/api/look-presets']
    lat = []
    def hit(i):
        t0 = time.monotonic(); r = c.get(paths[i % len(paths)]); lat.append(time.monotonic() - t0); return r.status_code
    t0 = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        codes = list(pool.map(hit, range(400)))
    total = time.monotonic() - t0
    p95 = statistics.quantiles(lat, n=20)[18]
    check(f'400 requests from 16 clients all succeed ({total:.1f}s total, p95 {p95 * 1000:.0f} ms)', all(code == 200 for code in codes) and p95 < 5)

    # ---- 3. 24 parts, each a different effect combination ------------------------------
    combos = [{}, {'pulse': {'amount': 60, 'bpm': 120}}, {'flash': {'amount': 80, 'mode': 'both', 'bpm': 100}}, {'trails': {'amount': 70}},
              {'mirror': {'mode': 'left'}}, {'mirror': {'mode': 'quad'}, 'pulse': {'amount': 40, 'bpm': 90}},
              {'shake': {'amount': 50, 'speed': 50, 'impact': True}}, {'wiggle': {'amount': 40, 'speed': 40, 'size': 50}},
              {'leak': {'amount': 60, 'speed': 40, 'color': 'warm'}}, {'flare': {'x': 70, 'y': 20, 'color': '#FFB060', 'blend': 'screen', 'amount': 70, 'drift': 30}},
              {'vignette': {'amount': 60}, 'letterbox': {'amount': 40}}, {'sharpen': {'amount': 50}, 'trails': {'amount': 30}},
              {'glitch': {'strength': 60, 'speed': 1.0, 'block': 'medium'}}, {'adjust': {'exposure': 10, 'contrast': 15, 'saturation': 20}},
              {'film': {'tone': 'sepia'}}, {'tone': {'shadow': '#203050', 'highlight': '#F0C080', 'amount': 60, 'balance': 0}},
              {'mirror': {'mode': 'top'}, 'flash': {'amount': 60, 'mode': 'intro', 'bpm': 120}},
              {'pulse': {'amount': 100, 'bpm': 200}, 'shake': {'amount': 30, 'speed': 70, 'impact': False}, 'intro': {'style': 'swipe_up', 'seconds': 0.4}, 'colorsplit': {'amount': 60, 'mode': 'beats', 'bpm': 120}},
              {'trails': {'amount': 100}, 'leak': {'amount': 40, 'speed': 60, 'color': 'rainbow'}},
              {'mirror': {'mode': 'bottom'}, 'vignette': {'amount': 80}}, {'flash': {'amount': 100, 'mode': 'beats', 'bpm': 200}, 'beforeafter': {'before': 'bw', 'start': 10, 'seconds': 0.5}, 'cineopen': {'amount': 60, 'zoom': 'out', 'fade': 'both', 'seconds': 0.3}, 'speedblur': {'amount': 40, 'direction': 'vertical', 'when': 'start'}},
              {'mirror': {'mode': 'right'}, 'wiggle': {'amount': 30, 'speed': 70, 'size': 30}},
              {'pulse': {'amount': 50, 'bpm': 60}, 'flash': {'amount': 50, 'mode': 'beats', 'bpm': 60}, 'trails': {'amount': 50}, 'mirror': {'mode': 'quad'}},
              {'fx_bypass': ['mirror'], 'mirror': {'mode': 'left'}, 'pulse': {'amount': 30, 'bpm': 120}}]
    clip = c.post('/api/assets/upload?project_id=' + pid, files={'file': ('clip.mp4', (ROOT / 'examples/fixture_assets/clip1.mp4').read_bytes(), 'video/mp4')}).json()
    buf = io.BytesIO(); Image.new('RGB', (320, 180), '#507090').save(buf, format='PNG')
    pic = c.post('/api/assets/upload?project_id=' + pid, files={'file': ('pic.png', buf.getvalue(), 'image/png')}).json()
    scenes = c.get(f'/api/projects/{pid}').json()['scenes']
    while len(scenes) < len(combos):
        c.post(f'/api/projects/{pid}/scenes', json={}); scenes = c.get(f'/api/projects/{pid}').json()['scenes']
    refused = []
    for i, (scene, look) in enumerate(zip(scenes, combos)):
        c.post(f"/api/scenes/{scene['id']}/shots", json={'asset_id': (clip if i % 2 else pic)['id']})
        r = c.patch(f"/api/scenes/{scene['id']}", json={'timing_mode': 'fixed', 'requested_duration_ms': 1000, 'lead_ms': 0, 'trail_ms': 0, 'look': look})
        if r.status_code != 200: refused.append((i, r.text[:200]))
    check('all 24 effect combinations are accepted' + (f': {refused}' if refused else ''), not refused)
    times = []
    for i, scene in enumerate(scenes[:len(combos)]):
        t0 = time.monotonic(); j = wait_job(c, c.post(f"/api/scenes/{scene['id']}/render").json()['job_id'])
        times.append(time.monotonic() - t0)
        assert j['status'] == 'succeeded', (i, combos[i], j.get('error'))
    check(f'24 parts render (mean {statistics.mean(times):.2f}s, slowest {max(times):.2f}s at 320x180, 1 s each)', True)
    t0 = time.monotonic(); job = c.post(f'/api/projects/{pid}/export?skip_empty=true', json={'settings': {}}).json()
    j = wait_job(c, job['job_id'], limit=900)
    check(f'the 24-part project exports ({time.monotonic() - t0:.1f}s)', j['status'] == 'succeeded')
    out = pathlib.Path(temp.name) / 'export.mp4'; out.write_bytes(c.get('/api/assets/' + j['artifact_asset_id'] + '/stream').content)
    dur = probe(str(out)).duration_ms / 1000
    check(f'export length matches the 24 parts ({dur:.2f}s for 24 s)', abs(dur - 24) < .5)

    # ---- 4. memory does not keep growing over repeated renders -------------------------
    me = psutil.Process()
    rss = []
    for k in range(30):
        wait_job(c, c.post(f"/api/scenes/{scenes[22]['id']}/render").json()['job_id'])
        if k in (4, 29): rss.append(me.memory_info().rss / 1e6)
    check(f'30 more renders: backend memory {rss[0]:.0f} MB -> {rss[1]:.0f} MB (growth under 120 MB)', rss[1] - rss[0] < 120)

print(f'{n} reliability and performance checks passed')
