"""Focused verification of the two backend fixes made this session:
  1. A newly created voice take is auto-accepted (no longer silently muted).
  2. timing_mode='fixed' + requested_duration_ms actually controls the
     rendered part's duration, overriding narration length.
"""
import subprocess
import requests

BASE = "http://127.0.0.1:8123"
FIXTURE_DIR = "/home/claude/sceneforge/examples/fixture_assets"

checks = []


def check(name, cond, detail=""):
    checks.append((name, cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {('- ' + detail) if detail else ''}")


# --- setup: project + one part with an image + a short script ---
project = requests.post(f"{BASE}/api/projects", json={"title": "Fix verify", "aspect": "16:9", "language": "ar"}).json()
pid = project["id"]

import sqlite3
conn = sqlite3.connect("/tmp/sf_verify/sceneforge.db")
conn.execute("UPDATE projects SET width=480, height=270 WHERE id=?", (pid,))
conn.commit()
conn.close()

scene = requests.get(f"{BASE}/api/projects/{pid}").json()["scenes"][0]
sid = scene["id"]
requests.patch(f"{BASE}/api/scenes/{sid}", json={
    "original_text": "مرحبا بالعالم", "spoken_text": "مرحبا بالعالم", "subtitle_text": "مرحبا بالعالم",
})

with open(f"{FIXTURE_DIR}/image1.png", "rb") as f:
    asset = requests.post(f"{BASE}/api/assets/upload", params={"project_id": pid}, files={"file": ("image1.png", f)}).json()
requests.post(f"{BASE}/api/scenes/{sid}/shots", json={"asset_id": asset["id"], "motion": {"type": "zoom_in"}, "fit": "cover"})

# --- fix 1: auto-accept ---
take = requests.post(f"{BASE}/api/scenes/{sid}/voice-takes/local-tts", json={"source": "local_offline_tts", "voice": "ar"}).json()
check("new_take_auto_accepted", take["accepted"] is True, f"accepted={take['accepted']}")

# --- fix 2: fixed duration overrides narration length ---
requests.patch(f"{BASE}/api/scenes/{sid}", json={"timing_mode": "fixed", "requested_duration_ms": 3000})

job = requests.post(f"{BASE}/api/scenes/{sid}/render").json()
import time
for _ in range(120):
    j = requests.get(f"{BASE}/api/jobs/{job['job_id']}").json()
    if j["status"] in ("succeeded", "failed", "cancelled"):
        break
    time.sleep(0.5)
check("fixed_duration_render_succeeded", j["status"] == "succeeded", str(j.get("error"))[:300])

if j["status"] == "succeeded":
    asset_id = j["artifact_asset_id"]
    path = "/tmp/fixed_duration_check.mp4"
    with requests.get(f"{BASE}/api/assets/{asset_id}/stream", stream=True) as resp:
        with open(path, "wb") as f:
            for chunk in resp.iter_content(1 << 16):
                f.write(chunk)
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                           "-of", "default=nw=1:nk=1", path], capture_output=True, text=True)
    duration = float(out.stdout.strip())
    # narration for "مرحبا بالعالم" is much shorter than 3s standalone but
    # the FIXED 3.0s duration should win regardless (narration + lead/trail
    # would otherwise be ~1.5-2s here)
    check("fixed_duration_actually_applied", abs(duration - 3.0) < 0.15, f"duration={duration:.2f}s (expected ~3.00s)")

    # Confirm the download endpoint's Content-Disposition works
    head = requests.get(f"{BASE}/api/assets/{asset_id}/stream?download=1", stream=True)
    cd = head.headers.get("Content-Disposition", "")
    check("download_content_disposition_present", "attachment" in cd and ".mp4" in cd, cd)

print("\nSummary:", sum(1 for _, ok in checks if ok), "/", len(checks), "passed")
