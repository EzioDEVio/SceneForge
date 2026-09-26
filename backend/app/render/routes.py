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

ROUTE_DEFAULT = {"points": [[20, 70], [45, 45], [75, 35]], "color": "#E8413C", "width": 8, "style": "solid", "pins": True, "start_ms": 0, "draw_ms": 3000,
                 # extras: arrowhead, a moving icon, stop labels, smooth curved path
                 "arrow": True, "marker": "none", "labels": [], "curve": False}
MARKERS = ("none", "dot", "plane", "ship", "car", "pin")


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
    if not isinstance(d["arrow"], bool) or not isinstance(d["curve"], bool):
        raise RouteError("Route arrow and curve must be true or false.")
    if d["marker"] not in MARKERS:
        raise RouteError("Route icon must be one of: " + ", ".join(MARKERS) + ".")
    labels = d["labels"]
    if not isinstance(labels, list) or len(labels) > 20 or any(not isinstance(x, str) or len(x) > 40 for x in labels):
        raise RouteError("Stop labels must be up to 20 texts of at most 40 characters.")
    return {"points": clean_pts, "color": d["color"].upper(), "width": int(d["width"]), "style": d["style"],
            "pins": d["pins"], "start_ms": int(d["start_ms"]), "draw_ms": int(d["draw_ms"]),
            "arrow": d["arrow"], "marker": d["marker"], "labels": [x.strip() for x in labels], "curve": d["curve"]}


_ARABIC = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")


def _label_text(text: str) -> str:
    """Labels are drawn with Pillow's basic layout, which neither joins Arabic letters nor
    orders right-to-left text. Shape and reorder Arabic here (same result on every OS;
    Pillow's RAQM engine is often missing on Windows)."""
    if not _ARABIC.search(text or ""):
        return text
    import arabic_reshaper
    from bidi import get_display
    return get_display(arabic_reshaper.reshape(text))


def _label_font(original: str, size: int):
    from PIL import ImageFont
    from app.config import RESOURCE_DIR
    name = "NotoNaskhArabic-Bold.ttf" if _ARABIC.search(original or "") else "NotoSans-Bold.ttf"
    try:
        return ImageFont.truetype(str(Path(RESOURCE_DIR) / "assets/fonts" / name), size, layout_engine=ImageFont.Layout.BASIC)
    except Exception:
        return ImageFont.load_default()


def _smooth(pts: list[tuple[float, float]], samples: int = 24) -> tuple[list[tuple[float, float]], list[int]]:
    """Catmull-Rom curve through the stops. Returns (dense points, index of each stop in them)."""
    if len(pts) < 3:
        return pts, list(range(len(pts)))
    ext = [pts[0]] + pts + [pts[-1]]
    out, idx = [pts[0]], [0]
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for k in range(1, samples + 1):
            t = k / samples; t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * (2 * p1[j] + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in (0, 1)))
        idx.append(len(out) - 1)
    return out, idx


def _icon(kind: str, size: float) -> list[tuple[float, float]]:
    """Icon outline pointing along +x, centred on (0, 0)."""
    s = size
    if kind == "plane":
        return [(1.0*s, 0), (0.3*s, 0.12*s), (0.1*s, 0.75*s), (-0.1*s, 0.75*s), (-0.05*s, 0.12*s), (-0.6*s, 0.1*s), (-0.8*s, 0.4*s),
                (-0.95*s, 0.4*s), (-0.85*s, 0), (-0.95*s, -0.4*s), (-0.8*s, -0.4*s), (-0.6*s, -0.1*s), (-0.05*s, -0.12*s),
                (-0.1*s, -0.75*s), (0.1*s, -0.75*s), (0.3*s, -0.12*s)]
    if kind == "ship":
        return [(1.0*s, 0), (0.55*s, 0.42*s), (-0.85*s, 0.42*s), (-0.85*s, -0.42*s), (0.55*s, -0.42*s)]
    if kind == "car":
        return [(0.9*s, 0.3*s), (0.9*s, -0.3*s), (0.55*s, -0.45*s), (-0.75*s, -0.45*s), (-0.9*s, -0.3*s), (-0.9*s, 0.3*s), (-0.75*s, 0.45*s), (0.55*s, 0.45*s)]
    return []


def _rotate(poly, angle, cx, cy):
    ca, sa = math.cos(angle), math.sin(angle)
    return [(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in poly]


def route_clip(route: dict, w: int, h: int, fps: int, cache: Path) -> str:
    """Transparent clip of the route being drawn (draw_ms long, plus 0.4 s for the last pin)."""
    from PIL import Image, ImageDraw, ImageFilter
    key = hashlib.sha256(f"v6|{w}x{h}|{fps}|{sorted((k, str(v)) for k, v in route.items())}".encode()).hexdigest()[:20]
    cache.mkdir(parents=True, exist_ok=True)
    out = cache / f"route_{key}.mov"
    if out.exists():
        return str(out)
    scale = 0.5 if w > 1280 else 1.0                          # draw at half size for big frames
    W, H = int(w * scale), int(h * scale)
    stops = [(x / 100 * W, y / 100 * H) for x, y in route["points"]]
    pts, stop_idx = _smooth(stops) if route.get("curve") else (stops, list(range(len(stops))))
    seg = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    total = sum(seg) or 1
    cum = [0.0]
    for L in seg:
        cum.append(cum[-1] + L)
    stop_when = [cum[i] / total for i in stop_idx]
    lw = max(1, int(route["width"] * H / 1080))
    col = tuple(int(route["color"][i:i + 2], 16) for i in (1, 3, 5))
    n = int(round((route["draw_ms"] + 400) / 1000 * fps))
    draw_frames = max(1, int(round(route["draw_ms"] / 1000 * fps)))
    labels = [_label_text(t) for t in (route.get("labels") or [])]
    size = max(10, int(H * 0.034))
    ease = lambda f: 0.5 - 0.5 * math.cos(math.pi * min(1.0, f / draw_frames))
    # Frame at which each stop is reached; pins pop and labels fade in from then, by the clock
    # (progress stops increasing once drawing ends, so it cannot time the last stop).
    reach = [next((f for f in range(n) if ease(f) >= w - 1e-9), n - 1) for w in stop_when]
    end_up = math.sin(math.atan2(pts[-1][1] - pts[-2][1], pts[-1][0] - pts[-2][0])) < -0.3 if len(pts) > 1 else False
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
            px_, py_ = path[-2]
            ang = math.atan2(hy - py_, hx - px_)
            marker = route.get("marker", "none")
            if marker in ("none", "dot"):
                glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                ImageDraw.Draw(glow).ellipse([hx - lw * 2.2, hy - lw * 2.2, hx + lw * 2.2, hy + lw * 2.2], fill=col + (200,))
                img = Image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(lw * 1.2)), img)
                d = ImageDraw.Draw(img)
            if marker in ("plane", "ship", "car"):
                poly = _rotate(_icon(marker, max(lw * 4.5, H * 0.05)), ang, hx, hy)
                d.polygon(poly, fill=(255, 255, 255, 255), outline=(20, 20, 20, 255), width=max(1, lw // 4))
            elif marker == "pin":
                r = max(lw * 2.2, H * 0.018)
                d.ellipse([hx - r, hy - 2.6 * r, hx + r, hy - 0.6 * r], fill=(255, 255, 255, 255), outline=col + (255,), width=max(2, lw // 2))
                d.polygon([(hx - r * 0.55, hy - 1.2 * r), (hx + r * 0.55, hy - 1.2 * r), (hx, hy)], fill=(255, 255, 255, 255))
            elif not route.get("arrow", True):
                d.ellipse([hx - lw, hy - lw, hx + lw, hy + lw], fill=(255, 255, 255, 255))
        if route["pins"]:
            for (px, py), when, rf in zip(stops, stop_when, reach):
                age = (f - rf) / fps if f >= rf else -1
                if age < 0:
                    continue
                pop = min(1.0, age / 0.25); pop = 1 + 0.35 * math.sin(math.pi * pop) if pop < 1 else 1   # overshoot pop
                r = lw * 1.8 * pop
                d.ellipse([px - r - 2, py - r - 2, px + r + 2, py + r + 2], fill=(255, 255, 255, 255))
                d.ellipse([px - r, py - r, px + r, py + r], fill=col + (255,))
        # arrowhead drawn after the pins so the destination pin never covers it
        if len(path) > 1 and route.get("arrow", True) and marker in ("none", "dot", "pin"):   # an icon already shows the direction
            a = lw * 3.2    # arrowhead just ahead of the line's end, clear of the final pin
            off = (lw * 1.8 + 3) if route["pins"] else 0
            bx_, by_ = hx + math.cos(ang) * off, hy + math.sin(ang) * off
            tip = (bx_ + math.cos(ang) * a * 0.9, by_ + math.sin(ang) * a * 0.9)
            d.polygon([tip, (bx_ + math.cos(ang + 2.5) * a * 0.75, by_ + math.sin(ang + 2.5) * a * 0.75),
                       (bx_ + math.cos(ang - 2.5) * a * 0.75, by_ + math.sin(ang - 2.5) * a * 0.75)], fill=col + (255,))
        for k, (text, (px, py), when) in enumerate(zip(labels, stops, stop_when)):
            if not text or f < reach[k]:
                continue
            age = (f - reach[k]) / fps
            alpha = int(255 * min(1.0, age / 0.3))
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ld = ImageDraw.Draw(layer)
            font = _label_font(route["labels"][k], size)
            tw, th = ld.textbbox((0, 0), text, font=font)[2:]
            bx, by = px - tw / 2 - 8, py - lw * 2.6 - th - 16
            last_below = k == len(stops) - 1 and route.get("arrow", True) and end_up   # keep the final arrowhead clear
            by = py + lw * 2.6 + 6 if (by <= 4 or last_below) else by   # below the stop near the top edge, or under the arrow
            bx = min(max(4, bx), W - tw - 20)
            ld.rounded_rectangle([bx, by, bx + tw + 16, by + th + 10], radius=8, fill=(15, 15, 20, int(alpha * 0.8)))
            ld.text((bx + 8, by + 3), text, font=font, fill=(255, 255, 255, alpha))
            img = Image.alpha_composite(img, layer)
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
