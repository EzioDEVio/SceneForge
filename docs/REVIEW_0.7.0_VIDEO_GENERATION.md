# SceneForge 0.7.0 WIP: Text-to-video review

**Source branch:** `chatgpt/0.7.0-video-generation`

**App version:** `0.7.0-wip.1`

**Status:** unreleased work in progress; provider output has not been live-tested in this environment.

## What changed

The app has a separate **Generate video** workspace opened from the editor toolbar or File menu. It preserves the existing SceneForge editor and its AI Engines/Help entry points. Users choose a local or cloud model, enter a prompt and optional local negative prompt, select supported quality/aspect/duration settings, see published per-second rates and the selected-job estimate, and confirm before a cloud generation request is accepted.

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

The configured local endpoint accepts HTTP loopback only (`127.0.0.1`, `localhost`, or `::1`); requests bypass proxy environment variables. Imported workflows must be ComfyUI **Save (API Format)** JSON, at most 2 MB. Custom nodes execute in ComfyUI with the user's permissions; use workflows and nodes from sources the user trusts.

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

Official references: [Google Veo pricing](https://ai.google.dev/gemini-api/docs/pricing#veo), [Google Veo API](https://ai.google.dev/gemini-api/docs/veo), [Runway pricing](https://docs.dev.runwayml.com/guides/pricing/), [Runway API changelog](https://docs.dev.runwayml.com/api-details/api_changelog/), [Wan 2.2 ComfyUI guide](https://docs.comfy.org/tutorials/video/wan/wan2_2), [LTX ComfyUI guide](https://docs.ltx.io/open-source-model/integration-tools/comfy-ui).

## Setup for users

1. Install/start ComfyUI separately and set its local URL under **Settings → Providers**.
2. Install the chosen model weights and matching workflow, including any required custom nodes.
3. Open the workflow in ComfyUI and export it with **Save (API Format)**.
4. In SceneForge, select that local model and import the workflow JSON.
5. For cloud providers, add the provider key in **Settings → Providers**; Google and Runway may require account billing/credits.
6. Generate and insert the clip, then use Text → Auto captions if the clip has speech/audio. Silent models can use audio added in SceneForge's Audio tools.

Model files and separate ComfyUI requirements are not included in the Windows, macOS or Linux base installer. See README for the per-model links and version limitations.

## Implementation map

- `backend/app/providers/video_generation.py`: catalog, estimates, request validation, ComfyUI workflow transforms, Google Veo and Runway API adapters.
- `backend/app/api/video_generation.py`: model catalog, local status/workflow import, paid confirmation and job creation endpoints.
- `backend/app/api/providers.py`: stores local ComfyUI profile and cloud keys in the existing provider settings/credential system.
- `backend/app/workers/jobs.py`: background provider generation, cancellation, FFprobe validation, asset record and generation metadata.
- `frontend/src/VideoGenerationPanel.tsx`: separate interface, cost disclosure, setup, progress, preview, timeline insertion and caption handoff.
- `frontend/src/App.tsx`: toolbar/File menu entry point, existing timeline insertion and Text panel integration.
- `tests/integration/test_video_generation.py`: server-side catalog, price estimate, Google/Runway/ComfyUI request adapter mocks, provider validation, loopback security, workflow mapping/import, and paid-confirmation coverage.
- `frontend/tests/video_generation.mjs`: mocked UI checks for custom local dimensions, generated asset insertion, caption-to-Text handoff, published cloud rates and paid consent.

## Verification in this workspace

- `npm run build` — passed (TypeScript and Vite; current editor bundle is 511.58 kB minified, over Vite's advisory threshold).
- `npm test` — passed: 191 component checks, 19 unit checks, 2 new text-to-video UI flows, 6 Share dialog checks.
- `npm test` in `desktop/` — passed: 14 tests.
- `python -m compileall -q backend/app tests/integration/test_video_generation.py` — passed.
- `git diff --check` — passed.
- `tests/integration/test_video_generation.py` is included in `.github/workflows/checks.yml`, but could not run locally. This workspace's Python has no backend dependencies such as Requests/FastAPI/SQLAlchemy, and package downloads were unavailable. CI installs `backend/requirements.txt`.
- No real ComfyUI model, Google Veo call or Runway call was made; all UI generation flow tests mock the API. No installer was built or manually launched during this feature work.
- Provider progress is generally unavailable, so SceneForge shows an indeterminate active-job bar. Cancelling a queued ComfyUI task removes that task; a ComfyUI generation already running may need to be stopped in ComfyUI. Canceling an accepted Google request does not promise to stop the remote task.

## Remaining acceptance work

- Run CI and fix any environment-specific backend failures.
- On a supported machine, import each built-in ComfyUI API workflow and test prompt/dimensions/seed, audio output, cancel behavior, and local generated-file transfer.
- Test Google and Runway with user-owned valid credentials and provider billing; verify returned file download, actual dimensions/duration/audio, published price and failure/cancellation errors.
- Add generated video to both an empty and populated project, apply captions/effects/overlays/audio, render/export, and open outputs in target-platform players.
- Build the Windows, Linux and macOS branch artifacts and do clean-install acceptance. A pushed branch build is a temporary Actions artifact, not a published release.
