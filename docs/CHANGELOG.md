# Changelog

## 0.9.4-beta.1 — owner remarks on RC3 (October 8, 2026, beta pre-release)

Version labels move to 0.9.4-beta.1 because v0.9.3 is already tagged. Release workflow fix: one draft is created before the parallel builds (they had raced and made two releases, and a beta version was published as a pre-release instead of staying a draft); the release check now also requires the pre-release flag for beta versions. Beta: offered only to users who turned on beta updates. Not yet tested on Windows: installer, Open file location in Explorer, Credential Manager.

- **Creative titles open in their own window.** Overlays → Creative titles → *Video inside text* or *Textured title* opens a dialog with a live preview beside the settings and tabs for Create, Position & size, Frame, Move & green screen and Timing & animation, so nothing needs scrolling. The preview updates as you type; once added, drag the layer on the picture to place it. Existing creative layers have an Adjust button. The rendered *Preview video inside text* now plays inside the dialog instead of behind it.
- **Censor words is easy to find again.** The Audio tab opens with a "Censor words (bleep or mute)" card that jumps to the narration, the video's own sound or a timeline audio clip.
- **Effects tab in four icon categories:** Looks, Old film, Adjust & LUT, More effects; one shows at a time (search still looks through all of them). Looks puts the classic looks (with Original) first, with chips to narrow to Classic, Color filters, Film & lens or Creative. A dot marks a category that is in use.
- **Typewriter is at the top of the Text tab** with a typewriter icon, an On/Off switch and a Settings link to its speed and sound.
- **Download and Open file location** (share window): shows where the video is saved with Copy location, reports what happened under the buttons, and works for any local SceneForge address (127.0.0.1, localhost, any port).
- **Free timeline look:** icon buttons, Render full video highlighted, and no more blue text selection while dragging clips.
- **Projects and other left-side actions no longer stall on a pending Motion/Effects draft:** SceneForge asks *Apply and continue* / *Discard and continue*; Cancel keeps the draft and shows it. Saves still in progress are retried for a few seconds, and a blocked action names the scene that is not saved yet.
- **Freezes under load (reproduced and fixed):** many scene renders at once held the database long enough for other saves to fail ("database is locked") and for the editor to wait. Renders and exports now queue for a limited number of slots, progress updates are written less often, the database waits for its turn instead of failing, and uploads no longer block other requests.
- **Long exports no longer run out of memory:** projects with more than 8 scenes are assembled in batches and then joined; transitions across batch joins are kept, and picture and sound stay the same length.
- Tests: `tests/integration/stress_live_server.py` (30 scenes with looks, old film, adjustments, three text layers each, typewriter, karaoke, stickers, picture-in-picture video, textured and video-inside-text titles, voice takes, music clips, transitions; renders, uploads, export and a Free-timeline export while measuring request times and FFmpeg memory), `tests/integration/test_export_batching.py`; updated editor, share-dialog and four browser harnesses for the new dialogs and categories.

## 0.9.3 RC3 — Director's Desk look (October 7, 2026, not published)

Stage 1 of the new design: the look, with no change in how anything works.

- **Director's Desk is the new default theme**: slate-blue panels, one cyan accent, 7 px rounded buttons and boxes, IBM Plex Sans/Arabic/Mono bundled for offline use (OFL). Graphite Night, Daylight, Midnight Blue and Warm Studio remain under Theme. People still on the old default move to the new look once; a theme chosen on purpose is kept.
- **Icon tabs everywhere**: library tabs (Scenes, Media Pool, Transitions), every menu item, and the timeline edit tools (icons with their shortcut letter).
- **Section shortcuts**: the "Jump to section" dropdown and Go button are replaced by a scrollable row of icon shortcuts that follows the section you are reading.
- **More room for the preview**: one-line narration bar (expands on Expand), a shorter default timeline, compact one-row timeline toolbars on laptop screens, and a wider settings panel so all tabs fit without "More".
- Section headings in Scene settings read as boxes; clips, tracks and dialogs use the same palette.
- Fixes found while restyling: theme switches are instant (no half-dark controls mid-transition); the cyan accent becomes a readable teal on Daylight; Free timeline buttons, fields and clip labels on Daylight were dark-on-dark and are now readable.
- Tests: `frontend/tests/preferences_look.mjs` (default theme and one-time move); updated the theme-default and section-shortcut checks.

## 0.9.3 owner fix — export left out the video (October 7, 2026, not published)

- **Export contained only the text overlay.** When Free timeline is switched on it copies only the scenes that already have media. A scene that gets its picture or video later was never added, and export (which uses the Free timeline, even while you view the original source scenes) silently left it out, including its sound and captions. Export now names the missing scenes and asks: **Add to the end and export**, **Export without them**, **Use Scene assembly instead**, or Cancel.
- Deleting a scene now removes its Free-timeline excerpts. Projects saved before this fix drop those dead excerpts on the next save or export instead of failing; a clip that names an unknown scene is still rejected.
- **Open file location** now works when SceneForge runs in a browser: the local SceneForge server opens the folder (Explorer on Windows). It is limited to exported videos, to this computer, and to the SceneForge page itself.
- New checks: `tests/integration/test_free_timeline_export_coverage.py` and `tests/browser/free_export_choice.cjs` (added to the browser suite).

## 0.9.3 release-candidate review — October 7, 2026 (not published; awaiting owner approval)

- Merged the handoff's warmup diagnosis into the newer GitHub baseline (ab85c7f): HTTP 404/405 from `POST /warmup` is reported as an older or different engine on that port, is never retried, and never blames the model download. Kept the explicit status check so an incompatible engine can never be reported ready (a first merge attempt regressed this; caught by `test_managed_ai.py` and fixed).
- Added `test_managed_ai_warmup.py` to CI and the crash-log review document.
- Made the Arabic-first RTL caption check tolerant of 1–3 px HarfBuzz/libass placement differences, and added a control so it still fails if the Latin word is not at the left edge. The rendered caption was inspected visually and is correct.
- Updated the stale `test_designer25` provider mock (`state` field) and made the nine legacy `*_live.py` harnesses portable (repository fixture path and `SF_LIVE_DATA_DIR` instead of hard-coded machine paths).
- Verification only on Linux. Windows installer, native Windows credential store, GPU and real model downloads remain untested.

## 0.9.3 source recovery — October 5, 2026 (not published)

- Reconstructed editor stages from the owner's Stage 1–5 HTML reports and visual review after the earlier source checkpoint was unavailable. This is a fresh implementation, not a recovered copy of the lost commits.
- Atomic Motion/Effects drafts and real render previews; Apply, Cancel, retry and shared Undo/Redo, with isolated preview metadata.
- Inspector sections and scope labels, laptop toolbar wrapping, keyboard menu navigation, light-theme caption readability and a fixed Text preview footer.
- Shared plane/ship/car/pin artwork, destination preview, four additional movements and centered zoom correction.
- Script import opens the first new scene; AutoCut source thumbnails and scrub preview; effective GIF size/rate and project-FPS export labels.
- Version alignment and offline release/archive gates; Windows, native vault and installer validation remain pending.

## Prepared: caption emoji and access review — October 4, 2026
- All 322 bundled caption emoji, colour browsing, category/search and removal.
- Effects shortcuts and search across additional groups make vignette/bars/sharpen and map route easier to find.
- Route appearance presets, Add stop, Reverse journey, coordinates, keyboard editing/removal and shared Undo/Redo.
- Selected overlay controls precede the sticker catalogue; section shortcuts and readable narrow-panel layout.
- Fixed old effect save responses replacing newer local edits; route editing handles appear only in Effects.
- Source review only; another build/checkpoint ZIP requires the owner's OK.


## 0.9.3 — Companion preview, caption emoji and censorship (unreleased)

- Move independent video/image/text draft previews beside the main monitor. Keep controls in Media/Text with Minimize, Restore and Close; preserve unsaved drafts. Use the current scene still as the placement backdrop.
- Add per-caption timed colour emoji from bundled artwork, left/right placement, persistence and export rendering.
- Add source-timed Bleep/Mute ranges for narration, video sound and timeline audio. Offer reviewed English/Arabic word matching from a linked narration transcript, with no new provider calls. Preserve source timing across trim/split; timeline censorship shares Undo/Redo.
- Add adjustable edge vignette, cinema bars and detail sharpening in a styled Finishing touches group; support render, stack order/bypass and portable presets.
- Verify real audio samples, rendered emoji timing, individual effect pixels/bypass, and browser controls. No new build or ZIP: owner approval is required before packaging.

## 0.9.3 — Combined owner-review adjustments (unreleased)

- Stack actual videos on the six overlay tracks, with source trim, placement, muted-by-default sound, playback and export mixing. Preserve source position across splits and skipped empty scenes.
- Group Audio controls and add listening options, narration mute, cleanup and music mix presets, precise timeline audio start, duplication and soft fades. Keep existing processing and Undo/Redo.
- Add optional Script → Scenes setup using selected media or connected local engines, narration, caption boxes or local transcription, styles, motion and rendering. Retain editable scenes on failed steps and restore completed setup on Redo without regenerating.
- Retain AutoCut timeline marker fixes, grouped speed controls and accurate Saved / Apply changes feedback. Improve light-theme control contrast.
- Validate frontend, real browser workflows and real FFmpeg video layers. No Windows validation or installed-model generation is claimed. Combined build awaits the owner’s OK; Sections E and F remain pending. See `STATUS_v0.9.3_COMBINED_REVIEW.md`.

## 0.9.3 — AutoCut marker-source adjustment (unreleased)

- Include ordinary timeline markers in AutoCut as a separate counted source, and select them by default when no detected beat markers exist. Keep music/audio detection and detected beat markers available. Explain that pictures are the media being cut while audio supplies detected beats.
- Verify manual-marker preview, exact clip durations, Apply and Undo in Chromium; also verify generated script scenes open and accept media.

## 0.9.3 — Section D checkpoint (unreleased)

- Add local video stabilization using FFmpeg deshake, with a movement-range slider, matching rendered preview/export, and Undo/Redo.
- Add AutoCut preview and a single undoable picture-sequence edit using timeline beat markers or locally detected music beats. Preserve scene length, narration, captions and overlay timing; respect Picture locks and reject stale previews.
- Add reusable project templates stored locally, available in the editor and on the Projects page. New projects receive independent IDs and remapped media references; templates survive deletion of the source project.
- Add Script → Scenes: TXT/Markdown files or pasted text, English/Arabic headings or blank-line paragraph splitting, editable narration preview, and batch Undo/Redo when appending scenes. Preserve original text and citation references.
- Add real API/render regressions and Chromium coverage; keep all previous features and source versions pending the final release step.

## 0.9.3 — Windows review fixes (unreleased)

- Read captions from a short filename in each FFmpeg subprocess's temporary folder, addressing the 279-character subtitle paths in the owner's Windows failure logs without changing project data locations or the global working directory.
- Darken beige caption boxes and fix caption-number/action contrast in both themes.
- Add sliders with exact values and a live draft preview before Apply changes for independent image/text clips.
- Style both text-card groups and explain whole-video clips versus scene titles with animation/keyframes. Preserve all earlier tools.
- Add deep-path/concurrent-render and browser contrast/draft-preview regressions. See `STATUS_v0.9.3_REVIEW_FIXES.md` for validation and the Windows retest.

## 0.9.3 — Release verification checkpoint (unreleased)

- Add a final tagged-release job that waits for the build matrix and checks the actual draft's Windows installer, blockmap and update metadata, plus the Linux AppImage, deb and update metadata.
- Fail verification for missing, duplicate, empty or unfinished uploads; match installer names to the desktop version and its existing electron-builder configuration. Reject already-published releases.
- Retain Windows blockmaps in downloadable workflow artifacts and add offline release-gate regressions to normal CI.
- Report readiness in the workflow summary without publishing or changing the draft. Windows and Linux build/installed-app tests must also pass.

Section C is implemented and tested offline. Its live GitHub run awaits an approved tag/build. Sections D–F remain pending; the earlier image/text overlay changes still need the owner's Windows review. Product versions remain unchanged until final release preparation.

## 0.9.3 — Independent overlay checkpoint (unreleased)

- Add up to six image/text tracks above the existing captions, picture and audio lanes. Files dropped on these tracks are independent overlays, with their own timing, rather than replacement scenes.
- Add images at the playhead with a real file picker; drag images from Media Pool or local folders onto an upper track.
- Add draggable Text, Text box and outlined Text+ cards inside Text → Text overlays. Click a card to insert it at the playhead.
- Move clips freely in time and between overlay tracks, trim either edge, and drag image/text placement in the preview.
- Add actual text, font, alignment, colour, size, timing, track, width, placement, rotation and opacity controls, with short help and Apply changes. Save pending edits before a restore point or export.
- Preview and full export use the same text rasters. Layers span scenes; skipped empty starter scenes retain placement over the intended footage.
- Support Undo/Redo, copy/cut/paste, duplicate, split and delete for overlay clips. Show working shortcuts in the Help list and clip menu.
- Give timed captions beige boxes with readable text in the timeline and editor; preserve caption render styles.
- Add real FFmpeg/API and Chromium regression checks without removing or relaxing earlier tests.

Sections C–F remain pending. The owner reported the A–B Windows smoke checks passed; this overlay checkpoint still needs their Windows review.

## 0.9.3 — A–B checkpoint (unreleased)

- Empty scene blocks on the timeline open an image/video file picker. Multiple files are added to that scene through the existing undoable upload operation.
- Title cards keep their controls open during editing. Dismissal uses Cancel, the close button, Escape, or a click directly on the backdrop. Keyboard focus stays in the dialog.
- Video inside text uses YOUR TITLE on a neutral card, with a PARIS / 1969 example and matching placeholder. The backend render behaviour is unchanged.
- Text keyframe guidance describes the working X, Y and Font size controls. Image overlays retain preview dragging.
- Keyboard shortcuts are searchable under Help, Ctrl+/ and ?. Real shortcut labels appear in menus, tooltips and context menus; S splits and C selects the blade tool.
- Add Ctrl+A selection, M markers, Ctrl+S restore points, Ctrl+E export settings and +/- timeline zoom. Undo/redo retain their existing handlers. Typing and open dialogs block editor shortcuts.
- Add a real Chromium/FastAPI regression test and run it in CI, alongside the existing frontend and backend checks.

Sections C–F of the owner’s request are still pending. Product version numbers remain at their supplied values until the final release preparation.

## M1.1 — user-reported fixes and UX improvements (post-M1 alpha feedback)

Based on real Windows testing feedback. Verified live against a running
backend (see `tests/integration/test_m1_1_fixes_live.py`, 4/4 checks pass).

### Fixed
- **Silent audio on generated parts** — a newly created or uploaded voice
  take required a separate explicit "Use this take" click before it would
  actually be included in a render; skipping that step produced a
  technically valid but silent video (normal-looking player controls, no
  sound). Voice takes are now auto-accepted immediately on creation.
- **Fixed-duration timing mode did nothing** — the `requested_duration_ms`
  field existed but the renderer always used narration-driven duration
  regardless of `timing_mode`. Fixed mode now genuinely overrides
  narration length (verified: a part with ~1.5s of narration and a fixed
  duration of 3000ms renders at exactly 3.00s).
- **Cache invalidation didn't track duration settings** — changing
  `timing_mode`/`requested_duration_ms` didn't mark a part stale.
- Script text could be silently lost if a project refresh (triggered by
  an unrelated action in a different part) landed before an unsaved
  textarea's `onBlur` fired. Fixed with debounced auto-save plus
  save-aware sync that never overwrites text you're actively typing.
- Job progress (Generate / Export) could get stuck showing stale
  "queued"/"5%" forever if the live event stream stalled, even after the
  job actually finished. Added a 2-second polling fallback alongside the
  live stream, plus an automatic project refresh on job completion.

### Added
- **Duration control UI** — choose "Audio-driven" or "Fixed length" per
  part, with a seconds input for fixed mode.
- **Download buttons** — explicit "Download this part" / "Download full
  video" buttons with friendly filenames (e.g. `Part-1.mp4`,
  `MyProject-export.mp4`) via a new `Content-Disposition` header on the
  asset stream endpoint (`?download=1`).
- All 8 motion presets (zoom in/out, close-up, 4-way pan, static) are now
  always visible in the Image-to-video grid — no more hidden toggle.
- Effect tiles now preview the actual FFmpeg-equivalent CSS filter on
  your real uploaded thumbnail instead of a flat gray swatch (clearly
  labeled as a browser-side preview aid; the rendered clip after Generate
  remains the authoritative result).
- Expanded font list (common Windows system fonts added alongside the
  two bundled, shaping-correct Noto Arabic fonts).
- Visual polish: lucide-react icons throughout (replacing emoji),
  hover/shadow/transition refinements.

### Known open item
- Export appearing stuck at a low percentage for a long time was
  reported but not yet root-caused against the reporter's exact project
  — the leading hypothesis is that it's genuinely re-rendering multiple
  stale parts sequentially (slow, not broken), consistent with the
  "individual part render is slow" report in the same feedback. Needs
  the reporter's `/api/jobs/{id}` status/error payload to confirm.

## M1.2 — Windows-tester round 2 fixes

Verified live (see `tests/integration/test_m1_2_fixes_live.py`, 5/5 checks
pass; espeak-ng-missing scenario verified by temporarily removing the
binary and confirming a clean error instead of a crash).

### Fixed
- **Unhandled crash when espeak-ng isn't installed** — `subprocess.run`
  raises `FileNotFoundError` (not a nonzero return code) when the
  executable is missing; this was never caught, producing a raw
  traceback and a generic "Internal Server Error" in the browser instead
  of a clear message. Now raises a clear, actionable error naming the
  install link, for both local-TTS narration and voice preview/audition.
  The same defensive handling was added to the ffmpeg/ffprobe subprocess
  wrappers themselves.
- **Blank page after creating a new project, fixed only by reloading** —
  `POST /api/projects` returns the new project without its (auto-created)
  scenes list; the frontend set state directly from that response and
  then crashed rendering `project.scenes.map(...)` on `undefined`. Fixed
  by fetching the full project detail (with scenes) before switching into
  the editor.
- **"Generate" looked permanently frozen on longer/slower renders** — for
  a single-shot part, progress only updated at the start and end of the
  entire FFmpeg encode, with nothing in between; a slow render (expected
  on CPU-constrained machines, especially at full 1080p) was
  indistinguishable from a hung one. Progress is now parsed from FFmpeg's
  own `-progress` output in real time during the encode and mapped into
  the job's overall progress, so the bar genuinely moves.
- Added a React error boundary so a future UI crash shows a clear message
  and reload button instead of a silent blank page.

## M1.3 — delete-scene crash fix

Verified live (`tests/integration/test_delete_scene_fk_fix_live.py`,
confirmed passing): deleting a part that had ever been rendered (i.e. had
any associated RenderJob row) crashed with a SQLite foreign-key
constraint violation — `RenderJob.scene_id` had no cascade behavior, so
the scene's row couldn't be removed while a job still referenced it.
Fixed by detaching (not deleting) associated job rows before removing
the scene, preserving job history while allowing the delete to succeed.

### Open investigation — render appears to hang indefinitely for one tester
A tester reported "Generate" never completing across multiple attempts
(5s and 10s fixed duration, with and without narration, Close-up motion).
This was not reproduced or root-caused this session — the M1.2 real-time
progress fix was verified working in this development environment, but
that does not rule out a genuine hang specific to the tester's Windows
setup (antivirus interference with the FFmpeg subprocess, a Python
subprocess line-buffering difference on Windows pipes, or a slow/atypical
FFmpeg build are all plausible but unconfirmed). Needs: Task Manager
confirmation of whether ffmpeg.exe is actively consuming CPU during a
"stuck" render, and a minimal isolation test (Static motion — no
zoompan — at a short fixed duration) to determine whether the zoompan
filter specifically is the bottleneck or something more fundamental.

## M1.4 — static motion fast path (major performance fix)

Verified live at full 1920x1080 (`tests/integration/test_static_fastpath_live.py`):
a 5-second "Static (no motion)" render went from **~100+ seconds to 2.0
seconds** — a ~50x speedup, confirmed end-to-end through the real API.

### Root cause
"Static (no motion)" was still being routed through the full animated
zoompan filter with the zoom pinned at 1.0 — meaning it paid the exact
same expensive per-frame swscale cost (including a large upscaled
intermediate frame with headroom for zoom it never used) as an actual
zoom/pan motion, for a result that never moved. This meant the
"minimal isolation test" a tester was asked to run (static motion, short
duration) wasn't actually testing a cheap path at all, undermining the
diagnosis.

### Fix
Static motion now takes a genuinely separate, minimal code path: a
single scale+crop with no zoompan, no animated crop window, and no
oversized intermediate frame. Zoom, pan, close-up, and Ken Burns motions
are unaffected and still use the full animated pipeline (which remains
inherently CPU-heavy — this is a real, measured characteristic of
FFmpeg's zoompan filter, not something this fix addresses).

### What this means for the "generate never finishes" reports
A tester's CPU-usage check (ffmpeg.exe fluctuating 19-21%, not 0%) during
a stuck-looking render is strong evidence the pipeline was working, not
hung — consistent with genuine zoompan cost at full 1080p on their
hardware. With this fix, "Static" parts should now complete in seconds
even at full resolution; Zoom/Pan/Close-up parts remain inherently slower
and this is expected, not a bug — reduce test resolution or expect
render times in the range of a minute or more per part on constrained
hardware until further zoompan-specific optimization work is done.

## M1.5 — the actual fix: removed `zoompan` entirely (major performance fix, all motion types)

Verified live at full 1920x1080 through the real API, with real
narration and captions (`tests/integration/test_motion_performance_fix_live.py`,
6/6 checks pass), plus the full 26-check M1 regression suite re-run
clean with no failures:

- **zoom_in, 5s @ 1080p: ~100s+ → 6.5s**
- **pan_left, 5s @ 1080p: ~100s+ → 6.5s**

### Root cause (this time, actually the root cause)
M1.4 only fixed "Static" motion. Every other motion — zoom in/out,
close-up, all four pans, Ken Burns — still used FFmpeg's `zoompan`
filter, which recreates its internal scaling context on every single
frame. This is a known, well-documented performance characteristic of
`zoompan` in the FFmpeg community, confirmed here by direct
benchmarking: the identical zoom effect took ~100s via `zoompan` and
~2-6s via the replacement below, at the same resolution and duration.

### Fix
Replaced `zoompan` entirely with a three-stage `scale`+`crop` pipeline:
1. One-time cover scale to fill the canvas
2. A `scale` filter with `eval=frame`, animating zoom level per frame
   (confirmed by direct pixel-diff testing to genuinely re-evaluate
   every frame — average pixel difference of 3.19 between first/last
   frame of a 5s zoom, vs 0.012 for a failed same-size-crop-only attempt
   that turned out not to animate at all, since `crop`'s width/height
   expressions are only evaluated once at init, unlike its x/y which do
   support per-frame evaluation)
3. A `crop` to the final constant output size, with per-frame x/y
   implementing pan and focal-point tracking

Same deterministic (focal_x, focal_y, scale) start/end contract as
before — this is a swap of the underlying FFmpeg technique, not a
change to the motion presets or their math. Verified visually (frame
extraction at start/mid/end) that the zoom and pan are genuinely
animating, not frozen.

### What this means
This should resolve the "Generate never finishes" reports for
Close-up/Zoom/Pan motions, which affected every motion type except
Static until now. If a render still takes an unreasonable amount of
time after this fix, please report the specific motion type, duration,
and resolution — this fix directly targets the confirmed root cause
(zoompan), so a persistent slowdown after this would point to a
different, new issue rather than the one already diagnosed.

## M1.6 — new effects, typewriter captions, UI modernization

Verified live (`tests/integration/test_new_effects_and_typewriter_live.py`,
4/4 checks pass; typewriter reveal additionally confirmed by extracting
real frames at 0.3s and 3.5s and visually confirming the caption grows
from "This is a" to the full sentence).

### Added
- **Glitch** effect — RGB-channel split (chromatic aberration) + grain,
  prototyped and visually reviewed before being added.
- **Old Film** effect — heavier desaturated vintage grade + grain +
  vignette, distinct from the existing lighter "Vintage" preset.
- **Typewriter caption reveal** — a new Font-panel checkbox; captions
  reveal progressively (character-by-character, chunked for very long
  text) over roughly the first 3 seconds or 60% of the shot, then hold
  the full text. Implemented as multiple timed ASS dialogue lines, not a
  simulated/cosmetic toggle.
- UI modernization pass: every part-row section (script, media, motion,
  duration, effects, font, voice, generate) now has a proper card
  treatment (soft background, border, consistent padding) instead of
  flat bordered boxes, plus a matching icon in every section header
  (lucide-react). Verified present in the actual built CSS/JS bundles
  served by the backend, not just in source.

### Still open
- AI image generation remains unimplemented pending the user's choice of
  provider (OpenAI, Stability AI, etc.) and their own API key — this is
  an external dependency, not a code task that can proceed further
  without that input.
