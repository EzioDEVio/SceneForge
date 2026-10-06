"""Deterministic per-script font selection for burned-in text.

The bundled Arabic families (Noto Naskh/Sans Arabic) carry only partial Latin
coverage: Latin digits are drawn at Arabic proportions and spaces are narrow,
while missing Latin letters fall back to whatever system font libass finds.
That made English captions look different on Windows, macOS and Linux.

Instead, every text run is tagged with an explicit ASS \\fn override: Arabic
script uses an Arabic family, everything else uses a Latin family, and both are
bundled in assets/fonts so libass never needs a system fallback. Text stays in
logical order; libass still performs bidi reordering and Arabic shaping.
"""
from __future__ import annotations
from app.render.font_runtime import load_font

import unicodedata

ARABIC_FAMILIES = ("Noto Naskh Arabic", "Noto Sans Arabic", "Amiri", "Tajawal", "Lalezar")
LATIN_DEFAULT = "Noto Sans"
# Arabic families that carry their own Latin letters (keep one design for both scripts).
_OWN_LATIN = {"Amiri", "Tajawal", "Lalezar"}
# Latin display families paired with a matching Arabic design.
_ARABIC_PARTNER = {"Poppins": "Tajawal", "Bebas Neue": "Lalezar", "Anton": "Lalezar", "Pacifico": "Amiri"}
from app.domain.fonts import ALL_FAMILIES
# Latin families whose design matches a serif Arabic companion better.
_SERIF_LATIN = {"Times New Roman", "Georgia"}

_ARABIC_BLOCKS = (
    (0x0600, 0x06FF), (0x0750, 0x077F), (0x0870, 0x089F), (0x08A0, 0x08FF),
    (0xFB50, 0xFDFF), (0xFE70, 0xFEFF), (0x10E60, 0x10E7F), (0x1EE00, 0x1EEFF),
)


def font_pair(family: str | None) -> tuple[str, str]:
    """Return (arabic_family, latin_family) for a user-selected family."""
    family = (family or ARABIC_FAMILIES[0]).strip()
    if family in ARABIC_FAMILIES:
        return family, (family if family in _OWN_LATIN else LATIN_DEFAULT)
    if family in _ARABIC_PARTNER:
        return _ARABIC_PARTNER[family], family
    arabic = "Noto Naskh Arabic" if family in _SERIF_LATIN else "Noto Sans Arabic"
    return arabic, family


def _script(char: str) -> str | None:
    code = ord(char)
    if any(lo <= code <= hi for lo, hi in _ARABIC_BLOCKS):
        # Arabic combining marks follow their base letter; they are Arabic too.
        return "ar"
    cat = unicodedata.category(char)
    if cat[0] == "M":
        return None  # combining mark: stays with its base
    if cat[0] in ("L", "N"):
        return "la"
    return None  # spaces, punctuation, symbols: neutral


def script_runs(text: str) -> list[tuple[str, str]]:
    """Split text into (script, chunk) runs. Neutrals join the preceding run,
    or the following run when they lead the string."""
    runs: list[list[str]] = []
    pending = ""
    for char in text:
        script = _script(char)
        if script is None:
            if runs:
                runs[-1][1] += char
            else:
                pending += char
            continue
        if runs and runs[-1][0] == script:
            runs[-1][1] += char
        else:
            runs.append([script, pending + char])
            pending = ""
    if pending:
        if runs:
            runs[-1][1] += pending
        else:
            runs.append(["la", pending])
    # Neutrals between an Arabic run and a following Arabic run already stay
    # Arabic; a space before a script change stays with the earlier run, which
    # keeps inter-word spacing in the font of the preceding word.
    return [(s, c) for s, c in runs]


def tag_runs(text: str, family: str | None, escape) -> tuple[str, str]:
    """Return (first_family, ass_text) where ass_text holds \\fn switches.

    `escape` neutralises ASS override injection for each chunk; the \\fn tags
    are added afterwards so user text can never open an override block.
    """
    arabic, latin = font_pair(family)
    runs = script_runs(text)
    if not runs:
        return latin, ""
    first = arabic if runs[0][0] == "ar" else latin
    parts: list[str] = []
    current = first
    for script, chunk in runs:
        wanted = arabic if script == "ar" else latin
        if wanted != current:
            parts.append("{\\fn%s}" % wanted)
            current = wanted
        parts.append(escape(chunk))
    return first, "".join(parts)


# libass sizes text by a font's full ascent+descent, which varies a lot between designs
# (Amiri and Lalezar reserve tall space and look small). The added families are scaled so
# their capital letters match Noto Sans at the same size setting; Noto families are
# unchanged, so existing projects keep their look.
_SCALE_FILES = {"Amiri": "Amiri-Regular.ttf", "Tajawal": "Tajawal-Regular.ttf", "Lalezar": "Lalezar-Regular.ttf",
                "Poppins": "Poppins-Regular.ttf", "Bebas Neue": "BebasNeue-Regular.ttf", "Anton": "Anton-Regular.ttf",
                "Pacifico": "Pacifico-Regular.ttf"}
_scale_cache: dict[str, float] = {}


def _line_ratio(path) -> float:
    """Visible capital height as a share of the height libass sizes by (ascent+descent).
    Matching this across fonts makes the same size setting look the same size."""
    from PIL import ImageFont
    f = load_font(str(path), 200)
    a, d = f.getmetrics()
    top, bottom = f.getbbox("H")[1], f.getbbox("H")[3]
    return (a + d) / max(1, bottom - top)


def family_scale(family: str | None) -> float:
    """Size multiplier for a family so libass matches the browser preview (1.0 for Noto)."""
    if family not in _SCALE_FILES:
        return 1.0
    if family not in _scale_cache:
        try:
            from pathlib import Path
            from app.config import RESOURCE_DIR
            fonts = Path(RESOURCE_DIR) / "assets" / "fonts"
            _scale_cache[family] = round(_line_ratio(fonts / _SCALE_FILES[family]) / _line_ratio(fonts / "NotoSans-Regular.ttf"), 3)
        except Exception:
            _scale_cache[family] = 1.0
    return _scale_cache[family]


def text_scale(family: str | None, text: str) -> float:
    """Scale for the font that draws most of this text (Arabic partner or Latin family)."""
    arabic, latin = font_pair(family)
    runs = script_runs(text or "")
    ar = sum(len(c) for s, c in runs if s == "ar")
    la = sum(len(c) for s, c in runs if s != "ar")
    return family_scale(arabic if ar > la else latin)
