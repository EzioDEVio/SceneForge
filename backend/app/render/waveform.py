"""Audio peak envelopes for the timeline and audio editor."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import numpy as np

from app.config import FFMPEG_BIN, PROXIES_DIR

WAVE_DIR = PROXIES_DIR / "waves"
RATE = 4000                      # mono samples per second analysed
MAX_SECONDS = 3 * 60 * 60        # never decode more than 3 hours


class WaveformError(RuntimeError):
    pass


def waveform(asset_id: str, source: Path, points: int = 600) -> dict:
    points = max(50, min(4000, int(points)))
    WAVE_DIR.mkdir(parents=True, exist_ok=True)
    cache = WAVE_DIR / f"{asset_id}_{points}.json"
    if cache.exists() and cache.stat().st_mtime >= source.stat().st_mtime:
        return json.loads(cache.read_text())
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0  # type: ignore[attr-defined]
    try:
        raw = subprocess.run(
            [FFMPEG_BIN, "-hide_banner", "-nostdin", "-loglevel", "error", "-t", str(MAX_SECONDS),
             "-i", str(source), "-vn", "-ac", "1", "-ar", str(RATE), "-f", "s16le", "-"],
            capture_output=True, timeout=120, creationflags=flags, check=True).stdout
    except FileNotFoundError:
        raise WaveformError("FFmpeg was not found, so the waveform could not be drawn.") from None
    except subprocess.TimeoutExpired:
        raise WaveformError("Reading this audio took too long.") from None
    except subprocess.CalledProcessError:
        raise WaveformError("This file has no readable audio.") from None
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if samples.size == 0:
        raise WaveformError("This file has no readable audio.")
    edges = np.linspace(0, samples.size, points + 1).astype(int)
    peaks = [float(np.abs(samples[a:max(b, a + 1)]).max()) if a < samples.size else 0.0 for a, b in zip(edges[:-1], edges[1:])]
    top = max(peaks) or 1.0
    result = {"duration_ms": int(samples.size * 1000 / RATE), "peaks": [round(p / top, 3) for p in peaks], "peak": round(top, 4)}
    tmp = cache.with_name(f"{cache.stem}.{os.getpid()}.{os.urandom(4).hex()}.tmp")
    tmp.write_text(json.dumps(result))
    tmp.replace(cache)
    return result
