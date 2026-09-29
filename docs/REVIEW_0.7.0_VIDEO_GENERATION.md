# SceneForge 0.7.0 WIP: Text-to-video review

**Source branch:** `chatgpt/0.7.0-video-generation`

**App version:** `0.7.0-wip.2`

**Status:** unreleased work in progress; provider output has not been live-tested in this environment.

## What changed

The app has a separate **Generate video** workspace opened from the editor toolbar or File menu. It preserves the existing SceneForge editor and its AI Engines/Help entry points. The generator now uses a higher-contrast graphite palette, stronger field labels, and visible selected-engine/model states. Setup links call the Electron external-link bridge, so they open in the user's browser in the desktop app instead of being denied as popup windows.

Users can select 1, 2 or 3 outputs for both video and image generation. Video candidates are produced as sequential independent provider requests, saved as separate Media Pool assets, displayed for preview, and the selected take is the one sent to the timeline. A fixed video seed increments per take; random seeds remain random. Hosted video cost estimates and the required consent scale by candidate count, and changing duration, quality or count clears prior consent. If a later take fails or the user cancels, already completed options remain available. Image Studio generates multiple candidates sequentially and prompts users to acknowledge that hosted image providers may bill each result; a fixed Stable Diffusion seed advances per candidate.

The local setup panel gives a step-by-step ComfyUI/model/workflow guide, clickable install/model references, and an optional NVIDIA `nvidia-smi` hardware check. It recommends a model based on detected VRAM. Paid Google and Runway choices provide account/API-key steps and direct links to their provider consoles.

When generation completes, SceneForge validates the returned video with FFprobe, stores it as a normal generated project asset, and previews it in the panel. The user can add it inside the selected scene or create a scene after the selected one. Existing clip sound, editing, caption, effects and overlay features are then available. **Generate captions & open Text** uses the existing local auto-caption path and closes the generator after it opens Text, so the timed caption segments can be edited.

## Provider catalog

### Local through ComfyUI

| Choice | Configured limits / notes |
|---|---|
| LTX-2.5 Fast | 480p, 720p or 1080p; 1–20 sec; native audio. LTX documentation describes high system requirements (32 GB+ VRAM, 32 GB RAM, 100 GB disk). |
| Wan 2.1 T2V 1.3B | 480p; 1–5 sec; silent output. |
| Wan 2.2 TI2V 5B | 480p or 720p; 1–5 sec; silent output. ComfyUI documents around 8 GB VRAM with native offloading; more VRAM improves performance. |
| Wan 2.2 T2V A14B | 480p or 720p; 1–5 sec; silent output; substantially larger GPU-memory requirements. |
| Custom ComfyUI workflow | Compatible imported text-to-video API graphs; 1–30 sec; common prompt, dimensions, frame count and seed fields are mapped. Specialized workflows may need edits in ComfyUI. Whether it emits audio depends on the imported workflow. |

All local choices expose 16:9, 9:16, 1:1 and custom dimensions. Custom width and height must each be 256–4096 pixels and divisible by 16. Local generation has no provider API charge, but uses the user's GPU/CPU, electricity, storage and the model's license. SceneForge does not bundle ComfyUI, weights, custom nodes or workflows.

For an 8 GB GPU, the official ComfyUI Wan 2.2 guide says the TI2V 5B workflow should fit with native offloading; start at 480p and expect slower generation. Wan 2.1 T2V 1.3B at 480p is the lighter fallback. A desktop GeForce RTX 4090 specification lists 24 GB; NVIDIA lists 16 GB for the RTX 4090 Laptop, so an 8 GB reading may be another GPU or available memory after reservation. Check the detected model/VRAM in the generator or with `nvidia-smi` before choosing a model. These recommendations are starting points, not guarantees.

The configured local endpoint accepts HTTP loopback only (`127.0.0.1`, `localhost`, or `::1`); requests bypass proxy environment variables. Imported workflows must be ComfyUI **Save (API Format)** JSON, at most 2 MB. Custom nodes execute in ComfyUI with the user's permissions; use workflows and nodes from sources the user trusts.

Vast.ai remote GPU generation is not part of the current build. See the [separate feasibility note](VAST_GPU_RELAY_PROPOSAL.md) for an opt-in text-to-video benchmark, all-in cost measurements and a suggested remote-worker design.

### Paid APIs

Prices are USD per generated second, checked on **2026-09-28**. The generator lists the rates for each model and resolution and calculates the selected clip estimate. Rates can change; the estimate does not include possible tax or provider billing differences.

| Provider/model | Published rate | Configured options |
|---|---:|---|
| Google Veo 3.1 Lite | $0.05/sec 720p; $0.08/sec 1080p | 4/6/8 sec; 16:9 or 9:16; 1080p requires 8 sec |
| Google Veo 3.1 Fast | $0.10/sec 720p; $0.12/sec 1080p; $0.30/sec 4K | 4/6/8 sec; 16:9 or 9:16; 1080p/4K require 8 sec |
| Google Veo 3.1 Standard | $0.40/sec 720p/1080p; $0.60/sec 4K | 4/6/8 sec; 16:9 or 9:16; 1080p/4K require 8 sec |
| Runway Gen-4.5 | $0.12/sec (12 credits/sec × $0.01) | 2–10 sec, 720p; 16:9 or 9:16 |
| Runway WAN 3.0 | $0.05/sec 480p; $0.10/sec 720p; $0.20/sec 1080p | 2–30 sec; 16:9 or 9:16; native audio |

The settings panel stores Google/Runway keys through the existing OS credential store. The generator blocks cloud start until the chosen profile is configured and the user confirms the displayed estimate. The backend checks that confirmation as well.

Official references: [Google Veo pricing](https://ai.google.dev/gemini-api/docs/pricing#veo), [Google Veo API](https://ai.google.dev/gemini-api/docs/veo), [Google AI Studio API keys](https://aistudio.google.com/app/apikey), [Google current key instructions](https://ai.google.dev/gemini-api/docs/api-key), [Runway pricing](https://docs.dev.runwayml.com/guides/pricing/), [Runway developer console](https://dev.runwayml.com/), [Runway API key setup and billing](https://docs.dev.runwayml.com/guides/setup/), [Runway API changelog](https://docs.dev.runwayml.com/api-details/api_changelog/), [ComfyUI install guide](https://docs.comfy.org/get_started/introduction), [Wan 2.2 ComfyUI guide](https://docs.comfy.org/tutorials/video/wan/wan2_2), [NVIDIA GPU memory support matrix](https://docs.nvidia.com/nim/visual-genai/latest/support-matrix.html), [LTX ComfyUI guide](https://docs.ltx.io/open-source-model/integration-tools/comfy-ui).

## Setup for users

1. Open the generator's **Local setup · step by step** guide and install/start ComfyUI from its official instructions.
2. Follow the selected model's guide, download its model files, and load or download the matching workflow.
3. Set the ComfyUI loopback address under **Settings → Providers**, then click **Check again**.
4. Export the workflow as **Save (API Format)** and import it in SceneForge.
5. For Google or Runway, open the generator's **Step-by-step API key setup** guide; create a key, review access/credits, and save it under **Settings → Providers**.
6. Generate 1–3 takes, compare them, add a selected clip to the timeline, and use Text → Auto captions if it has speech/audio.

Model files and separate ComfyUI requirements are not included in the Windows, macOS or Linux base installer. See README for the per-model links and version limitations.

## Implementation map

- `backend/app/providers/video_generation.py`: catalog, estimates, request validation, ComfyUI workflow transforms, Google Veo and Runway API adapters.
- `backend/app/api/video_generation.py`: model catalog, local status/GPU detection/workflow import, paid confirmation and job creation endpoints.
- `backend/app/api/providers.py`: stores local ComfyUI profile and cloud keys in the existing provider settings/credential system.
- `backend/app/workers/jobs.py`: sequential candidate generation, cancellation, partial-result retention, FFprobe validation, asset records and per-candidate metadata.
- `frontend/src/VideoGenerationPanel.tsx`: high-contrast interface, working external links, setup guides, VRAM recommendation, cost disclosure, candidate preview/selection, timeline insertion and caption handoff.
- `frontend/src/App.tsx`: 1–3 candidate generation and selection in AI Image Studio.
- `frontend/src/App.tsx`: toolbar/File menu entry point, existing timeline insertion and Text panel integration.
- `tests/integration/test_video_generation.py`: server-side catalog, GPU guidance, price estimate, Google/Runway/ComfyUI request adapter mocks, provider validation, loopback security, workflow mapping/import, candidate-count validation, and paid-confirmation coverage.
- `frontend/tests/video_generation.mjs`: mocked UI checks for setup-link bridge, custom dimensions, candidate selection, timeline insertion, caption handoff, scaled cloud estimate and paid consent.

## Verification in this workspace

- `npm run build` — passed (TypeScript and Vite; current editor bundle is 511.58 kB minified, over Vite's advisory threshold).
- `npm test` — passed: 191 component checks, 19 unit checks, 2 new text-to-video UI flows, 6 Share dialog checks.
- `npm test` in `desktop/` — passed: 14 tests.
- `python -m compileall -q backend/app tests/integration/test_video_generation.py` — passed.
- `git diff --check` — passed.
- The GitHub Actions Release matrix on feature commit `17de02742088315c00cbd7cd6f9b7e2d4a76c872` passed for Windows, Linux and Apple Silicon macOS. The jobs built installer artifacts and passed packaged-backend render checks; Windows also passed silent install and app startup, and Linux/macOS passed their packaged editor end-to-end checks. macOS remains marked experimental in the workflow.
- The feature-specific `tests/integration/test_video_generation.py` is included in `.github/workflows/checks.yml`. It could not run locally because this workspace's Python lacks backend dependencies such as Requests/FastAPI/SQLAlchemy. CI installs `backend/requirements.txt`; see the branch Actions page for the current result.
- No real ComfyUI model, Google Veo call or Runway call was made; provider generation is still untested against live services. The packaged installer checks exercise startup and editing/rendering, not paid or local model generation.
- Provider progress is generally unavailable, so SceneForge shows an indeterminate active-job bar. Cancelling a queued ComfyUI task removes that task; a ComfyUI generation already running may need to be stopped in ComfyUI. Canceling an accepted Google request does not promise to stop the remote task.

## Remaining acceptance work

- Review the source-branch backend integration run and fix any environment-specific failures.
- On a supported machine, import each built-in ComfyUI API workflow and test prompt/dimensions/seed, audio output, cancel behavior, and local generated-file transfer.
- Test Google and Runway with user-owned valid credentials and provider billing; verify returned file download, actual dimensions/duration/audio, published price and failure/cancellation errors.
- Add generated video to both an empty and populated project, apply captions/effects/overlays/audio, render/export, and open outputs in target-platform players.
- Manually install and test the Windows, Linux and macOS branch artifacts on user machines. A pushed branch build is a temporary Actions artifact, not a published release.
