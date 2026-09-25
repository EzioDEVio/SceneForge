"""Scene-level effects, applied over the whole scene picture (all shots),
together with picture-in-picture overlays and before captions:

  redact regions (blur / pixelate) -> overlays -> spotlight -> light leaks -> camera shake

Keeping them at scene level means their timing is in scene time, even when a
scene has several images or clips. Settings live in scene.look_json:

  shake     {amount 0-100, speed 0-100, impact bool}
  spotlight {x, y, w, h (% of frame, centre and size), shape rect|ellipse,
             dim 0-100, feather 0-100, start_ms, end_ms|None}
  redact    [{x, y, w, h, mode blur|pixelate, strength 0-100, start_ms, end_ms|None}]  (max 6)
  leak      {amount 0-100, speed 0-100, color warm|cool|rainbow}
  tone      {shadow #RRGGBB, highlight #RRGGBB, amount 0-100, balance -100..100}
            (split toning; baked into the grade LUT, see grade.py)
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import threading
import uuid
from pathlib import Path

import numpy as np

from app.config import FFMPEG_BIN

_HEX = re.compile(r"#[0-9A-Fa-f]{6}")
_lock = threading.Lock()


class SceneFxError(ValueError):
    pass


def _num(d: dict, key: str, lo: float, hi: float, name: str) -> float:
    v = d.get(key)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi:
        raise SceneFxError(f"{name} {key} must be between {lo} and {hi}.")
    return v


def _timing(d: dict, name: str) -> dict:
    start = int(_num({"start_ms": d.get("start_ms", 0)}, "start_ms", 0, 3_600_000, name))
    end = d.get("end_ms")
    if end is not None:
        if isinstance(end, bool) or not isinstance(end, (int, float)) or end <= start:
            raise SceneFxError(f"{name}: end must be after start.")
        end = int(end)
    return {"start_ms": start, "end_ms": end}


def _box(d: dict, name: str) -> dict:
    return {k: round(float(_num(d, k, lo, hi, name)), 2) for k, lo, hi in
            (("x", -10, 110), ("y", -10, 110), ("w", 1, 100), ("h", 1, 100))}


def _only(d, allowed: set, name: str) -> dict:
    if not isinstance(d, dict) or set(d) - allowed:
        raise SceneFxError(f"{name} settings may only contain: {', '.join(sorted(allowed))}.")
    return d


def clean_shake(d) -> dict:
    d = _only({"amount": 40, "speed": 50, "impact": False, **(d or {})}, {"amount", "speed", "impact"}, "Camera shake")
    if not isinstance(d["impact"], bool):
        raise SceneFxError("Camera shake impact must be true or false.")
    return {"amount": int(_num(d, "amount", 0, 100, "Camera shake")), "speed": int(_num(d, "speed", 0, 100, "Camera shake")), "impact": d["impact"]}


SPOT_DEFAULT = {"x": 50, "y": 50, "w": 40, "h": 50, "shape": "ellipse", "dim": 65, "feather": 40, "start_ms": 0, "end_ms": None}


def clean_spotlight(d) -> dict:
    d = _only({**SPOT_DEFAULT, **(d or {})}, set(SPOT_DEFAULT), "Spotlight")
    if d["shape"] not in ("rect", "ellipse"):
        raise SceneFxError("Spotlight shape must be rect or ellipse.")
    return {**_box(d, "Spotlight"), "shape": d["shape"], "dim": int(_num(d, "dim", 0, 100, "Spotlight")),
            "feather": int(_num(d, "feather", 0, 100, "Spotlight")), **_timing(d, "Spotlight")}


REDACT_DEFAULT = {"x": 50, "y": 50, "w": 20, "h": 20, "mode": "blur", "strength": 70, "start_ms": 0, "end_ms": None}


def clean_redact(items) -> list[dict]:
    if not isinstance(items, list) or len(items) > 6:
        raise SceneFxError("Blur regions must be a list of at most 6 regions.")
    out = []
    for i, d in enumerate(items):
        name = f"Blur region {i + 1}"
        d = _only({**REDACT_DEFAULT, **(d or {})}, set(REDACT_DEFAULT), name)
        if d["mode"] not in ("blur", "pixelate"):
            raise SceneFxError(f"{name}: mode must be blur or pixelate.")
        out.append({**_box(d, name), "mode": d["mode"], "strength": int(_num(d, "strength", 1, 100, name)), **_timing(d, name)})
    return out


def clean_leak(d) -> dict:
    d = _only({"amount": 50, "speed": 40, "color": "warm", **(d or {})}, {"amount", "speed", "color"}, "Light leaks")
    if d["color"] not in ("warm", "cool", "rainbow"):
        raise SceneFxError("Light leak colour must be warm, cool or rainbow.")
    return {"amount": int(_num(d, "amount", 0, 100, "Light leaks")), "speed": int(_num(d, "speed", 0, 100, "Light leaks")), "color": d["color"]}


def clean_tone(d) -> dict:
    d = _only({"shadow": "#1E5A8C", "highlight": "#F2A541", "amount": 40, "balance": 0, **(d or {})},
              {"shadow", "highlight", "amount", "balance"}, "Split toning")
    for k in ("shadow", "highlight"):
        if not isinstance(d[k], str) or not _HEX.fullmatch(d[k]):
            raise SceneFxError(f"Split toning {k} colour must look like #RRGGBB.")
    return {"shadow": d["shadow"].upper(), "highlight": d["highlight"].upper(),
            "amount": int(_num(d, "amount", 0, 100, "Split toning")), "balance": int(_num(d, "balance", -100, 100, "Split toning"))}


def clean_wheels(d) -> dict:
    """Lift / gamma / gain wheels: each an [r, g, b] offset in -100..100
    (0 = neutral). Lift moves shadows, gamma midtones, gain highlights."""
    d = _only({"lift": [0, 0, 0], "gamma": [0, 0, 0], "gain": [0, 0, 0], **(d or {})}, {"lift", "gamma", "gain"}, "Colour wheels")
    out = {}
    for k in ("lift", "gamma", "gain"):
        v = d[k]
        if not isinstance(v, list) or len(v) != 3 or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not -100 <= x <= 100 for x in v):
            raise SceneFxError(f"Colour wheel {k} must be three numbers between -100 and 100.")
        out[k] = [int(round(x)) for x in v]
    return out


CLEANERS = {"wheels": clean_wheels, "shake": clean_shake, "spotlight": clean_spotlight, "redact": clean_redact, "leak": clean_leak, "tone": clean_tone}


def has_scene_fx(look: dict | None) -> bool:
    look = look or {}
    return bool(look.get("shake") or look.get("spotlight") or look.get("redact") or look.get("leak") or look.get("route"))


# --------------------------------------------------------------------------
# Generated media (cached)
# --------------------------------------------------------------------------
def spotlight_png(sp: dict, w: int, h: int, cache: Path) -> str:
    from PIL import Image, ImageDraw, ImageFilter
    key = hashlib.sha256(f"v1|{w}x{h}|{sorted(sp.items())}".encode()).hexdigest()[:20]
    cache.mkdir(parents=True, exist_ok=True)
    out = cache / f"spot_{key}.png"
    if out.exists():
        return str(out)
    cx, cy, bw, bh = sp["x"] / 100 * w, sp["y"] / 100 * h, sp["w"] / 100 * w, sp["h"] / 100 * h
    hole = Image.new("L", (w, h), 0)
    box = [cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2]
    (ImageDraw.Draw(hole).ellipse if sp["shape"] == "ellipse" else ImageDraw.Draw(hole).rectangle)(box, fill=255)
    if sp["feather"]:
        hole = hole.filter(ImageFilter.GaussianBlur(sp["feather"] / 100 * min(bw, bh) * 0.35))
    alpha = (255 - np.asarray(hole, dtype=np.float32)) * sp["dim"] / 100
    img = np.zeros((h, w, 4), np.uint8)
    img[..., 3] = alpha.astype(np.uint8)
    Image.fromarray(img, "RGBA").save(out)
    return str(out)


LEAK_COLORS = {"warm": [(255, 140, 40), (255, 70, 30), (255, 200, 90)],
               "cool": [(80, 170, 255), (140, 90, 255), (90, 230, 220)],
               "rainbow": [(255, 80, 60), (255, 200, 60), (80, 220, 120), (70, 150, 255), (200, 90, 255)]}


def leak_clip(color: str, speed: int, cache: Path, fps: int = 15, seconds: int = 6) -> str:
    """Seamless loop of soft coloured light drifting across a black frame
    (480x270), to be screen-blended over the picture."""
    key = f"v1_{color}_{speed}_{fps}_{seconds}"
    cache.mkdir(parents=True, exist_ok=True)
    out = cache / f"leak_{key}.mkv"
    with _lock:
        if out.exists():
            return str(out)
        w, h, n = 480, 270, fps * seconds
        rng = np.random.default_rng(7)
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        frames = np.zeros((n, h, w, 3), np.float32)
        palette = LEAK_COLORS[color]
        cycles = 1 + round(speed / 34)                        # whole cycles per loop keep it seamless
        for k in range(5):
            col = np.array(palette[k % len(palette)], np.float32) / 255
            phase, r = rng.uniform(0, 6.28), rng.uniform(0.25, 0.55) * w
            ax, ay = rng.uniform(0.3, 0.7) * w, rng.uniform(0.2, 0.6) * h
            edge = rng.choice([-0.15, 1.15]) * w                 # leaks live near the frame edges
            for f in range(n):
                a = 2 * np.pi * cycles * f / n + phase
                cx = edge + np.sin(a) * ax * 0.5
                cy = h / 2 + np.cos(a * 0.7 + k) * ay
                glow = np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * r * r)) * (0.55 + 0.45 * np.sin(a * 1.3 + k))
                frames[f] += glow[..., None] * col
        data = (np.clip(frames, 0, 1) * 255).astype(np.uint8)
        tmp = out.with_name(f"{out.stem}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp.mkv")
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0  # type: ignore[attr-defined]
        r = subprocess.run([FFMPEG_BIN, "-y", "-hide_banner", "-nostdin", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{w}x{h}", "-r", str(fps), "-i", "-", "-c:v", "ffv1", "-pix_fmt", "bgr0", str(tmp)],
                           input=data.tobytes(), capture_output=True, timeout=300, creationflags=flags)
        if r.returncode != 0:
            tmp.unlink(missing_ok=True)
            raise SceneFxError("The light leak layer could not be made.")
        os.replace(tmp, out)
        return str(out)


# --------------------------------------------------------------------------
# Filter graph pieces (all operate on a labelled stream, return new label)
# --------------------------------------------------------------------------
def _enable(t: dict, dur: float) -> str:
    st = t["start_ms"] / 1000
    en = min(dur, t["end_ms"] / 1000) if t.get("end_ms") else dur
    return f"between(t,{st:.3f},{en:.3f})"


def redact_graph(base: str, regions: list[dict], w: int, h: int, dur: float) -> tuple[list[str], str]:
    graph = []
    for i, r in enumerate(regions):
        rw, rh = max(4, int(r["w"] / 100 * w) // 2 * 2), max(4, int(r["h"] / 100 * h) // 2 * 2)
        x = int(min(max(0, r["x"] / 100 * w - rw / 2), w - rw))
        y = int(min(max(0, r["y"] / 100 * h - rh / 2), h - rh))
        if r["mode"] == "pixelate":
            cells = max(2, int(round(3 + (100 - r["strength"]) / 100 * 30)))     # fewer cells = stronger
            fx = f"scale={cells}:-2:flags=area,scale={rw}:{rh}:flags=neighbor"
        else:
            rad = max(2, int(min(rw, rh) * (0.05 + 0.25 * r["strength"] / 100)))
            fx = f"boxblur=luma_radius={rad}:luma_power=2:chroma_radius={max(1, rad // 2)}:chroma_power=2"
        graph += [f"[{base}]split=2[rb{i}][rs{i}]", f"[rs{i}]crop={rw}:{rh}:{x}:{y},{fx}[rp{i}]",
                  f"[rb{i}][rp{i}]overlay=x={x}:y={y}:enable='{_enable(r, dur)}'[red{i}]"]
        base = f"red{i}"
    return graph, base


def spotlight_graph(base: str, sp: dict, png: str, fps: int, dur: float) -> tuple[list[str], str]:
    from app.render.ffmpeg_utils import escape_path_for_filter
    st = sp["start_ms"] / 1000
    en = min(dur, sp["end_ms"] / 1000) if sp.get("end_ms") else dur
    fade = min(0.4, max(0.05, (en - st) / 4))
    graph = [f"movie='{escape_path_for_filter(png)}':loop=0,setpts=N/({fps}*TB),format=rgba,"
             f"fade=t=in:st={st:.3f}:d={fade:.3f}:alpha=1,fade=t=out:st={max(st, en - fade):.3f}:d={fade:.3f}:alpha=1[spm]",
             f"[{base}][spm]overlay=shortest=1:enable='between(t,{st:.3f},{en:.3f})'[spot]"]
    return graph, "spot"


def leak_graph(base: str, lk: dict, clip: str, w: int, h: int, fps: int) -> tuple[list[str], str]:
    from app.render.ffmpeg_utils import escape_path_for_filter
    graph = [f"movie='{escape_path_for_filter(clip)}':loop=0,setpts=N/(15*TB),fps={fps},scale={w}:{h}:flags=bicubic,format=gbrp[lkc]",
             f"[{base}]format=gbrp[lkb]",
             f"[lkb][lkc]blend=all_mode=screen:all_opacity={0.25 + 0.75 * lk['amount'] / 100:.3f}:shortest=1,format=yuv420p[leak]"]
    return graph, "leak"


def shake_graph(base: str, sk: dict, w: int, h: int, fps: int) -> tuple[list[str], str]:
    """Handheld-style shake (layered sines at different rates) and an optional
    impact zoom that punches in at the start and settles."""
    a = sk["amount"] / 100
    spd = 0.4 + 2.2 * sk["speed"] / 100
    margin = 1.04 + 0.06 * a
    ax, ay = w * 0.012 * a, h * 0.016 * a
    impact = "+0.14*exp(-it*5)" if sk["impact"] else ""
    dx = f"{ax:.2f}*(sin(it*{7.3 * spd:.3f})+0.6*sin(it*{17.9 * spd:.3f}+1.3)+0.3*sin(it*{31.1 * spd:.3f}))"
    dy = f"{ay:.2f}*(sin(it*{5.9 * spd:.3f}+0.7)+0.6*sin(it*{13.7 * spd:.3f}+2.1)+0.3*sin(it*{27.3 * spd:.3f}))"
    graph = [f"[{base}]zoompan=z='{margin:.3f}{impact}':d=1:s={w}x{h}:fps={fps}:"
             f"x='iw/2-(iw/zoom/2)+({dx})/zoom':y='ih/2-(ih/zoom/2)+({dy})/zoom'[shk]"]
    return graph, "shk"


def _wrap(fn):
    def clean(d):
        try:
            return fn(d)
        except ValueError as e:
            raise SceneFxError(str(e)) from None
    return clean


from app.render.layouts import clean_layout  # noqa: E402
from app.render.photo import clean_parallax  # noqa: E402
from app.render.routes import clean_route  # noqa: E402

CLEANERS.update(layout=_wrap(clean_layout), route=_wrap(clean_route), parallax=_wrap(clean_parallax))
