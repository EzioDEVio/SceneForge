# Approved owner-fixes combined build — October 5, 2026

The owner approved packaging after clarifying mouse box selection. The source
commit and archive contents are recorded in BUILD_INFO.json and CHECKPOINT_CONTENTS.json.

- Production frontend: TypeScript + Vite build passed; version 0.9.3.
- Full frontend command: 334 editor component checks plus unit, timeline,
  keyframe, story setup, accessibility and owner-fix regressions passed.
- Offline release gates: 31 tests passed.
- Production browser command: release093, timeline_layers, story_tools,
  combined_tools, recovered_stages, owner_fixes and mouse_selection. Development
  mode is OFF; FastAPI serves the freshly compiled frontend.
- Route labels: real forward/reversed FFmpeg output for all six marker choices,
  including final labels, long/Arabic edge text and bundled font resolution.
- Continuous AutoCut: contiguous source ranges, real picture changes, preserved
  duration/text, preview-token mode binding, exact Undo/Redo snapshots.
- Draft integration: isolated render parity, stale-revision/rollback and exact
  style restoration passed.

The mouse test uploads actual pictures, video and a WAV narration take. It selects
with a visible rectangle, moves the group without Ctrl/Shift, verifies captions,
shot and voice-take data, then checks Undo/Redo, Escape, picture-track lock,
normal/compact track bounds and backwards selection after zoom/scroll.
Screenshot: [Timeline mouse selection](Timeline-Mouse-Selection.jpg).

The first marker-shortcut run exposed a harness save race: it sent Undo while
the new marker was still saving. The harness now waits for Undo to be enabled
before sending the shortcut; the keyboard and persisted marker assertions remain.

ZIP checks run after packaging: nonempty contents, compiled assets, version
agreement, corruption detection and SHA-256. Extraction verification checks every
payload hash, Windows case collisions and referenced compiled assets. A clean
extracted-app smoke run exercises mouse selection and persisted group Undo/Redo.

QA uses temporary Linux Python dependencies and Chromium. Dependency pins were
not rewritten. Windows launch, native credential-store, installer and actual
NVIDIA hardware validation remain pending. Stage 1–5 owner sign-offs were HTML
reviews. No live paid provider call, GitHub push, tag or publication was made.
Earlier Stage 6 reframe process-completion limitations remain historical.

Extract into a new folder; follow START_HERE_WINDOWS.md and retest the owner
findings in docs/OWNER_FIXES_2026-10-05.md before any GitHub release.
