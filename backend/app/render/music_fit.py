"""Beat-aware music fit: re-edit a music track to a target length.

This is a rule-based edit on the detected beat grid (render/beats.py), not AI:
  * shorter: whole bars (4 beats) are removed from the middle of the track and
    the two sides are joined with a short crossfade on a beat;
  * longer: a block of whole bars from the middle is repeated (as many times
    as needed), each join crossfaded on a beat;
  * the result is cut to the exact target length and ends with a fade-out.
The original file is never changed; the caller stores the result as a new asset.
"""
from __future__ import annotations

import math
import os
import subprocess

from app.config import FFMPEG_BIN

XFADE_S = 0.06          # short crossfade at each beat-aligned join
BAR = 4                 # beats per bar


class MusicFitError(ValueError):
    pass


def plan_segments(duration_s: float, target_s: float, beats: list[float], xfade: float = XFADE_S) -> list[tuple[float, float]]:
    """Source (start, end) pieces, joined in order with crossfades of `xfade`
    seconds, whose total is at least target_s. Cut points are beats one or
    more whole bars apart."""
    beats = [b for b in beats if 0 < b < duration_s]
    if target_s >= duration_s - 1e-3 and target_s <= duration_s + 0.05:
        return [(0.0, duration_s)]
    if len(beats) < BAR * 2 + 1:
        raise MusicFitError("Not enough beats were found in this music to re-edit it.")
    bar_s = (beats[-1] - beats[0]) / (len(beats) - 1) * BAR
    mid = duration_s / 2
    centre = min(range(len(beats)), key=lambda i: abs(beats[i] - mid))
    if target_s < duration_s:
        remove = duration_s - target_s
        bars = int((remove - xfade) // bar_s)
        max_bars = (len(beats) - 1) // BAR
        bars = max(0, min(bars, max_bars))
        if bars == 0:
            return [(0.0, duration_s)]              # less than a bar to lose: just trim the tail
        span = bars * BAR
        i0 = max(0, min(len(beats) - 1 - span, centre - span // 2))
        a, b = beats[i0], beats[i0 + span]
        return [s for s in ((0.0, a), (b, duration_s)) if s[1] - s[0] > 3 * xfade] or [(b, duration_s)]
    # longer: repeat a block of whole bars from the middle of the track
    extra = target_s - duration_s
    avail = (len(beats) - 1) // BAR
    block_bars = max(1, min(avail, int(round((duration_s * 0.5) / bar_s)) or 1))
    span = block_bars * BAR
    i0 = max(0, min(len(beats) - 1 - span, centre - span // 2))
    a, b = beats[i0], beats[i0 + span]
    block = b - a
    repeats = max(1, math.ceil(extra / max(0.2, block - xfade)))
    return [(0.0, b)] + [(a, b)] * (repeats - 1) + [(a, duration_s)]


def render_fit(src: str, out: str, duration_s: float, target_s: float, beats: list[float], fade_out_s: float = 2.5) -> list[tuple[float, float]]:
    segs = plan_segments(duration_s, target_s, beats)
    n = len(segs)
    fade = min(fade_out_s, target_s / 4)
    # One input per piece (seeked with -ss/-t): splitting a single input with
    # asplit stalls acrossfade chains in FFmpeg and silently drops pieces.
    inputs, parts = [], []
    for i, (a, b) in enumerate(segs):
        inputs += ["-ss", f"{a:.4f}", "-t", f"{b - a:.4f}", "-i", src]
        parts.append(f"[{i}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,asetpts=PTS-STARTPTS[p{i}]")
    cur = "p0"
    for i in range(1, n):
        parts.append(f"[{cur}][p{i}]acrossfade=d={XFADE_S}:c1=tri:c2=tri[x{i}]")
        cur = f"x{i}"
    parts.append(f"[{cur}]atrim=end={target_s:.4f},asetpts=PTS-STARTPTS,afade=t=out:st={max(0.0, target_s - fade):.4f}:d={fade:.4f}[out]")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0  # type: ignore[attr-defined]
    r = subprocess.run([FFMPEG_BIN, "-y", "-hide_banner", "-nostdin", "-loglevel", "error", *inputs,
                        "-filter_complex", ";".join(parts), "-map", "[out]", "-c:a", "pcm_s16le", out],
                       capture_output=True, text=True, timeout=600, creationflags=flags)
    if r.returncode != 0:
        raise MusicFitError("The music could not be re-edited: " + r.stderr.strip()[-300:])
    return segs
