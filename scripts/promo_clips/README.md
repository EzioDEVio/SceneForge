# Promo clip tools (work in progress)

These tools make short how-to clips for X, TikTok, Reels and Shorts. They record the real editor in headless Chromium, then edit the recording into two shapes:

- 16:9 at 1920×1080
- 9:16 at 1080×1920

Each clip gets step captions, zooms, a picture-in-picture view, an intro card and an end card.

| File | What it does |
|---|---|
| `rec.py` | Recording harness. It uses a CDP screencast, which gives JPEG frames with timestamps. It draws a pointer and click ripples, moves the pointer smoothly, and adds `caption`/`focus` marks. It also adds `skip_start`/`skip_end` marks to cut waits and `speed_start`/`speed_end` marks to speed up slow parts. `save_result()` downloads the rendered scene, and `grab_audio()` fetches sounds the browser played. |
| `edit.py` | Editing pass. The `CLIPS` dict holds each clip's title and kicker. Its `v` entry holds per-caption overrides: `vfocus` sets the 9:16 framing and `pip` sets the picture-in-picture region. Run it with `python3 edit.py <name> [--only 16x9\|9x16] [--preview SECONDS]`. |
| `reset.py` | Puts the demo project back into a known state before each take. |
| `clip1_keyframes.py` | Clip 1, keyframe animation. This one is finished. |
| `sheet.sh` | Makes a contact sheet so you can review a clip quickly. |

**Before you run them:**
- The scripts expect three things:
  - a backend on `127.0.0.1:8765` that serves a fresh `frontend/dist`;
  - the demo project made by `scripts/capture_readme_screenshots.py`;
  - working folders under `/tmp/claude-0/clips`.
- Edit the paths and the project id in `reset.py` to match your machine.
- The recordings are 1600×900, because the screencast is captured at CSS-pixel size.

**Status:**
- Clip 1 (keyframes) is finished.
- The `result.mp4` end segment and audio mixing in `edit.py` were written last and have not been run yet. Test them on clip 1 first by calling `save_result('Golden hour')` after the render step.
