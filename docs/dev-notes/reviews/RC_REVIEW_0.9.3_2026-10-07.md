# SceneForge 0.9.3 — release-candidate review (October 7, 2026)

Baseline: GitHub `claude/0.9.3` at ab85c7f (newer than the handoff bundle's 6850579) plus the fixes listed in CHANGELOG. Not published, not packaged as an installer: owner approval is required first.

## What was run (Linux, 2 CPU cores, no GPU)

| Layer | Result |
|---|---|
| Release label check (`scripts/check_release_versions.py`) | Pass — 0.9.3 everywhere |
| Frontend unit modules (`npm test`, 14 modules) and production build | Pass |
| Backend integration suite, 73 scripts (self-contained, disposable data folder) | 73/73 pass after the fixes below |
| `test_credentials.py` under dbus + unlocked gnome-keyring, as in CI | Pass |
| `test_stability_stress.py` (8 exports × 60 excerpts on six tracks) | Pass in 67.7 s, no stuck worker |
| `test_v06.py` (longest end-to-end render suite) | Pass in 566 s |
| Legacy live harnesses against a running server (cancel, delete-scene FK, M1.1, M1.2, M1 workflow, motion, typewriter, static fast-path) | 8/8 pass |
| Persistence: kill the server, restart on the same data, re-check project, takes and rendered parts | 17/17 checks pass |
| Browser harnesses in the release suite (9) | 9/9 pass (3 needed a test-only VP9 shim, see below) |
| Legacy browser harnesses (`test:legacy`, 2.3–2.5 layouts) | Fail on removed layouts such as `.program-monitor`; superseded by the 0.9.3 harnesses and not in CI |

## Bugs found and fixed

1. **Warmup merge regression (real).** Moving the 404 check out of the worker let a response whose `raise_for_status()` does not raise be reported as ready. Restored an explicit 404/405 check inside the worker; both warmup tests pass.
2. **Fragile RTL pixel test.** Measured 112.7 against a limit of 110 although the render is correct. Now searches ±3 px for the best alignment and adds a negative control.
3. **Stale mock** in `test_designer25` and **hard-coded machine paths** in nine legacy harnesses.

## Environment notes (not app bugs)

- This sandbox's Chromium has no H.264 decoder (`canPlayType('video/mp4; codecs="avc1…"')` is empty). `release093`, `combined_tools` and `owner_fixes` wait for rendered MP4 previews, so they timed out. With a test-only preload that serves VP9 copies of streamed MP4s (with byte-range support), all three pass. Electron and Chrome include H.264, so this does not affect users.
- `espeak-ng` had to be installed for the offline fallback voice tests, as on Windows.

## Still untested

Windows NSIS installer and uninstall, Windows Credential Manager, NVIDIA GPU paths, real Chatterbox/Kokoro/Stable Diffusion/Whisper/ComfyUI model downloads, and paid providers (not called, per the no-paid-credits rule). GitHub CI status for the new commit cannot be checked from here because this session cannot push.

## Usability observations for the next pass

- At 1280×720 (a common effective laptop resolution with display scaling) the preview monitor becomes small. Collapsing the timeline helps; a larger default preview is worth considering.
- Several inspector tabs sit behind **More** at laptop widths.
- The free-timeline strip at the bottom of the inspector reads as detached from the timeline.
