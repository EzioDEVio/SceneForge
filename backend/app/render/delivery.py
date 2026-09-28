"""Export delivery: turn the assembled master into the format the user chose.

settings = {resolution: project|720p|1080p|1440p|4k, fps: project|24|25|30|50|60,
            format: mp4_h264|mp4_h265|webm|mov_prores|gif|mp3|wav, quality: draft|standard|high|max}

Resolution keeps the project's shape (the short side becomes 720/1080/1440/2160). Every video
format is written in a widely playable way (4:2:0 colour, fast start for MP4/MOV, H.265 tagged
hvc1 so Apple and Windows players accept it). Caption files (SRT/VTT) come from the scenes'
caption text and timing (transcript words when present, otherwise phrases spread over the scene).
"""
from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path

RESOLUTIONS = {"project": None, "720p": 720, "1080p": 1080, "1440p": 1440, "4k": 2160}
FPS = ("project", 24, 25, 30, 50, 60)
FORMATS = {
    # key: (extension, mime, kind)
    "mp4_h264": ("mp4", "video/mp4", "video"),
    "mp4_h265": ("mp4", "video/mp4", "video"),
    "webm": ("webm", "video/webm", "video"),
    "mov_prores": ("mov", "video/quicktime", "video"),
    "gif": ("gif", "image/gif", "gif"),
    "mp3": ("mp3", "audio/mpeg", "audio"),
    "wav": ("wav", "audio/wav", "audio"),
}
QUALITY = ("draft", "standard", "high", "max")
DEFAULT = {"resolution": "project", "fps": "project", "format": "mp4_h264", "quality": "standard"}


class DeliveryError(ValueError):
    pass


def clean(raw: dict | None) -> dict:
    s = {**DEFAULT, **(raw or {})}
    if set(s) - set(DEFAULT):
        raise DeliveryError("Export settings are resolution, fps, format and quality.")
    if s["resolution"] not in RESOLUTIONS:
        raise DeliveryError("Resolution must be project, 720p, 1080p, 1440p or 4k.")
    if s["fps"] not in FPS:
        raise DeliveryError("Frame rate must be project, 24, 25, 30, 50 or 60.")
    if s["format"] not in FORMATS:
        raise DeliveryError("Format must be one of: " + ", ".join(FORMATS) + ".")
    if s["quality"] not in QUALITY:
        raise DeliveryError("Quality must be draft, standard, high or max.")
    return s


def target_size(settings: dict, width: int, height: int) -> tuple[int, int]:
    short = RESOLUTIONS[settings["resolution"]]
    if not short:
        return width, height
    if width >= height:
        h = short; w = round(short * width / height / 2) * 2
    else:
        w = short; h = round(short * height / width / 2) * 2
    return w, h


def extension(settings: dict) -> tuple[str, str]:
    ext, mime, _ = FORMATS[settings["format"]]
    return ext, mime


def deliver(master: str, settings: dict, width: int, height: int, fps: int, out_dir: str, ffmpeg_bin: str, cancel_check=None) -> str:
    s = clean(settings)
    ext, _, kind = FORMATS[s["format"]]
    out = str(Path(out_dir) / f"delivery_{uuid.uuid4().hex[:10]}.{ext}")
    w, h = target_size(s, width, height)
    rate = fps if s["fps"] == "project" else int(s["fps"])
    q = QUALITY.index(s["quality"])            # 0 draft … 3 max
    vf = []
    if (w, h) != (width, height):
        vf.append(f"scale={w}:{h}:flags=lanczos")
    if rate != fps:
        vf.append(f"fps={rate}")
    args = [ffmpeg_bin, "-y", "-hide_banner", "-nostdin", "-loglevel", "error", "-i", master]
    if kind == "audio":
        args += ["-vn"]
        args += (["-c:a", "libmp3lame", "-b:a", ("128k", "192k", "256k", "320k")[q]] if s["format"] == "mp3"
                 else ["-c:a", "pcm_s16le", "-ar", "48000"])
    elif kind == "gif":
        gw = min(w, (480, 640, 720, 960)[q])
        gh = round(h * gw / w / 2) * 2
        gfps = min(rate, (10, 12, 15, 20)[q])
        args += ["-an", "-vf", f"fps={gfps},scale={gw}:{gh}:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=sierra2_4a"]
    else:
        if vf:
            args += ["-vf", ",".join(vf)]
        if s["format"] == "mp4_h264":
            args += ["-c:v", "libx264", "-preset", ("veryfast", "medium", "slow", "slow")[q], "-crf", str((27, 21, 18, 15)[q]),
                     "-pix_fmt", "yuv420p", "-profile:v", "high", "-movflags", "+faststart",
                     "-c:a", "aac", "-b:a", ("128k", "192k", "256k", "320k")[q]]
        elif s["format"] == "mp4_h265":
            args += ["-c:v", "libx265", "-preset", ("veryfast", "medium", "slow", "slow")[q], "-crf", str((30, 25, 22, 19)[q]),
                     "-pix_fmt", "yuv420p", "-tag:v", "hvc1", "-x265-params", "log-level=error", "-movflags", "+faststart",
                     "-c:a", "aac", "-b:a", ("128k", "192k", "256k", "320k")[q]]
        elif s["format"] == "webm":
            args += ["-c:v", "libvpx-vp9", "-b:v", "0", "-crf", str((38, 32, 28, 24)[q]), "-row-mt", "1", "-deadline", "good",
                     "-cpu-used", ("5", "3", "2", "1")[q], "-pix_fmt", "yuv420p", "-c:a", "libopus", "-b:a", ("96k", "128k", "160k", "192k")[q]]
        else:   # ProRes 422 (Proxy/LT/standard/HQ) for further editing
            args += ["-c:v", "prores_ks", "-profile:v", ("0", "1", "2", "3")[q], "-pix_fmt", "yuv422p10le", "-vendor", "apl0",
                     "-movflags", "+faststart", "-c:a", "pcm_s16le"]
        args += ["-ar", "48000", "-ac", "2"] if s["format"] != "mov_prores" else ["-ar", "48000"]
    args.append(out)
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0  # type: ignore[attr-defined]
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, creationflags=flags)
    while True:
        try:
            _, err = proc.communicate(timeout=1)
            break
        except subprocess.TimeoutExpired:
            if cancel_check and cancel_check():
                proc.kill(); proc.wait()
                raise DeliveryError("cancelled")
    if proc.returncode != 0:
        Path(out).unlink(missing_ok=True)
        raise DeliveryError("The export could not be written in that format: " + err.decode(errors="replace")[-400:])
    return out


# ---------------------------------------------------------------------------------------------
# Caption files (SRT / VTT)
# ---------------------------------------------------------------------------------------------

def _ts(ms: int, sep: str) -> str:
    ms = max(0, int(ms))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def caption_cues(scenes_with_times: list[tuple[object, int, int]], words_per_cue: int = 7) -> list[tuple[int, int, str]]:
    """(start, end, text) cues for the whole video. scenes_with_times: (scene, start_ms, length_ms)."""
    cues = []
    for scene, start, length in scenes_with_times:
        font = getattr(scene, "font_json", None) or {}
        text = (getattr(scene, "subtitle_text", "") or "").strip()
        if not text or not font.get("captions_enabled", True):
            continue
        n = max(1, min(12, int(font.get("phrase_words", 0) or 0) if font.get("split") == "phrases" else words_per_cue))
        words = text.split()
        tr = (font.get("transcript") or {}).get("words") or []
        cd = int(((getattr(scene, "look_json", None) or {}).get("countdown") or {}).get("seconds", 0)) * 1000
        if len(tr) == len(words):
            for i in range(0, len(words), n):
                a = start + cd + int(tr[i][1])
                b = start + cd + int(tr[min(i + n, len(tr)) - 1][2])
                cues.append((a, max(b, a + 300), " ".join(words[i:i + n])))
        else:
            body = max(500, length - cd)
            chunks = [words[i:i + n] for i in range(0, len(words), n)]
            total = sum(len(" ".join(c)) for c in chunks) or 1
            t = start + cd
            for c in chunks:
                d = int(body * len(" ".join(c)) / total)
                cues.append((t, t + d, " ".join(c)))
                t += d
    return cues


def captions_file(cues: list[tuple[int, int, str]], fmt: str) -> str:
    if fmt == "vtt":
        return "WEBVTT\n\n" + "".join(f"{_ts(a, '.')} --> {_ts(b, '.')}\n{t}\n\n" for a, b, t in cues)
    return "".join(f"{i}\n{_ts(a, ',')} --> {_ts(b, ',')}\n{t}\n\n" for i, (a, b, t) in enumerate(cues, 1))
