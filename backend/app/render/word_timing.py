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


def words_from_alignment(alignment: dict, in_ms: int = 0, out_ms: int | None = None) -> list[tuple[str, int, int]]:
    """Group per-character timings (ElevenLabs) into words: (word, start_ms,
    end_ms) relative to the trimmed clip. Words outside the trim are dropped."""
    words, cur, start, end = [], "", None, None
    for ch, s, e in zip(alignment.get("chars", []), alignment.get("starts", []), alignment.get("ends", [])):
        if ch.isspace():
            if cur:
                words.append((cur, start, end))
            cur, start = "", None
            continue
        if start is None:
            start = s
        cur, end = cur + ch, e
    if cur:
        words.append((cur, start, end))
    out = []
    for w, s, e in words:
        s_ms, e_ms = int(round(s * 1000)) - in_ms, int(round(e * 1000)) - in_ms
        if e_ms <= 0 or (out_ms is not None and s_ms >= out_ms - in_ms):
            continue
        out.append((w, max(0, s_ms), e_ms))
    return out


def _norm(word: str) -> str:
    return "".join(c for c in word.lower() if c.isalnum())


def exact_word_times(caption_words: list[str], spoken: list[tuple[str, int, int]]) -> list[tuple[int, int]] | None:
    """Use the voice's own word timings when the caption says the same words
    (ignoring case and punctuation). Otherwise None, and the caller falls back
    to speech/pause detection."""
    if len(caption_words) != len(spoken) or not spoken:
        return None
    if sum(_norm(a) == _norm(b[0]) for a, b in zip(caption_words, spoken)) < 0.9 * len(spoken):
        return None
    return [(s, e) for _, s, e in spoken]
