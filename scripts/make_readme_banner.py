"""Draw the README banner (docs/images/banner.png, 1280x400) and the GitHub social preview
(docs/images/social-preview.png, 1280x640) from the app icon, the bundled fonts and four frames
of a SceneForge export.

    python scripts/make_readme_banner.py FRAME1.png FRAME2.png FRAME3.png FRAME4.png

The frames used for the committed images come from the demo project that
scripts/capture_readme_screenshots.py builds (generated pictures only), exported by SceneForge.
"""
from __future__ import annotations

import pathlib
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = pathlib.Path(__file__).resolve().parents[1]
FONTS = ROOT / "assets" / "fonts"
INK = (20, 17, 33)            # near-black with the brand's violet in it
VIOLET = (102, 83, 220)       # the app icon / accent colour (#6653dc)
LILAC = (207, 200, 242)
MUTED = (150, 146, 180)


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


def background(w: int, h: int) -> Image.Image:
    img = Image.new("RGB", (w, h), INK)
    glow = Image.new("L", (w, h), 0)
    ImageDraw.Draw(glow).ellipse((-w * 0.25, -h * 0.9, w * 0.55, h * 1.1), fill=120)
    glow = glow.filter(ImageFilter.GaussianBlur(h * 0.35))
    tint = Image.new("RGB", (w, h), (52, 38, 120))
    return Image.composite(tint, img, glow)


def film_strip(frames: list[Image.Image], frame_w: int) -> Image.Image:
    """A vertical strip of 35 mm-style film: sprocket holes either side, the frames inside."""
    frame_h = round(frame_w * 9 / 16)
    gap, side = 14, 34
    h = len(frames) * (frame_h + gap) + gap
    strip = Image.new("RGBA", (frame_w + 2 * side, h), (12, 10, 18, 255))
    d = ImageDraw.Draw(strip)
    for y in range(10, h - 10, 26):
        for x in (10, frame_w + side + 10):
            d.rounded_rectangle((x, y, x + 14, y + 12), radius=3, fill=(232, 228, 245, 255))
    for i, fr in enumerate(frames):
        y = gap + i * (frame_h + gap)
        strip.paste(fr.convert("RGB").resize((frame_w, frame_h), Image.LANCZOS), (side, y))
    return strip


def title_block(img: Image.Image, x: int, y: int, icon_size: int, title_size: int, social: bool) -> None:
    d = ImageDraw.Draw(img)
    icon = Image.open(ROOT / "desktop" / "icons" / "icon.png").convert("RGBA").resize((icon_size, icon_size), Image.LANCZOS)
    img.paste(icon, (x, y), icon)
    tx = x + icon_size + 22
    d.text((tx, y + icon_size // 2), "SceneForge Studio", font=font("Poppins-Bold.ttf", title_size), fill="white", anchor="lm")
    y2 = y + icon_size + (36 if social else 30)
    d.text((x, y2), "Your story, frame by frame.", font=font("Poppins-Regular.ttf", 34 if social else 30), fill=LILAC)
    # Arabic is a first-class language in SceneForge, so the tagline is in both.
    d.text((x, y2 + (64 if social else 56)), "قصّتك، لقطةً بلقطة", font=font("Tajawal-Bold.ttf", 30 if social else 26),
           fill=MUTED, direction="rtl", language="ar")
    lines = (["Free, open-source video editor",
              "for narrated stories",
              "Trending effects · captions · local AI"] if social else
             ["Free, open-source video editor for narrated stories"])
    for k, line in enumerate(lines):
        d.text((x, y2 + (132 if social else 110) + k * 40), line, font=font("Poppins-Regular.ttf", 24 if social else 21), fill=(232, 228, 245))


def main() -> None:
    frames = [Image.open(p) for p in sys.argv[1:5]]
    if len(frames) != 4:
        raise SystemExit(__doc__)
    out = ROOT / "docs" / "images"
    # banner: title left, a slightly tilted film strip bleeding off the right edge
    w, h = 1280, 400
    img = background(w, h)
    strip = film_strip(frames, 360).rotate(-8, resample=Image.BICUBIC, expand=True)
    img.paste(strip, (w - strip.width + 60, (h - strip.height) // 2 + 40), strip)
    title_block(img, 64, 70, 76, 54, social=False)
    img.save(out / "banner.png", optimize=True)
    # social preview: same, larger type, 2:1
    w, h = 1280, 640
    img = background(w, h)
    strip = film_strip(frames, 430).rotate(-8, resample=Image.BICUBIC, expand=True)
    img.paste(strip, (w - strip.width + 170, (h - strip.height) // 2 + 30), strip)
    title_block(img, 72, 120, 96, 64, social=True)
    img.save(out / "social-preview.png", optimize=True)
    print("wrote", out / "banner.png", "and", out / "social-preview.png")


if __name__ == "__main__":
    main()
