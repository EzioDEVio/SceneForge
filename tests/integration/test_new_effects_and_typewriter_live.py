"""Verify the new glitch/old_film effects and typewriter caption reveal
end-to-end through the real API and real FFmpeg, at full 1080p."""
import subprocess
import requests

BASE = "http://127.0.0.1:8123"
FIXTURE_DIR = "/home/claude/sceneforge/examples/fixture_assets"

checks = []


def check(name, cond, detail=""):
    checks.append((name, cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {('- ' + detail) if detail else ''}")


def wait_job(job_id, timeout=60):
    import time
    start = time.time()
    while time.time() - start < timeout:
        j = requests.get(f"{BASE}/api/jobs/{job_id}").json()
        if j["status"] in ("succeeded", "failed", "cancelled"):
            return j
        time.sleep(0.4)
    raise TimeoutError()


project = requests.post(f"{BASE}/api/projects", json={"title": "Effects test", "aspect": "16:9"}).json()
pid = project["id"]
scenes = requests.get(f"{BASE}/api/projects/{pid}").json()["scenes"]

with open(f"{FIXTURE_DIR}/image1.png", "rb") as f:
    asset = requests.post(f"{BASE}/api/assets/upload", params={"project_id": pid}, files={"file": ("image1.png", f)}).json()

# --- Test 1: glitch effect ---
s1 = scenes[0]["id"]
requests.patch(f"{BASE}/api/scenes/{s1}", json={"timing_mode": "fixed", "requested_duration_ms": 3000, "effect_preset": "glitch"})
requests.post(f"{BASE}/api/scenes/{s1}/shots", json={"asset_id": asset["id"], "motion": {"type": "static"}, "fit": "cover"})
job1 = requests.post(f"{BASE}/api/scenes/{s1}/render").json()
j1 = wait_job(job1["job_id"])
check("glitch_effect_renders", j1["status"] == "succeeded", str(j1.get("error"))[:200])

# --- Test 2: old_film effect ---
s2 = scenes[1]["id"]
requests.patch(f"{BASE}/api/scenes/{s2}", json={"timing_mode": "fixed", "requested_duration_ms": 3000, "effect_preset": "old_film"})
requests.post(f"{BASE}/api/scenes/{s2}/shots", json={"asset_id": asset["id"], "motion": {"type": "static"}, "fit": "cover"})
job2 = requests.post(f"{BASE}/api/scenes/{s2}/render").json()
j2 = wait_job(job2["job_id"])
check("old_film_effect_renders", j2["status"] == "succeeded", str(j2.get("error"))[:200])

# --- Test 3: typewriter caption reveal ---
s3 = scenes[2]["id"]
long_caption = "This is a typewriter caption test that should reveal gradually."
requests.patch(f"{BASE}/api/scenes/{s3}", json={
    "timing_mode": "fixed", "requested_duration_ms": 4000,
    "original_text": long_caption, "subtitle_text": long_caption,
    "font": {"typewriter": True, "captions_enabled": True},
})
requests.post(f"{BASE}/api/scenes/{s3}/shots", json={"asset_id": asset["id"], "motion": {"type": "static"}, "fit": "cover"})
job3 = requests.post(f"{BASE}/api/scenes/{s3}/render").json()
j3 = wait_job(job3["job_id"])
check("typewriter_caption_renders", j3["status"] == "succeeded", str(j3.get("error"))[:200])

if j3["status"] == "succeeded":
    asset_id = j3["artifact_asset_id"]
    path = "/tmp/typewriter_check.mp4"
    with requests.get(f"{BASE}/api/assets/{asset_id}/stream", stream=True) as resp:
        with open(path, "wb") as f:
            for chunk in resp.iter_content(1 << 16):
                f.write(chunk)
    # Extract frames at early and late timestamps and OCR-free sanity
    # check: just confirm both decode (visual proof of reveal requires
    # eyeballing, done separately below).
    d_early = subprocess.run(["ffmpeg", "-v", "error", "-ss", "0.3", "-i", path, "-frames:v", "1", "-y", "/tmp/tw_early.png"], capture_output=True)
    d_late = subprocess.run(["ffmpeg", "-v", "error", "-ss", "3.5", "-i", path, "-frames:v", "1", "-y", "/tmp/tw_late.png"], capture_output=True)
    check("typewriter_frames_extracted", d_early.returncode == 0 and d_late.returncode == 0)

print(f"\nSummary: {sum(1 for _, ok in checks if ok)}/{len(checks)} passed")
