"""Old-film damage: scratches, dust, hairs and blotches as a looping clip.

The clip is greyscale where 128 means "no change": values above 128 lighten
the picture (white scratches and specks, like damage to the emulsion) and
values below darken it (dust, hairs, dark scratches). The renderer blends it
onto the picture with FFmpeg's `grainmerge` mode (A + B - 128), so the clip
never changes colour, only brightness.

It is generated with NumPy at up to 960 px wide (film damage is soft anyway),
cached on disk, and seeded per scene: renders are reproducible and different
scenes do not share the same scratches. The loop is seamless because every
mark is drawn modulo the loop length.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import threading
import uuid
from pathlib import Path

import numpy as np

from app.config import FFMPEG_BIN

LOOP_SECONDS = 4
MAX_WIDTH = 960
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


class FilmDamageError(RuntimeError):
    pass


def _stamp(frame: np.ndarray, x: float, y: float, radius: float, value: float) -> None:
    """Add a soft round speck (Gaussian falloff) centred at (x, y)."""
    h, w = frame.shape
    r = max(0.6, radius)
    x0, x1 = int(max(0, x - 3 * r)), int(min(w, x + 3 * r + 1))
    y0, y1 = int(max(0, y - 3 * r)), int(min(h, y + 3 * r + 1))
    if x0 >= x1 or y0 >= y1:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1]
    frame[y0:y1, x0:x1] += value * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * (r * 0.6) ** 2))


def generate_frames(width: int, height: int, fps: int, scratches: float, dust: float, seed: int) -> np.ndarray:
    """Return uint8 frames (n, h, w), 128 = no change. Amounts are 0..1."""
    rng = np.random.default_rng(seed)
    n = LOOP_SECONDS * fps
    scale = width / 960.0
    delta = np.zeros((n, height, width), dtype=np.float32)

    # --- vertical scratches: persist 0.4-2.5 s, drift slowly, wobble -------
    if scratches > 0:
        count = int(round((0.6 + 5.0 * scratches) * LOOP_SECONDS / 1.2))
        rows = np.arange(height)
        for _ in range(count):
            start = rng.integers(0, n)
            life = int(rng.uniform(0.4, 2.5) * fps)
            x = rng.uniform(0.04, 0.96) * width
            drift = rng.uniform(-0.25, 0.25) * scale
            wobble = rng.uniform(0.3, 1.6) * scale
            thick = rng.choice([0.8, 1.2, 1.8]) * scale
            bright = rng.random() < 0.75                       # most scratches are white
            level = rng.uniform(0.5, 1.0) * (0.6 + 0.6 * scratches) * (1 if bright else -0.85)
            # brightness varies along the scratch, and some only cover part of the frame
            profile = np.convolve(rng.uniform(0.4, 1.0, height + 40), np.ones(40) / 40, "same")[20:20 + height]
            if rng.random() < 0.3:
                a, b = sorted(rng.uniform(0, height, 2))
                profile = profile * ((rows >= a) & (rows <= b))
            phase = rng.uniform(0, 6.28)
            for k in range(life):
                f = (start + k) % n
                if rng.random() < 0.08:                         # scratch drops out for a frame
                    continue
                cx = x + drift * k + wobble * np.sin(k * 0.7 + phase)
                cols = np.arange(max(0, int(cx - 3 * thick)), min(width, int(cx + 3 * thick) + 1))
                if not cols.size:
                    continue
                weight = np.exp(-((cols - cx) ** 2) / (2 * (thick * 0.7) ** 2))
                delta[f][:, cols] += (level * rng.uniform(0.7, 1.0)) * profile[:, None] * weight[None, :]

    # --- dust: new specks every frame, mostly dark; occasional blotch ------
    if dust > 0:
        for f in range(n):
            for _ in range(rng.poisson(1.0 + 18.0 * dust)):
                dark = rng.random() < 0.7
                _stamp(delta[f], rng.uniform(0, width), rng.uniform(0, height),
                       rng.uniform(1.0, 3.4) * scale, rng.uniform(0.5, 1.1) * (-1 if dark else 0.9))
            if rng.random() < 0.05 * dust:
                cx, cy = rng.uniform(0, width), rng.uniform(0, height)
                for _ in range(rng.integers(4, 10)):              # irregular blotch
                    _stamp(delta[f], cx + rng.normal(0, 5 * scale), cy + rng.normal(0, 5 * scale),
                           rng.uniform(2.5, 6) * scale, -rng.uniform(0.3, 0.6))

        # --- hairs: thin curly dark strands held in the gate for a few frames
        hairs = rng.poisson(0.7 * dust * LOOP_SECONDS)
        for _ in range(hairs):
            start, life = rng.integers(0, n), int(rng.integers(3, 12))
            x, y = rng.uniform(0.05, 0.95) * width, rng.uniform(0.05, 0.95) * height
            angle, points = rng.uniform(0, 6.28), []
            for _ in range(int(rng.integers(25, 70) * scale) + 5):
                angle += rng.normal(0, 0.18)
                x, y = x + np.cos(angle) * scale, y + np.sin(angle) * scale
                points.append((x, y))
            level = -rng.uniform(0.45, 0.85)
            for k in range(life):
                f = (start + k) % n
                jx, jy = rng.normal(0, 0.4 * scale, 2)
                for px, py in points:
                    _stamp(delta[f], px + jx, py + jy, 0.7 * scale, level * 0.6)

    return np.clip(128 + delta * 110, 0, 255).astype(np.uint8)


def damage_clip(out_w: int, out_h: int, fps: int, scratches: int, dust: int, seed: int, cache_dir: Path) -> str | None:
    """Write (or reuse) the looping damage clip; None when there is nothing to draw."""
    if scratches <= 0 and dust <= 0:
        return None
    w = min(MAX_WIDTH, out_w)
    w -= w % 2
    h = int(round(out_h * w / out_w))
    h -= h % 2
    key = hashlib.sha256(f"v1|{w}x{h}|{fps}|{scratches}|{dust}|{seed}".encode()).hexdigest()[:24]
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = cache_dir / f"damage_{key}.mkv"
    with _locks_guard:
        lock = _locks.setdefault(key, threading.Lock())
    with lock:
        if out.exists() and out.stat().st_size > 0:
            return str(out)
        frames = generate_frames(w, h, fps, scratches / 100, dust / 100, seed)
        tmp = out.with_name(f"{out.stem}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp.mkv")
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0  # type: ignore[attr-defined]
        result = subprocess.run(
            [FFMPEG_BIN, "-y", "-hide_banner", "-nostdin", "-loglevel", "error",
             "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
             "-c:v", "ffv1", "-pix_fmt", "gray", str(tmp)],
            input=frames.tobytes(), capture_output=True, timeout=300, creationflags=flags)
        if result.returncode != 0 or not tmp.exists():
            tmp.unlink(missing_ok=True)
            raise FilmDamageError("The old-film damage layer could not be made.")
        os.replace(tmp, out)
        return str(out)
