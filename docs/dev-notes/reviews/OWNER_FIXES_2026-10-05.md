# Owner findings — October 5, 2026

Baseline: `584937fb1e719241214f14973e9243d831911932`, the delivered combined 0.9.3 checkpoint. The owner approved the combined source build after clarifying mouse selection on October 5, 2026. Build results are recorded in BUILD_INFO.json and docs/COMBINED_BUILD_VALIDATION.md. No installer or GitHub publication is authorized by that approval.

## Changes

- Map routes: immediate draft stop names; Apply/Reverse include the final keystroke. Every label is shown in the completed source preview. Rendered labels use a font size independent of the icon, resolve bundled fonts correctly, fit long text and stay inside the frame. Origin/destination labels are readable on arrival, including the final draw frame. Render caches are invalidated. Stop cards are separated; None/Dot have visible symbols.
- Draft preview: a compact dedicated media area and rendered-frame poster; progress, stopped/failed states, retry and stop controls. Job-check requests time out after 10 seconds. Apply/Cancel stay in the inspector and wrap within its width. Minimize/restore keeps the draft.
- Script → Scenes: shared 16-motion catalogue, configured ElevenLabs voices with explicit paid-batch consent, visual storyboard using selected media and approximate caption layout before Add. This sample does not generate paid narration or simulate an exact render. After Add, result cards open the chosen scene editor. Old multi-selection is cleared; bulk actions are hidden while Story tools is open.
- AutoCut: separate V1 thumbnails/boundaries, source in-points in preview, and matching A2 durations. Split-screen tiles represent simultaneous panels; only the first panel supplies sound, matching the renderer. Repeat remains available. New Continue through one video advances source ranges at each cut and requires one video long enough for the scene. Preview tokens include this choice.
- Mouse box selection: drag from empty scene-track space, or click Box select and drag over clips. The rectangle selects intersecting scenes and highlights their linked pictures, text, narration and embedded sound. Release, then drag a selected scene to move the group. Escape cancels the rectangle; zoom/scroll and picture-track locking are respected. Compact picture clips now fit inside V1 instead of overlapping audio rows.
- Whole-scene selection: linked T1/A1/A2 clips highlight with V1. Ctrl/Shift-select and drag moves selected scenes together in project order. Scene text, captions, narration and embedded sound follow; independently positioned project music and upper timeline layers keep their authored project positions. Undo/Redo restores scene order.

## Validation commands

```
npm --prefix frontend test
npm --prefix frontend exec -- tsc -b frontend/tsconfig.json --pretty false
python scripts/check_release_versions.py
python tests/integration/test_route_owner_fixes.py
python tests/integration/test_autocut_continuous.py
python tests/integration/test_editor_drafts.py
python tests/integration/test_story_tools.py
SF_BROWSER_DEV=1 node tests/browser/owner_fixes.cjs
SF_BROWSER_DEV=1 node tests/browser/recovered_stages.cjs
SF_BROWSER_DEV=1 node tests/browser/combined_tools.cjs
SF_BROWSER_DEV=1 node tests/browser/story_tools.cjs
```

New focused regressions are included in the normal frontend/browser commands and CI. Linux checks use disposable databases, real FFmpeg output, Vite development mode and Chromium. Temporary Python dependencies and a serverless Chromium executable were used because the standard Playwright browser download was unavailable. These checks do not validate a pinned dependency installation, native Windows UI or packaged installer. ElevenLabs confirmation was checked with controlled metadata; no live paid generation or voice-catalog requests were made. Not every original visual-review concept is implemented by this focused change.

## Windows retest

1. Name route stops Spain/Rome/London, immediately Apply, render, Reverse, Apply/render, Undo/Redo, reopen. Try Arabic and edge labels; inspect None/Dot and card spacing.
2. Change Motion/Effects, render/play the draft, minimize/restore, Apply/Cancel. Try an unavailable backend, then reconnect and Retry.
3. Preview English/Arabic paragraphs; choose a pool picture, motion and caption style; review each storyboard and edit narration. Add, open the second result card, Undo/Redo and reopen. Original scenes remain. Live ElevenLabs generation is optional and uses the owner's account after explicit consent.
4. Check V1 picture boundaries and A2 timing. Use Repeat for pictures, Continue through one video for one long clip; preview, Apply, render, Undo/Redo and reopen. Verify narration and scene length remain.
5. Mouse-select two scenes using an empty-track drag or Box select, drag past a third, confirm their text/narration/embedded sound move together, then Undo/Redo. Independently positioned project clips retain their authored positions.

The owner's latest approval satisfies `docs/HANDOFF_TO_CHATGPT.md` section 1 for this combined build. Windows validation and GitHub publication remain separate.
