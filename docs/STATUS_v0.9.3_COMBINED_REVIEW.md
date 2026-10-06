# SceneForge 0.9.3 — Combined review adjustments

Prepared on October 4, 2026, on `claude/0.9.3`. No production build or checkpoint ZIP has been created for these changes. The owner requested approval before packaging. This update includes the earlier C/D work, AutoCut ordinary-marker support, grouped speed controls and overlay save feedback; the owner need not install the preceding AutoCut checkpoint first.

## Prepared changes

- Video stacking on O1–O6: actual moving video above existing picture clips, independent timing and placement, source start, source-aware trim/split, volume and mute. New layers start muted. Playback shows the stack; full-video export composites and mixes it. Skipping empty scenes advances the video source correctly. Base scenes remain intact.
- Audio: grouped trim/listening, levels/fades and voice cleanup; listening speed and original-file audition; narration mute with volume restoration; cleanup presets. Music and finishing now groups the bed, timeline clips and loudness, with mix presets, exact clip start, soft fades and duplicate onto the next audio track. Timeline audio changes use the shared Undo history.
- Optional Script → Scenes setup: selected Media Pool pictures/videos or connected local Stable Diffusion; local narration; estimated script caption boxes or installed local Whisper transcription; caption styles, image motion and optional rendering. Default import remains available. English/Arabic scenes remain editable, setup errors preserve imported scenes, and Redo restores final snapshots without generating again. Stopping finishes the current step; active rendering is cancelled and awaited.
- Light-theme button contrast and plain help for the new controls. Save feedback returns to Apply changes after another edit and preserves failed drafts for retry.

## Completed verification

- TypeScript check and all frontend suites, including delayed-save/retry and script setup orchestration.
- Real API/FFmpeg: 31 existing timeline layer checks, 20 new video layer checks, 26 audio edit checks and the story tools suite.
- Chromium: existing timeline layers and story tools suites, plus combined video stacking, source seeking, placement, duplication/Undo/Redo, audio controls, music presets, English/Arabic setup, caption style and batch Undo/Redo. No browser errors in these workflows.
- Visual review in dark and light themes; enabled Audio preset button contrast checked after theme transitions finish.

No Windows validation is claimed. Connected local image/voice engines and installed Whisper transcription were tested through request-contract fixtures, not real model generation. No paid generation calls were made. Production packaging awaits approval; Sections E and F are not claimed complete. Product versions remain unchanged.

## Owner checks after the approved combined build

1. Open an existing project. Stack a video on an upper Overlay track; move, trim, change source start and duplicate it. Compare playback with a short full-video export, including unmuted sound. Undo/Redo, save and reopen.
2. In Audio, preview original/trimmed sound, try mute and cleanup presets, then render. Try music presets and duplicate a timeline audio clip; change its start and fades, Undo/Redo and reopen.
3. Import English/Arabic paragraphs with optional setup off, then with selected Media Pool pictures, motion and estimated captions. Verify existing scenes remain and the new scenes open normally. Undo/Redo the batch.
4. With your local engines already installed, try narration/image generation and local transcription; check a failed or stopped setup leaves editable scenes. Review estimated caption timing manually.
5. Recheck AutoCut with ordinary markers, speed controls, overlay Apply/Saved/edit feedback, templates, stabilization, text/image insertion and the formerly failing caption scene render.
