"""End-to-end check of a PACKAGED backend doing real editor work, with time limits.

Starts the backend exactly like the installed app (per-launch token, empty PATH so only the
bundled FFmpeg can be used) and runs what users do: import, thumbnail, effects, colour grade
preview, audio waveform, provider lists, and a full scene render with Old film + overlay.
Any step that fails or is slower than its limit fails the build.

  python desktop/tests/e2e_backend.py --exe <sceneforge-backend[.exe]> --ffmpeg-dir <dir> --resources <repo or app-resources>
"""
import argparse, json, os, re, secrets, subprocess, sys, tempfile, time, urllib.request, uuid

ap = argparse.ArgumentParser()
ap.add_argument("--exe", required=True); ap.add_argument("--ffmpeg-dir", required=True); ap.add_argument("--resources", required=True)
args = ap.parse_args()
ext = ".exe" if os.name == "nt" else ""
data, token = tempfile.mkdtemp(prefix="sf-e2e-"), secrets.token_hex(32)
env = dict(os.environ, PATH=tempfile.mkdtemp(), SCENEFORGE_DESKTOP_TOKEN=token, SCENEFORGE_DATA_DIR=data,
           SCENEFORGE_RESOURCE_DIR=args.resources, SCENEFORGE_SD_AUTOSTART="0",
           SCENEFORGE_FFMPEG=os.path.join(args.ffmpeg_dir, "ffmpeg" + ext), SCENEFORGE_FFPROBE=os.path.join(args.ffmpeg_dir, "ffprobe" + ext))
if os.name == "nt":
    env["PATH"] = os.environ.get("SystemRoot", r"C:\Windows") + r"\System32"   # Windows needs System32; still no FFmpeg
log = open(os.path.join(data, "backend-stderr.log"), "w")
proc = subprocess.Popen([args.exe], env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log, text=True)
failures = []


def request(method, path, body=None, files=None, timeout=60):
    headers = {"X-SceneForge-Token": token}
    data_bytes = None
    if files:
        boundary = uuid.uuid4().hex
        name, content, ctype = files
        data_bytes = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{name}\"\r\nContent-Type: {ctype}\r\n\r\n").encode() + content + f"\r\n--{boundary}--\r\n".encode()
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    elif body is not None:
        data_bytes = json.dumps(body).encode(); headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data_bytes, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        return json.loads(raw) if r.headers.get("content-type", "").startswith("application/json") else raw


timeouts = 0


def step(name, limit, fn):
    global timeouts
    if timeouts >= 2:   # the backend has stopped answering: skip the rest (its log explains why)
        print(f"   ----   skipped (backend not answering) {name}", flush=True)
        failures.append(f"{name}: skipped, backend not answering")
        return None
    start = time.time()
    try:
        out = fn()
        took = time.time() - start
        status = "ok" if took <= limit else f"TOO SLOW (limit {limit}s)"
        if took > limit:
            failures.append(f"{name}: {took:.1f}s > {limit}s")
    except Exception as e:  # noqa: BLE001
        took, out, status = time.time() - start, None, f"FAILED: {e}"
        failures.append(f"{name}: {e}")
        if "timed out" in str(e):
            timeouts += 1
    print(f"{took:7.2f}s  {status:<24} {name}", flush=True)
    return out


try:
    line = proc.stdout.readline()
    if not line.startswith("SCENEFORGE_READY "):
        raise SystemExit("backend did not start: " + line)
    BASE = f"http://127.0.0.1:{json.loads(line.split(' ', 1)[1])['port']}"
    ff = env["SCENEFORGE_FFMPEG"]
    work = tempfile.mkdtemp()
    img, wav = os.path.join(work, "photo.jpg"), os.path.join(work, "voice.wav")
    subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=1920x1080", "-frames:v", "1", img], check=True)
    subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=300:d=2", img.replace("photo.jpg", "voice.wav")], check=True)

    project = step("create project", 5, lambda: request("POST", "/api/projects", {"title": "E2E", "aspect": "16:9"}))
    pid = project["id"]
    asset = step("import a 1920x1080 photo", 15, lambda: request("POST", f"/api/assets/upload?project_id={pid}", files=("photo.jpg", open(img, "rb").read(), "image/jpeg")))
    step("thumbnail", 10, lambda: request("GET", f"/api/assets/{asset['id']}/thumbnail?w=320"))
    step("thumbnail (cached)", 2, lambda: request("GET", f"/api/assets/{asset['id']}/thumbnail?w=320"))
    scene = step("load project", 5, lambda: request("GET", f"/api/projects/{pid}"))["scenes"][0]
    sid = scene["id"]
    step("add photo to scene", 5, lambda: request("POST", f"/api/scenes/{sid}/shots", {"asset_id": asset["id"]}))
    step("change look", 5, lambda: request("PATCH", f"/api/scenes/{sid}", {"effect_preset": "sepia", "look": {"tone": {"amount": 40}, "wheels": {"lift": [0, 0, 20]}}}))
    step("colour-graded preview frame", 20, lambda: request("GET", f"/api/scenes/{sid}/graded-frame?w=1280"))
    voice = step("upload narration", 15, lambda: request("POST", f"/api/scenes/{sid}/voice-takes/upload", files=("voice.wav", open(wav, "rb").read(), "audio/wav")))
    step("audio waveform", 15, lambda: request("GET", f"/api/assets/{voice['audio_asset']['id']}/waveform?points=300"))
    def isolate_voice():  # AI voice isolation: onnxruntime + MDX-Net model (downloads ~67 MB once)
        out = request("POST", f"/api/assets/{voice['audio_asset']['id']}/isolate-voice", {"strength": 100, "wait": True}, timeout=600)
        if out.get("status") != "done" or out["asset"]["type"] != "audio":
            raise AssertionError(f"voice isolation did not return an audio asset: {out}")
        return out
    step("AI voice isolation on the narration (model download + onnxruntime)", 600, isolate_voice)
    step("provider list", 5, lambda: request("GET", "/api/providers"))
    def whisper_engine():
        report = request("GET", "/api/local-speech/whisper/check")
        bad = [f"{c['name']}: {c['detail']}" for c in report["checks"] if not c["ok"] and c["name"] in ("CTranslate2 engine", "Faster-Whisper", "Model folder writable")]
        if bad:
            raise AssertionError("Local Whisper cannot load in this build: " + "; ".join(bad))
        return report
    step("local Whisper engine loads in the packaged backend (no model download)", 30, whisper_engine)
    step("local image engine settings", 5, lambda: request("GET", "/api/local-image-settings"))
    step("add overlay + old film", 5, lambda: request("PATCH", f"/api/scenes/{sid}", {"timing_mode": "fixed", "requested_duration_ms": 3000,
         "overlays": [{"asset_id": asset["id"], "x": 70, "y": 30, "width": 30}],
         "look": {"film": {"scratches": 60, "dust": 50, "flicker": 40, "weave": 35, "fps": 18, "tone": "bw"},
                  # Arabic stop labels exercise the bundled shaping libraries (python-bidi has a compiled part)
                  "route": {"points": [[15, 70], [50, 40], [85, 55]], "labels": ["قرطبة", "غرناطة 711", "Toledo"], "marker": "plane", "curve": True, "draw_ms": 1500},
                  "annotations": [{"type": "circle", "style": "hand"}, {"type": "callout", "text": "قرطبة 711", "x": 70, "y": 25, "x2": 55, "y2": 50}]}}))
    job = step("start scene render", 5, lambda: request("POST", f"/api/scenes/{sid}/render"))

    def wait():
        deadline = time.time() + 300
        while time.time() < deadline:
            st = request("GET", f"/api/jobs/{job['job_id']}")
            if st["status"] in ("succeeded", "failed", "cancelled"):
                if st["status"] != "succeeded":
                    raise RuntimeError(f"render {st['status']}: {st.get('error')}")
                return st
            time.sleep(1)
        raise RuntimeError("render did not finish")
    step("render 3 s scene (overlay + old film + grade + narration + Arabic map route + annotations)", 240, wait)

    # A video with its own sound in a scene without narration: length follows the video and its
    # sound is kept (regression guard for 0.5.3: clips used to render silent and 4 s long).
    clipf = os.path.join(work, "clip.mp4")
    subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:d=3:r=30", "-f", "lavfi", "-i", "sine=f=500:d=3",
                    "-c:v", "libx264", "-c:a", "aac", "-shortest", clipf], check=True)
    vasset = step("import a video with sound", 20, lambda: request("POST", f"/api/assets/upload?project_id={pid}", files=("clip.mp4", open(clipf, "rb").read(), "video/mp4")))
    vscene = request("GET", f"/api/projects/{pid}")["scenes"][1]["id"]
    step("add the video to a scene without narration", 5, lambda: request("POST", f"/api/scenes/{vscene}/shots", {"asset_id": vasset["id"]}))
    vjob = step("start video scene render", 5, lambda: request("POST", f"/api/scenes/{vscene}/render"))
    job = vjob

    def wait_video():
        wait()
        rendered = [x for x in request("GET", f"/api/projects/{pid}")["scenes"] if x["id"] == vscene][0]["rendered_asset_id"]
        data = request("GET", f"/api/assets/{rendered}/stream")
        out = os.path.join(work, "vscene.mp4"); open(out, "wb").write(data)
        dur = float(subprocess.run([env["SCENEFORGE_FFPROBE"], "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out], capture_output=True, text=True).stdout)
        vol = subprocess.run([ff, "-i", out, "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True).stderr
        peak = float(re.search(r"max_volume: (-?[\d.]+) dB", vol).group(1))
        if abs(dur - 3) > 0.25 or peak < -40:
            raise RuntimeError(f"video scene is {dur:.2f} s with peak {peak} dB (expected 3 s with sound)")
    step("video scene keeps its length and its own sound", 120, wait_video)

    # Real local Whisper in the packaged backend: downloads the model once (network), decodes
    # the clip's sound and runs inference. A tone has no words, so "No speech was recognised"
    # is the expected answer; any load/decode/inference error fails the build.
    def local_captions():
        import urllib.error
        try:
            request("POST", f"/api/scenes/{vscene}/auto-captions", {"provider": "local", "language": "en", "source": "clips"}, timeout=600)
            return "transcribed"
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            if e.code == 400 and "No speech was recognised" in detail:
                return "no speech in a test tone (engine ran)"
            raise RuntimeError(f"local Whisper failed ({e.code}): {detail[:600]}")
    step("local Whisper captions run in the packaged app (model download + inference)", 600, local_captions)

    # AI background removal in the packaged backend: onnxruntime + the small U2-Net model
    # (4.6 MB from GitHub releases), on the photo imported above.
    def cutout_runs():
        out = request("POST", f"/api/assets/{asset['id']}/cutout", {"model": "u2netp", "edge": "soft"}, timeout=300)
        if out.get("mime") != "image/png":
            raise RuntimeError(f"cutout did not return a PNG: {out}")
        return out["original_filename"]
    step("AI subject cutout runs in the packaged app (model download + onnxruntime)", 300, cutout_runs)

    # Text behind a moving subject: 1 s of the clip (30 frames) -> VP9-alpha layer job -> render
    # with the packaged FFmpeg (libvpx-vp9 alpha decode in the overlay pass).
    def video_cutout_runs():
        global job
        vshot = [x for x in request("GET", f"/api/projects/{pid}")["scenes"] if x["id"] == vscene][0]["shots"][0]
        request("PATCH", f"/api/scenes/shots/{vshot['id']}", {"source_in_ms": 0, "source_out_ms": 1000})
        started, st = request("POST", f"/api/scenes/{vscene}/subject-video-layer", {"model": "u2netp"}), {}
        while started.get("status") == "running":
            st = request("GET", f"/api/cutout/video-jobs/{started['job_id']}")
            if st["status"] in ("succeeded", "failed", "cancelled"):
                if st["status"] != "succeeded":
                    raise RuntimeError(f"video cutout {st['status']}: {st.get('error')}")
                break
            time.sleep(1)
        job = request("POST", f"/api/scenes/{vscene}/render")
        wait()
        return f"{st.get('frames_done')} frames at {st.get('ms_per_frame')} ms/frame ({st.get('codec')})"
    step("text behind a moving subject (video cutout job + render)", 120, video_cutout_runs)
finally:
    try:
        proc.stdin.close(); proc.wait(timeout=20)
    except Exception:  # noqa: BLE001
        proc.kill()
    log.close()

if failures:
    print("\nFAILED:\n  " + "\n  ".join(failures))
    print("\nbackend log:\n" + open(os.path.join(data, "backend-stderr.log"), errors="replace").read()[-12000:])
    sys.exit(1)
print("\nAll end-to-end steps passed.")
