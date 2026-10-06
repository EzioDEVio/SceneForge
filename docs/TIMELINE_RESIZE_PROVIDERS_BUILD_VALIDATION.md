# Approved combined update — timeline resizing and provider access

Owner approval: **“create the next combined build and ZIP”**, October 5, 2026.
Reviewed implementation commit: `4454efa`; final package source commit and
compiled frontend filenames are recorded in BUILD_INFO.json.

This checkpoint includes the previous combined stages, owner fixes and free
timeline implementation, plus the draggable height divider, Minimize/Restore,
per-project browser height memory, and AI Engines menu with expandable provider
key forms. No provider backend or generation capability was added or removed.

## Fresh production checks

- TypeScript and Vite production build passed at version 0.9.3. Vite's existing
  large-bundle advisory remains; it did not prevent compilation.
- Real Chromium `free_timeline` harness passed with development mode OFF:
  mouse resizing, keyboard bounds, Minimize/Restore, persisted height, free clip
  movement, range splitting, independent audio/text, Undo/Redo and reload.
- The same production run verified the AI provider menu and all eight expandable
  forms, password fields, collapse behavior and the empty-key save guard.
- Real Chromium `owner_fixes` harness passed against the compiled frontend:
  route labels/reversal, draft retry/render, preview minimize/restore, AutoCut
  picture cuts, group movement, storyboard and scene editing, batch Undo/Redo.
- Version agreement passed. Offline release tests: 31 passed. Desktop lifecycle
  unit tests: 18 passed. The full frontend suite and isolated provider save,
  error handling and key-clearing tests passed during source review.

Packaging checks enforce the existing size limit, required sources, production
assets, version agreement, nonempty contents, path safety and ZIP corruption
detection. Clean extraction checks every manifest hash, case-insensitive Windows
path collisions, asset references and the incremental Git recovery bundle.
An extracted-app production browser smoke test covers resize/provider access
and free editing again. The ZIP has complete current sources; its Git bundle
requires the previous Free-Timeline checkpoint commit `86a1469`.

## Owner testing

Extract to a new folder, close the old server, follow START_HERE_WINDOWS.md and
hard-refresh (Ctrl+F5). Verify divider dragging at your screen resolution and
provider key saving with your own account. Complete scene contents remain
linked; standalone media/audio/text can move separately. Marker editing remains
in Scene assembly. The separately delivered marker tutorial is not embedded in
the app ZIP.

This is a combined source checkpoint with compiled frontend, not a Windows
installer. Windows launch, native credential store, installer, GPU and live
provider validation remain pending. No paid calls or GitHub publication occurred.
