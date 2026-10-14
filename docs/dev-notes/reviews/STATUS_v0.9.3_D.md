# SceneForge 0.9.3 — Section D checkpoint

The owner passed all Windows checks for the previous review-fixes checkpoint on October 3, 2026. This checkpoint adds Section D and keeps the A/B, overlay, C and review fixes. Nothing has been pushed, tagged, merged or published. Source versions stay unchanged until Section F.

## Delivered behavior

- **Video stabilization:** Edit → Stabilize video. Local FFmpeg deshake runs on source videos before framing, grading and titles; still images are unaffected. Movement range maps to small/medium/large search windows. Mirrored edges fill movement gaps. Rendered scene preview and export use the same processing; the fast editing still does not simulate stabilization. Apply, removal, Undo and Redo retain the scene's audio and length.
- **AutoCut:** Edit → AutoCut. Preview selected-scene cuts using regular timeline markers, existing beat markers, or detect locally from the music bed / a timeline audio clip. Choose every beat, 2 beats or 4 beats. Cuts are rounded to project frames and the scene keeps its full length. Selected pictures repeat in order; video excerpts restart at their current in-point and keep speed and trim. A beat interval longer than a video's excerpt is rejected with a helpful message. Narration, captions, scene titles, upper layers and independent audio keep their original timing. Unselected media is retained. One Undo restores the entire original picture sequence; Redo restores the same edit.
- **Project templates:** Save a named project setup from Edit → Project templates. Open/use/delete templates here or from Projects → Project templates. Saved database rows survive deletion of the original project. New projects get fresh IDs and remapped references for scenes, shots, narration, LUTs, stickers and upper tracks; media files remain shared on disk. Deleting a template does not delete created projects. Templates are local reusable setups, not portable media archives.
- **Script → Scenes:** Paste text or open TXT/Markdown; split at blank lines or English/Arabic scene headings. Preview scenes, edit narration, inspect original text and warnings, then append a batch. Original text and citation references remain available; subtitle text omits citation markers. Multiline fields are preserved. Undo/Redo affects the batch. Importing does not generate paid images or voices; add pictures and narration separately.

AutoCut requires an unlocked Picture track, sequential media, and no countdown intro, speed ramp or freeze frame. It rejects stale scene/timeline previews and edits during rendering. It edits pictures inside the selected scene; existing whole-project Beat sync remains available. The dialog traps keyboard focus and supports Escape when idle.

## Verification in this environment

- Production frontend build passed.
- All six existing frontend suites passed: 334 component checks, 21 general units, 48 timeline checks, 2 mocked video-generation workflow checks, 6 share-dialog checks, 27 keyframe/playback units.
- Existing release093 and independent timeline-layer Chromium suites passed. New real Chromium suite verifies AutoCut Preview/Apply/Undo/Redo, editable Arabic script import with batch Undo/Redo, template creation from the Projects page, stabilization save/Undo/Redo, reload persistence and no browser JavaScript errors.
- Section D real API/FFmpeg checks passed (35 checks): rendered pictures change at beat cuts, Undo/Redo retains clip IDs, out-of-scene markers and stale previews/track locks are rejected, script modes retain multiline Arabic/citations, templates survive source deletion, media references are remapped, invalid stabilization settings are rejected, actual deshake rendering is playable and reduces movement in simulated handheld footage.
- Existing integration regressions passed: 31 template/sample/caption/ducking checks; 31 independent timeline-overlay export checks; 40 keyframe/playback checks; 4 deep caption-path/concurrency/cancellation checks.
- Workflow YAML and whitespace checks passed. Section D backend tests are included in checks.yml; the new browser suite is in the existing npm browser test command.

Local runtime: Linux, Python 3.12, FastAPI 0.142.2, SQLAlchemy 2.1.3, Pydantic 2.13.5, Pillow 12.3.0, system FFmpeg, Node tooling from the pinned npm lockfile, Chromium 153 through CHROMIUM_PATH. Python repository pins are unchanged; these results are local checks, not a GitHub CI or Windows-installer run. The existing large frontend bundle notice remains.

## Windows checks for this checkpoint

1. **Script → Scenes:** Edit → Script → Scenes. Paste two paragraphs, including Arabic; preview, edit one narration, add scenes. Close the dialog, Undo and Redo. Existing scenes should remain. Also try an English/Arabic headed script and TXT/Markdown file.
2. **AutoCut:** Choose a scene containing at least two pictures. Place two ordinary markers inside the selected scene using Marker, then choose Timeline markers in AutoCut. You can also add music and beat markers using ♪ Beats, or select a music source in AutoCut. Preview, apply and render the scene. Pictures should change at the listed times; narration and scene length should stay intact. Close, Undo and Redo; save/reopen.
3. **Stabilization:** Select a scene containing handheld video. Apply movement range 50, close and render. Compare with stabilization turned off. Export a short video to confirm the same result. Try Undo/Redo. This targets small camera movements, not heavy blur or fast pans.
4. **Templates:** Save a project as a template. Return to Projects, use it to create a new project. Edit its text and verify the original stays unchanged. Save/reopen; media and effects should remain. Delete a template and verify already-created projects remain.
5. Briefly recheck image/Text Box insertion and the formerly failing caption render.

Windows validation belongs to the owner; it has not been performed in this Linux environment. Sections E and F remain pending.
