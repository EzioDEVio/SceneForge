# SceneForge 0.9.3 — corrected combined source checkpoint

This contains the complete current source and a freshly compiled frontend. It is a source checkpoint, not a Windows installer. Local AI runtimes/models and Python/Node dependencies are not embedded in this ZIP. GitHub Actions builds platform installers separately after the branch push.

## Launch on Windows

Close the old SceneForge process and extract this ZIP into a new folder. Keep your old copy and project data. If Windows offers an “Extract all” destination, choose `C:\Users\moham\Downloads` so the archive's source folder lands at the path below.

With Python 3.12, Node 22.12 or newer, and FFmpeg/FFprobe on PATH, open PowerShell and run:

```powershell
Set-Location 'C:\Users\moham\Downloads\SceneForge-0.9.3-Stability-Corrected'
.\scripts\setup.bat
.\scripts\start.bat
```

Open http://127.0.0.1:8000 and press Ctrl+F5. Run setup for a new source environment. It may install dependencies and rebuild the UI. It does not include a Windows installer or predownloaded AI models.

## Check first

- Change Motion/Effects, switch to Media, then click Free timeline or Render full video. The draft status must direct you to Apply or Cancel; a draft must not be committed automatically.
- After Apply/Cancel, open Free timeline and render. Immediately edited narration should save before continuing. A failed save must show guidance and keep your text.
- Make repeated cuts, move excerpts across tracks, save/reopen, and export. Source assembly retains the original scenes; Free timeline retains its edited excerpts.
- Verify all 19 fonts, text overlays, Video inside text preview, captions, map route labels, AutoCut and audio censoring.
- Retry local-AI setup. If an older Chatterbox service uses port 8881 and lacks model setup, stop that engine in Docker Desktop, then Retry. Existing downloads are retained.

The source stability/stress review is `docs\STABILITY-REVIEW-2026-10-06.md`. Windows installation, NVIDIA execution and real model downloads still need native testing. `BUILD_INFO.json` identifies this archive; `CHECKPOINT_CONTENTS.json` contains per-file hashes.
