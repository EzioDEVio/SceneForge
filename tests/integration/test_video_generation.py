"""Catalog, estimate and local ComfyUI workflow contract; no provider keys or GPU required."""
import os, pathlib, sys, tempfile
from types import SimpleNamespace
from unittest.mock import patch

root = pathlib.Path(__file__).resolve().parents[2]
temp = tempfile.TemporaryDirectory()
os.environ["SCENEFORGE_DATA_DIR"] = temp.name
os.environ["SCENEFORGE_SD_AUTOSTART"] = "0"
sys.path.insert(0, str(root / "backend"))

from app.providers import video_generation as video

class FakeResponse:
    ok = True
    status_code = 200
    def __init__(self, payload=None, content=b"fake-video-bytes"):
        self.payload, self.content = payload or {}, content
    def json(self):
        return self.payload

by_id = {row["id"]: row for row in video.catalog()}
assert {"ltx-2.5-fast", "wan2.1-t2v-1.3b", "wan2.2-ti2v-5b", "wan2.2-t2v-a14b", "custom-comfy-workflow"} <= set(by_id)
assert {"veo-3.1-lite", "veo-3.1-fast", "veo-3.1", "runway-gen4.5", "runway-wan3"} <= set(by_id)
assert by_id["wan2.2-ti2v-5b"]["min_vram_gb"] == 8
assert by_id["wan2.1-t2v-1.3b"]["min_vram_gb"] == 8
assert by_id["ltx-2.5-fast"]["min_vram_gb"] == 32 and by_id["ltx-2.5-fast"]["min_system_ram_gb"] == 32
assert video.estimate_cost(by_id["veo-3.1-lite"], 8, "720p")["usd"] == 0.4
assert video.estimate_cost(by_id["runway-wan3"], 8, "1080p")["usd"] == 1.6
assert video.estimate_cost(by_id["wan2.2-ti2v-5b"], 8, "720p")["usd"] == 0

base = {"provider": "google_veo", "model": "veo-3.1-fast", "prompt": "A test prompt", "negative_prompt": "",
        "aspect_ratio": "9:16", "width": 720, "height": 1280, "duration_seconds": 8,
        "resolution": "1080p", "seed": None, "confirm_paid": True}
model, width, height = video.validate_request(base)
assert model["id"] == "veo-3.1-fast" and (width, height) == (720, 1280)
bad = {**base, "duration_seconds": 6, "resolution": "1080p"}
try:
    video.validate_request(bad)
except video.VideoGenerationError as exc:
    assert "only for 8-second" in str(exc)
else:
    raise AssertionError("Veo 1080p accepted an unsupported duration")
bad = {**base, "provider": "runway", "model": "runway-gen4.5", "resolution": "720p", "aspect_ratio": "custom"}
try:
    video.validate_request(bad)
except video.VideoGenerationError as exc:
    assert "Custom ratios" in str(exc)
else:
    raise AssertionError("Cloud provider accepted a custom ratio")

workflow = {
    "10": {"class_type": "CLIPTextEncode", "inputs": {"text": "old prompt", "clip": ["1", 0]}, "_meta": {"title": "Positive Prompt"}},
    "11": {"class_type": "CLIPTextEncode", "inputs": {"text": "old negative", "clip": ["1", 0]}, "_meta": {"title": "Negative Prompt"}},
    "12": {"class_type": "EmptyLTXVLatentVideo", "inputs": {"width": 1280, "height": 720, "length": 121, "batch_size": 1}},
}
encoded = video.parse_workflow(__import__("json").dumps(workflow).encode())
prepared = video._prepare_workflow(encoded, {"model": "ltx-2.5-fast", "duration_seconds": 4, "prompt": "new prompt", "negative_prompt": "avoid blur", "seed": 42}, 720, 1280)
assert prepared["10"]["inputs"]["text"] == "new prompt"
assert prepared["11"]["inputs"]["text"] == "avoid blur"
assert prepared["12"]["inputs"]["width"] == 720 and prepared["12"]["inputs"]["height"] == 1280
assert prepared["12"]["inputs"]["length"] == 97
assert video.validate_local_comfy_url("http://localhost:8188") == "http://localhost:8188"
try:
    video.validate_local_comfy_url("http://example.com:8188")
except video.VideoGenerationError:
    pass
else:
    raise AssertionError("Non-loopback ComfyUI address was accepted")

# Exercise provider request shapes without credentials, network traffic, or charges.
stages = []
stage = lambda *args: stages.append(args[0])
cloud_bytes = b"test-cloud-video-bytes"
veo_operation = {"name":"operations/test", "done":True, "response":{"generateVideoResponse":{"generatedSamples":[{"video":{"uri":"https://generativelanguage.googleapis.com/v1beta/files/test:download"}}]}}}
with patch.object(video.requests, "post", return_value=FakeResponse(veo_operation)) as post, \
     patch.object(video.requests, "get", return_value=FakeResponse(content=cloud_bytes)) as get:
    result = video._google_veo("test-key", video.model_for("google_veo", "veo-3.1-fast"), base, stage, lambda: False)
    assert result == cloud_bytes
    assert post.call_args.args[0].endswith("/models/veo-3.1-fast-generate-preview:predictLongRunning")
    assert post.call_args.kwargs["json"]["parameters"]["aspectRatio"] == "9:16"
    assert get.call_args.args[0].startswith("https://generativelanguage.googleapis.com/")

runway_req = {**base, "provider":"runway", "model":"runway-wan3", "resolution":"1080p"}
with patch.object(video.requests, "post", return_value=FakeResponse({"id":"runway-task"})) as post, \
     patch.object(video.requests, "get", side_effect=[FakeResponse({"status":"SUCCEEDED", "output":["https://cdn.runwayml.com/video.mp4"]}), FakeResponse(content=cloud_bytes)]) as get:
    result = video._runway("test-key", video.model_for("runway", "runway-wan3"), runway_req, stage, lambda: False)
    assert result == cloud_bytes
    assert post.call_args.kwargs["json"] == {"model":"wan3", "promptText":"A test prompt", "duration":8, "ratio":"720:1280", "resolution":"1080p"}
    assert len(get.call_args_list) == 2

from fastapi.testclient import TestClient
from app.main import app
from app.db.database import engine

with TestClient(app) as client:
    response = client.get("/api/video-generation/catalog")
    assert response.status_code == 200 and len(response.json()["models"]) >= 9
    hardware = client.get("/api/video-generation/local/system")
    assert hardware.status_code == 200 and "recommended_model_ids" in hardware.json()
    with patch("subprocess.run", return_value=SimpleNamespace(stdout="NVIDIA GeForce RTX 3060, 6144\nNVIDIA GeForce RTX 4090, 8192\n")):
        detected = client.get("/api/video-generation/local/system").json()
    assert detected["gpu_name"] == "NVIDIA GeForce RTX 4090" and detected["vram_gb"] == 8.0
    assert detected["gpu_count"] == 2 and detected["system_ram_gb"] is not None
    assert detected["recommended_model_ids"][0] == "wan2.2-ti2v-5b"
    with patch("subprocess.run", return_value=SimpleNamespace(stdout="NVIDIA GeForce RTX 2060, 6144\n")):
        lower_hardware = client.get("/api/video-generation/local/system").json()
    assert lower_hardware["vram_gb"] == 6.0
    assert lower_hardware["recommended_model_ids"][0] == "wan2.1-t2v-1.3b"
    response = client.post("/api/providers", json={"capability":"video", "name":"local_comfy", "api_key":"", "base_url":"http://127.0.0.1:8188"})
    assert response.status_code == 200 and response.json()["configured"]
    assert response.json()["masked_key"] == "Local engine · no API key"
    response = client.post("/api/providers", json={"capability":"video", "name":"local_comfy", "api_key":"", "base_url":"http://example.com:8188"})
    assert response.status_code == 400
    project = client.post("/api/projects", json={"title":"Video generation cost guard", "aspect":"16:9", "fps":25}).json()
    assert project["fps"] == 25
    updated_project = client.patch(f"/api/projects/{project['id']}", json={"fps":24})
    assert updated_project.status_code == 200 and updated_project.json()["fps"] == 24
    assert client.patch(f"/api/projects/{project['id']}", json={"fps":23}).status_code == 422
    response = client.post(f"/api/video-generation/projects/{project['id']}/generate", json={**base, "confirm_paid": False})
    assert response.status_code == 400 and "Confirm the displayed provider cost estimate" in response.json()["detail"]
    response = client.post("/api/video-generation/local/workflows/ltx-2.5-fast", files={"file":("ltx.json", __import__("json").dumps(workflow), "application/json")})
    assert response.status_code == 200 and response.json()["node_count"] == 3
    assert client.get("/api/video-generation/catalog").json()["models"][0]["workflow_imported"]

    from app.workers import jobs as job_worker
    local_request = {"provider":"local_comfy", "model":"ltx-2.5-fast", "prompt":"A test clip",
                     "negative_prompt":"", "aspect_ratio":"16:9", "width":1280, "height":720,
                     "duration_seconds":4, "resolution":"720p", "seed":41,
                     "candidate_count":3, "confirm_paid":False}
    generation_job_id = ""
    with patch.object(job_worker, "start_video_generation_job") as start_job:
        started = client.post(f"/api/video-generation/projects/{project['id']}/generate", json=local_request)
        assert started.status_code == 200 and start_job.call_args.args[2]["candidate_count"] == 3
        generation_job_id = started.json()["job_id"]
        status = client.get(f"/api/jobs/{started.json()['job_id']}")
        assert status.status_code == 200 and status.json()["result_asset_ids"] == []
    too_many = client.post(f"/api/video-generation/projects/{project['id']}/generate", json={**local_request, "candidate_count":4})
    assert too_many.status_code == 422

    mock_video = b"x" * 2048
    probe_result = SimpleNamespace(has_video=True, duration_ms=1000, width=1280, height=720, has_audio=False)
    with patch.object(video, "generate_video_bytes", side_effect=[(mock_video, "mock-local") for _ in range(3)]) as generate_mock, \
         patch("app.render.ffmpeg_utils.probe", return_value=probe_result):
        job_worker._run_video_generation_job(generation_job_id, project["id"], local_request)
    finished = client.get(f"/api/jobs/{generation_job_id}").json()
    assert finished["status"] == "succeeded" and len(finished["result_asset_ids"]) == 3
    assert len(set(finished["result_asset_ids"])) == 3 and finished["artifact_asset_id"] == finished["result_asset_ids"][-1]
    assert [call.kwargs["data"]["seed"] for call in generate_mock.call_args_list] == [41, 42, 43]

    class FakeComfySession:
        trust_env = True
        def post(self, url, **kwargs):
            self.url, self.body = url, kwargs["json"]
            return FakeResponse({"prompt_id":"comfy-prompt"})
        def get(self, url, **kwargs):
            if url.endswith("/history/comfy-prompt"):
                return FakeResponse({"comfy-prompt":{"status":{"status_str":"success"}, "outputs":{"9":{"videos":[{"filename":"generated.mp4", "type":"output"}]}}}})
            if url.endswith("/view"):
                assert kwargs["params"]["filename"] == "generated.mp4"
                return FakeResponse(content=b"fake-local-video-bytes")
            raise AssertionError(f"Unexpected ComfyUI request: {url}")

    comfy_session = FakeComfySession()
    local_req = {"model":"ltx-2.5-fast", "duration_seconds":4, "prompt":"A local clip", "negative_prompt":"", "seed":7}
    with patch.object(video.requests, "Session", return_value=comfy_session):
        result = video._comfyui("http://127.0.0.1:8188", video.model_for("local_comfy", "ltx-2.5-fast"), local_req, 720, 1280, stage, lambda:False)
    assert result == b"fake-local-video-bytes" and comfy_session.trust_env is False
    assert comfy_session.url.endswith("/prompt") and comfy_session.body["prompt"]["12"]["inputs"]["width"] == 720

engine.dispose()
temp.cleanup()
print("PASS model catalog/prices, GPU guidance endpoint, Google and Runway request adapters, ComfyUI queue/output flow, workflow mapping/import, candidate-count validation, paid confirmation, and loopback-only local connection")
