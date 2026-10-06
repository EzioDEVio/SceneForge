"""Textured text titles: a transparent PNG of a word or line filled with a texture.

Texture sources: procedural presets drawn with numpy (no network, deterministic),
any image from the project (cover-fitted to the text box), or an AI image
generated from a prompt (api/creative.py stores it as an asset first).
Optional outline, outer glow and soft drop shadow. The PNG is placed in the
scene as a sticker overlay, so position, size, animation and loop motion apply.

Arabic: letters are joined with arabic_reshaper and ordered with python-bidi
(the same approach as map route labels), then drawn with Pillow's BASIC layout,
so results match on every OS even where Pillow lacks the RAQM engine. Complex
OpenType features beyond joining (e.g. some ligatures, mark positioning in Amiri)
are therefore approximate.
"""
from __future__ import annotations
from app.render.font_runtime import load_font

import re
from pathlib import Path

PRESETS = ("lava", "neon", "gold", "chrome", "marble", "ice", "fire", "pixel", "galaxy")
FONTS = {
    "Anton": "Anton-Regular.ttf", "Bebas Neue": "BebasNeue-Regular.ttf", "Poppins": "Poppins-Bold.ttf",
    "Noto Sans": "NotoSans-Bold.ttf", "Pacifico": "Pacifico-Regular.ttf", "Lalezar": "Lalezar-Regular.ttf",
    "Noto Sans Arabic": "NotoSansArabic-Regular.ttf", "Amiri": "Amiri-Bold.ttf",
    'DejaVu Sans': 'DejaVuSans.ttf',
    'DejaVu Serif': 'DejaVuSerif.ttf',
    'DejaVu Sans Mono': 'DejaVuSansMono.ttf',
    'Latin Modern Sans': 'lmsans10-regular.otf',
    'Latin Modern Roman': 'lmroman10-regular.otf',
    'Latin Modern Mono': 'lmmono10-regular.otf',
    'Latin Modern Roman Slanted': 'lmromanslant10-regular.otf',
    'Latin Modern Sans Demi Cond': 'lmsansdemicond10-regular.otf',
    'Latin Modern Mono Caps': 'lmmonocaps10-regular.otf',
    "Tajawal": "Tajawal-Bold.ttf", "Noto Naskh Arabic": "NotoNaskhArabic-Bold.ttf",
}
# Latin-only display faces get an Arabic partner when the text contains Arabic.
_ARABIC_FALLBACK = {"Anton": "Lalezar", "Bebas Neue": "Lalezar", "Poppins": "Tajawal", "Noto Sans": "Noto Naskh Arabic", "Pacifico": "Lalezar"}
_ARABIC_FALLBACK.update({f: 'Noto Naskh Arabic' for f in FONTS if f.startswith(('DejaVu', 'Latin Modern'))})
_ARABIC = re.compile(r"[؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]")
MAX_CHARS = 80


class TexturedTextError(ValueError):
    pass


# ---------------------------------------------------------------- textures

def _noise(w: int, h: int, cell: int, rng):
    import numpy as np
    from PIL import Image
    gw, gh = max(2, w // max(1, cell) + 2), max(2, h // max(1, cell) + 2)
    g = Image.fromarray((rng.random((gh, gw)) * 255).astype(np.uint8))
    return np.asarray(g.resize((w, h), Image.Resampling.BICUBIC)).astype(np.float32) / 255


def _fbm(w: int, h: int, rng, base: int, octaves: int = 5):
    import numpy as np
    total, amp, norm = np.zeros((h, w), np.float32), 1.0, 0.0
    cell = base
    for _ in range(octaves):
        total += amp * _noise(w, h, max(2, cell), rng)
        norm += amp
        amp *= 0.5
        cell = max(2, cell // 2)
    return total / norm


def _ramp(t, stops):
    """Map t (0..1 array) through colour stops [(pos, (r,g,b)), ...] -> HxWx3 uint8."""
    import numpy as np
    pos = [p for p, _ in stops]
    out = np.stack([np.interp(t, pos, [c[i] for _, c in stops]) for i in range(3)], axis=-1)
    return np.clip(out, 0, 255).astype(np.uint8)


def texture_preset(name: str, w: int, h: int, seed: int = 7):
    """RGB PIL image of a procedural texture."""
    import numpy as np
    from PIL import Image
    if name not in PRESETS:
        raise TexturedTextError(f"Texture preset must be one of: {', '.join(PRESETS)}.")
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    v = yy / max(1, h - 1)
    s = max(w, h)
    if name == "lava":
        f = _fbm(w, h, rng, s // 4)
        cracks = (1 - np.abs(2 * _fbm(w, h, rng, s // 6) - 1)) ** 8
        t = np.clip(0.55 * f + 0.9 * cracks, 0, 1)
        arr = _ramp(t, [(0, (25, 5, 5)), (0.35, (110, 15, 5)), (0.6, (230, 70, 10)), (0.8, (255, 170, 30)), (1, (255, 245, 170))])
    elif name == "neon":
        band = 0.5 + 0.5 * np.sin(xx / s * 9 + v * 4)
        t = np.clip(0.65 * v + 0.35 * band, 0, 1)
        arr = _ramp(t, [(0, (255, 60, 220)), (0.5, (140, 80, 255)), (1, (40, 240, 255))])
        core = np.exp(-((v - 0.45) ** 2) / 0.02)[..., None]
        arr = np.clip(arr + core * 90, 0, 255).astype(np.uint8)
    elif name == "gold":
        f = _fbm(w, h, rng, s // 3, 3)
        t = 0.5 + 0.5 * np.sin((xx * 0.6 + yy) / s * 14 + f * 4)
        arr = _ramp(t, [(0, (110, 70, 15)), (0.35, (205, 150, 40)), (0.6, (255, 215, 90)), (0.8, (255, 245, 190)), (1, (175, 120, 30))])
    elif name == "chrome":
        t = np.where(v < 0.52, 0.55 + 0.45 * (1 - v / 0.52), 0.15 + 0.85 * np.clip((v - 0.52) / 0.48, 0, 1) ** 0.8)
        t = np.clip(t + 0.06 * (_fbm(w, h, rng, s // 8, 3) - 0.5), 0, 1)
        arr = _ramp(t, [(0, (35, 40, 55)), (0.3, (110, 120, 140)), (0.7, (220, 228, 240)), (1, (255, 255, 255))])
    elif name == "marble":
        turb = _fbm(w, h, rng, s // 3)
        t = np.abs(np.sin((xx + yy * 0.6) / s * 10 + turb * 9)) ** 0.35
        arr = _ramp(t, [(0, (70, 70, 80)), (0.4, (190, 190, 195)), (1, (248, 246, 240))])
    elif name == "ice":
        cracks = (1 - np.abs(2 * _fbm(w, h, rng, s // 5) - 1)) ** 12
        t = np.clip(0.55 * (1 - v) + 0.25 * _fbm(w, h, rng, s // 4) + 0.8 * cracks, 0, 1)
        arr = _ramp(t, [(0, (20, 80, 150)), (0.45, (90, 180, 235)), (0.8, (200, 240, 255)), (1, (255, 255, 255))])
    elif name == "fire":
        f = _fbm(w, h, rng, s // 6)
        t = np.clip(v * 1.15 + (f - 0.5) * 0.45, 0, 1)
        arr = _ramp(t, [(0, (120, 0, 10)), (0.3, (220, 30, 10)), (0.6, (255, 120, 0)), (0.85, (255, 210, 40)), (1, (255, 250, 200))])
    elif name == "pixel":
        block = max(4, h // 10)
        palette = np.array([(255, 70, 110), (255, 200, 40), (60, 210, 120), (50, 150, 255), (170, 90, 255), (255, 255, 255)], np.uint8)
        gh, gw = h // block + 1, w // block + 1
        idx = rng.integers(0, len(palette), (gh, gw))
        small = Image.fromarray(palette[idx])
        arr = np.asarray(small.resize((gw * block, gh * block), Image.Resampling.NEAREST))[:h, :w].copy()
        arr[(yy.astype(int) % block == 0) | (xx.astype(int) % block == 0)] = (30, 30, 45)
    else:  # galaxy
        f = _fbm(w, h, rng, s // 3)
        g = _fbm(w, h, rng, s // 5)
        t = np.clip(f * 1.2 - 0.15, 0, 1)
        arr = _ramp(t, [(0, (10, 5, 35)), (0.4, (60, 20, 120)), (0.7, (170, 50, 170)), (1, (120, 200, 255))]).astype(np.float32)
        arr[..., 2] += 60 * g
        stars = rng.random((h, w)) > 0.996
        arr[stars] = 255
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def cover(img, w: int, h: int):
    """Scale-and-crop an image so it fills w x h (like CSS background-size: cover)."""
    from PIL import Image
    img = img.convert("RGB")
    s = max(w / img.width, h / img.height)
    nw, nh = max(w, round(img.width * s)), max(h, round(img.height * s))
    img = img.resize((nw, nh), Image.Resampling.LANCZOS)
    x, y = (nw - w) // 2, (nh - h) // 2
    return img.crop((x, y, x + w, y + h))


# ---------------------------------------------------------------- text

def _font_path(family: str, arabic: bool) -> Path:
    from app.config import RESOURCE_DIR
    if family not in FONTS:
        raise TexturedTextError(f"Font must be one of: {', '.join(FONTS)}.")
    if arabic and family in _ARABIC_FALLBACK:
        family = _ARABIC_FALLBACK[family]
    return Path(RESOURCE_DIR) / "assets" / "fonts" / FONTS[family]


def _shape(line: str) -> str:
    if not _ARABIC.search(line):
        return line
    import arabic_reshaper
    from bidi import get_display
    return get_display(arabic_reshaper.reshape(line))


def _rgb(hex_color: str) -> tuple[int, int, int]:
    if not isinstance(hex_color, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", hex_color):
        raise TexturedTextError("Colours must look like #RRGGBB.")
    return tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))


def render_textured_text(text: str, texture, font: str = "Anton", size: int = 160, outline: int = 0,
                         outline_color: str = "#FFFFFF", glow: int = 0, glow_color: str = "#FFD25A",
                         shadow: bool = True):
    """Return an RGBA PIL image. `texture` is a preset name or an RGB PIL image."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    text = (text or "").strip()
    if not text:
        raise TexturedTextError("Type the text for the title.")
    if len(text) > MAX_CHARS:
        raise TexturedTextError(f"Textured titles are limited to {MAX_CHARS} characters.")
    if not 24 <= size <= 400:
        raise TexturedTextError("Font size must be between 24 and 400.")
    if not 0 <= outline <= 30 or not 0 <= glow <= 100:
        raise TexturedTextError("Outline must be 0-30 and glow 0-100.")
    oc, gc = _rgb(outline_color), _rgb(glow_color)
    arabic = bool(_ARABIC.search(text))
    try:
        fnt = load_font(str(_font_path(font, arabic)), size, layout_engine=ImageFont.Layout.BASIC)
    except OSError as e:
        raise TexturedTextError(f"The font could not be loaded: {e}")
    shaped = "\n".join(_shape(line) for line in text.splitlines() if line.strip())
    probe = ImageDraw.Draw(Image.new("L", (8, 8)))
    spacing = int(size * 0.12)
    l, t, r, b = probe.multiline_textbbox((0, 0), shaped, font=fnt, align="center", spacing=spacing, stroke_width=outline)
    glow_r = int(size * 0.18 * glow / 100)
    pad = outline + 2 * glow_r + int(size * 0.12) + 4
    w, h = int(r - l) + 2 * pad, int(b - t) + 2 * pad
    origin = (pad - l, pad - t)

    def mask(stroke: int = 0):
        m = Image.new("L", (w, h), 0)
        ImageDraw.Draw(m).multiline_text(origin, shaped, font=fnt, fill=255, align="center", spacing=spacing,
                                         stroke_width=stroke, stroke_fill=255)
        return m

    fill_mask = mask()
    outer = mask(outline) if outline else fill_mask
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if shadow:
        sm = outer.filter(ImageFilter.GaussianBlur(max(2, size * 0.04)))
        sm = sm.point(lambda a: int(a * 0.6))
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        off = max(2, int(size * 0.05))
        layer.paste((0, 0, 0, 255), (off, off), sm.crop((0, 0, w - off, h - off)))
        out = Image.alpha_composite(out, layer)
    if glow_r:
        gm = outer.filter(ImageFilter.GaussianBlur(glow_r))
        ga = np.clip(np.asarray(gm).astype(np.float32) * (1.2 + 1.3 * glow / 100), 0, 255).astype(np.uint8)
        layer = Image.new("RGBA", (w, h), gc + (0,))
        layer.putalpha(Image.fromarray(ga))
        out = Image.alpha_composite(out, layer)
    if outline:
        layer = Image.new("RGBA", (w, h), oc + (0,))
        layer.putalpha(outer)
        out = Image.alpha_composite(out, layer)
    tex = texture_preset(texture, w, h) if isinstance(texture, str) else cover(texture, w, h)
    filled = tex.convert("RGBA")
    filled.putalpha(fill_mask)
    out = Image.alpha_composite(out, filled)
    bbox = out.getchannel("A").getbbox()
    return out.crop(bbox) if bbox else out


def render_knockout_card(text: str, width: int, height: int, font: str = "Anton", size: int = 220, x: float = 50, y: float = 50,
                         background: str = "#E10600", opacity: int = 100, outline: int = 6, outline_color: str = "#FFFFFF",
                         spacing: int = 4):
    """0.9.1 "video inside text": a full-frame card in a solid colour with the letters cut out, so the
    scene's video or picture shows through the text (optionally with an outline around the letters).
    Returns an RGBA image of width x height."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    text = (text or "").strip()
    if not text:
        raise TexturedTextError("Type the text for the title.")
    if len(text) > MAX_CHARS:
        raise TexturedTextError(f"Titles are limited to {MAX_CHARS} characters.")
    if not 24 <= size <= 600:
        raise TexturedTextError("Font size must be between 24 and 600.")
    if not 0 <= outline <= 30 or not 10 <= opacity <= 100 or not 0 <= spacing <= 60:
        raise TexturedTextError("Outline must be 0-30, opacity 10-100 and letter spacing 0-60.")
    bg, oc = _rgb(background), _rgb(outline_color)
    arabic = bool(_ARABIC.search(text))
    scale = height / 1080                        # size and outline are given at 1080p
    px, ol, sp = max(12, int(size * scale)), int(round(outline * scale)), int(round(spacing * scale))
    try:
        fnt = load_font(str(_font_path(font, arabic)), px, layout_engine=ImageFont.Layout.BASIC)
    except OSError as e:
        raise TexturedTextError(f"The font could not be loaded: {e}")
    lines = [_shape(line) for line in text.splitlines() if line.strip()]
    draw = ImageDraw.Draw(Image.new("L", (8, 8)))

    def line_width(line: str) -> int:
        if not sp or arabic:
            return int(draw.textlength(line, font=fnt))
        return int(sum(draw.textlength(ch, font=fnt) for ch in line) + sp * (len(line) - 1))
    # 0.9.2: shrink to fit. A long title at a big size ran off both edges of the frame;
    # the widest line (plus its outline) now always fits inside 92% of the width.
    room = width * 0.92 - 2 * ol
    widest = max(line_width(line) for line in lines)
    if widest > room > 0:
        px = max(12, int(px * room / widest))
        sp = int(round(sp * room / widest))
        fnt = load_font(str(_font_path(font, arabic)), px, layout_engine=ImageFont.Layout.BASIC)

    def line_width(line: str) -> int:  # noqa: F811  (re-measured with the fitted font)
        if not sp or arabic:
            return int(draw.textlength(line, font=fnt))
        return int(sum(draw.textlength(ch, font=fnt) for ch in line) + sp * (len(line) - 1))
    asc, desc = fnt.getmetrics()
    line_h = asc + desc
    gap = int(px * 0.08)
    total_h = line_h * len(lines) + gap * (len(lines) - 1)
    cx, cy = width * x / 100, height * y / 100
    holes = Image.new("L", (width, height), 0)
    ring = Image.new("L", (width, height), 0)
    dh, dr = ImageDraw.Draw(holes), ImageDraw.Draw(ring)
    top = cy - total_h / 2
    for i, line in enumerate(lines):
        lx = cx - line_width(line) / 2
        ly = top + i * (line_h + gap)
        pieces = [(line, lx)] if (not sp or arabic) else []
        if not pieces:
            pos = lx
            for ch in line:
                pieces.append((ch, pos))
                pos += draw.textlength(ch, font=fnt) + sp
        for chunk, px_x in pieces:
            if ol:
                dr.text((px_x, ly), chunk, font=fnt, fill=255, stroke_width=ol, stroke_fill=255)
            dh.text((px_x, ly), chunk, font=fnt, fill=255)
    hole = np.asarray(holes).astype(np.float32) / 255
    edge = np.clip(np.asarray(ring).astype(np.float32) / 255 - hole, 0, 1) if ol else np.zeros_like(hole)
    a_bg = opacity / 100
    rgb = np.empty((height, width, 3), np.float32)
    rgb[:] = bg
    rgb = rgb * (1 - edge[..., None]) + np.array(oc, np.float32) * edge[..., None]
    alpha = (a_bg * (1 - hole - edge) + edge).clip(0, 1)      # holes are see-through, outline is solid
    out = np.dstack([rgb, alpha * 255]).round().clip(0, 255).astype(np.uint8)
    return Image.fromarray(out, "RGBA")
