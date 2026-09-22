# Known Limitations (M1)

Honest, explicit list — nothing here is hidden or glossed over in the main
report.

## Performance

- **Measured in this development sandbox (single vCPU)**: a 3-second
  1080p shot with Ken Burns motion took ~75 seconds to render with FFmpeg's
  `zoompan` filter at the `ultrafast` x264 preset. `zoompan` is a
  per-frame `swscale`-based filter and is not well parallelized — this is
  a real, measured characteristic of the filter, not a bug. **This number
  will be substantially better on a normal multi-core Windows machine**
  (more cores, higher per-core throughput, and possibly hardware
  encoding), but that has not been benchmarked on real Windows hardware
  as part of this session — treat the sandbox number as a conservative
  floor, not a promise for your machine. The automated verification
  fixture in `examples/run_m1_workflow.py` uses a reduced 640×360 test
  canvas specifically to keep CI/verification practical on constrained
  hardware; the product's actual default remains 1920×1080 and is
  controlled by the normal aspect-ratio setting.
- If 1080p Ken Burns rendering proves too slow on real hardware, the
  next lever (not yet built) is an optional "fast preview" mode that
  renders motion at a lower intermediate resolution and only re-renders
  at full resolution for the final export.

## Not implemented in M1 (tracked for later milestones)

- **Separate durable worker OS process** — jobs run in a background
  thread inside the API process (see `docs/architecture.md`). Status and
  progress are DB-persisted so a crash leaves visible state, but nothing
  currently re-claims a "running" job automatically after a restart.
- **Pause** — only queued/running/cancelling/cancelled/failed/succeeded
  are implemented; there is no pause/resume.
- **Portable project export/import** (with media, provenance manifest,
  and hash verification) — the project's data lives in SQLite + a media
  folder on disk; there is no "export this project as a zip I can move to
  another machine" feature yet. This is spec section 16 validation #11
  and was not built this session.
- **Existing-asset-library browsing** in the "Add +" menu — you can
  upload a new file, but there's no UI yet to pick a previously-uploaded
  asset from the same project for a different part (the data model
  supports it; only the picker UI is missing).
- **Drag-to-reorder shots within a part** — shots can be added and
  removed, but not reordered, from the current UI.
- **Multi-shot-per-scene transitions** — shots within one scene are
  concatenated with hard cuts only; the spec's shot-level transition
  richness is scoped to M4.
- **Fault-injection testing** (spec section 16, item 7: missing codec,
  zero-byte media, full disk, invalid key, timeout, 429, invalid provider
  media) was not run this session. The upload path does reject
  non-decodable files (verified implicitly — FFprobe validation runs on
  every upload), but the deliberately-adversarial scenarios in item 7
  were not systematically exercised.
- **Browser end-to-end automation** (spec section 16, item 13) — no
  browser automation tool was available in this development session. The
  full create→edit→preview→export→reopen workflow was instead proven via
  direct HTTP calls against the real running API (see
  `docs/test-report.md`), which exercises the same backend code paths a
  browser session would, but does not prove the React UI itself renders
  and wires up correctly end-to-end in an actual browser. **You should
  open the app in a real browser and click through it before relying on
  it** — the UI code compiles and the API it calls is proven, but the
  DOM-level interaction has not been screenshotted or automated-clicked
  in this session.
- **RTL caption shaping** was rendered via libass (which does correct
  bidi/joining) and spot-checked by eye during development, but was not
  put through an automated glyph-level correctness assertion in this
  session.
- **Variable-frame-rate video input** — the code path that normalizes
  input fps (`fps=` filter applied to every video shot) runs
  unconditionally, but was not tested this session against a source file
  that is actually variable-frame-rate (the fixture's synthetic clip is
  constant-frame-rate).

## Voice quality

- The only narration path in M1 is **espeak-ng**, a local, offline,
  no-credential formant-synthesis voice. It is explicitly **not** the
  Arabic voice-quality deliverable described in spec section 6/M4 — it
  exists solely to prove the end-to-end pipeline (script → narration →
  timed captions → rendered MP4) without requiring any cloud account. Do
  not evaluate Arabic naturalness, pronunciation, or emotional fit
  against this voice; that evaluation is meaningful starting in M2 once a
  real cloud TTS provider is wired up.

## Everything else not yet built

See `docs/capability-matrix.md` for the full per-feature status table,
including image generation, cloud TTS, stock media search, and the
image-only mini chat (all correctly scoped to M2/M3 and stubbed honestly
— they report "not configured" rather than faking a result).
