# SceneForge 0.9.3 — A–B checkpoint

This is an unreleased source checkpoint on `claude/0.9.3`, starting from the exact supplied handoff commit `3ac0d44a05f53979f652854155369f3253cb2b0a`. Claude’s existing commits are preserved. It is not the final 0.9.3 release, an installer or a Windows-tested build.

## Section A

1. Click **Add media** inside an empty timeline scene to open an image/video picker. Multiple selected files are added to that specific scene through the existing upload and undo operation. The destination is captured when opening the picker. Disabled/locked picture tracks cannot upload.
2. The title-card dialog is mounted above the editor. Editing text, presets, dropdowns and other controls keeps it open. Cancel, ✕, Esc or clicking directly on its backdrop closes it; completing Create title card also closes it after creation. During creation, dismissal stays disabled so the operation cannot be interrupted. Tab stays inside the dialog.
3. Video inside text starts with **YOUR TITLE** on a neutral grey card. Its hint and placeholder use **PARIS or 1969**. Actual user text is sent unchanged to the existing render endpoint.
4. The allowed wording correction was used: text layers use X/Y/Font size controls, editing the keyframe at the playhead. Preview dragging remains available for image overlays. Text dragging has not been added.

## Section B

- Help → Keyboard shortcuts, **Ctrl+/** and **?** open the same searchable list.
- Real shortcuts appear in the existing menus, timeline tooltips and right-click menus. The erroneous C label on Split is now S; C retains the Blade tool.
- Existing Ctrl+Z / Ctrl+Y / Ctrl+Shift+Z, Delete and Space handlers are retained.
- **Ctrl+A:** all scenes on the picture lane; all unlocked timeline audio clips when audio has focus.
- **S:** split the focused scene/audio clip at the playhead, respecting track locks and the existing render/bake requirements.
- **M:** add a named marker, through the existing undoable marker operation.
- **Ctrl+S:** save current edits, then persist a manual restore point. Save failures block the snapshot. It does not export a project file.
- **Ctrl+E:** open export settings when the corresponding button is available.
- **+ / -:** timeline zoom. Ctrl+wheel continues to zoom the timeline/preview.
- Typing in inputs, textareas, selects and nested contenteditable text blocks blocks editor shortcuts. Open native confirmation dialogs and app dialogs also block them. Escape remains available for closing dialogs.
- App-level shortcuts read the current project state instead of the initial render’s closure.
- The new browser test is wired into `.github/workflows/checks.yml`. Existing integration tests remain intact.

## Validation on Linux

| Command / suite | Result |
| --- | --- |
| `npm --prefix frontend run build` | PASS: TypeScript and Vite production build. Existing large-chunk advisory remains. |
| `npm --prefix frontend test` | PASS: all six suites. 334 editor component checks, 21 units, 48 timeline checks, two video-generation workflows, six share-dialog checks, 27 keyframe/playback unit checks. API/provider interactions in these component tests are fixtures. |
| `python tests/integration/test_091_fixes.py` | PASS: 16 checks, including real FFmpeg video-inside-text rendering and cutout cancellation cleanup. |
| `python tests/integration/test_keyframes_playback.py` | PASS: 40 keyframe/render/playback checks. |
| `python tests/integration/test_090_features.py` | PASS: 31 checks, including restore points, beat markers and sample rendering. |
| `python tests/integration/test_source_split.py` | PASS: source splitting keeps clip audio, editable text/caption timings and correct thumbnails. |
| `npm --prefix tests/browser test` | PASS: real Linux Chromium 153 + disposable FastAPI backend. Click a scene-specific file chooser, upload two images and a video, confirm persisted destination; title typing/presets and all dismissal paths; neutral title example; searchable help; typing/contenteditable/native-dialog guards; selection/zoom; marker undo/redo; persisted manual restore point; export settings; persisted source split and undo/redo. |
| `git diff --check` | PASS. |

No Windows UI test, Windows installer build, full backend integration sweep, cloud-provider call, push, merge into main, tag or publication was performed. The full release test sweep remains part of section F.

## Broader browser failures found

The existing browser suites were also attempted. They are not reported as passing, and their assertions were not weakened.

- `workspace.cjs`: the preview-size assertion fails at 1366 × 768. Reproduced separately on the untouched handoff commit, as well as this checkpoint. The untouched preview measured about 101 × 57 pixels at the assertion; the required minimum short side is above 60 pixels. This needs layout/readiness investigation before release.
- `playback23.cjs`: `.program-monitor video` matches both SequencePlayer buffers, so Playwright stops with a strict-locator error. Also reproduced on the untouched handoff commit. This test needs to identify the active player while retaining its playback assertions.
- `titles24.cjs`: the first-run tour intercepts its Undo click; this suite does not dismiss the tour before exercising editor controls.
- `designer25.cjs`: the first-run tour likewise intercepts Undo. The new A–B test explicitly dismisses the tour and successfully exercises title-card controls.

The failure logs are included in the delivery archive. Resolve these before claiming all editor browser suites or the final release are green.

## Remaining request, in order

- **C:** draft release asset verification for Windows exe/blockmap/latest.yml and Linux AppImage/deb/latest-linux.yml.
- **D:** stabilisation, AutoCut to beats with Undo, project templates, Script to scenes.
- **E:** requested effects and transitions, each with actual preview/export behaviour, search, explanation, strength controls and backend coverage.
- **F:** final 0.9.3 version bump, final release documentation, complete backend/frontend/browser verification and final bundle. The supplied product version numbers are intentionally unchanged until that release step.

The source checkpoint includes updated README, CHANGELOG and manual wording. No final release notes claim that C–F are complete.
