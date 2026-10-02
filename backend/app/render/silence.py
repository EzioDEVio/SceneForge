"""Silence and filler-word detection for jump cuts ("Clean up").

Silence detection decodes the audio to mono 16 kHz PCM with FFmpeg and measures RMS
level in 10 ms windows with numpy. A run of windows below the threshold that lasts at
least `min_silence_ms` is a silence. Each silence is shrunk by `padding_ms` on every
side that touches speech, so cuts never clip the start or end of a word. Silence at
the very start or end of the audio is not padded on its outer edge.

Filler detection only reads an existing transcript (scene font_json.transcript.words,
[[word, start_ms, end_ms], ...]); nothing is transcribed here.

All functions are pure apart from `decode_mono`; times are integer milliseconds.
"""
from __future__ import annotations

import math
import os
import re
import subprocess

RATE = 16000
WINDOW_MS = 10
THRESHOLD_RANGE = (-60.0, -20.0)
MIN_SILENCE_RANGE = (200, 3000)
PADDING_RANGE = (0, 500)
DEFAULTS = {"threshold_db": -38.0, "min_silence_ms": 600, "padding_ms": 120}
FILLER_PADDING_MS = 40

# Default filler list. "like" and "so" are often meaningful, so they are offered but off.
DEFAULT_FILLERS = ["um", "uh", "erm", "er", "ah", "hmm", "mm", "uhm", "you know", "i mean", "يعني", "اه", "امم"]
OPTIONAL_FILLERS = ["like", "so"]
MAX_FILLER_TERMS = 60


class CleanupError(ValueError):
    pass


def decode_mono(path: str, start_ms: int = 0, duration_ms: int | None = None, rate: int = RATE):
    """Mono float32 samples of the first audio stream (FFmpeg → numpy)."""
    import numpy as np
    from app.config import FFMPEG_BIN
    args = [FFMPEG_BIN, "-nostdin", "-hide_banner", "-loglevel", "error"]
    if start_ms:
        args += ["-ss", f"{start_ms / 1000:.6f}"]
    args += ["-i", path]
    if duration_ms:
        args += ["-t", f"{duration_ms / 1000:.6f}"]
    args += ["-map", "0:a:0", "-vn", "-ac", "1", "-ar", str(rate), "-f", "s16le", "-acodec", "pcm_s16le", "-"]
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0  # type: ignore[attr-defined]
    proc = subprocess.run(args, capture_output=True, timeout=600, creationflags=flags)
    if proc.returncode != 0 or not proc.stdout:
        raise CleanupError("This media has no sound that SceneForge can read.")
    return np.frombuffer(proc.stdout, np.int16).astype(np.float32) / 32768.0


def clean_params(body: dict) -> dict:
    """Validate silence settings (missing values use the defaults). Raises CleanupError."""
    out = {}
    for key, (lo, hi), label in (("threshold_db", THRESHOLD_RANGE, "Threshold"),
                                 ("min_silence_ms", MIN_SILENCE_RANGE, "Minimum silence"),
                                 ("padding_ms", PADDING_RANGE, "Padding")):
        value = body.get(key, DEFAULTS[key])
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value:
            raise CleanupError(f"{label} must be a number.")
        if not lo <= value <= hi:
            unit = " dB" if key == "threshold_db" else " ms"
            raise CleanupError(f"{label} must be between {lo:g}{unit} and {hi:g}{unit}.")
        out[key] = float(value) if key == "threshold_db" else int(round(value))
    return out


def window_levels_db(samples, rate: int = RATE, window_ms: int = WINDOW_MS):
    """RMS level in dBFS of each consecutive window (the last partial window included)."""
    import numpy as np
    size = max(1, rate * window_ms // 1000)
    n = len(samples)
    if not n:
        return np.zeros(0, np.float32)
    pad = (-n) % size
    padded = np.concatenate([samples, np.zeros(pad, np.float32)]) if pad else samples
    frames = padded.reshape(-1, size)
    counts = np.full(len(frames), size, np.float32)
    if pad:
        counts[-1] = size - pad
    rms = np.sqrt((frames.astype(np.float64) ** 2).sum(axis=1) / counts)
    return 20 * np.log10(np.maximum(rms, 1e-9))


def find_silences(samples, threshold_db: float, min_silence_ms: int, padding_ms: int,
                  rate: int = RATE, window_ms: int = WINDOW_MS) -> list[list[int]]:
    """Removable silent ranges [start_ms, end_ms] (already shrunk by the padding)."""
    levels = window_levels_db(samples, rate, window_ms)
    total = int(round(len(samples) * 1000 / rate))
    out: list[list[int]] = []
    run_start = None
    for i, quiet in enumerate(list(levels < threshold_db) + [False]):
        if quiet and run_start is None:
            run_start = i
        elif not quiet and run_start is not None:
            start, end = run_start * window_ms, min(total, i * window_ms)
            run_start = None
            if end - start < min_silence_ms:
                continue
            cut_start = start + (padding_ms if start > 0 else 0)
            cut_end = end - (padding_ms if end < total else 0)
            if cut_end - cut_start >= max(window_ms, 20):
                out.append([cut_start, cut_end])
    return out


def total_ms(ranges) -> int:
    return int(sum(max(0, e - s) for s, e in ranges))


def merge_ranges(ranges, lo: int = 0, hi: int | None = None) -> list[list[int]]:
    """Sort, clamp to [lo, hi] and merge overlapping/touching ranges."""
    cleaned = []
    for r in ranges:
        if not isinstance(r, (list, tuple)) or len(r) != 2:
            raise CleanupError("Each range must be [start_ms, end_ms].")
        s, e = r
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in (s, e)):
            raise CleanupError("Range times must be numbers of milliseconds.")
        s, e = max(lo, int(round(s))), int(round(e))
        if hi is not None:
            e = min(hi, e)
        if e > s:
            cleaned.append([s, e])
    cleaned.sort()
    merged: list[list[int]] = []
    for s, e in cleaned:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return merged


def keep_ranges(cuts, total: int, frame: int = 1) -> list[list[int]]:
    """Complement of the cuts inside [0, total], snapped to frames; pieces under a frame are dropped."""
    snap = lambda v: int(math.floor(v / frame + 0.5) * frame)  # noqa: E731
    keeps, cursor = [], 0
    for s, e in merge_ranges(cuts, 0, total):
        s, e = snap(s), min(total, snap(e))
        if s - cursor >= frame:
            keeps.append([cursor, s])
        cursor = max(cursor, e)
    if total - cursor >= frame:
        keeps.append([cursor, total])
    return keeps


# --- filler words -------------------------------------------------------------------

_TASHKEEL = re.compile("[ؐ-ًؚ-ٰٟـ]")
_PUNCT = re.compile(r"[^\w\s']", re.UNICODE)


def normalize(word: str) -> str:
    text = _TASHKEEL.sub("", str(word)).replace("آ", "ا").replace("’", "'")
    text = _PUNCT.sub(" ", text.lower()).replace("_", " ")
    return " ".join(text.split()).strip("'")


def clean_terms(raw) -> list[list[str]]:
    """User filler list → token sequences (["you", "know"]). None = the default list."""
    if raw is None:
        raw = DEFAULT_FILLERS
    if not isinstance(raw, list) or any(not isinstance(t, str) for t in raw):
        raise CleanupError("words must be a list of words or short phrases.")
    if len(raw) > MAX_FILLER_TERMS:
        raise CleanupError(f"Use at most {MAX_FILLER_TERMS} filler words.")
    terms, seen = [], set()
    for t in raw:
        tokens = normalize(t).split()
        if not tokens or len(tokens) > 4:
            continue
        key = " ".join(tokens)
        if key not in seen:
            seen.add(key)
            terms.append(tokens)
    if not terms:
        raise CleanupError("Add at least one filler word to look for.")
    return sorted(terms, key=len, reverse=True)


def find_fillers(words, terms: list[list[str]], padding_ms: int = FILLER_PADDING_MS) -> list[dict]:
    """Matches of the filler terms in transcript words. Cuts are widened by `padding_ms`
    on each side but never into the neighbouring words."""
    rows = []
    for w in words or []:
        if isinstance(w, (list, tuple)) and len(w) >= 3:
            try:
                rows.append((str(w[0]), int(w[1]), int(w[2])))
            except (TypeError, ValueError):
                continue
    norm = [normalize(w) for w, _, _ in rows]
    out, i = [], 0
    while i < len(rows):
        hit = None
        for tokens in terms:
            n = len(tokens)
            if norm[i:i + n] == tokens or (n == 1 and norm[i].split() == tokens):
                hit = n
                break
        if not hit:
            i += 1
            continue
        first, last = rows[i], rows[i + hit - 1]
        prev_end = rows[i - 1][2] if i > 0 else None
        next_start = rows[i + hit][1] if i + hit < len(rows) else None
        start = first[1] - padding_ms
        end = last[2] + padding_ms
        if prev_end is not None:
            start = max(start, min(first[1], prev_end))
        if next_start is not None:
            end = min(end, max(last[2], next_start))
        out.append({"index": i, "text": " ".join(r[0] for r in rows[i:i + hit]),
                    "word_start_ms": first[1], "word_end_ms": last[2],
                    "start_ms": max(0, start), "end_ms": max(max(0, start), end),
                    "prev": " ".join(r[0] for r in rows[max(0, i - 3):i]),
                    "next": " ".join(r[0] for r in rows[i + hit:i + hit + 3])})
        i += hit
    return out
