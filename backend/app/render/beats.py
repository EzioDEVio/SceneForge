"""Beat detection for background music and snapping scene cuts to the beat.

Onset strength (spectral flux) -> tempo by autocorrelation (60-180 BPM) ->
beat phase that best matches the onsets -> a steady beat grid.
"""
from __future__ import annotations

import os
import subprocess

import numpy as np

from app.config import FFMPEG_BIN

SR, HOP = 11025, 256
# Flux value i compares frames i and i+1 and is labelled with frame i's start;
# a hit registers once it reaches the centre of the next window.
ONSET_OFFSET_S = (HOP + 512) / SR + 0.016   # + measured residual delay of the onset measure (calibrated on synthetic kicks, 72-170 BPM)


def detect_beats(path: str, max_seconds: int = 900) -> tuple[float, list[float]]:
    """Return (bpm, beat times in seconds)."""
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0  # type: ignore[attr-defined]
    raw = subprocess.run([FFMPEG_BIN, "-hide_banner", "-nostdin", "-loglevel", "error", "-t", str(max_seconds), "-i", path,
                          "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"], capture_output=True, timeout=180,
                         creationflags=flags, check=True).stdout
    a = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    if a.size < SR * 2:
        return 0.0, []
    n = (a.size - 1024) // HOP
    frames = np.stack([a[i * HOP:i * HOP + 1024] * np.hanning(1024) for i in range(n)])
    mag = np.log1p(np.abs(np.fft.rfft(frames, axis=1)))
    flux = np.maximum(0, np.diff(mag, axis=0)).sum(axis=1)
    flux = (flux - flux.mean()) / (flux.std() + 1e-9)
    fps = SR / HOP
    ac = np.correlate(flux, flux, "full")[flux.size - 1:]
    lags = np.arange(int(fps * 60 / 200), int(fps * 60 / 55) + 1)
    bpms = 60 * fps / lags
    # A beat every 0.5 s also repeats every 1 s, so autocorrelation alone
    # often picks half the tempo. Prefer tempos near 120 BPM (log-normal
    # prior, as in common beat trackers) so the musically usual reading wins.
    prior = np.exp(-0.5 * (np.log2(bpms / 120) / 0.6) ** 2)
    lag = lags[np.argmax(np.maximum(ac[lags], 0) * prior)]
    # Sub-frame precision: parabolic interpolation around the autocorrelation peak.
    y0, y1, y2 = ac[lag - 1], ac[lag], ac[lag + 1]
    denom = y0 - 2 * y1 + y2
    lag_f = lag + (0.5 * (y0 - y2) / denom if denom else 0.0)
    period = lag_f / fps
    phases = np.arange(lag)
    score = [flux[p::lag].sum() for p in phases]
    phase = phases[int(np.argmax(score))] / fps
    # Refine: fit a straight line through the strongest onset near each grid beat,
    # so the grid does not drift over long tracks.
    # Comb search: try tempos within +/-3 % of the estimate and every phase,
    # keep the grid that lands on the most onset energy. Robust to weak or
    # missing beats, and precise enough not to drift over long tracks.
    smooth = np.convolve(np.maximum(flux, 0), np.hanning(5) / np.hanning(5).sum(), "same")
    frame_t = np.arange(smooth.size) / fps
    best = (-1.0, period, phase)
    for per in np.linspace(period * 0.97, period * 1.03, 241):
        beats_n = int(frame_t[-1] / per)
        if beats_n < 4:
            continue
        k = np.arange(beats_n)
        for ph in np.arange(0, per, 1 / fps):
            score = np.interp(ph + k * per, frame_t, smooth).sum() / beats_n
            if score > best[0]:
                best = (score, per, ph)
    _, period, phase = best
    phase = (phase + ONSET_OFFSET_S) % period
    beats = list(np.arange(phase, a.size / SR, period))
    return round(60 / period, 1), [round(float(b), 3) for b in beats]


def snap_durations(durations_ms: list[int], fixed: list[bool], beats: list[float], min_ms: int = 1000) -> list[int]:
    """New lengths for fixed-length scenes so each cut lands on the nearest
    beat. Scenes that follow their narration keep their length."""
    out, t = [], 0.0
    for d, is_fixed in zip(durations_ms, fixed):
        end = t + d / 1000
        if is_fixed and beats:
            cands = [b for b in beats if b - t >= min_ms / 1000]
            if cands:
                end = min(cands, key=lambda b: abs(b - end))
        out.append(int(round((end - t) * 1000)) if is_fixed else d)
        t += out[-1] / 1000
    return out
