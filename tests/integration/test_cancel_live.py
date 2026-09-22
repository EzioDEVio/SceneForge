"""Cancellation test: start a render on a fresh, meaty part (so it runs
long enough to cancel mid-flight), request cancellation, and verify:
  1. The job transitions to 'cancelled' (not silently stuck/failed).
  2. No orphaned ffmpeg process remains for that job's working directory.
This exercises spec section 11: "Cancel rendering and verify no orphan
FFmpeg process."
"""
from __future__ import annotations
import subprocess
import sys
import time

import requests

BASE = "http://127.0.0.1:8123"
FIXTURE_DIR = "/home/claude/sceneforge/examples/fixture_assets"

results = []


def check(name, cond, detail=""):
    results.append({"name": name, "passed": bool(cond), "detail": detail})
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {('- ' + detail) if detail else ''}")


def ffmpeg_pids():
    out = subprocess.run(["pgrep", "-f", "ffmpeg"], capture_output=True, text=True)
    return [p for p in out.stdout.split() if p.strip()]


# Fresh project with one part carrying a long narration (so the zoompan
# render takes long enough to cancel mid-flight rather than racing to finish).
r = requests.post(f"{BASE}/api/projects", json={"title": "Cancel test", "aspect": "16:9", "language": "ar"})
project = r.json()
project_id = project["id"]

import sqlite3
conn = sqlite3.connect("/tmp/sf_smoketest/sceneforge.db")
conn.execute("UPDATE projects SET width=640, height=360 WHERE id=?", (project_id,))
conn.commit()
conn.close()

scene = requests.get(f"{BASE}/api/projects/{project_id}").json()["scenes"][0]
long_text = "هذا اختبار طويل جداً لعملية الإلغاء. " * 6
requests.patch(f"{BASE}/api/scenes/{scene['id']}", json={
    "original_text": long_text, "spoken_text": long_text, "subtitle_text": long_text,
}).raise_for_status()

with open(f"{FIXTURE_DIR}/image1.png", "rb") as f:
    asset = requests.post(f"{BASE}/api/assets/upload", params={"project_id": project_id},
                           files={"file": ("image1.png", f)}).json()
requests.post(f"{BASE}/api/scenes/{scene['id']}/shots",
              json={"asset_id": asset["id"], "motion": {"type": "zoom_in"}, "fit": "cover"}).raise_for_status()

take = requests.post(f"{BASE}/api/scenes/{scene['id']}/voice-takes/local-tts",
                      json={"source": "local_offline_tts", "voice": "ar"}).json()
check("long_narration_synthesized", take["measured_duration_ms"] > 8000, f"{take['measured_duration_ms']}ms")
requests.post(f"{BASE}/api/voice-takes/{take['id']}/select").raise_for_status()

before_pids = set(ffmpeg_pids())
job = requests.post(f"{BASE}/api/scenes/{scene['id']}/render").json()
job_id = job["job_id"]

# Wait for the render's ffmpeg process to actually appear and be doing
# real work before cancelling — cancelling an empty queue proves nothing.
new_pid = None
for _ in range(60):
    time.sleep(0.5)
    current = set(ffmpeg_pids()) - before_pids
    if current:
        new_pid = next(iter(current))
        break
check("render_ffmpeg_process_started", new_pid is not None, f"pid={new_pid}")

time.sleep(1.5)  # let it do a bit of real work before cancelling
cancel_resp = requests.post(f"{BASE}/api/jobs/{job_id}/cancel")
check("cancel_request_accepted", cancel_resp.status_code == 200, str(cancel_resp.status_code))

final_status = None
for _ in range(30):
    time.sleep(0.5)
    j = requests.get(f"{BASE}/api/jobs/{job_id}").json()
    final_status = j["status"]
    if final_status in ("cancelled", "failed", "succeeded"):
        break
check("job_reached_terminal_cancelled_state", final_status == "cancelled", f"status={final_status}")

# Give the OS a moment to reap, then confirm the specific ffmpeg pid we
# saw is gone (not just "some ffmpeg somewhere" — this exact process).
time.sleep(1.0)
still_running = new_pid in ffmpeg_pids() if new_pid else False
check("no_orphan_ffmpeg_process_after_cancel", not still_running, f"pid {new_pid} still present={still_running}")

import json
with open("/tmp/cancel_result.json", "w") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
failed = [r for r in results if not r["passed"]]
print(json.dumps({"total": len(results), "failed": [r["name"] for r in failed]}, indent=2))
sys.exit(0 if not failed else 1)
