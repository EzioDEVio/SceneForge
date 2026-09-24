# SceneForge Desktop 0.2.0 RC5 (in progress) — looks, grading and timeline drops

## Glitch
- Tears now reach the whole frame: horizontal bands tile the full height, and the RGB split and noise cover the full frame (previously three fixed strips).
- **Effect strength** sets tear distance, how many bands tear at once, and burst length. New **Speed** (0.25×–4×) sets how often bursts happen; **Block size** chooses Fine, Medium or Chunky bands. These controls appear when Glitch is selected.

## Adjust (Effects tab)
- Eleven sliders with number boxes and resets: Exposure, Contrast, Highlights, Shadows, Temperature, Tint, Saturation, Vibrance, Sharpen, Vignette, Grain. Double-click a slider to reset it; **Reset all** clears them.
- The preview approximates the result live; render the scene for the exact grade.
- Colour sliders and the LUT are baked into one 3D LUT per scene at render time, so grading adds roughly one filter pass however many sliders are used.

## Color LUT
- **Import .cube** in Effects → Color LUT, choose it per scene, and set its strength. 3D .cube files up to 65 points and 12 MB; invalid files are rejected with the reason. LUTs show in the rendered scene, not in the preview.

## Drag and drop onto the timeline
- Drop an audio file from Explorer onto a scene's picture or Narration lane: it becomes that scene's sound, and the scene switches to **Match narration** so picture and audio stay one clip.
- Drop images or videos onto a scene to add them to it, or after the last scene to fill empty starter parts and then create new scenes. Folders work; files are placed in name order.
- Items can also be dragged from the Media Pool onto a scene. Skipped files (unsupported types, more than one audio file per scene) are reported in the timeline.

## Upgrade notes
- Existing databases gain a `look_json` column automatically on first start; existing scenes keep all their data. Back up `backend\data` before upgrading, as always.
- NumPy is now a runtime dependency (`backend/requirements.txt`); run `scripts\setup.bat` again after updating.

## Tests
- `tests/integration/test_looks.py` (33 checks, in CI): full-frame glitch, strength and speed; .cube parsing and rejection; LUT import; slider validation; real renders for LUT strength, greyscale, temperature and exposure; database upgrade from RC4.
- 11 new component checks and 8 new unit checks for the Look panel and timeline drops.

# SceneForge Desktop 0.2.0 RC5 (in progress) — editor fixes

## Captions and text
- Latin text in captions, text layers and title cards now uses the bundled Noto Sans; Arabic text uses the selected Arabic font. Previously English captions borrowed the Arabic font's small digits and narrow spaces, and missing letters fell back to a different system font on each OS.
- Arabic-first lines now lay out right-to-left across the whole line, so a trailing English word appears on the left as it should. RC4 laid these lines out left-to-right.
- Latin system fonts (Arial, Georgia, …) keep an Arabic companion font for Arabic words. **Noto Sans** is added to the font lists. The editor preview picks fonts the same way as the renderer.
- Existing projects render with the new fonts the next time a scene is rendered. Re-render scenes whose captions mix Arabic and Latin text.

## Media
- Videos show a real frame in the Media Pool, scene bin, timeline, effect tiles and the scene media list. Images there load small cached thumbnails instead of full-size originals. Thumbnails are stored under `proxies/thumbs` in the data folder and can be deleted safely.
- **Add to timeline** fills the empty starter parts (Part-1, Part-2, Part-3) before creating new scenes. Empty parts between real scenes are left alone.

## Timeline
- Playback controls: start, previous scene, previous frame, play/pause, stop, next frame, next scene, end. The duplicate Pause and text Prev/Next buttons are removed.
- **Render full video** moved to the timeline tools on the right.
- The lane formerly called Titles is now **Text**: captions show with a captions icon, title layers as a count badge.
- Keyboard shortcuts: Space play/pause, ←/→ one frame, Shift+←/→ one scene, Home/End, Ctrl+Z / Ctrl+Shift+Z / Ctrl+Y undo/redo, Delete removes the selected scene after confirmation. Shortcuts are ignored while typing or when a dialog is open.
- Effects are now chosen only in Scene Settings → Effects; the duplicate left-panel Effects tab is removed.

## Tests
- `tests/integration/test_text_thumbs.py` (18 checks, added to CI): script runs, override-injection escaping, real libass renders for Latin and right-to-left mixed captions, and thumbnail endpoint behavior.
- `frontend/tests/units.mjs` (10 checks) and 6 new component checks for the transport, shortcuts and removed tab.
- Verified on Linux (libass 0.17.1). A mixed Arabic/Latin caption render on the Windows build is still needed.

# SceneForge Desktop 0.2.0 RC3

## Close and credential fixes
- X, Alt+F4 and File → Quit ask **Save and exit** or **Cancel**. Pending narration, captions, titles and project-name changes are saved before stopping the backend. Failed saves and active renders keep the app open.
- Provider credentials use the native Windows credential vault (macOS Keychain / Linux Secret Service in source installs). Legacy Base64 keys migrate on startup; failed migration is reported and the legacy key cannot be used. No plaintext fallback is permitted.
- Migration scrubs the active SQLite database and WAL. Older backups remain outside this migration; keep them private or rotate keys if they were shared.
- Linux CI starts a real Secret Service for credential tests. Windows build commands now stop immediately on a failed command.
- Corrects Together image routing and ElevenLabs audio file format. Cloud provider calls are tested with fixtures; live billable generation is not performed in CI.


## Editing fixes
- Title text saves as you type and stays editable when switching inspector tabs.
- Caption typewriter enables captions and can populate an empty caption from the narration script.
- Direct Edit narration and Edit captions & titles actions reopen the editors.
- Render text preview updates the rendered scene after text or animation changes. Title overlays use their own Animation selector.
- Voice generation waits for the latest narration script to save. Regenerate narration after editing its script.
- In-app confirmation dialogs restore editor focus after closing.

## Earlier changes
- Automatically starts an existing Stable Diffusion WebUI installation when enabled. The default folder is your user profile's `stable-diffusion-webui` folder.
- **AI Engines → Choose Stable Diffusion folder** opens the native folder picker, saves the location and starts the service. **Generate image → Local engine setup** contains the automatic startup switch and editable path.
- Reuses an already-running SD API. On exit, stops only an SD process launched by this app.
- Voice takes now have a Delete action with confirmation. Deleting selected narration invalidates its old scene render and leaves narration unselected. Shared media files remain available.
- Prevents audio deletion during an active project render.
- Explains why voice generation is unavailable when narration text is empty.
- Removes source-workspace launch instructions from desktop voice errors and improves selected-take contrast.

## Install and use
Close SceneForge before running the new setup executable. The same application identity and user workspace are retained, preserving saved projects and provider settings. Do not delete your existing workspace.

For SD, select your existing folder containing `webui-user.bat`, with `--api` in its launch options. Model downloads are not required when reusing your installation. Initial model startup can take several minutes; use Check engine or View startup log in Image Studio.

## Release status
This is an unsigned Windows x64 release candidate. The core editor, private Python runtime, FFmpeg and fonts are bundled. AI engines and model downloads are not bundled. Existing Chatterbox installations remain supported. macOS/Linux installers, signing and automatic engine installation are not included. Real SD inference on the user's GPU remains a manual acceptance check; CI checks launching and stopping a fixture service, not model quality.
