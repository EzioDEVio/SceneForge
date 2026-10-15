# Changelog

## Unreleased

- **Trending effects showed as Off after reopening a part** (0.9.4-beta.9): RGB split, Cinematic fade & zoom, Intro move, Before & after and Speed blur were saved and rendered, but the Effects panel showed them switched off when you came back to the part, and switching one on again reset its settings. The panel now reads every effect in the effect stack; a unit test checks that each effect-stack effect is kept, so a new effect can't be missed again.
- **AI help:** the "Local voices" card no longer says SceneForge sets up Docker Desktop (it hasn't since 0.9.4-beta.3).
- **Repository:** a new README with a demo reel edited in SceneForge from real photos, fresh screenshots, a banner and a social preview image, and a clip of every trending effect in the feature guide; the long reference moved to [`FEATURES.md`](FEATURES.md), [`AI_PROVIDERS.md`](AI_PROVIDERS.md) and [`DEVELOPMENT.md`](DEVELOPMENT.md). Issue forms, a pull request template, a code of conduct, and an updated security policy (keys are in the OS credential store). Internal handoffs, reviews and test evidence moved to [`dev-notes/`](dev-notes/README.md); the Docker-era voice launchers moved to `scripts/legacy-docker/`. Tests now write their screenshots and evidence to `tests/output/` (ignored by git) instead of `docs/`.

## 0.9.4-beta.9 — the CapCut trend effects in More effects (October 13, 2026, beta pre-release)

- beta.8 put the trend list into Transitions and Looks; the owner asked for them in **Effects → More effects**. Five new per-part effects in **More effects → Trending**, after CapCut's 2026 trend list:
  - **RGB split**: red and blue slide apart (the glitch look), snapping out on every beat or held steady; strength and beats per minute.
  - **Cinematic fade & zoom**: fade in from black (or in and out) while the picture slowly pushes in or pulls out across the part.
  - **Intro move**: the picture swipes in (left, right, up), spins in or zooms in at the start of the part, with motion blur; 0.2–1.5 s.
  - **Before & after**: the part starts as a black & white, faded or dark "before" picture and a white line sweeps across revealing the real one (the before/after transformation); start point and sweep length.
  - **Speed blur**: directional motion blur for the "velocity" feel, on the whole part or as a whoosh that clears over the first half second.
  They join the effect stack (reorder, bypass), look presets and effect search. The Trending group also points to Motion → Speed for speed ramps (velocity) and slow motion on video clips.
- Measured here, 5 s at 1080p30, filters only (no effects 0.4 s): RGB split 4.4 s (steady 1 s), before & after 3.9 s, speed blur 1.1 s, cinematic 0.9 s, intro 0.8 s.
- **Installers (all three) failed at "Test the packaged backend with a real render" since beta.3:** the packaged backend crashed at start-up ("NameError: cannot access free variable 'json'"). A local `import json` inside one branch of the start-up code made `json` local to the whole function, so the "backend is ready" message never reached the app. Fixed; reproduced and verified here by building the packaged backend the same way as the workflow (PyInstaller 6.22.3): the smoke test passes, and the packaged end-to-end test passes 23 of 24 steps (the remaining one downloads the Whisper model, which this sandbox cannot reach). New `desktop/tests/test_release_backend_start.py` (in the regular checks) starts the backend entry point as the app does and fails within 90 s if it never announces itself; it fails on the old code with the same error. Pushing a `release/…` branch now also builds the three installers (no release).
- **Release workflow: "Verify draft release files" failed on every tag** (v0.9.3, v0.9.4-beta.1) although all builds passed and every file was uploaded. The check expected the Linux files as `…-Linux-x64.AppImage` / `…-Linux-x64.deb`, but electron-builder names them `…-Linux-x86_64.AppImage` and `…-Linux-amd64.deb`. The check now expects the real names; confirmed against the files GitHub holds for v0.9.3 and v0.9.4-beta.1 (old check: 2 "missing" files, new check: all 6 found). `test_release_assets.py` now compares against those published names.
- Tests: `test_trending_fx2.py` (in CI) checks each effect frame by frame (length kept, where and when it changes the picture, untouched after it ends, no black gaps), every pair in both orders keeps the exact length, invalid settings are refused, picture and video parts render and export, look presets keep them, and the 1080p timings. `test_reliability_perf.py` now includes them in its 24-part project; the editor test switches them on and off.

## 0.9.4-beta.8 — CapCut-style trending transitions and aesthetic looks (October 13, 2026, beta pre-release)

- **Seven trending transitions** (part → Transitions), after CapCut's 2026 trend and transition guides: **Whip pan left / right** (fast swipe with motion blur), **Spin** (the picture spins and zooms into the next one), **Zoom punch** (punch into the centre, land on the next part with a zoom blur), **Glitch** (jitter, colour split and noise, cut in the middle), **Cinematic zoom fade** (crossfade while both pictures drift in scale) and **Before & after** (a white line sweeps across revealing the next part, like a before/after slider). Each has a hover preview in the list. They are built from fast native FFmpeg filters (FFmpeg's per-pixel custom transitions took about 3 minutes for one 0.6 s transition at 1080p); measured here at 1080p30: 0.4–0.8 s per transition, and the export keeps its exact length.
- **Three aesthetic looks** (Look → filters): **Y2K** (cool shadows, soft glow, slight colour fringe), **Cozy** (warm, lifted and faded, light grain) and **Clean & bright** (bright, soft contrast, gentle sharpening). Each has its own settings (Y2K: saturation, contrast, glow, colour fringe; Cozy: warm tint, saturation, grain, vignette; Clean & bright: brightness, contrast, saturation, sharpen).
- Already in SceneForge from that trend list: speed ramps and velocity-style "bullet" ramps (Motion → speed), slow motion, slow zooms (camera movement with speed curves), beat sync (Finishing → Sync scene cuts to the beat, and beat markers), the glitch effect, beat zoom / flash / motion trails / mirror (beta.7) and colour grading.
- Tests: `test_trend_transitions.py` (in CI) exports every transition through the API and checks length, untouched parts before and after, no black corners during the transition, the expected picture at its middle, the before/after divider sweeping left to right, each look changing the colour, and the 1080p build time.

## 0.9.4-beta.7 — engines left running by earlier versions, reliability pass, trending effects (October 13, 2026, beta pre-release)

- **Stable Diffusion stuck at 48 % and Chatterbox still failing with "'NoneType' object is not callable" after the beta.5 fix.** The owner's diagnostics showed the Chatterbox error still carrying the old message text, so the engine answering on its port was one started by an earlier SceneForge: engines are separate processes, and closing the start.bat window (or a crash) left them running. Each new SceneForge folder then reused that old engine (old packages, old code, processor build) instead of starting its own. Now:
  - SceneForge identifies which program holds each engine port. An engine from SceneForge's own engines folder that this run did not start is stopped and replaced by a fresh one from the current version (at startup, on Start/Repair, and on Install). An old SceneForge Docker container is stopped through its own compose project. Any other program is never closed; the message names it (program and process number).
  - On Windows, engines now belong to a job object that closes with SceneForge, so they cannot be left behind again.
  - Engines installed by an earlier SceneForge folder count as installed in a new folder (engines are shared; preferences are per folder), so a new folder no longer asks to install again or forgets to start them.
  - A new SceneForge folder no longer starts your own AUTOMATIC1111 just because it exists (it competed with SceneForge's Stable Diffusion for port 7860 and graphics memory); it starts only when you chose "Start with SceneForge".
  - Chatterbox shows **Repair Chatterbox** when its model failed to load; the error text no longer points to Docker-era files.
  - Engine logs now live next to the engines; **View startup log** shows the Stable Diffusion engine's log.
- **Export diagnostics** now includes `local_ai.json` (setup progress and its log, chosen tools, graphics-card option, installed builds, and which program holds ports 7860 and 8881) and the Stable Diffusion and Chatterbox engine logs. Setup messages also go to the backend log.
- **Editor stayed responsive only when engines answered:** the AI status the editor polls every 2.5 s waited up to 9 s when an engine was busy or hung (three 3-second checks), so requests could pile up. Checks now run in parallel with short timeouts and are cached for 3 s (1.6 s worst case measured with both ports hung).
- **Trending effects** (Effects → More effects → Trending), chosen from current short-video trends (beat-synced zooms, flash/strobe, slow-motion blur, mirror): **Beat zoom** (punch-in on every beat, set the BPM), **Flash** (white flash at the start, on every beat, or both), **Motion trails** (fading copies behind moving things) and **Mirror** (left, right, top, bottom or four-corner kaleidoscope). They join the effect stack (reorder, bypass), look presets and search. Measured at 1080p30 on the test machine: 5 s takes 2.0–4.2 s to render (no effects 2.5 s).
- **Reliability and performance tests** (`test_reliability_perf.py`, in CI): status endpoints with both engine ports hung (each under 3 s), 400 requests from 16 concurrent clients (p95 about 0.15 s), a 24-part project with a different effect combination per part renders and exports with exact length, and 30 repeated renders without memory growth. `test_native_engines.py` now starts a real engine, abandons it like an old SceneForge would, and checks that the next start replaces it, and that a program that is not SceneForge's is never closed. `test_trending_fx.py` checks every new effect pixel by pixel and renders them on a picture and a video.

## 0.9.4-beta.6 — Voicebox narrations stuck at "Generating…" (October 13, 2026, beta pre-release)

- **Stuck Voicebox queue:** Voicebox makes one narration at a time. One job that never finishes (in the owner's test, a narration sent by beta.4 with Voicebox's default Qwen 1.7B model, plus Voicebox 0.5's own "orphaned" jobs) keeps every later narration at "Generating…" forever, which looked like SceneForge failing. SceneForge now checks Voicebox's history first: if earlier jobs have been active for more than 10 minutes it says so instead of queueing behind them, the Voicebox card shows how many are stuck, and **Clear stuck Voicebox jobs** cancels them through Voicebox's own cancel endpoint (which also clears orphaned jobs).
- SceneForge no longer leaves its own jobs behind: a narration that does not finish in time (10 minutes, more for long text, up to 45) is cancelled in Voicebox. If Voicebox is still loading or downloading a model after 2 minutes, SceneForge stops waiting, says so and leaves the download running in Voicebox.
- **"No voice model downloaded" for CustomVoice voices** (beta.5): when Voicebox does not report a downloaded model for a voice, SceneForge now still asks for the voice's own engine (Voicebox may know better) instead of refusing; it still prefers a model Voicebox reports as loaded or downloaded, and says so when one is being downloaded.
- Errors name the voice, engine and model size that were requested.
- `scripts/voicebox-diagnose.ps1`: a read-only Windows check that lists Voicebox's voices, models, recent jobs and stuck jobs into `voicebox-report.txt`; `-ClearStuck` cancels stuck jobs and `-Test "voice name"` makes one short test narration directly in Voicebox. Checked with PowerShell 7 against a stand-in that answers like Voicebox 0.5.0. Windows PowerShell 5.1 fixes after the owner's first run: voices printed as "System.Object[]" and a text-shortening error.
- Tests: stuck-job report, card count and clearing, loading-model and never-finishing jobs, CustomVoice voices without a reported model (`test_builtin_voices.py`).

## 0.9.4-beta.5 — Chatterbox, Stable Diffusion and Voicebox on the owner's PC (October 13, 2026, beta pre-release)

- **Chatterbox: "TypeError: 'NoneType' object is not callable".** Chatterbox's audio watermark (resemble-perth) imports `pkg_resources`, which ships with setuptools. The Docker image had setuptools; the private Python environment that uv creates does not, so the watermark failed to import and Chatterbox crashed while loading. Chatterbox's requirements now include `setuptools<81` (reproduced here: `import pkg_resources` fails in a fresh uv environment and works after this). Engines installed by beta.3/beta.4 get their packages updated automatically before they start, and **Start** or **Install** in AI Engines now restarts an engine whose model failed, instead of reusing it. A failed engine is no longer shown as Ready. The error no longer points to the Docker-era DIAGNOSE_VOICE.bat.
- **Stable Diffusion slow / never usable:** the Docker engine always used the NVIDIA (CUDA) build of PyTorch, while the new engines used the processor unless the graphics-card option was ticked, and in beta.3 that tick was not saved. Now, when no choice was saved and an NVIDIA driver is installed, the graphics card is used; an installer checkbox left unticked means "detect". AI Engines says when an NVIDIA card is present but the engines run on the processor and offers the switch. Setup progress is now per engine ("1,800 MB of about 5,500 MB downloaded", then "loading it into memory"); before, it showed the total of every model folder under the wrong engine's name.
- **Voicebox never finished ("still generating after 15 minutes"):** Voicebox's /generate uses its Qwen 1.7B model unless told otherwise and, if that model is not on disk, downloads several GB in the background first. SceneForge now asks Voicebox which models are downloaded (GET /models/status) and uses one that fits the voice (loaded first, then the largest downloaded), passing the model size too. If none is downloaded, it says which to download in Voicebox → Models instead of waiting.
- Tests: Chatterbox setuptools requirement and automatic package update, per-engine download size, NVIDIA default and kept choice (`test_managed_ai.py`); Voicebox model choice and no-model message (`test_builtin_voices.py`).

## 0.9.4-beta.4 — owner's local test of beta.3 (October 13, 2026, beta pre-release)

- **NVIDIA option did not stay ticked.** "Use my NVIDIA graphics card" was only kept in the window and the next status refresh (every 2.5 s) cleared it. It is now saved. It also covers voices now, says when no NVIDIA driver is found, and when engines were installed for the other choice it offers **Switch to the graphics card / processor**, which replaces only PyTorch (the models are kept). An engine always starts on the device its installed PyTorch build supports, so a processor build is never asked to use the graphics card.
- **Voicebox:** connecting works when Voicebox is open but has no voices yet: the card and the voice list say to create, clone or add a preset voice in Voicebox → Voices, instead of showing an error. Generation was fixed against Voicebox's real API (checked in the 0.5.0 and 0.6.0 sources): Voicebox queues a generation and returns at once, so SceneForge now waits for it to finish before fetching the audio (it fetched too early before), and passes each voice's own engine (Voicebox otherwise uses Qwen, which rejects Kokoro and other preset voices). Voices show their names; Voicebox's own error text is shown when it refuses. **Check again** now visibly checks (spinner, then the time), says why Voicebox was not found (nothing answering, not replying in time, or something else on that address) and which address it tried, and the address can be changed when Voicebox runs on another port or computer.
- **Insert a picture between two parts:** dropping media near the edge of a part already inserted a new part, but nothing showed where it would go. A marker now shows **Insert as a new part here** at either edge and **Add to Part‑N** in the middle, and dragging a part shows **Move here**. Right-click a part for **Insert picture or video before… / after…**.
- **Timeline edit tools looked broken:** Select, Track select, Ripple, Roll, Slip, Slide and Blade edit music and sound clips on A3–A8, so with no sound clips nothing happened. Picking a tool now says what it does and, when there are no sound clips, how to add one. **Blade also cuts parts on the Picture track where you click.**
- **Narration first:** Motion, Effects and Text show a tip when a part has no narration yet (its length is still a placeholder), with a link to Voice & narration. Render, export, draft-preview and voice errors now add a "What to do" line under the original message (for example, add the narration first, render the scene first, start the engine, re-import a missing file). The reported error itself could not be reproduced here: effects, old-film sound, typewriter sound, glitch and Ken Burns motion before narration all rendered for pictures and videos, and narration added afterwards also rendered.
- Tests: `tests/browser/owner_beta4.cjs` (tip, tools, Blade, insert marker and menu, NVIDIA option kept after refresh and reopening), Voicebox checks in `test_builtin_voices.py` against a stand-in that behaves like Voicebox 0.5.0 (queued generation, Qwen default, empty voice list), NVIDIA option and PyTorch build switch checks in `test_managed_ai.py`.

## 0.9.4-beta.3 — voices without Docker, setup screen, layout audit (October 12, 2026, beta pre-release)

- **No Docker anywhere.** Stable Diffusion and Chatterbox now install with one click into SceneForge's own folder: SceneForge downloads uv (pinned, checksum-checked), which sets up a private Python 3.11 and the engine's packages, then runs the same engine on the same port. No administrator rights, no separate programs. Engines installed earlier in Docker Desktop still start.
- **Kokoro built in:** English, Spanish, French, Hindi, Italian and Portuguese voices run inside SceneForge on the CPU (Kokoro-82M through ONNX Runtime). **Download voices** fetches about 120 MB once (checksum-checked).
- **Gemini voices (cloud):** Google's text-to-speech with a free AI Studio key; 30 voices that speak 100+ languages including Arabic. Speaking speed is applied after generation.
- **Voicebox (optional):** if the free Voicebox app is open, its voice profiles (including cloned voices) appear as a narration engine through its local API.
- **Voice & narration** shows four cards (Kokoro, Chatterbox, Gemini voices, Voicebox) with one clear action each: Download, Install, Start, Add free key or Use.
- **AI provider list:** each provider is a clear dropdown row with a badge, a Connected / Not connected pill and a round chevron that turns when open; the account or key link moved inside.
- **Setup screen:** while engines install, a full progress screen shows the percentage, each tool's state, and a tour of SceneForge features with real screenshots and tips. **Keep working** shrinks it to a corner badge with a progress ring. The Windows installer now only records your choices (and adds Kokoro); the downloads happen in this screen on first start, so installing SceneForge stays quick.
- **Layout audit:** a new browser check (`tests/browser/layout_audit.cjs`) tries 1920×1080, 1536×864, 1366×768, 1280×720 and 1100×650 with the timeline and Free timeline at default, maximized and minimized heights. It found 15 cases where tabs, the preview or the timeline bar were squeezed or cut off; all now pass: the idle Motion/Effects draft panel is one line instead of 150 px, the maximized timeline leaves room for the preview and narration, smaller default timeline heights on small windows, slimmer editor bars on short screens, and the minimized Free timeline no longer pushes its bar off screen. The Free timeline now scrolls as one piece: its track area used to scroll separately from the track names, which could slide clips under the time ruler and out of line with their labels.
- Tests: `test_builtin_voices.py` (real Kokoro synthesis; Gemini and Voicebox with mocked HTTP), `test_native_engines.py` (real uv download, private Python 3.11, engine start, warm-up and stop), installer queue checks in `test_managed_ai.py`, NSIS page compiled with warnings as errors; CI runs the new tests.

## 0.9.4-beta.2 — owner testing on a second PC (October 12, 2026, beta pre-release)

- **One-click local AI.** AI Engines now lists Whisper, Stable Diffusion and Chatterbox, each with one **Install** button (or **Install all**). SceneForge installs Docker Desktop if needed, downloads the engine and its model, starts it and connects it; installed engines get **Start** and show **Ready** when they answer. No folders, `.bat` files or settings. Using your own AUTOMATIC1111 is now an optional "Advanced" section, and a guessed folder no longer shows as "Folder set" or tries to start. In Media → Generate image, a missing Stable Diffusion shows **Install Stable Diffusion**.
- **Chatterbox "Voice service unavailable" while its container ran:** requests to engines on this computer went through the Windows system proxy (VPN, antivirus web shield, company proxy) and failed. They now bypass any proxy for 127.0.0.1, and the message says whether nothing is answering, the engine is still loading, or it replied unexpectedly. The Start button and the installer share one Docker project, find Docker Desktop even when it is not on PATH, and reuse an engine already running on the port.
- **Captions for songs:** Whisper's voice detector dropped most sung vocals, so a 3:19 song produced two caption clips. When the first pass finds far fewer words than speech or singing would give, SceneForge transcribes again without the detector and keeps the fuller result; a line repeated endlessly over instrumentals is kept at most three times.
- **Laptop screens and small windows:** compact Scene settings tabs and headers below 900 px height (the settings area at 1366×768 grew from about 190 to 270 px), the Free timeline button moved into the timeline toolbar, icon-only timeline buttons where space is short so nothing is cut off from 1366 px wide, and **Maximize timeline**, the Free timeline and window resizing always leave room for the preview.
- **FFmpeg without setup:** the installers already include FFmpeg; `scripts\setup.bat` now downloads a verified copy into `tools\ffmpeg` when it is missing, SceneForge finds it there, and a clear message appears if FFmpeg is missing at all.
- **Search boxes:** one design everywhere (projects, effects, caption styles, stickers, captions, shortcuts, emoji): icon inside the field that lights up while searching, a clear button, Escape to clear, and a live "N found / No matches" count. "1 project" instead of "1 projects".
- Tests: `test_local_engine_proxy.py` (reproduces the proxy failure), song and loop cases in `test_local_transcribe.py`, one-click setup checks in `friendly_editing.mjs`; updated search-box roles in tests.

## 0.9.4-beta.1 — owner remarks on RC3 (October 8, 2026, beta pre-release)

Version labels move to 0.9.4-beta.1 because v0.9.3 is already tagged. Release workflow fix: one draft is created before the parallel builds (they had raced and made two releases, and a beta version was published as a pre-release instead of staying a draft); the release check now also requires the pre-release flag for beta versions. Beta: offered only to users who turned on beta updates. Not yet tested on Windows: installer, Open file location in Explorer, Credential Manager.

- **Creative titles open in their own window.** Overlays → Creative titles → *Video inside text* or *Textured title* opens a dialog with a live preview beside the settings and tabs for Create, Position & size, Frame, Move & green screen and Timing & animation, so nothing needs scrolling. The preview updates as you type; once added, drag the layer on the picture to place it. Existing creative layers have an Adjust button. The rendered *Preview video inside text* now plays inside the dialog instead of behind it.
- **Censor words is easy to find again.** The Audio tab opens with a "Censor words (bleep or mute)" card that jumps to the narration, the video's own sound or a timeline audio clip.
- **Effects tab in four icon categories:** Looks, Old film, Adjust & LUT, More effects; one shows at a time (search still looks through all of them). Looks puts the classic looks (with Original) first, with chips to narrow to Classic, Color filters, Film & lens or Creative. A dot marks a category that is in use.
- **Typewriter is at the top of the Text tab** with a typewriter icon, an On/Off switch and a Settings link to its speed and sound.
- **Download and Open file location** (share window): shows where the video is saved with Copy location, reports what happened under the buttons, and works for any local SceneForge address (127.0.0.1, localhost, any port).
- **Free timeline look:** icon buttons, Render full video highlighted, and no more blue text selection while dragging clips.
- **Projects and other left-side actions no longer stall on a pending Motion/Effects draft:** SceneForge asks *Apply and continue* / *Discard and continue*; Cancel keeps the draft and shows it. Saves still in progress are retried for a few seconds, and a blocked action names the scene that is not saved yet.
- **Freezes under load (reproduced and fixed):** many scene renders at once held the database long enough for other saves to fail ("database is locked") and for the editor to wait. Renders and exports now queue for a limited number of slots, progress updates are written less often, the database waits for its turn instead of failing, and uploads no longer block other requests.
- **Long exports no longer run out of memory:** projects with more than 8 scenes are assembled in batches and then joined; transitions across batch joins are kept, and picture and sound stay the same length.
- Tests: `tests/integration/stress_live_server.py` (30 scenes with looks, old film, adjustments, three text layers each, typewriter, karaoke, stickers, picture-in-picture video, textured and video-inside-text titles, voice takes, music clips, transitions; renders, uploads, export and a Free-timeline export while measuring request times and FFmpeg memory), `tests/integration/test_export_batching.py`; updated editor, share-dialog and four browser harnesses for the new dialogs and categories.

## 0.9.3 RC3 — Director's Desk look (October 7, 2026, not published)

Stage 1 of the new design: the look, with no change in how anything works.

- **Director's Desk is the new default theme**: slate-blue panels, one cyan accent, 7 px rounded buttons and boxes, IBM Plex Sans/Arabic/Mono bundled for offline use (OFL). Graphite Night, Daylight, Midnight Blue and Warm Studio remain under Theme. People still on the old default move to the new look once; a theme chosen on purpose is kept.
- **Icon tabs everywhere**: library tabs (Scenes, Media Pool, Transitions), every menu item, and the timeline edit tools (icons with their shortcut letter).
- **Section shortcuts**: the "Jump to section" dropdown and Go button are replaced by a scrollable row of icon shortcuts that follows the section you are reading.
- **More room for the preview**: one-line narration bar (expands on Expand), a shorter default timeline, compact one-row timeline toolbars on laptop screens, and a wider settings panel so all tabs fit without "More".
- Section headings in Scene settings read as boxes; clips, tracks and dialogs use the same palette.
- Fixes found while restyling: theme switches are instant (no half-dark controls mid-transition); the cyan accent becomes a readable teal on Daylight; Free timeline buttons, fields and clip labels on Daylight were dark-on-dark and are now readable.
- Tests: `frontend/tests/preferences_look.mjs` (default theme and one-time move); updated the theme-default and section-shortcut checks.

## 0.9.3 owner fix — export left out the video (October 7, 2026, not published)

- **Export contained only the text overlay.** When Free timeline is switched on it copies only the scenes that already have media. A scene that gets its picture or video later was never added, and export (which uses the Free timeline, even while you view the original source scenes) silently left it out, including its sound and captions. Export now names the missing scenes and asks: **Add to the end and export**, **Export without them**, **Use Scene assembly instead**, or Cancel.
- Deleting a scene now removes its Free-timeline excerpts. Projects saved before this fix drop those dead excerpts on the next save or export instead of failing; a clip that names an unknown scene is still rejected.
- **Open file location** now works when SceneForge runs in a browser: the local SceneForge server opens the folder (Explorer on Windows). It is limited to exported videos, to this computer, and to the SceneForge page itself.
- New checks: `tests/integration/test_free_timeline_export_coverage.py` and `tests/browser/free_export_choice.cjs` (added to the browser suite).

## 0.9.3 release-candidate review — October 7, 2026 (not published; awaiting owner approval)

- Merged the handoff's warmup diagnosis into the newer GitHub baseline (ab85c7f): HTTP 404/405 from `POST /warmup` is reported as an older or different engine on that port, is never retried, and never blames the model download. Kept the explicit status check so an incompatible engine can never be reported ready (a first merge attempt regressed this; caught by `test_managed_ai.py` and fixed).
- Added `test_managed_ai_warmup.py` to CI and the crash-log review document.
- Made the Arabic-first RTL caption check tolerant of 1–3 px HarfBuzz/libass placement differences, and added a control so it still fails if the Latin word is not at the left edge. The rendered caption was inspected visually and is correct.
- Updated the stale `test_designer25` provider mock (`state` field) and made the nine legacy `*_live.py` harnesses portable (repository fixture path and `SF_LIVE_DATA_DIR` instead of hard-coded machine paths).
- Verification only on Linux. Windows installer, native Windows credential store, GPU and real model downloads remain untested.

## 0.9.3 source recovery — October 5, 2026 (not published)

- Reconstructed editor stages from the owner's Stage 1–5 HTML reports and visual review after the earlier source checkpoint was unavailable. This is a fresh implementation, not a recovered copy of the lost commits.
- Atomic Motion/Effects drafts and real render previews; Apply, Cancel, retry and shared Undo/Redo, with isolated preview metadata.
- Inspector sections and scope labels, laptop toolbar wrapping, keyboard menu navigation, light-theme caption readability and a fixed Text preview footer.
- Shared plane/ship/car/pin artwork, destination preview, four additional movements and centered zoom correction.
- Script import opens the first new scene; AutoCut source thumbnails and scrub preview; effective GIF size/rate and project-FPS export labels.
- Version alignment and offline release/archive gates; Windows, native vault and installer validation remain pending.

## Prepared: caption emoji and access review — October 4, 2026
- All 322 bundled caption emoji, colour browsing, category/search and removal.
- Effects shortcuts and search across additional groups make vignette/bars/sharpen and map route easier to find.
- Route appearance presets, Add stop, Reverse journey, coordinates, keyboard editing/removal and shared Undo/Redo.
- Selected overlay controls precede the sticker catalogue; section shortcuts and readable narrow-panel layout.
- Fixed old effect save responses replacing newer local edits; route editing handles appear only in Effects.
- Source review only; another build/checkpoint ZIP requires the owner's OK.


## 0.9.3 — Companion preview, caption emoji and censorship (unreleased)

- Move independent video/image/text draft previews beside the main monitor. Keep controls in Media/Text with Minimize, Restore and Close; preserve unsaved drafts. Use the current scene still as the placement backdrop.
- Add per-caption timed colour emoji from bundled artwork, left/right placement, persistence and export rendering.
- Add source-timed Bleep/Mute ranges for narration, video sound and timeline audio. Offer reviewed English/Arabic word matching from a linked narration transcript, with no new provider calls. Preserve source timing across trim/split; timeline censorship shares Undo/Redo.
- Add adjustable edge vignette, cinema bars and detail sharpening in a styled Finishing touches group; support render, stack order/bypass and portable presets.
- Verify real audio samples, rendered emoji timing, individual effect pixels/bypass, and browser controls. No new build or ZIP: owner approval is required before packaging.

## 0.9.3 — Combined owner-review adjustments (unreleased)

- Stack actual videos on the six overlay tracks, with source trim, placement, muted-by-default sound, playback and export mixing. Preserve source position across splits and skipped empty scenes.
- Group Audio controls and add listening options, narration mute, cleanup and music mix presets, precise timeline audio start, duplication and soft fades. Keep existing processing and Undo/Redo.
- Add optional Script → Scenes setup using selected media or connected local engines, narration, caption boxes or local transcription, styles, motion and rendering. Retain editable scenes on failed steps and restore completed setup on Redo without regenerating.
- Retain AutoCut timeline marker fixes, grouped speed controls and accurate Saved / Apply changes feedback. Improve light-theme control contrast.
- Validate frontend, real browser workflows and real FFmpeg video layers. No Windows validation or installed-model generation is claimed. Combined build awaits the owner’s OK; Sections E and F remain pending. See `STATUS_v0.9.3_COMBINED_REVIEW.md`.

## 0.9.3 — AutoCut marker-source adjustment (unreleased)

- Include ordinary timeline markers in AutoCut as a separate counted source, and select them by default when no detected beat markers exist. Keep music/audio detection and detected beat markers available. Explain that pictures are the media being cut while audio supplies detected beats.
- Verify manual-marker preview, exact clip durations, Apply and Undo in Chromium; also verify generated script scenes open and accept media.

## 0.9.3 — Section D checkpoint (unreleased)

- Add local video stabilization using FFmpeg deshake, with a movement-range slider, matching rendered preview/export, and Undo/Redo.
- Add AutoCut preview and a single undoable picture-sequence edit using timeline beat markers or locally detected music beats. Preserve scene length, narration, captions and overlay timing; respect Picture locks and reject stale previews.
- Add reusable project templates stored locally, available in the editor and on the Projects page. New projects receive independent IDs and remapped media references; templates survive deletion of the source project.
- Add Script → Scenes: TXT/Markdown files or pasted text, English/Arabic headings or blank-line paragraph splitting, editable narration preview, and batch Undo/Redo when appending scenes. Preserve original text and citation references.
- Add real API/render regressions and Chromium coverage; keep all previous features and source versions pending the final release step.

## 0.9.3 — Windows review fixes (unreleased)

- Read captions from a short filename in each FFmpeg subprocess's temporary folder, addressing the 279-character subtitle paths in the owner's Windows failure logs without changing project data locations or the global working directory.
- Darken beige caption boxes and fix caption-number/action contrast in both themes.
- Add sliders with exact values and a live draft preview before Apply changes for independent image/text clips.
- Style both text-card groups and explain whole-video clips versus scene titles with animation/keyframes. Preserve all earlier tools.
- Add deep-path/concurrent-render and browser contrast/draft-preview regressions. See `STATUS_v0.9.3_REVIEW_FIXES.md` for validation and the Windows retest.

## 0.9.3 — Release verification checkpoint (unreleased)

- Add a final tagged-release job that waits for the build matrix and checks the actual draft's Windows installer, blockmap and update metadata, plus the Linux AppImage, deb and update metadata.
- Fail verification for missing, duplicate, empty or unfinished uploads; match installer names to the desktop version and its existing electron-builder configuration. Reject already-published releases.
- Retain Windows blockmaps in downloadable workflow artifacts and add offline release-gate regressions to normal CI.
- Report readiness in the workflow summary without publishing or changing the draft. Windows and Linux build/installed-app tests must also pass.

Section C is implemented and tested offline. Its live GitHub run awaits an approved tag/build. Sections D–F remain pending; the earlier image/text overlay changes still need the owner's Windows review. Product versions remain unchanged until final release preparation.

## 0.9.3 — Independent overlay checkpoint (unreleased)

- Add up to six image/text tracks above the existing captions, picture and audio lanes. Files dropped on these tracks are independent overlays, with their own timing, rather than replacement scenes.
- Add images at the playhead with a real file picker; drag images from Media Pool or local folders onto an upper track.
- Add draggable Text, Text box and outlined Text+ cards inside Text → Text overlays. Click a card to insert it at the playhead.
- Move clips freely in time and between overlay tracks, trim either edge, and drag image/text placement in the preview.
- Add actual text, font, alignment, colour, size, timing, track, width, placement, rotation and opacity controls, with short help and Apply changes. Save pending edits before a restore point or export.
- Preview and full export use the same text rasters. Layers span scenes; skipped empty starter scenes retain placement over the intended footage.
- Support Undo/Redo, copy/cut/paste, duplicate, split and delete for overlay clips. Show working shortcuts in the Help list and clip menu.
- Give timed captions beige boxes with readable text in the timeline and editor; preserve caption render styles.
- Add real FFmpeg/API and Chromium regression checks without removing or relaxing earlier tests.

Sections C–F remain pending. The owner reported the A–B Windows smoke checks passed; this overlay checkpoint still needs their Windows review.

## 0.9.3 — A–B checkpoint (unreleased)

- Empty scene blocks on the timeline open an image/video file picker. Multiple files are added to that scene through the existing undoable upload operation.
- Title cards keep their controls open during editing. Dismissal uses Cancel, the close button, Escape, or a click directly on the backdrop. Keyboard focus stays in the dialog.
- Video inside text uses YOUR TITLE on a neutral card, with a PARIS / 1969 example and matching placeholder. The backend render behaviour is unchanged.
- Text keyframe guidance describes the working X, Y and Font size controls. Image overlays retain preview dragging.
- Keyboard shortcuts are searchable under Help, Ctrl+/ and ?. Real shortcut labels appear in menus, tooltips and context menus; S splits and C selects the blade tool.
- Add Ctrl+A selection, M markers, Ctrl+S restore points, Ctrl+E export settings and +/- timeline zoom. Undo/redo retain their existing handlers. Typing and open dialogs block editor shortcuts.
- Add a real Chromium/FastAPI regression test and run it in CI, alongside the existing frontend and backend checks.

Sections C–F of the owner’s request are still pending. Product version numbers remain at their supplied values until the final release preparation.

## M1.1 — user-reported fixes and UX improvements (post-M1 alpha feedback)

Based on real Windows testing feedback. Verified live against a running
backend (see `tests/integration/test_m1_1_fixes_live.py`, 4/4 checks pass).

### Fixed
- **Silent audio on generated parts** — a newly created or uploaded voice
  take required a separate explicit "Use this take" click before it would
  actually be included in a render; skipping that step produced a
  technically valid but silent video (normal-looking player controls, no
  sound). Voice takes are now auto-accepted immediately on creation.
- **Fixed-duration timing mode did nothing** — the `requested_duration_ms`
  field existed but the renderer always used narration-driven duration
  regardless of `timing_mode`. Fixed mode now genuinely overrides
  narration length (verified: a part with ~1.5s of narration and a fixed
  duration of 3000ms renders at exactly 3.00s).
- **Cache invalidation didn't track duration settings** — changing
  `timing_mode`/`requested_duration_ms` didn't mark a part stale.
- Script text could be silently lost if a project refresh (triggered by
  an unrelated action in a different part) landed before an unsaved
  textarea's `onBlur` fired. Fixed with debounced auto-save plus
  save-aware sync that never overwrites text you're actively typing.
- Job progress (Generate / Export) could get stuck showing stale
  "queued"/"5%" forever if the live event stream stalled, even after the
  job actually finished. Added a 2-second polling fallback alongside the
  live stream, plus an automatic project refresh on job completion.

### Added
- **Duration control UI** — choose "Audio-driven" or "Fixed length" per
  part, with a seconds input for fixed mode.
- **Download buttons** — explicit "Download this part" / "Download full
  video" buttons with friendly filenames (e.g. `Part-1.mp4`,
  `MyProject-export.mp4`) via a new `Content-Disposition` header on the
  asset stream endpoint (`?download=1`).
- All 8 motion presets (zoom in/out, close-up, 4-way pan, static) are now
  always visible in the Image-to-video grid — no more hidden toggle.
- Effect tiles now preview the actual FFmpeg-equivalent CSS filter on
  your real uploaded thumbnail instead of a flat gray swatch (clearly
  labeled as a browser-side preview aid; the rendered clip after Generate
  remains the authoritative result).
- Expanded font list (common Windows system fonts added alongside the
  two bundled, shaping-correct Noto Arabic fonts).
- Visual polish: lucide-react icons throughout (replacing emoji),
  hover/shadow/transition refinements.

### Known open item
- Export appearing stuck at a low percentage for a long time was
  reported but not yet root-caused against the reporter's exact project
  — the leading hypothesis is that it's genuinely re-rendering multiple
  stale parts sequentially (slow, not broken), consistent with the
  "individual part render is slow" report in the same feedback. Needs
  the reporter's `/api/jobs/{id}` status/error payload to confirm.

## M1.2 — Windows-tester round 2 fixes

Verified live (see `tests/integration/test_m1_2_fixes_live.py`, 5/5 checks
pass; espeak-ng-missing scenario verified by temporarily removing the
binary and confirming a clean error instead of a crash).

### Fixed
- **Unhandled crash when espeak-ng isn't installed** — `subprocess.run`
  raises `FileNotFoundError` (not a nonzero return code) when the
  executable is missing; this was never caught, producing a raw
  traceback and a generic "Internal Server Error" in the browser instead
  of a clear message. Now raises a clear, actionable error naming the
  install link, for both local-TTS narration and voice preview/audition.
  The same defensive handling was added to the ffmpeg/ffprobe subprocess
  wrappers themselves.
- **Blank page after creating a new project, fixed only by reloading** —
  `POST /api/projects` returns the new project without its (auto-created)
  scenes list; the frontend set state directly from that response and
  then crashed rendering `project.scenes.map(...)` on `undefined`. Fixed
  by fetching the full project detail (with scenes) before switching into
  the editor.
- **"Generate" looked permanently frozen on longer/slower renders** — for
  a single-shot part, progress only updated at the start and end of the
  entire FFmpeg encode, with nothing in between; a slow render (expected
  on CPU-constrained machines, especially at full 1080p) was
  indistinguishable from a hung one. Progress is now parsed from FFmpeg's
  own `-progress` output in real time during the encode and mapped into
  the job's overall progress, so the bar genuinely moves.
- Added a React error boundary so a future UI crash shows a clear message
  and reload button instead of a silent blank page.

## M1.3 — delete-scene crash fix

Verified live (`tests/integration/test_delete_scene_fk_fix_live.py`,
confirmed passing): deleting a part that had ever been rendered (i.e. had
any associated RenderJob row) crashed with a SQLite foreign-key
constraint violation — `RenderJob.scene_id` had no cascade behavior, so
the scene's row couldn't be removed while a job still referenced it.
Fixed by detaching (not deleting) associated job rows before removing
the scene, preserving job history while allowing the delete to succeed.

### Open investigation — render appears to hang indefinitely for one tester
A tester reported "Generate" never completing across multiple attempts
(5s and 10s fixed duration, with and without narration, Close-up motion).
This was not reproduced or root-caused this session — the M1.2 real-time
progress fix was verified working in this development environment, but
that does not rule out a genuine hang specific to the tester's Windows
setup (antivirus interference with the FFmpeg subprocess, a Python
subprocess line-buffering difference on Windows pipes, or a slow/atypical
FFmpeg build are all plausible but unconfirmed). Needs: Task Manager
confirmation of whether ffmpeg.exe is actively consuming CPU during a
"stuck" render, and a minimal isolation test (Static motion — no
zoompan — at a short fixed duration) to determine whether the zoompan
filter specifically is the bottleneck or something more fundamental.

## M1.4 — static motion fast path (major performance fix)

Verified live at full 1920x1080 (`tests/integration/test_static_fastpath_live.py`):
a 5-second "Static (no motion)" render went from **~100+ seconds to 2.0
seconds** — a ~50x speedup, confirmed end-to-end through the real API.

### Root cause
"Static (no motion)" was still being routed through the full animated
zoompan filter with the zoom pinned at 1.0 — meaning it paid the exact
same expensive per-frame swscale cost (including a large upscaled
intermediate frame with headroom for zoom it never used) as an actual
zoom/pan motion, for a result that never moved. This meant the
"minimal isolation test" a tester was asked to run (static motion, short
duration) wasn't actually testing a cheap path at all, undermining the
diagnosis.

### Fix
Static motion now takes a genuinely separate, minimal code path: a
single scale+crop with no zoompan, no animated crop window, and no
oversized intermediate frame. Zoom, pan, close-up, and Ken Burns motions
are unaffected and still use the full animated pipeline (which remains
inherently CPU-heavy — this is a real, measured characteristic of
FFmpeg's zoompan filter, not something this fix addresses).

### What this means for the "generate never finishes" reports
A tester's CPU-usage check (ffmpeg.exe fluctuating 19-21%, not 0%) during
a stuck-looking render is strong evidence the pipeline was working, not
hung — consistent with genuine zoompan cost at full 1080p on their
hardware. With this fix, "Static" parts should now complete in seconds
even at full resolution; Zoom/Pan/Close-up parts remain inherently slower
and this is expected, not a bug — reduce test resolution or expect
render times in the range of a minute or more per part on constrained
hardware until further zoompan-specific optimization work is done.

## M1.5 — the actual fix: removed `zoompan` entirely (major performance fix, all motion types)

Verified live at full 1920x1080 through the real API, with real
narration and captions (`tests/integration/test_motion_performance_fix_live.py`,
6/6 checks pass), plus the full 26-check M1 regression suite re-run
clean with no failures:

- **zoom_in, 5s @ 1080p: ~100s+ → 6.5s**
- **pan_left, 5s @ 1080p: ~100s+ → 6.5s**

### Root cause (this time, actually the root cause)
M1.4 only fixed "Static" motion. Every other motion — zoom in/out,
close-up, all four pans, Ken Burns — still used FFmpeg's `zoompan`
filter, which recreates its internal scaling context on every single
frame. This is a known, well-documented performance characteristic of
`zoompan` in the FFmpeg community, confirmed here by direct
benchmarking: the identical zoom effect took ~100s via `zoompan` and
~2-6s via the replacement below, at the same resolution and duration.

### Fix
Replaced `zoompan` entirely with a three-stage `scale`+`crop` pipeline:
1. One-time cover scale to fill the canvas
2. A `scale` filter with `eval=frame`, animating zoom level per frame
   (confirmed by direct pixel-diff testing to genuinely re-evaluate
   every frame — average pixel difference of 3.19 between first/last
   frame of a 5s zoom, vs 0.012 for a failed same-size-crop-only attempt
   that turned out not to animate at all, since `crop`'s width/height
   expressions are only evaluated once at init, unlike its x/y which do
   support per-frame evaluation)
3. A `crop` to the final constant output size, with per-frame x/y
   implementing pan and focal-point tracking

Same deterministic (focal_x, focal_y, scale) start/end contract as
before — this is a swap of the underlying FFmpeg technique, not a
change to the motion presets or their math. Verified visually (frame
extraction at start/mid/end) that the zoom and pan are genuinely
animating, not frozen.

### What this means
This should resolve the "Generate never finishes" reports for
Close-up/Zoom/Pan motions, which affected every motion type except
Static until now. If a render still takes an unreasonable amount of
time after this fix, please report the specific motion type, duration,
and resolution — this fix directly targets the confirmed root cause
(zoompan), so a persistent slowdown after this would point to a
different, new issue rather than the one already diagnosed.

## M1.6 — new effects, typewriter captions, UI modernization

Verified live (`tests/integration/test_new_effects_and_typewriter_live.py`,
4/4 checks pass; typewriter reveal additionally confirmed by extracting
real frames at 0.3s and 3.5s and visually confirming the caption grows
from "This is a" to the full sentence).

### Added
- **Glitch** effect — RGB-channel split (chromatic aberration) + grain,
  prototyped and visually reviewed before being added.
- **Old Film** effect — heavier desaturated vintage grade + grain +
  vignette, distinct from the existing lighter "Vintage" preset.
- **Typewriter caption reveal** — a new Font-panel checkbox; captions
  reveal progressively (character-by-character, chunked for very long
  text) over roughly the first 3 seconds or 60% of the shot, then hold
  the full text. Implemented as multiple timed ASS dialogue lines, not a
  simulated/cosmetic toggle.
- UI modernization pass: every part-row section (script, media, motion,
  duration, effects, font, voice, generate) now has a proper card
  treatment (soft background, border, consistent padding) instead of
  flat bordered boxes, plus a matching icon in every section header
  (lucide-react). Verified present in the actual built CSS/JS bundles
  served by the backend, not just in source.

### Still open
- AI image generation remains unimplemented pending the user's choice of
  provider (OpenAI, Stability AI, etc.) and their own API key — this is
  an external dependency, not a code task that can proceed further
  without that input.
