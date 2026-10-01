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
    if not isinstance(raw, dict) or set(raw) - {"music", "audio_clips", "loudnorm", "leader", "timeline"}:
        raise FinishingError("Finishing settings may only contain music, audio_clips, loudnorm, leader and timeline.")
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
    clips = raw.get("audio_clips", [])
    if not isinstance(clips, list) or len(clips) > 64:
        raise FinishingError("The timeline supports up to 64 project audio clips.")
    clean_clips = []
    for index, clip in enumerate(clips):
        allowed = {"id", "asset_id", "name", "start_ms", "source_in_ms", "source_out_ms", "source_duration_ms", "volume", "fade_in_ms", "fade_out_ms", "mute", "track"}
        if not isinstance(clip, dict) or set(clip) - allowed:
            raise FinishingError(f"Project audio clip {index + 1} has unsupported settings.")
        asset = db.get(Asset, clip.get("asset_id")) if clip.get("asset_id") else None
        if not asset or asset.type != "audio" or asset.project_id != project_id:
            raise FinishingError(f"Project audio clip {index + 1} must use an audio file from this project's Media Pool.")
        def bounded(name, default, lo, hi):
            value = clip.get(name, default)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not lo <= value <= hi:
                raise FinishingError(f"Project audio clip {index + 1} {name} must be between {lo} and {hi}.")
            return int(value)
        source_ms = max(200, int(asset.duration_ms or 0))
        start = bounded("start_ms", 0, 0, 86_400_000)
        source_in = bounded("source_in_ms", 0, 0, source_ms - 100)
        source_out = bounded("source_out_ms", source_ms, source_in + 100, source_ms)
        volume = bounded("volume", 100, 0, 200)
        fade_in = bounded("fade_in_ms", 0, 0, 10_000)
        fade_out = bounded("fade_out_ms", 0, 0, 10_000)
        if fade_in + fade_out > source_out - source_in:
            raise FinishingError(f"Project audio clip {index + 1} fades are longer than the clip.")
        mute = clip.get("mute", False)
        if not isinstance(mute, bool):
            raise FinishingError(f"Project audio clip {index + 1} mute must be true or false.")
        name = str(clip.get("name") or asset.original_filename or "Audio clip")[:200]
        track = clip.get("track", "A3")
        if track not in AUDIO_TRACKS:
            raise FinishingError(f"Project audio clip {index + 1} track must be one of " + ", ".join(AUDIO_TRACKS) + ".")
        cleaned = {"id": str(clip.get("id") or uuid.uuid4()), "asset_id": asset.id, "name": name, "source_duration_ms": source_ms,
                   "start_ms": start, "source_in_ms": source_in, "source_out_ms": source_out,
                   "volume": volume, "fade_in_ms": fade_in, "fade_out_ms": fade_out, "mute": mute}
        if track != "A3":   # A3 stays implicit so projects remain readable by pre-timeline-v1 builds
            cleaned["track"] = track
        clean_clips.append(cleaned)
    if clean_clips:
        out["audio_clips"] = clean_clips
    if "timeline" in raw:
        out["timeline"] = clean_timeline(raw["timeline"])
    return out


# --------------------------------------------------------------------------
# Timeline settings (version 1): track state, visible audio tracks, markers.
# Mirrors frontend/src/timeline/timeline.types.ts normalizeTimeline.
# --------------------------------------------------------------------------
TIMELINE_VERSION = 1
SCENE_TRACKS = ("T1", "V1", "A1", "A2")
AUDIO_TRACKS = ("A3", "A4", "A5", "A6", "A7", "A8")
MARKER_COLORS = ("amber", "red", "green", "blue", "purple")
MAX_MARKERS = 200


def clean_timeline(raw) -> dict:
    if not isinstance(raw, dict) or set(raw) - {"version", "tracks", "audio_tracks", "markers"}:
        raise FinishingError("Timeline settings may only contain version, tracks, audio_tracks and markers.")
    version = raw.get("version", TIMELINE_VERSION)
    if isinstance(version, bool) or not isinstance(version, int) or not 0 <= version <= TIMELINE_VERSION:
        raise FinishingError(f"This SceneForge build reads timeline versions up to {TIMELINE_VERSION}.")
    tracks_in = raw.get("tracks", {})
    if not isinstance(tracks_in, dict):
        raise FinishingError("Timeline tracks must be an object.")
    tracks: dict = {}
    for key, state in tracks_in.items():
        if key not in SCENE_TRACKS + AUDIO_TRACKS:
            raise FinishingError(f"Unknown timeline track {str(key)[:8]}.")
        allowed = {"locked", "mute", "solo"} if key in AUDIO_TRACKS else {"locked"}
        if not isinstance(state, dict) or set(state) - allowed or any(not isinstance(v, bool) for v in state.values()):
            raise FinishingError(f"Track {key} supports " + ", ".join(sorted(allowed)) + " (true or false).")
        kept = {k: True for k, v in state.items() if v}
        if kept:
            tracks[key] = kept
    shown = raw.get("audio_tracks", ["A3"])
    if not isinstance(shown, list) or any(t not in AUDIO_TRACKS for t in shown):
        raise FinishingError("Visible audio tracks must be A3 to A8.")
    markers_in = raw.get("markers", [])
    if not isinstance(markers_in, list) or len(markers_in) > MAX_MARKERS:
        raise FinishingError(f"A timeline supports up to {MAX_MARKERS} markers.")
    markers = []
    for i, m in enumerate(markers_in):
        if not isinstance(m, dict) or set(m) - {"id", "time_ms", "duration_ms", "label", "color"}:
            raise FinishingError(f"Marker {i + 1} has unsupported settings.")
        t, d = m.get("time_ms"), m.get("duration_ms", 0)
        for name, v in (("time", t), ("length", d)):
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 86_400_000:
                raise FinishingError(f"Marker {i + 1} {name} must be between 0 and 24 hours.")
        color = m.get("color", "amber")
        if color not in MARKER_COLORS:
            raise FinishingError(f"Marker {i + 1} colour must be one of " + ", ".join(MARKER_COLORS) + ".")
        markers.append({"id": str(m.get("id") or uuid.uuid4())[:64], "time_ms": int(t), "duration_ms": int(d),
                        "label": str(m.get("label") or f"Marker {i + 1}")[:120], "color": color})
    markers.sort(key=lambda m: m["time_ms"])
    return {"version": TIMELINE_VERSION, "tracks": tracks,
            "audio_tracks": [t for t in AUDIO_TRACKS if t == "A3" or t in shown], "markers": markers}


def audible_clips(fin: dict) -> list[dict]:
    """Timeline audio clips heard in export: clip and track mute, then A3–A8 solo."""
    tracks = ((fin.get("timeline") or {}).get("tracks") or {})
    soloed = {t for t in AUDIO_TRACKS if (tracks.get(t) or {}).get("solo")}
    out = []
    for clip in fin.get("audio_clips", []) or []:
        track = clip.get("track", "A3")
        if clip.get("mute") or (tracks.get(track) or {}).get("mute") or (soloed and track not in soloed):
            continue
        out.append(clip)
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
              "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-profile:v", "high", "-movflags", "+faststart", "-c:a", "aac", "-b:a", "192k",
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
    music, loud = fin.get("music"), fin.get("loudnorm")
    audio_clips = audible_clips(fin)
    leader = False   # retired: the countdown is now a scene effect (Effects → Countdown intro)
    if not (music or audio_clips or leader or loud):
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
    if audio_clips:
        with SessionLocal() as db:
            assets = [(clip, db.get(Asset, clip["asset_id"])) for clip in audio_clips]
            for index, (clip, asset) in enumerate(assets):
                if not asset:
                    raise FinishingError(f"Project audio clip {clip.get('name') or index + 1} is missing. Remove it from the timeline and add it again.")
                source = Path(RENDERS_DIR if asset.origin == "render_output" else MEDIA_DIR) / asset.storage_key
                inputs += ["-i", str(source)]
                input_index = sum(1 for item in inputs if item == "-i") - 1
                clip_ms = max(100, int(clip["source_out_ms"]) - int(clip["source_in_ms"]))
                fade_in = min(int(clip["fade_in_ms"]), clip_ms) / 1000
                fade_out = min(int(clip["fade_out_ms"]), clip_ms) / 1000
                start = int(clip["start_ms"])
                parts = [f"[{input_index}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo",
                         f"atrim=start={int(clip['source_in_ms'])/1000:.3f}:end={int(clip['source_out_ms'])/1000:.3f}",
                         "asetpts=PTS-STARTPTS", f"volume={int(clip['volume'])/100:.3f}"]
                if fade_in:
                    parts.append(f"afade=t=in:st=0:d={fade_in:.3f}")
                if fade_out:
                    parts.append(f"afade=t=out:st={max(0, clip_ms/1000-fade_out):.3f}:d={fade_out:.3f}")
                parts.append(f"adelay={start}|{start}")
                clip_label = f"timeline_audio_{index}"
                mixed_label = f"timeline_mix_{index}"
                graph += [f"{','.join(parts)}[{clip_label}]",
                          f"[{label}][{clip_label}]amix=inputs=2:duration=first:normalize=0[{mixed_label}]"]
                label = mixed_label
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
        maps = ["-map", "[vout]", "-map", "[aout]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-profile:v", "high", "-movflags", "+faststart"]
    else:
        maps = ["-map", "0:v", "-map", f"[{label}]", "-c:v", "copy", "-movflags", "+faststart"]
    run_ffmpeg([*inputs, "-filter_complex", ";".join(graph), *maps, "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                "-movflags", "+faststart", out], cancel_check=cancel_check)
    return out


# --------------------------------------------------------------------------
# Scene preview mix: a rendered scene with the timeline audio (A3–A8) and the
# music bed that play under it. The rendered part itself stays clean, because
# full export mixes project audio once over the whole movie (no double mix).
# --------------------------------------------------------------------------
def scene_preview_plan(fin: dict, scene_start_ms: int, part_ms: int, project_ms: int) -> dict | None:
    """What to mix into one scene render, in scene-relative time. None when nothing plays."""
    fin = fin or {}
    window_end = scene_start_ms + part_ms
    clips = []
    for clip in audible_clips(fin):
        length = int(clip["source_out_ms"]) - int(clip["source_in_ms"])
        rel = int(clip["start_ms"]) - scene_start_ms
        if rel >= part_ms or rel + length <= 0:
            continue
        cut_head = max(0, -rel)
        clips.append({"asset_id": clip["asset_id"], "name": clip.get("name"), "delay_ms": max(0, rel),
                      "source_in_ms": int(clip["source_in_ms"]) + cut_head, "length_ms": length - cut_head,
                      "volume": int(clip["volume"]),
                      "fade_in_ms": 0 if cut_head else int(clip["fade_in_ms"]),
                      "fade_out_ms": int(clip["fade_out_ms"]) if rel + length <= part_ms + 50 else 0})
    music = fin.get("music")
    music_plan = None
    if music and window_end > 0:
        fi, fo = music["fade_in_ms"], min(music["fade_out_ms"], project_ms // 2)
        music_plan = {**music, "offset_ms": scene_start_ms,
                      "fade_in_ms": max(0, fi - scene_start_ms),
                      "fade_out_start_ms": project_ms - fo - scene_start_ms, "fade_out_ms": fo}
    if not clips and not music_plan:
        return None
    return {"clips": clips, "music": music_plan, "part_ms": part_ms}


def mix_scene_preview(part_path: str, plan: dict, out_path: str) -> str:
    from app.db.database import SessionLocal
    from app.db.models import Asset
    part_s = plan["part_ms"] / 1000
    inputs = ["-i", part_path]
    graph = []
    if probe(part_path).has_audio:
        graph.append("[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[main]")
    else:
        graph.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={part_s:.3f}[main]")
    label = "main"

    def path_of(db, asset_id):
        asset = db.get(Asset, asset_id)
        if not asset:
            raise FinishingError("A timeline audio file is missing. Remove it from the timeline and add it again.")
        return str(Path(RENDERS_DIR if asset.origin == "render_output" else MEDIA_DIR) / asset.storage_key)

    with SessionLocal() as db:
        music = plan.get("music")
        if music:
            inputs += ["-stream_loop", "-1", "-ss", f"{music['offset_ms'] / 1000:.3f}", "-i", path_of(db, music["asset_id"])]
            idx = inputs.count("-i") - 1
            chain = [f"[{idx}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo",
                     f"volume={music['volume'] / 100:.3f}", f"atrim=duration={part_s:.3f}"]
            if music["fade_in_ms"]:
                chain.append(f"afade=t=in:d={music['fade_in_ms'] / 1000:.3f}")
            if music["fade_out_ms"] and music["fade_out_start_ms"] < plan["part_ms"]:
                chain.append(f"afade=t=out:st={max(0, music['fade_out_start_ms']) / 1000:.3f}:d={music['fade_out_ms'] / 1000:.3f}")
            if music["duck"]:
                ratio = 2 + 18 * music["duck"] / 100
                graph += ["[main]asplit=2[main1][side]", ",".join(chain) + "[mus]",
                          f"[mus][side]sidechaincompress=threshold=0.015:ratio={ratio:.1f}:attack=40:release=600[musd]",
                          "[main1][musd]amix=inputs=2:duration=first:normalize=0[mix]"]
            else:
                graph += [",".join(chain) + "[mus]", "[main][mus]amix=inputs=2:duration=first:normalize=0[mix]"]
            label = "mix"
        for i, clip in enumerate(plan["clips"]):
            inputs += ["-i", path_of(db, clip["asset_id"])]
            idx = inputs.count("-i") - 1
            length = clip["length_ms"] / 1000
            parts = [f"[{idx}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo",
                     f"atrim=start={clip['source_in_ms'] / 1000:.3f}:duration={length:.3f}", "asetpts=PTS-STARTPTS",
                     f"volume={clip['volume'] / 100:.3f}"]
            if clip["fade_in_ms"]:
                parts.append(f"afade=t=in:st=0:d={min(clip['fade_in_ms'] / 1000, length):.3f}")
            if clip["fade_out_ms"]:
                fo = min(clip["fade_out_ms"] / 1000, length)
                parts.append(f"afade=t=out:st={max(0, length - fo):.3f}:d={fo:.3f}")
            parts.append(f"adelay={clip['delay_ms']}|{clip['delay_ms']}")
            graph += [",".join(parts) + f"[pc{i}]", f"[{label}][pc{i}]amix=inputs=2:duration=first:normalize=0[pm{i}]"]
            label = f"pm{i}"
    run_ffmpeg([*inputs, "-filter_complex", ";".join(graph), "-map", "0:v", "-map", f"[{label}]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", out_path])
    return out_path
