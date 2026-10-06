# Owner testing follow-up — SceneForge 0.9.3

Prepared October 6, 2026, from the exact Friendly AI Setup checkpoint (`c7d1f4a6cd28e8d5bc4aa236e3c26f50c0b89276`). No new checkpoint ZIP, installer, push, tag or publication has been created.

## Font request rejection

The reported `string_pattern_mismatch` came from `TextLayer.family`, whose request validator still listed the original ten families. Renderer and UI catalogues had nineteen. The schema and renderer now share the bundled catalogue; unknown names remain rejected.

Validation: all 19 families passed real `/api/title-preview` video renders and scene-font save requests, including mixed English/Arabic. Earlier font tests exercised the layer-image renderer and did not cover this request path; the new regression is in regular CI.

## Video inside text preview

The existing coloured title illustration was a layout guide. A new Preview button renders the actual selected scene with the unsaved knockout title in the companion pane. Settings changes mark the result outdated. Close keeps the entered settings. Add applies the title separately; optional AI subject cutout runs on Add and is explicitly excluded from this preview.

The snapshot and Apply share exactly the same overlay configuration, including zero card border, radius and shadow. A pixel-level regression verifies the colour card and source media visible through transparent letters. Preview dependency assets are hidden from the Media Pool. The saved scene, including revision and overlays, stays unchanged.

Validation: real renderer job, streamed MP4, colour/transparent-hole pixel checks, saved-state equality, and Chromium preview/Close/outdated-settings checks. Screenshot: `docs/qa/owner-knockout-preview.png`.

## Free timeline splits and source view

The old split eligibility check used the unrounded playhead, while splitting used a frame-rounded position. Near an edge that could pass the first check and save no actual cut. One integer frame-aligned position now controls both. Successful cuts select the right pieces for subsequent cuts. With no selection, Split cuts all eligible clips at that position; an existing selection limits the affected clips. Minimum piece length remains 0.1 seconds. No render or clip relocation is required to split.

Splits preserve source offsets, audio fades/censor data and original source scenes. Save operations have an immediate in-flight guard; a plain click does not start a move save. Seeking stops timeline playback before placing a cut.

Scene assembly displays the original source scenes, so it is expected to show full sources. Previously entering that view also disabled Free timeline export. Viewing sources now preserves the edited Free timeline and its active export mode, with a clear banner. The separate Use Scene assembly for export button retains the earlier export choice without deleting free excerpts. Returning to Free timeline restores the edits.

Validation: 24/25/30/50/60 fps unit checks; frame-edge rejection; repeated cuts; real browser mouse placement/range cuts/audio movement; three consecutive playhead cuts; exact Undo/Redo; source-view and explicit export-mode round trips. Existing real Free timeline export regression passes for excerpt timing, track ordering, gaps, overlapping audio and caption timing.

## Local AI setup follow-up

The screenshot shows Chatterbox model loading failed, but does not include its underlying engine error. The exact original cause is not established. Setup now includes the health-reported model error and retries one temporary download/connection failure using cached files. Out-of-memory, permission and other non-transient failures remain visible without automatic repetition. Chatterbox logs the warmup traceback.

The delivered source checkpoint is not a Windows Setup EXE. Running its scripts does not show the NSIS installation wizard. The native installer source includes the component-selection/terms page; an actual newly built Windows EXE must be tested to establish that page and its downloads work. The successful second in-app attempt is owner-reported Windows evidence, not a native installer acceptance result.

Validation: mocked setup contracts pass, including ordered completion, cached retry, existing connections, platform/space/port checks, autostart and close guards, one transient retry, and non-transient error retention. No new model download, GPU inference, paid provider call or Windows installer test was performed here.

## Additional checks

- Production frontend compile passes.
- Full frontend test command (14 scripts) passes.
- Focused production Chromium title/preview and Free timeline harnesses pass.
- Python compile and whitespace checks pass.

## Windows retest after the next approved package

1. Close the old backend before launching the updated copy; refresh the browser. In Add title card choose DejaVu Serif and each Latin Modern family, play the rendered preview, then create a card. Try a Text Box with those families too.
2. Overlays → Video inside text: enter a title, choose Preview video inside text, play it, change a setting and render again. Close it and verify nothing was added; then Add the title and render the saved scene.
3. Free timeline: select a clip, place the playhead inside it and Split. Move the playhead farther along the selected right piece and repeat. Undo/Redo, save/reopen and render a short export. No movement away from neighbouring clips is required.
4. Open Scene assembly: its banner must say original sources; switch back and verify every cut remains. Test Use Scene assembly for export only when the original assembly is the desired output; switch back to Free timeline for edited output.
5. Native installer: test the newly generated Setup EXE on Windows, select components and accept their terms, observe downloads, and verify successful engine startup after reopening. Capture the expanded setup log or diagnostic ZIP if Chatterbox fails again.
