# Changelog

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
