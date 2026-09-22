# Test Report — M1

All tests below were run against a **live backend process** with **real
FFmpeg subprocesses** — nothing here is mocked or simulated. Raw JSON
results are checked in alongside this report (`test-evidence-*.json`);
the scripts that produced them live in `tests/integration/` and
`examples/`.

## Environment this was actually run on

- 1 vCPU (Intel Xeon @ 2.10GHz), Linux sandbox
- FFmpeg 6.1.1, built with `--enable-libass --enable-libfribidi
  --enable-libharfbuzz --enable-libx264 --enable-libx265`
- Python 3.12.3, Node 22.22.2
- espeak-ng 1.51 (offline narration)

This is **not** Windows, and the CPU is unusually constrained (see
`docs/known-limitations.md` for what that means for performance
estimates). Everything reported below is a functional/correctness
result, not a performance guarantee for your machine.

## 1. Full workflow test — `tests/integration/test_m1_workflow_live.py`

Drives the real HTTP API exactly as the frontend would: create project →
upload image + video clip + image → distinct per-part scripts, motion,
effects, transitions → Arabic + English narration via local offline TTS →
independent per-part generation → probe every output → full export with
mixed cut/dissolve transitions → invalidation check.

**Result: 26/26 checks passed.** (`test-evidence-m1-workflow.json`)

Highlights:
- `part2_generate_did_not_touch_part1`: **PASS** — generating Part-2 left
  Part-1's `rendered_plan_hash` and `rendered_asset_id` byte-for-byte
  unchanged.
- `part{1,2,3}_decodes_start_mid_end`: **PASS** — each part's MP4 was
  fetched through the real `/api/assets/{id}/stream` endpoint and had a
  frame actually decoded (not just probed) at the start, middle, and near
  the end.
- `export_succeeded` / `export_decodes_start_mid_end`: **PASS** — a
  13.20s export combining a hard cut (Part1→2) and a 500ms dissolve
  (Part2→3) decodes cleanly throughout.
- `changed_motion_marks_only_part1_stale`: **PASS** — after changing
  Part-1's shot motion, `is_stale` was `true` for Part-1 and `false` for
  Part-2 and Part-3.

Note: this run used a 640×360 test canvas rather than the production
default 1920×1080, to keep total runtime practical on this sandbox's
single CPU core — see `docs/known-limitations.md`. Every code path
(motion, effects, captions, audio mux, transitions, invalidation) is
identical regardless of resolution; only the pixel count differs.

## 2. Persistence-after-restart test — `tests/integration/test_persistence_live.py`

The backend process was killed (`kill -9` on the uvicorn process, not a
graceful shutdown) and a fresh process started against the same data
directory, simulating an application restart / crash recovery of already
-completed work.

**Result: 17/17 checks passed.** (`test-evidence-persistence.json`)

- The project, its title, all 3 parts' script text, shots, and accepted
  voice takes were all reloaded correctly from SQLite.
- All 3 parts' previously-rendered MP4 files were still on disk and
  **still decoded successfully** when streamed back through the API
  after the restart.

## 3. Cancellation test — `tests/integration/test_cancel_live.py`

A part with an intentionally long narration (~22.7s, so the render would
still be running when we cancel) was generated; the render's actual
FFmpeg process was located by PID; a cancel request was issued mid-render;
the job's terminal status and the specific FFmpeg PID were both checked
afterward.

**Result: 5/5 checks passed.** (`test-evidence-cancel.json`)

- `render_ffmpeg_process_started`: confirmed a new FFmpeg process (PID
  302 in this run) actually appeared before cancelling — cancelling
  before any work started would prove nothing.
- `job_reached_terminal_cancelled_state`: the job's status became
  `cancelled` (not stuck, not silently `failed`).
- `no_orphan_ffmpeg_process_after_cancel`: PID 302 was confirmed **gone**
  after cancellation — the process-tree kill (`os.killpg` +
  `SIGKILL` on Linux, `taskkill /F /T` on Windows) worked.

This test also caught and fixed two real bugs during development (see
`docs/architecture.md` and the conversation history): an FFmpeg
stdout/stderr pipe deadlock risk, and — separately — an orphaned FFmpeg
process from an earlier manually-interrupted test run that was silently
consuming the sandbox's single CPU core. Both are fixed; the orphan-kill
path is now the one this test verifies.

## What was NOT tested this session

See `docs/known-limitations.md` and the validation table in
`docs/capability-matrix.md` for the complete, itemized list against spec
section 16. In short: fault injection (missing codec / zero-byte media /
full disk / 429 / timeout), restart-*during*-an-active-job, portable
project export/import, and real browser automation were not run. The
code and test harness are structured so each of these can be added
incrementally without rearchitecting.
