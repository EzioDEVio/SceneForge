# Text overlay repair and package stability — 2026-10-06

Baseline: source `65e612c53424ebeca618473ee7a43c3ac2340211`, delivered
Timeline-Resize-Providers checkpoint, SHA-256
`f74d19aa287e679563d131661afe797ac5b3ac4055138c25af82bfa0d5c54bf2`.
The original ZIP passes its original archive gate: 1024 files, 29,171,755 bytes.

## Evidence and changes

The two owner screenshots show video-inside-text insertion failing and a
broken Text Box raster preview. The supplied Windows log identifies Pillow's
`_imagingft` DLL import failing with “The filename or extension is too long.”
Injecting that exact exception into the extracted delivered app reproduces
HTTP 500 on knockout title, textured title and Text Box preview.

The source repair uses a per-checkout short Windows runtime, shared font-byte
loading, actual Latin/Arabic setup/start checks, recoverable HTTP 503 messages,
and visible preview error details. Failed insertion leaves the saved scene
unchanged. All Windows launch/update entry points carry the runtime helper;
setup failures cannot report success. The future ZIP gate requires these files.
See TEXT_RUNTIME_RECOVERY.md for Windows retest steps.

Cancellation testing exposed a process cleanup race: cancellation returned
before FFmpeg was reaped. The wrapper now terminates/reaps the process and
closes its output pipe; Windows taskkill also has a timeout. Three real
cancel/retry cycles pass with no live encoder and a playable retry output.

## Fresh validation

- **51 backend integration suites pass**, covering text and titles, Arabic,
  previews/atomic Apply, overlays, both timelines, source/rendered splitting,
  AutoCut, Script → Scenes/templates/stabilization, routes, effects, color/LUTs,
  captions/emoji/censoring, audio, exports, model request handling, diagnostics,
  stale-job recovery and deletion protection, provider adapter contracts,
  reframe/CPU fallback, real ONNX voice isolation, and cancellation.
- Text runtime regression: 72 real mixed-language previews across eight fonts
  and three text kinds; simulated DLL/missing-font errors on both title APIs
  and all three text kinds return recovery messages without saved mutation;
  recovery in the test process works. Deep Unicode font paths also render.
- Full-resolution finishing suite: **29 checks pass**, 607.6 seconds, including
  film burn, timing, music looping/ducking, measured -13.4 LUFS, projector sound,
  independent A3/A5 placement, gap silence, mute and solo.
- Reframe/encoder suite: 62 checks pass, including vertical output and CPU retry.
  Real NVENC hardware is not present. Voice isolation: 19 real model/API checks
  pass, including source preservation, cache, video input and finished jobs.
- **All eight regular Chromium harnesses pass** against source mode. A targeted
  timeline-layers rerun verifies a simulated 503 message appears in the draft,
  saved text remains intact and the recovered preview loads without JS errors.
- The full frontend test command passes again after the preview change.
  TypeScript checks pass. Desktop lifecycle: 18 pass. Offline release/version/
  archive tests: 31 pass. Labels still agree at 0.9.3. Python syntax and diff
  whitespace checks pass.

Initial failures were investigated, not suppressed: the combined-export test
expected older error wording and required a native vault for fixture keys;
its current preflight assertion also checks zero durable jobs. Adapter tests
now use an explicit test-only memory vault; production credentials are unchanged.
The old timeline fixture lacked the now-required `finishing_json` field. Both
updated suites pass. The new cancellation regression initially exposed the
cleanup race and passes after the production fix. Normal textured/knockout
render tests also pass again after the cleanup change.

## Limits and next step

Tests use disposable projects/media. No paid generation, real provider keys,
GitHub publication, production frontend rebuild, installer or new ZIP occurred.
The Windows DLL cause is evidenced by the owner's logs; reproduction in Linux
injects the same exception. Actual Windows Batch/PowerShell execution, short
runtime DLL loading, native credential store, GPU hardware and live AI services
remain owner/platform gates. Legacy live-server harnesses and extra model
cutout downloads were not part of this offline regression run.

This is a tested source repair ready for owner review. A fresh compiled frontend
and combined checkpoint ZIP require the owner's next build approval.
