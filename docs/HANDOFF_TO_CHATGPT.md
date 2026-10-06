# SceneForge Studio: handoff from Claude to ChatGPT (October 2, 2026)

**Owner:** Mohammed "Ezio" Aldaraji (Silverarmour Solution LLC)
**Repo:** github.com/EzioDEVio/SceneForge
**Licence:** open source, GPL

## 1. Rules the owner set (keep them)

- **Never remove features.** Add to the product and keep everything that works.
- **No fake controls.** Every button must really work.
- **Friendly for regular users.** Use plain words, give every feature short help, and group related controls neatly.
- **Bundle work.** Put many features and fixes into each release, because the owner has limited credits.
- **Use full real Windows paths in instructions, never placeholders.** The owner's repo is at:
  `C:\Users\moham\Downloads\Claude_sceneforge\HAND OVER FROM CHATGPT TO CLAUDE\SceneForge-0.9.1\SceneForge-0.9.1\SceneForge-repo`
- **No paid provider calls or credits during development.** Never read, print or commit API keys or secrets.
- **Never push, merge, tag or publish a release without the owner's explicit instruction.**
- **Ask for the owner’s OK before creating another update build or checkpoint ZIP.** Prepare fixes and run checks first, describe the exact changes, then wait for approval (owner instruction, October 3, 2026).
- **Don't weaken a test just to turn CI green.** Fix the cause.
- **Don't claim a Windows UI test was run unless it really was.** The owner tests on Windows.

## 2. Stack (short)

- **Frontend:** React 18, TypeScript and Vite 7, in `frontend/src`.
  - `App.tsx` is the editor.
  - `ProjectTimeline.tsx` is the multitrack timeline.
  - `KeyframeEditor.tsx` and `keyframes.ts` handle keyframes.
  - `TypewriterPanel.tsx`, `CreativeTools.tsx` (video inside text, textured titles, cutout), `EffectsPanels.tsx` (grouped effects), `TextTemplates.tsx`, `RestorePoints.tsx`, `CaptionsPro.tsx` and `ExportDialog.tsx` hold the feature panels.
- **Backend:**
  - FastAPI, SQLAlchemy, SQLite and FFmpeg, on Python 3.12, in `backend/app`.
  - The API is in `api/`, rendering in `render/`, and the domain logic in `domain/`.
  - AI providers are in `providers/`: local Whisper, espeak, image and video.
- **Desktop app:** Electron 44 and electron-builder 26 in `desktop/`. The backend is frozen with PyInstaller through `desktop_entry.py`.
- **AI that runs on the user's PC:** Whisper (faster-whisper); u2netp, u2net_human_seg and isnet for cutouts; Kim_Vocal_2 for voice isolation. Optional local Docker engines: Kokoro (8880), Chatterbox (8881), Stable Diffusion (7860) and ComfyUI (8188).
- **Cloud AI, only if the user adds a key:** OpenAI, ElevenLabs, Gemini and Veo.
- **CI** runs on GitHub Actions v6 and Ubuntu 24.04:
  - `.github/workflows/checks.yml` runs the backend integration tests, frontend build and tests, and editor browser tests.
  - `release.yml` runs when a `v*` tag is pushed. It builds the Windows and Linux installers into a **draft** release.
- **Docs:**
  - `docs/manual.html` is the full-colour user guide (19 chapters; images in `docs/images/`).
  - `docs/architecture.md`, `docs/TIMELINE_ARCHITECTURE.md` and the release notes `docs/RELEASE_v0.9.x_GITHUB.md`.

## 3. Release history (recent)

| Version | Status | Main changes |
|---|---|---|
| 0.9.0 | Released | Audio waveforms on clips; Typewriter box with keystroke sound; effects in collapsible groups; auto-ducking per clip; restore points; sample project; caption translation; title templates. |
| 0.9.1 | Released | Video inside text (knockout title); fix for the cutout that got stuck; hang watchdog; diagnostics now also save `backend-report.zip`; new README screenshots. |
| 0.9.2 | Released, Windows files missing | Video-inside-text title shrinks to fit the screen and its preview matches; new "put the subject in front" option. See the warning below. |
| **0.9.3** | **In progress on branch `claude/0.9.3`** | See section 4. |

**0.9.2 warning:** the release was published before the Windows build job finished, so its Windows assets (`SceneForge-Studio-Setup-0.9.2.exe` and `latest.yml`) were skipped. The owner was told to download the `SceneForge-Studio-Windows` artifact from Release run #51 and attach both files to the release by hand. Check that he did, and check 0.9.1 the same way.

## 4. Branch `claude/0.9.3`: unpushed, delivered as a bundle in this zip

Commits on top of 0.9.2 (`60faf81`):

1. `ef83fec` fixes a flaky CI failure (main run #122, `test_video_cutout.py`, "cancelled job ends as cancelled"). In `backend/app/api/video_cutout.py`, `_run_job` now saves the final state with `jobs._emit` (to the database) before calling `st.update`. The test passed 3 times out of 3 locally.
2. `4b6c1e4` adds `docs/manual.html`, the full-colour user guide.
3. The handoff commit adds this file and `scripts/promo_clips/` (clip tools, still in progress).

### Still to do for 0.9.3 (see `SceneForge_Roadmap.xlsx`, rows 18–29)

- **Release workflow check (important).** Add a final job to `release.yml` that confirms every expected file is attached before the release is called ready:
  - Windows: the `.exe`, its `.blockmap` and `latest.yml`;
  - Linux: the AppImage, the deb and `latest-linux.yml`.

  Also tell the owner: **don't publish the draft until both jobs are green.**
- **Dependabot:** 3 alerts (2 high, 1 moderate). The owner needs to send a screenshot of the alert list.
- **Code signing.** The recommended options are:
  - Azure Artifact Signing (about $9.99 a month; a US LLC qualifies);
  - SignPath Foundation (free for open source).

  The owner has to create the account and add the secrets; then wire it into `release.yml` for electron-builder.
- **3 open bugs, waiting for the owner's details:**
  - "timeline loading" (is it black, or just slow?);
  - the "this is a text" pictures;
  - "Render/save failed" in part 6.

  Ask the owner for screenshots and a diagnostics zip (Help → Collect diagnostics).
- **Features similar to CapCut, chosen by the owner:**
  - Project templates;
  - AutoCut to the beat (beat markers already exist: `POST /api/projects/{id}/beat-markers`);
  - Script → scenes;
  - Video stabilisation (FFmpeg `vidstabdetect`/`vidstabtransform`, or `deshake`).
- **Later:** turning a long video into Shorts; masks and blend modes; auto-enhance; a free music library.
- **Small correction for the manual and help text:** in the editing preview, text layers can't be dragged; their CSS has `pointer-events:none`. Keyframes for titles are set with the X/Y position, Font size and other controls. Changing one of those at a time with no keyframe adds a keyframe automatically, through `keyframedPatch`. Either fix the wording in `docs/manual.html` and the hint in `KeyframeEditor.tsx`, or add real dragging on the preview.
- Bump the version in `package.json`, `desktop/package.json` and the backend; update `docs/CHANGELOG.md` and the README; write `docs/RELEASE_v0.9.3_GITHUB.md`.

## 5. Promo how-to clips (owner's latest request, partly done)

**Goal:** six short clips for X and other platforms, each in 16:9 and 9:16.

**Done:** `1_keyframes_16x9.mp4` and `1_keyframes_9x16.mp4`, included in this zip under `promo_clips/`. This is an earlier render that doesn't yet end on the full-screen result.

**To do:**
- Clip 2: Typewriter captions on the scene "Into the hills". Turn it on, pick Natural speed, turn on the keystroke sound, Preview sound, then render. Use `grab_audio('/api/scenes/<id>/typewriter-preview', 'tw.wav')` to get the sound.
- Clip 3: Video inside text on "City lights". In the Overlays tab, type "CITY", set the size, click "Add video-inside-text title", then render. Clear the scene's overlays first.
- Clip 4: Caption styles on "Into the hills" (typewriter off). In the Text tab under Caption styles, click Social, try a few styles, end on a karaoke style, then render.
- Clip 5: Title templates on "Meet the storyteller". Remove the STORIES layer first. Click Lower third, type a name and role, then render.
- Clip 6: Vertical export. Click Export video, then "Create vertical 9:16 version", then Open vertical project, then Export with the TikTok preset, and end on the exported MP4.

**Can't be recorded in this kind of sandbox:**
- Auto-captions needs the Whisper model download (blocked here).
- Auto-ducking needs a real voice. The owner may send a voice memo for it.

**Two things to know when recording:**
- Playwright's Chromium has no H.264 decoder. `webm_bridge` in `capture_readme_screenshots.py` converts the previews on the fly.
- Rendering a scene with no narration asks for confirmation; click **Continue**.

## 6. How the owner pushes a bundle (PowerShell)

```
cd "C:\Users\moham\Downloads\Claude_sceneforge\HAND OVER FROM CHATGPT TO CLAUDE\SceneForge-0.9.1\SceneForge-0.9.1\SceneForge-repo"
git fetch "C:\Users\moham\Downloads\SceneForge-handoff\SceneForge-0.9.3.bundle" claude/0.9.3:claude/0.9.3
git checkout claude/0.9.3
git push origin claude/0.9.3
```

When CI is green, merge to `main`. Tag `v0.9.3` only when 0.9.3 is finished. Publish the draft release only after the Windows and Linux jobs are both green.

## 7. Local test commands

- **Backend tests:** `cd backend && python -m pytest tests/integration -q` (run each file with `< /dev/null`).
- **Frontend:** `npm --prefix frontend run build && npm --prefix frontend test`.
- **Editor browser tests:** `tests/browser/*.cjs` and `frontend/tests/editor.mjs`. Effect groups are collapsed by default, so use the `openFxGroups()` helper.
- **README screenshots:** `python scripts/capture_readme_screenshots.py --base http://127.0.0.1:8765`. Use a throwaway data folder, because the script deletes every project.
