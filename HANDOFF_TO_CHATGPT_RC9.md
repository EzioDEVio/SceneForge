# SceneForge Studio: handoff from Claude to ChatGPT (0.7.0 RC9)

**Prepared:** 2026-10-01
**Repository:** github.com/EzioDEVio/SceneForge
**Working branch:** `claude/0.7.0-rc5-timeline`. The RC9 head is the commit that adds this file. RC8 was `f62907f`.
**Published release:** still **0.5.3**. RC5–RC8 are unreleased test candidates.
**Owner:** Mohammed ("Ezio"). He tests the Windows installer built by GitHub Actions on his own PC.

Read this file first, then `README.md`, `desktop/RELEASE_NOTES.md`, `handoff.md`, `PROJECT_HISTORY_AND_HANDOFF.md`, `docs/TIMELINE_ARCHITECTURE.md` and the original brief `SceneForge_Claude_Takeover_and_Timeline_Prompt.md`, which is in the owner's files, not in this repo.

---

## 1. Ground rules the owner set
- **Ship features in large bundles** (one build = several fixes and features). The owner pays per session and has run out of credits more than once.
- **Never remove or regress existing features.** Earlier builds by other assistants accidentally deleted features. Keep 0.5.3 behaviour, the AI Engines and Help menus, and every RC4–RC8 feature.
- **No fake controls.** Every button must work end to end (UI → validated JSON → FFmpeg/backend → test). Label procedural effects honestly; don't call them "AI".
- **Never trigger paid provider calls** (OpenAI, Google Veo, Runway, ElevenLabs) in tests. Mock them.
- **Don't merge to `main`, tag, or publish a release** without the owner's explicit instruction. He pushes the branch himself (see §6).
- Don't claim a Windows UI test happened unless the owner ran it.

## 2. Stack and layout
- **Frontend** `frontend/`: React 18 + TypeScript + Vite. No Tailwind or UI library; styles are in `studio.css` and `preferences.css`.
  - Main files: `App.tsx` (very large), `ProjectTimeline.tsx`, `timeline/` (types, timeMath, editOps), `CreativeTools.tsx`, `VoiceIsolation.tsx`, `GainEnvelope.tsx`, `EffectStack.tsx`, `LookPresets.tsx`, `LocalServices.tsx`, `api.ts`.
  - **`BUILD_ID` in `api.ts` must equal `BUILD_ID` in `backend/app/main.py`.** It is currently `v0.7.0-rc8`.
- **Backend** `backend/`: FastAPI + SQLite (SQLAlchemy) + FFmpeg subprocesses.
  - Rendering is in `backend/app/render/`: renderer, filters, scene_fx, fx_stack, finishing, overlays, subtitles, speed, cutout, voice_isolation, textured_text, music_fit, beats.
  - APIs are in `backend/app/api/`.
  - New DB columns go through `_ADDED_COLUMNS` in `db/database.py`; changes must be additive only. Most new data lives in JSON columns (`look_json`, `overlays_json`, `finishing_json`, `speed_json`, `audio_json`).
- **Desktop** `desktop/`: Electron + electron-builder (NSIS, AppImage/deb, dmg).
  - The backend is frozen with PyInstaller by `desktop/scripts/build_backend.py`, which uses `--collect-all` for faster_whisper, ctranslate2, av and onnxruntime.
  - `desktop/scripts/fetch_ffmpeg.py` and `fetch_models.py` download what the installer bundles. `fetch_models.py` bundles u2netp.onnx for cutout.
- **Python 3.12** is required (requirements pin numpy 2.5.x). Use a 3.12 venv locally; `uv venv -p 3.12` works.

## 3. CI and how builds reach the owner
- **`.github/workflows/checks.yml`** ("Build and render checks") runs on every push:
  - frontend build and `npm test` (editor, units, timeline, video_generation and share_dialog suites);
  - **28 Python integration scripts** under a gnome-keyring session.
- **`.github/workflows/release.yml`** ("Release") builds Windows, Linux and macOS installers.
  - It runs automatically on pushes to `chatgpt/0.6.0-wip.10`, `chatgpt/0.7.0-video-generation` and `claude/0.7.0-*`, or manually with workflow_dispatch.
  - It publishes a GitHub Release **only for `v*` tags**. Branch builds produce temporary Actions artifacts only.
  - The packaged end-to-end test is `desktop/tests/e2e_backend.py`. It runs real renders, **real local Whisper (downloads the model)**, a real cutout and real voice isolation inside the installed backend.
- The owner downloads the **SceneForge-Studio-Windows** artifact, installs it and reports back with screenshots.
- Last known state: RC6 and RC7 were all green on all three OSes. RC8 was pushed; its CI result was not yet reported when this handoff was written.

### Local test commands
```bash
python3.12 -m venv .venv && . .venv/bin/activate && pip install -r backend/requirements.txt httpx
npm --prefix frontend ci && npm --prefix frontend run build && npm --prefix frontend test
npm --prefix desktop ci && npm --prefix desktop test          # 18 checks (ELECTRON_SKIP_BINARY_DOWNLOAD=1 is fine)
# integration (each is a standalone script; credentials/editor_plus need a Secret Service keyring on Linux):
dbus-run-session -- bash -c 'printf ci | gnome-keyring-daemon --unlock --components=secrets; for f in $(grep -o "tests/integration/test_[a-z0-9_]*\.py" .github/workflows/checks.yml); do python $f || echo FAIL $f; done'
```
Optional model folders for offline runs: `SCENEFORGE_CUTOUT_MODEL_DIR`, `SCENEFORGE_VOICE_MODEL_DIR`, `SCENEFORGE_MODEL_DIR` (Whisper).

Last full local run (RC9):

| Suite | Result |
|---|---|
| Frontend component checks | 264 |
| Unit checks | 19 |
| Timeline checks | 40 |
| Video-generation flows | 2 |
| Share-dialog checks | 6 |
| Desktop checks | 18 |
| Integration scripts | 32 (all passing) |

## 4. What Claude delivered (RC5 → RC8)
Full detail is in `desktop/RELEASE_NOTES.md`.

### RC5
- **CI fix.** A truly live job blocks project deletion (409); stale job rows don't. Job IDs are reserved as live before the row is committed, which closes a race.
- **Timeline v1:**
  - audio tracks **A3–A8**, each with mute, solo and lock;
  - edit tools V/A/B/N/Y/U/C (select, track select, ripple, roll, slip, slide, blade) and Razor All (Shift+C);
  - project-saved point and range markers with colours;
  - a versioned `finishing_json.timeline` (version 1) that migrates older projects;
  - viewport virtualization and Ctrl+wheel zoom.
- Pure edit operations live in `frontend/src/timeline/editOps.ts`.

### RC6
- **Delete only the cut piece.** Delete acts on the lane the user last worked in, so deleting audio never deletes the scene video.
- **Right-click menus** for audio clips, scenes, narration (A1) and clip sound (A2).
- **Detach** narration or clip sound to A3 (`POST /api/scenes/{id}/detach-audio`).
- **Scene renders play timeline audio and music** through a cached preview mix (`GET /api/scenes/{id}/preview-media`). The rendered part stays clean, so export mixes it once.
- **Whisper diagnostics and repair:** a "Check local captions" panel, plus `/api/local-speech/whisper/check` and `/reset`.
- **In-app Start buttons for Chatterbox and Kokoro.** They need Docker Desktop in Linux-containers mode. The services are bundled in the installer.
- **FFmpeg effects pack:**
  - shake presets, lens flare (screen/add), wiggle, focus blur, tilt-shift, mosaic, RGB split amount;
  - halation and film grades;
  - text reveal masks;
  - sticker float, bob and pendulum loops;
  - speed-ramp curves with optional minterpolate;
  - beat-aware music fit;
  - dialogue cleanup.

### RC7
- **Local Whisper fixed.** The installed PyAV rejected `open(metadata_errors=...)`, which faster-whisper passes. Audio is now decoded with FFmpeg to 16 kHz float samples and passed to the model as an array (`providers/transcribe.py::_decode_pcm16k`).
- **Black first scene render fixed.** It was a player timing problem, not the renders. The player waits for the refreshed project, retries once, and preview mixes are built one at a time per scene.
- **AI subject cutout:** local onnxruntime with u2netp, IS-Net or U²-Net human. "Text behind subject" uses an overlay with `above_text`; "Remove background → Media Pool" saves a PNG.
- **Textured titles:** 9 procedural textures, a Media Pool image, or a texture generated by the configured image engine.

### RC9
- **Library:** 400 stickers and emoji (322 Twemoji, CC-BY 4.0, plus 78 drawn graphics; builder in `scripts/build_sticker_library.py`, assets in `assets/stickers/`) and 71 caption styles (`frontend/src/captionStyles.json`).
- **Per-effect settings:** `look_json.fx_params`, with the schema in `backend/app/render/effect_params.py` served at `GET /api/effects/schema`. Default settings render byte-identically to before.
- **Text reveals:** clock, clock counter-clockwise and iris, built as stepped ASS vector clips (`subtitles._clock_steps`).
- **Moving-video subject cutout:** `backend/app/render/video_cutout.py`; a VP9 alpha WebM layer decoded with libvpx-vp9, with a qtrle fallback.
- **Clip groups and clip-attached markers:** `audio_clips[].group`; markers carry `clip_id` and `offset_ms` (`timeline.types.ts::markerTime`).

### RC8
- **Cutout quality:**
  - guided-filter edge refinement, speck and hole cleanup;
  - edge grow/shrink of ±10 px;
  - the people model;
  - a checkerboard result preview;
  - u2netp bundled in the installer.
  - BiRefNet was rejected because it needs more than 7.5 GB of RAM per photo on the CPU.
- **AI voice isolation:**
  - MDX-Net Kim_Vocal_2 ONNX, 67 MB, MD5 `fa29b9d118ba4ad14a000254a60114b8`, downloads once.
  - Available for narration takes, timeline clips and video clip sound.
  - Measured on a synthetic test: +7.75 dB SDR, with music suppressed by 42–48 dB.
- **Beat markers** (`POST /api/projects/{id}/beat-markers`) and **volume envelopes** on A3–A8 clips: `gain: [[source_ms, dB]]`, rendered in export and in the scene preview.
- **Effect stack:** `look.fx_order` / `fx_bypass` for spotlight, leak, flare, wiggle and shake. Without them the default order is unchanged.
- **Look preset packs:** `/api/look-presets`, drag-and-drop `.json`/`.sflook`, and a starter pack in `assets/look-packs/`.

## 5. Open items and next steps (owner's wish list)
1. **Wait for the owner's RC8 Windows test.** Check cutout quality with IS-Net and the people model, voice isolation, beat markers, envelopes, the effect stack and the presets.
2. **Chatterbox:** never confirmed working on the owner's PC. It needs Docker Desktop in Linux mode; the first start downloads several GB. The fallback is Kokoro or cloud voices.
3. **Licence check:** the Kim_Vocal_2 weights have no explicit licence from their author (UVR is MIT). Confirm before a public release.
4. **Not done from the request list:**
   - a full node-based compositor (only ordering and bypass exist);
   - true compound or nested clips (only groups exist);
   - free multitrack *video* (V1 is still scene-based).

   The video cutout is limited to 20 s, a static camera and speed 1.
5. **Dependabot** reported 4 vulnerabilities on `main` (the old 0.5.3 code). Review them before merging the candidate.
6. **When the owner approves:** merge the branch to `main`, bump the version, tag `v0.7.0`, and let Release publish it. Only do this on his explicit instruction.

## 6. How the owner gets a new build to GitHub
Each source zip contains `SceneForge/history/SceneForge.gitbundle`, which holds the full history. On Windows, from the folder the zip was extracted to:
```powershell
cd "C:\Users\moham\Downloads\Claude_sceneforge\HAND OVER FROM CHATGPT TO CLAUDE\SceneForge-<VERSION>-Source"
git clone -b claude/0.7.0-rc5-timeline "SceneForge\history\SceneForge.gitbundle" SceneForge-repo
cd SceneForge-repo
git remote set-url origin https://github.com/EzioDEVio/SceneForge.git
git push origin claude/0.7.0-rc5-timeline
```
The push starts both workflows. You may keep using this branch name (the Release workflow builds `claude/0.7.0-*`), or create e.g. `chatgpt/0.7.0-rc9`. In that case, add it to `release.yml` `on.push.branches`, or the owner runs Release manually.

When delivering, always produce **one zip**: the tracked source from `git archive HEAD` plus `history/SceneForge.gitbundle` (`git bundle create ... --all`). Also give PowerShell commands with **full real paths**. The owner copies them literally, so never write placeholders like `<path>`.

## 7. Gotchas learned the hard way
- FFmpeg `asplit` dropped pieces inside an `acrossfade` chain; music_fit reads each piece as its own input.
- Thumbnails are JPEG, which loses alpha. Preview transparent PNGs through `/api/assets/{id}/stream`.
- `frontend/tests/editor.mjs` asserts exact tile counts in some Effects sections. Put new tiles in new sections.
- Faster-Whisper must never get a file path: PyAV versions break it. Always pass samples.
- Project-level audio must not be baked into rendered scene parts, or export would mix it twice. Use the preview mix.
- Hugging Face downloads: `HF_HUB_DISABLE_XET=1` is set for reliability on Windows.
- The machine-local model cache folders are `%USERPROFILE%\.sceneforge\models\{whisper,cutout,voice}`.
