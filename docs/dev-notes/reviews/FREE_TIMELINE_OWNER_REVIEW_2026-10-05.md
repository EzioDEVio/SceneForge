# Free timeline and owner findings — October 5, 2026

Baseline: approved Owner-Fixes checkpoint source commit `20ad403`.
This is source preparation and a browser development preview. No new production
frontend build, checkpoint ZIP, installer or GitHub publication was made.

## Timeline behavior

Choose **Free timeline · move clips anywhere**. Existing media-bearing scenes
become source clips at their authored times. Place complete scenes or excerpts
on six picture tracks; drop raw images/video/text on those same tracks and sound
on A3–A8. Drag clips into empty time or between compatible tracks. Box selection
can move mixed scene/layer/audio selections in one undo step. Track bounds and
non-negative timing are enforced. Scroll and zoom use content coordinates.

**Highlight range** uses the mouse rectangle's time bounds and intersected clips.
**Split highlighted range** creates source excerpts on both sides and selects the
middle segments. Split at playhead, Remove, Undo/Redo, save/reopen, snap, maximize,
source-scene addition and independent Text box placement work. Double-click opens
source scene or existing layer/audio controls. Source scene rows stay intact.

Source scenes remain linked: their images, captions, effects and narration are
rendered together and edited in the source scene. A range cut preserves that
composition. This pass does not automatically unpack all scene-internal elements
into independently movable objects. Standalone picture/text/audio clips are
independent timeline objects. Picture tracks and audio tracks remain compatible
families; selected groups preserve their track offsets within each family.

Switching back to Scene assembly retains both the old ordering and saved free
placements. The active mode decides export assembly. Free clips use hard cuts /
track stacking; old sequence boundary transitions remain in Scene assembly.
No free-mode per-track lock/mute UI is added in this pass; source and finishing
settings remain available in their original controls.

## Export and preview

The free compositor renders exact starts, gaps, overlaps and excerpt in-points.
Scenes and standalone picture/text clips share track order (Track 1 above 6).
All present sound streams mix, including sound in lower picture tracks. Gaps
are black and silent unless project audio/music plays there. Independent media
can export with zero scene blocks. Project audio/music and finishing run after
composition. Caption download times follow placed source excerpts.

The free monitor uses rendered source scenes and timed independent media. Render
changed sources to see their exact motion/effects/captions. Timeline audio fades,
censoring, gain and project music need full rendering to audition exactly.
Changing a source to be shorter than a placed excerpt produces an explicit export
error; shorten that excerpt. Templates/restore points remap source IDs correctly.

## Route and narration findings

- Every named route stop is readable from the beginning, then reaches full
  emphasis as the journey arrives. Exactly three stops can show Paris/London/Tokyo;
  no extra unlabeled destination is required. Forward and reversed endpoint labels
  work for all six marker choices, including long/Arabic edge labels.
- Ship uses an original side-view SVG/PNG asset; car/ship keep their upright profile
  and mirror by direction rather than rotating upside down. Plane follows heading;
  pin stays upright. Editor and renderer use the same artwork and poses. Route
  caches and renderer version are invalidated. Original ship sticker remains.
- Narration engine dropdown lists Kokoro, Chatterbox and ElevenLabs even when
  unconfigured, with disabled setup labels. **Refresh narration engines** reloads
  saved profiles without paid provider calls. Configured engines keep voice
  selection; explicit ElevenLabs batch consent remains mandatory. Showing a name
  does not install/start a service or provide an API key.

## Validation

Passed: TypeScript source check; full frontend command (334 component checks plus
unit/timeline/keyframe/setup/accessibility suites); focused free range/group tests;
real Chromium free-timeline harness; owner-fixes browser harness; route FFmpeg
checks for six markers forward/reverse; free-compositor API/real-export checks,
including no-scene export, shared stack order, mixed sound, caption offsets and
independent template source IDs; version alignment and whitespace checks.

Free browser fixtures use actual uploaded pictures, video and WAV sound, no model
or paid generation. QA uses temporary Linux Python dependencies and Chromium.
Windows validation is pending. Browser review is development source validation,
not evidence that the previously delivered ZIP contains these changes.

## Build approval

`docs/HANDOFF_TO_CHATGPT.md`, section 1: **“Ask for the owner’s OK before creating
another update build or checkpoint ZIP.”** The previous approved ZIP has already
been delivered. Review these prepared source changes before authorizing a new
combined update build. GitHub push/tag/publication needs separate approval.
