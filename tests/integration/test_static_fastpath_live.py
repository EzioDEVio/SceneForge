"""End-to-end verification of the static-motion fast path at FULL 1080p
(matching the reporting tester's real conditions, not a downscaled test
canvas), timed, through the real API and real FFmpeg."""
import time
import requests

BASE = "http://127.0.0.1:8123"
FIXTURE_DIR = "/home/claude/sceneforge/examples/fixture_assets"

project = requests.post(f"{BASE}/api/projects", json={"title": "Static fast-path test", "aspect": "16:9"}).json()
pid = project["id"]
# NOTE: deliberately NOT downscaling this project — full 1920x1080,
# matching the real-world report exactly.

scene = requests.get(f"{BASE}/api/projects/{pid}").json()["scenes"][0]
sid = scene["id"]
requests.patch(f"{BASE}/api/scenes/{sid}", json={"timing_mode": "fixed", "requested_duration_ms": 5000})

with open(f"{FIXTURE_DIR}/image1.png", "rb") as f:
    asset = requests.post(f"{BASE}/api/assets/upload", params={"project_id": pid}, files={"file": ("image1.png", f)}).json()
requests.post(f"{BASE}/api/scenes/{sid}/shots", json={"asset_id": asset["id"], "motion": {"type": "static"}, "fit": "cover"})

job = requests.post(f"{BASE}/api/scenes/{sid}/render").json()
start = time.time()
final_status = None
for _ in range(120):
    j = requests.get(f"{BASE}/api/jobs/{job['job_id']}").json()
    if j["status"] in ("succeeded", "failed", "cancelled"):
        final_status = j["status"]
        break
    time.sleep(0.5)
elapsed = time.time() - start

print(f"[{'PASS' if final_status == 'succeeded' else 'FAIL'}] static_1080p_5s_render_succeeded - status={final_status}")
print(f"[{'PASS' if elapsed < 30 else 'FAIL'}] static_1080p_5s_completed_quickly - {elapsed:.1f}s (was ~100s+ before this fix)")

if final_status == "succeeded":
    import subprocess
    asset_id = j["artifact_asset_id"]
    path = "/tmp/static_e2e_check.mp4"
    with requests.get(f"{BASE}/api/assets/{asset_id}/stream", stream=True) as resp:
        with open(path, "wb") as f:
            for chunk in resp.iter_content(1 << 16):
                f.write(chunk)
    info = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height",
                            "-of", "default=nw=1", path], capture_output=True, text=True)
    print("Rendered file info:", info.stdout.strip().replace("\n", " "))
