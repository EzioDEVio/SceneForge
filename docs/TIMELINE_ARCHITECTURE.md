# Timeline architecture (timeline v1)

This describes the timeline as of 0.7.0 RC5. It adds independent audio tracks, edit tools, and project-saved markers and track state. The scene-based picture model it was built on is kept.

## Lanes

| Track | Holds | Model | Stored in |
|---|---|---|---|
| T1 | Captions, caption segments, Text/Text+/Text Box layers | Per scene | `scene.font_json` |
| V1 | Scene picture (one or more shots) | Scene sequence, transitions overlap | `scene`, `shot` rows |
| A1 | Accepted narration take | Per scene | `voice_take` rows |
| A2 | Embedded source-video sound | Per shot | `shot.audio_json` |
| A3–A8 | Timeline audio clips | Independent clips at sequence time | `project.finishing_json.audio_clips[]` |
| Music bed | Whole-project music with ducking | Project | `project.finishing_json.music` |

Picture editing still happens scene by scene on V1. Free clip-based video on arbitrary tracks and multitrack compositing are **not** part of timeline v1.

## Persistence and migration

`project.finishing_json` gains two additive fields:

- `audio_clips[].track`: `"A4"`–`"A8"`. A3 stays implicit (the key is left out), so a clip without `track` is on A3, which is its pre-v1 meaning.
- `timeline`: `{version: 1, tracks, audio_tracks, markers}`
  - `tracks`: `{T1|V1|A1|A2: {locked}, A3–A8: {locked, mute, solo}}`. Only `true` values are stored.
  - `audio_tracks`: audio tracks shown even when empty. A3 is always included, and any track holding a clip is always shown.
  - `markers`: `{id, time_ms, duration_ms, label, color}`. `duration_ms > 0` makes a range marker. The colours are amber, red, green, blue and purple. Up to 200 markers are allowed.

The migration is **forward**: `normalizeTimeline()` (frontend, `src/timeline/timeline.types.ts`) turns a missing or older value into v1.

- Older builds kept markers and T1/V1/A1/A2/A3 locks in browser `localStorage`. That data is read as a fallback only while the project has no `timeline` key. It moves into the project on the next timeline save.
- Legacy markers use `{time, label}`; these become `time_ms`, with the default colour.

The migration is **reversible**:

- `downgradeTimeline()` strips `track` from clips.
- An older build ignores the `timeline` key on read. Its validator would reject the key on a later write of finishing settings, though. To open a v1 project in an older build, remove `timeline` and any `track` fields first. Clips on A4–A8 then play on A3.

The backend validator is `clean_timeline()` in `backend/app/render/finishing.py`. It checks track names, which states each track type allows, marker bounds and colours. It rejects timeline versions newer than it knows, so a future format is never silently truncated.

## Audibility (export)

`audible_clips()` in `finishing.py` decides which timeline audio clips are heard:

1. A clip that is muted is not heard.
2. A clip on a muted track is not heard.
3. If any track A3–A8 is soloed, only clips on soloed tracks are heard.

Solo applies among timeline audio tracks only. Scene narration (A1), clip sound (A2) and the music bed are not affected. The track-header tooltip says so.

The editor mirrors this rule with `isAudioTrackAudible()`: tracks that are not heard are dimmed and labelled "Muted" or "Not soloed".

## Code map

| File | Role |
|---|---|
| `src/timeline/timeline.types.ts` | Types, constants, `normalizeTimeline`, `downgradeTimeline`, `clipTrack`, `isAudioTrackAudible`, tool keys |
| `src/timeline/timeMath.ts` | `timeTransform` (ms↔px), `frameMs`/`toFrame`, `zoomAround` (Ctrl+wheel zooms around the pointer), `visibleWindow`/`intersectsWindow` (virtualization), `rafCoalesce` (one pointer update per animation frame) |
| `src/timeline/editOps.ts` | Pure edit operations: `blade`, `bladeAll` (Razor All), `moveClips` (with track change), `trim`, `rippleTrim`, `rippleDelete`, `roll`, `slip`, `slide`, `trackSelectForward`, `packRows`, `clampFades` |
| `src/ProjectTimeline.tsx` | The timeline surface. It uses the modules above; there is no second store. |
| `src/App.tsx` | `updateProjectAudioClips` and `updateTimelineSettings` write `finishing_json` through the existing undo/redo `record()` history |

Every edit is computed by a pure function over the clip array. The drag preview and the saved result use the same function, so what the user sees while dragging is exactly what is saved. Operations never mutate their input. When a clip's length changes, its fades are clamped to the new length.

## Tools

The tools apply to timeline audio clips on A3–A8. Scenes on V1 keep their existing reorder, edge-trim, scissors and ripple-delete tools.

| Key | Tool | Gesture |
|---|---|---|
| V | Select | Drag to move. Drag up or down to change track. Ctrl+click adds to the selection, and dragging a selected clip moves the whole selection. |
| A | Track select forward | Pressing a clip selects it and every later clip on that track; dragging moves them together. |
| B | Ripple trim | Dragging an edge also moves later clips on the track, so no gap or overlap forms. |
| N | Roll | Dragging the edge shared by two touching clips moves the edit point. Total length does not change. |
| Y | Slip | Changes which part of the source plays. Position and length stay fixed. |
| U | Slide | Moves a clip between touching neighbours; the neighbours absorb the change. |
| C | Blade | Click to cut at the pointer. Shift+click, Shift+C or Shift+scissors cuts every unlocked audio track (Razor All). |

- Delete removes the focused clip or selection. Shift+Delete ripple-deletes it.
- A tool reaches the limits of the available media or the 100 ms minimum clip length, and the reason is reported. It never fails silently.
- Locked tracks ignore gestures, drops and Razor All.

## Undo and state rules

- Marker changes and track mute/solo are undoable timeline edits.
- Locks and showing or hiding tracks are view state. They are saved with the project but are not put on the undo stack.

## Performance

- Audio clips outside the scrolled viewport (plus 400 px of overscan) are not rendered. The selected clip is always rendered.
- Pointer moves are coalesced to one preview update per animation frame.
- Measured in Node on the development container (not a Windows UI measurement):

| Operation | 64 clips | 1,000 clips |
|---|---|---|
| Blade | ~21 µs | ~29 µs |
| Razor All | ~14 µs | ~55 µs |
| Ripple trim | ~31 µs | ~65 µs |
| Slide | ~16 µs | ~55 µs |
| Lane packing | ~16 µs | ~70 µs |

With 1,000 clips at 55 px/s in a 1,600 px view, 45 of 1,000 clips are rendered. The backend still limits a project to 64 timeline audio clips.

## Not yet implemented (roadmap)

These wait until their full workflows (UI, persistence, export and tests) can land together:

- Clip-attached markers
- Gain envelopes and keyframes
- Compound/nested clips
- A1/A2/music-bed solo
- Free multitrack video
