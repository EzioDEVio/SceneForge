"""Animated map routes: a line draws itself along points on the picture, with
pins popping in at each stop and a glowing head leading the line.

look.route = {"points": [[x, y], ...] (2-20, % of frame), "color": "#RRGGBB", "width": 2-30 (px at 1080p),
              "style": "solid" | "dashed", "pins": bool, "start_ms": int, "draw_ms": 300-20000}
The route is drawn once into a transparent clip (cached) and overlaid in the
scene pass; after drawing it stays on screen.
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

ROUTE_DEFAULT = {"points": [[20, 70], [45, 45], [75, 35]], "color": "#E8413C", "width": 8, "style": "solid", "pins": True, "start_ms": 0, "draw_ms": 3000}


class RouteError(ValueError):
    pass


def clean_route(d) -> dict:
    if not isinstance(d, dict) or set(d) - set(ROUTE_DEFAULT):
        raise RouteError("Route settings may only contain: " + ", ".join(ROUTE_DEFAULT) + ".")
    d = {**ROUTE_DEFAULT, **d}
    pts = d["points"]
    if not isinstance(pts, list) or not 2 <= len(pts) <= 20:
        raise RouteError("A route needs between 2 and 20 points.")
    clean_pts = []
    for p in pts:
        if not isinstance(p, list) or len(p) != 2 or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not -10 <= v <= 110 for v in p):
            raise RouteError("Each route point must be [x, y] in % of the frame.")
        clean_pts.append([round(float(p[0]), 2), round(float(p[1]), 2)])
    if not isinstance(d["color"], str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", d["color"]):
        raise RouteError("Route colour must look like #RRGGBB.")
    for key, lo, hi in (("width", 2, 30), ("start_ms", 0, 3_600_000), ("draw_ms", 300, 20000)):
        v = d[key]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi:
            raise RouteError(f"Route {key} must be between {lo} and {hi}.")
    if d["style"] not in ("solid", "dashed") or not isinstance(d["pins"], bool):
        raise RouteError("Route style must be solid or dashed, and pins true or false.")
    return {"points": clean_pts, "color": d["color"].upper(), "width": int(d["width"]), "style": d["style"],
            "pins": d["pins"], "start_ms": int(d["start_ms"]), "draw_ms": int(d["draw_ms"])}


def route_clip(route: dict, w: int, h: int, fps: int, cache: Path) -> str:
    """Transparent clip of the route being drawn (draw_ms long, plus 0.4 s for the last pin)."""
    from PIL import Image, ImageDraw, ImageFilter
    key = hashlib.sha256(f"v1|{w}x{h}|{fps}|{sorted((k, str(v)) for k, v in route.items())}".encode()).hexdigest()[:20]
    cache.mkdir(parents=True, exist_ok=True)
    out = cache / f"route_{key}.mov"
    if out.exists():
        return str(out)
    scale = 0.5 if w > 1280 else 1.0                          # draw at half size for big frames
    W, H = int(w * scale), int(h * scale)
    pts = [(x / 100 * W, y / 100 * H) for x, y in route["points"]]
    seg = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    total = sum(seg) or 1
    lw = max(1, int(route["width"] * H / 1080))
    col = tuple(int(route["color"][i:i + 2], 16) for i in (1, 3, 5))
    n = int(round((route["draw_ms"] + 400) / 1000 * fps))
    draw_frames = max(1, int(round(route["draw_ms"] / 1000 * fps)))
    frames = []
    for f in range(n):
        prog = min(1.0, f / draw_frames)
        prog = 0.5 - 0.5 * math.cos(math.pi * prog)            # ease in and out
        dist, path, reached = prog * total, [pts[0]], [0.0]
        acc = 0.0
        for i, L in enumerate(seg):
            if acc + L <= dist:
                path.append(pts[i + 1]); reached.append((acc + L) / total); acc += L
            else:
                r = (dist - acc) / L if L else 0
                path.append((pts[i][0] + (pts[i + 1][0] - pts[i][0]) * r, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * r))
                break
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        if len(path) > 1:
            if route["style"] == "dashed":
                dash, gap, carry = lw * 3, lw * 2, 0.0
                for a, b in zip(path, path[1:]):
                    L = math.dist(a, b); pos = -carry
                    while pos < L:
                        s0, s1 = max(0, pos), min(L, pos + dash)
                        if s1 > s0:
                            d.line([(a[0] + (b[0] - a[0]) * s0 / L, a[1] + (b[1] - a[1]) * s0 / L),
                                    (a[0] + (b[0] - a[0]) * s1 / L, a[1] + (b[1] - a[1]) * s1 / L)], fill=col + (255,), width=lw)
                        pos += dash + gap
                    carry = (pos - L) if pos > L else 0
            else:
                d.line(path, fill=col + (255,), width=lw, joint="curve")
            hx, hy = path[-1]
            glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(glow).ellipse([hx - lw * 2.2, hy - lw * 2.2, hx + lw * 2.2, hy + lw * 2.2], fill=col + (200,))
            img = Image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(lw * 1.2)), img)
            d = ImageDraw.Draw(img)
            d.ellipse([hx - lw, hy - lw, hx + lw, hy + lw], fill=(255, 255, 255, 255))
        if route["pins"]:
            for (px, py), when in zip(pts, [0.0] + [sum(seg[:i + 1]) / total for i in range(len(seg))]):
                age = (prog - when) * route["draw_ms"] / 1000 if prog >= when else -1
                if age < 0:
                    continue
                pop = min(1.0, age / 0.25); pop = 1 + 0.35 * math.sin(math.pi * pop) if pop < 1 else 1   # overshoot pop
                r = lw * 1.8 * pop
                d.ellipse([px - r - 2, py - r - 2, px + r + 2, py + r + 2], fill=(255, 255, 255, 255))
                d.ellipse([px - r, py - r, px + r, py + r], fill=col + (255,))
        frames.append(np.asarray(img))
    tmp = out.with_name(f"{out.stem}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp.mov")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0  # type: ignore[attr-defined]
    r = subprocess.run([FFMPEG_BIN, "-y", "-hide_banner", "-nostdin", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba",
                        "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-vf", f"scale={w}:{h}:flags=bicubic",
                        "-c:v", "qtrle", "-pix_fmt", "argb", str(tmp)],
                       input=np.stack(frames).tobytes(), capture_output=True, timeout=600, creationflags=flags)
    if r.returncode != 0:
        tmp.unlink(missing_ok=True)
        raise RouteError("The map route could not be drawn.")
    os.replace(tmp, out)
    return str(out)


def route_graph(base: str, route: dict, clip: str, fps: int) -> tuple[list[str], str]:
    from app.render.ffmpeg_utils import escape_path_for_filter
    st = route["start_ms"] / 1000
    return ([f"movie='{escape_path_for_filter(clip)}',setpts=PTS-STARTPTS+{st:.3f}/TB,format=rgba[rtc]",
             f"[{base}][rtc]overlay=eof_action=repeat:format=auto[route]"], "route")
