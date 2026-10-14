"""Scene-level effects, applied over the whole scene picture (all shots),
together with picture-in-picture overlays and before captions:

  redact regions (blur / pixelate) -> overlays -> spotlight -> light leaks
  -> lens flare -> wiggle (turbulent displace) -> camera shake

Keeping them at scene level means their timing is in scene time, even when a
scene has several images or clips. Settings live in scene.look_json:

  shake     {amount 0-100, speed 0-100, impact bool,
             preset custom|handheld|walk|run|impact}
  flare     {x, y (% of frame, flare source), color #RRGGBB, blend screen|add,
             amount 0-100, drift 0-100 (horizontal drift across the scene)}
  wiggle    {amount 0-100, speed 0-100, size 0-100}  (turbulent displace)
  spotlight {x, y, w, h (% of frame, centre and size), shape rect|ellipse,
             dim 0-100, feather 0-100, start_ms, end_ms|None}
  redact    [{x, y, w, h, mode blur|pixelate, strength 0-100, start_ms, end_ms|None}]  (max 6)
  leak      {amount 0-100, speed 0-100, color warm|cool|rainbow}
  tone      {shadow #RRGGBB, highlight #RRGGBB, amount 0-100, balance -100..100}
            (split toning; baked into the grade LUT, see grade.py)
  pulse     {amount 0-100, bpm 40-200}            beat zoom: quick punch-in on every beat
  flash     {amount 0-100, mode intro|beats|both, bpm 40-200}   white flash in / strobe
  trails    {amount 0-100}                        motion trails (frame echo)
  mirror    {mode left|right|top|bottom|quad}     mirror / kaleidoscope
"""
from __future__ import annotations

import hashlib
import math
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


SHAKE_PRESETS = ("custom", "handheld", "walk", "run", "impact")


def clean_shake(d) -> dict:
    d = _only({"amount": 40, "speed": 50, "impact": False, "preset": "custom", **(d or {})}, {"amount", "speed", "impact", "preset"}, "Camera shake")
    if not isinstance(d["impact"], bool):
        raise SceneFxError("Camera shake impact must be true or false.")
    if d["preset"] not in SHAKE_PRESETS:
        raise SceneFxError("Camera shake preset must be one of: " + ", ".join(SHAKE_PRESETS) + ".")
    out = {"amount": int(_num(d, "amount", 0, 100, "Camera shake")), "speed": int(_num(d, "speed", 0, 100, "Camera shake")), "impact": d["impact"]}
    if d["preset"] != "custom":
        out["preset"] = d["preset"]
    return out


FLARE_DEFAULT = {"x": 78, "y": 22, "color": "#FFB060", "blend": "screen", "amount": 70, "drift": 0}


def clean_flare(d) -> dict:
    d = _only({**FLARE_DEFAULT, **(d or {})}, set(FLARE_DEFAULT), "Lens flare")
    if not isinstance(d["color"], str) or not _HEX.fullmatch(d["color"]):
        raise SceneFxError("Lens flare colour must look like #RRGGBB.")
    if d["blend"] not in ("screen", "add"):
        raise SceneFxError("Lens flare blend must be screen or add.")
    return {"x": round(float(_num(d, "x", 0, 100, "Lens flare")), 1), "y": round(float(_num(d, "y", 0, 100, "Lens flare")), 1),
            "color": d["color"].upper(), "blend": d["blend"], "amount": int(_num(d, "amount", 0, 100, "Lens flare")),
            "drift": int(_num(d, "drift", 0, 100, "Lens flare"))}


def clean_wiggle(d) -> dict:
    d = _only({"amount": 40, "speed": 40, "size": 50, **(d or {})}, {"amount", "speed", "size"}, "Wiggle")
    return {k: int(_num(d, k, 0, 100, "Wiggle")) for k in ("amount", "speed", "size")}


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


def clean_stabilize(d) -> dict:
    d = _only({"strength": 50, **(d or {})}, {"strength"}, "Stabilization")
    return {"strength": int(_num(d, "strength", 1, 100, "Stabilization"))}


def clean_finish(d):
    d = _only({"amount": 50, **(d or {})}, {"amount"}, "Finishing effect")
    return {"amount": int(_num(d, "amount", 0, 100, "Finishing effect"))}


# ---- Trending (0.9.4-beta.7): beat zoom, flash, motion trails, mirror -------------
MIRROR_MODES = ("left", "right", "top", "bottom", "quad")
FLASH_MODES = ("intro", "beats", "both")


def clean_pulse(d) -> dict:
    d = _only({"amount": 45, "bpm": 120, **(d or {})}, {"amount", "bpm"}, "Beat zoom")
    return {"amount": int(_num(d, "amount", 0, 100, "Beat zoom")), "bpm": int(_num(d, "bpm", 40, 200, "Beat zoom"))}


def clean_flash(d) -> dict:
    d = _only({"amount": 70, "mode": "intro", "bpm": 120, **(d or {})}, {"amount", "mode", "bpm"}, "Flash")
    if d["mode"] not in FLASH_MODES:
        raise SceneFxError("Flash mode must be one of: " + ", ".join(FLASH_MODES) + ".")
    return {"amount": int(_num(d, "amount", 0, 100, "Flash")), "mode": d["mode"], "bpm": int(_num(d, "bpm", 40, 200, "Flash"))}


def clean_trails(d) -> dict:
    d = _only({"amount": 50, **(d or {})}, {"amount"}, "Motion trails")
    return {"amount": int(_num(d, "amount", 0, 100, "Motion trails"))}


def clean_mirror(d) -> dict:
    d = _only({"mode": "left", **(d or {})}, {"mode"}, "Mirror")
    if d["mode"] not in MIRROR_MODES:
        raise SceneFxError("Mirror mode must be one of: " + ", ".join(MIRROR_MODES) + ".")
    return {"mode": d["mode"]}


def pulse_graph(base: str, pl: dict, w: int, h: int, fps: int) -> tuple[list[str], str]:
    """Beat zoom: on every beat the picture punches in and eases back (zoompan, per frame)."""
    a, bps = pl["amount"] / 100, pl["bpm"] / 60
    z = f"1+{0.14 * a:.4f}*exp(-mod(it*{bps:.4f},1)*7)"
    return [f"[{base}]zoompan=z='{z}':d=1:s={w}x{h}:fps={fps}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'[pulse]"], "pulse"


def flash_graph(base: str, fl: dict) -> tuple[list[str], str]:
    """White flash: brightness jumps up and fades out, at the start and/or on every beat."""
    a, bps = fl["amount"] / 100, fl["bpm"] / 60
    terms = []
    if fl["mode"] in ("intro", "both"):
        terms.append(f"{0.85 * a:.3f}*exp(-t*7)")
    if fl["mode"] in ("beats", "both"):
        terms.append(f"{0.45 * a:.3f}*exp(-mod(t*{bps:.4f},1)*12)")
    bright = "min(1,(" + "+".join(terms) + "))"
    return [f"[{base}]eq=brightness='{bright}':eval=frame,format=yuv420p[flash]"], "flash"


def trails_graph(base: str, tr: dict) -> tuple[list[str], str]:
    """Motion trails: each frame keeps fading copies of the previous frames (tmix)."""
    n = 2 + round(tr["amount"] / 100 * 6)
    weights = " ".join(f"{0.62 ** i:.3f}" for i in range(n))
    return [f"[{base}]tmix=frames={n}:weights='{weights}'[trails]"], "trails"


def mirror_graph(base: str, mr: dict, w: int, h: int) -> tuple[list[str], str]:
    """Mirror one half of the picture onto the other (or a quarter into all four corners)."""
    hw, hh = (w // 2) // 2 * 2, (h // 2) // 2 * 2   # even halves: yuv420 chroma rows must line up when flipped
    m = mr["mode"]
    if m in ("left", "right"):
        src = f"crop={hw}:{h}:{0 if m == 'left' else w - hw}:0"
        g = [f"[{base}]{src},split[mr1][mr2]", f"[mr2]hflip[mrf]",
             f"[mr1][mrf]hstack" if m == "left" else f"[mrf][mr1]hstack"]
        g[-1] += f",scale={w}:{h}[mirror]"
        return g, "mirror"
    if m in ("top", "bottom"):
        src = f"crop={w}:{hh}:0:{0 if m == 'top' else h - hh}"
        g = [f"[{base}]{src},split[mr1][mr2]", f"[mr2]vflip[mrf]",
             (f"[mr1][mrf]vstack" if m == "top" else f"[mrf][mr1]vstack") + f",scale={w}:{h}[mirror]"]
        return g, "mirror"
    g = [f"[{base}]crop={hw}:{hh}:0:0,split[q1][q2]", "[q2]hflip[q3]", "[q1][q3]hstack,split[q4][q5]", "[q5]vflip[q6]",
         f"[q4][q6]vstack,scale={w}:{h}[mirror]"]
    return g, "mirror"


# ---- Trending, part 2 (0.9.4-beta.9): CapCut 2026 trend list as per-part effects -------
# RGB split, cinematic fade & zoom, intro move (swipe / spin / zoom), before & after, speed blur.
SPLIT_MODES = ("beats", "steady")
CINE_ZOOMS = ("in", "out", "none")
CINE_FADES = ("in", "both", "none")
INTRO_STYLES = ("swipe_left", "swipe_right", "swipe_up", "spin", "zoom")
BEFORE_STYLES = ("bw", "faded", "dark")
BLUR_DIRS = ("horizontal", "vertical")
BLUR_WHEN = ("whole", "start")


def _choice(d: dict, key: str, options: tuple, name: str) -> str:
    if d[key] not in options:
        raise SceneFxError(f"{name} {key} must be one of: " + ", ".join(options) + ".")
    return d[key]


def clean_colorsplit(d) -> dict:
    d = _only({"amount": 50, "mode": "beats", "bpm": 120, **(d or {})}, {"amount", "mode", "bpm"}, "RGB split")
    return {"amount": int(_num(d, "amount", 0, 100, "RGB split")), "mode": _choice(d, "mode", SPLIT_MODES, "RGB split"),
            "bpm": int(_num(d, "bpm", 40, 200, "RGB split"))}


def clean_cineopen(d) -> dict:
    d = _only({"amount": 50, "zoom": "in", "fade": "in", "seconds": 1.0, **(d or {})}, {"amount", "zoom", "fade", "seconds"}, "Cinematic fade & zoom")
    return {"amount": int(_num(d, "amount", 0, 100, "Cinematic fade & zoom")), "zoom": _choice(d, "zoom", CINE_ZOOMS, "Cinematic fade & zoom"),
            "fade": _choice(d, "fade", CINE_FADES, "Cinematic fade & zoom"), "seconds": round(float(_num(d, "seconds", 0.2, 3, "Cinematic fade & zoom")), 2)}


def clean_intro(d) -> dict:
    d = _only({"style": "swipe_left", "seconds": 0.5, **(d or {})}, {"style", "seconds"}, "Intro move")
    return {"style": _choice(d, "style", INTRO_STYLES, "Intro move"), "seconds": round(float(_num(d, "seconds", 0.2, 1.5, "Intro move")), 2)}


def clean_beforeafter(d) -> dict:
    d = _only({"before": "bw", "start": 25, "seconds": 1.5, **(d or {})}, {"before", "start", "seconds"}, "Before & after")
    return {"before": _choice(d, "before", BEFORE_STYLES, "Before & after"), "start": int(_num(d, "start", 0, 90, "Before & after")),
            "seconds": round(float(_num(d, "seconds", 0.3, 5, "Before & after")), 2)}


def clean_speedblur(d) -> dict:
    d = _only({"amount": 50, "direction": "horizontal", "when": "whole", **(d or {})}, {"amount", "direction", "when"}, "Speed blur")
    return {"amount": int(_num(d, "amount", 0, 100, "Speed blur")), "direction": _choice(d, "direction", BLUR_DIRS, "Speed blur"),
            "when": _choice(d, "when", BLUR_WHEN, "Speed blur")}


def _ease(x: str) -> str:
    c = f"clip({x},0,1)"
    return f"({c}*{c}*(3-2*{c}))"


def _split_head(base: str, tag: str, seconds: float, fps: int) -> list[str]:
    """[base] -> [{tag}h] (first `seconds`) and [{tag}r] (the rest), both at a fixed frame rate."""
    k = max(1, round(seconds * fps))    # split by frame number: time-based trims drift by a frame after other filters
    return [f"[{base}]format=yuv420p,setsar=1,setpts=N/({fps}*TB),split[{tag}a][{tag}b]",
            f"[{tag}a]trim=end_frame={k},setpts=PTS-STARTPTS[{tag}h]",
            f"[{tag}b]trim=start_frame={k},setpts=PTS-STARTPTS[{tag}r]"]


def colorsplit_graph(base: str, cs: dict, w: int, h: int) -> tuple[list[str], str]:
    """RGB split: the red and blue layers slide apart (on every beat, or steadily), built
    from per-frame crops of padded colour layers added back together (no per-pixel expressions)."""
    m = max(2, round(w * 0.04 * cs["amount"] / 100))           # largest shift, px (4 % of the width at 100)
    bps = cs["bpm"] / 60
    k = f"exp(-mod(t*{bps:.4f},1)*8)" if cs["mode"] == "beats" else "1"
    if cs["mode"] == "steady":    # a fixed shift: FFmpeg's own (fast) channel shift
        return [f"[{base}]rgbashift=rh=-{m}:bh={m}:edge=smear,format=yuv420p[colorsplit]"], "colorsplit"
    pad = f"pad={w + 2 * m}:{h}:{m}:0,fillborders=left={m}:right={m}:mode=smear"
    return [f"[{base}]format=gbrp,split=3[csr][csg][csb]",
            f"[csr]lutrgb=g=0:b=0,{pad},crop={w}:{h}:x='{m}-{m}*{k}':y=0[csr2]",
            f"[csb]lutrgb=r=0:g=0,{pad},crop={w}:{h}:x='{m}+{m}*{k}':y=0[csb2]",
            "[csg]lutrgb=r=0:b=0[csg2]",
            "[csr2][csg2]blend=all_mode=addition[csrg]",
            "[csrg][csb2]blend=all_mode=addition,format=yuv420p[colorsplit]"], "colorsplit"


def cineopen_graph(base: str, co: dict, w: int, h: int, fps: int, dur: float) -> tuple[list[str], str]:
    """Cinematic fade & zoom: a slow push in (or pull out) across the part, fading in from
    black at the start (and out at the end)."""
    g, filt = [], []
    span = max(dur, 0.1)
    z = 0.15 * co["amount"] / 100
    if co["zoom"] != "none" and z > 0:
        p = _ease(f"it/{span:.4f}")
        zexpr = f"1+{z:.4f}*{p}" if co["zoom"] == "in" else f"1+{z:.4f}*(1-{p})"
        filt.append(f"zoompan=z='{zexpr}':d=1:s={w}x{h}:fps={fps}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'")
    fd = min(co["seconds"], span / 2)
    if co["fade"] in ("in", "both"):
        filt.append(f"fade=t=in:st=0:d={fd:.3f}")
    if co["fade"] == "both":
        filt.append(f"fade=t=out:st={max(0, span - fd):.3f}:d={fd:.3f}")
    if not filt:
        filt.append("null")
    g.append(f"[{base}]{','.join(filt)},format=yuv420p[cineopen]")
    return g, "cineopen"


def intro_graph(base: str, it: dict, w: int, h: int, fps: int, dur: float) -> tuple[list[str], str]:
    """Intro move: the picture swipes, spins or zooms into place over its first moments, with
    motion blur. Only the opening is processed; the rest of the part passes through unchanged."""
    d = min(it["seconds"], max(dur - 1 / fps, 1 / fps))
    st = it["style"]
    g = _split_head(base, "in", d, fps)
    pos = _ease(f"t/{d:.4f}")
    if st in ("swipe_left", "swipe_right"):
        # the picture beside itself, scrolled into place (no black edges), 6 sub-frames averaged
        x = f"(iw-ow)*(1-{pos})" if st == "swipe_left" else f"(iw-ow)*{pos}"
        g.append(f"[inh]split[inh1][inh2];[inh1][inh2]hstack,fps={fps * 6},crop=w={w}:h={h}:x='{x}':y=0,tmix=frames=6,fps={fps}[inm]")
    elif st == "swipe_up":
        y = f"(ih-oh)*(1-{pos})"
        g.append(f"[inh]split[inh1][inh2];[inh1][inh2]vstack,fps={fps * 6},crop=w={w}:h={h}:x=0:y='{y}',tmix=frames=6,fps={fps}[inm]")
    elif st == "spin":
        ang = f"-PI/2*(1-{_ease(f'it/{d:.4f}')})"
        r = max(w, h) / min(w, h)
        zoom = f"(abs(cos({ang}))+{r:.4f}*abs(sin({ang})))*1.02+0.3*(1-{_ease(f'it/{d:.4f}')})"
        rot = ang.replace("it/", "t/")
        g.append(f"[inh]rotate=a='{rot}':c=black,zoompan=z='{zoom}':d=1:s={w}x{h}:fps={fps}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',tmix=frames=2[inm]")
    else:   # zoom: lands from a punched-in close-up
        g.append(f"[inh]zoompan=z='1+1.5*pow(1-{_ease(f'it/{d:.4f}')},2)':d=1:s={w}x{h}:fps={fps}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',tmix=frames=3[inm]")
    frames = max(1, round(d * fps))
    g.append(f"[inm]format=yuv420p,setsar=1,tpad=stop_mode=clone:stop={frames},trim=end_frame={frames},setpts=PTS-STARTPTS[inm2]")
    g.append("[inm2][inr]concat=n=2:v=1:a=0,format=yuv420p[intro]")
    return g, "intro"


def beforeafter_graph(base: str, ba: dict, w: int, h: int, fps: int, dur: float) -> tuple[list[str], str]:
    """Before & after: the part starts as a "before" version (black & white, faded or dark);
    a white line sweeps left to right revealing the real picture behind it."""
    before = {"bw": "hue=s=0", "faded": "eq=saturation=0.35:contrast=0.75:brightness=0.05",
              "dark": "eq=brightness=-0.18:saturation=0.6:contrast=0.9"}[ba["before"]]
    start = dur * ba["start"] / 100
    length = max(0.1, min(ba["seconds"], max(dur - start, 0.1)))
    line = max(4, w // 240)
    p = f"clip((t-{start:.4f})/{length:.4f},0,1)"
    x = f"W*{p}"   # steady sweep, like dragging a slider
    return [f"[{base}]format=yuv420p,split[baa][bab]",
            f"[bab]{before},format=yuva420p[bab2]",
            # mask: opaque everywhere, a transparent block slides in from the left over the sweep
            f"color=c=white:s={w}x{h}:r={fps}:d={dur + 1:.3f},format=gray[bam0]",
            f"color=c=black:s={w}x{h}:r={fps}:d={dur + 1:.3f},format=gray[bam1]",
            f"[bam0][bam1]overlay=x='{x}-W':y=0:shortest=1,format=gray,lut=y='if(gt(val,127),255,0)'[bamask]",   # full 0/255: video-range white (235) let colour through
            "[bab2][bamask]alphamerge[babm]",
            f"[baa][babm]overlay=0:0:shortest=1,format=yuv420p[baov]",
            f"color=c=white:s={line}x{h}:r={fps}:d={dur + 1:.3f},format=yuv420p[baline]",
            f"[baov][baline]overlay=x='if(between(t,{start:.4f},{start + length:.4f}),{x}-{line // 2},-{line * 4})':y=0:shortest=1,format=yuv420p[beforeafter]"], "beforeafter"


def speedblur_graph(base: str, sb: dict, w: int, h: int, fps: int, dur: float) -> tuple[list[str], str]:
    """Speed blur: directional motion blur (the "velocity" look), on the whole part or as a
    whoosh over its first half second that clears up."""
    size = max(1, round(min(w, h) * 0.08 * sb["amount"] / 100))
    blur = f"avgblur=sizeX={size}:sizeY=1" if sb["direction"] == "horizontal" else f"avgblur=sizeX=1:sizeY={size}"
    if sb["when"] == "whole":
        return [f"[{base}]{blur},format=yuv420p[speedblur]"], "speedblur"
    d = min(0.5, max(dur - 1 / fps, 1 / fps))
    g = _split_head(base, "sb", d, fps)
    # strong at the start, fading to sharp: a blurred copy faded out over the sharp picture
    g += [f"[sbh]split[sbh1][sbh2]",
          f"[sbh2]{blur},format=yuva420p,fade=t=out:st=0:d={d:.3f}:alpha=1[sbhb]",
          f"[sbh1][sbhb]overlay=0:0,format=yuv420p[sbm]",
          "[sbm][sbr]concat=n=2:v=1:a=0,format=yuv420p[speedblur]"]
    return g, "speedblur"


CLEANERS = {"vignette": clean_finish, "letterbox": clean_finish, "sharpen": clean_finish,"stabilize": clean_stabilize, "wheels": clean_wheels, "shake": clean_shake, "spotlight": clean_spotlight, "redact": clean_redact, "leak": clean_leak, "tone": clean_tone,
            "flare": clean_flare, "wiggle": clean_wiggle, "pulse": clean_pulse, "flash": clean_flash, "trails": clean_trails,
            "mirror": clean_mirror, "colorsplit": clean_colorsplit, "cineopen": clean_cineopen, "intro": clean_intro,
            "beforeafter": clean_beforeafter, "speedblur": clean_speedblur}


def has_scene_fx(look: dict | None) -> bool:
    look = look or {}
    return bool(look.get("shake") or look.get("spotlight") or look.get("redact") or look.get("leak") or look.get("route") or look.get("annotations")
                or look.get("flare") or look.get("wiggle") or look.get("vignette") or look.get("letterbox") or look.get("sharpen")
                or look.get("pulse") or look.get("flash") or look.get("trails") or look.get("mirror")
                or look.get("colorsplit") or look.get("cineopen") or look.get("intro") or look.get("beforeafter") or look.get("speedblur"))


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


def flare_png(fl: dict, w: int, h: int, cache: Path) -> tuple[str, int]:
    """Procedural lens flare on black (for screen/add blending): hot core,
    soft halo, anamorphic streak, a thin ring and ghosts along the line from
    the source through the frame centre. When drifting, the canvas is wider
    than the frame by the drift distance on each side. Returns (png, drift px)."""
    from PIL import Image
    drift = int(round(fl["drift"] / 100 * 0.25 * w))
    key = hashlib.sha256(f"v1|{w}x{h}|{fl['x']}|{fl['y']}|{fl['color']}|{drift}".encode()).hexdigest()[:20]
    cache.mkdir(parents=True, exist_ok=True)
    out = cache / f"flare_{key}.png"
    if out.exists():
        return str(out), drift
    cw = w + 2 * drift
    yy, xx = np.mgrid[0:h, 0:cw].astype(np.float32)
    sx, sy = drift + fl["x"] / 100 * w, fl["y"] / 100 * h
    cx, cy = drift + w / 2, h / 2
    tint = np.array([int(fl["color"][i:i + 2], 16) for i in (1, 3, 5)], np.float32) / 255
    u = w / 1920
    r2 = (xx - sx) ** 2 + (yy - sy) ** 2
    img = np.zeros((h, cw, 3), np.float32)
    core = np.exp(-r2 / (2 * (28 * u) ** 2))
    halo = np.exp(-r2 / (2 * (230 * u) ** 2)) * 0.45
    streak = np.exp(-((yy - sy) ** 2) / (2 * (5 * u) ** 2)) * np.exp(-np.abs(xx - sx) / (620 * u)) * 0.8
    ring = np.exp(-((np.sqrt(r2) - 150 * u) ** 2) / (2 * (5 * u) ** 2)) * 0.18
    img += core[..., None] * (0.65 + 0.35 * tint)          # nearly white hot centre
    img += (halo + streak + ring)[..., None] * tint
    for k, rad, a in ((0.45, 40, 0.20), (1.25, 22, 0.28), (1.6, 70, 0.12), (2.1, 110, 0.10)):
        gx, gy = sx + k * (cx - sx), sy + k * (cy - sy)
        d = np.sqrt((xx - gx) ** 2 + (yy - gy) ** 2)
        disc = np.clip((rad * u - d) / (rad * u * 0.35), 0, 1) * a
        hue = np.roll(tint, int(k * 2)) * 0.6 + tint * 0.4     # ghosts shift colour a little
        img += disc[..., None] * hue
    Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8), "RGB").save(out)
    return str(out), drift


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
    impact zoom that punches in at the start and settles.

    Presets change the character of the motion; amount and speed still scale it:
      handheld  slow, soft drift (subtle)
      walk      sway plus a vertical bob on each footstep (~1.8 steps/s)
      run       faster, bigger footstep bob plus high-frequency jitter
      impact    violent shake that decays over ~1 s, with the zoom punch"""
    a = sk["amount"] / 100
    spd = 0.4 + 2.2 * sk["speed"] / 100
    preset = sk.get("preset", "custom")
    ax, ay = w * 0.012 * a, h * 0.016 * a
    impact = "+0.14*exp(-it*5)" if sk["impact"] or preset == "impact" else ""
    if preset == "handheld":
        ax, ay, spd = ax * 0.6, ay * 0.6, spd * 0.35
    dx = f"{ax:.2f}*(sin(it*{7.3 * spd:.3f})+0.6*sin(it*{17.9 * spd:.3f}+1.3)+0.3*sin(it*{31.1 * spd:.3f}))"
    dy = f"{ay:.2f}*(sin(it*{5.9 * spd:.3f}+0.7)+0.6*sin(it*{13.7 * spd:.3f}+2.1)+0.3*sin(it*{27.3 * spd:.3f}))"
    peak_x, peak_y = ax * 1.9, ay * 1.9
    if preset in ("walk", "run"):
        step = (1.8 if preset == "walk" else 2.9) * (0.5 + spd / 2.6)       # footsteps per second
        big = 1.0 if preset == "walk" else 1.9
        bx, by = ax * 0.5 * big, ay * 1.6 * big
        dx = f"{bx:.2f}*sin(it*{math.pi * step:.3f})+{ax * 0.25:.2f}*sin(it*{11.3 * spd:.3f}+0.4)"
        dy = f"{by:.2f}*(abs(sin(it*{math.pi * step:.3f}))-0.64)+{ay * 0.25:.2f}*sin(it*{9.1 * spd:.3f}+1.1)"
        if preset == "run":
            dx += f"+{ax * 0.35:.2f}*sin(it*{41.0 * spd:.3f})"
            dy += f"+{ay * 0.35:.2f}*sin(it*{37.0 * spd:.3f}+0.5)"
        peak_x, peak_y = bx + ax * 0.6, by * 0.64 + ay * 0.6
    elif preset == "impact":
        env = "(0.25+2.6*exp(-it*3.2))"
        dx = f"{env}*{ax:.2f}*(sin(it*{23.0 * spd:.3f})+0.5*sin(it*{41.0 * spd:.3f}+1.3))"
        dy = f"{env}*{ay:.2f}*(sin(it*{19.0 * spd:.3f}+0.7)+0.5*sin(it*{37.0 * spd:.3f}+2.1))"
        peak_x, peak_y = ax * 2.85 * 1.5, ay * 2.85 * 1.5
    # zoom in just enough that the moving window never leaves the picture
    margin = max(1.04 + 0.06 * a, 1 + 2.1 * max(peak_x / w, peak_y / h))
    graph = [f"[{base}]zoompan=z='{margin:.3f}{impact}':d=1:s={w}x{h}:fps={fps}:"
             f"x='iw/2-(iw/zoom/2)+({dx})/zoom':y='ih/2-(ih/zoom/2)+({dy})/zoom'[shk]"]
    return graph, "shk"


def flare_graph(base: str, fl: dict, png: str, drift: int, w: int, h: int, fps: int, dur: float) -> tuple[list[str], str]:
    """Blend the flare over the picture (FFmpeg blend screen / addition).
    With drift, a frame-sized window slides across the wider flare canvas so
    the flare travels horizontally over the scene."""
    from app.render.ffmpeg_utils import escape_path_for_filter
    crop = f",crop={w}:{h}:x='{2 * drift}*clip(t/{max(dur, 0.1):.3f},0,1)':y=0" if drift else ""
    mode = "addition" if fl["blend"] == "add" else "screen"
    graph = [f"movie='{escape_path_for_filter(png)}':loop=0,setpts=N/({fps}*TB){crop},format=gbrp[flc]",
             f"[{base}]format=gbrp[flb]",
             f"[flb][flc]blend=all_mode={mode}:all_opacity={fl['amount'] / 100:.3f}:shortest=1,format=yuv420p[flare]"]
    return graph, "flare"


def wiggle_graph(base: str, wg: dict, w: int, h: int, fps: int, dur: float) -> tuple[list[str], str]:
    """Turbulent displace: two smooth animated noise fields (sums of moving
    sine waves, computed on a small grid with geq and scaled up) drive
    FFmpeg's displace filter. Map value 128 = no shift; value-128 = pixels."""
    amp = wg["amount"] / 100 * 0.02 * w                      # max shift in px
    omega = 2 * math.pi * (0.15 + 1.6 * wg["speed"] / 100)
    waves = 1.5 + 5.0 * (1 - wg["size"] / 100)               # waves across the frame (bigger size = broader)
    gw, gh = 96, 54
    kx, ky = 2 * math.pi * waves / gw, 2 * math.pi * waves / gw

    def field(p: float) -> str:
        return (f"128+{amp * 0.62:.2f}*sin(X*{kx:.4f}+T*{omega:.3f}+{p})*cos(Y*{ky * 0.8:.4f}-T*{omega * 0.7:.3f}+{p * 1.7:.2f})"
                f"+{amp * 0.38:.2f}*sin((X*0.6+Y)*{kx * 2.3:.4f}-T*{omega * 1.6:.3f}+{p * 0.5:.2f})")

    graph = []
    for lab, p in (("wgx", 0.0), ("wgy", 2.1)):
        e = field(p)
        graph.append(f"nullsrc=s={gw}x{gh}:r={fps}:d={dur + 1:.3f},format=gbrp,geq=r='{e}':g='{e}':b='{e}',"
                     f"scale={w}:{h}:flags=bicubic,format=gbrp[{lab}]")
    graph += [f"[{base}]format=gbrp[wgb]", "[wgb][wgx][wgy]displace=edge=smear,format=yuv420p[wig]"]
    return graph, "wig"


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
from app.render.annotations import clean_annotations  # noqa: E402

CLEANERS.update(layout=_wrap(clean_layout), route=_wrap(clean_route), parallax=_wrap(clean_parallax), annotations=_wrap(clean_annotations))


def _clean_countdown(raw):
    from app.render.countdowns import clean, CountdownError
    try:
        return clean(raw)
    except CountdownError as e:
        raise SceneFxError(str(e))


CLEANERS['countdown'] = _clean_countdown

from app.render.filters import clean_focus, clean_mosaic, clean_rgbsplit  # noqa: E402

CLEANERS.update(focus=_wrap(clean_focus), mosaic=_wrap(clean_mosaic), rgbsplit=_wrap(clean_rgbsplit))

from app.render.fx_stack import clean_fx_bypass, clean_fx_order  # noqa: E402  (effect stack order / bypass)

CLEANERS.update(fx_order=_wrap(clean_fx_order), fx_bypass=_wrap(clean_fx_bypass))

from app.render.effect_params import clean_fx_params  # noqa: E402  (per-effect settings, look.fx_params)

CLEANERS["fx_params"] = _wrap(clean_fx_params)
