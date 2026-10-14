# SceneForge — emoji catalogue, route tools and access review

Prepared after the owner's October 4 UI/accessibility feedback. The previous preview/censor checkpoint remains the delivered build. No production build or checkpoint ZIP has been created for this review; a new owner OK is required.

## Changes

- Caption cards offer all 322 bundled Twemoji choices, replacing the earlier eight-choice limit. The existing selection and left/right side remain. Browse opens colour thumbnails, name/symbol search and a category filter, with selected-state/focus feedback and removal. Original-file artwork renders with caption timing. This is the bundled catalogue, not every Unicode emoji. The 64 emoji-caption and typewriter limits remain.
- Effects has direct shortcuts for Vignette/Bars/Sharpen, Map route, Split screen/privacy and Stack/presets. Shortcuts expand and scroll to the relevant group. The existing effect search now also includes additional effect groups and expands matches. Existing image looks and other controls remain available.
- Map routes gain Flight, Road trip, Sea journey and Historical march appearance presets. They preserve stops, labels and timing. Add stop places a centre stop; stop coordinates can be edited numerically. Reverse journey reverses stops with their attached labels. Individual removal preserves at least two stops. Preview stops support Tab, arrows, Shift for larger movement and Delete/Backspace. Route edits share timeline Undo/Redo history. Editing handles belong to Effects; animated icons/curves/labels need a render. The user supplies a map image; no map download or geocoding occurs.
- Overlay selection and its controls precede layout and sticker browsing. Section shortcuts focus Position/Frame/Move/Timing/Loop controls. Narrow panels use one column with readable labels, larger action targets and visible focus. The caption emoji browser has readable dark/light styling.
- Fixed effect-control synchronization so an older save response cannot overwrite newer local values; external saved changes still synchronize after acknowledgement.

## Verification

- TypeScript, focused emoji/route/effects access controls and inspector feedback passed. The existing component editor suite passed 334 checks (mock API).
- 39 real API/FFmpeg checks passed, including complete bundled emoji support/artwork, invalid emoji rejection, timed rendering, censoring, detached sound and finishing effects.
- Existing real Batch B/C render suite passed 36 checks, including route functionality.
- Frontend/backend emoji catalogues match. Source whitespace checks passed.
- Chromium with the development frontend checks full emoji search/selection, effect search/shortcuts, route presets/coordinates/reversal/keyboard movement/deletion, route Undo/Redo, overlay shortcut focus, narrow layout, settings reopening and caption action contrast in the light theme. Existing combined flows remain exercised.

No Windows validation, production build, provider calls, push, merge, tag or publication. Sections E/F remain pending and product versions are unchanged.

## Owner checks after an approved build

1. Open a generated caption card, Browse emoji, search a face or symbol and change category. Pick an emoji beyond the original eight, choose side, render, remove, save/reopen. Try Arabic and wrapped captions.
2. Effects: use Vignette/Bars/Sharpen shortcut; vary each amount and render. Search Sharpen and Map route; clear search and check other groups remain available.
3. Add your map in Media. Enable Map route, choose a preset, name stops, edit coordinates, reverse, add/remove. Edit preview points with keyboard and mouse, Undo/Redo, save/reopen and render. Labels stay attached during reversal/removal.
4. Select an overlay. Use each section shortcut, change sliders, check narrow/wide panels and dark/light themes. Check the layout/sticker catalogue remains usable below the selected controls.
5. Briefly recheck stacked video, Text Box, caption rendering and Bleep/Mute audio.
