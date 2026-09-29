<p align="center"><img src="docs/sceneforge-banner.svg" alt="SceneForge Studio — Your story, frame by frame" width="100%"></p>

# SceneForge Studio

**Free, open-source desktop editor for narrated documentary videos.** Turn a script, photos, clips and a voice into a finished film, one scene at a time, with film-style looks, captions that follow the narration, music, maps and more. Arabic and English are first-class.

[Download](#download) · [What it can do](#what-it-can-do) · [AI providers](#ai-providers) · [Build from source](#build-from-source) · [Contributing](CONTRIBUTING.md) · [License](#license)

![SceneForge Studio editor with an animated map route](docs/screenshots/editor-map-route.png)

## Download

Get the installer for your system from the **[latest release](https://github.com/EzioDEVio/SceneForge/releases/latest)**.

| System | File | First launch |
|---|---|---|
| **Windows 10/11** (64-bit) | `SceneForge-Studio-<version>-Windows-x64-Setup.exe` | Windows may show *"Windows protected your PC"*. Click **More info → Run anyway**. This appears because SceneForge is a free project without a paid code-signing certificate. |
| **Linux** (64-bit) | `.AppImage` (any distribution) or `.deb` (Ubuntu/Debian) | AppImage: make it executable (`chmod +x`) and run it. Deb: `sudo apt install ./SceneForge-Studio-*.deb` |
| **macOS** (Apple Silicon) | `.dmg` | Drag SceneForge to Applications. The first time, **right-click the app → Open → Open** (macOS blocks unsigned apps on a normal double-click). *macOS builds are experimental.* |

**Updates:** on Windows and Linux (AppImage) SceneForge downloads new versions in the background and asks to restart. On macOS it tells you when a new version is out and opens the download page. Help → *Receive beta updates* opts in to test versions.

**Your projects are safe across updates:** they live in your user folder, separate from the app, and the project database is backed up automatically before a new version opens it (Help → *Open project backups*; the last 5 are kept).

## What it can do

![Effects panel](docs/screenshots/effects-panel.png)

**Scenes and timeline** — scene-by-scene timeline with picture, narration, source-video-audio and text lanes; drag-and-drop images, videos, audio and whole folders; 42 transitions including film burn, wind and clock wipe, with live previews; keyboard shortcuts; undo/redo; split scenes; multi-select and batch apply; ruler snapping and named markers; linked source video/audio edge trimming for eligible single-video scenes.

**Pictures and motion** — Ken Burns zoom and pan with smooth easing; **3D photo (parallax)**, which gives still photos depth; **picture-in-picture overlays** you drag and resize on the preview, with borders, rounded corners, shadows, animations, glide paths and green screen; **split screen** (side by side, top & bottom, three panels, 2×2); **animated map routes** you draw by clicking on the preview; video clip speed, slow-motion ramps and freeze frames; **restore old photo** (dust, grain, contrast and sharpness for archive scans).

**Looks and filters** — 18 looks including VHS and full-frame glitch; **Old film** (scratches, dust, hair, flicker, gate weave, 16/18 fps projector motion, black & white or sepia, projector sound); colour sliders, **colour wheels**, split toning and **.cube LUT import** (3D, 1D and DaVinci Resolve shaper LUTs); camera shake with impact zoom; spotlight; blur or pixelate areas to hide faces and names; light leaks; Teal & Amber, Pastel and Bleach Bypass color filters.

**Text** — captions with correct Arabic right-to-left layout; automatic captions from narration or video sound (free local Whisper, with optional cloud services); **24 caption styles** and word-by-word timing; animated title layers; typewriter reveal with sound.

![Word-by-word captions](docs/screenshots/word-by-word-captions.png)

**Sound** — narration from AI voices or your own recordings; trim, volume, fades and waveform editing; voice effects (clean up, 1940s radio, telephone); background music that loops and **ducks under narration** automatically; **sync scene cuts to the beat**; loudness levelling for YouTube (-14 LUFS); film countdown leader.

**Export** — platform presets for YouTube, TikTok/Reels/Shorts and Instagram; advanced resolution up to 4K, frame rate, quality and format controls; MP4, H.265, WebM, ProRes, GIF, MP3 and WAV; SRT/VTT caption files. Video sound is preserved and can be adjusted per clip.

**Share and overlays** — after export, a local-first Share dialog offers download, file-location access in the desktop app, and upload steps for YouTube, TikTok, Instagram and Facebook. Direct account uploads are not included. Overlays also include a searchable, categorized emoji/sticker picker; selected symbols use the standard image-overlay editor and render pipeline.

**Text-to-video (0.7.0 WIP)** — a dark, high-contrast Generate Video workspace offers step-by-step local ComfyUI/model guidance, VRAM-aware model suggestions, Google/Runway key instructions, and paid estimates that scale to 1–3 candidate videos. Compare finished takes and add the selected one to a new or existing scene. Image Studio also supports 1–3 selectable options. Existing clip audio, captions, styles, effects and overlays remain available. Cloud video requests require an explicit total-cost confirmation in the UI and backend.

The features above include the **0.6.0 and 0.7.0 work in progress** from source. The latest published installer may not include them yet; check the release notes for the version you download.

## AI providers

AI is optional. You can build a complete video from your own photos, clips and recordings without any account.

| Purpose | Cloud (your own account/key) | Local (free, on your computer) |
|---|---|---|
| Images | OpenAI, Google Gemini, Cloudflare Workers AI, Hugging Face | Stable Diffusion via AUTOMATIC1111 (point SceneForge at its folder: *AI Engines* menu) |
| Voice | ElevenLabs (with exact word timing), Together AI | Chatterbox and Kokoro (separate services); espeak is an optional basic fallback with its own install |
| Captions | OpenAI Whisper or ElevenLabs Scribe | Faster-Whisper (model download required once) |
| Text-to-video | Google Veo 3.1 and Runway Gen-4.5 / WAN 3.0 APIs | ComfyUI workflows for LTX-2.5, Wan 2.1, Wan 2.2 and compatible custom workflows |

### Text-to-video model choices and prices

The 0.7.0 WIP catalog below shows the provider's published USD rate per generated second and estimates the selected clip's cost before a request starts. Users can generate 1–3 video or image options to compare. Cloud video estimates and consent cover the full candidate count; hosted image providers show that each result may incur a separate charge. Prices were checked on **2026-09-28** and can change; provider billing, taxes, account credits, retries and regional terms can affect the final charge. Local generation has no API fee, but uses the user's hardware and electricity. Review each model's license before publishing or using output commercially.

| Provider and model | Published price | Current output options in SceneForge |
|---|---:|---|
| Google Veo 3.1 Lite | $0.05/sec at 720p; $0.08/sec at 1080p | 4, 6 or 8 sec; 16:9 or 9:16; 1080p only at 8 sec |
| Google Veo 3.1 Fast | $0.10/sec at 720p; $0.12/sec at 1080p; $0.30/sec at 4K | 4, 6 or 8 sec; 16:9 or 9:16; 1080p/4K only at 8 sec |
| Google Veo 3.1 Standard | $0.40/sec at 720p or 1080p; $0.60/sec at 4K | 4, 6 or 8 sec; 16:9 or 9:16; 1080p/4K only at 8 sec |
| Runway Gen-4.5 | $0.12/sec (12 credits/sec at $0.01 per credit) | 2–10 sec at 720p; 16:9 or 9:16 |
| Runway WAN 3.0 | $0.05/sec at 480p; $0.10/sec at 720p; $0.20/sec at 1080p | 2–30 sec; 16:9 or 9:16; native audio |

Official price references: [Google Veo pricing](https://ai.google.dev/gemini-api/docs/pricing#veo), [Google Veo API options](https://ai.google.dev/gemini-api/docs/veo), [Runway API pricing](https://docs.dev.runwayml.com/guides/pricing/), [Runway API changelog](https://docs.dev.runwayml.com/api-details/api_changelog/).

Key setup guides: [Google AI Studio key instructions](https://ai.google.dev/gemini-api/docs/api-key), [Google AI Studio API keys](https://aistudio.google.com/app/apikey), [Runway API account/key/credit setup](https://docs.dev.runwayml.com/guides/setup/), [Runway Dev console](https://dev.runwayml.com/). SceneForge stores provider keys through the operating system credential store.

**Local model catalog:** LTX-2.5 Fast, Wan 2.1 T2V 1.3B, Wan 2.2 TI2V 5B, Wan 2.2 T2V A14B, plus a Custom ComfyUI workflow option. Models differ in quality, speed, audio, resolution and GPU needs. For an 8 GB card, ComfyUI says its Wan 2.2 5B workflow should fit with native offloading; begin at 480p. Wan 2.1 T2V 1.3B at 480p is a lighter fallback. A desktop GeForce RTX 4090 lists 24 GB; the 4090 Laptop is listed at 16 GB, so if SceneForge detects 8 GB, check the actual GPU and available memory before downloading. See the [Wan 2.2 setup](https://docs.comfy.org/tutorials/video/wan/wan2_2), [NVIDIA memory matrix](https://docs.nvidia.com/nim/visual-genai/latest/support-matrix.html) and [LTX ComfyUI setup](https://docs.ltx.io/open-source-model/integration-tools/comfy-ui).

**Local setup:** The generator now has a step-by-step guide, direct links, ComfyUI connection check and optional GPU/VRAM-based model suggestion. ComfyUI, model weights, required custom nodes and API-format workflow files are still installed separately; they are not bundled or downloaded automatically by SceneForge. Start ComfyUI, connect its loopback address under **Settings → Providers**, download the matching model and workflow, export with **Save (API Format)**, then import the JSON into Generate Video. Custom ComfyUI nodes execute inside ComfyUI with the user's permissions, so import workflows and nodes from sources you trust. Local custom dimensions must be multiples of 16. Cloud providers expose only their supported sizes, ratios and durations. Google and Runway setup panels link to key creation pages and explain adding a key under **Settings → Providers**.

**Multiple options:** The generator creates candidates sequentially. Each finished video is previewable and separately saved in the Media Pool; select one before adding it to the timeline. SceneForge retains completed options if a later take fails or is cancelled. Image Studio similarly shows a 1–3 option chooser before attaching an image to the scene.

**Remote GPU direction:** Vast.ai has not been connected to the app. The [remote GPU feasibility note](docs/VAST_GPU_RELAY_PROPOSAL.md) proposes a text-to-video benchmark and a separate, opt-in relay if the all-in compute/storage/transfer costs are worthwhile.

**What installs:** Source setup needs Python, Node.js and FFmpeg. The Windows desktop installer bundles the app, private backend runtime and FFmpeg so end users do not need those tools installed separately. Optional Chatterbox/Kokoro narration servers and Stable Diffusion image generation are separate installs today; their large models are not bundled. The Whisper model downloads automatically the first time captions run. Rendering and exports use local FFmpeg; cloud features only run when you choose a provider and supply its key.

Keys are stored in your operating system's credential store (Windows Credential Manager, macOS Keychain, Linux Secret Service), never in the project files.

**Automatic captions:** Local Faster-Whisper transcription is included in the backend dependencies. Its multilingual model downloads once when first used (internet required for that first download), then runs on the user's CPU without an API key or network connection. ElevenLabs and OpenAI remain optional cloud services.

## Build from source

Requirements: Python 3.11+, Node.js 20+, and FFmpeg (only for running from source; the desktop installer bundles its backend runtime and FFmpeg). Local captioning downloads a Whisper model on first use. The optional Chatterbox/Kokoro speech servers and Stable Diffusion image-generation server remain separate installs; the desktop installer does not bundle these large models or services.

**Windows**
```bat
git clone https://github.com/EzioDEVio/SceneForge.git
cd SceneForge
scripts\setup.bat
scripts\start.bat
```
Then open http://127.0.0.1:8000.

**macOS / Linux**
```bash
git clone https://github.com/EzioDEVio/SceneForge.git && cd SceneForge
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
npm --prefix frontend ci && npm --prefix frontend run build
cd backend && ../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**Build the desktop installers yourself**
```bash
pip install -r desktop/requirements-build.txt
npm --prefix frontend ci && npm --prefix frontend run build
npm --prefix desktop ci
python desktop/scripts/fetch_ffmpeg.py        # downloads and verifies FFmpeg for your OS
python desktop/scripts/build_backend.py       # bundles the Python backend
npm --prefix desktop run dist:win             # or dist:mac / dist:linux
```

## Releasing (maintainers)

1. Set the version in `desktop/package.json` (e.g. `0.3.1`, or `0.3.1-beta.1` for a beta).
2. Commit, then tag and push: `git tag v0.3.1 && git push origin v0.3.1`.
3. The **Release** workflow tests everything, builds Windows, Linux and macOS installers on GitHub's machines, and attaches them to a **draft** release.
4. Review the draft and click **Publish release**. Only then do users' apps offer the update.

## Architecture

| Folder | What it is |
|---|---|
| `frontend/` | React + TypeScript editor |
| `backend/app/` | FastAPI server, SQLite database, FFmpeg rendering (`render/`), providers |
| `desktop/` | Electron shell, updater, packaging and build scripts |
| `assets/` | Bundled fonts and sounds |
| `tests/` | Integration tests that render real video and measure the result |

## Roadmap

- [x] Scene editor, timeline, transitions, captions, export
- [x] Film looks, LUTs, colour grading, overlays, map routes, split screen, 3D photos
- [x] Word-by-word captions, music ducking, beat sync, loudness
- [x] Desktop installers for Windows, Linux and macOS with automatic updates
- [ ] AI providers workspace and model manager for optional local speech and image models
- [ ] Colorize black & white photos; automatic subject detection for 3D photos (local AI models)
- [ ] Signed installers (free open-source signing programmes are being considered)

## License

SceneForge Studio is free software: you can redistribute it and/or modify it under the terms of the **GNU General Public License v3.0 or later** as published by the Free Software Foundation. See [LICENSE](LICENSE).

It is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY. Bundled components (FFmpeg, Electron, Python libraries, Noto fonts) keep their own licenses; see [desktop/THIRD_PARTY.md](desktop/THIRD_PARTY.md). AI models and cloud services are not part of SceneForge and have their own terms.

Copyright © 2026 EzioDEVio and SceneForge contributors.
