"""Media-driven scene timing and the sound of video clips.

A scene without narration (and without a fixed length) lasts as long as its videos: each
video's trimmed length divided by its speed, plus any freeze. Images count 4 s each when
they sit next to videos; an image-only scene keeps the usual default. With split-screen
layouts the longest video decides. Several videos in one scene each keep their own length.

`clip_audio` builds the scene's clip-sound track with exactly the same cuts as the picture
(same in-point, same per-shot duration, same speed), so sound and picture stay in sync.
"""
from __future__ import annotations

import os
from pathlib import Path

IMAGE_MS = 4000


def _speed(shot) -> float:
    sj = getattr(shot, "speed_json", None) or {}
    try:
        return max(0.1, min(4.0, float(sj.get("speed", 1) or 1)))
    except (TypeError, ValueError):
        return 1.0


def shot_natural_ms(shot) -> int | None:
    """Natural on-screen length of one shot (None for images)."""
    asset = getattr(shot, "asset", None)
    if not asset or str(getattr(asset.type, "value", asset.type)) != "video":
        return None
    src = asset.duration_ms or 0
    if not src:
        return None
    end = shot.source_out_ms or src
    length = max(100, min(end, src) - (shot.source_in_ms or 0))
    sj = getattr(shot, "speed_json", None) or {}
    freeze = int(sj.get("freeze_ms", 0) or 0) if sj.get("freeze_at_ms") is not None else 0
    return int(round(length / _speed(shot))) + freeze


def selected_shots(scene):
    return [s for s in scene.shots if s.is_selected] or list(scene.shots)


def media_duration_ms(scene) -> int | None:
    shots = selected_shots(scene)
    lengths = [shot_natural_ms(s) for s in shots]
    videos = [x for x in lengths if x]
    if not videos:
        return None
    layout = (getattr(scene, "look_json", None) or {}).get("layout")
    if layout:
        return max(videos)
    return sum(x if x else IMAGE_MS for x in lengths)


def shot_durations(scene, shots, total_ms: int) -> list[int]:
    """Per-shot durations summing exactly to total_ms. Explicit durations win; videos keep
    their natural length when it fits; the rest is shared equally (as before)."""
    n = len(shots)
    if not n:
        return []
    fixed = [s.duration_ms or None for s in shots]
    natural = [shot_natural_ms(s) for s in shots]
    plan = list(fixed)
    budget = total_ms - sum(x for x in plan if x)
    want = sum(natural[i] for i in range(n) if plan[i] is None and natural[i])
    implicit_images = [i for i in range(n) if plan[i] is None and not natural[i]]
    if want and want <= budget:
        for i in range(n):
            if plan[i] is None and natural[i]:
                plan[i] = natural[i]
        budget -= want
    rest = [i for i in range(n) if plan[i] is None]
    per = budget // len(rest) if rest else 0
    for i in rest:
        plan[i] = per
    plan = [max(1, int(x)) for x in plan]
    plan[-1] = max(1, total_ms - sum(plan[:-1]))
    return plan


def clip_audio(scene, shots, durations, media_root, work_dir: Path, ffmpeg_bin: str, has_narration: bool, original: bool = False) -> str | None:
    """WAV of the video clips' own sound, cut like the picture; None when nothing is audible.
    original=True (for automatic captions) ignores mute, volume and ducking."""
    import subprocess
    from app.render.ffmpeg_utils import probe
    parts, audible = [], False
    for i, (shot, ms) in enumerate(zip(shots, durations)):
        seg = work_dir / f"clipaudio_{i}.wav"
        a = {} if original else (getattr(shot, "audio_json", None) or {})
        asset = shot.asset
        src = Path(media_root) / asset.storage_key if asset else None
        vol = float(a.get("volume", 100)) / 100 * (0.35 if has_narration and a.get("duck", True) else 1.0)
        has_audio = False
        if asset and shot_natural_ms(shot) and not a.get("mute") and vol > 0 and src and src.exists():
            try:
                has_audio = probe(str(src)).has_audio
            except Exception:
                has_audio = False
        if has_audio:
            speed = _speed(shot)
            tempo = []
            s = speed
            while s > 2.0:
                tempo.append("atempo=2.0"); s /= 2.0
            while s < 0.5:
                tempo.append("atempo=0.5"); s /= 0.5
            if abs(s - 1) > 1e-3:
                tempo.append(f"atempo={s:.4f}")
            af = ",".join([*tempo, f"volume={vol:.3f}", "aresample=48000", "aformat=channel_layouts=stereo", f"apad", f"atrim=0:{ms/1000:.3f}"])
            cmd = [ffmpeg_bin, "-y", "-v", "error", "-ss", f"{(shot.source_in_ms or 0)/1000:.3f}", "-i", str(src),
                   "-t", f"{ms/1000*speed:.3f}", "-vn", "-af", af, "-ar", "48000", "-ac", "2", str(seg)]
            audible = True
        else:
            cmd = [ffmpeg_bin, "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", f"{ms/1000:.3f}", str(seg)]
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0  # type: ignore[attr-defined]
        subprocess.run(cmd, check=True, capture_output=True, timeout=600, creationflags=flags)
        parts.append(seg)
    if not audible:
        return None
    lst = work_dir / "clipaudio.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    out = work_dir / "clipaudio.wav"
    subprocess.run([ffmpeg_bin, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)],
                   check=True, capture_output=True, timeout=600,
                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)  # type: ignore[attr-defined]
    return str(out)
