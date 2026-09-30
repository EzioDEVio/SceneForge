# SceneForge Studio — Project History and Combined Handoff

**Prepared:** 2026-09-30  
**Project:** [EzioDEVio/SceneForge](https://github.com/EzioDEVio/SceneForge)  
**Latest published release:** 0.5.3  
**Current candidate:** 0.7.0 RC5, unreleased (local branch `claude/0.7.0-rc5-timeline` on top of RC4)  
**Candidate branch:** `chatgpt/0.7.0-video-generation`  
**Candidate commit:** `c9a8ee74831ab8ebc0a48aa0875e8139c98f568b` (tree `c813c8cdfe63446734c19e4031437ce531aedcea`)

This is the single-document handoff: it combines current status and next steps, the session handoff, and cumulative release notes. Historical WIP/RC entries are development snapshots, not published releases. The earliest release notes present in this repository begin at 0.2.0 RC3; earlier prototype history is not reconstructed in the available records.

## Read this status first

- **RC5 update (2026-09-30):** the RC4 CI failure is fixed (see the RC5 section in Appendix A). RC5 adds timeline v1: audio tracks A3–A8 with mute/solo/lock, edit tools, and project-saved range/colour markers. The full local CI sequence passes. RC5 has not been pushed; GitHub CI must rerun after an authorized push. The RC4 status notes below are kept for history.

- **Public release stays 0.5.3.** The 0.6.0 WIP and 0.7.0 RC4 source additions have not been published as stable releases.
- **Release workflow:** [Run 36763871298](https://github.com/EzioDEVio/SceneForge/actions/runs/36763871298) succeeded for Windows, Linux and macOS. The Windows job built the installer and passed packaged render, installed-app startup and uninstall smoke checks. The Windows artifact is `SceneForge-Studio-Windows` (artifact ID `11120491437`) and contains `SceneForge-Studio-0.7.0-Windows-x64-Setup.exe`. It is a temporary Actions artifact, not a GitHub Release.
- **Build/render checks:** [Run 36763871406](https://github.com/EzioDEVio/SceneForge/actions/runs/36763871406) failed in `tests/integration/test_editor_plus.py`. Its active-render deletion assertion expected HTTP 409 and received another status. Linux credential checks and 40 earlier combined checks passed; later scripted tests did not run. This gate needs a fix and rerun.
- **Local checks:** frontend production build passed; 226 component checks, 19 unit checks, 2 video-generation UI flows and 6 share-dialog checks passed; desktop tests passed (18). Local integration checks passed for generation, real-FFmpeg source splitting and A3 audio finishing. Local Whisper mock/normalization checks passed, but transcription on the user's previously failing clean-audio sample has not been verified.
- **Next release gate:** fix/rerun the failed CI test, then the user tests the Windows installer and relevant local/cloud generation/caption workflows. Keep this candidate unmerged and unpublished until those gates pass.
- **No live provider run** (ComfyUI, Google Veo or Runway) was repeated for RC4. A prior local Runway generation was reported successful; that result is not a substitute for testing this candidate.

## Work inventory at a glance

- Preserved the 0.5.3 editor baseline and its original AI Engines/Help experience while carrying forward the reviewed 0.6.0 WIP work.
- Added text-to-video and multi-option image generation, local ComfyUI workflow guidance, hardware recommendations, cloud model pricing/estimates and explicit paid-generation confirmation.
- Added preferences/themes, corrected theme contrast, clarified project setup, restored Safe zones, and added a native save/exit decision dialog.
- Expanded caption/timeline/audio editing, independent stacked A3 clips, timed editable captions, caption regeneration/source selection, local Whisper recovery, layout presets for media overlays, curated transitions, extra filters/effects, and searchable stickers/emoji.
- Added sharing guidance after export, feature-help popovers, social platform instructions, and comprehensive project/release documentation.
- Kept later-requested research items (Vast.ai, subject cutout, tracking, optical-flow slow motion, AI voice isolation, AI music re-editing and a full node graph) documented as roadmap rather than claiming they shipped.

## Source archive contents

The companion ZIP contains the complete tracked SceneForge source tree (frontend, backend, Electron desktop app, assets, setup/build scripts, workflows, tests and documentation) plus a Git bundle containing repository history. Installed dependencies, generated build output/caches, local databases and `backend/data` user project files are excluded. This is a source package, not a platform installer. Optional AI model weights, ComfyUI, custom nodes and provider API keys are not bundled. The Windows installer is a separate temporary Actions artifact linked above.

For source setup, install boundaries, provider configuration and current app features, see [README.md](README.md). Detailed historical release entries are reproduced in Appendix B and also maintained in [`desktop/RELEASE_NOTES.md`](desktop/RELEASE_NOTES.md). The working handoff remains in [`handoff.md`](handoff.md).

---

## Appendix A — Complete session handoff

## SceneForge 0.7.0 Release Candidate — Session Handoff

**Prepared:** 2026-09-30
**Current source:** branch `chatgpt/0.7.0-video-generation` in `EzioDEVio/SceneForge` (candidate commit `c9a8ee7`; local source tree matches it)
**Current working version:** 0.7.0 release candidate (unreleased)
**Base:** preserved `chatgpt/0.6.0-wip.10` editor branch
**Published baseline:** GitHub release `0.5.3`

### Purpose and handling

This handoff preserves the earlier 0.5.3/0.6.0 review below and records the 0.7.0 text-to-video milestone plus the latest UI/timeline follow-up. The 0.5.3 published release remains unchanged; 0.6.0-wip.10 is the source baseline for this additive branch. The 0.7.0 candidate is not a stable release. Keep it separate and wait for a fresh Windows installer test before merge or publication.

Reviewed inputs in this workspace include the 0.5.3 source ZIP, the original 0.6.0 WIP ZIP, reviewed wip.2–wip.6 snapshots, their READMEs and handoffs, the SceneForge session handoff, chat notes, and the user screenshots. The 0.5.3 technical handoff predates the 0.5.3/0.6.0 work and should not be treated as a complete description of the present build.

### 0.7.0 RC5 — CI fix and timeline v1 (Claude continuation, 2026-09-30)

**Branch:** local `claude/0.7.0-rc5-timeline`, based on `codex/0.7.0-release-candidate` source commit `3d6107a`. That commit's tree `c813c8c` is identical to GitHub `chatgpt/0.7.0-video-generation` at `c9a8ee7`. Nothing has been pushed, merged, tagged or published. No paid or live provider call was made. The Windows UI was **not** tested by Claude.

#### What changed
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

#### Verification (Linux container, Python 3.12, Node 22, system FFmpeg)
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

#### Manual Windows checklist (not yet run)
1. Install the RC5 installer from a CI artifact. Open an RC4 project that has markers and locks: they should appear, and after one marker edit they are saved in the project.
2. Drop audio on A3. Add A4 and drag a clip down onto it. Mute A4 and export: the clip should be silent. Solo A4 and export: only A4 should be heard among A3–A8, while narration and music are unchanged.
3. Press each tool key (V, A, B, N, Y, U, C) and repeat each gesture on two touching clips. Undo and redo each one.
4. Shift+C with clips on three tracks and one track locked: the locked track must stay uncut.
5. Start a render, then try to delete that project (expect "Wait for rendering…"). Cancel the render and delete again (expect success).
6. Ctrl+wheel over the timeline: the time under the pointer stays in place. Scroll across a long project: it should feel smooth.
7. Recheck the RC4 items that are still open: Whisper on the clean-audio sample that previously failed, and any local or cloud generation provider you plan to ship.

### User test follow-up: editable cuts, captions, audio and overlays

This follow-up addresses the latest local test findings while keeping 0.5.3 and the existing 0.7.0 features intact. The candidate API build ID is `v0.7.0-rc4`; the packaged app version remains 0.7.0 until a stable release is approved.

- **Cutting before render:** scissors now cuts at the timeline playhead. A single source shot can split without rendering even if it has generated caption segments or timed text. Both scenes continue to reference the original media with source ranges/audio settings divided at the cut; caption segments and timed text are divided and rebased. Filmstrip thumbnails start at each segment's source-in time. A ratio change exits the last-export monitor so an old export cannot look like it restored the full source. Multiple shots, accepted separate narration, animation or speed changes still require rendering before a baked split.
- **Regenerating Auto Captions:** the action changes to **Regenerate captions** when a transcript exists. When both a scene narration take and video sound exist, a picker lets the user select the source. Text/Text+/Text Box editing appears immediately below Auto Captions.
- **A3 timeline audio:** project-level audio clips are independent of scene narration (A1), source-video sound (A2), and the whole-project music bed. Drop MP3, WAV, M4A, AAC, OGG or FLAC from the Media Pool or desktop onto A3. Pressing an A3 clip places the playhead there before drag starts, so the scissors split the clip at the intended time. Clips may overlap and are vertically stacked. They support drag-to-move, edge trim, mute, volume and fades; export mixes each unmuted clip at its sequence time. The Audio tab exposes these clip controls alongside the existing music-bed controls. Settings live additively in `finishing_json`, so existing projects keep their music settings. The backend limits projects to 64 audio clips and checks project ownership, ranges, levels, fades and mute values.
- **Overlay composition and stickers:** the side-by-side, stacked and 2×2 layout presets now explicitly arrange video/image PiP layers added from the Media Pool or Upload. Stickers and emoji are marked separately and keep their own placement. The preset buttons include small layout diagrams, visible labels and disabled states until enough media layers are added. Sticker tiles remain constrained to their cards; custom PNG/WebP uploads support transparency and JPEG is accepted with its solid background.
- **Local captions:** Local Whisper stays the free default. Input is normalized to mono 16 kHz and dynamically leveled when the local FFmpeg build supports it; failure to normalize falls back to the original audio. If voice activity detection returns no words for short or quiet speech, transcription retries without VAD. Recognized phrase text without usable word alignment still creates editable caption clips with estimated word intervals, labeled as estimated. This improves the reported clean-video-sound/manual-English case, which still needs the user's same source tested on Windows before release.
- **Transition picker:** the picker now shows 28 curated, visibly distinct transition families instead of dozens of repeated directional variants. Existing transition identifiers from older projects remain supported by the renderer and the Inspector labels legacy choices instead of losing them.
- **Project deletion after interruption:** startup marks queued/running/cancelling database jobs as interrupted. Deletion also checks the current process's live job IDs, so stale rows can be recovered while the editor stays open; an active render or generation still protects its project.
- **Cut feedback:** timeline validation messages, including the yellow warning shown in the test screenshot, now clear automatically after 3.5 seconds.

#### Follow-up roadmap for the larger creative requests

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

### Latest UI and timeline follow-up

- **Project home:** Preferences is under File. Removed the redundant static mode tabs, provider selector and duplicate new-project defaults. Project aspect/frame rate stay in Create Project; the existing top-level AI Engines and Help menus, Media Pool and editor features remain.
- **Editor navigation and themes:** Added an explicit Projects button to return to create/open projects instead of Reload. The upper-right Theme menu offers Graphite Night, Daylight, Midnight Blue and Warm Studio. Corrected Daylight contrast for inspector buttons/forms, cards and timeline panels.
- **Safe zones and close behavior:** Restored the Safe zones toggle above the timeline. Close readiness now checks live in-process generation/render/export work, so an idle app is not held open by stale job rows left after a prior crash.
- **RC4 follow-up fixes:** A3 pointer-down places the playhead before a drag and allows scissors splitting; yellow cut feedback auto-dismisses; orphaned render records no longer block deletion while the editor is open; local Whisper uses normalized input, VAD retry and estimated phrase timing when word-level timestamps are unavailable. Media layout presets target video/image PiP layers, not stickers. The transition picker is curated to 28 choices while old project types remain renderable.
- **Timeline tools:** Added per-project locks for T1 text, V1 picture, A1 narration and A2 clip sound; A2 quick mute buttons for embedded source audio; and explicit ripple-delete labels/confirmation that state the scene gap closes. Existing snapping, named markers, scene drag-reorder, eligible linked video/audio trims, split and undo/redo remain.
- **Visual library:** The candidate offers 28 curated transitions (with 55 prior transition IDs still renderable), 31 caption styles and a searchable 66-item emoji/graphic-sticker library. The Effects panel groups 8 additional color filters (Golden hour, Arctic, Portra film, Matte fade, Color pop, Teal shadows, Rose glow and Blue monochrome) separately and adds FFmpeg-rendered Chromatic split and Motion trail effects. Existing visual looks, LUT tools and effect panels remain.
- **Limits:** Visual editing is still arranged as scenes on V1. A3 now supports independent project audio clips, but unrestricted clip-based video editing across arbitrary tracks and full multitrack compositing remain future work.

#### Latest regression checks (2026-09-30)

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

### Initial 0.7.0 text-to-video milestone

- Added a separate text-to-video workspace while preserving the existing AI Engines and Help menus, editor tabs, scenes, Media Pool, timeline, captions, effects and overlays.
- Added a curated local catalog for LTX-2.5 Fast, Wan 2.1 T2V 1.3B, Wan 2.2 TI2V 5B, Wan 2.2 T2V A14B, and compatible custom ComfyUI workflows.
- Added paid integrations for Google Veo 3.1 Lite/Fast/Standard and Runway Gen-4.5/WAN 3.0. Rates are shown per second/per resolution and the selected clip receives a total estimate. Rates were checked 2026-09-28; provider billing can change. Cloud starts require explicit cost confirmation checked by both UI and API.
- Added model-specific ratio, duration and resolution validation; local custom dimensions (multiples of 16); API workflow import; local ComfyUI status; loopback-only server access; background job progress/cancellation; and output media validation.
- Generated output becomes a normal project Media Pool asset. The user can add it to the selected scene or create a timeline scene. The caption action uses existing local speech transcription (scene narration when present, otherwise video sound) and opens Text for timed caption edits and styles. Existing Clip Audio, Effects and Overlays remain available.
- Local ComfyUI and model weights/workflows are installed separately and are not bundled. A visible notice explains that custom nodes run inside ComfyUI with the user's permissions. Paid provider API keys use the OS credential store.
- Added UI interaction tests for local custom-size generation → asset insertion → caption handoff and cloud rate display → explicit paid confirmation.
- The Release workflow is configured to create temporary Windows, Linux and macOS build artifacts after branch push. A branch build is not a GitHub release; no stable tag is created by this milestone.

#### Earlier verification notes (superseded by Latest regression checks above)

- `npm run build` passed on the initial text-to-video snapshot (later candidate build: 540.73 kB).
- `npm test` passed on the initial text-to-video snapshot (current candidate: 215 editor checks, 19 unit checks, 2 video-generation flows and 6 share checks).
- `npm test` in `desktop/` passed on the initial snapshot (current candidate: 18 checks).
- `python -m compileall -q backend/app tests/integration/test_video_generation.py` and `git diff --check` passed.
- Backend integration scripts now pass locally; the GitHub Linux keyring gate remains a CI-only check.
- No live ComfyUI, Google Veo or Runway request was repeated in the latest regression pass. The user previously tested Runway successfully and generated ComfyUI clips; broad prompts produced low-quality output and took about 8–10 minutes for five seconds.
- Complete candidate CI and test the fresh Windows installer before merge/publication; do not create a stable release tag before those gates pass.

#### Provider catalog, published rates and setup

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

#### Files changed for 0.7.0-wip.1

- Backend: `backend/app/providers/video_generation.py`, `backend/app/api/video_generation.py`, `backend/app/domain/schemas.py`, `backend/app/api/providers.py`, `backend/app/workers/jobs.py`, `backend/app/main.py`.
- Frontend: `frontend/src/VideoGenerationPanel.tsx`, `frontend/src/App.tsx`, `frontend/src/api.ts`, `frontend/src/styles.css`; UI regression test: `frontend/tests/video_generation.mjs`.
- Build metadata and CI: `desktop/package.json`, `desktop/package-lock.json`, `.github/workflows/checks.yml`, `.github/workflows/release.yml`.
- Notes: `README.md`, `desktop/RELEASE_NOTES.md`, `docs/REVIEW_0.7.0_VIDEO_GENERATION.md`.

---

### Earlier 0.6.0 handoff and history

### User requirements carried forward

- Preserve all working 0.5.3 features and existing tabs/menus; enhancements must be additive.
- Keep the AI Engines menu and provider configuration accessible, plus the existing Scenes, Media Pool, and Transitions library tabs. The duplicate AI Engines library tab was removed.
- Repair timeline undo/redo, clip audio controls, scene movement, and cutting/splitting so source sound follows its video.
- Keep clip audio controls separate from Motion and make audio settings functional and persistent.
- Make the app friendlier for nontechnical users: free local speech captions, visible installation/service requirements, modern narration and export controls, and contextual help for features.
- Improve transitions, captions, effects, timeline operations, stickers/filters, title cards, and sharing without removing established features.

### Baseline and 0.6.0 feature inventory

#### Version lineage and authorship

- The GitHub `release/v0.5.3` branch remains unchanged and is the published base.
- The locally tested 0.6.0 WIP source (which includes Claude-authored changes) is carried forward as a clearly named snapshot branch. Its original unpublished per-commit Git authorship is not reconstructed; the snapshot commit documents that limitation.
- The reviewed ChatGPT-assisted changes are a distinct commit on `chatgpt/0.6.0-wip.10`, based on that 0.6.0 snapshot. Both branches live in the existing repository; no second repository is created.
- No stable release tag is created by this work. The Release workflow runs for pushes to `chatgpt/0.6.0-wip.10` and uploads branch builds as temporary Actions artifacts using `--publish never`; tagged releases retain their existing behavior.

#### Preserved 0.5.3 features

The released baseline includes source-video audio, per-video volume/mute/narration ducking, scene duration tied to video length, per-scene countdown intros, vertical-project fit behavior and safe zones, captions from speech through configured cloud providers, project/file menus, and the existing AI Engines/Help desktop experience. These are baseline features, not additions made by this review. Do not remove or silently replace them.

#### Broader 0.6.0 WIP additions present in the submitted work

- More transitions and live transition previews (42 transition choices total), caption styles (24 total), batch/multi-select apply, progress cards, export presets/advanced options, animated GIF/audio-only formats, and SRT/VTT export.
- Free local Faster-Whisper transcription as the default automatic-caption route; ElevenLabs and OpenAI remain optional cloud services. The multilingual model downloads on first use and runs locally afterward.
- Improved export compatibility using H.264 4:2:0 and fast-start MP4 settings; per-video sound and clip duration are retained in vertical exports.
- Additional caption styling and transitions; auto-closing/minimizable multi-select actions; narration-script and export-panel styling.
- Service and installer documentation: the desktop package bundles the app, private backend runtime, and FFmpeg, but not optional Chatterbox/Kokoro servers, Stable Diffusion models, or Whisper model weights.

These features largely predate the screenshot repair work. Refer to `desktop/RELEASE_NOTES.md` and `docs/REVIEW_0.6.0_WIP.md` for the detailed WIP inventory.

### Troubleshooting chronology and repairs in the reviewed source

#### Regression report from the user

The user reported an unusable build and supplied screenshots titled `the original UI release 0.5.3.png`, `this is the build you handed me which is broken and missing the Ai engine tab and others.png`, `thumbnais inside the motion tab.png`, and `none-functional audio button or crop and focal .png`. The later screenshots `new_sound_panel.png` and `auto caption layout stretched out.png` added clip-audio and caption-layout feedback.

Findings and resolution:

1. **AI Engines and Help access:** the original 0.5.3 screenshot showed a top-level AI Engines menu, while the reviewed wip.4 interface had lost that access. The top-level AI Engines menu and Help/About were restored. The original Scenes, Media Pool, and Transitions library tabs and provider settings remain. The redundant AI Engines library tab was removed. Help/update capabilities are exposed through the desktop shell; browser mode cannot provide native updater/file-menu behavior.
2. **Clip sound mixed into Motion:** A2 source-audio timeline blocks now route to a separate **Clip Audio** inspector. Volume, mute, and narration ducking remain; fade-in/fade-out controls were added in wip.6. Fade settings are validated, persisted, applied in FFmpeg, and carried through split/undo.
3. **Nonfunctional-looking crop/focal/media thumbnails:** media crop/focal controls now use generated poster thumbnails with a fallback instead of a broken placeholder. Crop/focal and audio slider edits save on commit/release. Regression checks cover committed audio values and fade persistence.
4. **Crowded Auto captions card:** the Auto captions controls stack in a narrow inspector and switch to two columns only when the panel is wide enough.
5. **Timeline editing/history:** undo/redo coverage was added for scene add/delete, media insertion, title cards, narration attach/remove, scene reorder, clip sound, and scene split (up to 100 recent operations per session). Split preserves source-audio and speed settings; undo restores the original scene/clip identities. Whole scene blocks can be dragged to reorder, and dropping media at timeline gaps/scene edges inserts before/after as indicated.

#### Timeline scope boundary

SceneForge remains a scene-assembly editor. It supports scene reordering/insertion, source-audio lane selection, scene splitting, and scene history. It is not yet a full nonlinear editor: independent arbitrary clip movement across unlimited tracks, frame-accurate trim handles for every media type, full waveform editing for embedded clip sound, and a multitrack compositing graph remain incomplete. Do not describe the current timeline as equivalent to DaVinci Resolve.

### Current 0.6.0-wip.6 changes

- Added **Clip Audio** fade-in and fade-out controls (0–10 seconds) alongside existing volume, mute, and narration ducking. The backend rejects out-of-range fade values and FFmpeg applies fades after the clip's source trim.
- Kept fade values in shot audio state and through clip split/undo, with integration coverage.
- Made the Auto captions card responsive to inspector width to prevent the narrow-panel layout seen in the screenshot.
- Updated frontend/backend build identifiers and desktop package version to `0.6.0-wip.6`.
- Updated README/release/review documentation and created this consolidated handoff.

### Current 0.6.0-wip.9 additions (previous WIP)

- **Post-export sharing:** a successful export opens a Share dialog with download, desktop open-file-location, device/browser share fallback, and instructions for YouTube, TikTok, Instagram and Facebook. It does not upload automatically. Browser mode directs users to Downloads when native folder reveal is unavailable. Desktop reveal validates that the asset is a render and that its path stays under the render directory.
- **Timeline editing:** ruler snapping targets scene boundaries and named markers; markers save per project in local browser storage. Video edge trim handles update video source in/out and linked source audio together for a single-video, non-fixed, narration-free scene. Existing scene delete removes that block and naturally closes the sequence gap.
- **Stickers/emoji:** Overlays provides a searchable 48-item categorized library. Selecting a symbol creates a PNG image asset which uses the existing overlay position/scale/rotation/animation and render paths.
- **Filters:** added Teal & Amber, Pastel and Bleach Bypass as separate FFmpeg-rendered effect presets.
- Bumped frontend/backend identifiers and desktop package to `0.6.0-wip.9`; no changes were pushed to GitHub.

### Review of the user's eight requested areas

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

### Local services, costs, and install expectations

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

### Current 0.6.0-wip.10 additions

- Moved the T1 captions/titles lane above V1 in the timeline, including the sticky track headers and timeline content height.
- Added transcript search, previous/next caption navigation, active-segment highlighting, and collapse/expand controls for long transcripts.
- Added per-scene caption direction (Auto, RTL, LTR) to generated caption clips and the manual caption editor. The direction is applied in timeline/editor UI and embedded in ASS text to guide libass for mixed Arabic/Latin captions.
- Added frontend regression coverage for lane order, navigation, search, collapse/expand, direction persistence, and manual-caption direction; added a render smoke check for RTL/LTR direction marks.
- Bumped app/backend build IDs and desktop package version to `0.6.0-wip.10`.

### Verification status for wip.10

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

### Suggested next work, in order

1. Launch the browser build and manually verify the Share dialog, platform actions, marker/snapping behavior, trim handles, sticker preview/render, new filters, AI Engines/Help access, clip-audio controls, and transition preview/render.
2. Test captions with Faster-Whisper locally and a configured cloud provider if desired; record model/service, language detection, exact UI/errors and caption timing.
3. Test Windows playback and a clean-machine installer before calling this a release. Do not publish this source snapshot as 0.6.0 yet.
4. Continue the timeline with independent clip movement, audio unlinking, track lock/mute/solo, generalized trim and explicit ripple-delete behavior.

### Files of interest

- `desktop/RELEASE_NOTES.md` — cumulative release notes; current header identifies `0.6.0-wip.10` as unreleased.
- `docs/REVIEW_0.6.0_WIP.md` — source comparison and regression review; distinguishes historical wip.9 checks from current checks.
- `README.md` — feature and services/install overview.
- `SceneForge_Technical_Handoff.md` — architecture and technical background; note it predates some WIP changes.
- `frontend/src/SpeedControls.tsx` — Clip Audio controls.
- `backend/app/api/scenes.py`, `backend/app/render/media.py` — fade validation/persistence and FFmpeg application.
- `frontend/src/studio.css` — inspector responsive layout.
- `frontend/tests/editor.mjs`, `tests/integration/test_v06.py` — regression checks.
- `work/053` — preserved released 0.5.3 baseline; `work/060` — submitted local 0.6.0 source; `work/review` — current reviewed working source.

### 0.7.0 release-candidate continuation (2026-09-30)

The public release remains 0.5.3. The 0.7.0 RC4 source is on `chatgpt/0.7.0-video-generation` at `c9a8ee74831ab8ebc0a48aa0875e8139c98f568b` (tree `c813c8cdfe63446734c19e4031437ce531aedcea`). Its package version is 0.7.0 and API build ID is `v0.7.0-rc4`. The CI build-and-render failure must be resolved and the Windows installer must be tested by the user before merge or publication.

The candidate includes the preferences/theme/close-flow improvements, local hardware guidance, text-to-video and image candidate selection, paid provider estimates and confirmation, timeline/audio/caption fixes, curated transitions, effects/filters and sticker/layout work recorded above. These are RC features, not claims about the 0.5.3 public release.

#### Current verification and artifacts

- Release workflow [36763871298](https://github.com/EzioDEVio/SceneForge/actions/runs/36763871298): **success** for Windows, Linux and macOS. Windows packaged render and installed startup/uninstall smoke passed. Open the run and download the `SceneForge-Studio-Windows` artifact (ID `11120491437`); it contains `SceneForge-Studio-0.7.0-Windows-x64-Setup.exe`. This is a temporary Actions artifact, not a GitHub Release.
- Build and render checks [36763871406](https://github.com/EzioDEVio/SceneForge/actions/runs/36763871406): **failure** in `tests/integration/test_editor_plus.py`, which expected project deletion during an active render to return HTTP 409 but received another status. Linux keyring credential tests and 40 combined checks earlier in that job passed. Tests sequenced after the assertion did not run.
- Frontend: build passed; 226 component checks, 19 unit checks, two video-generation flows and six share checks passed. Desktop suite: 18 passed. Local video-generation integration and real-FFmpeg source-split/audio-finishing tests passed. Local Whisper mock and normalization smoke checks passed; actual user-sample inference is unverified.
- Do not merge to `main`, tag or publish 0.7.0 yet. Resolve and rerun the failed CI check, then test the installer and local/cloud workflows that matter to the user.

#### What is not bundled or implemented

- ComfyUI, custom workflow nodes/files and model weights remain separate installs. Provider keys are user-supplied and stored with the OS credential store. No direct account upload to social platforms is implemented; sharing gives the user export/location and platform instructions.
- Vast.ai is still a separate feasibility proposal, not an app integration. Auto cutout, subject/object tracking, optical-flow interpolation, advanced voice isolation, AI music re-editing and a full Fusion-style node graph remain roadmap work.
- The timeline is still scene-based for video. Independent A3 audio clips are editable, while unrestricted multitrack video compositing and universal frame-accurate clip editing remain future work.

### Source archive contents

The accompanying full-source ZIP contains the complete tracked SceneForge project tree (frontend, backend, Electron desktop app, assets, setup/build scripts, workflows, tests and documentation) plus a Git bundle with repository history. It excludes installed dependency folders, build caches/output, local databases and `backend/data` user project files. It is a source package, not a platform installer; the Windows installer is downloaded separately from the successful Release Actions run above. Optional AI model weights, ComfyUI, custom nodes and user API keys are not bundled.


---

## Appendix B — Complete cumulative release notes

## SceneForge Studio 0.7.0 RC5 (unreleased)

RC5 builds on RC4 commit `3d6107a` and is committed locally on `claude/0.7.0-rc5-timeline`. It has not been pushed, tagged or published. The public release remains 0.5.3. No live ComfyUI, Google Veo, Runway or other paid provider call was made for RC5.

### CI fix: deleting a project during an active render
- **Cause.** RC4 changed project deletion so that only jobs live in the current process block it; stale job rows are recovered instead. `test_editor_plus.py` still created a bare `running` row with no live worker and expected 409. The server correctly treated that row as stale and returned 200.
- **Invariant, unchanged.** A job that is truly active blocks deletion with 409. An abandoned job row never blocks deletion forever.
- **Race closed.** Render, export and video-generation endpoints now reserve the job ID as live *before* committing the queued row (`reserve_job_id` / `release_job_id`). Previously, a delete that landed between the commit and the worker start could treat a brand-new job as stale.
- **Tests.** The test now registers a genuinely live job. It adds checks for a reserved-but-not-started job (409), release of the live registry, and a stale queued row (deletable). The existing stale-job suite still passes.

### Timeline v1
- **Audio tracks A3–A8.** Timeline audio clips can live on six independent tracks.
  - Add a track from the track header, and remove an empty one.
  - Move a clip between tracks by dragging it up or down, or with the Audio inspector's Track menu.
  - Dropping audio on a track places it there.
  - A1 narration, A2 clip sound and the whole-project music bed keep their meaning.
- **Track mute, solo and lock** for every audio track, saved with the project and honoured in export.
  - Solo applies among A3–A8 only; narration, clip sound and music are not affected, and the tooltip says so.
  - Tracks that won't be heard are dimmed and labelled.
- **Edit tools** for timeline audio clips:
  - Select (V) and Track select forward (A)
  - Ripple trim (B), Roll (N), Slip (Y) and Slide (U)
  - Blade (C). Shift+click, Shift+C or Shift+scissors runs Razor All across unlocked audio tracks.
  - Delete removes the focused clip; Shift+Delete ripple-deletes it.
  - Every tool uses the same pure edit function for the drag preview and the saved result, and all edits are undoable.
- **Markers** are saved with the project (they were previously kept only in this browser profile).
  - New **range markers** span the selected audio clip(s) or scene.
  - A marker's colour can be changed.
  - Marker edits can be undone.
  - Existing browser-stored markers and locks migrate into the project automatically.
- **Versioned timeline format.** `finishing_json.timeline` is at version 1, and A3 stays implicit on clips so older data keeps its meaning. The backend rejects unknown tracks, invalid track states and newer versions. See `docs/TIMELINE_ARCHITECTURE.md`.
- **Performance.** Off-screen audio clips are not rendered, drag previews are coalesced to one update per animation frame, and Ctrl+wheel zooms around the pointer.
- **Unchanged.** V1 remains scene-based. Gain envelopes, clip-attached markers, compound clips and free multitrack video are roadmap items, not part of RC5.
- **Build ID** is now `v0.7.0-rc5`.

## SceneForge Studio 0.7.0 RC4 (unreleased)

This is an installer-test candidate on `chatgpt/0.7.0-video-generation`, not a published GitHub release. Keep it on this branch until the Windows installer has been tested; the public release remains unchanged. A prior local build was reported to generate successfully with Runway, but this regression pass does not repeat live provider calls.

### Test feedback follow-up
- **Cut source clips at the playhead:** one-shot source video/image scenes can split without first rendering, including editable generated caption segments and timed text. The source video and embedded audio stay linked; segment thumbnails start at each segment's actual source time. Multi-shot scenes, separate narration, motion and speed effects still require a render before a baked cut.
- **Caption regeneration:** Auto Captions now offers “Regenerate captions” after a transcript exists and lets users choose video sound versus scene narration when both are present. The Text Layers editor sits immediately below Auto Captions.
- **Project audio lane A3:** MP3, WAV, M4A, AAC, OGG and FLAC files can be dropped from disk or the Media Pool onto A3. Each project clip can be moved, trimmed, split at the playhead, muted, leveled, faded and stacked with other clips. The clips are mixed at their timeline positions on export while preserving the existing whole-project Music bed.
- Clicking inside an A3 clip places the playhead there for a scissors split. The Audio tab distinguishes the whole-project music bed from independent A3 clips and explains the move/trim/mute/volume/fade/split workflow.
- **Media layout presets:** side-by-side, stacked and 2×2 controls now arrange video/image PiP layers from the Media Pool or Upload. Stickers and emoji are kept independent so layouts do not move them. The controls have visible diagrams and clear enabled/disabled states.
- **Local Whisper recovery:** if voice activity detection returns no words, local transcription retries without VAD. When the model recognizes text but omits word alignment, SceneForge creates editable captions with estimated intervals and labels the timing as estimated.
- **A more focused transition picker:** 28 visually distinct transition families replace repeated directional variants in the default list. Existing projects keep rendering their saved transition IDs, and the Inspector labels legacy choices.
- **More reliable local captions:** the local Whisper path normalizes audio to mono 16 kHz with dynamic leveling when supported, retries without voice activity detection, and keeps recognized phrases when word-level alignment is missing.
- **Audio editing and cleanup:** clicking an A3 audio block sets the playhead before a drag begins, so the scissors split at the pointed time. Abandoned render records no longer block project deletion while the editor stays open; actual live jobs still do.
- **Cut feedback and project cleanup:** split warnings auto-dismiss after 3.5 seconds. At startup, stale queued/running/cancelling jobs left by a previous process are marked interrupted, so they no longer block project deletion; live jobs still protect their project.
- Updated the matching frontend/backend API build ID to `v0.7.0-rc4`; this remains an unreleased 0.7.0 candidate.

### Preferences, project setup and close flow
- Preferences now lives under **File**. The editor’s upper-right **Theme** menu offers Graphite Night, Daylight, Midnight Blue and Warm Studio, with accent, density and reduced-motion controls in Preferences.
- New-project format and frame rate remain in **Create Project**; Preferences no longer repeats those controls. Existing projects keep their own aspect ratio, adjustable from the editor.
- Added a native close dialog with **Save**, **Don’t save**, **Save and exit**, and **Cancel**. Save flushes changes and keeps the app open; failed saves or active generation/render/export keep SceneForge open.
- Added local hardware guidance for NVIDIA GPU name, maximum detected VRAM, GPU count and system RAM. Local model choices display requirement warnings when detected hardware is below the model guidance. Detection advises the user; it does not install ComfyUI or download model weights.
- Set the application build identifier and desktop package to `0.7.0`.

### Startup, theme and timeline follow-up
- Cleaned the project home: removed the static mode tabs, duplicate provider selector and repeated project-default controls. Existing AI Engines, Help, Media Pool, Scenes and editor tabs remain available.
- Added an explicit **Projects** button in the editor to return to project creation/opening without using Reload.
- Restored the **Safe zones** toggle above the timeline. Corrected Daylight theme colors across inspector controls, cards, buttons and timeline panels for readable contrast.
- Fixed the close readiness check to use live in-process work. A stale queued/running job record left after a prior crash no longer traps an otherwise idle user in the close dialog.
- Added per-project T1/V1/A1/A2 lane locks, an A2 quick mute button for each video clip’s embedded sound, and an explicitly labeled **Ripple delete** action that closes the scene gap. Existing snapping, markers, scene reorder, linked edge trim, split, and undo/redo remain.
- Added 55 renderable transition IDs, with the default transition picker now curated to 28 distinct families; caption styling includes **31** presets and the searchable emoji/graphic sticker library includes **66** items. Added **8** separately grouped color filters plus the FFmpeg-rendered creative effects **Chromatic split** and **Motion trail**.

### Text-to-video workspace
- Added a dedicated **Generate video** workspace that leaves the existing editor, top-level AI Engines and Help menus, timeline and media panels in place.
- Added local ComfyUI choices: LTX-2.5 Fast, Wan 2.1 T2V 1.3B, Wan 2.2 TI2V 5B, Wan 2.2 T2V A14B, and a compatible custom-workflow option.
- Added paid Google Veo 3.1 Lite/Fast/Standard and Runway Gen-4.5/WAN 3.0 API choices. Provider API keys remain in the operating system's credential store.
- Added per-resolution per-second provider list rates, checked 2026-09-28, and a total estimate based on chosen duration/quality. Cloud generation requires explicit cost confirmation in both the interface and API.
- Added provider-specific limits for duration, resolution and aspect ratio. Local ComfyUI workflows can use custom dimensions from 256 to 4096 pixels, in multiples of 16.
- Added local ComfyUI status, API-workflow JSON import, safe loopback-only connection validation, job progress/cancellation, and generated-video decoding checks.
- Restyled the generator as a high-contrast graphite workspace; engine/model choices, quality, ratio, duration and seed controls now have stronger visual hierarchy. External setup links open through the desktop shell instead of Electron's blocked new-window path.
- Added guided local ComfyUI setup steps, clickable install/model references and an optional NVIDIA GPU/VRAM check that recommends a lighter model. Added step-by-step Google and Runway API-key setup links.
- Added a 1–3 video-candidate setting. Each take is generated as a separate request, cloud estimates and consent cover the full count, completed options stay in the Media Pool, and a user can preview/select one before timeline insertion. A specified seed advances for each take.
- Added the same 1–3 compare-and-select workflow to AI Image Studio; hosted providers show a per-image billing acknowledgment, while local Stable Diffusion advances a fixed seed for each option.
- Generated results are stored as project Media Pool assets, can be inserted into the selected scene or as a new timeline scene, and can be passed to existing local auto captions. Successful caption handoff closes the generator and opens Text for segment edits/styles.
- Model weights, ComfyUI, workflow nodes and workflow files are not included in the base installer. Local custom nodes execute within ComfyUI using the user's permissions; only import trusted workflows.
- Full API references and install details are in [README.md](README.md); current scope and checks are in [the 0.7.0 review](docs/REVIEW_0.7.0_VIDEO_GENERATION.md).

### Verification
- `npm run build` — passed (TypeScript and Vite). Vite reports a 555.65 kB minified editor bundle, above its 500 kB advisory threshold.
- `npm test` — passed: 226 editor component checks, 19 unit checks, 2 video-generation UI flows and 6 Share dialog checks. Provider requests are mocked; these checks do not replace visual QA.
- `npm test` in `desktop/` — passed: 18 tests, including the four close choices, save failure, active work and repeated-close handling.
- `PYTHONPATH=backend /tmp/sceneforge-release-venv/bin/python tests/integration/test_video_generation.py` — passed, covering the model catalog, hardware guidance, provider request adapters, ComfyUI queue/output, workflow mapping, paid confirmation, candidate count and loopback-only connection.
- Direct backend integration checks for stale/live close readiness and color/creative effects passed; Chromatic split and Motion trail render through the complete scene filter graph.
- The new source-split integration test passed against real FFmpeg media, checking source ranges, linked sound, caption/text timing, source-time thumbnails and export. The finishing/export integration test passed all 22 checks, including A3 clip placement, fade validation, audio output and silence between clips.
- Python compile checks and `git diff --check` — passed.
- Release workflow run [36763871298](https://github.com/EzioDEVio/SceneForge/actions/runs/36763871298) completed successfully on 2026-09-30 for Windows, Linux and macOS. The Windows job built the installer and passed packaged render, installed-app startup and uninstall smoke checks. Its Windows installer is a temporary Actions artifact (`SceneForge-Studio-Windows`, artifact ID `11120491437`), not a published GitHub Release.
- Build and render checks run [36763871406](https://github.com/EzioDEVio/SceneForge/actions/runs/36763871406) failed after the Linux credential checks and 40 combined checks passed. `tests/integration/test_editor_plus.py` failed its “Cannot delete project during an active render” assertion because the delete request did not return the expected 409 response. Treat this as an unresolved CI regression; the later integration scripts in that shell sequence did not run.
- No live ComfyUI, Google Veo or Runway generation was repeated in this regression pass. Check installed models, hardware, account billing, returned audio, captions and export codecs separately. The setup guide does not install ComfyUI, download model weights or install custom nodes.
- The successful platform package workflow is not a public release and does not replace user testing. The user still needs to test the fresh Windows installer and the specific local Whisper sample; resolve and rerun the failed build-and-render CI gate before merge or publication. Action artifacts are temporary branch-test builds.
- Vast.ai remains a separate optional remote-GPU prototype idea. Before app integration, benchmark end-to-end generation and data transfer costs, make upload scope explicit, and guarantee that instances are destroyed after jobs.

## SceneForge Studio 0.6.0-wip.10 (unreleased)

This is a reviewed source snapshot, not a published GitHub release. See [the source comparison and review](docs/REVIEW_0.6.0_WIP.md).

### Compatibility and timeline fixes
- Restored undo/redo coverage for scene add/delete, media insertion, title cards, narration attach/remove, scene reorder, clip sound, and scene splits (up to 100 recent timeline operations).
- Scene splits preserve per-shot source audio settings and speed settings; undo restores original scene and clip IDs.
- Added a dedicated source-video-audio lane with separate blocks for each video clip. Selecting a block opens that clip’s **Clip Audio** inspector (separate from Motion), including volume, mute, narration ducking, and fades.
- Restored the original AI Engines top-level menu and Help menu while retaining Scenes, Media Pool, Transitions, and toolbar provider settings. Removed the redundant AI Engines entry from the Scenes library tabs.
- Whole-scene timeline blocks can be dragged to reorder; source sound follows video splits.

### New and improved
- **Additional caption looks:** Creator punch, Soft subtitle, Glass panel, Pastel pop, Cyber cyan and Clean white.
- Transition tiles now show more distinct cover, slide, zoom, wipe, blur and radial motion cues while previewing.
- Dropping media into empty timeline space inserts it at that point in the sequence; the left/right scene-edge insertion behavior remains available.
- **18 additional transitions** with live previews on your clips (42 choices total).
- **Select several parts** and apply chosen effects, caption styles, titles, or transitions together while preserving each part's caption text and position-specific effects.
- **Free local captions:** Faster-Whisper is the default and needs no API key. Its multilingual model downloads once on first use; subsequent transcription runs on-device. ElevenLabs and OpenAI remain optional cloud choices.
- **Fourteen additional caption styles** (24 total).
- **Export presets and controls:** platform presets, estimated size, resolution up to 4K, frame rate, quality, H.264/H.265 MP4, WebM, ProRes MOV, GIF, MP3 and WAV; export SRT/VTT caption files.
- **Progress cards** show the current stage, percentage, elapsed time and estimate, with cancellation for renders and exports.
- The multi-select toolbar can be minimized and closes automatically after a successful action.
- Advanced export controls open by default in a redesigned dark editing-style panel; the narration script box has updated styling.
- The timeline shows video source sound on its own A2 lane; clicking a block opens the existing clip sound controls. Drop media near a scene's left/right edge to insert a new part before/after it.

### Fixed
- Exports use broadly supported H.264 4:2:0 and fast-start MP4 settings, including projects with transitions, to improve playback in Windows Photos and Media Player.
- The fast timeline export uses draft quality; the Export dialog retains its selected delivery quality.
- A 9:16 project preserves the full duration and sound of source video clips. Clip sound can be muted or adjusted individually.

### Additional updates in wip.8 (previous WIP)
- Added **Text**, **Text Box**, and **Text+** creation tools. Text is a short title; Text Box adds a width-controlled, wrapping block; Text+ uses SceneForge's styled/animated title controls. These are not a full DaVinci Resolve Fusion replacement.
- Text titles and on-screen captions appear as labeled, timed clips on the T1 timeline. Selecting a clip switches to Text and focuses the matching editable caption/title field.
- Added click-to-open “What it does / How to use it” help popovers across Media, Motion, Effects, Overlays, Text, Audio and Clip Audio, plus feature sections such as stickers, effects, framing and narration.
- Timeline marker help now explains that markers are named bookmarks for returning to a point in the project.
- Frontend/backend build IDs and desktop package version were `0.6.0-wip.8`.
- The post-export Share dialog from wip.7 remains included.

### Additional updates in wip.9 (previous WIP)
- Auto captions now create individually timed caption clips on T1, grouped by a user-selected 1–8 words per clip. Click a clip to open and focus its text editor; change wording and start/end times, split a phrase into two clips, or remove a clip. Caption styles still apply across the caption set.
- Fixed clipped feature-help popovers by placing them in a viewport-level layer, repositioning them near the trigger, constraining long content to a scrollable viewport, and supporting Escape to close.
- Bumped frontend/backend build IDs and desktop package to `0.6.0-wip.9`; the post-export Share dialog remains included.

### Additional updates in wip.10
- Moved the T1 text/caption lane above the V1 picture lane so timed captions sit directly above their video on the timeline.
- Added caption search, previous/next navigation, active-segment highlighting, and collapse/expand for long transcripts.
- Added Auto, Right to left, and Left to right caption direction. The setting follows edited captions into ASS rendering, including mixed Arabic/Latin phrases.
- Updated the frontend/backend build identifiers and desktop package version to `0.6.0-wip.10`.

### Installation notes
- The Windows desktop installer bundles the editor, its private backend runtime and FFmpeg. It does not bundle the Whisper model, optional Chatterbox/Kokoro narration servers, or Stable Diffusion image models. Whisper downloads its model once on first use; the others require separate setup if needed.

## SceneForge Studio 0.5.3

### Fixed (important)
- **Video clips now keep their own sound.** Videos with sound used to export silent; only narration and music were heard.
- **Scenes last as long as their videos.** A scene without narration used to fall back to 4 seconds, and a scene longer than its video looped the video to fill the gap. Now a scene lasts exactly as long as its videos (after trimming and speed changes), and several videos in one scene each keep their own length.
- **No unexpected countdown.** The whole-video "Countdown leader" switch is removed; the countdown is now an effect you add to a scene (below).
- **File → New project / Open project** (Ctrl+N / Ctrl+O), in the desktop menu and the editor menu. They wait for saves instead of being greyed out.
- Changing only a clip's speed or sound now always re-renders the scene (it could reuse an old render).

### New
- **Clip sound** (Motion tab, for videos): volume, mute, and "Lower it under narration" so a voice-over stays clear.
- **Captions from speech** (Text tab): automatic captions from the narration or from the sound of your videos, in any language (detected automatically), with exact word timing for phrase captions and word highlight. Uses your ElevenLabs (Scribe v2) or OpenAI (Whisper) key; the text stays editable.
- **Countdown intro** (Effects tab): a cinema countdown before a scene: Film leader (grain, scratches, projector sound; black & white or sepia), Modern (glowing ring) or Minimal; 3–10 s; beeps on every number, the classic 2-pop, or silent. Off unless you switch it on.

### 9:16 (TikTok, Reels, Shorts)
- **Landscape clips and photos keep the whole picture over a blurred background** by default in vertical projects, instead of being cropped. Choose in Motion → Fill the frame: Fill (crop), Fit + blurred background, or Fit + bars.
- **Captions sit above the platform's buttons and caption** (about 20 % up) by default.
- **Safe zones** toggle on the preview shows the areas TikTok, Reels and Shorts cover.
- Split screen defaults to top & bottom in vertical projects.

## SceneForge Studio 0.5.2

- **No more flicker** when changing effects: background saves no longer grey out the timeline or the scene settings.
- **Duplicate and copy/paste on the timeline:** right-click a picture clip → Duplicate scene, Copy scene, Paste after (or Ctrl+D / Ctrl+C / Ctrl+V). The copy keeps every picture, effect, caption, title, overlay and audio take, so you can give it different effects. Right-click a narration clip → Copy audio, then Paste audio here on another scene.
- **Preview zoom:** zoom buttons next to the cut tool and in the preview header (up to 400 %), Ctrl + mouse wheel zooms at the cursor, and middle-drag or Space + drag pans.

## SceneForge Studio 0.5.1

- **Move and resize annotations directly on the picture.** In the Effects tab, every annotation shows handles on the preview: drag a point to change where it starts or ends (or its corners, for circles and boxes), and drag the ✥ handle to move the whole shape. The sliders update as you drag.
- **Accurate arrow preview.** Curved arrows now preview as curves with their arrowhead, matching the render (they used to preview as a straight line).

## SceneForge Studio 0.5.0 — Captions Pro

Captions now have CapCut-level styling. Everything is in **Text → Caption styles**, with a live preview on the picture.

### Caption styles (one click)
Classic, YouTube box, **Viral bold**, Karaoke, Neon, Cinematic, Documentary, Underline, **Arabic modern**, Pulse.

### Font
- **Seven new bundled fonts:** Poppins, Bebas Neue, Anton, Pacifico, and Arabic **Amiri**, **Tajawal**, **Lalezar**, each paired with a matching font for the other script.
- **Bold, italic, underline**; letter case (as typed, UPPERCASE, Title Case, lowercase); letter spacing; size up to 120.
- Added fonts are size-matched so the same size setting looks the same size.

### Colours, outline, shadow, box
- Text colour; outline colour and width; shadow with colour and opacity.
- **Background box** with colour, opacity and padding.

### Position
- Top / middle / bottom, left / centre / right, move up or down, maximum width.

### Phrase captions (CapCut style)
- Show a few words at a time (1–8 per phrase), each phrase appearing as its words are spoken (exact timing with ElevenLabs, measured from the audio for other voices).

### Word highlight
- New styles: **Box** (a marker behind the spoken word), **Colour** (only the current word) and **Underline**, besides Colour fill, Pop and Glow. Works inside phrases.

### Animation
- Entrance (all the ✦ animations), **exit** (fade out, pop out) and a looping **pulse**. In phrase mode each phrase gets its own entrance, exit and pulse.

### Also
- The old flat caption controls are replaced by the organised Caption styles panel. Existing projects keep their settings.

## SceneForge Studio 0.4.1

- **Caption animations** (Text tab → *Caption animation ✦*): the captions themselves can now use the new animations: letters pop/fade/flip/blur-in, words pop/fade/flip, shine, bounce, zoom, blur, neon, wobble and glitch, with an adjustable length. Arabic captions animate word by word. (Typewriter and Word-by-word highlight still animate captions their own way; turn them off to use a caption animation.)
- **✦ Add animated title** button at the top of the Text tab: adds a letter-pop title in one click (edit it under Text overlays).

## SceneForge Studio 0.4.0 — Motion & Text

### New: text animations (Text tab → Text overlays, and the Title Designer)
- **Letter by letter:** Letters pop, Letters fade, Letters flip, Letters blur in, and **Shine** (a highlight sweeps across the text).
- **Word by word:** Words pop, Words fade, Words flip. Arabic text animates word by word automatically, so letters stay joined.
- **Whole line:** Bounce, Neon flicker (with a coloured glow) and Wobble.
- **Letter spacing** and a highlight/glow colour for Shine and Neon.
- **One-click text styles:** Documentary, Bold pop, Neon, Cinematic, Headline, Golden shine, Arabic title.
- The Title Designer's *Play rendered preview* shows the real animation before you add the card.

### New: animated annotations (Effects → Annotations)
- **Arrow** (curved or straight), **Circle** (hand-drawn or neat), **Underline** (line or highlighter), **Box**, and **Callout** (a label with a pointer, Arabic supported). They draw themselves on screen with their own start, draw and end times, and fade out at the end. Up to 10 per scene, previewed on the picture.

### New looks
- **Glow** (soft bloom), **Duotone** (deep blue to warm gold), **Newspaper** (high-contrast print on paper).

### Also in this release (from 0.3.5)

### Fixes
- **Arabic map-route stop labels now render correctly**: joined letters, right-to-left, in the Noto Naskh Arabic font, including mixed text such as "قرطبة 711". (The labels used a font without Arabic letters, and Windows lacks the shaping engine the image library relies on; shaping is now done by bundled libraries that work the same on every system.)
- **Typing a stop label is no longer interrupted.** Background saves used to disable the editor for a moment, which greyed out the timeline, took the cursor out of the field and dropped keystrokes. Stop labels now keep their text while you type and save after a short pause or when you leave the field.

### Tests
- The release end-to-end test now renders an Arabic-labelled map route in the installed app on every system.

## SceneForge Studio 0.3.4

### New
- **Map routes: arrowhead, moving icon, stop labels, curved paths.** The line can end in an arrowhead that stays visible at the destination; a plane, ship, car, dot or pin can ride along the route and turn with it; each stop can have a label (a city or a date) that appears when the line reaches it; and the route can follow a smooth curve through the stops.
- **Right-click menu** everywhere: undo/redo, cut, copy, paste, paste as plain text, select all, spelling suggestions, and copy image.
- **Paste media from anywhere**: copy an image, video or audio file (from a browser, Explorer or a screenshot) and paste it into the scene with Ctrl+V or right-click → Paste. Text boxes keep normal paste.
- A hint above the looks grid: hover a look to preview it, click to apply.

### Fixes
- **After an update the app could keep showing the previous version's editor**, so some new features (such as the look preview) did not appear. The editor page is now always re-checked, and the saved copy is cleared once whenever the app version changes.

## SceneForge Studio 0.3.3

- **AI engines & providers panel** (AI Engines menu, Ctrl+Shift+A): a getting-started guide, which cloud providers are connected (with where to get a key), step-by-step Stable Diffusion setup with Choose folder / Start now / Start automatically, and local voice help. Replaces the plain message boxes.
- **About panel** (Help → About): version, update check with a clear result, beta updates switch, license, GitHub, Report a problem, Collect diagnostics, Open logs.
- **Clearer update messages**: "no published release yet", "can't reach GitHub", or the actual error, instead of always "check your internet". Turning beta updates on or off now confirms it and checks for a beta straight away.
- **Preview looks before applying**: hover over a look to see it on the picture ("Previewing … · click to apply"), including split-screen scenes.
- **Animated transition previews**: every transition in the Transitions list plays its real motion on hover.
- **Branded Windows installer**: SceneForge icon on the installer and uninstaller, sidebar artwork on the welcome and finish pages, a header on every step including the progress page, and "Run SceneForge Studio" at the end.

## SceneForge Studio 0.3.2

- **Fixed (Windows): the app froze when choosing an effect or look, and then stopped responding.** The release test reproduced it on a clean Windows machine: the first action that loads the maths library (NumPy) hung the whole backend. NumPy and OpenCV are now loaded once at start-up on the main thread, with their maths engine limited to one thread.
- The backend now writes a diagnostic report to its log if any action takes longer than 20 seconds, showing exactly where it is stuck.

## SceneForge Studio 0.3.1

- **Stable Diffusion no longer starts automatically** after this update (a one-time change). Starting it with SceneForge could slow the whole computer while it loads. Start it from **AI Engines → Stable Diffusion → Start Stable Diffusion now**, or tick **Start automatically with SceneForge** in the same menu.
- **Guided AI Engines menu**: *Getting started with AI*, *Add or change API keys*, step-by-step help for Stable Diffusion and local voices.
- **Help → Collect diagnostics for a bug report**: puts logs and system details (no API keys, no media) in a folder on your Desktop.
- **View → Developer tools** (Ctrl+Shift+I) for bug reports.
- Release builds now run an **end-to-end test of real editor work** in the packaged app on Windows, Linux and macOS (import, thumbnails, effects, colour preview, narration waveform, provider settings, and a full scene render), with time limits.

## SceneForge Studio 0.3.0 — first public open-source release

- **Open source** under the GNU GPL v3.0 or later.
- **Installers for Windows, Linux (AppImage, .deb) and macOS (Apple Silicon, experimental)**, built by GitHub Actions and published on GitHub Releases.
- **Automatic updates** (Help → Check for updates; Help → Receive beta updates). Windows and Linux AppImage update in the background; macOS announces new versions.
- **Project backups** before every update (Help → Open project backups; the last 5 are kept).
- Renamed from "SceneForge Desktop Alpha" to **SceneForge Studio**; projects from the Desktop Alpha are copied over automatically on first start (the old folder is left untouched).
- New README, third-party notices and contributing guide; new app icon.
- Includes everything since RC4: effects packs A–C, overlays, map routes, split screen, 3D photos, photo restore, word-by-word captions, music and finishing, audio editing, LUTs, old film and more (see the entries below).

## SceneForge Desktop 0.2.0 RC5 (in progress) — photo restore rewritten

- **Restore old photo** no longer damages detailed photos. The previous version treated fine detail (debris, clothing, branches) as dust and smeared it; on a real WWII photo it "repaired" 23 % of the picture. Now:
  - dust is only removed where it is a tiny isolated speck on a smooth area (sky, smoke, walls), never inside texture, and never more than 0.5 % of the photo;
  - grain reduction is scaled to the photo's measured noise;
  - black-and-white photos are processed and saved as black and white;
  - contrast and sharpening are gentler (no halos).
  On the same WWII photo, 94–105 % of the detail is kept.

## SceneForge Desktop 0.2.0 RC5 (in progress) — split screen and photo restore fixes

- **Split screen**: the editor preview now shows the layout. When a scene has only one picture, an **Add another image or video to this scene** button appears under Split screen, and the hint says how many pictures the scene has.
- **Restore old photo**: shows progress and a confirmation naming the restored copy; the Media Pool refreshes right away. If the photo tools are missing (setup.bat not re-run after updating), a clear message says what to do instead of a generic error.

## SceneForge Desktop 0.2.0 RC5 (in progress) — Batch B and C

### Pictures
- **3D photo (parallax)**: mark the subject of a still photo; the background behind it is filled in automatically and the two layers move at different depths (push in, pull out, drift left or right).
- **Restore old photo** (Media tab): a cleaned-up copy with less noise, dust and scratches removed, recovered contrast, sharper detail, and small scans upscaled. The original is kept.
- **Colour wheels**: lift, gamma and gain, shown in the preview.
- **Split screen**: side by side, top & bottom, three panels, or a 2 × 2 grid, with gap and background colour.

### Motion and timing
- **Clip speed** for video clips (Motion tab): 0.25×–4×, a slow-motion or fast moment in the middle, and freeze frames. Scene length does not change.
- **Map route**: a line draws itself across the picture with pins popping in at each stop. Click the preview to add stops and drag them to adjust; solid or dashed, colour, width, start and draw time.
- **Sync scene cuts to the beat** (Audio → Music & finishing): finds the tempo of the background music and moves fixed-length scene cuts onto beats. Narrated scenes keep their length.

### Captions
- **Exact word timing with ElevenLabs**: new ElevenLabs voices include per-word timings, and word-by-word captions follow them exactly when the caption matches the narration. Other voices keep the speech/pause detection.

### Fixes
- The VHS look's rolling tracking band never appeared (FFmpeg evaluates drawbox positions only once); it is now drawn with a per-frame overlay.

### Notes
- New dependency: OpenCV (headless), about 70 MB, for 3D photo and photo restore. Run `scripts\setup.bat` again after updating.
- Colorizing black & white photos and automatic subject detection need AI models and are not included yet.
- Build ID `rc5-batchbc-7`. New tests: `test_batch_b.py` (27 real-render checks); 7 component checks (115 total).

## SceneForge Desktop 0.2.0 RC5 (in progress) — Effects pack

### New looks and scene effects (Effects tab)
- **VHS** look: colour bleed, scanlines, a rolling tracking band and tape noise.
- **Split toning**: tint shadows and highlights with two colours; shown in the preview.
- **Camera shake** with optional **impact zoom** at the start.
- **Spotlight**: darken everything except an oval or box, with soft edges and timing.
- **Blur or pixelate areas** (up to 6) to hide faces, names or number plates.
- **Light leaks**: warm, cool or rainbow light drifting in from the edges.
- Spotlight, blur areas and light leaks are previewed live in the editor.

### Transitions
- Wind, Slice, Open, Close and Quick fade (25 in total).

### Overlays
- **Glide** from one position to another during the overlay's time, **green screen** (make a colour transparent), and **soft edges**.

### Narration and captions
- **Voice effect** per take (Audio tab): Clean up, 1940s radio / newsreel, Telephone.
- **Caption style** for word-by-word: Colour fill, Pop (the current word grows), Glow (the current word glows).

### Tests
- `tests/integration/test_effects_pack.py` (28 real-render checks, in CI); 8 new component checks (108 total). Build ID `rc5-effects-6`.

## SceneForge Desktop 0.2.0 RC5 (in progress) — caption timing, roomier editor

### Word-by-word captions follow the real voice
- Fixed: in scenes with a fixed length longer than the narration, the highlight was spread over the whole scene and finished late.
- Word timing is now measured from the narration audio: SceneForge finds where the voice speaks and where it pauses and places the words on the spoken parts. The highlight waits during pauses and ends when the voice ends. Works with every voice engine (ElevenLabs, Chatterbox, Kokoro, uploads) and language, including Arabic. Trimmed takes are respected.

### Editor layout
- **Scene settings is resizable**: drag its left edge (280–760 px), double-click to reset, arrow keys for fine steps. The width is remembered.
- When the panel is wide, groups sit side by side (two or three columns).
- Controls are grouped into cards; number boxes are wider; choice buttons (animations, tone, frame rate) wrap as pills instead of squashing.
- **Narration script** card is taller, has **Expand**, and shows the word count, the estimated speaking time, and the voice status (length, or "Script changed · generate a new voice"), with a clear **Generate voice** button.

## SceneForge Desktop 0.2.0 RC5 (in progress) — Picture in picture

### Overlays (new Overlays tab)
- Place images or videos inside a scene: maps, portraits, documents, a second camera angle.
- **Drag on the preview to move; drag the corner handle to resize.** Arrow keys nudge (Shift for bigger steps).
- Position, size, rotation, opacity, rounded corners (up to a circle), border and border colour, drop shadow.
- Show from / until within the scene; entrance and exit animations: Fade, Slide, Rise, Zoom pop; animation length.
- Up to 8 per scene, with bring forward, send back, duplicate and delete.
- Videos play silently and loop. Overlays sit above the picture and its effects, below captions and titles.
- The editor preview matches the render; each card's shadow, border and corner mask are drawn once and cached under `proxies/overlays`.

### Upgrade notes
- Existing databases gain `scenes.overlays_json` automatically. Build ID is now `rc5-overlays-5`.

### Tests
- `tests/integration/test_overlays.py` (20 checks, in CI): validation, placement, size and aspect, border, rounded corners, rotation, timing, fade, slide, zoom pop, opacity, looping video, stacking order.
- 8 new component checks (100 total).

## SceneForge Desktop 0.2.0 RC5 (in progress) — transitions, motion, captions, music, film extras

### Transitions and motion
- 20 scene transitions: adds Circle close, Zoom in, Smooth slide left/right, Clock wipe, Pixelate, Blur, Diagonal wipe, Squeeze, Fade through grey, and **Film burn** (a hot orange flare that blooms across the cut).
- **Speed curve** for camera movement (Motion tab): Smooth (ease in and out, the default), Ease in, Ease out, or Constant speed.

### Word-by-word captions
- Text tab → **Word-by-word highlight**: each word changes to the highlight colour as it is spoken, following the narration. Timing is shared across the narration by word length.

### Music & finishing (Audio tab, whole video, applied on export)
- **Background music**: loops to the length of the video, with volume and fades, and **gets quieter automatically under narration** (sidechain ducking).
- **Level loudness for YouTube**: EBU R128 to -14 LUFS / -1.5 dBTP.
- **Film countdown leader**: 5-4-3-2 with a rotating sweep and the one-frame "2-pop" beep, added before the video (5 s).

### Old film
- **Projector sound**: clatter at the film frame rate with motor hum, mixed under Old film scenes. The three film styles set it.

### Fixes
- The motion speed-curve picker read its value after the save was queued, so a choice could be replaced by the previous one. Fixed.
- Export finishing tolerates older callers without finishing settings.

### Upgrade notes
- Existing databases gain `projects.finishing_json` automatically. Build ID is now `rc5-finishing-4`.

### Tests
- `tests/integration/test_finishing.py` (in CI): all 19 transitions render; film burn colour; easing curves; word timing and highlight on real libass frames; easing validation; film burn export length; music looping and ducking; measured loudness; leader length, picture and beep; projector clatter rate.
- 5 new component checks (92 total).

## SceneForge Desktop 0.2.0 RC5 (in progress) — Old film effect

### Old film (Effects → Old film)
- A real old-film look, like WWII newsreels and 8 mm home movies:
  - **Scratches:** vertical lines that drift, wobble, drop out and last up to a few seconds; mostly white, some dark.
  - **Dust & hair:** specks that change every frame, curly hairs caught in the gate for a few frames, the odd dark blotch.
  - **Flicker:** exposure that varies from frame to frame, with the gate vignette "breathing" along with it.
  - **Gate weave:** the picture wobbles in the projector gate, with the occasional frame slip.
  - **Frame rate:** 16 or 18 fps for the jerky hand-cranked look (24 fps, or keep the project rate). Scene length is unchanged.
  - **Tone:** Colour, Faded, Sepia, or B & W.
  - Film grain and slight lens softness scale with the amount of damage.
- One-click styles: **WWII newsreel**, **8mm home movie**, **Silent era**.
- The effect plays **live in the editor preview**; the render uses the same settings through FFmpeg.
- Each scene gets its own damage pattern, and re-rendering a scene gives identical results. The damage layer is cached under `proxies/film` in the data folder and can be deleted safely.
- Works on top of any look, LUT and adjustment. Titles and captions stay sharp above the film damage.

### Fixes
- With the **Original** look selected, the colour-slider preview had no effect: the preview combined the CSS value `none` with other filters, which made the whole filter invalid. Fixed.

### Version check
- Build ID is now `rc5-old-film-3`.

## SceneForge Desktop 0.2.0 RC5 (in progress) — LUT compatibility

### LUTs from DaVinci Resolve
- **1D LUTs** (`LUT_1D_SIZE`, e.g. gamma, log and HDR conversions) and Resolve's **1D shaper + 3D** LUTs (e.g. ACES LMT) now import and render. Previously they were rejected. All 108 `.cube` files in Resolve's LUT folder import.
- **Import a whole folder of LUTs** (Effects → Color LUT). Only `.cube` files are imported; other Resolve formats (`.ilut`, `.olut`, `.xml`, `.dat`) are listed as skipped, and broken files are named with the reason. Several files can also be chosen at once in the file picker.
- The LUT size limit is raised from 12 MB to 32 MB (Resolve's "Samsung Log to Rec709" is a legal 65-point LUT of 12.9 MB).
- If the backend does not keep a LUT choice, the panel now says so instead of silently doing nothing. Choosing a LUT is no longer blocked by an earlier failed save.

### Version check
- The backend build ID is now `rc5-looks-audio-2` and is shared with the interface (`BUILD_ID`). A new interface connected to an older backend (for example a `start.bat` window from a previous version that is still open) shows "Backend update required" instead of silently dropping new settings.

## SceneForge Desktop 0.2.0 RC5 (in progress) — audio clip editing, LUT preview

### Scene audio editor
- Click a scene's audio clip on the timeline (or open Audio) to edit it: waveform with draggable trim handles (arrow keys nudge 0.1 s), Start/End in seconds, Volume 0–200%, Fade in and Fade out, **Play clip** to audition the trimmed, levelled and faded result, and **Reset edits**.
- Edits are non-destructive: the original file is never changed. **Match narration** uses the trimmed length.
- **Remove from scene** takes the audio off without touching the picture. The scene keeps its current length, and the audio stays in the takes list and the Media Pool. With a timeline audio clip focused, Delete removes only the audio.
- Timeline audio clips show their waveform and file name.

### LUT fixes
- The editor preview now shows the LUT (and colour sliders) exactly as the render will, and Effects → Color LUT shows a before/after comparison. Previously LUTs were only visible after rendering, which made them look like they did nothing.
- .cube files with a UTF-8 byte-order mark or accented titles now import; `LUT_3D_INPUT_RANGE` is honoured.
- Fixed a race when the preview and a render built the same grade at the same time.

### Other fixes
- A lead or trail of 0 now renders as zero; previously it rendered the defaults (0.25 s / 0.4 s), so the render was longer than the timeline showed.
- Scene cards and the settings header show the scene's current length rather than the length of its last render.

### Upgrade notes
- Existing databases gain `voice_takes.edit_json` automatically; existing takes keep their data.

### Tests
- `tests/integration/test_audio_edit.py` (26 checks, in CI): trim, volume, fades and length measured on rendered audio; waveform; removal keeps picture and file; database upgrade.
- `test_looks.py` now 40 checks, including the graded preview matching the render; 7 new component checks.

## SceneForge Desktop 0.2.0 RC5 (in progress) — looks, grading and timeline drops

### Glitch
- Tears now reach the whole frame: horizontal bands tile the full height, and the RGB split and noise cover the full frame (previously three fixed strips).
- **Effect strength** sets tear distance, how many bands tear at once, and burst length. New **Speed** (0.25×–4×) sets how often bursts happen; **Block size** chooses Fine, Medium or Chunky bands. These controls appear when Glitch is selected.

### Adjust (Effects tab)
- Eleven sliders with number boxes and resets: Exposure, Contrast, Highlights, Shadows, Temperature, Tint, Saturation, Vibrance, Sharpen, Vignette, Grain. Double-click a slider to reset it; **Reset all** clears them.
- The preview approximates the result live; render the scene for the exact grade.
- Colour sliders and the LUT are baked into one 3D LUT per scene at render time, so grading adds roughly one filter pass however many sliders are used.

### Color LUT
- **Import .cube** in Effects → Color LUT, choose it per scene, and set its strength. 3D .cube files up to 65 points and 12 MB; invalid files are rejected with the reason. LUTs show in the rendered scene, not in the preview.

### Drag and drop onto the timeline
- Drop an audio file from Explorer onto a scene's picture or Narration lane: it becomes that scene's sound, and the scene switches to **Match narration** so picture and audio stay one clip.
- Drop images or videos onto a scene to add them to it, or after the last scene to fill empty starter parts and then create new scenes. Folders work; files are placed in name order.
- Items can also be dragged from the Media Pool onto a scene. Skipped files (unsupported types, more than one audio file per scene) are reported in the timeline.

### Upgrade notes
- Existing databases gain a `look_json` column automatically on first start; existing scenes keep all their data. Back up `backend\data` before upgrading, as always.
- NumPy is now a runtime dependency (`backend/requirements.txt`); run `scripts\setup.bat` again after updating.

### Tests
- `tests/integration/test_looks.py` (33 checks, in CI): full-frame glitch, strength and speed; .cube parsing and rejection; LUT import; slider validation; real renders for LUT strength, greyscale, temperature and exposure; database upgrade from RC4.
- 11 new component checks and 8 new unit checks for the Look panel and timeline drops.

## SceneForge Desktop 0.2.0 RC5 (in progress) — editor fixes

### Captions and text
- Latin text in captions, text layers and title cards now uses the bundled Noto Sans; Arabic text uses the selected Arabic font. Previously English captions borrowed the Arabic font's small digits and narrow spaces, and missing letters fell back to a different system font on each OS.
- Arabic-first lines now lay out right-to-left across the whole line, so a trailing English word appears on the left as it should. RC4 laid these lines out left-to-right.
- Latin system fonts (Arial, Georgia, …) keep an Arabic companion font for Arabic words. **Noto Sans** is added to the font lists. The editor preview picks fonts the same way as the renderer.
- Existing projects render with the new fonts the next time a scene is rendered. Re-render scenes whose captions mix Arabic and Latin text.

### Media
- Videos show a real frame in the Media Pool, scene bin, timeline, effect tiles and the scene media list. Images there load small cached thumbnails instead of full-size originals. Thumbnails are stored under `proxies/thumbs` in the data folder and can be deleted safely.
- **Add to timeline** fills the empty starter parts (Part-1, Part-2, Part-3) before creating new scenes. Empty parts between real scenes are left alone.

### Timeline
- Playback controls: start, previous scene, previous frame, play/pause, stop, next frame, next scene, end. The duplicate Pause and text Prev/Next buttons are removed.
- **Render full video** moved to the timeline tools on the right.
- The lane formerly called Titles is now **Text**: captions show with a captions icon, title layers as a count badge.
- Keyboard shortcuts: Space play/pause, ←/→ one frame, Shift+←/→ one scene, Home/End, Ctrl+Z / Ctrl+Shift+Z / Ctrl+Y undo/redo, Delete removes the selected scene after confirmation. Shortcuts are ignored while typing or when a dialog is open.
- Effects are now chosen only in Scene Settings → Effects; the duplicate left-panel Effects tab is removed.

### Tests
- `tests/integration/test_text_thumbs.py` (18 checks, added to CI): script runs, override-injection escaping, real libass renders for Latin and right-to-left mixed captions, and thumbnail endpoint behavior.
- `frontend/tests/units.mjs` (10 checks) and 6 new component checks for the transport, shortcuts and removed tab.
- Verified on Linux (libass 0.17.1). A mixed Arabic/Latin caption render on the Windows build is still needed.

## SceneForge Desktop 0.2.0 RC3

### Close and credential fixes
- X, Alt+F4 and File → Quit ask **Save and exit** or **Cancel**. Pending narration, captions, titles and project-name changes are saved before stopping the backend. Failed saves and active renders keep the app open.
- Provider credentials use the native Windows credential vault (macOS Keychain / Linux Secret Service in source installs). Legacy Base64 keys migrate on startup; failed migration is reported and the legacy key cannot be used. No plaintext fallback is permitted.
- Migration scrubs the active SQLite database and WAL. Older backups remain outside this migration; keep them private or rotate keys if they were shared.
- Linux CI starts a real Secret Service for credential tests. Windows build commands now stop immediately on a failed command.
- Corrects Together image routing and ElevenLabs audio file format. Cloud provider calls are tested with fixtures; live billable generation is not performed in CI.


### Editing fixes
- Title text saves as you type and stays editable when switching inspector tabs.
- Caption typewriter enables captions and can populate an empty caption from the narration script.
- Direct Edit narration and Edit captions & titles actions reopen the editors.
- Render text preview updates the rendered scene after text or animation changes. Title overlays use their own Animation selector.
- Voice generation waits for the latest narration script to save. Regenerate narration after editing its script.
- In-app confirmation dialogs restore editor focus after closing.

### Earlier changes
- Automatically starts an existing Stable Diffusion WebUI installation when enabled. The default folder is your user profile's `stable-diffusion-webui` folder.
- **AI Engines → Choose Stable Diffusion folder** opens the native folder picker, saves the location and starts the service. **Generate image → Local engine setup** contains the automatic startup switch and editable path.
- Reuses an already-running SD API. On exit, stops only an SD process launched by this app.
- Voice takes now have a Delete action with confirmation. Deleting selected narration invalidates its old scene render and leaves narration unselected. Shared media files remain available.
- Prevents audio deletion during an active project render.
- Explains why voice generation is unavailable when narration text is empty.
- Removes source-workspace launch instructions from desktop voice errors and improves selected-take contrast.

### Install and use
Close SceneForge before running the new setup executable. The same application identity and user workspace are retained, preserving saved projects and provider settings. Do not delete your existing workspace.

For SD, select your existing folder containing `webui-user.bat`, with `--api` in its launch options. Model downloads are not required when reusing your installation. Initial model startup can take several minutes; use Check engine or View startup log in Image Studio.

### Release status
This is an unsigned Windows x64 release candidate. The core editor, private Python runtime, FFmpeg and fonts are bundled. AI engines and model downloads are not bundled. Existing Chatterbox installations remain supported. macOS/Linux installers, signing and automatic engine installation are not included. Real SD inference on the user's GPU remains a manual acceptance check; CI checks launching and stopping a fixture service, not model quality.

### Regression repairs in wip.5
- Source clip sound controls now have a dedicated Clip Audio inspector tab and no longer appear inside Motion. A2 timeline blocks open that tab.
- Crop and focal maps use backend-generated image thumbnails/poster frames, with a readable fallback if preview generation fails. Crop/focal controls save on slider release or keyboard edits as well as through Apply buttons.
- Clip volume commits the exact selected value instead of relying on stale slider state.

### Additional updates in wip.6
- Source clip sound now includes render-applied fade-in and fade-out sliders alongside volume, mute, and narration ducking. Fade settings follow a clip through scene splits.
- Auto captions now switch to a single-column layout in a narrow inspector and return to two columns when there is room.

### Additional updates in wip.7 (previous WIP)
- Export completion offers a local-first share dialog with download, desktop file-location reveal, platform links and step-by-step posting guidance for YouTube, TikTok, Instagram and Facebook. SceneForge does not upload automatically; the dialog explains platform authorization and account limits.
- Timeline ruler scrubbing can snap to scene boundaries and named markers. Markers persist per project in the local browser profile.
- Single, narration-free video scenes can be trimmed from either edge on the timeline; source video audio follows the same in/out points. The existing scene delete operation removes a scene and closes the sequence gap.
- Overlays now include a searchable, categorized 48-item emoji/sticker picker. A chosen symbol is rasterized as a standard image overlay asset so it follows existing placement, transform, animation and render behavior.
- Added three distinct color filter presets: Teal & Amber, Pastel, and Bleach Bypass.
- Updated frontend/backend build IDs and desktop package to `0.6.0-wip.7`. This is still an unreleased source snapshot; no platform upload APIs or full multitrack lock/mute/solo controls are included.
