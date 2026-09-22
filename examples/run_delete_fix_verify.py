"""Verify the fix: deleting a scene/part that has an associated
RenderJob (i.e. was ever Generated) no longer crashes with a foreign
key constraint violation."""
import requests

BASE = "http://127.0.0.1:8123"
FIXTURE_DIR = "/home/claude/sceneforge/examples/fixture_assets"

project = requests.post(f"{BASE}/api/projects", json={"title": "Delete test", "aspect": "16:9"}).json()
pid = project["id"]

import sqlite3
conn = sqlite3.connect("/tmp/sf_delete_test/sceneforge.db")
conn.execute("UPDATE projects SET width=480, height=270 WHERE id=?", (pid,))
conn.commit()
conn.close()

scene = requests.get(f"{BASE}/api/projects/{pid}").json()["scenes"][0]
sid = scene["id"]
requests.patch(f"{BASE}/api/scenes/{sid}", json={"original_text": "test", "timing_mode": "fixed", "requested_duration_ms": 1500})

with open(f"{FIXTURE_DIR}/image1.png", "rb") as f:
    asset = requests.post(f"{BASE}/api/assets/upload", params={"project_id": pid}, files={"file": ("image1.png", f)}).json()
requests.post(f"{BASE}/api/scenes/{sid}/shots", json={"asset_id": asset["id"], "motion": {"type": "static"}, "fit": "cover"})

job = requests.post(f"{BASE}/api/scenes/{sid}/render").json()
print("job started:", job["job_id"], "- NOT waiting for completion, deleting scene immediately")

# Delete the scene RIGHT AWAY, while a RenderJob row referencing it
# already exists in the DB (created at render-start, before this delete)
# — this is exactly the condition that crashed before.
r = requests.delete(f"{BASE}/api/scenes/{sid}")
print("delete status:", r.status_code)
print("delete body:", r.json())
assert r.status_code == 200, "DELETE crashed — fix did not work"
print("PASS: scene with an associated render job deleted without a foreign-key crash")
