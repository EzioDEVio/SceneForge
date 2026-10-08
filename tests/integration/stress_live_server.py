"""Live-server stress: a heavy project plus renders, uploads and an export while a
prober measures how long ordinary requests take. Uses a real uvicorn process (the
event-loop blocking that freezes the editor only shows up over real HTTP).

Run:  python tests/integration/stress_live_server.py [scenes=30] [port=8400]
Prints latency percentiles per phase and exits non-zero if a request stalls past
the budget or any render/export fails. Disposable data folder; no AI providers.
"""
from __future__ import annotations
import json, os, pathlib, statistics, subprocess, sys, tempfile, threading, time
import requests

root = pathlib.Path(__file__).resolve().parents[2]
N = int(sys.argv[1]) if len(sys.argv) > 1 else 30
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8400
BASE = f"http://127.0.0.1:{PORT}/api"
STALL_BUDGET_S = float(os.environ.get("SF_STALL_BUDGET", "2.0"))
data = tempfile.mkdtemp(prefix="sf-live-stress-")
media = pathlib.Path(data) / "_fixtures"; media.mkdir()


def ff(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


# Fixtures: 3 pictures, 2 videos with sound, 1 music bed, 1 voice take, 1 large upload file.
for i, c in enumerate(["0x3b6e8f", "0xb5651d", "0x2e7d32"]):
    ff("-f", "lavfi", "-i", f"color=c={c}:s=1280x720", "-frames:v", "1", str(media / f"pic{i}.png"))
for i, c in enumerate(["teal", "purple"]):
    ff("-f", "lavfi", "-i", f"testsrc2=s=640x360:r=25:d=6", "-f", "lavfi", "-i", f"sine=frequency={440+i*220}:duration=6",
       "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(media / f"vid{i}.mp4"))
ff("-f", "lavfi", "-i", "sine=frequency=220:duration=40", "-ac", "2", str(media / "music.wav"))
ff("-f", "lavfi", "-i", "sine=frequency=300:duration=2.5", "-af", "volume=0.6,tremolo=f=6:d=0.8", str(media / "voice.wav"))
ff("-f", "lavfi", "-i", "testsrc2=s=1920x1080:r=30:d=20", "-c:v", "libx264", "-preset", "ultrafast", "-b:v", "6M", str(media / "big.mp4"))

server = subprocess.Popen(([sys.executable, os.environ["SF_SERVER_SCRIPT"]] if os.environ.get("SF_SERVER_SCRIPT") else [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PORT)]),
                          cwd=root / "backend", env={**os.environ, "SCENEFORGE_DATA_DIR": data, "SF_PORT": str(PORT)},
                          stdout=subprocess.DEVNULL, stderr=open(pathlib.Path(data) / "server.log", "w"))
for _ in range(120):
    try:
        if requests.get(BASE + "/health", timeout=1).ok: break
    except requests.RequestException: pass
    time.sleep(.5)
else:
    sys.exit("server did not start")

S = requests.Session()
def call(method, path, **kw):
    r = S.request(method, BASE + path, timeout=300, **kw)
    if not r.ok: raise AssertionError(f"{method} {path} -> {r.status_code} {r.text[:300]}")
    return r.json() if r.content else None
def upload(pid, f):
    with open(f, "rb") as fh:
        return call("POST", f"/assets/upload?project_id={pid}", files={"file": (f.name, fh)})

def upload_voice(sid):
    with open(media / "voice.wav", "rb") as fh:
        return call("POST", f"/scenes/{sid}/voice-takes/upload", files={"file": ("voice.wav", fh)})

failures = []
try:
    t0 = time.time()
    p = call("POST", "/projects", json={"title": "Live stress", "aspect": "16:9", "fps": 25})
    pid = p["id"]
    while len(call("GET", f"/projects/{pid}")["scenes"]) < N:
        call("POST", f"/projects/{pid}/scenes", json={})
    scenes = call("GET", f"/projects/{pid}")["scenes"]
    pics = [upload(pid, media / f"pic{i}.png") for i in range(3)]
    vids = [upload(pid, media / f"vid{i}.mp4") for i in range(2)]
    music = upload(pid, media / "music.wav")
    stickers = [call("POST", f"/projects/{pid}/stickers/{s}") for s in ("grinning-face", "laughing")]
    effects = ["original", "warm", "sepia", "vhs", "glow", "glitch", "old_film", "noir", "cinematic", "dream", "halation", "tilt_shift", "chromatic_split", "film_grain", "golden_hour"]
    transitions = ["cut", "dissolve", "fade_through_black", "wipe_left", "slide", "circle_open", "film_burn", "pixelize"]
    for i, s in enumerate(scenes):
        asset = vids[i % 2] if i % 3 == 0 else pics[i % 3]
        call("POST", f"/scenes/{s['id']}/shots", json={"asset_id": asset["id"]})
        layers = [{"id": f"t{i}-{k}", "text": f"Title {i}.{k} عنوان", "x": 20 + 25 * k, "y": 15 + 20 * k, "size": 40 + 6 * k,
                   "color": "#FFFFFF", "start_ms": 200 * k, "end_ms": 2600 + 200 * k, "bold": k == 0} for k in range(3)]
        font = {"captions_enabled": True, "layers": layers}
        if i % 3 == 1: font.update(typewriter=True, typewriter_sound=True)
        if i % 4 == 2: font.update(karaoke=True)
        call("PATCH", f"/scenes/{s['id']}", json={
            "title": f"Scene {i+1}", "subtitle_text": f"Caption for scene {i+1} — نص الترجمة", "spoken_text": f"Scene {i+1}",
            "timing_mode": "fixed", "requested_duration_ms": 3000, "effect_preset": effects[i % len(effects)], "effect_intensity": 80,
            "transition_in": {"type": transitions[i % len(transitions)], "duration_ms": 300 if i % len(transitions) else 0},
            "font": font,
            "overlays": [{"asset_id": stickers[k]["id"], "kind": "sticker", "x": 15 + 60 * k, "y": 20, "width": 12, "start_ms": 0, "end_ms": 2500} for k in range(2)]
                        + ([{"asset_id": vids[1]["id"], "kind": "media", "x": 75, "y": 70, "width": 28, "start_ms": 0, "end_ms": 3000}] if i % 3 == 2 else []),
            "look": ({"film": {"scratches": 60, "dust": 50, "flicker": 40, "weave": 35, "sound": 30, "fps": 18, "tone": "bw"}} if i % 4 == 0 else
                     {"adjust": {"exposure": 20, "contrast": 15, "saturation": -10}} if i % 4 == 1 else {}),
        })
        # Creative titles stack on top of the stickers (they add their own overlay layer).
        if i % 5 == 0: call("POST", f"/scenes/{s['id']}/textured-title", json={"text": f"LAVA {i}", "texture": {"preset": ["lava", "gold", "neon", "chrome"][i % 4]}, "glow": 30})
        if i % 5 == 3: call("POST", f"/scenes/{s['id']}/knockout-title", json={"text": f"SCENE {i}", "font_size": 200})
        if i % 2 == 0: upload_voice(s["id"])
    call("PATCH", f"/projects/{pid}", json={"finishing": {"audio_clips": [
        {"id": f"m{k}", "asset_id": music["id"], "name": f"Music {k}", "start_ms": k * 9000, "source_in_ms": 0, "source_out_ms": 8000,
         "volume": 70, "fade_in_ms": 300, "fade_out_ms": 300, "mute": False} for k in range(4)]}})
    print(f"built {N}-scene project in {time.time()-t0:.1f}s", flush=True)

    # Prober: the requests the editor makes constantly.
    lat = {}; phase = ["idle"]; stop = threading.Event(); probe_errors = []
    def prober():
        sess = requests.Session(); k = 0
        while not stop.is_set():
            k += 1
            for name, fn in (("open project", lambda: sess.get(f"{BASE}/projects/{pid}", timeout=60)),
                             ("save scene", lambda: sess.patch(f"{BASE}/scenes/{scenes[k % N]['id']}", json={"title": f"Scene {k % N + 1}"}, timeout=60)),
                             ("health", lambda: sess.get(f"{BASE}/health", timeout=60))):
                a = time.perf_counter()
                try:
                    r = fn()
                    if not r.ok: probe_errors.append(f"{name} {r.status_code}")
                except requests.RequestException as e:
                    probe_errors.append(f"{name} {type(e).__name__}")
                lat.setdefault((phase[0], name), []).append(time.perf_counter() - a)
            time.sleep(.15)
    th = threading.Thread(target=prober, daemon=True); th.start()
    time.sleep(3)

    def wait_job(jid, limit=1800):
        end = time.time() + limit
        while time.time() < end:
            j = call("GET", f"/jobs/{jid}")
            if j["status"] in ("succeeded", "failed", "cancelled"): return j
            time.sleep(.5)
        return {"status": "timeout", "id": jid}

    phase[0] = "uploads"
    for _ in range(3): upload(pid, media / "big.mp4")
    phase[0] = "rendering scenes"
    t1 = time.time(); jobs = [call("POST", f"/scenes/{s['id']}/render")["job_id"] for s in scenes]
    results = [wait_job(j) for j in jobs]
    bad = [r for r in results if r["status"] != "succeeded"]
    print(f"rendered {N} scenes in {time.time()-t1:.0f}s, failed: {len(bad)}", flush=True)
    for r in bad[:3]: failures.append(f"scene render {r.get('status')}: {str(r.get('error'))[:200]}")
    peak = {"mb": 0}
    def mem_watch():
        while not stop.is_set():
            total = 0
            for d in pathlib.Path("/proc").glob("[0-9]*"):
                try:
                    if (d / "comm").read_text().strip() == "ffmpeg":
                        total += int(next(l for l in (d / "status").read_text().splitlines() if l.startswith("VmRSS")).split()[1]) // 1024
                except Exception: pass
            peak["mb"] = max(peak["mb"], total); time.sleep(.25)
    if pathlib.Path("/proc").exists(): threading.Thread(target=mem_watch, daemon=True).start()
    phase[0] = "uploads during export"
    t2 = time.time(); ej = call("POST", f"/projects/{pid}/export", json={"settings": {"quality": "draft"}})["job_id"]
    for _ in range(2): upload(pid, media / "big.mp4")
    er = wait_job(ej)
    print(f"export {er['status']} in {time.time()-t2:.0f}s; peak FFmpeg memory {peak['mb']} MB", flush=True)
    if er["status"] != "succeeded": failures.append(f"export {er['status']}: {str(er.get('error'))[:300]}")
    if os.environ.get("SF_FREE_EXPORT", "1") != "0":
        # Free timeline: every scene as an excerpt, some overlapping on two picture tracks, plus text boxes and music.
        phase[0] = "free-timeline export"
        clips, t = [], 0
        for i, sc in enumerate(scenes):
            clips.append({"id": f"f{i}", "scene_id": sc["id"], "start_ms": t, "source_in_ms": 0, "duration_ms": 3000, "track": 5 if i % 3 else 4})
            t += 2400 if i % 3 == 0 else 3000
        texts = [{"id": f"lt{k}", "kind": "text", "track": 1 + k % 2, "start_ms": k * 4000, "duration_ms": 2500, "text": f"Free text {k}", "x": 50, "y": 80, "size": 48, "color": "#FFFFFF"} for k in range(max(1, N // 3))]
        texts += [{"id": "lv0", "kind": "video", "asset_id": vids[0]["id"], "track": 3, "start_ms": 1000, "duration_ms": 5000, "x": 25, "y": 25, "width": 30},
                  {"id": "li0", "kind": "image", "asset_id": pics[1]["id"], "track": 3, "start_ms": 8000, "duration_ms": 4000, "x": 75, "y": 25, "width": 25}]
        call("PATCH", f"/projects/{pid}", json={"finishing": {"free_timeline": {"enabled": True, "clips": clips}, "layer_clips": texts}})
        peak["mb"] = 0; t3 = time.time()
        fj = call("POST", f"/projects/{pid}/export", json={"settings": {"quality": "draft"}})["job_id"]
        fr = wait_job(fj)
        print(f"free-timeline export {fr['status']} in {time.time()-t3:.0f}s; peak FFmpeg memory {peak['mb']} MB", flush=True)
        if fr["status"] != "succeeded": failures.append(f"free-timeline export {fr['status']}: {str(fr.get('error'))[:300]}")
    phase[0] = "idle after"; time.sleep(3); stop.set(); th.join(5)

    worst = 0.0
    print(f"\n{'phase':24} {'request':14} {'n':>4} {'p50':>7} {'p95':>7} {'max':>7}")
    for (ph, name), v in sorted(lat.items(), key=lambda x: x[0]):
        v = sorted(v); p95 = v[int(len(v) * .95) - 1] if len(v) > 1 else v[0]; worst = max(worst, v[-1])
        print(f"{ph:24} {name:14} {len(v):4d} {statistics.median(v):7.3f} {p95:7.3f} {v[-1]:7.3f}")
    if probe_errors: failures.append(f"{len(probe_errors)} probe errors, e.g. {probe_errors[:3]}")
    if worst > STALL_BUDGET_S: failures.append(f"a routine request took {worst:.1f}s (budget {STALL_BUDGET_S}s)")
finally:
    server.terminate()
    try: server.wait(10)
    except subprocess.TimeoutExpired: server.kill()
print("\nFAIL:\n- " + "\n- ".join(failures) if failures else "\nPASS live stress: no stalls, all renders and export succeeded")
sys.exit(1 if failures else 0)
