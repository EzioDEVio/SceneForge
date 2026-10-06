"""Bounded stress: repeated saves, concurrent reads and real multi-track exports.

Uses a disposable database and generated fixtures. No AI/provider calls.
This exercises API/workers/rendering; it does not claim Windows UI coverage.
"""
import concurrent.futures
import os
import pathlib
import subprocess
import sys
import tempfile
import time

root = pathlib.Path(__file__).resolve().parents[2]
temp = tempfile.TemporaryDirectory(prefix="sf-stress-")
os.environ["SCENEFORGE_DATA_DIR"] = temp.name
sys.path.insert(0, str(root / "backend"))
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import SessionLocal
from app.db.models import Asset, Project
from app.config import RENDERS_DIR
from app.render.ffmpeg_utils import probe

started = time.monotonic()
with TestClient(app) as client:
    def request(method, path, **kw):
        response = client.request(method, "/api" + path, **kw)
        assert response.is_success, (path, response.text)
        return response.json() if response.content else None

    project = request("POST", "/projects", json={"title": "Stress", "fps": 25})
    pid = project["id"]
    scenes = request("GET", "/projects/" + pid)["scenes"]
    for scene, color in zip(scenes[:2], ("red", "blue")):
        video = pathlib.Path(temp.name) / (color + ".mp4")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                        f"color={color}:s=320x180:r=25:d=2", "-f", "lavfi", "-i",
                        "sine=frequency=440:duration=2", "-c:v", "libx264", "-threads", "1",
                        "-c:a", "aac", str(video)], check=True)
        asset = request("POST", "/assets/upload?project_id=" + pid,
                        files={"file": (video.name, video.read_bytes(), "video/mp4")})
        request("POST", "/scenes/" + scene["id"] + "/shots", json={"asset_id": asset["id"]})
        request("PATCH", "/scenes/" + scene["id"], json={"timing_mode": "fixed",
                "requested_duration_ms": 2000, "font": {"captions_enabled": False}})
    with SessionLocal() as db:
        row = db.get(Project, pid)
        row.width, row.height = 320, 180
        db.commit()
    clips = [{"id": "stress-" + str(i), "scene_id": scenes[i % 2]["id"],
              "start_ms": (i // 6) * 400, "source_in_ms": (i % 3) * 200,
              "duration_ms": 400, "track": i % 6} for i in range(60)]
    for i in range(80):
        clips[0]["start_ms"] = i % 20
        request("PATCH", "/projects/" + pid,
                json={"finishing": {"free_timeline": {"enabled": True, "clips": clips}}})
    expected = request("GET", "/projects/" + pid)["finishing_json"]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        snapshots = list(pool.map(lambda _: request("GET", "/projects/" + pid), range(120)))
    assert all(p["finishing_json"] == expected for p in snapshots)
    print("PASS 80 saves and 120 reads across eight concurrent clients; all 60 clip placements preserved", flush=True)

    for cycle in range(8):
        job_id = request("POST", "/projects/" + pid + "/export", json={"quality": "draft"})["job_id"]
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            job = request("GET", "/jobs/" + job_id)
            if job["status"] in ("succeeded", "failed", "cancelled"):
                break
            time.sleep(.1)
        assert job["status"] == "succeeded", job
        with SessionLocal() as db:
            path = pathlib.Path(RENDERS_DIR) / db.get(Asset, job["artifact_asset_id"]).storage_key
        assert abs(probe(str(path)).duration_ms - 4000) < 60
        subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"], check=True)
        assert request("GET", "/projects/" + pid)["finishing_json"] == expected
        assert request("GET", "/close-status")["ready"] is True
        print(f"PASS export {cycle + 1}/8: 60 excerpts on six tracks, exact duration, decoded video/audio, no stuck worker", flush=True)
    print(f"PASS bounded stress completed in {time.monotonic() - started:.1f}s", flush=True)
