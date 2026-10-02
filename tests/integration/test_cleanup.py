"""Clean up: silence detection, scene jump cuts and filler-word detection with real FFmpeg.

No speech model runs here: filler detection reads a synthetic transcript (the same
[[word, start_ms, end_ms], ...] shape Auto captions stores in font_json.transcript).
"""
import os
import pathlib
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
tmp = tempfile.TemporaryDirectory()
os.environ["SCENEFORGE_DATA_DIR"] = tmp.name
sys.path.insert(0, str(ROOT / "backend"))
from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.db.database import SessionLocal  # noqa: E402
from app.db.models import Project  # noqa: E402
from app.render import silence as sil  # noqa: E402
from app.render.ffmpeg_utils import probe  # noqa: E402

TOL = 60
passed = 0


def ok(name, cond, detail=""):
    global passed
    assert cond, f"{name}: {detail}"
    passed += 1
    print("PASS", name)


def run(*args):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True, capture_output=True)


def close(got, want):
    return len(got) == len(want) and all(abs(a - b) <= TOL for g, w in zip(got, want) for a, b in zip(g, w))


def wait_job(client, job_id):
    for _ in range(1800):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] == "failed":
            raise AssertionError(job.get("error"))
        if job["status"] == "succeeded":
            return job
        time.sleep(0.2)
    raise AssertionError("export timed out")


# Tone bursts (seconds) separated by known silences; total 6.4 s.
BURSTS = [(0.7, 1.7), (2.7, 3.2), (4.0, 4.7), (5.0, 5.6)]
expr = "+".join(f"between(t,{a},{b})" for a, b in BURSTS)
tone = f"aevalsrc='({expr})*0.5*sin(2*PI*440*t)':s=48000:d=6.4"
# Silences: 0–700 (leading), 1700–2700, 3200–4000, 4700–5000 (300 ms: too short), 5600–6400 (trailing).
# With 120 ms padding on speech sides only:
EXPECTED = [[0, 580], [1820, 2580], [3320, 3880], [5720, 6400]]

audio_path = pathlib.Path(tmp.name) / "bursts.wav"
run("-f", "lavfi", "-i", tone, "-c:a", "pcm_s16le", str(audio_path))
video_path = pathlib.Path(tmp.name) / "bursts.mp4"
run("-f", "lavfi", "-i", "testsrc=s=320x180:d=6.4:r=25", "-f", "lavfi", "-i", tone,
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-shortest", str(video_path))

# --- pure helpers --------------------------------------------------------------------------
ok("keep ranges are the frame-snapped complement of the cuts",
   sil.keep_ranges([[100, 200], [150, 300], [990, 1000]], 1000, 40) == [[0, 120], [320, 1000]], sil.keep_ranges([[100, 200], [150, 300], [990, 1000]], 1000, 40))
ok("filler normalization strips punctuation, case and Arabic diacritics",
   sil.normalize("Um,") == "um" and sil.normalize("«يَعْني»") == "يعني" and sil.normalize("آه") == "اه")

with TestClient(app) as client:
    project = client.post("/api/projects", json={"title": "Clean up", "aspect": "16:9", "fps": 25}).json()
    project_id = project["id"]
    with SessionLocal() as db:
        item = db.get(Project, project_id)
        item.width, item.height = 320, 180
        db.commit()
    audio = client.post(f"/api/assets/upload?project_id={project_id}",
                        files={"file": (audio_path.name, audio_path.read_bytes(), "audio/wav")}).json()
    video = client.post(f"/api/assets/upload?project_id={project_id}",
                        files={"file": (video_path.name, video_path.read_bytes(), "video/mp4")}).json()

    # --- silence detection on a timeline audio asset -----------------------------------------
    r = client.post("/api/silence/detect", json={"asset_id": audio["id"]})
    assert r.status_code == 200, r.text
    det = r.json()
    ok("silence detection finds the known gaps within ±60 ms (default -38 dB, 600 ms, 120 ms padding)",
       close(det["ranges"], EXPECTED), det["ranges"])
    ok("the 300 ms gap is kept (shorter than the minimum silence)",
       not any(1 <= s - 4700 <= 300 or 4700 <= s <= 5000 for s, _ in det["ranges"]))
    ok("total removable time is the sum of the ranges",
       det["total_removable_ms"] == sum(e - s for s, e in det["ranges"]) and det["cuts"] == 4 and abs(det["duration_ms"] - 6400) < 30)
    r = client.post("/api/silence/detect", json={"asset_id": audio["id"], "min_silence_ms": 200, "padding_ms": 0}).json()
    ok("a shorter minimum silence also finds the 300 ms gap; zero padding cuts at the edges",
       len(r["ranges"]) == 5 and any(abs(s - 4700) <= TOL and abs(e - 5000) <= TOL for s, e in r["ranges"]), r["ranges"])

    # --- validation ---------------------------------------------------------------------------
    bad = [({"asset_id": audio["id"], "threshold_db": -10}, "Threshold must be between -60"),
           ({"asset_id": audio["id"], "min_silence_ms": 50}, "Minimum silence must be between 200"),
           ({"asset_id": audio["id"], "padding_ms": "x"}, "Padding must be a number"),
           ({}, "Send either asset_id or scene_id"),
           ({"asset_id": audio["id"], "scene_id": "x"}, "Send either asset_id or scene_id")]
    for body, msg in bad:
        r = client.post("/api/silence/detect", json=body)
        assert r.status_code == 400 and msg in r.json()["detail"], (body, r.text)
    ok("invalid silence settings return clear 400 messages", True)
    ok("unknown asset is 404", client.post("/api/silence/detect", json={"asset_id": "nope"}).status_code == 404)

    # --- video scene -----------------------------------------------------------------------
    scene_id = client.get(f"/api/projects/{project_id}").json()["scenes"][0]["id"]
    client.post(f"/api/scenes/{scene_id}/shots", json={"asset_id": video["id"]}).raise_for_status()
    words = [["So", 600, 800], ["um,", 900, 1100], ["I", 1200, 1300], ["mean", 1300, 1500], ["we", 1550, 1650],
             ["like", 2700, 2900], ["it.", 2950, 3150], ["Uh", 4000, 4200], ["يعني", 5000, 5300]]
    font = {"captions_enabled": True,
            "caption_segments": [{"id": "c1", "text": "So um I mean we", "start_ms": 600, "end_ms": 1650},
                                 {"id": "c2", "text": "like it.", "start_ms": 2700, "end_ms": 3150},
                                 {"id": "c3", "text": "Uh يعني", "start_ms": 4000, "end_ms": 5300}],
            "transcript": {"language": "en", "source": "clips", "words": words},
            "layers": [{"id": "t", "kind": "text", "text": "Title", "start_ms": 0, "end_ms": 6400}]}
    client.patch(f"/api/scenes/{scene_id}", json={"timing_mode": "fixed", "requested_duration_ms": 6400,
                                                     "subtitle_text": "So um I mean we like it. Uh يعني", "font": font}).raise_for_status()

    r = client.post("/api/fillers/detect", json={"scene_id": scene_id, "source": "clips"})
    assert r.status_code == 200, r.text
    fill = r.json()
    texts = [m["text"] for m in fill["matches"]]
    ok("filler detection finds um, the phrase 'I mean', Uh and Arabic يعني; like/so are off by default",
       texts == ["um,", "I mean", "Uh", "يعني"], texts)
    um, imean = fill["matches"][0], fill["matches"][1]
    ok("filler cuts get 40 ms padding but never reach into the neighbouring words",
       (um["start_ms"], um["end_ms"]) == (860, 1140) and (imean["start_ms"], imean["end_ms"]) == (1160, 1540)
       and um["prev"] == "So" and um["next"].startswith("I mean"), (um, imean))
    r = client.post("/api/fillers/detect", json={"scene_id": scene_id, "source": "clips", "words": ["like", "so", "UM"]}).json()
    ok("the filler list is user-editable (case-insensitive)", [m["text"] for m in r["matches"]] == ["So", "um,", "like"], r)
    r = client.post("/api/fillers/detect", json={"scene_id": scene_id, "source": "narration"})
    ok("asking for narration fillers when captions came from the clip sound is a clear 400",
       r.status_code == 400 and "Run Auto captions" in r.json()["detail"], r.text)
    r = client.post("/api/fillers/detect", json={"scene_id": scene_id, "source": "clips", "words": ["!!"]})
    ok("an empty filler list is rejected", r.status_code == 400 and "at least one" in r.json()["detail"], r.text)

    r = client.post("/api/silence/detect", json={"scene_id": scene_id, "source": "clips"})
    assert r.status_code == 200, r.text
    sdet = r.json()
    ok("scene clip-sound detection returns the same silences in scene time", close(sdet["scene_ranges"], EXPECTED), sdet)
    r = client.post("/api/silence/detect", json={"scene_id": scene_id, "source": "narration"})
    ok("narration detection on a scene without narration is a clear 400", r.status_code == 400 and "no narration" in r.json()["detail"])

    r = client.post(f"/api/cleanup/scenes/{scene_id}/jump-cut", json={"cuts": [[0, 6400]]})
    ok("a cut covering the whole scene is rejected", r.status_code == 400 and "whole scene" in r.json()["detail"], r.text)
    r = client.post(f"/api/cleanup/scenes/{scene_id}/jump-cut", json={"cuts": [[5, 10]]})
    ok("a cut shorter than a frame is reported as nothing to remove", r.status_code == 400 and "Nothing to remove" in r.json()["detail"], r.text)
    r = client.post(f"/api/cleanup/scenes/{scene_id}/jump-cut", json={"cuts": "x"})
    ok("cuts must be a list", r.status_code == 400)

    r = client.post(f"/api/cleanup/scenes/{scene_id}/jump-cut", json={"cuts": sdet["scene_ranges"]})
    assert r.status_code == 200, r.text
    cut = r.json()
    all_scenes = client.get(f"/api/projects/{project_id}").json()["scenes"]
    scenes = [s for s in all_scenes if s["shots"]]   # new projects also have empty placeholder parts
    ok("the segments sit where the scene was, before the other parts",
       [s["id"] for s in all_scenes[:3]] == [s["id"] for s in cut["scenes"]] and len(all_scenes) == 5, [s["title"] for s in all_scenes])
    lengths = [s["requested_duration_ms"] for s in scenes]
    want_kept = 6400 - sum(e - s for s, e in EXPECTED)
    ok("jump cut makes one scene per kept range (N=3), in order, with the right total length",
       cut["segments"] == 3 and len(scenes) == 3 and [s["id"] for s in scenes] == [s["id"] for s in cut["scenes"]]
       and abs(sum(lengths) - want_kept) <= 2 * TOL and sum(lengths) == cut["kept_ms"], (lengths, cut["kept_ms"]))
    shots = [s["shots"][0] for s in scenes]
    ok("each segment plays the matching source range of the same video (linked clip sound stays with it)",
       all(sh["asset_id"] == video["id"] for sh in shots)
       and all(sh["source_out_ms"] - sh["source_in_ms"] == length for sh, length in zip(shots, lengths))
       and all(abs(sh["source_in_ms"] - want) <= TOL for sh, want in zip(shots, [580, 2580, 3880]))
       and all(shots[i]["source_out_ms"] <= shots[i + 1]["source_in_ms"] for i in range(2)), shots)
    first, second, third = scenes
    ok("captions and transcript words are rebased into each segment",
       [w[0] for w in first["font_json"]["transcript"]["words"]] == ["So", "um,", "I", "mean", "we"]
       and first["font_json"]["transcript"]["words"][0][1] == 600 - shots[0]["source_in_ms"]
       and [w[0] for w in second["font_json"]["transcript"]["words"]] == ["like", "it."]
       and second["font_json"]["caption_segments"][0]["start_ms"] == 2700 - shots[1]["source_in_ms"]
       and third["subtitle_text"] == "Uh يعني", [s["font_json"] for s in scenes])
    ok("a full-length title is divided across the segments",
       all(s["font_json"]["layers"][0]["start_ms"] == 0 for s in scenes))
    ok("new segments start with a cut, the first keeps the scene title",
       second["title"] == first["title"] + " · 2" and third["title"] == first["title"] + " · 3"
       and second["transition_in_json"]["type"] == "cut", [s["title"] for s in scenes])
    r = client.post("/api/fillers/detect", json={"scene_id": third["id"], "source": "clips"}).json()
    ok("fillers can be found again after the cut (rebased words)", [m["text"] for m in r["matches"]] == ["Uh", "يعني"], r)

    # Narration and multi-shot scenes are refused with clear messages.
    narr_scene = client.post(f"/api/projects/{project_id}/scenes", json={}).json()
    client.post(f"/api/scenes/{narr_scene['id']}/shots", json={"asset_id": video["id"]}).raise_for_status()
    client.post(f"/api/scenes/{narr_scene['id']}/voice-takes/from-asset", json={"asset_id": audio["id"]}).raise_for_status()
    r = client.post(f"/api/cleanup/scenes/{narr_scene['id']}/jump-cut", json={"cuts": [[1000, 2000]]})
    ok("a scene with separate narration is refused (cut the narration on the timeline instead)",
       r.status_code == 400 and "separate narration" in r.json()["detail"], r.text)
    r = client.post("/api/silence/detect", json={"scene_id": narr_scene["id"], "source": "narration"}).json()
    ok("narration silences are reported in narration time and in scene time (+lead)",
       close(r["ranges"], EXPECTED) and all(b[0] - a[0] == r["scene_offset_ms"] for a, b in zip(r["ranges"], r["scene_ranges"])), r)
    client.post(f"/api/scenes/{narr_scene['id']}/voice-takes/clear-selection").raise_for_status()
    client.post(f"/api/scenes/{narr_scene['id']}/shots", json={"asset_id": video["id"]}).raise_for_status()
    r = client.post(f"/api/cleanup/scenes/{narr_scene['id']}/jump-cut", json={"cuts": [[1000, 2000]]})
    ok("a multi-clip scene is refused", r.status_code == 400 and "exactly one video clip" in r.json()["detail"], r.text)
    client.delete(f"/api/scenes/{narr_scene['id']}").raise_for_status()
    blank = client.post(f"/api/projects/{project_id}/scenes", json={}).json()
    r = client.post("/api/fillers/detect", json={"scene_id": blank["id"], "source": "narration"})
    ok("filler detection without a transcript asks for Auto captions first",
       r.status_code == 400 and "Run Auto captions" in r.json()["detail"], r.text)
    client.delete(f"/api/scenes/{blank['id']}").raise_for_status()

    # --- the jump-cut scenes render ------------------------------------------------------------
    exported = wait_job(client, client.post(f"/api/projects/{project_id}/export?skip_empty=true").json()["job_id"])
    result_path = pathlib.Path(tmp.name) / "cleanup-export.mp4"
    result_path.write_bytes(client.get(f"/api/assets/{exported['artifact_asset_id']}/stream").content)
    info = probe(str(result_path))
    ok("the jump-cut scenes export with sound at the shortened length",
       info.has_audio and abs(info.duration_ms - sum(lengths)) < 200, (info.duration_ms, sum(lengths)))
    pcm = sil.decode_mono(str(result_path))
    rerun = sil.find_silences(pcm, -38, 600, 0)
    ok("the exported sound has no silence of 600 ms or more left", not rerun, rerun)

print(f"{passed} clean-up checks passed")
