"""Effect stack: a constrained, Fusion-style node order for the scene-level FX.

Not a node graph. The scene picture still runs through a fixed spine:

  redact -> overlays (below text) -> route -> annotations -> [STACK] -> captions

Redact must come first (it hides things before anything is drawn over them),
and overlays / route / annotations are graphics placed by the user on the
picture, so they stay where they are. The stack is the set of scene-level
"lens and camera" stages that only transform the picture they receive:

  spotlight, leak, flare, wiggle, shake            (default order)

look_json keys (both optional, validated by the cleaners below and registered
in scene_fx.CLEANERS):

  fx_order   list of stack ids, no duplicates. Listed ids run in that order;
             ids not listed run afterwards in the default order. Missing key
             = the default order, so existing projects render identically.
  fx_bypass  list of stack ids rendered as if absent; their settings are kept.

Order matters: shake before flare shakes the picture under a steady flare
(the flare looks attached to the lens); flare before shake moves the flare
with the picture (it looks attached to the scene).
"""
from __future__ import annotations

from pathlib import Path

STACK_IDS: tuple[str, ...] = ("spotlight", "leak", "flare", "wiggle", "shake")
DEFAULT_ORDER: tuple[str, ...] = STACK_IDS
LABELS = {"spotlight": "Spotlight", "leak": "Light leaks", "flare": "Lens flare", "wiggle": "Wiggle", "shake": "Camera shake"}


def _clean_ids(value, name: str) -> list[str]:
    if not isinstance(value, list) or len(value) > len(STACK_IDS):
        raise ValueError(f"{name} must be a list of up to {len(STACK_IDS)} effect ids: {', '.join(STACK_IDS)}.")
    seen: list[str] = []
    for v in value:
        if not isinstance(v, str) or v not in STACK_IDS:
            raise ValueError(f"{name}: unknown effect '{v}'. Allowed: {', '.join(STACK_IDS)}.")
        if v in seen:
            raise ValueError(f"{name}: '{v}' is listed twice.")
        seen.append(v)
    return seen


def clean_fx_order(value) -> list[str]:
    return _clean_ids(value, "Effect stack order")


def clean_fx_bypass(value) -> list[str]:
    return _clean_ids(value, "Effect stack bypass")


def is_enabled(look: dict, fx_id: str) -> bool:
    """True when the stage has settings that change the picture (bypass ignored)."""
    v = look.get(fx_id)
    if not v:
        return False
    if fx_id == "spotlight":
        return True
    if fx_id == "shake":
        return v.get("amount", 0) > 0 or bool(v.get("impact"))
    return v.get("amount", 0) > 0


def resolved_order(look: dict | None) -> list[str]:
    """All stack ids in render order (enabled or not)."""
    look = look or {}
    listed = [i for i in (look.get("fx_order") or []) if i in STACK_IDS]
    return listed + [i for i in DEFAULT_ORDER if i not in listed]


def active_stages(look: dict | None) -> list[str]:
    """Stack ids that will actually render, in order (enabled and not bypassed)."""
    look = look or {}
    bypass = set(look.get("fx_bypass") or [])
    return [i for i in resolved_order(look) if is_enabled(look, i) and i not in bypass]


def stack_graph(base: str, look: dict, w: int, h: int, fps: int, dur: float, cache: Path) -> tuple[list[str], str]:
    """Filter-graph parts for the stack, chained from label ``base``."""
    from app.render import scene_fx as fx
    parts: list[str] = []
    for fx_id in active_stages(look):
        p = look[fx_id]
        if fx_id == "spotlight":
            g, base = fx.spotlight_graph(base, p, fx.spotlight_png(p, w, h, cache), fps, dur)
        elif fx_id == "leak":
            g, base = fx.leak_graph(base, p, fx.leak_clip(p["color"], p["speed"], cache), w, h, fps)
        elif fx_id == "flare":
            png, drift = fx.flare_png(p, w, h, cache)
            g, base = fx.flare_graph(base, p, png, drift, w, h, fps, dur)
        elif fx_id == "wiggle":
            g, base = fx.wiggle_graph(base, p, w, h, fps, dur)
        else:
            g, base = fx.shake_graph(base, p, w, h, fps)
        parts += g
    return parts, base
