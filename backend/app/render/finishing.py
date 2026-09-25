"""Sound and finishing for the whole video.

* Projector sound: a generated clatter (one click per film frame) with motor
  hum, looped under scenes that use the Old film look.
* Countdown leader: a 5-second film leader (5, 4, 3, 2 with a rotating sweep,
  then black) with the classic one-frame "2-pop" beep, prepended to the export.
* Background music: one track for the whole video, looped to length, faded,
  and ducked under narration with a sidechain compressor.
* Loudness: EBU R128 levelling to -14 LUFS / -1.5 dBTP, YouTube's target.

Generated media is cached under PROXIES_DIR/finishing and is safe to delete.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import threading
import uuid
from pathlib import Path

import numpy as np

from app.config import BUNDLED_FONT_PATH, FFMPEG_BIN, MEDIA_DIR, PROXIES_DIR, RENDERS_DIR
from app.render.ffmpeg_utils import probe, run_ffmpeg

CACHE = Path(PROXIES_DIR) / "finishing"
LEADER_SECONDS = 5
YOUTUBE_LUFS = -14
_lock = threading.Lock()


class FinishingError(ValueError):
    pass


def _tmp(path: Path) -> Path:
    return path.with_name(f"{path.stem}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp{path.suffix}")


def _run(args: list[str], data: bytes | None = None) -> None:
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0  # type: ignore[attr-defined]
    r = subprocess.run([FFMPEG_BIN, "-y", "-hide_banner", "-nostdin", "-loglevel", "error", *args],
                       input=data, capture_output=True, timeout=600, creationflags=flags)
    if r.returncode != 0:
        raise FinishingError(r.stderr.decode(errors="replace")[-400:] or "FFmpeg failed while finishing the video.")


# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------
MUSIC_DEFAULTS = {"asset_id": None, "volume": 35, "duck": 70, "fade_in_ms": 1500, "fade_out_ms": 3000}


def clean_finishing(raw: dict, project_id: str, db) -> dict:
    from app.db.models import Asset
    if not isinstance(raw, dict) or set(raw) - {"music", "loudnorm", "leader"}:
        raise FinishingError("Finishing settings may only contain music, loudnorm and leader.")
    out: dict = {}
    for key in ("loudnorm", "leader"):
        value = raw.get(key, False)
        if not isinstance(value, bool):
            raise FinishingError(f"{key} must be true or false.")
        if value:
            out[key] = True
    music = raw.get("music")
    if music:
        if not isinstance(music, dict) or set(music) - set(MUSIC_DEFAULTS):
            raise FinishingError("Music settings may only contain: " + ", ".join(MUSIC_DEFAULTS) + ".")
        m = {**MUSIC_DEFAULTS, **music}
        asset = db.get(Asset, m["asset_id"]) if m["asset_id"] else None
        if not asset or asset.type != "audio" or asset.project_id != project_id:
            raise FinishingError("Choose an audio file from this project's Media Pool for the music.")
        for key, lo, hi in (("volume", 0, 100), ("duck", 0, 100), ("fade_in_ms", 0, 20000), ("fade_out_ms", 0, 20000)):
            v = m[key]
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi:
                raise FinishingError(f"Music {key} must be between {lo} and {hi}.")
            m[key] = int(v)
        out["music"] = m
    return out


# --------------------------------------------------------------------------
# Projector sound
# --------------------------------------------------------------------------
def projector_wav(fps: int) -> Path:
    """4 s seamless loop: a mechanical click per film frame (with a softer
    second click from the claw), motor hum, and slight speed flutter."""
    CACHE.mkdir(parents=True, exist_ok=True)
    out = CACHE / f"projector_v2_{fps}.wav"
    with _lock:
        if out.exists():
            return out
        sr, seconds = 48000, 4
        rng = np.random.default_rng(1939)
        t = np.arange(sr * seconds) / sr
        sig = np.zeros_like(t)
        period = sr / fps
        click = rng.normal(0, 1, int(0.006 * sr)) * np.exp(-np.linspace(0, 7, int(0.006 * sr)))
        for k in range(int(seconds * fps)):
            for offset, gain in ((0, 1.0), (0.45, 0.22)):
                i = int((k + offset) * period + rng.normal(0, 0.0008 * sr))
                if 0 <= i < len(sig) - len(click):
                    sig[i:i + len(click)] += click * gain * rng.uniform(0.7, 1.0)
        # smooth the clicks into a rattle and add motor hum (loop-exact frequencies)
        sig = np.convolve(sig, np.hanning(24) / 12, "same")
        hum = sum(a * np.sin(2 * np.pi * f * t) for f, a in ((50, .012), (100, .006), (150, .003)))
        sig = sig * 0.5 + hum + rng.normal(0, 0.004, len(t))
        sig = sig / np.abs(sig).max() * 0.6
        pcm = (np.stack([sig, np.roll(sig, 37)], 1) * 32767).astype("<i2")
        tmp = _tmp(out)
        _run(["-f", "s16le", "-ar", str(sr), "-ac", "2", "-i", "-", str(tmp)], pcm.tobytes())
        os.replace(tmp, out)
        return out


def add_projector_sound(part_path: str, level: int, fps: int, work_dir: Path, cancel_check=None) -> str:
    out = str(Path(work_dir) / "part_projector.mp4")
    run_ffmpeg(["-i", part_path, "-stream_loop", "-1", "-i", str(projector_wav(fps)),
                "-filter_complex", f"[1:a]volume={0.5 * level / 100:.3f}[p];[0:a][p]amix=inputs=2:duration=first:normalize=0[a]",
                "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", out],
               cancel_check=cancel_check)
    return out


# --------------------------------------------------------------------------
# Countdown leader
# --------------------------------------------------------------------------
def countdown_leader(width: int, height: int, fps: int) -> Path:
    from PIL import Image, ImageDraw, ImageFont
    CACHE.mkdir(parents=True, exist_ok=True)
    out = CACHE / f"leader_v1_{width}x{height}_{fps}.mp4"
    with _lock:
        if out.exists():
            return out
        font_path = BUNDLED_FONT_PATH.parent / "NotoSans-Bold.ttf"
        font = ImageFont.truetype(str(font_path), int(height * 0.42))
        cx, cy, r = width / 2, height / 2, height * 0.36
        frames = []
        for f in range(LEADER_SECONDS * fps):
            sec, frac = divmod(f / fps, 1)
            number = 5 - int(sec)
            img = Image.new("L", (width, height), 0 if number <= 1 else 150)
            if number > 1:
                d = ImageDraw.Draw(img)
                d.pieslice([cx - r * 1.6, cy - r * 1.6, cx + r * 1.6, cy + r * 1.6], -90, -90 + 360 * frac, fill=95)
                for rr, w in ((r, 6), (r * 0.82, 4)):
                    d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=235, width=max(2, int(w * height / 1080)))
                lw = max(2, int(3 * height / 1080))
                d.line([0, cy, width, cy], fill=40, width=lw)
                d.line([cx, 0, cx, height], fill=40, width=lw)
                d.text((cx, cy), str(number), font=font, fill=20, anchor="mm")
            frames.append(np.asarray(img))
        raw = np.stack(frames).tobytes()
        tmp = _tmp(out)
        pop_at = LEADER_SECONDS - 2  # the classic one-frame beep on "2"
        beep = f"if(between(t\\,{pop_at}\\,{pop_at}+1/{fps})\\,0.5*sin(2*PI*1000*t)\\,0)"
        _run(["-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{width}x{height}", "-r", str(fps), "-i", "-",
              "-f", "lavfi", "-i", f"aevalsrc={beep}|{beep}:s=48000:d={LEADER_SECONDS}",
              "-vf", "noise=alls=14:allf=t,vignette=angle=0.55,format=yuv420p,setsar=1",
              "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", "-b:a", "192k",
              "-shortest", str(tmp)], raw)
        os.replace(tmp, out)
        return out


# --------------------------------------------------------------------------
# Export finishing
# --------------------------------------------------------------------------
def finish_export(export_path: str, project, cancel_check=None) -> str:
    from app.db.database import SessionLocal
    from app.db.models import Asset
    fin = getattr(project, "finishing_json", None) or {}  # older callers pass minimal project objects
    music, leader, loud = fin.get("music"), fin.get("leader"), fin.get("loudnorm")
    if not (music or leader or loud):
        return export_path
    duration = (probe(export_path).duration_ms or 0) / 1000
    inputs = ["-i", export_path]
    graph = ["[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[main]"]
    label = "main"
    if music:
        with SessionLocal() as db:
            asset = db.get(Asset, music["asset_id"])
            if not asset:
                raise FinishingError("The background music file is missing. Choose it again in Audio → Music & finishing.")
            music_path = str(Path(RENDERS_DIR if asset.origin == "render_output" else MEDIA_DIR) / asset.storage_key)
        inputs += ["-stream_loop", "-1", "-i", music_path]
        fi, fo = music["fade_in_ms"] / 1000, min(music["fade_out_ms"] / 1000, duration / 2)
        mus = (f"[1:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,volume={music['volume'] / 100:.3f},"
               f"atrim=duration={duration:.3f},afade=t=in:d={fi:.3f},afade=t=out:st={max(0, duration - fo):.3f}:d={fo:.3f}")
        if music["duck"]:
            # Duck the music whenever the narration is present (sidechain).
            ratio = 2 + 18 * music["duck"] / 100
            graph += ["[main]asplit=2[main1][side]", f"{mus}[mus]",
                      f"[mus][side]sidechaincompress=threshold=0.015:ratio={ratio:.1f}:attack=40:release=600[musd]",
                      "[main1][musd]amix=inputs=2:duration=first:normalize=0[mix]"]
        else:
            graph += [f"{mus}[mus]", "[main][mus]amix=inputs=2:duration=first:normalize=0[mix]"]
        label = "mix"
    if loud:
        graph.append(f"[{label}]loudnorm=I={YOUTUBE_LUFS}:TP=-1.5:LRA=11,aresample=48000[lvl]")
        label = "lvl"
    out = str(Path(RENDERS_DIR) / f"export_{project.id}_{uuid.uuid4().hex[:8]}.mp4")
    if leader:
        lead = countdown_leader(project.width, project.height, project.fps)
        idx = len([a for a in inputs if a == "-i"])
        inputs += ["-i", str(lead)]
        graph += [f"[{idx}:v]scale={project.width}:{project.height},setsar=1,fps={project.fps},format=yuv420p[lv]",
                  f"[{idx}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[la]",
                  f"[0:v]setsar=1,fps={project.fps},format=yuv420p[mv]",
                  f"[lv][la][mv][{label}]concat=n=2:v=1:a=1[vout][aout]"]
        maps = ["-map", "[vout]", "-map", "[aout]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]
    else:
        maps = ["-map", "0:v", "-map", f"[{label}]", "-c:v", "copy"]
    run_ffmpeg([*inputs, "-filter_complex", ";".join(graph), *maps, "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                "-movflags", "+faststart", out], cancel_check=cancel_check)
    return out
