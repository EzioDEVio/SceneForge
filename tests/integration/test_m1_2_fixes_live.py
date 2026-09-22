"""Verify real, moving progress reporting during a single long shot render
(the root cause of "Generate looks frozen"), plus the createProject
full-detail fix (checked via the POST response shape it depends on)."""
import time
import requests

BASE = "http://127.0.0.1:8123"
FIXTURE_DIR = "/home/claude/sceneforge/examples/fixture_assets"

checks = []


def check(name, cond, detail=""):
    checks.append((name, cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {('- ' + detail) if detail else ''}")


# --- confirm POST /api/projects does NOT include scenes (this is exactly
# the shape that crashed the old frontend) — documents the contract the
# fix now correctly works around by re-fetching.
created = requests.post(f"{BASE}/api/projects", json={"title": "Progress test", "aspect": "16:9"}).json()
check("post_projects_response_has_no_scenes_key", "scenes" not in created,
      "(confirms why the frontend MUST re-fetch — this is the exact bug shape)")

full = requests.get(f"{BASE}/api/projects/{created['id']}").json()
check("get_project_has_scenes", "scenes" in full and len(full["scenes"]) == 3)

pid = created["id"]
import sqlite3
conn = sqlite3.connect("/tmp/sf_progress_test/sceneforge.db")
conn.execute("UPDATE projects SET width=960, height=540 WHERE id=?", (pid,))
conn.commit()
conn.close()

scene = full["scenes"][0]
sid = scene["id"]
long_text = "هذا اختبار طويل جداً للتحقق من أن شريط التقدم يتحرك فعلياً أثناء العرض. " * 4
requests.patch(f"{BASE}/api/scenes/{sid}", json={"original_text": long_text, "spoken_text": long_text, "subtitle_text": long_text})
requests.patch(f"{BASE}/api/scenes/{sid}", json={"timing_mode": "fixed", "requested_duration_ms": 8000})

with open(f"{FIXTURE_DIR}/image1.png", "rb") as f:
    asset = requests.post(f"{BASE}/api/assets/upload", params={"project_id": pid}, files={"file": ("image1.png", f)}).json()
requests.post(f"{BASE}/api/scenes/{sid}/shots", json={"asset_id": asset["id"], "motion": {"type": "close_up"}, "fit": "cover"})

take = requests.post(f"{BASE}/api/scenes/{sid}/voice-takes/local-tts", json={"source": "local_offline_tts", "voice": "ar"}).json()
check("narration_take_auto_accepted", take["accepted"] is True)

job = requests.post(f"{BASE}/api/scenes/{sid}/render").json()
job_id = job["job_id"]

observed_progress_values = set()
final_status = None
start = time.time()
while time.time() - start < 180:
    j = requests.get(f"{BASE}/api/jobs/{job_id}").json()
    observed_progress_values.add(j["progress"])
    if j["status"] in ("succeeded", "failed", "cancelled"):
        final_status = j["status"]
        break
    time.sleep(0.4)

check("job_reached_terminal_state", final_status == "succeeded", f"status={final_status}")
# The real test: did we see MORE than the old two-value jump (0 -> 50)?
# A genuinely moving progress bar during the single-shot visual stage
# should produce several distinct intermediate values, not just a couple.
check("progress_showed_multiple_distinct_values_during_render",
      len(observed_progress_values) >= 4,
      f"observed {sorted(observed_progress_values)}")

print("\nSummary:", sum(1 for _, ok in checks if ok), "/", len(checks), "passed")
