"""Split-screen and collage layouts: several of a scene's shots on screen at
once (then-and-now comparisons, multiple angles).

look.layout = {"type": "split2" | "split2v" | "split3" | "grid4", "gap": 0-40 px at 1080p, "bg": "#RRGGBB"}
Shots fill the panels in order; each panel gets the shot's own fit, crop,
motion and the scene's look, rendered at panel size.
"""
from __future__ import annotations

import re

LAYOUTS = {"split2": 2, "split2v": 2, "split3": 3, "grid4": 4}


class LayoutError(ValueError):
    pass


def clean_layout(d) -> dict:
    if not isinstance(d, dict) or set(d) - {"type", "gap", "bg"}:
        raise LayoutError("Layout settings may only contain type, gap and bg.")
    d = {"type": "split2", "gap": 8, "bg": "#000000", **d}
    if d["type"] not in LAYOUTS:
        raise LayoutError("Layout must be one of: " + ", ".join(LAYOUTS) + ".")
    if isinstance(d["gap"], bool) or not isinstance(d["gap"], (int, float)) or not 0 <= d["gap"] <= 40:
        raise LayoutError("Layout gap must be between 0 and 40.")
    if not isinstance(d["bg"], str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", d["bg"]):
        raise LayoutError("Layout background must look like #RRGGBB.")
    return {"type": d["type"], "gap": int(d["gap"]), "bg": d["bg"].upper()}


def panels(layout: dict, w: int, h: int) -> list[tuple[int, int, int, int]]:
    """(x, y, width, height) per panel, even sizes, separated by the gap."""
    g = int(round(layout["gap"] * h / 1080))
    ev = lambda v: max(2, int(v) // 2 * 2)
    t = layout["type"]
    if t == "split2":
        pw = ev((w - g) / 2); return [(0, 0, pw, h), (w - pw, 0, pw, h)]
    if t == "split2v":
        ph = ev((h - g) / 2); return [(0, 0, w, ph), (0, h - ph, w, ph)]
    if t == "split3":
        pw = ev((w - 2 * g) / 3); return [(0, 0, pw, h), ((w - pw) // 2 // 2 * 2, 0, pw, h), (w - pw, 0, pw, h)]
    pw, ph = ev((w - g) / 2), ev((h - g) / 2)
    return [(0, 0, pw, ph), (w - pw, 0, pw, ph), (0, h - ph, pw, ph), (w - pw, h - ph, pw, ph)]
