# SceneForge 0.7.0 WIP — Session Handoff

**Prepared:** 2026-09-29
**Current source:** branch `chatgpt/0.7.0-video-generation` in `EzioDEVio/SceneForge`
**Current working version:** `0.7.0-wip.1` (unreleased source snapshot)
**Base:** preserved `chatgpt/0.6.0-wip.10` editor branch
**Published baseline:** GitHub release `0.5.3`

## Purpose and handling

This handoff preserves the earlier 0.5.3/0.6.0 review below and records the new 0.7.0 text-to-video milestone first. The 0.5.3 published release remains part of the product history; 0.6.0-wip.10 is the source baseline for this additive branch. The 0.7.0-wip.1 branch is not a stable release.

Reviewed inputs in this workspace include the 0.5.3 source ZIP, the original 0.6.0 WIP ZIP, reviewed wip.2–wip.6 snapshots, their READMEs and handoffs, the SceneForge session handoff, chat notes, and the user screenshots. The 0.5.3 technical handoff predates the 0.5.3/0.6.0 work and should not be treated as a complete description of the present build.

## Current 0.7.0-wip.1 additions

- Added a separate text-to-video workspace while preserving the existing AI Engines and Help menus, editor tabs, scenes, Media Pool, timeline, captions, effects and overlays.
- Added a curated local catalog for LTX-2.5 Fast, Wan 2.1 T2V 1.3B, Wan 2.2 TI2V 5B, Wan 2.2 T2V A14B, and compatible custom ComfyUI workflows.
- Added paid integrations for Google Veo 3.1 Lite/Fast/Standard and Runway Gen-4.5/WAN 3.0. Rates are shown per second/per resolution and the selected clip receives a total estimate. Rates were checked 2026-09-28; provider billing can change. Cloud starts require explicit cost confirmation checked by both UI and API.
- Added model-specific ratio, duration and resolution validation; local custom dimensions (multiples of 16); API workflow import; local ComfyUI status; loopback-only server access; background job progress/cancellation; and output media validation.
- Generated output becomes a normal project Media Pool asset. The user can add it to the selected scene or create a timeline scene. The caption action uses existing local speech transcription (scene narration when present, otherwise video sound) and opens Text for timed caption edits and styles. Existing Clip Audio, Effects and Overlays remain available.
- Local ComfyUI and model weights/workflows are installed separately and are not bundled. A visible notice explains that custom nodes run inside ComfyUI with the user's permissions. Paid provider API keys use the OS credential store.
- Added UI interaction tests for local custom-size generation → asset insertion → caption handoff and cloud rate display → explicit paid confirmation.
- The Release workflow is configured to create temporary Windows, Linux and macOS build artifacts after branch push. A branch build is not a GitHub release; no stable tag is created by this milestone.

### Current verification and remaining acceptance tests

- `npm run build` passed (TypeScript and Vite; Vite retains a bundle-size advisory above 500 kB).
- `npm test` passed: 191 existing editor component checks, 19 unit checks, 2 text-to-video panel checks and 6 share checks; provider APIs are mocked.
- `npm test` in `desktop/` passed: 14 lifecycle/update/storage checks.
- `python -m compileall -q backend/app tests/integration/test_video_generation.py` and `git diff --check` passed.
- The new FastAPI integration test is wired into CI but could not run locally: backend packages are not present and package downloads were unavailable in this workspace.
- No real local or paid video has been generated. Acceptance needs ComfyUI with model-specific weights and an API workflow, plus Google/Runway credentials and billing for cloud tests. Verify result media/audio, captions, timeline insertion, rendering and export on target operating systems.
- Do not describe 0.7.0-wip.1 as a stable public release until CI and real-provider/installer acceptance tests pass.

### Provider catalog, published rates and setup

Rates shown by the app, checked 2026-09-28:

| Provider/model | Published price |
|---|---|
| Google Veo 3.1 Lite | $0.05/sec at 720p; $0.08/sec at 1080p |
| Google Veo 3.1 Fast | $0.10/sec at 720p; $0.12/sec at 1080p; $0.30/sec at 4K |
| Google Veo 3.1 Standard | $0.40/sec at 720p and 1080p; $0.60/sec at 4K |
| Runway Gen-4.5 | $0.12/sec (12 credits/sec; Runway lists a credit at $0.01) |
| Runway WAN 3.0 | $0.05/sec at 480p; $0.10/sec at 720p; $0.20/sec at 1080p |
| Local ComfyUI choices | No provider API fee; user's hardware, electricity, storage and licenses still apply |

The app and [README.md](README.md) link to official prices and setup pages. Estimates can differ from final provider bills, taxes, regional billing or account credits. Local weights are not included: users run ComfyUI on loopback, install the chosen model and dependencies, export with **Save (API Format)**, and import that JSON. Common prompt/size/frame-count/seed inputs are mapped; specialized graphs may need adjustment. Cloud output sizes, ratios and durations are limited to the chosen model's supported options; local custom width/height must be multiples of 16.

### Files changed for 0.7.0-wip.1

- Backend: `backend/app/providers/video_generation.py`, `backend/app/api/video_generation.py`, `backend/app/domain/schemas.py`, `backend/app/api/providers.py`, `backend/app/workers/jobs.py`, `backend/app/main.py`.
- Frontend: `frontend/src/VideoGenerationPanel.tsx`, `frontend/src/App.tsx`, `frontend/src/api.ts`, `frontend/src/styles.css`; UI regression test: `frontend/tests/video_generation.mjs`.
- Build metadata and CI: `desktop/package.json`, `desktop/package-lock.json`, `.github/workflows/checks.yml`, `.github/workflows/release.yml`.
- Notes: `README.md`, `desktop/RELEASE_NOTES.md`, `docs/REVIEW_0.7.0_VIDEO_GENERATION.md`.

---

## Earlier 0.6.0 handoff and history

## User requirements carried forward

- Preserve all working 0.5.3 features and existing tabs/menus; enhancements must be additive.
- Keep the AI Engines menu and provider configuration accessible, plus the existing Scenes, Media Pool, and Transitions library tabs. The duplicate AI Engines library tab was removed.
- Repair timeline undo/redo, clip audio controls, scene movement, and cutting/splitting so source sound follows its video.
- Keep clip audio controls separate from Motion and make audio settings functional and persistent.
- Make the app friendlier for nontechnical users: free local speech captions, visible installation/service requirements, modern narration and export controls, and contextual help for features.
- Improve transitions, captions, effects, timeline operations, stickers/filters, title cards, and sharing without removing established features.

## Baseline and 0.6.0 feature inventory

### Version lineage and authorship

- The GitHub `release/v0.5.3` branch remains unchanged and is the published base.
- The locally tested 0.6.0 WIP source (which includes Claude-authored changes) is carried forward as a clearly named snapshot branch. Its original unpublished per-commit Git authorship is not reconstructed; the snapshot commit documents that limitation.
- The reviewed ChatGPT-assisted changes are a distinct commit on `chatgpt/0.6.0-wip.10`, based on that 0.6.0 snapshot. Both branches live in the existing repository; no second repository is created.
- No stable release tag is created by this work. The Release workflow runs for pushes to `chatgpt/0.6.0-wip.10` and uploads branch builds as temporary Actions artifacts using `--publish never`; tagged releases retain their existing behavior.

### Preserved 0.5.3 features

The released baseline includes source-video audio, per-video volume/mute/narration ducking, scene duration tied to video length, per-scene countdown intros, vertical-project fit behavior and safe zones, captions from speech through configured cloud providers, project/file menus, and the existing AI Engines/Help desktop experience. These are baseline features, not additions made by this review. Do not remove or silently replace them.

### Broader 0.6.0 WIP additions present in the submitted work

- More transitions and live transition previews (42 transition choices total), caption styles (24 total), batch/multi-select apply, progress cards, export presets/advanced options, animated GIF/audio-only formats, and SRT/VTT export.
- Free local Faster-Whisper transcription as the default automatic-caption route; ElevenLabs and OpenAI remain optional cloud services. The multilingual model downloads on first use and runs locally afterward.
- Improved export compatibility using H.264 4:2:0 and fast-start MP4 settings; per-video sound and clip duration are retained in vertical exports.
- Additional caption styling and transitions; auto-closing/minimizable multi-select actions; narration-script and export-panel styling.
- Service and installer documentation: the desktop package bundles the app, private backend runtime, and FFmpeg, but not optional Chatterbox/Kokoro servers, Stable Diffusion models, or Whisper model weights.

These features largely predate the screenshot repair work. Refer to `desktop/RELEASE_NOTES.md` and `docs/REVIEW_0.6.0_WIP.md` for the detailed WIP inventory.

## Troubleshooting chronology and repairs in the reviewed source

### Regression report from the user

The user reported an unusable build and supplied screenshots titled `the original UI release 0.5.3.png`, `this is the build you handed me which is broken and missing the Ai engine tab and others.png`, `thumbnais inside the motion tab.png`, and `none-functional audio button or crop and focal .png`. The later screenshots `new_sound_panel.png` and `auto caption layout stretched out.png` added clip-audio and caption-layout feedback.

Findings and resolution:

1. **AI Engines and Help access:** the original 0.5.3 screenshot showed a top-level AI Engines menu, while the reviewed wip.4 interface had lost that access. The top-level AI Engines menu and Help/About were restored. The original Scenes, Media Pool, and Transitions library tabs and provider settings remain. The redundant AI Engines library tab was removed. Help/update capabilities are exposed through the desktop shell; browser mode cannot provide native updater/file-menu behavior.
2. **Clip sound mixed into Motion:** A2 source-audio timeline blocks now route to a separate **Clip Audio** inspector. Volume, mute, and narration ducking remain; fade-in/fade-out controls were added in wip.6. Fade settings are validated, persisted, applied in FFmpeg, and carried through split/undo.
3. **Nonfunctional-looking crop/focal/media thumbnails:** media crop/focal controls now use generated poster thumbnails with a fallback instead of a broken placeholder. Crop/focal and audio slider edits save on commit/release. Regression checks cover committed audio values and fade persistence.
4. **Crowded Auto captions card:** the Auto captions controls stack in a narrow inspector and switch to two columns only when the panel is wide enough.
5. **Timeline editing/history:** undo/redo coverage was added for scene add/delete, media insertion, title cards, narration attach/remove, scene reorder, clip sound, and scene split (up to 100 recent operations per session). Split preserves source-audio and speed settings; undo restores the original scene/clip identities. Whole scene blocks can be dragged to reorder, and dropping media at timeline gaps/scene edges inserts before/after as indicated.

### Timeline scope boundary

SceneForge remains a scene-assembly editor. It supports scene reordering/insertion, source-audio lane selection, scene splitting, and scene history. It is not yet a full nonlinear editor: independent arbitrary clip movement across unlimited tracks, frame-accurate trim handles for every media type, full waveform editing for embedded clip sound, and a multitrack compositing graph remain incomplete. Do not describe the current timeline as equivalent to DaVinci Resolve.

## Current 0.6.0-wip.6 changes

- Added **Clip Audio** fade-in and fade-out controls (0–10 seconds) alongside existing volume, mute, and narration ducking. The backend rejects out-of-range fade values and FFmpeg applies fades after the clip's source trim.
- Kept fade values in shot audio state and through clip split/undo, with integration coverage.
- Made the Auto captions card responsive to inspector width to prevent the narrow-panel layout seen in the screenshot.
- Updated frontend/backend build identifiers and desktop package version to `0.6.0-wip.6`.
- Updated README/release/review documentation and created this consolidated handoff.

## Current 0.6.0-wip.9 additions (previous WIP)

- **Post-export sharing:** a successful export opens a Share dialog with download, desktop open-file-location, device/browser share fallback, and instructions for YouTube, TikTok, Instagram and Facebook. It does not upload automatically. Browser mode directs users to Downloads when native folder reveal is unavailable. Desktop reveal validates that the asset is a render and that its path stays under the render directory.
- **Timeline editing:** ruler snapping targets scene boundaries and named markers; markers save per project in local browser storage. Video edge trim handles update video source in/out and linked source audio together for a single-video, non-fixed, narration-free scene. Existing scene delete removes that block and naturally closes the sequence gap.
- **Stickers/emoji:** Overlays provides a searchable 48-item categorized library. Selecting a symbol creates a PNG image asset which uses the existing overlay position/scale/rotation/animation and render paths.
- **Filters:** added Teal & Amber, Pastel and Bleach Bypass as separate FFmpeg-rendered effect presets.
- Bumped frontend/backend identifiers and desktop package to `0.6.0-wip.9`; no changes were pushed to GitHub.

## Review of the user's eight requested areas

| Request | State in the reviewed source | Still needed |
|---|---|---|
| More caption styles | 24 styles exist, including six newer styles (Creator punch, Soft subtitle, Glass panel, Pastel pop, Cyber cyan, Clean white) and additional variants already in the style library. | Review visual consistency in a real browser and rendered scenes; add further styles only where they add a distinct use case. |
| More effects and helpful feature descriptions | Many non-look effects already exist (for example glitch, Old Film, camera shake, spotlight, redaction, light leaks, split toning, LUTs, annotations). Effect tiles have previews/search and section cards. | Click-open guidance now covers these tabs and major feature sections; some low-level controls may still need more specific explanations as user testing identifies confusion. |
| Clip Audio controls | Separate inspector with volume, mute, narration ducking, fade-in and fade-out; backend validation/rendering and persistence implemented. | Manually verify on actual source clips in browser/desktop and after split, undo, and export. |
| Trending transitions | 42 choices with live previews; additional cover, slide, zoom, wipe, blur, radial, wind, squeeze, rectangle, and morph-like transitions. | Avoid near-duplicates; compare rendered results and add only clearly differentiated motion. Do not use third-party proprietary assets without rights review. |
| Social sharing | Post-export prompt includes download, desktop open-file-location, platform links and posting guidance. | Direct account uploads require platform developer setup, user authorization and policy review. |
| Timeline tools | Undo/redo, scene move/insert, split/restore, A2 source-audio lane, drag/drop, multi-select, snapping, named markers, playhead, keyboard shortcuts and constrained linked video/audio edge trimming are available. Deleting a scene closes the sequence gap. | Track lock/mute/solo, unlinking audio, arbitrary independent clip moves, ripple delete as a distinct edit command, and trim handles for general/multitrack audio remain backlog. |
| Stickers, filters, emoji | Searchable categorized 48-item emoji/sticker picker in Overlays; added Teal & Amber, Pastel and Bleach Bypass render filters; existing LUT/looks remain. | Rights-cleared sticker packs, favorites and downloadable pack management remain possible follow-up work. |
| Title cards | Six title-card presets, solid/gradient backgrounds, title animations and duration controls already exist. | The generated background is baked into the card; reopening to edit the original background/animation as editable source remains limited. Improve slider grouping/labels and preview consistency. |

## Local services, costs, and install expectations

- Core editing, rendering, and export use the local SceneForge frontend/backend and FFmpeg. These do not require a paid AI account.
- Local auto captions use Faster-Whisper; the model downloads once on first use, then transcription runs on the machine. First use requires internet and enough disk/RAM/CPU/GPU resources for the selected model.
- Optional hosted OpenAI/ElevenLabs features use the user's own credentials and may incur provider charges/limits. Do not claim these are free.
- Local narration with Chatterbox or Kokoro and local image generation with Stable Diffusion require separately installed services/models; they are not bundled with the desktop installer. Their startup and model dependencies are documented in the README/AI Engines area.
- The Windows installer bundles the app, private backend runtime, and FFmpeg; source development setup additionally needs Python, Node.js, and FFmpeg. Exact operating-system installer coverage and requirements should be checked against the release being distributed.

- **Text tools:** added Text, Text Box (width-controlled wrapping), and Text+ (SceneForge styled/animated title tool; not full Resolve Fusion parity). Titles and captions are visible as labeled, timed T1 clips; selecting one switches to Text and focuses its edit field.
- **Feature help:** click-to-open “What it does / How to use it” explanations are available across Media, Motion, Effects, Overlays, Text, Audio and Clip Audio, plus major controls and panels.
- **Marker guidance:** markers are per-project named bookmarks; clicking one returns the playhead to that position.
- **AI Engines:** original top-level menu retained; duplicate AI Engines tab removed from the Scenes library tabs.

- **Auto-caption editing:** speech transcription is divided into individually timed phrase clips on T1 (1–8 words per clip; chosen with style defaults and editable in Auto captions). Clicking a clip focuses that segment's text box. Users can edit wording, start/end times, split phrases, remove a segment, then apply shared caption styling to the whole set. Backend render uses segment timings so exports preserve edits.
- **Help popovers:** moved into a fixed viewport portal with left/right placement, bounded scroll height, resize/scroll repositioning, and Escape dismissal to prevent inspector clipping.
- Added an in-between caption workflow: user can adjust words per clip, split a phrase, or replace the segments with one narration text clip.

## Current 0.6.0-wip.10 additions

- Moved the T1 captions/titles lane above V1 in the timeline, including the sticky track headers and timeline content height.
- Added transcript search, previous/next caption navigation, active-segment highlighting, and collapse/expand controls for long transcripts.
- Added per-scene caption direction (Auto, RTL, LTR) to generated caption clips and the manual caption editor. The direction is applied in timeline/editor UI and embedded in ASS text to guide libass for mixed Arabic/Latin captions.
- Added frontend regression coverage for lane order, navigation, search, collapse/expand, direction persistence, and manual-caption direction; added a render smoke check for RTL/LTR direction marks.
- Bumped app/backend build IDs and desktop package version to `0.6.0-wip.10`.

## Verification status for wip.10

Re-run in this workspace on 2026-09-28:

- `npm run build` — **passed** (TypeScript + Vite production build).
- `npm test` — **passed**: 191 component checks, 19 unit checks, and 6 Share dialog checks. These use mocked APIs and are not browser visual QA.
- `npm test` in `desktop/` — **passed**: 14 desktop lifecycle/update/storage tests.
- `PYTHONPATH=backend python tests/integration/test_caption_segments.py` — **passed**: independently timed caption events and explicit RTL/LTR direction marks.
- `python -m compileall -q backend/app tests/integration/test_caption_segments.py tests/integration/test_effect_presets_addon.py tests/integration/test_share_location.py` — **passed**.
- `git diff --check` — **passed**.
- GitHub Checks run **36486468767** on commit `8c1532b6a3a6b3e65c2abc2fcc712ad2398e23c7` — **passed**. It ran the frontend build/tests and the full backend integration/render suite, including native credential migration plus the caption, effect-preset, and share-location checks.
- GitHub Release workflow run **36485090171** on app-source commit `4cb3a6715c52085095d3fe17313c500f3793ab29` — **passed** for all three configured targets: Windows x64 NSIS installer, Linux AppImage and `.deb`, and macOS Apple Silicon `.dmg` and `.zip`. Packaged backend/editor render checks passed. The macOS target is Apple Silicon only; Intel macOS is not built.
- The three installer artifacts are attached to that Actions run and expire **2026-12-27**. They are temporary branch-build artifacts, not a published stable release.
- wip.9 verification (historical): 185 component checks, 19 unit checks, 6 Share dialog checks, caption render smoke, and Python compile passed; these are not wip.10 test results.

The following still need hands-on or real-service verification: browser visual behavior, real cloud caption API credentials, first-run Faster-Whisper model download/inference, Windows Photos/Media Player playback, and clean-machine installation on each OS. CI confirms the installer packages launch and pass packaged-app render checks, but does not replace those user acceptance checks.

`docs/REVIEW_0.6.0_WIP.md` records the latest review and remaining work. Any Actions-built installers from a branch dispatch are test artifacts, not a published stable release.

## Suggested next work, in order

1. Launch the browser build and manually verify the Share dialog, platform actions, marker/snapping behavior, trim handles, sticker preview/render, new filters, AI Engines/Help access, clip-audio controls, and transition preview/render.
2. Test captions with Faster-Whisper locally and a configured cloud provider if desired; record model/service, language detection, exact UI/errors and caption timing.
3. Test Windows playback and a clean-machine installer before calling this a release. Do not publish this source snapshot as 0.6.0 yet.
4. Continue the timeline with independent clip movement, audio unlinking, track lock/mute/solo, generalized trim and explicit ripple-delete behavior.

## Files of interest

- `desktop/RELEASE_NOTES.md` — cumulative release notes; current header identifies `0.6.0-wip.10` as unreleased.
- `docs/REVIEW_0.6.0_WIP.md` — source comparison and regression review; distinguishes historical wip.9 checks from current checks.
- `README.md` — feature and services/install overview.
- `SceneForge_Technical_Handoff.md` — architecture and technical background; note it predates some WIP changes.
- `frontend/src/SpeedControls.tsx` — Clip Audio controls.
- `backend/app/api/scenes.py`, `backend/app/render/media.py` — fade validation/persistence and FFmpeg application.
- `frontend/src/studio.css` — inspector responsive layout.
- `frontend/tests/editor.mjs`, `tests/integration/test_v06.py` — regression checks.
- `work/053` — preserved released 0.5.3 baseline; `work/060` — submitted local 0.6.0 source; `work/review` — current reviewed working source.
