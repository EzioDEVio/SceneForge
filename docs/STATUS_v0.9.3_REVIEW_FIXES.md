# SceneForge 0.9.3 — Windows review fixes (unreleased)

Owner verification: Mohammed reported **ALL CHECKS PASSED** on Windows on October 3, 2026, after the review-fixes checklist.

Continues section C commit `6655a9d778bef756348278a82c4bed5b494b4834` on `claude/0.9.3`. The owner reported image insertion and Text box insertion passed on Windows, then supplied five screenshots and a diagnostics archive. All earlier A–B, overlay and release-gate work is retained.

## Changes from the review

- **Caption render failure:** all four recorded failed jobs stopped at the libass caption filter. Their subtitle filenames were 279 characters long. The caption subprocess now reads a short filename from its own temporary folder outside the deep project-data tree. The original generated ASS stays beside the render job for diagnostics; its temporary copy is cleaned after rendering or cancellation. This avoids handing libass a long absolute Windows filename or a relative filename that still resolves inside the deep project tree, and also keeps data-folder apostrophes out of the filter argument. The parent process's working directory is never changed, so concurrent jobs remain isolated. This is a targeted fix based on the diagnostics; the owner's failing scene still needs a Windows retest.
- **Darker beige captions:** use muted beige cards and darker text for the caption numbers, Split/Delete actions and timing fields. Generated caption boxes on the timeline use the same darker family. Dark and light themes are covered by contrast checks.
- **Sliders:** image/text placement, width, rotation, opacity, start, length and text size now have sliders alongside exact number entry. Existing font, colour, alignment and track controls remain.
- **Preview before Apply:** the inspector shows the pending image/text on a sample frame using the same text raster as export. Position, size, rotation and opacity update locally; text raster requests are debounced. Apply changes saves one undoable edit. The preview is a sample frame, not a composite of the current footage; the main monitor and full export keep their existing behaviour.
- **Styled text cards:** both groups have coloured visual samples. **Whole-video tracks** add freely timed clips that can cross scenes. **Scene titles & labels** retain the existing within-scene animation/keyframe tools. Their purpose is now stated beside each group. No tools were removed or redirected.

## Retest on Windows

1. Open the scene that failed and click **Render scene**. Keep its existing captions, image and text; there is no need to recreate the project. If it still fails, collect a new diagnostics archive.
2. Open caption clips and confirm the numbered headers, Split and Delete are legible in your theme.
3. Select an image or text clip. Move a slider or type an exact value. Check the preview before clicking **Apply changes**. Then Apply, Undo and Redo.
4. Check that the two text-card groups are clear. Use a whole-video clip for free placement; use scene titles for animated titles inside a scene.
5. **Export video** and check image/text timing and placement. Independent whole-video overlays are composited in full export; a downloaded individual scene retains its scene-local layers.

## Validation

- TypeScript/Vite production build and all six frontend suites pass (334 component checks, 21 units, 48 timeline checks, two fixture video-generation workflows, six share-dialog checks and 27 keyframe/playback unit checks). The existing large-chunk advisory remains.
- Both A–B and overlay browser suites pass against real Linux Chromium 153 and a disposable FastAPI backend. Added checks cover image/text draft previews, local changes before Apply, sliders/exact inputs, retained scene-title cards and caption header/action contrast above 4.5:1 in both themes.
- 31 real API/FFmpeg independent-overlay checks pass, including timed image/text export pixels, Arabic text, track ordering and restore points.
- The new deep-path regression renders real captions and a scene title in two simultaneous jobs from paths longer than 279 characters containing apostrophes. Output pixel checks confirm both caption and title are visible; global cwd remains unchanged. Staged input paths are shorter than 260 characters and their copies are cleaned after success and real FFmpeg cancellation.
- The existing two caption-segment rendering checks pass.
- 40 existing keyframe/playback checks and 29 real export-finishing checks pass, including music ducking, measured loudness and timeline audio mute/solo.
- The 23 offline section C release-verifier tests pass.
- The Windows failure itself cannot be reproduced on this Linux host. No Windows UI or installer test is claimed, and no cloud providers or models were called.

Sections D–F and the earlier legacy browser-suite failures remain outstanding. Product versions are intentionally unchanged. No push, merge into main, tag or publication was performed.

Technical reference: [Microsoft path limits](https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation). Short temporary caption inputs avoid relying on long-path support in the bundled libass build.
