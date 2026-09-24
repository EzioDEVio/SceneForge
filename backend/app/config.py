"""Central paths and settings for the SceneForge backend.

All paths are resolved relative to a single DATA_DIR so the whole application
(database, media blobs, render outputs, logs) is portable and can be zipped
for backup/export.
"""
from __future__ import annotations

import os
from pathlib import Path

RESOURCE_DIR = Path(os.environ.get("SCENEFORGE_RESOURCE_DIR", Path(__file__).resolve().parents[2]))

# Root data directory. Overridable via SCENEFORGE_DATA_DIR for tests/CI.
# Defaults to backend/data (this file is backend/app/config.py, so
# parents[1] is backend/).
DATA_DIR = Path(os.environ.get("SCENEFORGE_DATA_DIR", Path(__file__).resolve().parents[1] / "data"))

DB_PATH = DATA_DIR / "sceneforge.db"
MEDIA_DIR = DATA_DIR / "media"           # uploaded / generated source assets
RENDERS_DIR = DATA_DIR / "renders"       # per-part and full-export outputs
PROXIES_DIR = DATA_DIR / "proxies"       # 720p preview proxies
LOGS_DIR = DATA_DIR / "logs"
TMP_DIR = DATA_DIR / "tmp"

for _d in (DATA_DIR, MEDIA_DIR, RENDERS_DIR, PROXIES_DIR, LOGS_DIR, TMP_DIR):
    _d.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{DB_PATH}"

# Upload limits (M1 defaults; configurable later via settings UI)
MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MB per asset
ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
ALLOWED_VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
ALLOWED_AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac"}

# Render defaults
DEFAULT_FPS = 30
DEFAULT_WIDTH_16_9 = 1920
DEFAULT_HEIGHT_16_9 = 1080
PREVIEW_WIDTH_16_9 = 1280
PREVIEW_HEIGHT_16_9 = 720

# Narration padding (ms) baked into each scene's visual/audio track. This is
# the "handle" that lets a later dissolve transition consume silent video
# without ever overlapping two scenes' narration.
DEFAULT_LEAD_MS = 250
DEFAULT_TRAIL_MS = 400

FFMPEG_BIN = os.environ.get("SCENEFORGE_FFMPEG", "ffmpeg")
FFPROBE_BIN = os.environ.get("SCENEFORGE_FFPROBE", "ffprobe")

# x264 preset/CRF for shot and export encodes. "ultrafast" is the M1
# default because the render bottleneck in practice is the zoompan filter
# (per-frame swscale), not the encoder — on constrained/single-core
# hardware, preset barely trades quality for a large speed difference
# here, so we default fast. On a multi-core Windows machine this can be
# raised (e.g. "veryfast" or "medium") via SCENEFORGE_X264_PRESET for
# better compression at the same wall-clock budget.
X264_PRESET = os.environ.get("SCENEFORGE_X264_PRESET", "ultrafast")
X264_CRF = os.environ.get("SCENEFORGE_X264_CRF", "21")

BUNDLED_FONT_PATH = RESOURCE_DIR / "assets" / "fonts" / "NotoNaskhArabic-Regular.ttf"
