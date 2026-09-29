"""Video generation adapters and the user-facing provider/model catalog.

Cloud keys are passed only from the OS-backed provider vault. Local open
models are run by the user's ComfyUI process; model weights and workflow
files are deliberately not bundled into SceneForge's base installer.
"""
from __future__ import annotations

import json
import secrets
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

from app.config import DATA_DIR


class VideoGenerationError(RuntimeError):
    """A safe-to-display error from a video provider."""


class VideoGenerationCancelled(VideoGenerationError):
    pass


VIDEO_WORKFLOWS_DIR = DATA_DIR / "video_workflows"

MODEL_CATALOG: list[dict] = [
    {
        "id": "ltx-2.5-fast", "provider": "local_comfy", "provider_label": "Local · ComfyUI",
        "name": "LTX-2.5 Fast", "model": "LTX-2.5", "kind": "local", "price_per_second": 0,
        "resolutions": ["480p", "720p", "1080p"], "ratios": ["16:9", "9:16", "1:1", "custom"],
        "duration_min": 1, "duration_max": 20, "durations": [], "native_audio": True,
        "requirements": "ComfyUI with the official LTX-2.5 text-to-video workflow and model files. High-end NVIDIA GPU recommended; LTX docs currently list 32 GB+ VRAM, 32 GB RAM and 100 GB free disk as minimums.",
        "workflow_url": "https://docs.ltx.io/open-source-model/integration-tools/comfy-ui",
        "terms_url": "https://huggingface.co/Lightricks/LTX-2.5",
        "cost_note": "No API fee. GPU electricity, hardware and model license terms still apply.",
    },
    {
        "id": "wan2.1-t2v-1.3b", "provider": "local_comfy", "provider_label": "Local · ComfyUI",
        "name": "Wan 2.1 · T2V 1.3B", "model": "Wan2.1-T2V-1.3B", "kind": "local", "price_per_second": 0,
        "resolutions": ["480p"], "ratios": ["16:9", "9:16", "1:1", "custom"],
        "duration_min": 1, "duration_max": 5, "durations": [], "native_audio": False,
        "requirements": "ComfyUI workflow and downloaded model files. Lighter than the 14B Wan model; generation speed depends on the user's GPU.",
        "workflow_url": "https://docs.comfy.org/tutorials/video/wan/wan-video",
        "terms_url": "https://github.com/Wan-Video/Wan2.1",
        "cost_note": "No API fee. GPU electricity, hardware and model license terms still apply.",
    },
    {
        "id": "wan2.2-ti2v-5b", "provider": "local_comfy", "provider_label": "Local · ComfyUI",
        "name": "Wan 2.2 · TI2V 5B", "model": "Wan2.2-TI2V-5B", "kind": "local", "price_per_second": 0,
        "resolutions": ["480p", "720p"], "ratios": ["16:9", "9:16", "1:1", "custom"],
        "duration_min": 1, "duration_max": 5, "durations": [], "native_audio": False,
        "requirements": "ComfyUI's official Wan2.2 5B workflow. Official ComfyUI docs say it can fit around 8 GB VRAM with native offloading; more VRAM is faster.",
        "workflow_url": "https://docs.comfy.org/tutorials/video/wan/wan2_2",
        "terms_url": "https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B",
        "cost_note": "No API fee. GPU electricity, hardware and model license terms still apply.",
    },
    {
        "id": "wan2.2-t2v-a14b", "provider": "local_comfy", "provider_label": "Local · ComfyUI",
        "name": "Wan 2.2 · T2V A14B", "model": "Wan2.2-T2V-A14B", "kind": "local", "price_per_second": 0,
        "resolutions": ["480p", "720p"], "ratios": ["16:9", "9:16", "1:1", "custom"],
        "duration_min": 1, "duration_max": 5, "durations": [], "native_audio": False,
        "requirements": "Advanced local setup. This large model requires substantially more GPU memory than the 5B workflow; expect a high-end GPU and a large model download.",
        "workflow_url": "https://docs.comfy.org/tutorials/video/wan/wan2_2",
        "terms_url": "https://huggingface.co/Wan-AI/Wan2.2-T2V-A14B",
        "cost_note": "No API fee. GPU electricity, hardware and model license terms still apply.",
    },
    {
        "id": "custom-comfy-workflow", "provider": "local_comfy", "provider_label": "Local · ComfyUI",
        "name": "Custom ComfyUI workflow", "model": "user-supplied", "kind": "local", "price_per_second": 0,
        "resolutions": ["480p", "720p", "1080p", "4k"], "ratios": ["16:9", "9:16", "1:1", "custom"],
        "duration_min": 1, "duration_max": 30, "durations": [], "native_audio": None,
        "requirements": "Use a trusted ComfyUI text-to-video API workflow. SceneForge maps common prompt, size, frame-count and seed inputs; specialized workflows may need adjustment in ComfyUI. Custom nodes run inside ComfyUI with your user permissions.",
        "workflow_url": "https://docs.comfy.org/development/comfyui-server/comms_routes",
        "cost_note": "No API fee. GPU electricity, hardware, custom-node dependencies and model license terms still apply.",
    },
    {
        "id": "veo-3.1-lite", "provider": "google_veo", "provider_label": "Google Gemini API",
        "name": "Veo 3.1 Lite", "model": "veo-3.1-lite-generate-preview", "kind": "cloud",
        "price_per_second": {"720p": 0.05, "1080p": 0.08}, "resolutions": ["720p", "1080p"],
        "ratios": ["16:9", "9:16"], "duration_min": 4, "duration_max": 8,
        "durations": [4, 6, 8], "native_audio": True,
        "requirements": "Google AI Studio API key. Cloud generation is billed by Google; video includes generated audio.",
        "workflow_url": "https://ai.google.dev/gemini-api/docs/veo",
        "cost_note": "Google list price per second; estimate updates with duration and resolution.",
    },
    {
        "id": "veo-3.1-fast", "provider": "google_veo", "provider_label": "Google Gemini API",
        "name": "Veo 3.1 Fast", "model": "veo-3.1-fast-generate-preview", "kind": "cloud",
        "price_per_second": {"720p": 0.10, "1080p": 0.12, "4k": 0.30}, "resolutions": ["720p", "1080p", "4k"],
        "ratios": ["16:9", "9:16"], "duration_min": 4, "duration_max": 8,
        "durations": [4, 6, 8], "native_audio": True,
        "requirements": "Google AI Studio API key. Cloud generation is billed by Google; 1080p and 4K require an 8-second clip.",
        "workflow_url": "https://ai.google.dev/gemini-api/docs/veo",
        "cost_note": "Google list price per second; estimate updates with duration and resolution.",
    },
    {
        "id": "veo-3.1", "provider": "google_veo", "provider_label": "Google Gemini API",
        "name": "Veo 3.1 Standard", "model": "veo-3.1-generate-preview", "kind": "cloud",
        "price_per_second": {"720p": 0.40, "1080p": 0.40, "4k": 0.60}, "resolutions": ["720p", "1080p", "4k"],
        "ratios": ["16:9", "9:16"], "duration_min": 4, "duration_max": 8,
        "durations": [4, 6, 8], "native_audio": True,
        "requirements": "Google AI Studio API key. Cloud generation is billed by Google; 1080p and 4K require an 8-second clip.",
        "workflow_url": "https://ai.google.dev/gemini-api/docs/veo",
        "cost_note": "Google list price per second; estimate updates with duration and resolution.",
    },
    {
        "id": "runway-gen4.5", "provider": "runway", "provider_label": "Runway API",
        "name": "Gen-4.5", "model": "gen4.5", "kind": "cloud", "price_per_second": {"720p": 0.12},
        "resolutions": ["720p"], "ratios": ["16:9", "9:16"], "duration_min": 2, "duration_max": 10,
        "durations": [], "native_audio": False,
        "requirements": "Runway API key and account credits. Text-to-video supports landscape 16:9 and portrait 9:16 output.",
        "workflow_url": "https://docs.dev.runwayml.com/guides/using-the-api/",
        "cost_note": "12 Runway credits per second; Runway lists each credit at USD $0.01.",
    },
    {
        "id": "runway-wan3", "provider": "runway", "provider_label": "Runway API",
        "name": "WAN 3.0", "model": "wan3", "kind": "cloud", "price_per_second": {"480p": 0.05, "720p": 0.10, "1080p": 0.20},
        "resolutions": ["480p", "720p", "1080p"], "ratios": ["16:9", "9:16"],
        "duration_min": 2, "duration_max": 30, "durations": [], "native_audio": True,
        "requirements": "Runway API key and account credits. WAN 3.0 supports 2–30 seconds and generates native audio.",
        "workflow_url": "https://docs.dev.runwayml.com/api-details/api_changelog/",
        "cost_note": "5 / 10 / 20 Runway credits per second at 480p / 720p / 1080p; each credit is USD $0.01.",
    },
]


def catalog() -> list[dict]:
    """Return a copy safe for API serialization and add local workflow state."""
    VIDEO_WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for row in MODEL_CATALOG:
        item = dict(row)
        if item["kind"] == "local":
            item["workflow_imported"] = (VIDEO_WORKFLOWS_DIR / f"{item['id']}.json").is_file()
        out.append(item)
    return out


def model_for(provider: str, model_id: str) -> dict:
    found = next((m for m in MODEL_CATALOG if m["provider"] == provider and m["id"] == model_id), None)
    if not found:
        raise VideoGenerationError("Choose a supported model from the provider list.")
    return found


def estimate_cost(model: dict, duration_seconds: int, resolution: str) -> dict:
    price = model["price_per_second"]
    if isinstance(price, dict):
        rate = price.get(resolution)
        if rate is None:
            return {"usd": None, "credits": None, "label": "Select a supported resolution"}
    else:
        rate = price
    usd = round(float(rate) * duration_seconds, 4)
    credits = round(usd / 0.01, 2) if model["provider"] == "runway" else None
    if model["kind"] == "local":
        label = "No provider charge · local GPU use only"
    else:
        label = f"About ${usd:.2f} USD" + (f" · {credits:g} Runway credits" if credits is not None else "")
    return {"usd": usd, "credits": credits, "label": label, "per_second_usd": float(rate)}


def validate_request(data: dict) -> tuple[dict, int, int]:
    model = model_for(data["provider"], data["model"])
    duration, resolution, ratio = int(data["duration_seconds"]), data["resolution"], data["aspect_ratio"]
    if not model["duration_min"] <= duration <= model["duration_max"]:
        raise VideoGenerationError(f"{model['name']} supports {model['duration_min']}–{model['duration_max']} second clips.")
    if model["durations"] and duration not in model["durations"]:
        allowed = ", ".join(map(str, model["durations"]))
        raise VideoGenerationError(f"{model['name']} supports {allowed} second clips.")
    if resolution not in model["resolutions"]:
        raise VideoGenerationError(f"{model['name']} does not support {resolution}. Choose: {', '.join(model['resolutions'])}.")
    if ratio not in model["ratios"]:
        raise VideoGenerationError(f"{model['name']} supports these ratios: {', '.join(model['ratios'])}. Custom ratios are available with local models.")
    width, height = int(data["width"]), int(data["height"])
    if ratio != "custom" and data["provider"] != "local_comfy":
        pair = {"16:9": (1280, 720), "9:16": (720, 1280), "1:1": (1024, 1024)}[ratio]
        width, height = pair
    if width % 16 or height % 16:
        raise VideoGenerationError("Custom width and height must each be divisible by 16.")
    if data["provider"] == "google_veo":
        if duration != 8 and resolution != "720p":
            raise VideoGenerationError("Google Veo supports 1080p and 4K only for 8-second clips.")
        if resolution == "4k" and model["id"] == "veo-3.1-lite":
            raise VideoGenerationError("Veo 3.1 Lite does not support 4K output.")
    if data["provider"] == "runway" and model["id"] == "runway-gen4.5" and resolution != "720p":
        raise VideoGenerationError("Runway Gen-4.5 text-to-video is currently configured for 720p output.")
    return model, width, height


def workflow_path(model_id: str) -> Path:
    model_for("local_comfy", model_id)
    return VIDEO_WORKFLOWS_DIR / f"{model_id}.json"


def parse_workflow(raw: bytes) -> dict:
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VideoGenerationError("Workflow must be a valid UTF-8 JSON file.") from exc
    if not isinstance(data, dict) or not data or len(data) > 1000:
        raise VideoGenerationError("This does not look like a ComfyUI API workflow. Export using Save (API Format).")
    graph = data.get("prompt", data)
    if not isinstance(graph, dict) or not graph or len(graph) > 1000:
        raise VideoGenerationError("This workflow does not contain a ComfyUI API node graph. Export using Save (API Format).")
    if not all(isinstance(n, dict) and isinstance(n.get("inputs"), dict) and isinstance(n.get("class_type"), str) for n in graph.values()):
        raise VideoGenerationError("Workflow nodes are not in ComfyUI API format. In ComfyUI choose Save (API Format), not Save.")
    return graph


def _prepare_workflow(graph: dict, data: dict, width: int, height: int) -> dict:
    graph = json.loads(json.dumps(graph))
    duration = int(data["duration_seconds"])
    seed = int(data["seed"]) if data.get("seed") is not None else secrets.randbits(32)
    # The most reliable way to adapt ComfyUI templates across node versions is
    # to update semantic input names and text-encode nodes, leaving the model's
    # sampler and all other advanced settings untouched.
    text_nodes = []
    for node_id, node in graph.items():
        cls = node.get("class_type", "").lower()
        meta = node.get("_meta", {}) or {}
        title = str(meta.get("title", "")).lower()
        for key, value in node.get("inputs", {}).items():
            low = str(key).lower()
            if isinstance(value, str) and low in {"text", "prompt", "positive", "negative_prompt"}:
                text_nodes.append((str(node_id), node, key, value, cls, title))
        inputs = node.get("inputs", {})
        for key in inputs:
            low = str(key).lower()
            if low in {"width", "output_width"} and isinstance(inputs[key], (int, float)):
                inputs[key] = width
            elif low in {"height", "output_height"} and isinstance(inputs[key], (int, float)):
                inputs[key] = height
            elif low in {"length", "frames", "num_frames", "frame_count", "video_length"} and isinstance(inputs[key], (int, float)):
                # Video models commonly require N*8+1 frames. Use their nearest
                # valid frame count; the rendered duration may differ by < 1 frame.
                raw_frames = max(9, round(duration * 24))
                inputs[key] = max(9, round((raw_frames - 1) / 8) * 8 + 1)
            elif low in {"seed", "noise_seed", "random_seed"} and isinstance(inputs[key], (int, float)):
                inputs[key] = seed
    positive = [x for x in text_nodes if not any(tag in (x[4] + " " + x[5] + " " + str(x[3]).lower()) for tag in ("negative", "uncond"))]
    negative = [x for x in text_nodes if x not in positive]
    if not negative and len(positive) == 2 and all("cliptextencode" in row[4] for row in positive):
        # Many stock ComfyUI text-to-video templates use the standard positive
        # and negative CLIP encoders without labeling the node titles.
        negative, positive = positive[1:], positive[:1]
    if not positive:
        raise VideoGenerationError("Could not find a positive text prompt field in this ComfyUI workflow. Use a text-to-video workflow exported as API Format.")
    # Prefer a named prompt field, otherwise the first positive text encoder.
    preferred = next((x for x in positive if str(x[2]).lower() in {"text", "prompt", "positive"}), positive[0])
    preferred[1]["inputs"][preferred[2]] = data["prompt"].strip()
    if data.get("negative_prompt"):
        if negative:
            negative[0][1]["inputs"][negative[0][2]] = data["negative_prompt"].strip()
        else:
            raise VideoGenerationError("This local workflow has no negative-prompt field. Clear the negative prompt or import a workflow that includes one.")
    return graph


def local_comfy_status(base_url: str) -> dict:
    url = validate_local_comfy_url(base_url)
    try:
        session = requests.Session()
        session.trust_env = False
        response = session.get(url + "/system_stats", timeout=(2, 4), allow_redirects=False)
        if response.status_code != 200:
            return {"ready": False, "message": f"ComfyUI returned HTTP {response.status_code}."}
        return {"ready": True, "message": "ComfyUI is connected."}
    except requests.RequestException:
        return {"ready": False, "message": "Could not reach ComfyUI. Start it locally and check its address."}


def validate_local_comfy_url(value: str | None) -> str:
    url = (value or "http://127.0.0.1:8188").strip().rstrip("/")
    parsed = urlparse(url)
    if parsed.scheme != "http" or not parsed.hostname or parsed.username or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise VideoGenerationError("Local ComfyUI address must be an HTTP loopback URL such as http://127.0.0.1:8188.")
    if parsed.hostname.lower() not in {"127.0.0.1", "localhost", "::1"}:
        raise VideoGenerationError("For security, SceneForge connects only to ComfyUI running on this computer.")
    return url


def generate_video_bytes(*, provider: str, model: dict, api_key: str, base_url: str | None,
                         data: dict, width: int, height: int, stage, cancelled) -> tuple[bytes, str]:
    if provider == "google_veo":
        return _google_veo(api_key, model, data, stage, cancelled), "google_veo"
    if provider == "runway":
        return _runway(api_key, model, data, stage, cancelled), "runway"
    return _comfyui(base_url or "", model, data, width, height, stage, cancelled), f"Local · {model['name']}"


def _google_veo(api_key: str, model: dict, data: dict, stage, cancelled) -> bytes:
    if not api_key.strip():
        raise VideoGenerationError("Add a Google AI Studio key in Settings → Providers before generating.")
    base = "https://generativelanguage.googleapis.com/v1beta"
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    body = {"instances": [{"prompt": data["prompt"].strip()}], "parameters": {
        "aspectRatio": data["aspect_ratio"], "durationSeconds": str(data["duration_seconds"]),
        "resolution": data["resolution"],
    }}
    if data.get("seed") is not None:
        body["parameters"]["seed"] = int(data["seed"])
    try:
        response = requests.post(f"{base}/models/{model['model']}:predictLongRunning", headers=headers,
                                 json=body, timeout=(15, 60))
        if not response.ok:
            raise VideoGenerationError(f"Google Veo rejected the request (HTTP {response.status_code}). Check the model, key, billing and quota in Google AI Studio.")
        op = response.json()
        name = op.get("name")
        if not name:
            raise VideoGenerationError("Google Veo did not return a generation operation.")
        stage("Google is generating the video · provider progress is not available", 0)
        deadline = time.monotonic() + 30 * 60
        while time.monotonic() < deadline:
            if cancelled():
                raise VideoGenerationCancelled("Generation cancelled. Google may continue processing a request already accepted by its service.")
            if op.get("done"):
                if op.get("error"):
                    raise VideoGenerationError("Google Veo reported that generation failed. Check the key, billing and quota, then try again.")
                samples = (op.get("response") or {}).get("generateVideoResponse", {}).get("generatedSamples", [])
                video_uri = (samples[0].get("video") or {}).get("uri") if samples else None
                if not video_uri:
                    raise VideoGenerationError("Google Veo completed without returning a video file.")
                parsed = urlparse(video_uri)
                host = (parsed.hostname or "").lower()
                if parsed.scheme != "https" or not (host == "googleapis.com" or host.endswith(".googleapis.com")):
                    raise VideoGenerationError("Google returned an unexpected video download address.")
                stage("Downloading generated video", 0)
                video = requests.get(video_uri, headers={"x-goog-api-key": api_key}, timeout=(15, 180))
                if not video.ok:
                    raise VideoGenerationError("Could not download the video Google generated. Try generating again.")
                return video.content
            time.sleep(6)
            poll = requests.get(f"{base}/{name}", headers=headers, timeout=(15, 30))
            if not poll.ok:
                raise VideoGenerationError(f"Could not check the Google generation status (HTTP {poll.status_code}).")
            op = poll.json()
        raise VideoGenerationError("Google generation is taking longer than 30 minutes. Check your provider history before retrying to avoid a duplicate charge.")
    except requests.RequestException as exc:
        raise VideoGenerationError("Could not reach Google Veo or download its result. Check the network and provider status.") from exc


def _runway(api_key: str, model: dict, data: dict, stage, cancelled) -> bytes:
    if not api_key.strip():
        raise VideoGenerationError("Add a Runway API key in Settings → Providers before generating.")
    headers = {"Authorization": f"Bearer {api_key}", "X-Runway-Version": "2024-11-06", "Content-Type": "application/json"}
    resolution = data["resolution"]
    ratio = "1280:720" if data["aspect_ratio"] == "16:9" else "720:1280"
    body = {"model": model["model"], "promptText": data["prompt"].strip(),
            "duration": int(data["duration_seconds"]), "ratio": ratio}
    if model["id"] == "runway-wan3":
        body["resolution"] = resolution
    if data.get("seed") is not None:
        body["seed"] = int(data["seed"])
    try:
        response = requests.post("https://api.dev.runwayml.com/v1/text_to_video", headers=headers,
                                 json=body, timeout=(15, 60))
        if not response.ok:
            raise VideoGenerationError(f"Runway rejected the request (HTTP {response.status_code}). Check the model settings, API credits and account limits.")
        task = response.json().get("id")
        if not task:
            raise VideoGenerationError("Runway did not return a task ID.")
        stage("Runway is generating the video · provider progress is not available", 0)
        deadline = time.monotonic() + 30 * 60
        while time.monotonic() < deadline:
            if cancelled():
                try:
                    requests.delete(f"https://api.dev.runwayml.com/v1/tasks/{task}", headers=headers, timeout=(5, 10))
                except requests.RequestException:
                    pass
                raise VideoGenerationCancelled("Generation cancelled.")
            poll = requests.get(f"https://api.dev.runwayml.com/v1/tasks/{task}", headers=headers, timeout=(15, 30))
            if not poll.ok:
                raise VideoGenerationError(f"Could not check the Runway task (HTTP {poll.status_code}).")
            result = poll.json()
            status = str(result.get("status", "")).upper()
            if status in {"SUCCEEDED", "COMPLETED"}:
                outputs = result.get("output") or []
                url = outputs[0] if outputs else None
                if not isinstance(url, str) or urlparse(url).scheme != "https":
                    raise VideoGenerationError("Runway completed without a secure video download link.")
                stage("Downloading generated video", 0)
                file_resp = requests.get(url, timeout=(15, 180))
                if not file_resp.ok:
                    raise VideoGenerationError("Could not download the video Runway generated. Try generating again.")
                return file_resp.content
            if status in {"FAILED", "CANCELED", "CANCELLED"}:
                raise VideoGenerationError("Runway generation failed. Check task details, account credits and content requirements.")
            time.sleep(4)
        raise VideoGenerationError("Runway generation is taking longer than 30 minutes. Check your provider history before retrying to avoid a duplicate charge.")
    except requests.RequestException as exc:
        raise VideoGenerationError("Could not reach Runway or download its result. Check the network and provider status.") from exc


def _comfyui(base_url: str, model: dict, data: dict, width: int, height: int, stage, cancelled) -> bytes:
    url = validate_local_comfy_url(base_url)
    path = workflow_path(model["id"])
    if not path.is_file():
        raise VideoGenerationError(f"Import the {model['name']} ComfyUI API workflow first. Open Setup in this panel for steps.")
    graph = _prepare_workflow(parse_workflow(path.read_bytes()), data, width, height)
    session = requests.Session()
    session.trust_env = False
    try:
        response = session.post(url + "/prompt", json={"prompt": graph}, timeout=(10, 30), allow_redirects=False)
        if not response.ok:
            raise VideoGenerationError(f"ComfyUI could not queue this workflow (HTTP {response.status_code}). Check the imported API workflow and installed nodes/models.")
        prompt_id = response.json().get("prompt_id")
        if not prompt_id:
            raise VideoGenerationError("ComfyUI did not return a prompt ID. Re-export the workflow using Save (API Format).")
        stage("Local model is generating on your computer · ComfyUI does not report a percentage", 0)
        deadline = time.monotonic() + 60 * 60
        while time.monotonic() < deadline:
            if cancelled():
                # Remove only this prompt if it has not started. ComfyUI's
                # /interrupt is global to that server and could stop a render
                # launched outside SceneForge, so never call it here.
                try:
                    session.post(url + "/queue", json={"delete": [prompt_id]}, timeout=(3, 5), allow_redirects=False)
                except requests.RequestException:
                    pass
                raise VideoGenerationCancelled("Local generation cancelled. A ComfyUI task already running may need to be stopped in ComfyUI.")
            history = session.get(f"{url}/history/{prompt_id}", timeout=(5, 15), allow_redirects=False)
            if history.ok:
                record = history.json().get(prompt_id, {})
                status = record.get("status", {}) or {}
                state = str(status.get("status_str", "")).lower()
                if state == "error":
                    raise VideoGenerationError("ComfyUI could not run the workflow. Check that its required models and custom nodes are installed.")
                outputs = record.get("outputs", {}) or {}
                files = []
                for output in outputs.values():
                    for kind in ("videos", "gifs", "images"):
                        for item in output.get(kind, []) or []:
                            filename = str(item.get("filename", ""))
                            if Path(filename).suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"}:
                                files.append(item)
                if files:
                    file_info = files[-1]
                    stage("Copying generated video into the SceneForge Media Pool", 0)
                    file_resp = session.get(url + "/view", params={"filename": file_info["filename"], "subfolder": file_info.get("subfolder", ""), "type": file_info.get("type", "output")}, timeout=(10, 180), allow_redirects=False)
                    if not file_resp.ok:
                        raise VideoGenerationError("ComfyUI finished, but SceneForge could not read its video output.")
                    return file_resp.content
                if state in {"success", "completed"}:
                    raise VideoGenerationError("ComfyUI completed, but this workflow did not save a video. Use a video Save node in the workflow.")
            time.sleep(2)
        raise VideoGenerationError("Local model is still running after one hour. Check the ComfyUI window before retrying.")
    except requests.RequestException as exc:
        raise VideoGenerationError("Could not communicate with the local ComfyUI server. Check that it is still running.") from exc
