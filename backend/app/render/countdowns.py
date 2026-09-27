"""Cinema countdowns that can be inserted as a scene anywhere in a project.

  film     classic Academy leader: grey frame, sweeping wedge, circles, crosshair, big
           numbers, film grain, scratches, dust, flicker, gate weave, projector clatter;
           black & white or sepia
  modern   dark background, glowing progress ring, numbers that pop in
  minimal  white numbers fading on black

Counts from N (3–10) down to 2, then one second of black (as a real leader does, so the
picture starts exactly 2 s after the "2"). Beeps: every number, only the classic 2-pop, or
none. Frames stream into FFmpeg one at a time (no large memory use at 4K); the result is an
MP4 with sound, cached by its settings.
"""
from __future__ import annotations

import hashlib
import math
import os
import random
import subprocess
import uuid
from pathlib import Path

import numpy as np

from app.config import BUNDLED_FONT_PATH, FFMPEG_BIN, PROXIES_DIR

CACHE = Path(PROXIES_DIR) / "countdowns"
STYLES = ("film", "modern", "minimal")
BEEPS = ("each", "two-pop", "none")
TONES = ("bw", "sepia")


class CountdownError(ValueError):
    pass


def clean(raw: dict) -> dict:
    raw = raw or {}
    style = raw.get("style", "film")
    beep = raw.get("beep", "each")
    tone = raw.get("tone", "bw")
    seconds = raw.get("seconds", 5)
    color = raw.get("color", "#8F7CF0")
    if style not in STYLES:
        raise CountdownError("Countdown style must be one of: " + ", ".join(STYLES) + ".")
    if beep not in BEEPS:
        raise CountdownError("Countdown beep must be one of: " + ", ".join(BEEPS) + ".")
    if tone not in TONES:
        raise CountdownError("Countdown tone must be bw or sepia.")
    if isinstance(seconds, bool) or not isinstance(seconds, int) or not 3 <= seconds <= 10:
        raise CountdownError("Countdown length must be a whole number of seconds from 3 to 10.")
    if not isinstance(color, str) or len(color) != 7 or not color.startswith("#"):
        raise CountdownError("Countdown colour must look like #RRGGBB.")
    int(color[1:], 16)
    return {"style": style, "beep": beep, "tone": tone, "seconds": seconds, "color": color.upper()}


def _font(size: int):
    from PIL import ImageFont
    return ImageFont.truetype(str(BUNDLED_FONT_PATH.parent / "NotoSans-Bold.ttf"), size)


def _film_frame(W, H, f, fps, total, rng):
    from PIL import Image, ImageDraw
    sec, frac = divmod(f / fps, 1)
    number = total - int(sec)
    flicker = rng.uniform(-9, 9)
    if number <= 1:
        img = Image.new("L", (W, H), int(max(0, 8 + flicker / 3)))
    else:
        img = Image.new("L", (W, H), int(150 + flicker))
        d = ImageDraw.Draw(img)
        cx, cy, r = W / 2, H / 2, H * 0.36
        d.pieslice([cx - r * 1.7, cy - r * 1.7, cx + r * 1.7, cy + r * 1.7], -90, -90 + 360 * frac, fill=int(96 + flicker))
        for rr, w in ((r, 6), (r * 0.82, 4)):
            d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=236, width=max(2, int(w * H / 1080)))
        lw = max(2, int(3 * H / 1080))
        d.line([0, cy, W, cy], fill=40, width=lw)
        d.line([cx, 0, cx, H], fill=40, width=lw)
        d.text((cx, cy), str(number), font=_font(int(H * 0.44)), fill=18, anchor="mm")
    d = ImageDraw.Draw(img)
    # damage: scratches, dust, hairs
    for _ in range(rng.randint(0, 2)):
        x = rng.uniform(0.05, 0.95) * W
        d.line([x, 0, x + rng.uniform(-6, 6), H], fill=rng.choice((25, 225)), width=max(1, int(H / 900)))
    for _ in range(rng.randint(2, 9)):
        x, y, s = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(1, 4) * H / 720
        d.ellipse([x, y, x + s, y + s], fill=rng.choice((10, 20, 235)))
    if rng.random() < 0.08:
        x, y = rng.uniform(0.1, 0.9) * W, rng.uniform(0.1, 0.9) * H
        d.arc([x, y, x + H * 0.12, y + H * 0.2], rng.uniform(0, 180), rng.uniform(180, 360), fill=15, width=max(1, int(H / 700)))
    # gate weave: the frame drifts a little
    dx, dy = int(rng.uniform(-2, 2) * H / 720), int(rng.uniform(-3, 3) * H / 720)
    arr = np.asarray(img)
    arr = np.roll(np.roll(arr, dy, axis=0), dx, axis=1)
    return np.repeat(arr[..., None], 3, axis=2)


def _modern_frame(W, H, f, fps, total, color):
    from PIL import Image, ImageDraw, ImageFilter
    sec, frac = divmod(f / fps, 1)
    number = total - int(sec)
    base = Image.new("RGB", (W, H), (16, 17, 26))
    if number <= 1:
        return np.asarray(base)
    col = tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))
    cx, cy, r = W / 2, H / 2, H * 0.3
    ring = Image.new("RGB", (W, H), (0, 0, 0))
    rd = ImageDraw.Draw(ring)
    rd.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(60, 62, 80), width=max(3, int(H * 0.012)))
    rd.arc([cx - r, cy - r, cx + r, cy + r], -90, -90 + 360 * (1 - frac), fill=col, width=max(4, int(H * 0.018)))
    glow = ring.filter(ImageFilter.GaussianBlur(H * 0.02))
    out = Image.fromarray(np.clip(np.asarray(base, int) + np.asarray(glow, int) * 1.4 + np.asarray(ring, int), 0, 255).astype(np.uint8))
    pop = min(1.0, frac / 0.18)
    scale = 0.6 + 0.5 * pop - 0.1 * max(0.0, (frac - 0.18) / 0.82) * 0  # grows fast, then holds
    scale = 0.6 + 0.45 * math.sin(pop * math.pi / 2) + (0.05 if pop < 1 else 0)
    d = ImageDraw.Draw(out)
    d.text((cx, cy), str(number), font=_font(max(10, int(H * 0.3 * scale))), fill=(255, 255, 255), anchor="mm")
    return np.asarray(out)


def _minimal_frame(W, H, f, fps, total):
    from PIL import Image, ImageDraw
    sec, frac = divmod(f / fps, 1)
    number = total - int(sec)
    img = Image.new("RGB", (W, H), (0, 0, 0))
    if number > 1:
        a = int(255 * (min(1.0, frac / 0.2) if frac < 0.7 else max(0.0, (1 - frac) / 0.3)))
        ImageDraw.Draw(img).text((W / 2, H / 2), str(number), font=_font(int(H * 0.28)), fill=(a, a, a), anchor="mm")
    return np.asarray(img)


def _audio(opts: dict, fps: int, dur: float, out_wav: Path) -> None:
    """Beeps (and projector clatter for the film style) as a WAV."""
    total = opts["seconds"]
    beeps = []
    if opts["beep"] == "each":
        beeps = [(i, 0.12 if opts["style"] != "minimal" else 0.05) for i in range(total - 1)]
    elif opts["beep"] == "two-pop":
        beeps = [(total - 2, 1 / fps)]                    # the classic one-frame 1 kHz pop at "2"
    freq = {"film": 1000, "modern": 880, "minimal": 1500}[opts["style"]]
    inputs, labels = [], []
    for k, (at, length) in enumerate(beeps):
        inputs += ["-f", "lavfi", "-i", f"sine=frequency={freq}:sample_rate=48000:duration={length:.4f}"]
        labels.append(f"[{k}]adelay={int(at * 1000)}|{int(at * 1000)},volume=3.0[b{k}]")   # lavfi sine starts at 1/8 amplitude: ≈ -9 dBFS
    n = len(beeps)
    if opts["style"] == "film":
        from app.render.finishing import projector_wav
        inputs += ["-stream_loop", "-1", "-i", str(projector_wav(fps))]
        labels.append(f"[{n}]atrim=0:{dur:.3f},volume=0.35[pj]")
    mix = "".join(f"[b{k}]" for k in range(n)) + ("[pj]" if opts["style"] == "film" else "")
    parts = len(beeps) + (1 if opts["style"] == "film" else 0)
    if parts == 0:
        cmd = [FFMPEG_BIN, "-y", "-v", "error", "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo", "-t", f"{dur:.3f}", str(out_wav)]
    else:
        graph = ";".join(labels) + f";{mix}amix=inputs={parts}:normalize=0,apad,atrim=0:{dur:.3f},aformat=channel_layouts=stereo[a]"
        cmd = [FFMPEG_BIN, "-y", "-v", "error", *inputs, "-filter_complex", graph, "-map", "[a]", "-ar", "48000", str(out_wav)]
    subprocess.run(cmd, check=True, capture_output=True, timeout=120)


def render(opts: dict, width: int, height: int, fps: int) -> Path:
    """Countdown MP4 (H.264 + AAC) at the project's size; cached by its settings."""
    opts = clean(opts)
    CACHE.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(f"v2|{sorted(opts.items())}|{width}x{height}|{fps}".encode()).hexdigest()[:20]
    out = CACHE / f"countdown_{key}.mp4"
    if out.exists():
        return out
    total, dur = opts["seconds"], float(opts["seconds"])
    # draw at up to 720p, then scale to the project size (the look is soft by nature)
    ph = min(height, 720)
    pw = int(round(width * ph / height / 2)) * 2
    wav = out.with_suffix(f".{uuid.uuid4().hex[:6]}.wav")
    _audio(opts, fps, dur, wav)
    tone = ",colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131:0" if opts["style"] == "film" and opts["tone"] == "sepia" else ""
    grain = ",noise=alls=14:allf=t" if opts["style"] == "film" else ""
    tmp = out.with_name(f"{out.stem}.{os.getpid()}.{uuid.uuid4().hex[:6]}.tmp.mp4")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0  # type: ignore[attr-defined]
    proc = subprocess.Popen([FFMPEG_BIN, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{pw}x{ph}", "-r", str(fps), "-i", "-",
                             "-i", str(wav), "-vf", f"scale={width}:{height}:flags=bicubic{grain}{tone},format=yuv420p",
                             "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-shortest", str(tmp)],
                            stdin=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=flags)
    rng = random.Random(42)
    try:
        for f in range(int(total * fps)):
            if opts["style"] == "film":
                frame = _film_frame(pw, ph, f, fps, total, rng)
            elif opts["style"] == "modern":
                frame = _modern_frame(pw, ph, f, fps, total, opts["color"])
            else:
                frame = _minimal_frame(pw, ph, f, fps, total)
            proc.stdin.write(np.ascontiguousarray(frame, dtype=np.uint8).tobytes())
        proc.stdin.close()
        err = proc.stderr.read().decode(errors="replace")
        if proc.wait(timeout=300) != 0:
            raise CountdownError("The countdown could not be rendered: " + err[-300:])
    finally:
        wav.unlink(missing_ok=True)
    os.replace(tmp, out)
    return out
