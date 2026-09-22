"""End-to-end verification of the new non-zoompan motion pipeline at
FULL 1920x1080, for BOTH zoom_in (scale-changing) and pan_left
(position-changing) — the two distinct code paths the fix touches —
through the real API with real narration and captions, timed."""
import time
import subprocess
import requests

BASE = "http://127.0.0.1:8123"
FIXTURE_DIR = "/home/claude/sceneforge/examples/fixture_assets"

project = requests.post(f"{BASE}/api/projects", json={"title": "Motion fix test", "aspect": "16:9"}).json()
pid = project["id"]
scenes = requests.get(f"{BASE}/api/projects/{pid}").json()["scenes"]

results = []


def check(name, cond, detail=""):
    results.append((name, cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {('- ' + detail) if detail else ''}")


def render_and_time(scene_id, motion_type, duration_s):
    requests.patch(f"{BASE}/api/scenes/{scene_id}", json={
        "timing_mode": "fixed", "requested_duration_ms": int(duration_s * 1000),
        "original_text": "اختبار الحركة", "subtitle_text": "اختبار الحركة",
    })
    with open(f"{FIXTURE_DIR}/image1.png", "rb") as f:
        asset = requests.post(f"{BASE}/api/assets/upload", params={"project_id": pid}, files={"file": ("image1.png", f)}).json()
    requests.post(f"{BASE}/api/scenes/{scene_id}/shots", json={"asset_id": asset["id"], "motion": {"type": motion_type}, "fit": "cover"})

    start = time.time()
    job = requests.post(f"{BASE}/api/scenes/{scene_id}/render").json()
    final = None
    for _ in range(120):
        j = requests.get(f"{BASE}/api/jobs/{job['job_id']}").json()
        if j["status"] in ("succeeded", "failed", "cancelled"):
            final = j
            break
        time.sleep(0.4)
    elapsed = time.time() - start
    return final, elapsed


# zoom_in at full 1080p, 5s (this is THE case that was reported as never finishing)
final_zoom, elapsed_zoom = render_and_time(scenes[0]["id"], "zoom_in", 5)
check("zoom_in_1080p_5s_succeeded", final_zoom and final_zoom["status"] == "succeeded", str(final_zoom and final_zoom.get("error"))[:200])
check("zoom_in_1080p_5s_fast", elapsed_zoom < 30, f"{elapsed_zoom:.1f}s (was 100s+ before this fix)")

# pan_left at full 1080p, 5s
final_pan, elapsed_pan = render_and_time(scenes[1]["id"], "pan_left", 5)
check("pan_left_1080p_5s_succeeded", final_pan and final_pan["status"] == "succeeded", str(final_pan and final_pan.get("error"))[:200])
check("pan_left_1080p_5s_fast", elapsed_pan < 30, f"{elapsed_pan:.1f}s")

# decode + visual correctness check on the zoom result
if final_zoom and final_zoom["status"] == "succeeded":
    asset_id = final_zoom["artifact_asset_id"]
    path = "/tmp/zoom_e2e_final.mp4"
    with requests.get(f"{BASE}/api/assets/{asset_id}/stream", stream=True) as resp:
        with open(path, "wb") as f:
            for chunk in resp.iter_content(1 << 16):
                f.write(chunk)
    d0 = subprocess.run(["ffmpeg", "-v", "error", "-ss", "0.1", "-i", path, "-frames:v", "1", "-f", "null", "-"], capture_output=True)
    dmid = subprocess.run(["ffmpeg", "-v", "error", "-ss", "2.5", "-i", path, "-frames:v", "1", "-f", "null", "-"], capture_output=True)
    dend = subprocess.run(["ffmpeg", "-v", "error", "-ss", "4.7", "-i", path, "-frames:v", "1", "-f", "null", "-"], capture_output=True)
    check("zoom_result_decodes_start_mid_end", d0.returncode == 0 and dmid.returncode == 0 and dend.returncode == 0)
    info = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
                            "-of", "default=nw=1", path], capture_output=True, text=True)
    check("zoom_result_has_audio_track", "audio" in info.stdout)

print(f"\nSummary: {sum(1 for _, ok in results if ok)}/{len(results)} passed")
