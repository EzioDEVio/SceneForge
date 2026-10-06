# SceneForge 0.9.3 — Stage 6 release readiness

Historical source review, October 5, 2026. The owner subsequently approved a combined source checkpoint and the current owner fixes, including mouse box selection. See BUILD_INFO.json and docs/COMBINED_BUILD_VALIDATION.md for the packaged build results. No Windows installer, GitHub push, tag or publication has been performed.

## Recovery and owner review

The owner supplied Stage 1–5 completion HTML files and SceneForge-Visual-Review.html. The previous Stage 5 source commit was unavailable; reconstruction started from local commit `45ce055`. These changes implement the reports' main workflows as a fresh source recovery. They are not an exact restoration of the lost commits or every historical validation claim. Stages 1–5 owner sign-offs are **HTML reviews**, not Windows test results. Local recovery checkpoint: `f496fb6`; the final source checkpoint is recorded in the accompanying HTML review.

## Combined changes

1. Timeline toolbar wrapping, theme and keyboard menu access.
2. Atomic Motion/Effects drafts, isolated real-render preview, Apply/Cancel, preview retry/stop, Undo/Redo and revision-conflict protection. Apply or Cancel before leaving with a pending draft. Timeline layer placement previews retain their own existing Apply workflow.
3. Inspector section navigation and scope labels; a fixed Text preview action; all existing tabs retained, with Clip Audio available for video.
4. Shared Twemoji plane, ship, car and pin artwork; a destination preview; four additional camera movements; centered zoom correction. This reuses the existing licensed artwork rather than recreating the lost Stage 4 icon assets.
5. Script import opens the first added scene; existing scenes remain; optional setup retains local-provider controls. AutoCut previews source thumbnails and cut times. Project FPS and effective GIF dimensions/rate are disclosed. No paid generation was used.
6. Version alignment to 0.9.3, offline source/tag drift checks, draft-release asset checks, and a read-only ZIP gate for the later approved package. ZIP validation tests use synthetic fixtures, not a newly built product archive.

## Fresh validation

| Check | Result | Scope |
|---|---|---|
| TypeScript source check | Passed | No production frontend build |
| Frontend test command | Passed | 334 editor component assertions; remaining unit/component harnesses also passed; mock API |
| Browser harnesses | Passed | release093, timeline_layers, story_tools, combined_tools, recovered_stages; real disposable API + Chromium + Vite development server |
| Story tools integration | Passed | 35 checks; actual AutoCut/stabilization rendering and template/import data |
| Editor draft integration | Passed | Four groups: isolated render parity, atomic rollback/stale revision, exact style restoration, shared artwork/new motion plans |
| Centered zoom regression | Passed | 12 FFmpeg renders across three zooms and four easing curves |
| Full-resolution finishing | Passed | 29 checks; timing, ducking, loudness, projector audio, independent audio placement, track mute and solo |
| Desktop lifecycle unit tests | Passed | 18 checks; no packaged Electron/Windows run |
| Offline release checks | Passed | 31 unittest methods, including parameterized cases |
| Follow-subject/GPU regression | 62 assertions reported passed; completion unverified | Automatic approval review blocked the final process check because of an unrelated Microsoft telemetry request with unknown payload. No telemetry approval was granted. Actual NVIDIA hardware unavailable. |
| Native credential vault | Pending | Requires platform service; no secrets read |
| Windows source launch and installer | Pending owner/platform validation | HTML reviews do not satisfy this gate |
| Production build/package | Owner approved | Current results in BUILD_INFO.json and docs/COMBINED_BUILD_VALIDATION.md |
| GitHub publication | Pending owner instruction | No push, tag or release publication |

The fresh runtime required installing Python dependencies locally; dependency manifests were not rewritten to match the temporary environment. Validation here is Linux source validation, not proof of a clean Windows dependency install or a native vault session. The old full-resolution test's five-minute timeout was not reused: finishing was allowed to complete at its original resolution.

## Windows test sequence after an approved package is created

The latest owner-provided checkpoint path is:
`C:\Users\moham\Downloads\Claude_sceneforge\HAND OVER FROM  CLAUDE TO CHATGPT\SceneForge-0.9.3-C-checkpoint`

This names the existing owner checkpoint, not a new package root. New extraction instructions must use the actual approved package path once it exists. Source setup requires Python 3.12, Node 22.12+ and FFmpeg on PATH.

1. Launch the approved combined source build. Confirm About/settings identify 0.9.3. Open a disposable project and check Media, Motion, Effects, Overlays, Text, Audio and Clip Audio. Check dark, light, midnight and warm themes at a laptop-sized window; use section Go and keyboard focus.
2. In Motion and Effects, change several settings. Confirm the saved scene stays unchanged until Apply. Render the draft, minimize/restore/close preview, Cancel, then repeat and Apply. Test Undo/Redo, refresh, stopping/retrying a preview, and moving to another scene after Apply/Cancel.
3. On the timeline, add video above video, plus image, Text Box and Text+. Move, trim, change track, preview placement, Apply and Undo/Redo. Verify caption numbers and all toolbar targets stay readable and clickable.
4. Try the four route icons on straight, turning and reversed routes. Compare destination preview with scene render. Test new camera movements and centered zooms on both still images and video.
5. Import two English/Arabic paragraphs and a headed TXT/Markdown file. Edit one narration before Add. Confirm the first new scene opens, originals remain and batch Undo/Redo works. Test optional setup only with owner-selected available local engines; plain import does not generate narration by itself.
6. AutoCut a scene with two pictures using timeline markers or music beats. Inspect thumbnails, scrub times, Apply and render. Narration and duration should remain. Stabilize a handheld clip, compare off/on, export and Undo/Redo. Create, edit, reopen and delete a template without affecting its source or already-created project.
7. Browse/search caption emoji, edit a censor range, confirm audible bleep or mute, then save/reopen. Recheck the formerly failing image/text/caption render. Review export FPS and GIF size/rate; empty scenes should be disclosed before skipping.
8. Installer gate: install/launch, packaged assets and FFmpeg, native credential storage/migration, real export, uninstall/reinstall and update behavior. Hardware GPU checks need the actual supported hardware. Release draft must contain every required nonempty installer/update file for the matching tag.

## Owner approval boundary

`docs/HANDOFF_TO_CHATGPT.md`, section 1: **“Ask for the owner’s OK before creating another update build or checkpoint ZIP.”** Prepare and review source first. Approval to package is separate from authorization to publish GitHub or to claim Windows validation. Preserve the existing draft-release file gate and all render assertions.
