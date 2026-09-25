"""End-to-end check of a PACKAGED backend doing real editor work, with time limits.

Starts the backend exactly like the installed app (per-launch token, empty PATH so only the
bundled FFmpeg can be used) and runs what users do: import, thumbnail, effects, colour grade
preview, audio waveform, provider lists, and a full scene render with Old film + overlay.
Any step that fails or is slower than its limit fails the build.

  python desktop/tests/e2e_backend.py --exe <sceneforge-backend[.exe]> --ffmpeg-dir <dir> --resources <repo or app-resources>
"""
import argparse, json, os, secrets, subprocess, sys, tempfile, time, urllib.request, uuid

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


def step(name, limit, fn):
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
    step("provider list", 5, lambda: request("GET", "/api/providers"))
    step("local image engine settings", 5, lambda: request("GET", "/api/local-image-settings"))
    step("add overlay + old film", 5, lambda: request("PATCH", f"/api/scenes/{sid}", {"timing_mode": "fixed", "requested_duration_ms": 3000,
         "overlays": [{"asset_id": asset["id"], "x": 70, "y": 30, "width": 30}],
         "look": {"film": {"scratches": 60, "dust": 50, "flicker": 40, "weave": 35, "fps": 18, "tone": "bw"}}}))
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
    step("render 3 s scene (overlay + old film + grade + narration)", 240, wait)
finally:
    try:
        proc.stdin.close(); proc.wait(timeout=20)
    except Exception:  # noqa: BLE001
        proc.kill()
    log.close()

if failures:
    print("\nFAILED:\n  " + "\n  ".join(failures))
    print("\nbackend log:\n" + open(os.path.join(data, "backend-stderr.log"), errors="replace").read()[-4000:])
    sys.exit(1)
print("\nAll end-to-end steps passed.")
