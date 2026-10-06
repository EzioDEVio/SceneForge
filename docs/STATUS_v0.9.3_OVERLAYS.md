# SceneForge 0.9.3 — independent overlay checkpoint (unreleased)

This checkpoint extends the A–B work before sections C–F. The owner reported all A–B Windows smoke checks passed. The checks below were run on Linux, not Windows. This is source code and a git bundle, not an installer or a published release.

## Delivered behaviour

- Image and Text / Text box / Text+ clips live on independent upper tracks above the existing scene captions, video and audio. Up to six tracks and 64 clips; overlapping clips have separate visible rows rather than hiding each other.
- Drag images from Media Pool or local folders to a time on an overlay track, or use the actual image picker at the playhead. Videos still use Picture and audio still uses its existing tracks.
- Drag the new cards inside Text → Text overlays, or click one to insert at the playhead. The existing per-scene text and Text+ animation tools remain available.
- Drag clips in time or between visible tracks; trim either edge. Controls set start/length, track, placement, width, rotation and opacity; text controls add wording, size, colour, font and alignment. Each new control has short help.
- Images and text can be dragged in the editing preview. Project text previews and exports use the same Pillow-generated raster, including bundled fonts and Arabic shaping. Live timeline playback includes the project overlays; full export burns them into the assembled video before music/loudness finishing.
- Undo/Redo, split, copy/cut/paste, duplicate and delete operate on selected overlays and retain the underlying video. A context menu and searchable shortcut sheet show the real keys.
- Apply changes saves inspector edits. Ctrl+S, export and project closing also flush pending text before continuing; deleting an overlay removes only that clip. Restore points preserve and remap image references.
- Clips can span scenes. Export timing accounts for skipped empty starter scenes so overlays remain over the intended footage. Empty-only spans are omitted along with that empty footage.
- Timed caption segments appear as readable beige boxes both on the timeline and in the caption editor. Existing caption rendering/styling is preserved. The browser check uses timed caption fixtures and does not claim to run a speech model.

## Validation run

| Check | Result |
|---|---|
| `npm --prefix frontend run build` | PASS: TypeScript and Vite production build. Vite retains its large-chunk advisory. |
| `npm --prefix frontend test` | PASS: 334 component checks, 21 units, 48 timeline checks, 2 mocked video-generation workflows, 6 share-dialog checks, 27 keyframe/playback checks. |
| `python tests/integration/test_timeline_layers.py` | PASS: 31 checks, real FFmpeg exports and pixel checks. Includes image timing at five seconds in a 20-second video, scene-spanning duration, all three text kinds, Arabic Text+, track order, preview/export raster equality, invalid/foreign assets, snapshot restoration and skipped empty scenes. |
| `python tests/integration/test_finishing.py` | PASS: 29 existing checks, including actual music ducking and loudness measurement. |
| `python tests/integration/test_caption_segments.py` | PASS: 2 existing caption checks, including independently timed ASS cues and RTL/LTR direction. |
| `python tests/integration/test_keyframes_playback.py` | PASS: 40 existing keyframe/playback checks. |
| `npm --prefix tests/browser test` | PASS: both `release093.cjs` and `timeline_layers.cjs`, actual Chromium 153 plus disposable FastAPI backends. Tests actual choosers, browser pointer movement/trim, Text+ drop, local File and real Media Pool drag payloads, preview drag, live sequence playback, persistence/reload, beige caption boxes, context actions, typing guards, shortcuts, Undo/Redo and pending-text restore-point saving. |
| `git diff --check` | PASS. |

Chromium ran with a local executable via CHROMIUM_PATH because the standard Chromium download returned a truncated archive. All provider calls were avoided. No secrets were read or included in the delivery.

## Remaining release work

Sections C–F remain pending, including the full backend integration sweep, installer builds and final version/release documentation. No push, merge into main, tag or publication was performed. Earlier legacy browser-suite failures are recorded in STATUS_v0.9.3_AB.md; those four suites were not rerun or reported as passing in this overlay checkpoint. No Windows UI or installer test is claimed for these new changes.

Text+ timeline cards currently use a bold outlined title. Animation/keyframe controls for existing per-scene Text+ remain unchanged. Independent layers are part of full export; downloading an individual scene gives its existing scene-local layers. Project overlay compositing uses a software FFmpeg pass after scene assembly, so exports with many overlays take additional time even when the scene/export encoder is set to GPU.
