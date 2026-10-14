# SceneForge Studio — Technical Handoff

**Document status:** RC4 handoff
**Repository:** `https://github.com/EzioDEVio/SceneForge`
**Active development branch:** `desktop-alpha/core`
**Current desktop package:** `SceneForge Desktop Alpha 0.2.0-rc.4`
**Primary purpose:** local-first creation of narrated, image-led documentary and educational videos.

## 1. What SceneForge is

SceneForge is a local video-story editor. A project is divided into ordered parts (scenes). Each part can contain images or video, narration, captions, title overlays, motion, effects, transitions, and a duration. The application renders individual scenes for inspection and exports the ordered project as one MP4.

The product is designed for documentary and educational videos, including Arabic narration and bilingual scripts. It runs locally with a Python/FastAPI backend and a React/TypeScript editor. Cloud providers are optional and use credentials supplied by the user. Media, projects, rendered files, and provider configuration are stored locally.

SceneForge is currently a **scene assembly editor**, rather than a full nonlinear editor such as DaVinci Resolve. The timeline represents complete scene clips and their relationships. It does not yet provide independent arbitrary video tracks, waveform editing, frame-accurate trimming, or a full compositing graph.

## 2. Main capabilities

- Create, search, rename, and delete projects.
- Create, reorder, rename, and delete scenes.
- Upload images, videos, and audio.
- Maintain a Media Pool so imported media can be reviewed before insertion.
- Generate images through configured providers or a local Stable Diffusion API.
- Add scene narration by local Chatterbox, Kokoro, hosted ElevenLabs, or uploaded audio.
- Edit narration text and title/text overlays after creation.
- Add captions and typewriter animation with optional keystroke audio.
- Apply image fitting, crop, focal movement, zoom, pan, close-up, diagonal, push/pull, and combined motion presets.
- Apply color, film, glitch, grain, blur, vignette, and other effects.
- Set incoming transitions between scenes.
- Render a scene preview and export all eligible scenes as one movie.
- Use a desktop shell with save-confirmed close behavior and an NSIS Windows installer.

## 3. Repository structure

```text
SceneForge/
├── backend/
│   ├── app/
│   │   ├── api/                 FastAPI routes
│   │   ├── db/                  SQLAlchemy models and database
│   │   ├── providers/           Image and speech adapters
│   │   ├── render/              FFmpeg rendering pipeline
│   │   ├── security/            Credential vault and upload validation
│   │   ├── workers/             Render jobs and progress
│   │   └── main.py              Application startup and routing
│   ├── desktop_entry.py         Packaged backend entrypoint
│   └── requirements.txt         Runtime Python dependencies
├── frontend/
│   ├── src/App.tsx              Main editor and panels
│   ├── src/MediaPool.tsx        Media browser and insertion workflow
│   ├── src/ProjectTimeline.tsx  Timeline, tracks, transport and transitions
│   ├── src/FramingControls.tsx  Crop and focal-motion controls
│   ├── src/TitleDesigner.tsx    Title-card creation
│   ├── src/api.ts               Typed HTTP client
│   └── tests/editor.mjs         Component-level UI checks
├── desktop/
│   ├── main.cjs                 Electron main process
│   ├── backend-process.cjs      Packaged backend lifecycle
│   ├── close-controller.cjs     Save/close sequencing
│   ├── scripts/build_backend.py Backend bundling
│   ├── scripts/fetch_ffmpeg.py  FFmpeg retrieval
│   └── tests/                   Desktop lifecycle tests
├── services/
│   ├── chatterbox/              Chatterbox API container
│   └── compose.yaml              Optional local service composition
├── assets/                      Fonts and sound assets
├── scripts/                     Windows setup, start, voice, and update scripts
├── tests/integration/           Backend, rendering, provider, security tests
├── docs/                        Effects, validation, desktop and architecture docs
└── README.md                    User-facing project overview
```

## 4. Runtime architecture

```text
React editor
    │ HTTP + SSE
    ▼
FastAPI backend
    ├── SQLite project database
    ├── local media/data directory
    ├── provider adapters
    ├── render worker
    └── FFmpeg / ffprobe

Optional external processes
    ├── AUTOMATIC1111 Stable Diffusion API :7860
    ├── Chatterbox service                 :8881
    ├── Kokoro service                     :8880
    └── hosted image/TTS APIs
```

The frontend edits scenes through JSON API requests. Long-running render and generation tasks return a job identifier. The frontend subscribes to job progress over Server-Sent Events, polls job state when needed, and updates the relevant scene or project when the job completes.

The backend validates inputs, writes project state to SQLite, stores media under the configured data directory, and calls FFmpeg in controlled subprocesses. Render inputs are assembled from scene media, motion parameters, effects, captions, transitions, and the selected narration take.

## 5. Data and persistence

The default data root is `backend/data`. It contains the SQLite database, media files, generated audio, generated images, rendered scene files, and exported movies. Set `SCENEFORGE_DATA_DIR` to relocate it.

Project records include projects, scenes, media/assets, voice takes, provider profiles, jobs, and image-generation history. A newly generated or uploaded narration take is accepted automatically and previous takes for the scene are unaccepted. Users can delete unwanted takes from the Audio panel.

Deleting a project removes its database records while media files may remain on disk for recovery and deduplication. Back up the complete data directory before upgrades or cleanup. Do not back up only the SQLite file.

Provider secrets are stored through the platform credential vault where available: Windows Credential Manager, macOS Keychain, or Linux Secret Service. The database stores references rather than raw keys. If vault access is unavailable, the application fails closed and asks the user to re-enter the credential; it does not silently use a plaintext fallback.

## 6. Editor components

### Project library

The library lists saved projects and supports search, opening, renaming, and confirmed deletion. Project deletion is intentionally separate from media-pool deletion so users can preserve source files.

### Scene editor

Each scene has a title, visual media, narration script, selected narration take, timing mode, duration, media fit, motion, effects, text layers, and incoming transition. The preview tab is an editing approximation. The rendered-scene tab shows output from the real renderer.

### Media Pool

Files are imported into the pool first. Selected files can then be added to the selected scene or used to create new scenes. This prevents a folder import from unexpectedly becoming an uncontrolled timeline sequence. Media cards retain thumbnails and source metadata.

### Motion and framing

Motion includes static, zoom, pan, close-up, diagonal rise/descend, push-and-pan, pull-and-pan, and combined presets. Crop and focal framing provide numeric values, sliders, reset actions, draggable crop bounds, and focal-point selection. Final framing should be verified by rendering because the editor preview is a motion sketch.

### Effects

Effects are represented as scene settings and translated into FFmpeg filters or renderer operations. Implemented effects include color looks, film grain, vignette, blur, and full-frame glitch behavior. The effects guide documents additional planned aged-film treatments such as scratches, dust, gate weave, flicker, light leaks, and film burn.

### Text and title cards

Text overlays support Arabic-capable fonts, size, color, alignment, position, outline, shadow, animation, entrance/exit timing, and typewriter behavior. Title cards can be created with chapter, lower-third, typewriter, and headline presets, solid or gradient backgrounds, and durations from 0.5 to 60 seconds. Existing text layers can be edited without deleting the scene. A title-card background is baked into the generated card; replacing that background currently requires creating a replacement card.

### Audio and narration

The Audio panel supports local services, hosted ElevenLabs, uploaded recordings, auditioning, generating takes, selecting a take, deleting a take, and choosing no narration. Narration text is sent as continuous text; typewriter animation is a separate visual layer.

For local services, Chatterbox is the preferred multilingual and Arabic option. Kokoro is lightweight but does not support Arabic. Docker Desktop is currently used by the Windows Chatterbox/Kokoro launchers; a user can also point SceneForge at a compatible local service.

For ElevenLabs, the API key is stored locally in the credential vault. Voice discovery returns voice ID plus readable name and available language, accent, gender, age, description, and preview metadata. The voice ID remains an internal value used for synthesis.

### Timeline

The timeline has picture, narration, and title lanes, a ruler, scene thumbnails, transport controls, zoom, scene reordering, duration controls, and incoming transitions. Image scene duration can be changed by dragging or using duration controls. Transitions attach to the incoming scene and move when scenes are reordered.

The timeline does not yet include independent audio waveform editing, arbitrary clip trimming, unlimited tracks, or frame-accurate NLE operations. Full-project playback is represented by the rendered export; the editor transport is still scene-assembly oriented.

## 7. Rendering and export logic

1. Validate the project and identify scenes with usable visual media.
2. Resolve each scene duration from fixed timing or the selected narration take.
3. Build a scene render plan containing media, fit, crop, motion, effects, text, captions, and audio.
4. Render each scene through FFmpeg and the text/typewriter renderer.
5. Apply the incoming transition at each scene boundary.
6. Crossfade narration where the transition requires overlap.
7. Concatenate rendered scenes into the final MP4.
8. Save the export as a local asset and expose preview/download actions.

Empty scenes remain visible in the timeline and can be skipped only through an explicit export option. Frame rounding and actual FFmpeg output determine final duration, so timeline estimates can differ slightly from the exported file.

## 8. Image providers

| Provider | Use | Credential/runtime |
|---|---|---|
| OpenAI | Hosted image generation | User API key; usage billed by OpenAI |
| Google Gemini | Hosted image generation | User API key and supported image model |
| Cloudflare Workers AI | Hosted FLUX generation | API token and account ID |
| Hugging Face | Routed hosted generation | HF token and model availability |
| Together | Hosted image generation | Together API key and image model |
| Local Stable Diffusion | Local image generation | AUTOMATIC1111 WebUI with `--api` |
| Anthropic | Image analysis and prompt assistance | Claude API; not an image-generation endpoint |

The local Stable Diffusion integration starts an existing AUTOMATIC1111 installation when configured. It does not install the model or download checkpoints. The API must be available at `http://127.0.0.1:7860` and the WebUI must be started with `--api`. The image drawer provides start/retry, readiness check, and startup-log controls. A user may disable automatic start with `SCENEFORGE_SD_AUTOSTART=0`.

## 9. Voice providers

| Provider | Languages | Requirements |
|---|---|---|
| Chatterbox | Multilingual, including Arabic | Local service/container and model; Docker launcher on Windows |
| Kokoro | Supported non-Arabic languages | Local service/container and model |
| ElevenLabs | Hosted multilingual voices | ElevenLabs API key with text-to-speech and voice-read permissions |
| Uploaded audio | Any language | WAV, MP3, or another supported audio file |
| Diagnostic espeak | Basic fallback diagnostic | Explicit user selection; robotic quality |

ElevenLabs API keys must be created in ElevenLabs Developers → API Keys. The full secret is shown only at creation time. SceneForge sends it to ElevenLabs through the `xi-api-key` header and forces the official ElevenLabs API host. It does not send the key to a user-supplied remote URL.

## 10. Dependencies

### Backend runtime

- Python 3.11 or newer
- FastAPI and Starlette
- Uvicorn and WebSockets/SSE support
- SQLAlchemy and SQLite
- Pydantic
- Requests
- Pillow
- python-multipart and aiofiles
- `keyring` for native credential storage
- Hugging Face Hub for supported local/model integrations
- FFmpeg and ffprobe

The complete pinned list is in `backend/requirements.txt`. `uvloop` is intentionally excluded because it is not a reliable Windows dependency and most work is performed by FFmpeg subprocesses.

### Frontend runtime/build

- Node.js 20 or newer
- React 18
- TypeScript
- Vite
- lucide-react
- jsdom and Testing Library packages for UI checks

The pinned frontend package files are `frontend/package.json` and `frontend/package-lock.json`.

### Desktop packaging

- Electron 44
- electron-builder 26
- Python build tooling for the packaged backend
- NSIS through electron-builder
- Bundled FFmpeg for the Windows package

### Optional services

- Docker Desktop for the supplied Chatterbox/Kokoro containers
- AUTOMATIC1111 Stable Diffusion WebUI with a compatible checkpoint and `--api`
- GPU drivers and sufficient VRAM for local image or speech models

## 11. Development setup

### Windows

```powershell
git clone https://github.com/EzioDEVio/SceneForge.git
cd SceneForge
.\scripts\setup.bat
.\scripts\start.bat
```

Open `http://127.0.0.1:8000`. Keep the server window open. Stop it with Ctrl+C. Do not run two instances against port 8000.

### macOS/Linux

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
npm --prefix frontend ci
npm --prefix frontend run build
cd backend
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The Windows launcher is the primary supported development path. Local model performance and service startup vary by operating system and hardware.

## 12. Desktop application and installer

The Electron desktop shell starts the packaged backend, serves the built frontend, manages application data paths, and handles window lifecycle. Closing the window, Alt+F4, or application quit invokes the close controller. If there are unsaved edits, the user can save and exit, cancel, or remain in the application. Active renders and failed saves block silent exit.

The Windows installer is an NSIS setup executable. It creates Start Menu and desktop shortcuts, allows installation-directory selection, preserves application data on uninstall, and does not automatically launch the app after installation. The installer does not bundle all large AI model weights; local Stable Diffusion, Chatterbox, and Kokoro models remain separate runtime installations.

Cross-platform installers are planned. macOS and Linux currently use the local development/startup path and have not reached the same packaged acceptance level as Windows.

## 13. Testing and validation

Local checks used for the RC4 work include:

```bash
npm --prefix frontend run build
npm --prefix frontend test
python -m compileall -q backend/app
desktop/.venv/bin/python tests/integration/test_hosted_adapters.py
```

The hosted-adapter checks mock provider calls and verify routing, fixed ElevenLabs host behavior, voice validation, metadata parsing, and local voice compatibility. The frontend suite contains 50 component checks covering project operations, timeline behavior, title editing, captions, motion, effects, providers, voice behavior, and desktop-close save handling.

GitHub Actions runs frontend build/tests, backend integration checks, native credential-vault checks, rendering checks, and Windows installer/startup verification. Hosted provider tests do not spend real provider credits. Local GPU/model performance remains hardware-dependent and requires user verification.

## 14. Latest issues and limitations

### ElevenLabs

- Voice metadata support has just been added; the current RC4 installer must be rebuilt before the UI displays names.
- A key without Voices read permission can return HTTP 401 during voice discovery even if text-to-speech permissions are present.
- ElevenLabs labels are provider metadata. A language selection in SceneForge does not prove that a speaker is from a particular nationality or dialect.
- Free-tier voice availability and quotas are controlled by ElevenLabs.

### Local voice

- Chatterbox and Kokoro require their service and model to be installed and running.
- Docker Desktop is used by the supplied Windows launchers.
- Arabic quality depends on the selected model, text normalization, GPU/CPU performance, and the voice service configuration.
- The diagnostic espeak voice is intentionally robotic and must be selected explicitly.

### Stable Diffusion

- The local engine depends on an existing AUTOMATIC1111 installation.
- `--api` must remain in `webui-user.bat` or the API cannot be reached.
- Checkpoint quality, resolution, sampling steps, hires fix, VRAM, and model family determine output quality.
- Automatic startup manages the configured localhost WebUI but does not install checkpoints or repair a broken model environment.

### Timeline and editing

- The timeline is scene assembly, not a complete multitrack NLE.
- Continuous full-project transport, waveform audio editing, arbitrary trimming, and independent track compositing remain future work.
- Transition duration is constrained by neighboring scene lengths and final renderer overlap rules.
- The editor preview approximates final effects and motion; render a scene to verify exact output.

### Text and title cards

- Existing text content and styling can be edited after creation.
- Baked title-card backgrounds cannot be reopened as fully editable source layers; create a replacement card to change them.
- Typewriter visual timing and keystroke sound are separate controls.

### Packaging and release

- Windows desktop packaging is the most complete path.
- macOS/Linux installers, signed binaries, automatic model downloads, and production-grade update delivery remain future milestones.
- The repository is still an alpha/preview product. Do not promise that every provider or GPU/model combination works without local acceptance testing.

## 15. Recommended next milestones

1. Build and distribute the RC4 Windows installer after the GitHub Actions run is green.
2. Add a voice preview button and searchable/filterable ElevenLabs voice catalog.
3. Add a clear provider-health panel showing API key, permission, quota, and endpoint status without exposing secrets.
4. Add waveform-based narration and music lanes.
5. Add frame-accurate trim handles and continuous project playback.
6. Improve title-card reopening so background and animation settings remain editable.
7. Add signed Windows releases and reproducible macOS/Linux packaging.
8. Provide optional guided installers for AUTOMATIC1111, Chatterbox, and Kokoro while keeping model licenses and downloads explicit.

## 16. Support checklist

When reporting a problem, include:

- SceneForge version and whether it is browser or desktop installer.
- Operating system and CPU/GPU.
- The exact provider and model selected.
- Whether the issue occurs during preview, scene render, or full export.
- Whether narration is uploaded, local, ElevenLabs, or absent.
- The redacted backend error and the relevant launcher/service log.
- The project aspect ratio and approximate scene duration.

Never include API keys, credential-vault values, or unredacted provider tokens in a bug report.
