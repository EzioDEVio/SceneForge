"""Small cached JPEG thumbnails for images and poster frames for videos.

Used by the Media Pool, scene bin and timeline so they no longer load full
resolution originals (images) or show a generic icon (videos). Thumbnails are
derived data: they live under PROXIES_DIR/thumbs and are regenerated whenever
the source file is newer than the cached file, so deleting the folder is safe.
"""
from __future__ import annotations

import os
import subprocess
import threading
from pathlib import Path

from app.config import FFMPEG_BIN, PROXIES_DIR

THUMB_DIR = PROXIES_DIR / "thumbs"
ALLOWED_WIDTHS = (160, 320, 640, 1280)
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


class ThumbnailError(RuntimeError):
    pass


def poster_offset_s(duration_ms: int | None) -> float:
    """Skip black lead-in frames: 10% into the clip, at most 1 second."""
    if not duration_ms or duration_ms <= 0:
        return 0.0
    return round(min(1.0, duration_ms / 1000 * 0.1), 3)


def _lock_for(key: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(key, threading.Lock())


def thumbnail_path(asset_id: str, source: Path, kind: str, duration_ms: int | None, width: int = 320) -> Path:
    if kind not in ("image", "video"):
        raise ThumbnailError("Thumbnails are available for images and videos only.")
    width = min(ALLOWED_WIDTHS, key=lambda w: abs(w - int(width)))
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    out = THUMB_DIR / f"{asset_id}_{width}.jpg"
    key = str(out)
    with _lock_for(key):
        if out.exists() and out.stat().st_mtime >= source.stat().st_mtime and out.stat().st_size > 0:
            return out
        tmp = out.with_name(f"{out.stem}.{os.getpid()}.{threading.get_ident()}.tmp.jpg")
        args = [FFMPEG_BIN, "-y", "-hide_banner", "-nostdin", "-loglevel", "error"]
        if kind == "video":
            args += ["-ss", f"{poster_offset_s(duration_ms):.3f}"]
        args += ["-i", str(source), "-frames:v", "1",
                 "-vf", f"scale='min({width},iw)':-2:flags=bicubic", "-q:v", "4", str(tmp)]
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0  # type: ignore[attr-defined]
        try:
            result = subprocess.run(args, capture_output=True, timeout=30, creationflags=flags)
        except FileNotFoundError:
            raise ThumbnailError("FFmpeg was not found, so a preview frame could not be made.") from None
        except subprocess.TimeoutExpired:
            raise ThumbnailError("Making a preview frame took too long.") from None
        if result.returncode != 0 or not tmp.exists() or tmp.stat().st_size == 0:
            tmp.unlink(missing_ok=True)
            raise ThumbnailError("This file could not be decoded to make a preview frame.")
        os.replace(tmp, out)
        return out


def graded_frame(thumb: Path, grade_lut: str, key: str) -> Path:
    """Apply a baked grade LUT to a thumbnail: an exact colour preview of the
    render (same LUT, same interpolation), made in a fraction of a second."""
    from app.render.ffmpeg_utils import escape_path_for_filter
    out_dir = THUMB_DIR / "graded"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{key}.jpg"
    with _lock_for(str(out)):
        if out.exists() and out.stat().st_size > 0:
            return out
        tmp = out.with_name(f"{out.stem}.{os.getpid()}.{threading.get_ident()}.tmp.jpg")
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0  # type: ignore[attr-defined]
        vf = f"format=gbrp,lut3d=file='{escape_path_for_filter(grade_lut)}':interp=tetrahedral"
        result = subprocess.run([FFMPEG_BIN, "-y", "-hide_banner", "-nostdin", "-loglevel", "error", "-i", str(thumb),
                                 "-vf", vf, "-frames:v", "1", "-q:v", "3", str(tmp)], capture_output=True, timeout=30, creationflags=flags)
        if result.returncode != 0 or not tmp.exists():
            tmp.unlink(missing_ok=True)
            raise ThumbnailError("The graded preview could not be made.")
        os.replace(tmp, out)
        return out
