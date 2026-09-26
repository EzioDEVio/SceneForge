"""Animated annotations: arrows, circles, underlines/highlighters, boxes and callouts that
draw themselves on screen, for pointing things out in documentary shots.

look.annotations = [ {type, x, y, x2, y2, color, width, text, start_ms, draw_ms, end_ms|None, style}, ... ]  (max 10)
  arrow      line from (x, y) to (x2, y2), then the head appears     style: straight | curved
  circle     ellipse inside the box (x, y)–(x2, y2), drawn as a sweep  style: neat | hand
  underline  line from (x, y) to (x2, y)                              style: line | highlighter
  box        rectangle (x, y)–(x2, y2)
  callout    label box at (x, y) with a pointer to (x2, y2)
All positions are % of the frame. Rendered once into a transparent clip (cached) and overlaid
in the scene pass; it fades out over the last 0.3 s before end_ms.
"""
from __future__ import annotations

import hashlib
import math
import os
import re
import subprocess
import uuid
from pathlib import Path

import numpy as np

from app.config import FFMPEG_BIN

TYPES = ("arrow", "circle", "underline", "box", "callout")
STYLES = {"arrow": ("straight", "curved"), "circle": ("neat", "hand"), "underline": ("line", "highlighter"), "box": ("neat",), "callout": ("neat",)}
DEFAULT = {"type": "arrow", "x": 30, "y": 60, "x2": 55, "y2": 40, "color": "#FFD84D", "width": 8, "text": "",
           "start_ms": 0, "draw_ms": 800, "end_ms": None, "style": ""}


class AnnotationError(ValueError):
    pass


def clean_annotations(items) -> list[dict]:
    if not isinstance(items, list) or len(items) > 10:
        raise AnnotationError("Annotations must be a list of at most 10 items.")
    out = []
    for i, raw in enumerate(items):
        name = f"Annotation {i + 1}"
        if not isinstance(raw, dict) or set(raw) - set(DEFAULT) - {"id"}:
            raise AnnotationError(f"{name} has unknown settings.")
        a = {**DEFAULT, **raw}
        if a["type"] not in TYPES:
            raise AnnotationError(f"{name}: type must be one of: {', '.join(TYPES)}.")
        for k, lo, hi in (("x", -10, 110), ("y", -10, 110), ("x2", -10, 110), ("y2", -10, 110), ("width", 2, 40),
                          ("start_ms", 0, 3_600_000), ("draw_ms", 100, 10000)):
            v = a[k]
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi:
                raise AnnotationError(f"{name}: {k} must be between {lo} and {hi}.")
        if a["end_ms"] is not None and (isinstance(a["end_ms"], bool) or not isinstance(a["end_ms"], (int, float)) or a["end_ms"] <= a["start_ms"]):
            raise AnnotationError(f"{name}: end must be after start.")
        if not isinstance(a["color"], str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", a["color"]):
            raise AnnotationError(f"{name}: colour must look like #RRGGBB.")
        if not isinstance(a["text"], str) or len(a["text"]) > 80:
            raise AnnotationError(f"{name}: text must be at most 80 characters.")
        style = a["style"] or STYLES[a["type"]][0]
        if style not in STYLES[a["type"]]:
            raise AnnotationError(f"{name}: style must be one of: {', '.join(STYLES[a['type']])}.")
        out.append({"id": str(raw.get("id") or f"an{i}")[:40], "type": a["type"], "style": style,
                    **{k: round(float(a[k]), 2) for k in ("x", "y", "x2", "y2")}, "width": int(a["width"]),
                    "color": a["color"].upper(), "text": a["text"].strip(), "start_ms": int(a["start_ms"]),
                    "draw_ms": int(a["draw_ms"]), "end_ms": None if a["end_ms"] is None else int(a["end_ms"])})
    return out


def _ease(p: float) -> float:
    p = max(0.0, min(1.0, p))
    return 0.5 - 0.5 * math.cos(math.pi * p)


def _partial(points: list[tuple[float, float]], prog: float) -> list[tuple[float, float]]:
    """The first `prog` (0..1) of a polyline, by length."""
    seg = [math.dist(points[i], points[i + 1]) for i in range(len(points) - 1)]
    total = sum(seg) or 1
    want, out, acc = prog * total, [points[0]], 0.0
    for i, L in enumerate(seg):
        if acc + L <= want:
            out.append(points[i + 1]); acc += L
        else:
            r = (want - acc) / L if L else 0
            out.append((points[i][0] + (points[i + 1][0] - points[i][0]) * r, points[i][1] + (points[i + 1][1] - points[i][1]) * r))
            break
    return out


def _shape_points(a: dict, W: int, H: int) -> list[tuple[float, float]]:
    x1, y1, x2, y2 = a["x"] / 100 * W, a["y"] / 100 * H, a["x2"] / 100 * W, a["y2"] / 100 * H
    t = a["type"]
    if t == "arrow":
        if a["style"] == "curved":
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            nx, ny = -(y2 - y1), (x2 - x1)
            c = (mx + nx * 0.25, my + ny * 0.25)
            return [((1 - s) ** 2 * x1 + 2 * (1 - s) * s * c[0] + s * s * x2, (1 - s) ** 2 * y1 + 2 * (1 - s) * s * c[1] + s * s * y2) for s in np.linspace(0, 1, 40)]
        return [(x1, y1), (x2, y2)]
    if t == "underline":
        return [(x1, y1), (x2, y1)]
    if t == "box":
        return [(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)]
    if t == "circle":
        cx, cy, rx, ry = (x1 + x2) / 2, (y1 + y2) / 2, abs(x2 - x1) / 2, abs(y2 - y1) / 2
        hand = a["style"] == "hand"
        turns = 1.12 if hand else 1.0            # a hand-drawn circle overshoots its start
        pts = []
        for s in np.linspace(0, turns, 120):
            ang = -math.pi / 2 + 2 * math.pi * s
            wob = 1 + (0.035 * math.sin(3 * ang + 0.7) + 0.02 * s if hand else 0)
            pts.append((cx + rx * wob * math.cos(ang), cy + ry * wob * math.sin(ang)))
        return pts
    return [(x1, y1), (x2, y2)]            # callout pointer


def annotation_clip(a: dict, w: int, h: int, fps: int, dur_ms: int, cache: Path) -> str:
    """Transparent clip for one annotation, from its start to its end (or the scene end)."""
    from PIL import Image, ImageDraw
    from app.render.routes import _label_font, _label_text
    end_ms = min(dur_ms, a["end_ms"]) if a["end_ms"] else dur_ms
    length = max(1, end_ms - a["start_ms"])
    key = hashlib.sha256(f"v1|{w}x{h}|{fps}|{length}|{sorted((k, str(v)) for k, v in a.items())}".encode()).hexdigest()[:20]
    cache.mkdir(parents=True, exist_ok=True)
    out = cache / f"annot_{key}.mov"
    if out.exists():
        return str(out)
    scale = 0.5 if w > 1280 else 1.0
    W, H = int(w * scale), int(h * scale)
    col = tuple(int(a["color"][i:i + 2], 16) for i in (1, 3, 5))
    lw = max(2, int(a["width"] * H / 1080))
    n = max(1, int(round(length / 1000 * fps)))
    draw_f = max(1, int(round(a["draw_ms"] / 1000 * fps)))
    fade_f = max(1, int(round(0.3 * fps)))
    pts = _shape_points(a, W, H)
    font = _label_font(a["text"], max(12, int(H * 0.038))) if a["type"] == "callout" else None
    text = _label_text(a["text"]) if a["type"] == "callout" else ""
    frames = []
    for f in range(n):
        prog = _ease(f / draw_f)
        alpha = 1.0 if f < n - fade_f else max(0.0, (n - f) / fade_f)
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        A = int(255 * alpha)
        if a["type"] == "underline" and a["style"] == "highlighter":
            part = _partial(pts, prog)
            if len(part) > 1:
                d.line(part, fill=col + (int(110 * alpha),), width=lw * 4)
        elif a["type"] == "callout":
            pop = min(1.0, f / max(1, draw_f * 0.6))
            part = _partial(pts, min(1.0, prog * 1.4))
            if len(part) > 1:
                d.line(part, fill=col + (A,), width=lw)
                tx, ty = part[-1]
                d.ellipse([tx - lw * 1.4, ty - lw * 1.4, tx + lw * 1.4, ty + lw * 1.4], fill=col + (A,))
            if text:
                tw, th = d.textbbox((0, 0), text, font=font)[2:]
                bx, by = pts[0][0] - tw / 2 - 12, pts[0][1] - th / 2 - 8
                bx, by = min(max(4, bx), W - tw - 28), min(max(4, by), H - th - 20)
                box_a = int(230 * alpha * pop)
                d.rounded_rectangle([bx, by, bx + tw + 24, by + th + 16], radius=10, fill=(18, 18, 24, box_a), outline=col + (int(255 * alpha * pop),), width=max(2, lw // 2))
                d.text((bx + 12, by + 5), text, font=font, fill=(255, 255, 255, int(255 * alpha * pop)))
        else:
            part = _partial(pts, prog)
            if len(part) > 1:
                d.line(part, fill=col + (A,), width=lw, joint="curve")
                if a["type"] == "arrow" and prog > 0.85:
                    (px, py), (hx, hy) = part[-2], part[-1]
                    ang = math.atan2(hy - py, hx - px)
                    s = lw * 3.4 * min(1.0, (prog - 0.85) / 0.15)
                    d.polygon([(hx + math.cos(ang) * s, hy + math.sin(ang) * s),
                               (hx + math.cos(ang + 2.5) * s, hy + math.sin(ang + 2.5) * s),
                               (hx + math.cos(ang - 2.5) * s, hy + math.sin(ang - 2.5) * s)], fill=col + (A,))
        frames.append(np.asarray(img))
    tmp = out.with_name(f"{out.stem}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp.mov")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0  # type: ignore[attr-defined]
    r = subprocess.run([FFMPEG_BIN, "-y", "-hide_banner", "-nostdin", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba",
                        "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-vf", f"scale={w}:{h}:flags=bicubic",
                        "-c:v", "qtrle", "-pix_fmt", "argb", str(tmp)],
                       input=np.stack(frames).tobytes(), capture_output=True, timeout=600, creationflags=flags)
    if r.returncode != 0:
        tmp.unlink(missing_ok=True)
        raise AnnotationError("An annotation could not be drawn.")
    os.replace(tmp, out)
    return str(out)


def annotations_graph(base: str, items: list[dict], clips: list[str]) -> tuple[list[str], str]:
    from app.render.ffmpeg_utils import escape_path_for_filter
    graph = []
    for i, (a, clip) in enumerate(zip(items, clips)):
        st = a["start_ms"] / 1000
        graph += [f"movie='{escape_path_for_filter(clip)}',setpts=PTS-STARTPTS+{st:.3f}/TB,format=rgba[an{i}c]",
                  f"[{base}][an{i}c]overlay=eof_action=pass:format=auto[an{i}]"]
        base = f"an{i}"
    return graph, base
