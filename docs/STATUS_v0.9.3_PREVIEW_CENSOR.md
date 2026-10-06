# SceneForge — companion preview, caption emoji and voice censoring

Prepared for the owner's October 3, 2026 review suggestions. These changes extend the combined checkpoint. No production build or ZIP has been made for this update; packaging requires a new owner OK.

## Changes

- Independent video/image/text controls open in Media or Text. Their draft preview appears beside the main monitor, using a still from the current scene as a placement backdrop. Minimize, Restore and Close retain the draft; Apply saves one overlay edit. Narrow windows stack the monitors. Existing scene editing remains available.
- Generated caption cards have eight bundled colour emoji choices and a left/right side. Emoji follows that card's time span and sits beside its text. Caption style and words stay editable. The render uses bundled PNG artwork, avoiding missing emoji fonts. Rendering confirms final placement, especially long or wrapped Arabic text. Up to 64 caption cards per scene can carry emoji. Timed emoji is disabled with typewriter captions.
- Voice censoring provides original-file time ranges with Bleep or Mute for narration, embedded video sound and timeline audio. Source audio remains unchanged. Trim and split retain source-clock positions. Other tracks remain audible; caption words are not censored by this feature. Narration Play clip provides an approximate live audition; rendering/export applies sample-based replacement. Video/timeline clips are auditioned by rendering.
- Narration can find English/Arabic whole-word matches from an existing linked auto-caption transcript. The user reviews matches before adding; adjoining matches merge. No provider or model call occurs from censor controls. New transcription metadata records the source asset, source trim and scene offset so matches remain attached to the right recording. Older transcripts need regeneration before word matching; manual ranges work without a transcript.
- Effects gains a styled Finishing touches group: edge vignette, cinema bars and detail sharpening, each with an amount control. They render, participate in stack ordering/bypass, and save in portable look presets. The editing preview approximates vignette/bars; sharpening needs a render. Export dimensions remain unchanged.

## Verification

- TypeScript and focused frontend checks passed: censor ranges/overlaps, English/Arabic word matching and review; delayed overlay save/edit/retry; optional script setup. The existing editor component suite passed 334 checks.
- 36 new real API/FFmpeg checks passed. They measure 1000 Hz replacement without the original 300 Hz tone, silence, unchanged audio outside ranges, source trim, narration rendering, timeline export, embedded and detached video sound, timed colour emoji, invalid ranges/emoji/effects, and individual effect pixels/bypass.
- Existing audio-edit suite: 26 checks; effect stack/preset suite: 70 checks; finishing suite: 29 checks passed.
- Real Chromium checks passed for companion geometry, Minimize/Restore/Close, video stacking, narration censor add/remove, timeline censor Undo/Redo, caption emoji, effect controls, and existing Audio and Script setup workflows. No browser JavaScript errors in these flows.
- Visual review caught and fixed a collapsed main monitor when closing the companion and duplicate keyed Audio controls when switching clips. Dark/light Audio action contrast remains checked.

No Windows test or real installed-model transcription/generation is claimed. No paid calls, push, merge, tag or publication. Product versions remain unchanged; Sections E/F are not declared complete.

## Owner checklist after an approved build

1. Select upper-track video, image and text clips. Adjust placement while watching the second monitor; minimize, restore and close it. Check Apply/Saved/edit feedback and Undo/Redo. Try a narrow window.
2. Generate timed captions, choose an emoji and side on one card, then render. Verify colour and timing, remove it, save/reopen, and try an Arabic caption. Check long/wrapped captions in the render.
3. In Audio, add a short Bleep range and a separate Mute range, Play clip, then render/export. Repeat on video sound and a timeline audio clip. Trim/split afterward and verify censoring stays on the same original sound. Test timeline Undo/Redo and reopening.
4. For linked narration captions, enter a known word, Review word matches, listen to the times and Add reviewed matches. Verify the caption words remain unchanged and other audio tracks still play.
5. Toggle each Finishing touches effect, vary the amount and render. Try stack order/bypass and saving/applying a look preset. Recheck the original effects and the previously failing caption render.
