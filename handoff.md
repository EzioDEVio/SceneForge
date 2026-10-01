# SceneForge 0.7.0 Release Candidate — Session Handoff

**Prepared:** 2026-09-30
**Current source:** branch `chatgpt/0.7.0-video-generation` in `EzioDEVio/SceneForge` (candidate commit `c9a8ee7`; local source tree matches it)
**Current working version:** 0.7.0 release candidate (unreleased)
**Base:** preserved `chatgpt/0.6.0-wip.10` editor branch
**Published baseline:** GitHub release `0.5.3`

## Purpose and handling

This handoff preserves the earlier 0.5.3/0.6.0 review below and records the 0.7.0 text-to-video milestone plus the latest UI/timeline follow-up. The 0.5.3 published release remains unchanged; 0.6.0-wip.10 is the source baseline for this additive branch. The 0.7.0 candidate is not a stable release. Keep it separate and wait for a fresh Windows installer test before merge or publication.

Reviewed inputs in this workspace include the 0.5.3 source ZIP, the original 0.6.0 WIP ZIP, reviewed wip.2–wip.6 snapshots, their READMEs and handoffs, the SceneForge session handoff, chat notes, and the user screenshots. The 0.5.3 technical handoff predates the 0.5.3/0.6.0 work and should not be treated as a complete description of the present build.

## 0.7.0 RC8 (2026-10-01)

The user said RC7's cutout worked but the edges were poor, and asked for more features from the original list. RC8 contents are in RELEASE_NOTES.

Open items:
- The licence of the Kim_Vocal_2 weights is not stated by the author; UVR, which hosts the model, is MIT. Confirm before a public release.
- Video (moving) cutout, a full node compositor, compound clips and clip-attached markers are not done.

New tests:
- `test_voice_isolation.py` (19, real model)
- `test_fx_stack_presets.py` (70)
- `test_rc8_audio.py` (10)
- the cutout tests continue
- 252 frontend component checks

## 0.7.0 RC7: RC6 Windows test follow-up (2026-09-30)

The user's RC6 test found three problems:
- Local Whisper failed with `open() got an unexpected keyword argument 'metadata_errors'` (a PyAV change). Fixed by decoding the audio with FFmpeg and passing the samples to Whisper.
- The first scene render showed a black screen. The renders were correct (verified by measuring frame brightness for halation, flare, wiggle, mosaic and shake); the player was the problem and is fixed.
- The speed-ramp options were cramped. Fixed.

Added: AI subject cutout and textured titles (see RELEASE_NOTES).

Tests:
- 245 component checks
- 19 unit, 38 timeline, 2 video-generation and 6 share-dialog checks
- 18 desktop checks
- 25 integration scripts, including the new `test_cutout.py` (real U²-Net model, 25 checks) and `test_textured_title.py` (10 checks)
- The packaged e2e test now runs real local Whisper and cutout.

The next build should look at voice isolation and video cutout.

## 0.7.0 RC6: Windows test follow-up and effects pack (2026-09-30)

The user tested the RC5 installer on Windows and reported five issues. Each is listed with its resolution:

1. **Local Whisper fails; cloud works.** This could not be reproduced in the Linux container, because model downloads are blocked there. RC6 hardens every step and adds diagnostics:
   - HTTPS downloads without Xet
   - cache self-repair
   - an int8 → float32 fallback
   - a **Check local captions** panel
   - a packaged-app CI check that the engine loads

   Still open: the user needs to run **Check local captions** and send the output if captions still fail.
2. **Cutting a sound clip and deleting one half deleted the video.** Fixed:
   - Delete follows the lane you last worked in (audio or scenes).
   - Right-click menus were added.
   - Narration and clip sound can be moved to A3 so they can be cut.
3. **Right-click cut/copy/paste/delete on the timeline.** Added for audio clips, scenes, narration and clip sound.
4. **A scene render didn't include the added audio or music.** Fixed with a cached preview mix (`GET /api/scenes/{id}/preview-media`); the rendered part stays clean for export.
5. **Chatterbox not running.** The installer never included the voice-service files, and starting the engine needs Docker. RC6 bundles the files, adds in-app Start buttons with Docker checks and a live log, and pins a CPU-only PyTorch in the image.

The FFmpeg effects pack is described in `desktop/RELEASE_NOTES.md`. Deferred: AI cutout, AI text textures, AI voice isolation, and a node compositor.

**Tests:**
- 243 component checks
- 19 unit and 38 timeline checks
- 2 video-generation and 6 share-dialog checks
- 18 desktop checks
- The full CI integration list, now 23 scripts, including the new `test_effects_rc6.py` (88 checks) and `test_rc6_timeline_audio.py` (12 checks, real FFmpeg)

## 0.7.0 RC5 — CI fix and timeline v1 (Claude continuation, 2026-09-30)

**Branch:** local `claude/0.7.0-rc5-timeline`, based on `codex/0.7.0-release-candidate` source commit `3d6107a`. That commit's tree `c813c8c` is identical to GitHub `chatgpt/0.7.0-video-generation` at `c9a8ee7`. Nothing has been pushed, merged, tagged or published. No paid or live provider call was made. The Windows UI was **not** tested by Claude.

### What changed
- **CI regression.** `test_editor_plus.py` expected 409 from a bare `running` row, but RC4 correctly treats rows without a live worker as stale.
  - The test now uses a genuinely live job (`jobs.live_job`).
  - Render, export and video-generation endpoints reserve the job ID as live before committing the queued row, which closes the commit-to-thread-start race.
  - New checks: a reserved job blocks deletion (409); a stale queued row does not.
- **Timeline v1.**
  - Audio tracks A3–A8, each with mute, solo and lock.
  - Edit tools V/A/B/N/Y/U/C, plus Razor All.
  - Project-saved markers (point and range, with colours) and track locks, migrated from browser storage.
  - Versioned `finishing_json.timeline`, with backend validation.
  - Viewport virtualization, rAF-coalesced drag previews, Ctrl+wheel zoom around the pointer.
  - Design, migration and limits are in `docs/TIMELINE_ARCHITECTURE.md`.
- **Files.**
  - Backend: `backend/app/workers/jobs.py`, `backend/app/api/render.py`, `backend/app/api/video_generation.py`, `backend/app/render/finishing.py`, `backend/app/main.py` (build ID `v0.7.0-rc5`).
  - Frontend: `frontend/src/timeline/{timeline.types.ts,timeMath.ts,editOps.ts}` (new), `ProjectTimeline.tsx`, `App.tsx`, `FinishingPanel.tsx`, `api.ts`, `studio.css`.
  - Tests: `frontend/tests/timeline.mjs` (new), `frontend/tests/editor.mjs`, `frontend/package.json`, `tests/integration/test_editor_plus.py`, `tests/integration/test_finishing.py`.
- **Migration.** Additive and versioned. A clip without `track` is on A3. A project without `timeline` reads browser-stored markers and locks once, and they are saved into the project on the next timeline change. To downgrade, remove `timeline` and `track`; clips on A4–A8 then play on A3.

### Verification (Linux container, Python 3.12, Node 22, system FFmpeg)
- Frontend:
  - Production build passed; the editor bundle is 572.5 kB (was 555.7 kB), and Vite's >500 kB advisory is unchanged.
  - 237 component checks (226 before), 19 unit, 38 new timeline model/migration/edit-operation checks, 2 video-generation flows and 6 share-dialog checks.
- Desktop: 18/18 passed.
- Backend: the full `checks.yml` integration sequence was run under a disposable gnome-keyring exactly as CI runs it, and all 21 scripts passed. That includes `test_editor_plus.py` (16 checks) and `test_stale_jobs.py` (6 at the time; 10 after the real-render check was added).
- `test_finishing.py`, rerun with the RC5 additions: 29/29 passed (22 existing plus 7 new). The new checks cover:
  - A3 staying implicit on clips
  - timeline round-trip
  - rejection of invalid tracks, invalid track states and newer versions
  - A5 mixed at its sequence time
  - A5 mute silencing only that clip
  - A5 solo
  - the audibility rules
- `test_source_split.py` passed.
- `test_cancel_live.py` could not run here: it needs a running server plus a local TTS voice engine, and it is not part of CI.
- In its place, `test_stale_jobs.py` now has a real-FFmpeg render check (10 checks in total): a render that is in progress blocks deletion (409) and leaves the job intact; it then finishes, releases its live slot, and the project deletes (200).
- Edit-operation timing in Node, per call:
  - 64 clips: ≤31 µs
  - 1,000 clips: ≤70 µs
  - With 1,000 clips at 55 px/s in a 1,600 px view, 45 clips are rendered.
- **GitHub workflow diagnosis.** Run 36763871406 failed only because of the stale-row test assumption above; the product behaviour was correct. The workflow itself needs no change, because `npm test` now includes `tests/timeline.mjs`. Push the branch (with authorization) to get a real CI rerun.

### Manual Windows checklist (not yet run)
1. Install the RC5 installer from a CI artifact. Open an RC4 project that has markers and locks: they should appear, and after one marker edit they are saved in the project.
2. Drop audio on A3. Add A4 and drag a clip down onto it. Mute A4 and export: the clip should be silent. Solo A4 and export: only A4 should be heard among A3–A8, while narration and music are unchanged.
3. Press each tool key (V, A, B, N, Y, U, C) and repeat each gesture on two touching clips. Undo and redo each one.
4. Shift+C with clips on three tracks and one track locked: the locked track must stay uncut.
5. Start a render, then try to delete that project (expect "Wait for rendering…"). Cancel the render and delete again (expect success).
6. Ctrl+wheel over the timeline: the time under the pointer stays in place. Scroll across a long project: it should feel smooth.
7. Recheck the RC4 items that are still open: Whisper on the clean-audio sample that previously failed, and any local or cloud generation provider you plan to ship.

## User test follow-up: editable cuts, captions, audio and overlays

This follow-up addresses the latest local test findings while keeping 0.5.3 and the existing 0.7.0 features intact. The candidate API build ID is `v0.7.0-rc4`; the packaged app version remains 0.7.0 until a stable release is approved.

- **Cutting before render:** scissors now cuts at the timeline playhead. A single source shot can split without rendering even if it has generated caption segments or timed text. Both scenes continue to reference the original media with source ranges/audio settings divided at the cut; caption segments and timed text are divided and rebased. Filmstrip thumbnails start at each segment's source-in time. A ratio change exits the last-export monitor so an old export cannot look like it restored the full source. Multiple shots, accepted separate narration, animation or speed changes still require rendering before a baked split.
- **Regenerating Auto Captions:** the action changes to **Regenerate captions** when a transcript exists. When both a scene narration take and video sound exist, a picker lets the user select the source. Text/Text+/Text Box editing appears immediately below Auto Captions.
- **A3 timeline audio:** project-level audio clips are independent of scene narration (A1), source-video sound (A2), and the whole-project music bed. Drop MP3, WAV, M4A, AAC, OGG or FLAC from the Media Pool or desktop onto A3. Pressing an A3 clip places the playhead there before drag starts, so the scissors split the clip at the intended time. Clips may overlap and are vertically stacked. They support drag-to-move, edge trim, mute, volume and fades; export mixes each unmuted clip at its sequence time. The Audio tab exposes these clip controls alongside the existing music-bed controls. Settings live additively in `finishing_json`, so existing projects keep their music settings. The backend limits projects to 64 audio clips and checks project ownership, ranges, levels, fades and mute values.
- **Overlay composition and stickers:** the side-by-side, stacked and 2×2 layout presets now explicitly arrange video/image PiP layers added from the Media Pool or Upload. Stickers and emoji are marked separately and keep their own placement. The preset buttons include small layout diagrams, visible labels and disabled states until enough media layers are added. Sticker tiles remain constrained to their cards; custom PNG/WebP uploads support transparency and JPEG is accepted with its solid background.
- **Local captions:** Local Whisper stays the free default. Input is normalized to mono 16 kHz and dynamically leveled when the local FFmpeg build supports it; failure to normalize falls back to the original audio. If voice activity detection returns no words for short or quiet speech, transcription retries without VAD. Recognized phrase text without usable word alignment still creates editable caption clips with estimated word intervals, labeled as estimated. This improves the reported clean-video-sound/manual-English case, which still needs the user's same source tested on Windows before release.
- **Transition picker:** the picker now shows 28 curated, visibly distinct transition families instead of dozens of repeated directional variants. Existing transition identifiers from older projects remain supported by the renderer and the Inspector labels legacy choices instead of losing them.
- **Project deletion after interruption:** startup marks queued/running/cancelling database jobs as interrupted. Deletion also checks the current process's live job IDs, so stale rows can be recovered while the editor stays open; an active render or generation still protects its project.
- **Cut feedback:** timeline validation messages, including the yellow warning shown in the test screenshot, now clear automatically after 3.5 seconds.

### Follow-up roadmap for the larger creative requests

The following items are not part of this editor-fix candidate. They need their own measurable quality, hardware, licensing and render-time work. Add them as optional, reversible tools and keep original media available.

| Priority | Feature | Practical first implementation |
|---|---|---|
| 1 | Voice isolation | Optional local model/service with compatibility checks, first-run model download/progress, bypass and A/B preview; store a processed stem alongside the original. |
| 2 | Tracked overlays and object attachment | User-set tracking points and editable keyframes first; optional local AI tracking after. Add restrained float/pendulum motion as a keyframe preset. Enables stickers, callouts, blur/redaction and text to follow an object. |
| 3 | Subject cutout/background removal | Segment a selected object/person, track/refine its matte through the shot, and render separate foreground/background layers. Requires VRAM/time benchmarks and a correction path for hair/occlusion. |
| 4 | Speed-ramp curves/optical flow | Add a visual velocity curve, then separately benchmark frame interpolation. Keep source timing editable and make slower interpolation optional. |
| 5 | Text reveal/material fills | Add original SceneForge reveal masks first. Prompt-generated texture fills can be generated/imported as a texture and clipped inside the text mask; also allow licensed/user-supplied textures without AI. |
| 6 | Grade and effects packs | Add halation/film grades, procedural camera-shake presets, practical lens-flare overlays with Screen/Add blending and masked text-reveal transitions. Use original or licensed assets, retain LUT/filter tools, and document pack licenses. |
| 7 | Beat-aware music re-edit | Build on current beat detection with trim candidates, downbeat-aware section matching and crossfades; preview before applying and preserve the source soundtrack. |
| 8 | Fusion-style node graph | A full node compositor is a separate architecture project. Consider a constrained non-destructive effect-order graph only after clip-level tracks and parameter serialization are stable. |

Resolve Studio currently describes AI object isolation/tracking, Speed Warp optical-flow retiming and audio AI tools; Adobe documents Object Masking and mask tracking. This is a feasibility comparison, not a promise of SceneForge feature parity. References: [Blackmagic Resolve Studio](https://www.blackmagicdesign.com/products/davinciresolve/studio), [Adobe Object Masking](https://helpx.adobe.com/premiere/desktop/add-video-effects/work-with-masks/object-masking.html), [Adobe mask tracking](https://helpx.adobe.com/premiere/desktop/add-video-effects/work-with-masks/track-masks.html), and [CapCut editing tools](https://www.capcut.com/tools).

## Latest UI and timeline follow-up

- **Project home:** Preferences is under File. Removed the redundant static mode tabs, provider selector and duplicate new-project defaults. Project aspect/frame rate stay in Create Project; the existing top-level AI Engines and Help menus, Media Pool and editor features remain.
- **Editor navigation and themes:** Added an explicit Projects button to return to create/open projects instead of Reload. The upper-right Theme menu offers Graphite Night, Daylight, Midnight Blue and Warm Studio. Corrected Daylight contrast for inspector buttons/forms, cards and timeline panels.
- **Safe zones and close behavior:** Restored the Safe zones toggle above the timeline. Close readiness now checks live in-process generation/render/export work, so an idle app is not held open by stale job rows left after a prior crash.
- **RC4 follow-up fixes:** A3 pointer-down places the playhead before a drag and allows scissors splitting; yellow cut feedback auto-dismisses; orphaned render records no longer block deletion while the editor is open; local Whisper uses normalized input, VAD retry and estimated phrase timing when word-level timestamps are unavailable. Media layout presets target video/image PiP layers, not stickers. The transition picker is curated to 28 choices while old project types remain renderable.
- **Timeline tools:** Added per-project locks for T1 text, V1 picture, A1 narration and A2 clip sound; A2 quick mute buttons for embedded source audio; and explicit ripple-delete labels/confirmation that state the scene gap closes. Existing snapping, named markers, scene drag-reorder, eligible linked video/audio trims, split and undo/redo remain.
- **Visual library:** The candidate offers 28 curated transitions (with 55 prior transition IDs still renderable), 31 caption styles and a searchable 66-item emoji/graphic-sticker library. The Effects panel groups 8 additional color filters (Golden hour, Arctic, Portra film, Matte fade, Color pop, Teal shadows, Rose glow and Blue monochrome) separately and adds FFmpeg-rendered Chromatic split and Motion trail effects. Existing visual looks, LUT tools and effect panels remain.
- **Limits:** Visual editing is still arranged as scenes on V1. A3 now supports independent project audio clips, but unrestricted clip-based video editing across arbitrary tracks and full multitrack compositing remain future work.

### Latest regression checks (2026-09-30)

- Frontend production build passed (TypeScript + Vite); minified editor bundle is 555.65 kB and Vite prints its advisory above 500 kB.
- Frontend tests passed after the RC4 edits: 226 editor component checks, 19 unit checks, 2 video-generation flows and 6 share-dialog checks.
- Local Whisper regression script passed five mocked checks, and an FFmpeg smoke check produced mono 16 kHz WAV input. Python compilation and `git diff --check` passed. Actual Whisper inference on the user's clean audio sample still needs Windows/manual validation.
- Desktop tests passed: 18 lifecycle, close-flow and storage checks.
- Direct backend integration scripts passed for video generation, stale/live close readiness, and FFmpeg filter smoke tests. Chromatic split and Motion trail also passed the full scene filter graph.
- Python compile checks and `git diff --check` passed. Frontend flows use a mock API; they do not replace installed-app visual testing.
- The follow-up source-split integration test passed against real FFmpeg media: it verifies an unrendered cut, linked source audio, split caption/text timings, segment thumbnail selection and a complete export.
- The finishing/export integration test passed all 22 checks, including multiple A3 clips, fade validation, audible clip placement and silence in the gap. The suite emits a Starlette/httpx deprecation warning from its test client; all checks succeeded.
- GitHub Release workflow [36763871298](https://github.com/EzioDEVio/SceneForge/actions/runs/36763871298) passed on Windows, Linux and macOS. Windows packaged render, installer build, installed-app startup and uninstall smoke checks passed. The Windows installer is temporary Actions artifact `11120491437`, not a published release.
- Build and render checks workflow [36763871406](https://github.com/EzioDEVio/SceneForge/actions/runs/36763871406) failed in `tests/integration/test_editor_plus.py`: its “Cannot delete project during an active render” test received a status other than the expected 409. The credential tests and 40 combined checks before it passed; because the script stops on failure, later integration tests in that sequence did not run. Fix and rerun this gate.
- No live ComfyUI, Google Veo or Runway generation was repeated for this candidate. Test the fresh Windows installer, local Whisper using the previously failing clean-audio sample, and any local/cloud video provider that you plan to use before merge or publication. No stable tag or public release is being created.

## Initial 0.7.0 text-to-video milestone

- Added a separate text-to-video workspace while preserving the existing AI Engines and Help menus, editor tabs, scenes, Media Pool, timeline, captions, effects and overlays.
- Added a curated local catalog for LTX-2.5 Fast, Wan 2.1 T2V 1.3B, Wan 2.2 TI2V 5B, Wan 2.2 T2V A14B, and compatible custom ComfyUI workflows.
- Added paid integrations for Google Veo 3.1 Lite/Fast/Standard and Runway Gen-4.5/WAN 3.0. Rates are shown per second/per resolution and the selected clip receives a total estimate. Rates were checked 2026-09-28; provider billing can change. Cloud starts require explicit cost confirmation checked by both UI and API.
- Added model-specific ratio, duration and resolution validation; local custom dimensions (multiples of 16); API workflow import; local ComfyUI status; loopback-only server access; background job progress/cancellation; and output media validation.
- Generated output becomes a normal project Media Pool asset. The user can add it to the selected scene or create a timeline scene. The caption action uses existing local speech transcription (scene narration when present, otherwise video sound) and opens Text for timed caption edits and styles. Existing Clip Audio, Effects and Overlays remain available.
- Local ComfyUI and model weights/workflows are installed separately and are not bundled. A visible notice explains that custom nodes run inside ComfyUI with the user's permissions. Paid provider API keys use the OS credential store.
- Added UI interaction tests for local custom-size generation → asset insertion → caption handoff and cloud rate display → explicit paid confirmation.
- The Release workflow is configured to create temporary Windows, Linux and macOS build artifacts after branch push. A branch build is not a GitHub release; no stable tag is created by this milestone.

### Earlier verification notes (superseded by Latest regression checks above)

- `npm run build` passed on the initial text-to-video snapshot (later candidate build: 540.73 kB).
- `npm test` passed on the initial text-to-video snapshot (current candidate: 215 editor checks, 19 unit checks, 2 video-generation flows and 6 share checks).
- `npm test` in `desktop/` passed on the initial snapshot (current candidate: 18 checks).
- `python -m compileall -q backend/app tests/integration/test_video_generation.py` and `git diff --check` passed.
- Backend integration scripts now pass locally; the GitHub Linux keyring gate remains a CI-only check.
- No live ComfyUI, Google Veo or Runway request was repeated in the latest regression pass. The user previously tested Runway successfully and generated ComfyUI clips; broad prompts produced low-quality output and took about 8–10 minutes for five seconds.
- Complete candidate CI and test the fresh Windows installer before merge/publication; do not create a stable release tag before those gates pass.

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
| More caption styles | 31 styles are available, including Bold outline, Yellow box, Green karaoke, Blue glow, Handwritten, News lower third, Elegant serif, TikTok word pop, Reels minimal, Creator highlight, Arabic clean and Neon lime karaoke. | Review visual consistency in a real browser and rendered scenes; preserve Arabic shaping and per-word timing. |
| More effects and helpful feature descriptions | Many non-look effects already exist (for example glitch, Old Film, camera shake, spotlight, redaction, light leaks, split toning, LUTs, annotations). Effect tiles have previews/search and section cards. | Click-open guidance now covers these tabs and major feature sections; some low-level controls may still need more specific explanations as user testing identifies confusion. |
| Clip Audio controls | Separate inspector with volume, mute, narration ducking, fade-in and fade-out; backend validation/rendering and persistence implemented. | Manually verify on actual source clips in browser/desktop and after split, undo, and export. |
| Trending transitions | 28 curated choices with live previews, including film burn, cover/reveal, slices, wind, diagonal wipes and distance morph. Older saved transition IDs remain renderable. | Review live previews and rendered results in the Windows candidate before release. |
| Social sharing | Post-export prompt includes download, desktop open-file-location, platform links and posting guidance. | Direct account uploads require platform developer setup, user authorization and policy review. |
| Timeline tools | Undo/redo, scene move/reorder, split/restore, A2 source-audio lane, drag/drop, multi-select, snapping, named markers, playhead, keyboard shortcuts, constrained linked video/audio edge trimming, per-lane locks, A2 quick mute, and scene ripple delete are available. Deleting a scene closes the sequence gap. | Track solo, unlinking audio, arbitrary independent clip moves, and trim handles for general/multitrack audio remain backlog. |
| Stickers, filters, emoji | Searchable 66-item emoji/graphic-sticker picker; 8 extra color filters; Chromatic split and Motion trail creative effects; existing LUT/looks remain. | Rights-cleared themed sticker packs, favorites and downloadable pack management remain possible follow-up work. |
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

## 0.7.0 release-candidate continuation (2026-09-30)

The public release remains 0.5.3. The 0.7.0 RC4 source is on `chatgpt/0.7.0-video-generation` at `c9a8ee74831ab8ebc0a48aa0875e8139c98f568b` (tree `c813c8cdfe63446734c19e4031437ce531aedcea`). Its package version is 0.7.0 and API build ID is `v0.7.0-rc4`. The CI build-and-render failure must be resolved and the Windows installer must be tested by the user before merge or publication.

The candidate includes the preferences/theme/close-flow improvements, local hardware guidance, text-to-video and image candidate selection, paid provider estimates and confirmation, timeline/audio/caption fixes, curated transitions, effects/filters and sticker/layout work recorded above. These are RC features, not claims about the 0.5.3 public release.

### Current verification and artifacts

- Release workflow [36763871298](https://github.com/EzioDEVio/SceneForge/actions/runs/36763871298): **success** for Windows, Linux and macOS. Windows packaged render and installed startup/uninstall smoke passed. Open the run and download the `SceneForge-Studio-Windows` artifact (ID `11120491437`); it contains `SceneForge-Studio-0.7.0-Windows-x64-Setup.exe`. This is a temporary Actions artifact, not a GitHub Release.
- Build and render checks [36763871406](https://github.com/EzioDEVio/SceneForge/actions/runs/36763871406): **failure** in `tests/integration/test_editor_plus.py`, which expected project deletion during an active render to return HTTP 409 but received another status. Linux keyring credential tests and 40 combined checks earlier in that job passed. Tests sequenced after the assertion did not run.
- Frontend: build passed; 226 component checks, 19 unit checks, two video-generation flows and six share checks passed. Desktop suite: 18 passed. Local video-generation integration and real-FFmpeg source-split/audio-finishing tests passed. Local Whisper mock and normalization smoke checks passed; actual user-sample inference is unverified.
- Do not merge to `main`, tag or publish 0.7.0 yet. Resolve and rerun the failed CI check, then test the installer and local/cloud workflows that matter to the user.

### What is not bundled or implemented

- ComfyUI, custom workflow nodes/files and model weights remain separate installs. Provider keys are user-supplied and stored with the OS credential store. No direct account upload to social platforms is implemented; sharing gives the user export/location and platform instructions.
- Vast.ai is still a separate feasibility proposal, not an app integration. Auto cutout, subject/object tracking, optical-flow interpolation, advanced voice isolation, AI music re-editing and a full Fusion-style node graph remain roadmap work.
- The timeline is still scene-based for video. Independent A3 audio clips are editable, while unrestricted multitrack video compositing and universal frame-accurate clip editing remain future work.

## Source archive contents

The accompanying full-source ZIP contains the complete tracked SceneForge project tree (frontend, backend, Electron desktop app, assets, setup/build scripts, workflows, tests and documentation) plus a Git bundle with repository history. It excludes installed dependency folders, build caches/output, local databases and `backend/data` user project files. It is a source package, not a platform installer; the Windows installer is downloaded separately from the successful Release Actions run above. Optional AI model weights, ComfyUI, custom nodes and user API keys are not bundled.
