# SceneForge Workspace 2.5 — Title designer and framing controls

## Update safely
Stop SceneForge and back up the current app folder. Copy the contents of this release into that folder, replacing application files while preserving `backend/data` and `backend/.venv`. The ZIP excludes both. Run from the app folder:

```powershell
.\scripts\setup.bat
.\scripts\start.bat
```
Refresh with Ctrl+F5. The sidebar must show Workspace 2.5.

## Stable Diffusion
The backend starts your existing Windows AUTOMATIC1111 installation in the background. The default folder is `C:\Users\moham\stable-diffusion-webui` for Mohammed's Windows account (generally `%USERPROFILE%\stable-diffusion-webui`). It runs your existing `webui-user.bat`; retain `--api` in its configuration. It does not install models or modify that environment.

For another folder, set `$env:SCENEFORGE_SD_DIR='C:\your\stable-diffusion-webui'` before running start.bat. Set `SCENEFORGE_SD_AUTOSTART=0` to disable automatic launch. The image drawer polls readiness every five seconds and provides **Start / retry engine**, **Check engine**, and **View startup log**. Controls manage localhost port 7860 only. A ready API may belong to an already-running WebUI. Startup does not necessarily open a browser tab. An occupied port is never killed or replaced. A timeout is reported after five minutes; retry will not duplicate a still-running process. Close/restart the failed WebUI yourself if its log calls for that.

## Crop and focal motion
Under Motion, each crop percentage and start/end focal value has a slider, numeric input, and reset. Crop sliders stay inside the image. Drag the crop rectangle to move it; drag its lower-right handle to resize. Click each focal image to position its marker. Choose **Apply crop** and **Apply focal movement** to save.

**Preview movement** shows a two-second motion sketch from the source image, without the final crop/effects. Render the scene to verify exact framing. Zoom remains limited to the existing 1–1.5 range. These controls target image framing, not video trim handles.

## Title designer
Scenes → **Add title card** opens a wider designer with Chapter, Lower third, Typewriter, and Headline presets. Choose English/Arabic text, either bundled font, bold, size, color, alignment, position, outline, shadow, solid/gradient background, and a duration from 0.5–60 seconds.

Animations: none, fade, slide from left/right/bottom/top, zoom, reveal, typewriter, blur, and a brief glitch skew. Entrance and exit fade timing are configurable; remaining duration is hold time. Short clips clamp animation timing. Typewriter is visual; caption keystroke sound remains separate.

The layout sketch is approximate. **Play rendered preview** uses the same subtitle renderer as export, at reduced resolution. Create the card to append it to the timeline. Text → Text overlays edits its font, styling, position, animation, entrance and exit timing. Backgrounds are baked into generated images; create a replacement card to change a background. Duration handles still resize image scenes; Undo/Redo supports duration edits.

## Verification and limitations
Production build, existing component checks, real FFmpeg preview encodes for all eleven animations, and Arabic frame checks pass. Windows startup process invocation is mocked here; the actual Windows/GPU environment still requires local verification. This release does not add independent tracks, video trimming, or a full compositing engine. The crop motion sketch intentionally does not replace the final rendered preview.

A real Chromium/backend test also passed: crop and focal settings, motion sketch, Arabic rendered title preview, title creation, image duration drag/undo/redo, full 9.6-second movie export, and transport controls. The Windows launch command and duplicate-process guard passed with mocked Windows process execution.
