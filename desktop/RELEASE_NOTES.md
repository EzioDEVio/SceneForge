# SceneForge Studio 0.6.0-wip.10 (unreleased)

This is a reviewed source snapshot, not a published GitHub release. See [the source comparison and review](../docs/REVIEW_0.6.0_WIP.md).

## Compatibility and timeline fixes
- Restored undo/redo coverage for scene add/delete, media insertion, title cards, narration attach/remove, scene reorder, clip sound, and scene splits (up to 100 recent timeline operations).
- Scene splits preserve per-shot source audio settings and speed settings; undo restores original scene and clip IDs.
- Added a dedicated source-video-audio lane with separate blocks for each video clip. Selecting a block opens that clip’s **Clip Audio** inspector (separate from Motion), including volume, mute, narration ducking, and fades.
- Restored the original AI Engines top-level menu and Help menu while retaining Scenes, Media Pool, Transitions, and toolbar provider settings. Removed the redundant AI Engines entry from the Scenes library tabs.
- Whole-scene timeline blocks can be dragged to reorder; source sound follows video splits.

## New and improved
- **Additional caption looks:** Creator punch, Soft subtitle, Glass panel, Pastel pop, Cyber cyan and Clean white.
- Transition tiles now show more distinct cover, slide, zoom, wipe, blur and radial motion cues while previewing.
- Dropping media into empty timeline space inserts it at that point in the sequence; the left/right scene-edge insertion behavior remains available.
- **18 additional transitions** with live previews on your clips (42 choices total).
- **Select several parts** and apply chosen effects, caption styles, titles, or transitions together while preserving each part's caption text and position-specific effects.
- **Free local captions:** Faster-Whisper is the default and needs no API key. Its multilingual model downloads once on first use; subsequent transcription runs on-device. ElevenLabs and OpenAI remain optional cloud choices.
- **Fourteen additional caption styles** (24 total).
- **Export presets and controls:** platform presets, estimated size, resolution up to 4K, frame rate, quality, H.264/H.265 MP4, WebM, ProRes MOV, GIF, MP3 and WAV; export SRT/VTT caption files.
- **Progress cards** show the current stage, percentage, elapsed time and estimate, with cancellation for renders and exports.
- The multi-select toolbar can be minimized and closes automatically after a successful action.
- Advanced export controls open by default in a redesigned dark editing-style panel; the narration script box has updated styling.
- The timeline shows video source sound on its own A2 lane; clicking a block opens the existing clip sound controls. Drop media near a scene's left/right edge to insert a new part before/after it.

## Fixed
- Exports use broadly supported H.264 4:2:0 and fast-start MP4 settings, including projects with transitions, to improve playback in Windows Photos and Media Player.
- The fast timeline export uses draft quality; the Export dialog retains its selected delivery quality.
- A 9:16 project preserves the full duration and sound of source video clips. Clip sound can be muted or adjusted individually.

## Additional updates in wip.8 (previous WIP)
- Added **Text**, **Text Box**, and **Text+** creation tools. Text is a short title; Text Box adds a width-controlled, wrapping block; Text+ uses SceneForge's styled/animated title controls. These are not a full DaVinci Resolve Fusion replacement.
- Text titles and on-screen captions appear as labeled, timed clips on the T1 timeline. Selecting a clip switches to Text and focuses the matching editable caption/title field.
- Added click-to-open “What it does / How to use it” help popovers across Media, Motion, Effects, Overlays, Text, Audio and Clip Audio, plus feature sections such as stickers, effects, framing and narration.
- Timeline marker help now explains that markers are named bookmarks for returning to a point in the project.
- Frontend/backend build IDs and desktop package version were `0.6.0-wip.8`.
- The post-export Share dialog from wip.7 remains included.

## Additional updates in wip.9 (previous WIP)
- Auto captions now create individually timed caption clips on T1, grouped by a user-selected 1–8 words per clip. Click a clip to open and focus its text editor; change wording and start/end times, split a phrase into two clips, or remove a clip. Caption styles still apply across the caption set.
- Fixed clipped feature-help popovers by placing them in a viewport-level layer, repositioning them near the trigger, constraining long content to a scrollable viewport, and supporting Escape to close.
- Bumped frontend/backend build IDs and desktop package to `0.6.0-wip.9`; the post-export Share dialog remains included.

## Additional updates in wip.10
- Moved the T1 text/caption lane above the V1 picture lane so timed captions sit directly above their video on the timeline.
- Added caption search, previous/next navigation, active-segment highlighting, and collapse/expand for long transcripts.
- Added Auto, Right to left, and Left to right caption direction. The setting follows edited captions into ASS rendering, including mixed Arabic/Latin phrases.
- Updated the frontend/backend build identifiers and desktop package version to `0.6.0-wip.10`.

## Installation notes
- The Windows desktop installer bundles the editor, its private backend runtime and FFmpeg. It does not bundle the Whisper model, optional Chatterbox/Kokoro narration servers, or Stable Diffusion image models. Whisper downloads its model once on first use; the others require separate setup if needed.

# SceneForge Studio 0.5.3

## Fixed (important)
- **Video clips now keep their own sound.** Videos with sound used to export silent; only narration and music were heard.
- **Scenes last as long as their videos.** A scene without narration used to fall back to 4 seconds, and a scene longer than its video looped the video to fill the gap. Now a scene lasts exactly as long as its videos (after trimming and speed changes), and several videos in one scene each keep their own length.
- **No unexpected countdown.** The whole-video "Countdown leader" switch is removed; the countdown is now an effect you add to a scene (below).
- **File → New project / Open project** (Ctrl+N / Ctrl+O), in the desktop menu and the editor menu. They wait for saves instead of being greyed out.
- Changing only a clip's speed or sound now always re-renders the scene (it could reuse an old render).

## New
- **Clip sound** (Motion tab, for videos): volume, mute, and "Lower it under narration" so a voice-over stays clear.
- **Captions from speech** (Text tab): automatic captions from the narration or from the sound of your videos, in any language (detected automatically), with exact word timing for phrase captions and word highlight. Uses your ElevenLabs (Scribe v2) or OpenAI (Whisper) key; the text stays editable.
- **Countdown intro** (Effects tab): a cinema countdown before a scene: Film leader (grain, scratches, projector sound; black & white or sepia), Modern (glowing ring) or Minimal; 3–10 s; beeps on every number, the classic 2-pop, or silent. Off unless you switch it on.

## 9:16 (TikTok, Reels, Shorts)
- **Landscape clips and photos keep the whole picture over a blurred background** by default in vertical projects, instead of being cropped. Choose in Motion → Fill the frame: Fill (crop), Fit + blurred background, or Fit + bars.
- **Captions sit above the platform's buttons and caption** (about 20 % up) by default.
- **Safe zones** toggle on the preview shows the areas TikTok, Reels and Shorts cover.
- Split screen defaults to top & bottom in vertical projects.

# SceneForge Studio 0.5.2

- **No more flicker** when changing effects: background saves no longer grey out the timeline or the scene settings.
- **Duplicate and copy/paste on the timeline:** right-click a picture clip → Duplicate scene, Copy scene, Paste after (or Ctrl+D / Ctrl+C / Ctrl+V). The copy keeps every picture, effect, caption, title, overlay and audio take, so you can give it different effects. Right-click a narration clip → Copy audio, then Paste audio here on another scene.
- **Preview zoom:** zoom buttons next to the cut tool and in the preview header (up to 400 %), Ctrl + mouse wheel zooms at the cursor, and middle-drag or Space + drag pans.

# SceneForge Studio 0.5.1

- **Move and resize annotations directly on the picture.** In the Effects tab, every annotation shows handles on the preview: drag a point to change where it starts or ends (or its corners, for circles and boxes), and drag the ✥ handle to move the whole shape. The sliders update as you drag.
- **Accurate arrow preview.** Curved arrows now preview as curves with their arrowhead, matching the render (they used to preview as a straight line).

# SceneForge Studio 0.5.0 — Captions Pro

Captions now have CapCut-level styling. Everything is in **Text → Caption styles**, with a live preview on the picture.

## Caption styles (one click)
Classic, YouTube box, **Viral bold**, Karaoke, Neon, Cinematic, Documentary, Underline, **Arabic modern**, Pulse.

## Font
- **Seven new bundled fonts:** Poppins, Bebas Neue, Anton, Pacifico, and Arabic **Amiri**, **Tajawal**, **Lalezar**, each paired with a matching font for the other script.
- **Bold, italic, underline**; letter case (as typed, UPPERCASE, Title Case, lowercase); letter spacing; size up to 120.
- Added fonts are size-matched so the same size setting looks the same size.

## Colours, outline, shadow, box
- Text colour; outline colour and width; shadow with colour and opacity.
- **Background box** with colour, opacity and padding.

## Position
- Top / middle / bottom, left / centre / right, move up or down, maximum width.

## Phrase captions (CapCut style)
- Show a few words at a time (1–8 per phrase), each phrase appearing as its words are spoken (exact timing with ElevenLabs, measured from the audio for other voices).

## Word highlight
- New styles: **Box** (a marker behind the spoken word), **Colour** (only the current word) and **Underline**, besides Colour fill, Pop and Glow. Works inside phrases.

## Animation
- Entrance (all the ✦ animations), **exit** (fade out, pop out) and a looping **pulse**. In phrase mode each phrase gets its own entrance, exit and pulse.

## Also
- The old flat caption controls are replaced by the organised Caption styles panel. Existing projects keep their settings.

# SceneForge Studio 0.4.1

- **Caption animations** (Text tab → *Caption animation ✦*): the captions themselves can now use the new animations: letters pop/fade/flip/blur-in, words pop/fade/flip, shine, bounce, zoom, blur, neon, wobble and glitch, with an adjustable length. Arabic captions animate word by word. (Typewriter and Word-by-word highlight still animate captions their own way; turn them off to use a caption animation.)
- **✦ Add animated title** button at the top of the Text tab: adds a letter-pop title in one click (edit it under Text overlays).

# SceneForge Studio 0.4.0 — Motion & Text

## New: text animations (Text tab → Text overlays, and the Title Designer)
- **Letter by letter:** Letters pop, Letters fade, Letters flip, Letters blur in, and **Shine** (a highlight sweeps across the text).
- **Word by word:** Words pop, Words fade, Words flip. Arabic text animates word by word automatically, so letters stay joined.
- **Whole line:** Bounce, Neon flicker (with a coloured glow) and Wobble.
- **Letter spacing** and a highlight/glow colour for Shine and Neon.
- **One-click text styles:** Documentary, Bold pop, Neon, Cinematic, Headline, Golden shine, Arabic title.
- The Title Designer's *Play rendered preview* shows the real animation before you add the card.

## New: animated annotations (Effects → Annotations)
- **Arrow** (curved or straight), **Circle** (hand-drawn or neat), **Underline** (line or highlighter), **Box**, and **Callout** (a label with a pointer, Arabic supported). They draw themselves on screen with their own start, draw and end times, and fade out at the end. Up to 10 per scene, previewed on the picture.

## New looks
- **Glow** (soft bloom), **Duotone** (deep blue to warm gold), **Newspaper** (high-contrast print on paper).

## Also in this release (from 0.3.5)

## Fixes
- **Arabic map-route stop labels now render correctly**: joined letters, right-to-left, in the Noto Naskh Arabic font, including mixed text such as "قرطبة 711". (The labels used a font without Arabic letters, and Windows lacks the shaping engine the image library relies on; shaping is now done by bundled libraries that work the same on every system.)
- **Typing a stop label is no longer interrupted.** Background saves used to disable the editor for a moment, which greyed out the timeline, took the cursor out of the field and dropped keystrokes. Stop labels now keep their text while you type and save after a short pause or when you leave the field.

## Tests
- The release end-to-end test now renders an Arabic-labelled map route in the installed app on every system.

# SceneForge Studio 0.3.4

## New
- **Map routes: arrowhead, moving icon, stop labels, curved paths.** The line can end in an arrowhead that stays visible at the destination; a plane, ship, car, dot or pin can ride along the route and turn with it; each stop can have a label (a city or a date) that appears when the line reaches it; and the route can follow a smooth curve through the stops.
- **Right-click menu** everywhere: undo/redo, cut, copy, paste, paste as plain text, select all, spelling suggestions, and copy image.
- **Paste media from anywhere**: copy an image, video or audio file (from a browser, Explorer or a screenshot) and paste it into the scene with Ctrl+V or right-click → Paste. Text boxes keep normal paste.
- A hint above the looks grid: hover a look to preview it, click to apply.

## Fixes
- **After an update the app could keep showing the previous version's editor**, so some new features (such as the look preview) did not appear. The editor page is now always re-checked, and the saved copy is cleared once whenever the app version changes.

# SceneForge Studio 0.3.3

- **AI engines & providers panel** (AI Engines menu, Ctrl+Shift+A): a getting-started guide, which cloud providers are connected (with where to get a key), step-by-step Stable Diffusion setup with Choose folder / Start now / Start automatically, and local voice help. Replaces the plain message boxes.
- **About panel** (Help → About): version, update check with a clear result, beta updates switch, license, GitHub, Report a problem, Collect diagnostics, Open logs.
- **Clearer update messages**: "no published release yet", "can't reach GitHub", or the actual error, instead of always "check your internet". Turning beta updates on or off now confirms it and checks for a beta straight away.
- **Preview looks before applying**: hover over a look to see it on the picture ("Previewing … · click to apply"), including split-screen scenes.
- **Animated transition previews**: every transition in the Transitions list plays its real motion on hover.
- **Branded Windows installer**: SceneForge icon on the installer and uninstaller, sidebar artwork on the welcome and finish pages, a header on every step including the progress page, and "Run SceneForge Studio" at the end.

# SceneForge Studio 0.3.2

- **Fixed (Windows): the app froze when choosing an effect or look, and then stopped responding.** The release test reproduced it on a clean Windows machine: the first action that loads the maths library (NumPy) hung the whole backend. NumPy and OpenCV are now loaded once at start-up on the main thread, with their maths engine limited to one thread.
- The backend now writes a diagnostic report to its log if any action takes longer than 20 seconds, showing exactly where it is stuck.

# SceneForge Studio 0.3.1

- **Stable Diffusion no longer starts automatically** after this update (a one-time change). Starting it with SceneForge could slow the whole computer while it loads. Start it from **AI Engines → Stable Diffusion → Start Stable Diffusion now**, or tick **Start automatically with SceneForge** in the same menu.
- **Guided AI Engines menu**: *Getting started with AI*, *Add or change API keys*, step-by-step help for Stable Diffusion and local voices.
- **Help → Collect diagnostics for a bug report**: puts logs and system details (no API keys, no media) in a folder on your Desktop.
- **View → Developer tools** (Ctrl+Shift+I) for bug reports.
- Release builds now run an **end-to-end test of real editor work** in the packaged app on Windows, Linux and macOS (import, thumbnails, effects, colour preview, narration waveform, provider settings, and a full scene render), with time limits.

# SceneForge Studio 0.3.0 — first public open-source release

- **Open source** under the GNU GPL v3.0 or later.
- **Installers for Windows, Linux (AppImage, .deb) and macOS (Apple Silicon, experimental)**, built by GitHub Actions and published on GitHub Releases.
- **Automatic updates** (Help → Check for updates; Help → Receive beta updates). Windows and Linux AppImage update in the background; macOS announces new versions.
- **Project backups** before every update (Help → Open project backups; the last 5 are kept).
- Renamed from "SceneForge Desktop Alpha" to **SceneForge Studio**; projects from the Desktop Alpha are copied over automatically on first start (the old folder is left untouched).
- New README, third-party notices and contributing guide; new app icon.
- Includes everything since RC4: effects packs A–C, overlays, map routes, split screen, 3D photos, photo restore, word-by-word captions, music and finishing, audio editing, LUTs, old film and more (see the entries below).

# SceneForge Desktop 0.2.0 RC5 (in progress) — photo restore rewritten

- **Restore old photo** no longer damages detailed photos. The previous version treated fine detail (debris, clothing, branches) as dust and smeared it; on a real WWII photo it "repaired" 23 % of the picture. Now:
  - dust is only removed where it is a tiny isolated speck on a smooth area (sky, smoke, walls), never inside texture, and never more than 0.5 % of the photo;
  - grain reduction is scaled to the photo's measured noise;
  - black-and-white photos are processed and saved as black and white;
  - contrast and sharpening are gentler (no halos).
  On the same WWII photo, 94–105 % of the detail is kept.

# SceneForge Desktop 0.2.0 RC5 (in progress) — split screen and photo restore fixes

- **Split screen**: the editor preview now shows the layout. When a scene has only one picture, an **Add another image or video to this scene** button appears under Split screen, and the hint says how many pictures the scene has.
- **Restore old photo**: shows progress and a confirmation naming the restored copy; the Media Pool refreshes right away. If the photo tools are missing (setup.bat not re-run after updating), a clear message says what to do instead of a generic error.

# SceneForge Desktop 0.2.0 RC5 (in progress) — Batch B and C

## Pictures
- **3D photo (parallax)**: mark the subject of a still photo; the background behind it is filled in automatically and the two layers move at different depths (push in, pull out, drift left or right).
- **Restore old photo** (Media tab): a cleaned-up copy with less noise, dust and scratches removed, recovered contrast, sharper detail, and small scans upscaled. The original is kept.
- **Colour wheels**: lift, gamma and gain, shown in the preview.
- **Split screen**: side by side, top & bottom, three panels, or a 2 × 2 grid, with gap and background colour.

## Motion and timing
- **Clip speed** for video clips (Motion tab): 0.25×–4×, a slow-motion or fast moment in the middle, and freeze frames. Scene length does not change.
- **Map route**: a line draws itself across the picture with pins popping in at each stop. Click the preview to add stops and drag them to adjust; solid or dashed, colour, width, start and draw time.
- **Sync scene cuts to the beat** (Audio → Music & finishing): finds the tempo of the background music and moves fixed-length scene cuts onto beats. Narrated scenes keep their length.

## Captions
- **Exact word timing with ElevenLabs**: new ElevenLabs voices include per-word timings, and word-by-word captions follow them exactly when the caption matches the narration. Other voices keep the speech/pause detection.

## Fixes
- The VHS look's rolling tracking band never appeared (FFmpeg evaluates drawbox positions only once); it is now drawn with a per-frame overlay.

## Notes
- New dependency: OpenCV (headless), about 70 MB, for 3D photo and photo restore. Run `scripts\setup.bat` again after updating.
- Colorizing black & white photos and automatic subject detection need AI models and are not included yet.
- Build ID `rc5-batchbc-7`. New tests: `test_batch_b.py` (27 real-render checks); 7 component checks (115 total).

# SceneForge Desktop 0.2.0 RC5 (in progress) — Effects pack

## New looks and scene effects (Effects tab)
- **VHS** look: colour bleed, scanlines, a rolling tracking band and tape noise.
- **Split toning**: tint shadows and highlights with two colours; shown in the preview.
- **Camera shake** with optional **impact zoom** at the start.
- **Spotlight**: darken everything except an oval or box, with soft edges and timing.
- **Blur or pixelate areas** (up to 6) to hide faces, names or number plates.
- **Light leaks**: warm, cool or rainbow light drifting in from the edges.
- Spotlight, blur areas and light leaks are previewed live in the editor.

## Transitions
- Wind, Slice, Open, Close and Quick fade (25 in total).

## Overlays
- **Glide** from one position to another during the overlay's time, **green screen** (make a colour transparent), and **soft edges**.

## Narration and captions
- **Voice effect** per take (Audio tab): Clean up, 1940s radio / newsreel, Telephone.
- **Caption style** for word-by-word: Colour fill, Pop (the current word grows), Glow (the current word glows).

## Tests
- `tests/integration/test_effects_pack.py` (28 real-render checks, in CI); 8 new component checks (108 total). Build ID `rc5-effects-6`.

# SceneForge Desktop 0.2.0 RC5 (in progress) — caption timing, roomier editor

## Word-by-word captions follow the real voice
- Fixed: in scenes with a fixed length longer than the narration, the highlight was spread over the whole scene and finished late.
- Word timing is now measured from the narration audio: SceneForge finds where the voice speaks and where it pauses and places the words on the spoken parts. The highlight waits during pauses and ends when the voice ends. Works with every voice engine (ElevenLabs, Chatterbox, Kokoro, uploads) and language, including Arabic. Trimmed takes are respected.

## Editor layout
- **Scene settings is resizable**: drag its left edge (280–760 px), double-click to reset, arrow keys for fine steps. The width is remembered.
- When the panel is wide, groups sit side by side (two or three columns).
- Controls are grouped into cards; number boxes are wider; choice buttons (animations, tone, frame rate) wrap as pills instead of squashing.
- **Narration script** card is taller, has **Expand**, and shows the word count, the estimated speaking time, and the voice status (length, or "Script changed · generate a new voice"), with a clear **Generate voice** button.

# SceneForge Desktop 0.2.0 RC5 (in progress) — Picture in picture

## Overlays (new Overlays tab)
- Place images or videos inside a scene: maps, portraits, documents, a second camera angle.
- **Drag on the preview to move; drag the corner handle to resize.** Arrow keys nudge (Shift for bigger steps).
- Position, size, rotation, opacity, rounded corners (up to a circle), border and border colour, drop shadow.
- Show from / until within the scene; entrance and exit animations: Fade, Slide, Rise, Zoom pop; animation length.
- Up to 8 per scene, with bring forward, send back, duplicate and delete.
- Videos play silently and loop. Overlays sit above the picture and its effects, below captions and titles.
- The editor preview matches the render; each card's shadow, border and corner mask are drawn once and cached under `proxies/overlays`.

## Upgrade notes
- Existing databases gain `scenes.overlays_json` automatically. Build ID is now `rc5-overlays-5`.

## Tests
- `tests/integration/test_overlays.py` (20 checks, in CI): validation, placement, size and aspect, border, rounded corners, rotation, timing, fade, slide, zoom pop, opacity, looping video, stacking order.
- 8 new component checks (100 total).

# SceneForge Desktop 0.2.0 RC5 (in progress) — transitions, motion, captions, music, film extras

## Transitions and motion
- 20 scene transitions: adds Circle close, Zoom in, Smooth slide left/right, Clock wipe, Pixelate, Blur, Diagonal wipe, Squeeze, Fade through grey, and **Film burn** (a hot orange flare that blooms across the cut).
- **Speed curve** for camera movement (Motion tab): Smooth (ease in and out, the default), Ease in, Ease out, or Constant speed.

## Word-by-word captions
- Text tab → **Word-by-word highlight**: each word changes to the highlight colour as it is spoken, following the narration. Timing is shared across the narration by word length.

## Music & finishing (Audio tab, whole video, applied on export)
- **Background music**: loops to the length of the video, with volume and fades, and **gets quieter automatically under narration** (sidechain ducking).
- **Level loudness for YouTube**: EBU R128 to -14 LUFS / -1.5 dBTP.
- **Film countdown leader**: 5-4-3-2 with a rotating sweep and the one-frame "2-pop" beep, added before the video (5 s).

## Old film
- **Projector sound**: clatter at the film frame rate with motor hum, mixed under Old film scenes. The three film styles set it.

## Fixes
- The motion speed-curve picker read its value after the save was queued, so a choice could be replaced by the previous one. Fixed.
- Export finishing tolerates older callers without finishing settings.

## Upgrade notes
- Existing databases gain `projects.finishing_json` automatically. Build ID is now `rc5-finishing-4`.

## Tests
- `tests/integration/test_finishing.py` (in CI): all 19 transitions render; film burn colour; easing curves; word timing and highlight on real libass frames; easing validation; film burn export length; music looping and ducking; measured loudness; leader length, picture and beep; projector clatter rate.
- 5 new component checks (92 total).

# SceneForge Desktop 0.2.0 RC5 (in progress) — Old film effect

## Old film (Effects → Old film)
- A real old-film look, like WWII newsreels and 8 mm home movies:
  - **Scratches:** vertical lines that drift, wobble, drop out and last up to a few seconds; mostly white, some dark.
  - **Dust & hair:** specks that change every frame, curly hairs caught in the gate for a few frames, the odd dark blotch.
  - **Flicker:** exposure that varies from frame to frame, with the gate vignette "breathing" along with it.
  - **Gate weave:** the picture wobbles in the projector gate, with the occasional frame slip.
  - **Frame rate:** 16 or 18 fps for the jerky hand-cranked look (24 fps, or keep the project rate). Scene length is unchanged.
  - **Tone:** Colour, Faded, Sepia, or B & W.
  - Film grain and slight lens softness scale with the amount of damage.
- One-click styles: **WWII newsreel**, **8mm home movie**, **Silent era**.
- The effect plays **live in the editor preview**; the render uses the same settings through FFmpeg.
- Each scene gets its own damage pattern, and re-rendering a scene gives identical results. The damage layer is cached under `proxies/film` in the data folder and can be deleted safely.
- Works on top of any look, LUT and adjustment. Titles and captions stay sharp above the film damage.

## Fixes
- With the **Original** look selected, the colour-slider preview had no effect: the preview combined the CSS value `none` with other filters, which made the whole filter invalid. Fixed.

## Version check
- Build ID is now `rc5-old-film-3`.

# SceneForge Desktop 0.2.0 RC5 (in progress) — LUT compatibility

## LUTs from DaVinci Resolve
- **1D LUTs** (`LUT_1D_SIZE`, e.g. gamma, log and HDR conversions) and Resolve's **1D shaper + 3D** LUTs (e.g. ACES LMT) now import and render. Previously they were rejected. All 108 `.cube` files in Resolve's LUT folder import.
- **Import a whole folder of LUTs** (Effects → Color LUT). Only `.cube` files are imported; other Resolve formats (`.ilut`, `.olut`, `.xml`, `.dat`) are listed as skipped, and broken files are named with the reason. Several files can also be chosen at once in the file picker.
- The LUT size limit is raised from 12 MB to 32 MB (Resolve's "Samsung Log to Rec709" is a legal 65-point LUT of 12.9 MB).
- If the backend does not keep a LUT choice, the panel now says so instead of silently doing nothing. Choosing a LUT is no longer blocked by an earlier failed save.

## Version check
- The backend build ID is now `rc5-looks-audio-2` and is shared with the interface (`BUILD_ID`). A new interface connected to an older backend (for example a `start.bat` window from a previous version that is still open) shows "Backend update required" instead of silently dropping new settings.

# SceneForge Desktop 0.2.0 RC5 (in progress) — audio clip editing, LUT preview

## Scene audio editor
- Click a scene's audio clip on the timeline (or open Audio) to edit it: waveform with draggable trim handles (arrow keys nudge 0.1 s), Start/End in seconds, Volume 0–200%, Fade in and Fade out, **Play clip** to audition the trimmed, levelled and faded result, and **Reset edits**.
- Edits are non-destructive: the original file is never changed. **Match narration** uses the trimmed length.
- **Remove from scene** takes the audio off without touching the picture. The scene keeps its current length, and the audio stays in the takes list and the Media Pool. With a timeline audio clip focused, Delete removes only the audio.
- Timeline audio clips show their waveform and file name.

## LUT fixes
- The editor preview now shows the LUT (and colour sliders) exactly as the render will, and Effects → Color LUT shows a before/after comparison. Previously LUTs were only visible after rendering, which made them look like they did nothing.
- .cube files with a UTF-8 byte-order mark or accented titles now import; `LUT_3D_INPUT_RANGE` is honoured.
- Fixed a race when the preview and a render built the same grade at the same time.

## Other fixes
- A lead or trail of 0 now renders as zero; previously it rendered the defaults (0.25 s / 0.4 s), so the render was longer than the timeline showed.
- Scene cards and the settings header show the scene's current length rather than the length of its last render.

## Upgrade notes
- Existing databases gain `voice_takes.edit_json` automatically; existing takes keep their data.

## Tests
- `tests/integration/test_audio_edit.py` (26 checks, in CI): trim, volume, fades and length measured on rendered audio; waveform; removal keeps picture and file; database upgrade.
- `test_looks.py` now 40 checks, including the graded preview matching the render; 7 new component checks.

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

## Regression repairs in wip.5
- Source clip sound controls now have a dedicated Clip Audio inspector tab and no longer appear inside Motion. A2 timeline blocks open that tab.
- Crop and focal maps use backend-generated image thumbnails/poster frames, with a readable fallback if preview generation fails. Crop/focal controls save on slider release or keyboard edits as well as through Apply buttons.
- Clip volume commits the exact selected value instead of relying on stale slider state.

## Additional updates in wip.6
- Source clip sound now includes render-applied fade-in and fade-out sliders alongside volume, mute, and narration ducking. Fade settings follow a clip through scene splits.
- Auto captions now switch to a single-column layout in a narrow inspector and return to two columns when there is room.

## Additional updates in wip.7 (previous WIP)
- Export completion offers a local-first share dialog with download, desktop file-location reveal, platform links and step-by-step posting guidance for YouTube, TikTok, Instagram and Facebook. SceneForge does not upload automatically; the dialog explains platform authorization and account limits.
- Timeline ruler scrubbing can snap to scene boundaries and named markers. Markers persist per project in the local browser profile.
- Single, narration-free video scenes can be trimmed from either edge on the timeline; source video audio follows the same in/out points. The existing scene delete operation removes a scene and closes the sequence gap.
- Overlays now include a searchable, categorized 48-item emoji/sticker picker. A chosen symbol is rasterized as a standard image overlay asset so it follows existing placement, transform, animation and render behavior.
- Added three distinct color filter presets: Teal & Amber, Pastel, and Bleach Bypass.
- Updated frontend/backend build IDs and desktop package to `0.6.0-wip.7`. This is still an unreleased source snapshot; no platform upload APIs or full multitrack lock/mute/solo controls are included.
