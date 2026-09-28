# SceneForge 0.6.0 WIP — source comparison and review

## Sources reviewed

Compared the supplied 0.5.3 released source with the original 0.6.0 WIP and both reviewed WIP archives (wip.2 and wip.3). Read the README and technical handoff included in the archives, the supplied 0.6.0 test plan and follow-up user feedback. The included technical handoff is an older RC4 document; it predates the 0.5.3 and 0.6.0 changes.

## Feature baseline

The 0.6.0 work builds on the released editor: video sound/duration fixes; Windows-compatible MP4 output; render/export progress; 42 transitions with live preview; batch selection/application; captions from speech; expanded caption styles; export presets and advanced settings; multi-format exports and subtitle files. WIP documentation also records local Faster-Whisper captions, auto-closing/collapsible multi-select controls, script/export UI updates, and local install requirements.

The source comparison found the three library tabs — Scenes, Media Pool, and Transitions — in the 0.5.3 and all supplied WIP variants. The user-provided 0.5.3 screenshot also shows the AI Engines top-level menu. It was missing from the reviewed wip.4 build and is restored here, with Help/About. The redundant AI Engines library tab has been removed; the original top-level AI Engines menu remains.

## Changes in this reviewed source snapshot

- Add/delete scene, title card, media insertion, narration attach/remove, scene order, source clip sound, and scene split operations participate in undo/redo. History retains up to 100 operations per editing session.
- Scene splits preserve source clip audio and speed settings; undo restores the original scene and clip IDs. Baked complex splits display an undo-aware confirmation.
- Source-video audio has a separate A2 lane with one block per video shot. Selecting a block routes to a distinct Clip Audio inspector tab (volume, mute, and narration ducking), separate from Motion.
- Whole scene blocks can be dragged to reorder. Media dropped at scene edges or timeline space is inserted before/after as indicated.
- Restore the original AI Engines top-level menu and Help/About; remove only the duplicate library AI Engines entry; retain Scenes, Media Pool, Transitions, and toolbar provider settings.
- Frontend/backend build IDs and desktop package versions are aligned at `v0.6.0-wip.10` / `0.6.0-wip.10`.
- Export completion opens a local-first Share dialog with Download, open export location in desktop mode, browser/device share fallback, and platform-specific posting steps. Direct uploading is deliberately not represented as available.
- Timeline ruler snapping targets scene edges and named per-project markers. Trimming is supported for a single video in a non-fixed, narration-free scene; source sound uses the same trimmed range. Existing scene deletion closes the sequence gap.
- Added searchable categorized emoji/sticker choices in Overlays. Symbols become standard image overlay assets and use existing transforms, animations and render paths.
- Added three distinct renderable filter presets: Teal & Amber, Pastel and Bleach Bypass.
- Added Text, Text Box and Text+ title tools with timed, labeled T1 timeline clips; clicking a clip opens the Text inspector and focuses its editable text. Text Box has adjustable wrap width. Text+ is a SceneForge styled/animated title tool, not full Fusion parity.
- Added click-open feature guidance across Media, Motion, Effects, Overlays, Text, Audio and Clip Audio, plus major feature sections. Marker help describes markers as named timeline bookmarks.
- Auto captions now produce independently editable, timed phrase clips on T1; clip wording and boundaries can be edited, phrases split or removed, and caption style continues to apply across the set.
- Feature-help popovers render in a viewport-level portal and scroll within viewport bounds rather than clipping inside the inspector.
- Timed captions/titles use a T1 lane above V1; the caption editor supports transcript search, previous/next navigation, active-segment focus, collapse/expand, and per-scene Auto/RTL/LTR direction.

## Verification status (wip.9 historical baseline)

- Frontend production build passed.
- Frontend tests passed: 185 component checks, 19 unit checks, and 6 Share dialog checks (mock APIs/jsdom; not browser visual QA).
- Individually timed caption rendering smoke test passed; `git diff --check` passed.
- Python `compileall` passed.
- Backend integration tests could not start in this workspace because FastAPI is not installed (`ModuleNotFoundError`). Previous wip.7 integration results remain recorded below as prior baseline evidence, not wip.9 verification.

The tests do not call real cloud caption APIs or exercise a first-run Faster-Whisper model download/inference. Windows Photos/Media Player and clean-machine installer behavior still need Windows verification. This archive is a source snapshot rather than an installer.

The checks above describe wip.9 only. Current wip.10 verification follows below.

## Screenshot-driven regressions repaired in wip.5
The supplied screenshots showed that the AI Engines top-level menu from the original UI had disappeared, clip sound controls were mixed into Motion, and video crop/focal maps showed broken image placeholders. This build restores the AI Engines menu and Help/About, separates source clip controls under Clip Audio, routes A2 blocks there, and uses generated poster thumbnails with a nonbroken fallback. Crop/focal edits save on release/commit.

## wip.6 screenshot follow-up
The new sound-panel screenshot showed that mute, volume, and voice ducking were present but clip fades were missing; wip.6 adds fade-in and fade-out controls and render filters, and the split/undo integration test verifies the fade settings persist. The auto-caption screenshot showed a crowded two-column card in a narrow inspector; wip.6 stacks those controls until the inspector is wide enough for two columns.

## wip.9 follow-up
Adds a post-export sharing workflow, snapping and named markers, constrained video edge trimming with linked source sound, 48 searchable emoji/sticker assets and three additional filters. These are source-level tests; the share destinations, download behavior and trim handles still need manual visual/browser acceptance. Full audio unlinking and track lock/mute/solo remain outstanding because the scene-based timeline and renderer do not yet have a generalized track-state model. Direct social API posting is also not included.

## wip.10 follow-up

- Moved the T1 captions/titles lane above V1 and added transcript search, segment navigation, collapse/expand, and Auto/RTL/LTR caption direction.
- Frontend production build passed; frontend checks passed (191 component, 19 unit, 6 share-dialog checks), as did 14 desktop tests, Python compile checks, and the RTL/LTR caption-render smoke test. Full counts and commands are in `handoff.md`.
- The full backend integration suite could not start locally because FastAPI is absent. The push-triggered GitHub checks workflow installs the required dependencies; its result is reported after the run completes.
- Branch-dispatched installers are test artifacts. This work does not tag or publish a stable GitHub release.
