"""Build the bundled sticker & emoji library (assets/stickers/).

  python scripts/build_sticker_library.py            # fetch Twemoji SVGs (cached) + draw graphics
  python scripts/build_sticker_library.py --graphics # redraw only the Pillow graphics + manifest

Emoji artwork: Twemoji by Twitter, Inc. and other contributors, maintained at
https://github.com/jdecked/twemoji (graphics CC-BY 4.0, code MIT). The SVGs for the chosen subset
are downloaded once at a pinned tag and rasterised to 320 px PNGs. Rasterising needs `cairosvg`
(pip install cairosvg; needs the system cairo library) or the `rsvg-convert` command; neither is
needed at runtime, because the PNGs are committed in assets/stickers/emoji/.

Graphic stickers (badges, arrows, speech bubbles, shapes, social buttons) are drawn here with
Pillow and the bundled OFL fonts, supersampled 2x for clean edges, with a soft drop shadow.

Outputs: assets/stickers/{emoji,graphics}/<id>.png, assets/stickers/library.json and a copy of the
manifest for the editor at frontend/src/stickerLibrary.json (kept identical; a test checks it).
"""
from __future__ import annotations

import argparse
import json
import math
import random
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sticker_catalog import CATEGORY_ORDER, EMOJI, GRAPHICS  # noqa: E402

TWEMOJI_TAG = "v17.0.3"
TWEMOJI_RAW = f"https://raw.githubusercontent.com/jdecked/twemoji/{TWEMOJI_TAG}"
OUT = ROOT / "assets" / "stickers"
FONTS = ROOT / "assets" / "fonts"
CACHE = Path.home() / ".cache" / "sceneforge" / f"twemoji-{TWEMOJI_TAG}"
EMOJI_PX = 320
S = 2  # supersampling factor for the Pillow graphics


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def twemoji_code(emoji: str) -> str:
    cps = [f"{ord(ch):x}" for ch in emoji]
    if "200d" not in cps:  # Twemoji drops VS-16 except inside ZWJ sequences
        cps = [c for c in cps if c != "fe0f"]
    return "-".join(cps)


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read()


def twemoji_svg(emoji: str) -> bytes:
    CACHE.mkdir(parents=True, exist_ok=True)
    code = twemoji_code(emoji)
    candidates = [code, "-".join(f"{ord(ch):x}" for ch in emoji)]
    for c in dict.fromkeys(candidates):
        p = CACHE / f"{c}.svg"
        if p.exists():
            return p.read_bytes()
        try:
            data = fetch(f"{TWEMOJI_RAW}/assets/svg/{c}.svg")
        except Exception:
            continue
        p.write_bytes(data)
        return data
    raise SystemExit(f"Twemoji has no SVG for {emoji!r} ({code})")


def rasterise(svg: bytes, px: int) -> Image.Image:
    try:
        import cairosvg  # type: ignore
        import io
        return Image.open(io.BytesIO(cairosvg.svg2png(bytestring=svg, output_width=px, output_height=px))).convert("RGBA")
    except ImportError:
        if not shutil.which("rsvg-convert"):
            raise SystemExit("Install cairosvg (pip install cairosvg) or rsvg-convert to rasterise Twemoji.")
        import io
        out = subprocess.run(["rsvg-convert", "-w", str(px), "-h", str(px)], input=svg, capture_output=True, check=True).stdout
        return Image.open(io.BytesIO(out)).convert("RGBA")


def save_png(img: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, optimize=True)


# ----------------------------------------------------------------------------- drawing helpers
def rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def mix(c: tuple[int, int, int], t: tuple[int, int, int], a: float) -> tuple[int, int, int]:
    return tuple(int(round(c[i] * (1 - a) + t[i] * a)) for i in range(3))  # type: ignore[return-value]


def lum(c: tuple[int, int, int]) -> float:
    return (0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]) / 255


def font(name: str, size: float) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), max(8, int(size)))


def fit(text: str, face: str, max_w: float, max_h: float, start: float) -> ImageFont.FreeTypeFont:
    size = start
    probe = ImageDraw.Draw(Image.new("L", (8, 8)))
    while size > 10:
        f = font(face, size)
        l, t, r, b = probe.multiline_textbbox((0, 0), text, font=f, align="center", spacing=size * 0.05)
        if r - l <= max_w and b - t <= max_h:
            return f
        size *= 0.94
    return font(face, size)


def text_size(text: str, f: ImageFont.FreeTypeFont) -> tuple[int, int]:
    l, t, r, b = ImageDraw.Draw(Image.new("L", (8, 8))).multiline_textbbox((0, 0), text, font=f, align="center")
    return r - l, b - t


def new_mask(w: int, h: int) -> Image.Image:
    return Image.new("L", (w, h), 0)


def dilate(mask: Image.Image, r: float) -> Image.Image:
    if r <= 0:
        return mask
    return mask.filter(ImageFilter.GaussianBlur(r * 0.55)).point(lambda v: 255 if v > 6 else v * 40)


def gradient(w: int, h: int, top: tuple[int, int, int], bottom: tuple[int, int, int], horizontal: bool = False) -> Image.Image:
    n = w if horizontal else h
    strip = Image.new("RGB", (n, 1) if horizontal else (1, n))
    for i in range(n):
        a = i / max(1, n - 1)
        strip.putpixel((i, 0) if horizontal else (0, i), mix(top, bottom, a))
    return strip.resize((w, h))


def sheen(w: int, h: int, color: str) -> Image.Image:
    c = rgb(color)
    return gradient(w, h, mix(c, (255, 255, 255), 0.16), mix(c, (0, 0, 0), 0.10))


class Canvas:
    """A supersampled RGBA canvas built from masks: fill(mask, colour) layers, then finish()."""

    def __init__(self, w: int, h: int):
        self.w, self.h = w * S, h * S
        self.img = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        self.coverage = new_mask(self.w, self.h)

    def fill(self, mask: Image.Image, paint: str | Image.Image, outline: str | None = None, outline_w: float = 0) -> None:
        if outline and outline_w:
            o = dilate(mask, outline_w * S)
            self._paint(o, outline)
        self._paint(mask, paint)

    def _paint(self, mask: Image.Image, paint: str | Image.Image) -> None:
        layer = Image.new("RGBA", (self.w, self.h), rgb(paint) + (255,) if isinstance(paint, str) else (0, 0, 0, 0))
        if not isinstance(paint, str):
            layer.paste(paint.convert("RGB"), (0, 0))
        layer.putalpha(mask)
        self.img.alpha_composite(layer)
        self.coverage = ImageChops.lighter(self.coverage, mask)

    def text(self, xy: tuple[float, float], text: str, f: ImageFont.FreeTypeFont, color: str,
             stroke: str | None = None, stroke_w: float = 0, angle: float = 0) -> None:
        layer = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.multiline_text((xy[0] * S, xy[1] * S), text, font=f, fill=rgb(color) + (255,), anchor="mm", align="center",
                         spacing=f.size * 0.05, stroke_width=int(stroke_w * S), stroke_fill=(rgb(stroke) + (255,)) if stroke else None)
        if angle:
            layer = layer.rotate(angle, resample=Image.BICUBIC, center=(xy[0] * S, xy[1] * S))
        self.img.alpha_composite(layer)

    def paste(self, im: Image.Image, center: tuple[float, float]) -> None:
        layer = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        layer.paste(im, (int(center[0] * S - im.width / 2), int(center[1] * S - im.height / 2)), im)
        self.img.alpha_composite(layer)

    def finish(self, shadow: float = 0.34, rotate: float = 0) -> Image.Image:
        img = self.img
        if rotate:
            img = img.rotate(rotate, resample=Image.BICUBIC, expand=True)
        if shadow:
            a = img.getchannel("A").filter(ImageFilter.GaussianBlur(9 * S))
            sh = Image.new("RGBA", img.size, (12, 14, 24, 0))
            sh.putalpha(a.point(lambda v: int(v * shadow)))
            pad = 24 * S
            base = Image.new("RGBA", (img.width + 2 * pad, img.height + 2 * pad), (0, 0, 0, 0))
            base.alpha_composite(sh, (pad, pad + 7 * S))
            base.alpha_composite(img, (pad, pad))
            img = base
        img = img.resize((img.width // S, img.height // S), Image.LANCZOS)
        box = img.getchannel("A").point(lambda v: 255 if v > 3 else 0).getbbox()
        if box:
            m = 4
            img = img.crop((max(0, box[0] - m), max(0, box[1] - m), min(img.width, box[2] + m), min(img.height, box[3] + m)))
        return img


def d_of(mask: Image.Image) -> ImageDraw.ImageDraw:
    return ImageDraw.Draw(mask)


def rrect(w: int, h: int, box: tuple[float, float, float, float], r: float) -> Image.Image:
    m = new_mask(w, h)
    d_of(m).rounded_rectangle([v * S for v in box], radius=r * S, fill=255)
    return m


def poly(w: int, h: int, pts: list[tuple[float, float]]) -> Image.Image:
    m = new_mask(w, h)
    d_of(m).polygon([(x * S, y * S) for x, y in pts], fill=255)
    return m


def ellipse(w: int, h: int, box: tuple[float, float, float, float]) -> Image.Image:
    m = new_mask(w, h)
    d_of(m).ellipse([v * S for v in box], fill=255)
    return m


def union(*masks: Image.Image) -> Image.Image:
    out = masks[0]
    for m in masks[1:]:
        out = ImageChops.lighter(out, m)
    return out


def minus(a: Image.Image, b: Image.Image) -> Image.Image:
    return ImageChops.subtract(a, b)


def star_pts(cx, cy, r_out, r_in, n, rot=-math.pi / 2):
    return [(cx + math.cos(rot + i * math.pi / n) * (r_out if i % 2 == 0 else r_in),
             cy + math.sin(rot + i * math.pi / n) * (r_out if i % 2 == 0 else r_in)) for i in range(2 * n)]


def heart_pts(cx, cy, size):
    pts = []
    for i in range(160):
        t = i / 160 * 2 * math.pi
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((cx + x * size / 34, cy - y * size / 34 - size * 0.04))
    return pts


# ----------------------------------------------------------------------------- icons (white glyphs)
def icon(name: str, size: int, color: str) -> Image.Image:
    """A crisp glyph image (already supersampled; pasted with Canvas.paste)."""
    z = size * S
    m = Image.new("L", (z, z), 0)
    d = ImageDraw.Draw(m)
    u = z / 100
    if name == "play":
        d.rounded_rectangle([6 * u, 18 * u, 94 * u, 82 * u], radius=20 * u, fill=255)
        d.polygon([(40 * u, 34 * u), (40 * u, 66 * u), (68 * u, 50 * u)], fill=0)
    elif name == "check":
        d.line([(16 * u, 52 * u), (40 * u, 76 * u), (86 * u, 26 * u)], fill=255, width=int(16 * u), joint="curve")
        for x, y in ((16, 52), (86, 26)):
            d.ellipse([(x - 8) * u, (y - 8) * u, (x + 8) * u, (y + 8) * u], fill=255)
    elif name == "heart":
        d.polygon(heart_pts(50 * u, 54 * u, 92 * u), fill=255)
    elif name == "plus":
        d.rounded_rectangle([40 * u, 12 * u, 60 * u, 88 * u], radius=10 * u, fill=255)
        d.rounded_rectangle([12 * u, 40 * u, 88 * u, 60 * u], radius=10 * u, fill=255)
    elif name == "bell":
        d.ellipse([22 * u, 10 * u, 78 * u, 66 * u], fill=255)
        d.polygon([(22 * u, 40 * u), (78 * u, 40 * u), (88 * u, 74 * u), (12 * u, 74 * u)], fill=255)
        d.rounded_rectangle([8 * u, 68 * u, 92 * u, 80 * u], radius=6 * u, fill=255)
        d.ellipse([40 * u, 78 * u, 60 * u, 96 * u], fill=255)
        d.ellipse([44 * u, 2 * u, 56 * u, 14 * u], fill=255)
    elif name == "share":
        pts = [(74, 20), (26, 50), (74, 80)]
        d.line([(x * u, y * u) for x, y in pts], fill=255, width=int(9 * u))
        for x, y in pts:
            d.ellipse([(x - 15) * u, (y - 15) * u, (x + 15) * u, (y + 15) * u], fill=255)
    elif name == "chat":
        d.rounded_rectangle([8 * u, 12 * u, 92 * u, 74 * u], radius=18 * u, fill=255)
        d.polygon([(24 * u, 68 * u), (22 * u, 94 * u), (48 * u, 72 * u)], fill=255)
        for x in (30, 50, 70):
            d.ellipse([(x - 6) * u, 37 * u, (x + 6) * u, 49 * u], fill=0)
    elif name == "link":
        for (x0, y0) in ((6, 30), (46, 30)):
            d.rounded_rectangle([x0 * u, y0 * u, (x0 + 48) * u, (y0 + 40) * u], radius=20 * u, outline=255, width=int(11 * u))
        m = m.rotate(-35, resample=Image.BICUBIC)
    elif name == "bookmark":
        d.polygon([(22 * u, 6 * u), (78 * u, 6 * u), (78 * u, 94 * u), (50 * u, 70 * u), (22 * u, 94 * u)], fill=255)
    elif name == "exclaim":
        d.rounded_rectangle([40 * u, 10 * u, 60 * u, 66 * u], radius=10 * u, fill=255)
        d.ellipse([39 * u, 74 * u, 61 * u, 96 * u], fill=255)
    elif name == "info":
        d.ellipse([39 * u, 6 * u, 61 * u, 28 * u], fill=255)
        d.rounded_rectangle([40 * u, 38 * u, 60 * u, 94 * u], radius=10 * u, fill=255)
    img = Image.new("RGBA", (z, z), rgb(color) + (0,))
    img.putalpha(m)
    return img


# ----------------------------------------------------------------------------- sticker kinds
BOLD = "Poppins-Bold.ttf"
IMPACT = "Anton-Regular.ttf"
BEBAS = "BebasNeue-Regular.ttf"


def k_pill(p, radius=None, h=200):
    text, ic = p["text"], p.get("icon")
    f = fit(text, BOLD, 2000, h * 0.42 * S, h * 0.42 * S)
    tw, _ = text_size(text, f)
    icon_w = h * 0.42 if ic else 0
    w = int(tw / S + icon_w + (h * 0.18 if ic else 0) + h * 0.75)
    c = Canvas(w + 20, h + 20)
    box = (10, 10, 10 + w, 10 + h)
    c.fill(rrect(c.w, c.h, box, h / 2 if radius is None else radius), sheen(c.w, c.h, p["bg"]),
           outline="#FFFFFF" if lum(rgb(p["bg"])) < 0.8 else "#1A1A1A", outline_w=6)
    x0 = 10 + (w - (tw / S + icon_w + (h * 0.18 if ic else 0))) / 2
    if ic:
        c.paste(icon(ic, int(icon_w), p["fg"]), (x0 + icon_w / 2, 10 + h / 2))
        x0 += icon_w + h * 0.18
    c.text((x0 + tw / S / 2, 10 + h / 2 + 2), text, f, p["fg"])
    return c.finish()


def k_button(p):
    return k_pill(p, radius=34, h=170)


def k_banner(p):
    text = p["text"]
    h = 190
    f = fit(text, IMPACT, 2000, h * 0.52 * S, h * 0.52 * S)
    tw, _ = text_size(text, f)
    w = int(tw / S + 170)
    c = Canvas(w + 20, h + 20)
    pts = [(10, 10), (w - 40, 10), (w + 10, 10 + h / 2), (w - 40, 10 + h), (10, 10 + h), (52, 10 + h / 2)]
    c.fill(poly(c.w, c.h, pts), sheen(c.w, c.h, p["bg"]), outline="#FFFFFF", outline_w=6)
    c.text((10 + w / 2 + 6, 10 + h / 2), text, f, p["fg"])
    return c.finish()


def k_burst(p):
    text = p.get("text", "")
    c = Canvas(520, 520)
    m = poly(c.w, c.h, star_pts(260, 260, 240, 188 if text else 200, 16))
    if not text:  # comic shout bubble: jagged and irregular
        rnd = random.Random(7)
        pts = [(260 + math.cos(-math.pi / 2 + i * math.pi / 13) * (238 if i % 2 == 0 else 178 + rnd.randint(-14, 14)),
                260 + math.sin(-math.pi / 2 + i * math.pi / 13) * (210 if i % 2 == 0 else 160 + rnd.randint(-14, 14))) for i in range(26)]
        m = poly(c.w, c.h, pts)
    c.fill(m, sheen(c.w, c.h, p["bg"]), outline=p.get("edge", "#FFFFFF"), outline_w=10)
    if text:
        f = fit(text, IMPACT, 290 * S, 230 * S, 150 * S)
        dark = lum(rgb(p["fg"])) < 0.5
        c.text((260, 262), text, f, p["fg"], stroke=None if dark else "#1A1A1A", stroke_w=0 if dark else 5, angle=8)
    return c.finish()


def k_icon_circle(p):
    c = Canvas(300, 300)
    c.fill(ellipse(c.w, c.h, (20, 20, 280, 280)), sheen(c.w, c.h, p["bg"]), outline="#FFFFFF", outline_w=10)
    c.paste(icon(p["icon"], 150, p["fg"]), (150, 152))
    return c.finish()


def k_stack(p):
    text = p["text"]
    c = Canvas(460, 330)
    for i, y in enumerate((40, 92)):
        m = new_mask(c.w, c.h)
        ImageDraw.Draw(m).line([(150 * S, (y + 44) * S), (230 * S, y * S), (310 * S, (y + 44) * S)], fill=255, width=22 * S, joint="curve")
        c.fill(m, "#FFFFFF", outline="#151515", outline_w=5)
    f = fit(text, BOLD, 380 * S, 70 * S, 80 * S)
    box = (40, 180, 420, 300)
    c.fill(rrect(c.w, c.h, box, 60), sheen(c.w, c.h, p["bg"]), outline="#151515", outline_w=5)
    c.text((230, 242), text, f, p["fg"])
    return c.finish()


def k_live(p):
    h = 170
    f = fit(p["text"], BOLD, 2000, h * 0.5 * S, h * 0.5 * S)
    tw, _ = text_size(p["text"], f)
    w = int(tw / S + h * 1.05)
    c = Canvas(w + 20, h + 20)
    c.fill(rrect(c.w, c.h, (10, 10, 10 + w, 10 + h), 30), sheen(c.w, c.h, p["bg"]), outline="#FFFFFF", outline_w=6)
    r = h * 0.14
    cx = 10 + h * 0.42
    c.fill(ellipse(c.w, c.h, (cx - r * 1.8, 10 + h / 2 - r * 1.8, cx + r * 1.8, 10 + h / 2 + r * 1.8)), mix_hex(p["fg"], p["bg"], 0.55))
    c.fill(ellipse(c.w, c.h, (cx - r, 10 + h / 2 - r, cx + r, 10 + h / 2 + r)), p["fg"])
    c.text((10 + h * 0.62 + tw / S / 2 + h * 0.15, 10 + h / 2 + 2), p["text"], f, p["fg"])
    return c.finish()


def mix_hex(a: str, b: str, t: float) -> str:
    return "#%02X%02X%02X" % mix(rgb(a), rgb(b), t)


def k_tag(p):
    left, right = p["text"].split(" ", 1)
    h = 170
    fl = fit(left, IMPACT, 2000, h * 0.55 * S, h * 0.55 * S)
    fr = fit(right, IMPACT, 2000, h * 0.55 * S, h * 0.55 * S)
    wl = text_size(left, fl)[0] / S + 70
    wr = text_size(right, fr)[0] / S + 70
    c = Canvas(int(wl + wr + 40), h + 20)
    c.fill(rrect(c.w, c.h, (10, 10, 10 + wl + wr, 10 + h), 16), "#FFFFFF", outline="#FFFFFF", outline_w=6)
    c.fill(rrect(c.w, c.h, (10, 10, 10 + wl + 20, 10 + h), 16), sheen(c.w, c.h, p["bg"]))
    c.fill(poly(c.w, c.h, [(10 + wl, 10), (10 + wl + wr, 10), (10 + wl + wr, 10 + h), (10 + wl - 18, 10 + h)]), sheen(c.w, c.h, p["bg2"]))
    c.text((10 + wl / 2, 10 + h / 2 + 2), left, fl, p["fg"])
    c.text((10 + wl + wr / 2 - 6, 10 + h / 2 + 2), right, fr, p["fg2"])
    return c.finish()


def k_ribbon(p):
    text = p["text"]
    h = 150
    f = fit(text, IMPACT, 2000, h * 0.55 * S, h * 0.55 * S)
    tw = text_size(text, f)[0] / S
    w = int(tw + 120)
    W = w + 160
    c = Canvas(W + 20, h + 80)
    dark = mix_hex(p["bg"], "#000000", 0.35)
    for side in (0, 1):
        x0 = 10 if side == 0 else W + 10 - 120
        pts = [(x0, 40), (x0 + 120, 40), (x0 + 120, 40 + h), (x0, 40 + h), (x0 + 36, 40 + h / 2)] if side == 0 else \
              [(x0, 40), (x0 + 120, 40), (x0 + 84, 40 + h / 2), (x0 + 120, 40 + h), (x0, 40 + h)]
        c.fill(poly(c.w, c.h, pts), dark, outline="#FFFFFF", outline_w=5)
    fold = [(90, 10 + h + 10), (90, 40 + h), (130, 10 + h + 10)]
    c.fill(poly(c.w, c.h, fold), mix_hex(p["bg"], "#000000", 0.55))
    fold2 = [(W - 70, 10 + h + 10), (W - 70, 40 + h), (W - 110, 10 + h + 10)]
    c.fill(poly(c.w, c.h, fold2), mix_hex(p["bg"], "#000000", 0.55))
    c.fill(rrect(c.w, c.h, (90, 10, W - 70, 10 + h + 10), 8), sheen(c.w, c.h, p["bg"]), outline="#FFFFFF", outline_w=5)
    c.text(((90 + W - 70) / 2, 10 + (h + 10) / 2 + 2), text, f, p["fg"])
    return c.finish()


def k_seal(p):
    c = Canvas(420, 420)
    c.fill(poly(c.w, c.h, star_pts(210, 210, 200, 182, 24)), sheen(c.w, c.h, p["bg"]), outline="#FFFFFF", outline_w=6)
    ring = minus(ellipse(c.w, c.h, (52, 52, 368, 368)), ellipse(c.w, c.h, (62, 62, 358, 358)))
    c.fill(ring, p["fg"])
    f = fit(p["text"], IMPACT, 250 * S, 220 * S, 130 * S)
    c.text((210, 212), p["text"], f, p["fg"])
    return c.finish()


def k_verified(p):
    c = Canvas(320, 320)
    c.fill(poly(c.w, c.h, star_pts(160, 160, 150, 128, 12)), sheen(c.w, c.h, p["bg"]), outline="#FFFFFF", outline_w=8)
    c.paste(icon("check", 170, p["fg"]), (160, 164))
    return c.finish()


def k_stamp(p):
    text = p["text"]
    f = fit(text, IMPACT, 2000, 120 * S, 120 * S)
    tw = text_size(text, f)[0] / S
    w, h = int(tw + 110), 210
    c = Canvas(w + 20, h + 20)
    outer = minus(rrect(c.w, c.h, (10, 10, 10 + w, 10 + h), 26), rrect(c.w, c.h, (24, 24, w - 4, h - 4), 18))
    inner = minus(rrect(c.w, c.h, (34, 34, w - 14, h - 14), 12), rrect(c.w, c.h, (40, 40, w - 20, h - 20), 8))
    tl = new_mask(c.w, c.h)
    ImageDraw.Draw(tl).multiline_text((c.w / 2, c.h / 2 + 4 * S), text, font=f, fill=255, anchor="mm")
    ink = union(outer, inner, tl)
    rnd = random.Random(11)  # worn-ink speckle
    speck = new_mask(c.w, c.h)
    sd = ImageDraw.Draw(speck)
    for _ in range(700):
        x, y, r = rnd.uniform(0, c.w), rnd.uniform(0, c.h), rnd.uniform(1.5, 5) * S
        sd.ellipse([x - r, y - r, x + r, y + r], fill=255)
    c.fill(minus(ink, speck), p["fg"])
    return c.finish(shadow=0.12, rotate=12)


def k_number(p):
    c = Canvas(260, 260)
    c.fill(ellipse(c.w, c.h, (20, 20, 240, 240)), sheen(c.w, c.h, p["bg"]), outline="#FFFFFF", outline_w=12)
    f = fit(p["text"], IMPACT, 150 * S, 150 * S, 150 * S)
    c.text((130, 134), p["text"], f, "#FFFFFF")
    return c.finish()


def arrow_mask(c: Canvas, angle: float, cx=260, cy=260, length=420, shaft=96, head=210, head_len=180) -> Image.Image:
    x0, x1 = cx - length / 2, cx + length / 2
    pts = [(x0, cy - shaft / 2), (x1 - head_len, cy - shaft / 2), (x1 - head_len, cy - head / 2), (x1, cy),
           (x1 - head_len, cy + head / 2), (x1 - head_len, cy + shaft / 2), (x0, cy + shaft / 2)]
    a = math.radians(-angle)
    rot = [(cx + (x - cx) * math.cos(a) - (y - cy) * math.sin(a), cy + (x - cx) * math.sin(a) + (y - cy) * math.cos(a)) for x, y in pts]
    m = new_mask(c.w, c.h)
    ImageDraw.Draw(m).polygon([(x * S, y * S) for x, y in rot], fill=255)
    return m.filter(ImageFilter.GaussianBlur(4 * S)).point(lambda v: 255 if v > 128 else 0)  # soften corners


def k_arrow(p):
    c = Canvas(520, 520)
    c.fill(arrow_mask(c, p["angle"]), sheen(c.w, c.h, p["bg"]), outline="#FFFFFF" if lum(rgb(p["bg"])) < 0.8 else "#151515", outline_w=10)
    return c.finish()


def k_curve_arrow(p):
    c = Canvas(520, 520)
    m = new_mask(c.w, c.h)
    d = ImageDraw.Draw(m)
    pts = []
    for i in range(60):  # a quarter-and-a-bit arc sweeping down to the right
        t = math.radians(200 + i * 1.9)
        pts.append(((300 + math.cos(t) * 220) * S, (420 + math.sin(t) * 300) * S))
    d.line(pts, fill=255, width=46 * S, joint="curve")
    x, y = pts[-1][0] / S, pts[-1][1] / S
    t = math.radians(200 + 59 * 1.9)
    tx, ty = -math.sin(t) * 220, math.cos(t) * 300  # tangent
    n = math.hypot(tx, ty)
    tx, ty = tx / n, ty / n
    px, py = -ty, tx
    head = [(x + tx * 90, y + ty * 90), (x + px * 70, y + py * 70), (x - px * 70, y - py * 70)]
    d.polygon([(a * S, b * S) for a, b in head], fill=255)
    d.ellipse([(pts[0][0] - 23 * S), (pts[0][1] - 23 * S), (pts[0][0] + 23 * S), (pts[0][1] + 23 * S)], fill=255)
    c.fill(m, p["bg"], outline="#151515" if lum(rgb(p["bg"])) > 0.8 else "#FFFFFF", outline_w=9)
    return c.finish()


def k_ring(p):
    c = Canvas(560, 420)
    m = new_mask(c.w, c.h)
    pts = []
    for i in range(240):  # hand-drawn: a bit more than a full loop, slightly wobbly
        t = math.radians(-60 + i * 1.62)
        wob = 1 + 0.035 * math.sin(i / 9) + 0.04 * (i / 240)
        pts.append(((280 + math.cos(t) * 236 * wob) * S, (210 + math.sin(t) * 168 * wob) * S))
    ImageDraw.Draw(m).line(pts, fill=255, width=26 * S, joint="curve")
    for pt in (pts[0], pts[-1]):
        ImageDraw.Draw(m).ellipse([pt[0] - 13 * S, pt[1] - 13 * S, pt[0] + 13 * S, pt[1] + 13 * S], fill=255)
    c.fill(m, p["bg"])
    return c.finish(shadow=0.4)


def k_label_arrow(p):
    text = p["text"]
    f = fit(text, BOLD, 2000, 72 * S, 72 * S)
    tw = text_size(text, f)[0] / S
    w = int(max(tw + 120, 300))
    c = Canvas(w + 20, 440)
    outline = "#FFFFFF" if lum(rgb(p["bg"])) < 0.8 else "#151515"
    c.fill(rrect(c.w, c.h, (10, 10, 10 + w, 160), 75), sheen(c.w, c.h, p["bg"]), outline=outline, outline_w=6)
    c.text((10 + w / 2, 87), text, f, p["fg"])
    c.fill(arrow_mask(c, 270, cx=10 + w / 2, cy=300, length=250, shaft=70, head=170, head_len=120), sheen(c.w, c.h, p["bg"]), outline=outline, outline_w=8)
    return c.finish()


def k_swoosh(p):
    c = Canvas(620, 200)
    m = new_mask(c.w, c.h)
    pts = [((30 + i * 5.6) * S, (120 - math.sin(i / 100 * math.pi) * 34 + i * 0.25) * S) for i in range(101)]
    ImageDraw.Draw(m).line(pts, fill=255, width=40 * S, joint="curve")
    for pt, r in ((pts[0], 20), (pts[-1], 20)):
        ImageDraw.Draw(m).ellipse([pt[0] - r * S, pt[1] - r * S, pt[0] + r * S, pt[1] + r * S], fill=255)
    c.fill(m, p["bg"])
    return c.finish(shadow=0.25)


def cloud_mask(c: Canvas, cx, cy, sx, sy):
    blobs = [(-0.55, 0.15, 0.42), (-0.2, -0.25, 0.5), (0.25, -0.3, 0.46), (0.6, 0.05, 0.4), (0.25, 0.3, 0.42), (-0.2, 0.32, 0.42)]
    return union(*[ellipse(c.w, c.h, (cx + (x - r) * sx, cy + (y - r * 0.8) * sy, cx + (x + r) * sx, cy + (y + r * 0.8) * sy)) for x, y, r in blobs])


def k_shape(p):
    s = p["shape"]
    if s == "bar":
        c = Canvas(640, 170)
        c.fill(rrect(c.w, c.h, (10, 10, 630, 160), 22), sheen(c.w, c.h, p["bg"]), outline="#FFFFFF", outline_w=4)
        c.fill(rrect(c.w, c.h, (10, 10, 40, 160), 14), "#FFD60A")
        return c.finish()
    c = Canvas(420, 420)
    paint = sheen(c.w, c.h, p["bg"])
    outline, ow = "#FFFFFF", 8
    if s == "circle":
        m = ellipse(c.w, c.h, (30, 30, 390, 390))
    elif s == "square":
        m = rrect(c.w, c.h, (40, 40, 380, 380), 70)
    elif s == "star":
        m = poly(c.w, c.h, star_pts(210, 222, 200, 86, 5)).filter(ImageFilter.GaussianBlur(5 * S)).point(lambda v: 255 if v > 110 else 0)
    elif s == "heart":
        m = poly(c.w, c.h, heart_pts(210, 222, 380))
    elif s == "triangle":
        m = poly(c.w, c.h, [(210, 40), (385, 360), (35, 360)]).filter(ImageFilter.GaussianBlur(12 * S)).point(lambda v: 255 if v > 128 else 0)
    elif s == "hexagon":
        m = poly(c.w, c.h, [(210 + math.cos(math.radians(30 + 60 * i)) * 185, 210 + math.sin(math.radians(30 + 60 * i)) * 185) for i in range(6)])
        m = m.filter(ImageFilter.GaussianBlur(8 * S)).point(lambda v: 255 if v > 128 else 0)
    elif s == "diamond":
        m = poly(c.w, c.h, [(210, 25), (365, 210), (210, 395), (55, 210)]).filter(ImageFilter.GaussianBlur(8 * S)).point(lambda v: 255 if v > 128 else 0)
    elif s == "ring":
        m = minus(ellipse(c.w, c.h, (30, 30, 390, 390)), ellipse(c.w, c.h, (78, 78, 342, 342)))
        outline = "#151515"
        ow = 4
    elif s == "blob":
        pts = []
        for i in range(120):
            t = i / 120 * 2 * math.pi
            r = 165 + 22 * math.sin(3 * t + 0.6) + 14 * math.cos(5 * t)
            pts.append((210 + math.cos(t) * r, 210 + math.sin(t) * r))
        m = poly(c.w, c.h, pts)
        paint = gradient(c.w, c.h, rgb(p["bg"]), rgb(p["bg2"]), horizontal=True)
    elif s == "sparkle":
        pts = []
        for i in range(4):  # four-point twinkle with concave (quadratic) sides
            a0, a1 = -math.pi / 2 + i * math.pi / 2, -math.pi / 2 + (i + 1) * math.pi / 2
            p0 = (210 + math.cos(a0) * 195, 210 + math.sin(a0) * 195)
            p1 = (210 + math.cos(a1) * 195, 210 + math.sin(a1) * 195)
            ctrl = (210 + math.cos((a0 + a1) / 2) * 30, 210 + math.sin((a0 + a1) / 2) * 30)
            for k in range(24):
                t = k / 24
                pts.append(((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * ctrl[0] + t * t * p1[0],
                            (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * ctrl[1] + t * t * p1[1]))
        m = poly(c.w, c.h, pts)
        outline, ow = "#FFD60A", 6
    elif s == "cloud":
        m = cloud_mask(c, 210, 215, 180, 210)
        outline, ow = "#CBD5E1", 4
    else:
        raise ValueError(s)
    c.fill(m, paint, outline=outline, outline_w=ow)
    return c.finish()


def bubble_text(c: Canvas, p, cx, cy, max_w, max_h):
    if p.get("text"):
        f = fit(p["text"], BOLD if len(p["text"]) > 4 else IMPACT, max_w * S, max_h * S, max_h * S)
        c.text((cx, cy), p["text"], f, p.get("fg", "#151515"))


def k_bubble(p):
    c = Canvas(520, 440)
    body = ellipse(c.w, c.h, (20, 20, 500, 330))
    left = p.get("tail") == "left"
    tail = poly(c.w, c.h, [(150, 270), (230, 300), (90, 420)] if left else [(370, 270), (290, 300), (430, 420)])
    c.fill(union(body, tail), p["bg"], outline="#151515", outline_w=9)
    bubble_text(c, p, 260, 178, 360, 130)
    return c.finish()


def k_thought(p):
    c = Canvas(520, 460)
    m = cloud_mask(c, 280, 175, 220, 230)
    dots = union(ellipse(c.w, c.h, (110, 320, 170, 372)), ellipse(c.w, c.h, (64, 392, 100, 424)))
    c.fill(union(m, dots), p["bg"], outline="#151515", outline_w=8)
    bubble_text(c, p, 282, 180, 250, 100)
    return c.finish()


def k_chat(p):
    c = Canvas(520, 300)
    left = p.get("tail") == "left"
    body = rrect(c.w, c.h, (30, 20, 490, 250), 100)
    m = new_mask(c.w, c.h)
    d = ImageDraw.Draw(m)
    if left:
        d.pieslice([(-10) * S, 150 * S, 110 * S, 270 * S], 0, 90, fill=255)
        d.polygon([(10 * S, 270 * S), (90 * S, 200 * S), (110 * S, 250 * S)], fill=255)
    else:
        d.pieslice([410 * S, 150 * S, 530 * S, 270 * S], 90, 180, fill=255)
        d.polygon([(510 * S, 270 * S), (430 * S, 200 * S), (410 * S, 250 * S)], fill=255)
    c.fill(union(body, m), sheen(c.w, c.h, p["bg"]))
    if p.get("text"):
        bubble_text(c, p, 260, 137, 340, 120)
    else:  # typing dots
        dot = "#FFFFFF" if lum(rgb(p["bg"])) < 0.6 else "#8E8E93"
        for x in (190, 260, 330):
            c.fill(ellipse(c.w, c.h, (x - 26, 109, x + 26, 161)), dot)
    return c.finish()


KINDS = {"pill": k_pill, "button": k_button, "banner": k_banner, "burst": k_burst, "icon_circle": k_icon_circle,
         "stack": k_stack, "live": k_live, "tag": k_tag, "ribbon": k_ribbon, "seal": k_seal, "verified": k_verified,
         "stamp": k_stamp, "number": k_number, "arrow": k_arrow, "curve_arrow": k_curve_arrow, "ring": k_ring,
         "label_arrow": k_label_arrow, "swoosh": k_swoosh, "shape": k_shape, "bubble": k_bubble, "thought": k_thought,
         "chat": k_chat}


# ----------------------------------------------------------------------------- build
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--graphics", action="store_true", help="only redraw the Pillow graphics and the manifest")
    args = ap.parse_args()
    items: list[dict] = []
    seen: set[str] = set()
    for category in CATEGORY_ORDER:
        for emoji, name, tags in EMOJI.get(category, []):
            sid = slug(name)
            assert sid not in seen, sid
            seen.add(sid)
            rel = f"emoji/{sid}.png"
            if not args.graphics or not (OUT / rel).exists():
                save_png(rasterise(twemoji_svg(emoji), EMOJI_PX), OUT / rel)
            items.append({"id": sid, "name": name, "category": category, "tags": tags, "emoji": emoji,
                          "file": rel, "source": "twemoji"})
    for name, category, tags, kind, params in GRAPHICS:
        sid = slug(name)
        assert sid not in seen, sid
        seen.add(sid)
        rel = f"graphics/{sid}.png"
        save_png(KINDS[kind](params), OUT / rel)
        items.append({"id": sid, "name": name, "category": category, "tags": tags, "file": rel, "source": "sceneforge"})
    order = {c: i for i, c in enumerate(CATEGORY_ORDER)}
    items.sort(key=lambda it: order[it["category"]])
    manifest = {
        "format": "sceneforge-sticker-library", "version": 1, "categories": CATEGORY_ORDER, "items": items,
        "attribution": {"twemoji": f"Emoji graphics: Twemoji {TWEMOJI_TAG} by Twitter, Inc. and other contributors (https://github.com/jdecked/twemoji), licensed CC-BY 4.0.",
                        "sceneforge": "Drawn for SceneForge Studio (GPL-3.0-or-later) with bundled OFL fonts."},
    }
    text = json.dumps(manifest, ensure_ascii=False, indent=1) + "\n"
    (OUT / "library.json").write_text(text, encoding="utf-8")
    (ROOT / "frontend" / "src" / "stickerLibrary.json").write_text(text, encoding="utf-8")
    lic = OUT / "LICENSE-TWEMOJI-GRAPHICS.txt"
    if not lic.exists():
        lic.write_bytes(fetch(f"{TWEMOJI_RAW}/LICENSE-GRAPHICS"))
    size = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    print(f"{len(items)} stickers ({sum(1 for i in items if i['source'] == 'twemoji')} emoji, "
          f"{sum(1 for i in items if i['source'] == 'sceneforge')} graphics), {size / 1e6:.1f} MB in {OUT}")


if __name__ == "__main__":
    main()
