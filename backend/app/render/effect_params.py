"""Per-effect settings ("Effect settings" panel) for every effect preset.

Each preset gets a small declarative schema (name, label, kind number|color,
min, max, step, default, optional unit and CSS-preview hint) plus a builder
that turns the parameters into the FFmpeg filter fragment.

Stored on the scene as ``look_json.fx_params = {<preset_key>: {param: value}}``
(kept per preset, so switching back to a look restores its settings; only the
active preset's entry is used when rendering). Missing params use defaults.

Backwards compatibility: every builder works by *rewriting* the preset's
existing filter string (``filters._EFFECT_FILTERS`` / the halation chain) and
only touches a token when its parameter differs from the default, so default
parameters reproduce the old filter string byte-for-byte — existing projects
render exactly as before (tests/integration/test_effect_params.py proves it
for every preset).

Presets whose settings already live elsewhere in look_json (glitch, focus
blur / tilt-shift, mosaic, chromatic split) are listed with ``managed_by``;
their dedicated panels keep owning them and fx_params rejects them.

Served to the frontend by GET /api/effects/schema so the two never drift.
"""
from __future__ import annotations

import re
from typing import Callable

from app.domain.constants import EffectPreset

_HEX = re.compile(r"#[0-9A-Fa-f]{6}")


class EffectParamsError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------
def _num(name, label, lo, hi, default, step=1, unit="", css=None, help=""):
    p = {"name": name, "label": label, "kind": "number", "min": lo, "max": hi, "step": step, "default": default}
    if unit:
        p["unit"] = unit
    if css:
        p["css"] = css          # live-preview hint for the editor (CSS filter approximation)
    if help:
        p["help"] = help
    return p


def _color(name, label, default, help=""):
    p = {"name": name, "label": label, "kind": "color", "default": default}
    if help:
        p["help"] = help
    return p


# Common parameters. css: {"fn": ratio fns saturate|contrast (value/default),
# offset fns brightness|warmth|hue|blur (value-default)*k}
def CONTRAST(d):
    return _num("contrast", "Contrast", 50, 200, d, unit="%", css={"fn": "contrast"})


def SATURATION(d):
    return _num("saturation", "Saturation", 0, 200, d, unit="%", css={"fn": "saturate"})


def BRIGHTNESS(d, lo=-30, hi=30, step=1):
    return _num("brightness", "Brightness", lo, hi, d, step=step, css={"fn": "brightness", "k": 0.01})


WARMTH = _num("warmth", "Warmth", -100, 100, 0, css={"fn": "warmth", "k": 0.004}, help="Negative = cooler, positive = warmer.")
TINT = _num("tint", "Tint", -100, 100, 0, css={"fn": "hue", "k": -0.2}, help="Negative = green, positive = magenta.")
FADE = _num("fade", "Fade (lift blacks)", 0, 100, 0, css={"fn": "brightness", "k": 0.0015})
GRAIN = _num("grain", "Grain", 0, 60, 0)
SHADOWS = _num("shadows", "Shadow tint", 0, 200, 100, unit="%", help="Strength of the colour cast in the shadows.")
HIGHLIGHTS = _num("highlights", "Highlight tint", 0, 200, 100, unit="%", help="Strength of the colour cast in the highlights.")
TONE = _num("tone", "Tint strength", 0, 200, 100, unit="%", help="Strength of the colour cast.")


def VIGNETTE(d=50):
    return _num("vignette", "Vignette", 0, 100, d, help="How much the corners darken.")


# ---------------------------------------------------------------------------
# Filter-string rewriting helpers
# ---------------------------------------------------------------------------
def _n(x, nd=4) -> str:
    x = round(float(x), nd)
    return "0" if x == 0 else format(x, "g")


def _filter_opts(chain: str, filt: str, nth: int = 0) -> tuple[int, int]:
    """(start, end) of the option text of the nth `filt=` in a filter chain."""
    starts = [m.end() for m in re.finditer(r"(?:^|(?<=[,;\]]))" + re.escape(filt) + "=", chain)]
    if len(starts) <= nth:
        raise KeyError(f"{filt} not in chain")
    j, quoted = starts[nth], False
    while j < len(chain):
        c = chain[j]
        if c == "'":
            quoted = not quoted
        elif not quoted and c in ",;[":
            break
        j += 1
    return starts[nth], j


def _set(chain: str, filt: str, key: str, text: str, nth: int = 0) -> str:
    """Replace option `key` of the nth `filt` (appended when missing)."""
    a, b = _filter_opts(chain, filt, nth)
    pos, quoted, tok = a, False, a
    tokens = []
    while pos <= b:
        c = chain[pos] if pos < b else ":"
        if c == "'":
            quoted = not quoted
        elif c == ":" and not quoted:
            tokens.append((tok, pos))
            tok = pos + 1
        pos += 1
    for s, e in tokens:
        if chain[s:e].startswith(key + "="):
            return chain[:s] + f"{key}={text}" + chain[e:]
    return chain[:b] + f":{key}={text}" + chain[b:]


def _scale_cb(chain: str, factor: float, ranges: str) -> str:
    """Scale the colorbalance offsets of the given tonal ranges (s/m/h)."""
    if factor == 1:
        return chain
    a, b = _filter_opts(chain, "colorbalance")
    out = []
    for tok in chain[a:b].split(":"):
        k, _, v = tok.partition("=")
        out.append(f"{k}={_n(float(v) * factor)}" if len(k) == 2 and k[1] in ranges else tok)
    return chain[:a] + ":".join(out) + chain[b:]


def _rgb(hexcolor: str) -> tuple[int, int, int]:
    return int(hexcolor[1:3], 16), int(hexcolor[3:5], 16), int(hexcolor[5:7], 16)


def _vig_div(v: float, d0: float) -> float:
    """Vignette amount 0-100 -> divisor of PI (angle = PI/d). 50 = the preset's
    original divisor, 0 = barely visible (PI/8), 100 = strongest (PI/2)."""
    if v == 50:
        return d0
    return d0 + (50 - v) / 50 * (8 - d0) if v < 50 else d0 - (v - 50) / 50 * (d0 - 2)


class _P(dict):
    """Effective params (defaults merged) that know which ones changed."""

    def __init__(self, values: dict, defaults: dict):
        super().__init__({**defaults, **values})
        self.defaults = defaults

    def changed(self, name: str) -> bool:
        return name in self.defaults and self[name] != self.defaults[name]


def _upd(chain: str, p: _P, name: str, filt: str, key: str, scale=0.01, nth=0) -> str:
    return _set(chain, filt, key, _n(p[name] * scale), nth) if p.changed(name) else chain


def _tail(chain: str, p: _P, eq: tuple = ()) -> str:
    """Append the generic finishing tweaks (only those that changed):
    eq (contrast/saturation/brightness) -> warmth/tint -> fade -> grain."""
    extra = []
    eqs = [f"{k}={_n(p[k] / 100)}" for k in eq if p.changed(k)]
    if eqs:
        extra.append("eq=" + ":".join(eqs))
    if p.changed("warmth") or p.changed("tint"):
        w, t = p.get("warmth", 0) / 100, p.get("tint", 0) / 100
        extra.append(f"colorbalance=rm={_n(0.1 * w)}:gm={_n(-0.08 * t)}:bm={_n(-0.1 * w)}")
    if p.changed("fade"):
        f = p["fade"] / 100
        extra.append(f"curves=all='0/{_n(0.15 * f)} 1/{_n(1 - 0.05 * f)}'")
    if p.changed("grain"):
        extra.append(f"noise=alls={int(round(p['grain']))}:allf=t+u")
    return ",".join([chain, *extra]) if extra else chain


def _base(preset) -> str:
    from app.render.filters import _EFFECT_FILTERS
    return _EFFECT_FILTERS[preset]


# ---------------------------------------------------------------------------
# Builders (p: effective params, w/h: render size)
# ---------------------------------------------------------------------------
def _b_bw(p, w, h):
    c = _base(EffectPreset.BLACK_AND_WHITE)
    if p.changed("filter"):
        k = p["filter"] / 100
        r, g, b = _n(0.299 + 0.4 * k), _n(0.587 - 0.2 * k), _n(0.114 - 0.2 * k)
        c = f"colorchannelmixer={r}:{g}:{b}:0:{r}:{g}:{b}:0:{r}:{g}:{b}:0," + c
    return _tail(c, p, ("contrast", "brightness"))


_SEPIA_TONE = "#FFE3B1"     # the colour of the classic sepia matrix (row sums 1.351 : 1.203 : 0.937)


def _b_sepia(p, w, h):
    c = _base(EffectPreset.SEPIA)
    if p.changed("color"):
        ratios = [x / y for x, y in zip(_rgb(p["color"]), _rgb(_SEPIA_TONE))]
        a, b = _filter_opts(c, "colorchannelmixer")
        vals = c[a:b].split(":")
        vals = [v if v == "0" else _n(float(v) * ratios[i // 4], 3) for i, v in enumerate(vals)]
        c = c[:a] + ":".join(vals) + c[b:]
    return _tail(c, p, ("contrast",))


def _b_warm(p, w, h):
    c = _base(EffectPreset.WARM)
    if p.changed("warmth"):
        c = _set(_set(c, "eq", "gamma_r", _n(1 + 0.0012 * p["warmth"])), "eq", "gamma_b", _n(1 - 0.0012 * p["warmth"]))
    if p.changed("tint"):
        c = _set(c, "eq", "gamma_g", _n(1 - 0.001 * p["tint"]))
    c = _upd(c, p, "saturation", "eq", "saturation")
    return _upd(c, p, "contrast", "eq", "contrast")


def _b_cool(p, w, h):
    c = _base(EffectPreset.COOL)
    if p.changed("coolness"):
        c = _set(_set(c, "eq", "gamma_b", _n(1 + 0.0016 * p["coolness"])), "eq", "gamma_r", _n(1 - 0.001 * p["coolness"]))
    if p.changed("tint"):
        c = _set(c, "eq", "gamma_g", _n(1 - 0.001 * p["tint"]))
    c = _upd(c, p, "saturation", "eq", "saturation")
    return _upd(c, p, "contrast", "eq", "contrast")


def _b_tail_only(preset, eq=("contrast", "saturation")):
    return lambda p, w, h: _tail(_base(preset), p, eq)


def _b_vignette(p, w, h):
    c = f"vignette=PI/{_n(_vig_div(p['vignette'], 4), 3)}"
    if p.changed("x"):
        c += f":x0=w*{_n(p['x'] / 100)}"
    if p.changed("y"):
        c += f":y0=h*{_n(p['y'] / 100)}"
    return c


def _b_soft_glow(p, w, h):
    c = _upd(_base(EffectPreset.SOFT_GLOW), p, "radius", "gblur", "sigma", 1)
    return _tail(c, p, ("brightness", "saturation"))


def _b_grades(preset, eq_keys=("contrast", "saturation"), gamma=False):
    """colorbalance grades: shadow/highlight tint strength + eq values."""
    def build(p, w, h):
        c = _scale_cb(_base(preset), p["shadows"] / 100, "s")
        c = _scale_cb(c, p["highlights"] / 100, "h")
        for k in eq_keys:
            c = _upd(c, p, k, "eq", k)
        return c
    return build


def _b_noir(p, w, h):
    c = _upd(_base(EffectPreset.NOIR), p, "contrast", "eq", "contrast")
    c = _upd(c, p, "brightness", "eq", "brightness")
    if p.changed("vignette"):
        c = c.replace("vignette=PI/4", f"vignette=PI/{_n(_vig_div(p['vignette'], 4), 3)}")
    return _tail(c, p)


def _b_sharpen(p, w, h):
    r = int(p["radius"])
    return f"unsharp={r}:{r}:{_n(p['amount'])}:{r}:{r}:{_n(p['chroma'])}"


def _b_negative(p, w, h):
    c = _tail(_base(EffectPreset.NEGATIVE), p, ("contrast", "saturation"))
    return c + f",hue=h={_n(p['hue'])}" if p.changed("hue") else c


def _b_film_grain(p, w, h):
    c = _base(EffectPreset.FILM_GRAIN)
    a = int(round(p["amount"]))
    if p.changed("color"):
        ch = int(round(a * p["color"] / 100))
        c = f"noise=c0s={a}:c1s={ch}:c2s={ch}:allf=t+u"
    elif p.changed("amount"):
        c = _set(c, "noise", "alls", str(a))
    return _tail(c, p, ("contrast",))


def _b_eq_core(preset, keys):
    """Presets whose look is one eq: map params straight onto its options.
    keys: (param, eq option, scale)."""
    def build(p, w, h):
        c = _base(preset)
        for name, key, scale in keys:
            c = _upd(c, p, name, "eq", key, scale)
        return _tail(c, p)
    return build


def _b_dream(p, w, h):
    c = _upd(_base(EffectPreset.DREAM), p, "softness", "gblur", "sigma", 1)
    c = _upd(c, p, "brightness", "eq", "brightness")
    c = _upd(c, p, "saturation", "eq", "saturation")
    return _tail(c, p)


def _b_vhs(p, w, h):
    c = _base(EffectPreset.VHS)
    if p.changed("bleed"):
        b = int(round(p["bleed"]))
        c = _set(_set(c, "chromashift", "cbh", str(b)), "chromashift", "crh", str(-b))
    if p.changed("noise"):
        c = _set(c, "noise", "alls", str(int(round(p["noise"]))))
    if p.changed("scanlines"):
        c = _set(c, "drawgrid", "c", f"black@{_n(p['scanlines'] / 100)}")
    if p.changed("tracking"):
        c = _set(c, "colorchannelmixer", "aa", _n(p["tracking"] / 100))
    return c


def _b_glow(p, w, h):
    c = _upd(_base(EffectPreset.GLOW), p, "radius", "gblur", "sigma", 1)
    c = _upd(c, p, "brightness", "eq", "brightness")
    c = _upd(c, p, "contrast", "eq", "contrast")
    return _upd(c, p, "amount", "blend", "all_opacity")


_DUO_SHADOW, _DUO_HIGHLIGHT = "#1B2A6B", "#F2C94C"      # (27,42,107) -> (242,201,76)


def _b_duotone(p, w, h):
    (r0, g0, b0), (r1, g1, b1) = _rgb(p["shadow"]), _rgb(p["highlight"])
    con = f",eq=contrast={_n(p['contrast'] / 100)}" if p.changed("contrast") else ""
    return (f"hue=s=0{con},lutrgb=r='{r0}+val*({r1}-{r0})/255':g='{g0}+val*({g1}-{g0})/255':"
            f"b='{b0}+val*({b1}-{b0})/255'")


_PAPER = "#F2EBD1"   # warm newsprint paper (the .95/.92/.82 channel gains)


def _b_newsprint(p, w, h):
    c = _upd(_base(EffectPreset.NEWSPRINT), p, "contrast", "eq", "contrast")
    if p.changed("grain"):
        c = _set(c, "noise", "alls", str(int(round(p["grain"]))))
    if p.changed("paper"):
        ratios = [x / y for x, y in zip(_rgb(p["paper"]), _rgb(_PAPER))]
        a, b = _filter_opts(c, "colorchannelmixer")
        vals = c[a:b].split(":")
        for i, pos in enumerate((0, 5, 10)):
            vals[pos] = _n(float(vals[pos]) * ratios[i], 3)
        c = c[:a] + ":".join(vals) + c[b:]
    if p.changed("sharpen"):
        c = c.replace("unsharp=3:3:0.6", f"unsharp=3:3:{_n(p['sharpen'] / 100)}")
    return c


def _b_old_film(p, w, h):
    c = _upd(_base(EffectPreset.OLD_FILM), p, "saturation", "eq", "saturation")
    c = _upd(c, p, "contrast", "eq", "contrast")
    if p.changed("grain"):
        c = _set(c, "noise", "alls", str(int(round(p["grain"]))))
    if p.changed("vignette"):
        c = c.replace("vignette=PI/3.5", f"vignette=PI/{_n(_vig_div(p['vignette'], 3.5), 3)}")
    return c


def _b_pastel(p, w, h):
    c = _base(EffectPreset.PASTEL)
    for k in ("contrast", "brightness", "saturation"):
        c = _upd(c, p, k, "eq", k)
    return _scale_cb(c, p["tone"] / 100, "smh")


def _b_bleach(p, w, h):
    c = _upd(_base(EffectPreset.BLEACH_BYPASS), p, "color", "hue", "s")
    c = _upd(c, p, "contrast", "eq", "contrast")
    c = _upd(c, p, "brightness", "eq", "brightness")
    return _scale_cb(c, p["tone"] / 100, "smh")


def _b_portra(p, w, h):
    c = _scale_cb(_base(EffectPreset.PORTRA), p["tone"] / 100, "smh")
    c = _upd(c, p, "saturation", "eq", "saturation")
    c = _upd(c, p, "contrast", "eq", "contrast")
    return _tail(c, p)


def _b_matte(p, w, h):
    c = _base(EffectPreset.MATTE)
    if p.changed("lift"):
        c = c.replace("'0/0.08 ", f"'0/{_n(p['lift'] / 100)} ")
    if p.changed("white"):
        c = c.replace(" 1/0.94'", f" 1/{_n(p['white'] / 100)}'")
    c = _upd(c, p, "contrast", "eq", "contrast")
    return _upd(c, p, "saturation", "eq", "saturation")


def _b_pop(p, w, h):
    c = _base(EffectPreset.POP_COLOR)
    for k in ("saturation", "contrast", "gamma"):
        c = _upd(c, p, k, "eq", k)
    if p.changed("sharpen"):
        c = c.replace("unsharp=5:5:0.45:", f"unsharp=5:5:{_n(p['sharpen'] / 100)}:")
    return c


def _b_rose(p, w, h):
    c = _scale_cb(_base(EffectPreset.ROSE_GLOW), p["shadows"] / 100, "s")
    c = _scale_cb(c, p["highlights"] / 100, "h")
    c = _upd(c, p, "brightness", "eq", "brightness")
    return _upd(c, p, "softness", "gblur", "sigma", 1)


def _b_mono_blue(p, w, h):
    c = _scale_cb(_base(EffectPreset.MONO_BLUE), p["tone"] / 100, "smh")
    c = _upd(c, p, "contrast", "eq", "contrast")
    return _upd(c, p, "brightness", "eq", "brightness")


_TRAIL = (1.0, 0.55, 0.25, 0.1)    # the original 4-frame weight curve


def _b_motion_trail(p, w, h):
    if not (p.changed("frames") or p.changed("trail")):
        return _base(EffectPreset.MOTION_TRAIL)
    n, expo = int(p["frames"]), 100 / p["trail"]
    weights = []
    for i in range(n):
        t = i * (len(_TRAIL) - 1) / (n - 1)
        k = min(int(t), len(_TRAIL) - 2)
        v = _TRAIL[k] + (_TRAIL[k + 1] - _TRAIL[k]) * (t - k)
        weights.append(_n(v ** expo, 3))
    return f"tmix=frames={n}:weights='{' '.join(weights)}'"


_HALATION = "#FF611A"   # red-orange: r x1, g x0.38, b x0.10


def _b_halation(p, w, h):
    sigma = max(2.0, w * p["radius"] / 1000)
    hi = f"clip((val-{int(p['threshold'])})*2.6,0,255)"
    r, g, b = "", "*0.38", "*0.10"
    if p.changed("color"):
        cr, cg, cb = _rgb(p["color"])
        r, g, b = f"*{_n(cr / 255, 3)}", f"*{_n(0.38 * cg / 97, 3)}", f"*{_n(0.10 * cb / 26, 3)}"
    return ("format=gbrp,split[hlb][hlh];"
            "[hlh]colorchannelmixer=rr=0.30:rg=0.59:rb=0.11:gr=0.30:gg=0.59:gb=0.11:br=0.30:bg=0.59:bb=0.11,"
            f"lutrgb=r='{hi}{r}':g='{hi}{g}':b='{hi}{b}',gblur=sigma={sigma:.2f}[hlg];"
            f"[hlb][hlg]blend=all_mode=screen:all_opacity={_n(p['amount'] / 100)},format=yuv420p")


# ---------------------------------------------------------------------------
# The schema: preset -> (params, builder). Managed presets: (managed_by, params).
# ---------------------------------------------------------------------------
E = EffectPreset
_GRADE_SH = [SHADOWS, HIGHLIGHTS]

PRESETS: dict[str, tuple[list[dict], Callable]] = {
    E.BLACK_AND_WHITE: ([CONTRAST(100), BRIGHTNESS(0),
                         _num("filter", "Colour filter", -100, 100, 0, help="Negative = blue filter (lighter skies), positive = red filter (darker skies).")], _b_bw),
    E.SEPIA: ([_color("color", "Tone colour", _SEPIA_TONE), CONTRAST(100), FADE], _b_sepia),
    E.WARM: ([_num("warmth", "Warmth", 0, 100, 50, css={"fn": "warmth", "k": 0.004}), TINT, SATURATION(108), CONTRAST(100)], _b_warm),
    E.COOL: ([_num("coolness", "Coolness", 0, 100, 50, css={"fn": "warmth", "k": -0.004}), TINT, SATURATION(96), CONTRAST(100)], _b_cool),
    E.VINTAGE: ([FADE, WARMTH, SATURATION(100), CONTRAST(100)], _b_tail_only(E.VINTAGE)),
    E.VIGNETTE: ([VIGNETTE(50), _num("x", "Centre left–right", 0, 100, 50, unit="%"),
                  _num("y", "Centre up–down", 0, 100, 50, unit="%")], _b_vignette),
    E.SOFT_GLOW: ([_num("radius", "Glow radius", 1, 40, 6, step=0.5, css={"fn": "blur", "k": 0.05}),
                   BRIGHTNESS(0), SATURATION(100)], _b_soft_glow),
    E.CINEMATIC: (_GRADE_SH + [CONTRAST(112), SATURATION(85)], _b_grades(E.CINEMATIC)),
    E.NOIR: ([CONTRAST(145), BRIGHTNESS(-3), VIGNETTE(50), GRAIN], _b_noir),
    E.SHARPEN: ([_num("amount", "Amount", 0, 3, 1.2, step=0.05, css={"fn": "contrast_k", "k": 0.05}),
                 _num("radius", "Radius", 3, 13, 5, step=2, unit="px"),
                 _num("chroma", "Colour sharpening", 0, 2, 0, step=0.05)], _b_sharpen),
    E.NEGATIVE: ([CONTRAST(100), SATURATION(100), _num("hue", "Hue shift", -180, 180, 0, unit="°", css={"fn": "hue", "k": 1})], _b_negative),
    E.FILM_GRAIN: ([_num("amount", "Grain amount", 0, 100, 24),
                    _num("color", "Colour grain", 0, 100, 100, unit="%", help="0 = monochrome grain."),
                    CONTRAST(100)], _b_film_grain),
    E.HIGH_CONTRAST: ([CONTRAST(135), SATURATION(112), BRIGHTNESS(0)],
                      _b_eq_core(E.HIGH_CONTRAST, (("contrast", "contrast", 0.01), ("saturation", "saturation", 0.01), ("brightness", "brightness", 0.01)))),
    E.FADED: ([CONTRAST(80), _num("lift", "Lift", -10, 30, 7, css={"fn": "brightness", "k": 0.01}), SATURATION(80), WARMTH],
              _b_eq_core(E.FADED, (("contrast", "contrast", 0.01), ("lift", "brightness", 0.01), ("saturation", "saturation", 0.01)))),
    E.DREAM: ([_num("softness", "Softness", 0.1, 10, 1.5, step=0.1, css={"fn": "blur", "k": 0.3}),
               BRIGHTNESS(4), SATURATION(80), WARMTH], _b_dream),
    E.VHS: ([_num("bleed", "Colour bleed", 0, 20, 5, unit="px"), _num("noise", "Tape noise", 0, 50, 10),
             _num("scanlines", "Scanlines", 0, 80, 22, unit="%"), _num("tracking", "Tracking band", 0, 60, 12, unit="%")], _b_vhs),
    E.GLOW: ([_num("radius", "Glow radius", 2, 60, 14), _num("amount", "Glow amount", 0, 100, 55, unit="%", css={"fn": "brightness", "k": 0.002}),
              BRIGHTNESS(4, -20, 30), _num("contrast", "Glow threshold", 50, 200, 110, unit="%", help="Higher = only bright areas glow.")], _b_glow),
    E.DUOTONE: ([_color("shadow", "Shadow colour", _DUO_SHADOW), _color("highlight", "Highlight colour", _DUO_HIGHLIGHT), CONTRAST(100)], _b_duotone),
    E.NEWSPRINT: ([CONTRAST(155), _num("grain", "Print grain", 0, 60, 16), _color("paper", "Paper colour", _PAPER),
                   _num("sharpen", "Sharpen", 0, 200, 60, unit="%")], _b_newsprint),
    E.OLD_FILM: ([SATURATION(75), CONTRAST(105), _num("grain", "Grain", 0, 60, 22), VIGNETTE(50)], _b_old_film),
    E.TEAL_AMBER: (_GRADE_SH + [CONTRAST(108), SATURATION(112)], _b_grades(E.TEAL_AMBER)),
    E.PASTEL: ([CONTRAST(90), BRIGHTNESS(6), SATURATION(78), TONE], _b_pastel),
    E.BLEACH_BYPASS: ([_num("color", "Colour retained", 0, 100, 48, unit="%", css={"fn": "saturate"}), CONTRAST(132),
                       BRIGHTNESS(-1.5, step=0.5), TONE], _b_bleach),
    E.GOLDEN_HOUR: (_GRADE_SH + [_num("gamma", "Gamma", 50, 200, 104, unit="%", css={"fn": "brightness", "k": 0.01}), SATURATION(108)],
                    _b_grades(E.GOLDEN_HOUR, ("gamma", "saturation"))),
    E.ARCTIC: (_GRADE_SH + [CONTRAST(104), SATURATION(92)], _b_grades(E.ARCTIC)),
    E.PORTRA: ([TONE, SATURATION(96), CONTRAST(100), FADE], _b_portra),
    E.MATTE: ([_num("lift", "Black lift", 0, 30, 8, unit="%", css={"fn": "brightness", "k": 0.005}),
               _num("white", "White point", 70, 100, 94, unit="%"), CONTRAST(94), SATURATION(88)], _b_matte),
    E.POP_COLOR: ([SATURATION(134), CONTRAST(112), _num("gamma", "Gamma", 50, 200, 102, unit="%", css={"fn": "brightness", "k": 0.01}),
                   _num("sharpen", "Sharpen", 0, 200, 45, unit="%")], _b_pop),
    E.TEAL_SHADOW: (_GRADE_SH + [CONTRAST(106), SATURATION(102)], _b_grades(E.TEAL_SHADOW)),
    E.ROSE_GLOW: (_GRADE_SH + [BRIGHTNESS(2.5, step=0.5), _num("softness", "Softness", 0, 3, 0.35, step=0.05, css={"fn": "blur", "k": 0.3})], _b_rose),
    E.MONO_BLUE: ([TONE, CONTRAST(108), BRIGHTNESS(0)], _b_mono_blue),
    E.MOTION_TRAIL: ([_num("frames", "Trail length", 2, 10, 4, unit=" frames"),
                      _num("trail", "Trail strength", 25, 300, 100, unit="%", help="Higher = older frames stay visible longer.")], _b_motion_trail),
    E.HALATION: ([_num("threshold", "Threshold", 100, 240, 165, help="Brightness above which highlights glow (0-255)."),
                  _num("radius", "Radius", 2, 40, 12, help="Glow size, in thousandths of the frame width."),
                  _color("color", "Glow colour", _HALATION),
                  _num("amount", "Glow amount", 0, 100, 90, unit="%")], _b_halation),
    E.PRINT_2383: ([CONTRAST(104), SATURATION(90), FADE, WARMTH], None),  # builder set below
    E.TUNGSTEN_NIGHT: ([CONTRAST(106), SATURATION(85), FADE, WARMTH], None),
    E.CROSS_PROCESS: ([CONTRAST(106), SATURATION(118), FADE, WARMTH], None),
}


def _b_curves_grade(preset):
    def build(p, w, h):
        c = _upd(_base(preset), p, "contrast", "eq", "contrast")
        c = _upd(c, p, "saturation", "eq", "saturation")
        return _tail(c, p)
    return build


for _k in (E.PRINT_2383, E.TUNGSTEN_NIGHT, E.CROSS_PROCESS):
    PRESETS[_k] = (PRESETS[_k][0], _b_curves_grade(_k))
# vintage uses appended tweaks only (curves preset has no numbers to rewrite)
PRESETS[E.VINTAGE] = (PRESETS[E.VINTAGE][0], _b_tail_only(E.VINTAGE, ("contrast", "saturation")))

# Presets whose settings already live in their own look_json key + panel.
MANAGED: dict[str, tuple[str, list[dict]]] = {
    E.GLITCH: ("glitch", [_num("speed", "Speed", 0.25, 4, 1, step=0.25)]),
    E.FOCUS_BLUR: ("focus", [_num("size", "Sharp area", 5, 95, 40), _num("blur", "Blur", 1, 100, 50),
                             _num("x", "Centre left–right", 0, 100, 50), _num("y", "Centre up–down", 0, 100, 50)]),
    E.TILT_SHIFT: ("focus", [_num("size", "Sharp area", 5, 95, 40), _num("blur", "Blur", 1, 100, 50),
                             _num("y", "Centre up–down", 0, 100, 50)]),
    E.MOSAIC: ("mosaic", [_num("block", "Block size", 2, 120, 24, unit="px")]),
    E.CHROMATIC_SPLIT: ("rgbsplit", [_num("amount", "Split amount", 1, 100, 25, unit="%")]),
}


def defaults_for(preset: str) -> dict:
    entry = PRESETS.get(preset)
    return {q["name"]: q["default"] for q in entry[0]} if entry else {}


def schema() -> dict:
    """JSON schema served at GET /api/effects/schema."""
    out = {}
    for e in EffectPreset:
        if e == EffectPreset.ORIGINAL:
            continue
        if e in PRESETS:
            out[e.value] = {"params": PRESETS[e][0]}
        elif e in MANAGED:
            out[e.value] = {"managed_by": MANAGED[e][0], "params": MANAGED[e][1]}
    return {"version": 1, "look_key": "fx_params", "presets": out}


# ---------------------------------------------------------------------------
# Validation (registered as scene_fx.CLEANERS["fx_params"])
# ---------------------------------------------------------------------------
def clean_fx_params(raw) -> dict:
    if not isinstance(raw, dict):
        raise EffectParamsError("Effect settings must be an object of {effect: {setting: value}}.")
    out = {}
    for preset, vals in raw.items():
        if preset in MANAGED:
            raise EffectParamsError(f"{preset} settings are stored under look.{MANAGED[preset][0]}, not fx_params.")
        if preset not in PRESETS:
            raise EffectParamsError(f"Unknown effect '{preset}' in effect settings.")
        if vals is None or vals == {}:
            continue
        if not isinstance(vals, dict):
            raise EffectParamsError(f"Settings for {preset} must be an object.")
        spec = {q["name"]: q for q in PRESETS[preset][0]}
        unknown = set(vals) - set(spec)
        if unknown:
            raise EffectParamsError(f"Unknown setting(s) for {preset}: {', '.join(sorted(unknown))}. "
                                    f"Allowed: {', '.join(spec)}.")
        clean = {}
        for k, v in vals.items():
            q = spec[k]
            if q["kind"] == "color":
                if not isinstance(v, str) or not _HEX.fullmatch(v):
                    raise EffectParamsError(f"{preset} {k} must look like #RRGGBB.")
                clean[k] = v.upper()
            else:
                if isinstance(v, bool) or not isinstance(v, (int, float)) or not q["min"] <= v <= q["max"]:
                    raise EffectParamsError(f"{preset} {k} must be between {q['min']} and {q['max']}.")
                v = round(float(v), 4)
                clean[k] = int(v) if v == int(v) else v
        out[preset] = clean
    return out


def effect_filter(preset: str, fx_params: dict | None, width: int = 1920, height: int = 1080) -> str | None:
    """Filter fragment for a preset with its fx_params (defaults when unset).
    None for presets this module does not build (original / managed)."""
    entry = PRESETS.get(preset)
    if not entry:
        return None
    values = (fx_params or {}).get(str(getattr(preset, 'value', preset))) or {}
    if not isinstance(values, dict):
        values = {}
    p = _P({k: v for k, v in values.items() if k in defaults_for(preset)}, defaults_for(preset))
    return entry[1](p, width, height)
