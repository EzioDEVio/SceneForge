"""Word timing for word-by-word captions, measured from the narration audio.

The voice engines do not report when each word is spoken, so SceneForge finds
where the voice is actually speaking (short-time energy) and where it pauses,
then shares the words out over the spoken parts only, by word length. The
highlight therefore waits during pauses and ends exactly when the voice ends,
whatever the scene length, engine or language.
"""
from __future__ import annotations

import os
import subprocess

import numpy as np

from app.config import FFMPEG_BIN

RATE = 8000
FRAME_MS = 20
MIN_PAUSE_MS = 220      # shorter gaps are breaths inside a phrase
MIN_SPEECH_MS = 60


def voiced_segments(path: str, in_ms: int = 0, out_ms: int | None = None) -> list[tuple[int, int]]:
    """Spoken spans in ms, relative to the (trimmed) clip start."""
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0  # type: ignore[attr-defined]
    args = [FFMPEG_BIN, "-hide_banner", "-nostdin", "-loglevel", "error", "-ss", f"{in_ms / 1000:.3f}", "-i", path]
    if out_ms is not None:
        args += ["-t", f"{max(0, out_ms - in_ms) / 1000:.3f}"]
    args += ["-vn", "-ac", "1", "-ar", str(RATE), "-f", "s16le", "-"]
    try:
        raw = subprocess.run(args, capture_output=True, timeout=120, creationflags=flags, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
    hop = RATE * FRAME_MS // 1000
    n = a.size // hop
    if n == 0:
        return []
    rms = np.sqrt((a[: n * hop].reshape(n, hop) ** 2).mean(axis=1))
    loud = np.percentile(rms, 95)
    if loud <= 1e-4:
        return []
    voiced = rms > max(loud * 0.08, 0.004)
    segs, start = [], None
    for i, v in enumerate(np.append(voiced, False)):
        if v and start is None:
            start = i
        elif not v and start is not None:
            segs.append([start * FRAME_MS, i * FRAME_MS])
            start = None
    merged: list[list[int]] = []
    for s, e in segs:
        if merged and s - merged[-1][1] < MIN_PAUSE_MS:
            merged[-1][1] = e
        else:
            merged.append([s, e])
    return [(s, e) for s, e in merged if e - s >= MIN_SPEECH_MS]


def word_starts(weights: list[float], segments: list[tuple[int, int]]) -> list[int]:
    """Start time (ms) of each word: cumulative word weight mapped onto the
    spoken time only, skipping pauses."""
    total_voiced = sum(e - s for s, e in segments)
    total_w = sum(weights) or 1
    starts, acc = [], 0.0
    for w in weights:
        target = acc / total_w * total_voiced
        for s, e in segments:
            if target < e - s:
                starts.append(int(round(s + target)))
                break
            target -= e - s
        else:
            starts.append(segments[-1][1])
        acc += w
    return starts
