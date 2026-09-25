"""Non-destructive edits for a scene's narration/audio take.

The source file is never modified. A take's edit_json holds:
  in_ms / out_ms   trim points inside the source file (out_ms None = end)
  volume           gain in percent, 0-200 (100 = unchanged)
  fade_in_ms / fade_out_ms   linear fades on the trimmed clip
The renderer applies them with atrim/volume/afade before placing the audio
in the scene, and "Match narration" timing uses the trimmed length.
"""
from __future__ import annotations

MIN_CLIP_MS = 200
MAX_FADE_MS = 10000
DEFAULT_EDIT = {"in_ms": 0, "out_ms": None, "volume": 100, "fade_in_ms": 0, "fade_out_ms": 0, "voice_fx": "none"}
# Voice effects: "clean" reduces background noise and evens the level (home
# recordings); "radio" is a 1940s newsreel / wireless sound; "telephone" is narrower.
VOICE_FX = {
    "none": "",
    "clean": "highpass=f=70,afftdn=nf=-25,dynaudnorm=f=150:g=15",
    "radio": "highpass=f=300,lowpass=f=3400,acompressor=threshold=0.1:ratio=6:attack=5:release=80,volume=1.8,alimiter=limit=0.9",
    "telephone": "highpass=f=500,lowpass=f=2600,acompressor=threshold=0.08:ratio=8,volume=2.0,alimiter=limit=0.9",
}


class AudioEditError(ValueError):
    pass


def _int(value, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AudioEditError(f"{name} must be a number.")
    return int(round(value))


def clean_edit(raw: dict | None, source_ms: int | None) -> dict:
    """Validate an edit against the source length. Raises AudioEditError."""
    raw = raw or {}
    unknown = set(raw) - set(DEFAULT_EDIT)
    if unknown:
        raise AudioEditError(f"Unknown audio setting: {', '.join(sorted(unknown))}.")
    edit = {**DEFAULT_EDIT, **raw}
    in_ms = _int(edit["in_ms"], "Start")
    out_ms = None if edit["out_ms"] is None else _int(edit["out_ms"], "End")
    if in_ms < 0:
        raise AudioEditError("Start cannot be before the beginning of the audio.")
    if source_ms:
        if out_ms is not None and out_ms > source_ms:
            out_ms = source_ms  # tolerate rounding from the UI
        if out_ms == source_ms:
            out_ms = None
        end = out_ms if out_ms is not None else source_ms
        if in_ms >= source_ms:
            raise AudioEditError("Start must be before the end of the audio.")
    else:
        end = out_ms
    if end is not None and end - in_ms < MIN_CLIP_MS:
        raise AudioEditError(f"Keep at least {MIN_CLIP_MS / 1000:.1f} s of audio.")
    volume = _int(edit["volume"], "Volume")
    if not 0 <= volume <= 200:
        raise AudioEditError("Volume must be between 0% and 200%.")
    fades = {}
    for key in ("fade_in_ms", "fade_out_ms"):
        value = _int(edit[key], "Fade")
        if not 0 <= value <= MAX_FADE_MS:
            raise AudioEditError("Fades must be between 0 and 10 seconds.")
        fades[key] = value
    if end is not None and fades["fade_in_ms"] + fades["fade_out_ms"] > end - in_ms:
        raise AudioEditError("Fade in and fade out together are longer than the trimmed audio.")
    if edit["voice_fx"] not in VOICE_FX:
        raise AudioEditError("Voice effect must be one of: " + ", ".join(VOICE_FX) + ".")
    return {"in_ms": in_ms, "out_ms": out_ms, "volume": volume, **fades, "voice_fx": edit["voice_fx"]}


def is_default(edit: dict | None) -> bool:
    return not edit or {**DEFAULT_EDIT, **edit} == DEFAULT_EDIT


def effective_ms(measured_ms: int | None, edit: dict | None) -> int | None:
    """Length of the take after trimming."""
    if measured_ms is None:
        return None
    e = {**DEFAULT_EDIT, **(edit or {})}
    end = e["out_ms"] if e["out_ms"] is not None else measured_ms
    return max(0, min(end, measured_ms) - e["in_ms"])


def narration_filter(edit: dict | None, clip_ms: int) -> str:
    """Filter chain (no labels) for the trimmed, levelled, faded clip."""
    e = {**DEFAULT_EDIT, **(edit or {})}
    parts = []
    if e["in_ms"] or e["out_ms"] is not None:
        end = f":end={e['out_ms'] / 1000:.3f}" if e["out_ms"] is not None else ""
        parts.append(f"atrim=start={e['in_ms'] / 1000:.3f}{end},asetpts=PTS-STARTPTS")
    if VOICE_FX.get(e.get("voice_fx", "none")):
        parts.append(VOICE_FX[e["voice_fx"]])
    if e["volume"] != 100:
        parts.append(f"volume={e['volume'] / 100:.3f}")
    if e["fade_in_ms"]:
        parts.append(f"afade=t=in:st=0:d={e['fade_in_ms'] / 1000:.3f}")
    if e["fade_out_ms"]:
        start = max(0.0, (clip_ms - e["fade_out_ms"]) / 1000)
        parts.append(f"afade=t=out:st={start:.3f}:d={e['fade_out_ms'] / 1000:.3f}")
    return ",".join(parts)
