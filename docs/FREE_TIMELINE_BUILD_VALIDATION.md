# Approved free timeline combined build — October 5, 2026

The owner replied **Continue** to the explicit question asking approval for the
combined update build and ZIP. The current source commit is recorded in
BUILD_INFO.json. This package includes the preceding combined stages and owner
fixes, plus free timeline, route and narration-discovery changes reviewed at
source commit `1652ae7`.

## Fresh package checks

- Production frontend: TypeScript + Vite build passed, version 0.9.3. Vite reports
  the existing large-bundle advisory; compilation succeeded.
- Production browser: `free_timeline` and `owner_fixes` passed. Development mode
  was OFF; FastAPI served the freshly compiled frontend. These checks used real
  uploaded image/video/WAV fixtures and disposable databases, not paid providers.
- Free timeline: empty-space mouse placement, compatible track changes, group
  selection, highlighted-range excerpts, independent text/audio, Undo/Redo and
  reopen passed. Source scene order and source composition remain unchanged.
- Real export: black/silent gaps, exact duration, mixed sound, shared picture
  track stack, source excerpt bounds, caption offsets, template remapping and
  independent media export with zero scenes passed.
- Offline release gates: 31 tests passed. Desktop lifecycle: 18 unit tests passed.
- Release version labels agree at 0.9.3. No production dependency pins changed.

The earlier source validation, including full frontend suites and six route
markers forward/reverse, is recorded in FREE_TIMELINE_OWNER_REVIEW_2026-10-05.md.
Archive checks verify required files, nonempty compiled assets, corruption, size
and SHA-256. Clean extraction additionally verifies every manifest hash, Windows
case collisions, referenced compiled assets and a production browser smoke run.

## Environment and boundaries

Temporary QA Python/Chromium tools had been cleared between sessions and were
restored locally. The initial browser startup failed because uvicorn was missing;
the browser download and alternate unpacker also needed recovery. The final
browser runs passed after local tooling restoration. These temporary tools are
not included in the ZIP and do not establish a clean Windows dependency install.

Complete scene contents remain linked. Standalone pictures, video, text and
audio move independently; source-scene internals are not automatically unpacked.
Free timeline export uses hard cuts and track stacking; old sequence boundary
transitions remain in Scene assembly. Render source changes for exact preview.
Audio finishing must be fully rendered to audition exactly. No new free-track
lock/mute controls are included.

Extract to a new folder and follow START_HERE_WINDOWS.md. This is a source
checkpoint with compiled frontend, not a Windows installer. Windows launch,
native credential vault, installer and actual GPU checks remain pending.
No live paid provider call, GitHub push, merge, tag or publication was performed.
