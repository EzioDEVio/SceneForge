"""Editable source-clip split, timed text slicing, source sound and segment thumbnails."""
import os
import pathlib
import subprocess
import sys
import tempfile
import time

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[2]
tmp = tempfile.TemporaryDirectory()
os.environ["SCENEFORGE_DATA_DIR"] = tmp.name
sys.path.insert(0, str(ROOT / "backend"))
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import SessionLocal
from app.db.models import Project
from app.render.ffmpeg_utils import probe


def run(*args):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True, capture_output=True)


def wait_job(client, job_id):
    for _ in range(300):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] == "failed":
            raise AssertionError(job.get("error"))
        if job["status"] == "succeeded":
            return job
        time.sleep(0.1)
    raise AssertionError("source split export timed out")


video_path = pathlib.Path(tmp.name) / "red-blue-with-sound.mp4"
run("-f", "lavfi", "-i", "color=c=red:s=320x180:d=2:r=25",
    "-f", "lavfi", "-i", "color=c=blue:s=320x180:d=2:r=25",
    "-f", "lavfi", "-i", "sine=f=440:d=4:r=48000",
    "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
    "-map", "[v]", "-map", "2:a", "-c:v", "libx264", "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-shortest", str(video_path))

with TestClient(app) as client:
    project = client.post("/api/projects", json={"title": "Source cut regression", "aspect": "16:9", "fps": 25}).json()
    project_id = project["id"]
    with SessionLocal() as db:
        item = db.get(Project, project_id)
        item.width, item.height = 320, 180
        db.commit()
    asset = client.post(f"/api/assets/upload?project_id={project_id}",
                        files={"file": (video_path.name, video_path.read_bytes(), "video/mp4")}).json()
    scene_id = client.get(f"/api/projects/{project_id}").json()["scenes"][0]["id"]
    client.post(f"/api/scenes/{scene_id}/shots", json={"asset_id": asset["id"]}).raise_for_status()
    font = {"captions_enabled": True,
            "caption_segments": [{"id": "cap-a", "text": "before", "start_ms": 500, "end_ms": 1500},
                                 {"id": "cap-b", "text": "crossing cut", "start_ms": 1500, "end_ms": 2500},
                                 {"id": "cap-c", "text": "after", "start_ms": 2500, "end_ms": 3500}],
            "transcript": {"language": "en", "source": "clips", "words": [["before", 500, 1500], ["crossing", 1500, 2500], ["after", 2500, 3500]]},
            "layers": [{"id": "title", "kind": "text", "text": "Timed title", "start_ms": 1000, "end_ms": 3500}]}
    client.patch(f"/api/scenes/{scene_id}", json={"timing_mode": "fixed", "requested_duration_ms": 4000,
                                                     "subtitle_text": "before crossing cut after", "font": font}).raise_for_status()

    response = client.post(f"/api/scenes/{scene_id}/split", json={"at_ms": 2000, "baked": False})
    assert response.status_code == 200, response.text
    right = response.json()
    left = client.get(f"/api/scenes/{scene_id}").json()
    assert left["requested_duration_ms"] == right["requested_duration_ms"] == 2000
    assert left["shots"][0]["source_in_ms"] == 0 and left["shots"][0]["source_out_ms"] == 2000
    assert right["shots"][0]["source_in_ms"] == 2000 and right["shots"][0]["source_out_ms"] in (None, 4000)
    assert left["shots"][0]["asset_id"] == right["shots"][0]["asset_id"] == asset["id"]
    assert left["font_json"]["caption_segments"] == [
        {"id": "cap-a", "text": "before", "start_ms": 500, "end_ms": 1500},
        {"id": "cap-b", "text": "crossing cut", "start_ms": 1500, "end_ms": 2000},
    ]
    assert right["font_json"]["caption_segments"] == [
        {"id": "cap-b", "text": "crossing cut", "start_ms": 0, "end_ms": 500},
        {"id": "cap-c", "text": "after", "start_ms": 500, "end_ms": 1500},
    ]
    assert left["font_json"]["transcript"]["words"][1] == ["crossing", 1500, 2000]
    assert right["font_json"]["transcript"]["words"][0] == ["crossing", 0, 500]
    assert left["font_json"]["layers"][0]["end_ms"] == 2000
    assert right["font_json"]["layers"][0]["start_ms"] == 0 and right["font_json"]["layers"][0]["end_ms"] == 1500
    assert left["subtitle_text"] == "before crossing cut" and right["subtitle_text"] == "crossing cut after"

    thumb = client.get(f"/api/assets/{asset['id']}/thumbnail?w=160&time_ms=2500")
    assert thumb.status_code == 200, thumb.text
    thumb_path = pathlib.Path(tmp.name) / "cut-thumbnail.jpg"
    thumb_path.write_bytes(thumb.content)
    with Image.open(thumb_path) as frame:
        r, g, b = frame.convert("RGB").getpixel((frame.width // 2, frame.height // 2))
    assert b > r + 70, (r, g, b)

    exported = wait_job(client, client.post(f"/api/projects/{project_id}/export?skip_empty=true").json()["job_id"])
    result_path = pathlib.Path(tmp.name) / "source-split-export.mp4"
    result_path.write_bytes(client.get(f"/api/assets/{exported['artifact_asset_id']}/stream").content)
    result = probe(str(result_path))
    assert result.has_audio and abs(result.duration_ms - 4000) < 160, result
    print("PASS raw source cut keeps clip audio, divides editable caption/text timings, and shows the correct segment thumbnail")
