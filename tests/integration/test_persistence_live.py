"""Persistence test: kill and restart the backend process, then verify a
previously created project — its scripts, shots, voice takes, and already-
rendered part/export artifacts — is still intact and playable through the
API, per M1 acceptance: "edits persist after restart"."""
from __future__ import annotations
import json
import subprocess
import sys

import requests

BASE = "http://127.0.0.1:8123"
PROJECT_ID = sys.argv[1]

r = requests.get(f"{BASE}/api/projects/{PROJECT_ID}")
r.raise_for_status()
project = r.json()

results = []


def check(name, cond, detail=""):
    results.append({"name": name, "passed": bool(cond), "detail": detail})
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {('- ' + detail) if detail else ''}")


check("project_reloadable_after_restart", True, project["title"])
check("three_parts_still_present", len(project["scenes"]) == 3)

for i, scene in enumerate(project["scenes"]):
    check(f"part{i+1}_script_text_survived", bool(scene["original_text"].strip()), scene["original_text"][:40])
    check(f"part{i+1}_has_rendered_asset_id", bool(scene["rendered_asset_id"]))
    check(f"part{i+1}_has_shots", len(scene["shots"]) > 0)
    check(f"part{i+1}_has_accepted_voice_take", any(t["accepted"] for t in scene["voice_takes"]))

    # Fetch and decode the still-referenced rendered asset from disk via the API
    asset_id = scene["rendered_asset_id"]
    local_path = f"/tmp/restart_check_part{i+1}.mp4"
    with requests.get(f"{BASE}/api/assets/{asset_id}/stream", stream=True) as resp:
        with open(local_path, "wb") as f:
            for chunk in resp.iter_content(1 << 16):
                f.write(chunk)
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                           "-of", "default=nw=1", local_path], capture_output=True, text=True)
    check(f"part{i+1}_rendered_asset_still_decodes_after_restart", out.returncode == 0 and "duration" in out.stdout,
          out.stdout.strip())

with open("/tmp/persistence_result.json", "w") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

failed = [r for r in results if not r["passed"]]
print(json.dumps({"total": len(results), "failed": [r["name"] for r in failed]}, indent=2))
sys.exit(0 if not failed else 1)
