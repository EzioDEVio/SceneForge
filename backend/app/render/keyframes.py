"""Keyframe animation for overlays (stickers, media, textured titles) and text layers.

A layer may carry ``keyframes``: a list of up to 32 points, each
``{t_ms, x, y, width|size, rotation, opacity, ease}``. ``t_ms`` is relative to the
layer's own start. Every value is optional; a missing value falls back to the layer's
own setting (text layers: rotation 0, opacity 100). ``ease`` shapes the segment that
LEAVES the keyframe (linear | ease_in | ease_out | ease_in_out). Before the first keyframe
the first values hold, after the last one the last values hold. When keyframes are
present they override the layer's x / y / width (size) / rotation / opacity.

Overlays render through FFmpeg expressions in ``t`` built from a sum of clipped,
eased segments (no nesting, so any number of keys stays a flat expression):

    v(t) = v0 + sum_i (v[i+1] - v[i]) * ease_i(clip((t - T[i]) / (T[i+1] - T[i]), 0, 1))

Text layers render through ASS: the layer is cut into short events (30 ms steps, about
33 per second) while something changes, each with \\pos, \\frz, \\fscx/\\fscy and
\\alpha; identical neighbouring steps are merged, so holds stay one event. Text layer
entrance animations other than ``fade`` are not combined with keyframes (fade and
the exit fade are).

frontend/src/keyframes.ts mirrors ``value_at`` exactly for the live editor preview.
"""
from __future__ import annotations

import math

EASES = ("linear", "ease_in", "ease_out", "ease_in_out")
MAX_KEYFRAMES = 32
MAX_T_MS = 3_600_000
OVERLAY_PROPS = {"x": (-50, 150), "y": (-50, 150), "width": (3, 100), "rotation": (-180, 180), "opacity": (0, 100)}
TEXT_PROPS = {"x": (0, 100), "y": (0, 100), "size": (12, 200), "rotation": (-180, 180), "opacity": (0, 100)}
TEXT_STEP_MS = 30


class KeyframeError(ValueError):
    pass


def clean_keyframes(raw, props: dict, label: str) -> list[dict] | None:
    """Validate and normalise a keyframe list. Returns None for "no keyframes"."""
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise KeyframeError(f"{label}: keyframes must be a list.")
    if not raw:
        return None
    if len(raw) > MAX_KEYFRAMES:
        raise KeyframeError(f"{label}: at most {MAX_KEYFRAMES} keyframes.")
    out = []
    for i, k in enumerate(raw):
        where = f"{label}, keyframe {i + 1}"
        if not isinstance(k, dict):
            raise KeyframeError(f"{where}: must be an object.")
        unknown = set(k) - set(props) - {"t_ms", "ease"}
        if unknown:
            raise KeyframeError(f"{where}: unknown setting {sorted(unknown)[0]}.")
        t = k.get("t_ms")
        if isinstance(t, bool) or not isinstance(t, (int, float)) or not 0 <= t <= MAX_T_MS:
            raise KeyframeError(f"{where}: t_ms must be between 0 and {MAX_T_MS}.")
        ease = k.get("ease", "linear")
        if ease not in EASES:
            raise KeyframeError(f"{where}: ease must be one of: {', '.join(EASES)}.")
        row = {"t_ms": int(round(t)), "ease": ease}
        for key, (lo, hi) in props.items():
            if key not in k or k[key] is None:
                continue
            v = k[key]
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not lo <= v <= hi:
                raise KeyframeError(f"{where}: {key} must be between {lo} and {hi}.")
            row[key] = round(float(v), 2)
        out.append(row)
    out.sort(key=lambda r: r["t_ms"])
    if any(a["t_ms"] == b["t_ms"] for a, b in zip(out, out[1:])):
        raise KeyframeError(f"{label}: two keyframes share the same time.")
    return out


def clean_overlay_keyframes(o: dict, label: str) -> None:
    """In place: validate o['keyframes'] (if any); drop the key when empty."""
    if "keyframes" not in o:
        return
    kfs = clean_keyframes(o.get("keyframes"), OVERLAY_PROPS, label)
    if kfs:
        o["keyframes"] = kfs
    else:
        o.pop("keyframes", None)


def with_text_keyframes(raw_layer, dumped: dict) -> dict:
    """Re-attach validated keyframes to a text layer after the schema dump."""
    if isinstance(raw_layer, dict) and raw_layer.get("keyframes") is not None:
        kfs = clean_keyframes(raw_layer.get("keyframes"), TEXT_PROPS, f"Text layer {dumped.get('id', '')[:12]}")
        if kfs:
            dumped["keyframes"] = kfs
    return dumped


# --- interpolation -------------------------------------------------------------------

def ease(name: str, p: float) -> float:
    p = min(1.0, max(0.0, p))
    if name == "ease_in":
        return p * p
    if name == "ease_out":
        return 1 - (1 - p) * (1 - p)
    if name == "ease_in_out":
        return 0.5 - 0.5 * math.cos(math.pi * p)
    return p


def _values(kfs: list[dict], prop: str, base: float) -> list[float]:
    return [float(k[prop]) if k.get(prop) is not None else float(base) for k in kfs]


def value_at(kfs: list[dict], prop: str, base: float, t_ms: float) -> float:
    """Value of `prop` at `t_ms` (relative to the layer start)."""
    if not kfs:
        return float(base)
    vals = _values(kfs, prop, base)
    v = vals[0]
    for i in range(len(kfs) - 1):
        t0, t1 = kfs[i]["t_ms"], kfs[i + 1]["t_ms"]
        p = (t_ms - t0) / max(1e-9, t1 - t0)
        v += (vals[i + 1] - vals[i]) * ease(kfs[i].get("ease", "linear"), p)
    return v


def _ease_expr(name: str, p: str) -> str:
    if name == "ease_in":
        return f"pow({p},2)"
    if name == "ease_out":
        return f"(1-pow(1-{p},2))"
    if name == "ease_in_out":
        return f"(0.5-0.5*cos(PI*{p}))"
    return p


def piecewise_expr(kfs: list[dict], prop: str, base: float, start_s: float, var: str = "t",
                   scale: float = 1.0, offset: float = 0.0) -> str:
    """FFmpeg expression of the keyframed value (times relative to start_s, in seconds)."""
    vals = [v * scale + offset for v in _values(kfs, prop, base)]
    expr = f"{vals[0]:.4f}"
    for i in range(len(kfs) - 1):
        dv = vals[i + 1] - vals[i]
        if abs(dv) < 1e-9:
            continue
        t0 = start_s + kfs[i]["t_ms"] / 1000
        dt = max(0.001, (kfs[i + 1]["t_ms"] - kfs[i]["t_ms"]) / 1000)
        p = f"clip(({var}-{t0:.3f})/{dt:.3f},0,1)"
        expr += f"{dv:+.4f}*{_ease_expr(kfs[i].get('ease', 'linear'), p)}"
    return f"({expr})"


def _varies(kfs: list[dict], prop: str, base: float) -> bool:
    vals = _values(kfs, prop, base)
    return max(vals) - min(vals) > 1e-9


# --- overlays (FFmpeg) ---------------------------------------------------------------

def split_overlay(o: dict) -> dict:
    """The overlay as build_overlay_pass should see it. Without keyframes this is `o`
    itself (so the filter graph is byte-identical). With keyframes the static rotation,
    opacity and glide are neutralised (the keyframed filters replace them) and the card is
    drawn at the widest keyframed size so scaling only ever shrinks it."""
    kfs = o.get("keyframes")
    if not kfs:
        return o
    base = {k: o[k] for k in ("x", "y", "width", "rotation", "opacity")}
    widest = max(_values(kfs, "width", base["width"]))
    return {**o, "rotation": 0, "opacity": 100, "x2": None, "y2": None, "width": widest,
            "_kf": kfs, "_kf_base": base}


def overlay_filters(o: dict, start_s: float) -> list[str]:
    """Per-frame rotate / opacity / scale filters for a keyframed overlay ([] otherwise)."""
    kfs = o.get("_kf")
    if not kfs:
        return []
    base = o["_kf_base"]
    out = []
    rots = _values(kfs, "rotation", base["rotation"])
    if any(abs(r) > 1e-9 for r in rots):
        a = piecewise_expr(kfs, "rotation", base["rotation"], start_s, scale=math.pi / 180)
        out.append(f"rotate=a='{a}':c=none:ow='hypot(iw,ih)':oh='hypot(iw,ih)'")
    if _varies(kfs, "opacity", base["opacity"]):
        a = piecewise_expr(kfs, "opacity", base["opacity"], start_s, var="T", scale=0.01)
        out.append(f"format=rgba,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='alpha(X,Y)*clip({a},0,1)'")
    else:
        op = _values(kfs, "opacity", base["opacity"])[0]
        if op < 100:
            out.append(f"colorchannelmixer=aa={op / 100:.3f}")
    if _varies(kfs, "width", base["width"]):
        s = piecewise_expr(kfs, "width", base["width"], start_s, scale=1 / o["width"])
        out.append(f"scale=w='max(2,trunc(iw*{s}/2)*2)':h='max(2,trunc(ih*{s}/2)*2)':eval=frame")
    return out


def overlay_position(o: dict, cx: float, cy: float, frame_w: int, frame_h: int, start_s: float) -> tuple[str, str]:
    """Centre x/y for the overlay filter: the static numbers, or keyframed expressions."""
    kfs = o.get("_kf")
    if not kfs:
        return f"{cx:.1f}", f"{cy:.1f}"
    base = o["_kf_base"]
    return (piecewise_expr(kfs, "x", base["x"], start_s, scale=frame_w / 100),
            piecewise_expr(kfs, "y", base["y"], start_s, scale=frame_h / 100))


# --- text layers (ASS) ---------------------------------------------------------------

def text_state(layer: dict, t_ms: float) -> dict:
    kfs = layer.get("keyframes") or []
    return {
        "x": value_at(kfs, "x", float(layer.get("x", 50)), t_ms),
        "y": value_at(kfs, "y", float(layer.get("y", 50)), t_ms),
        "size": value_at(kfs, "size", float(layer.get("size", 64)), t_ms),
        "rotation": value_at(kfs, "rotation", 0.0, t_ms),
        "opacity": value_at(kfs, "opacity", 100.0, t_ms),
    }


def keyframed_text_events(layer: dict, index: int, start: int, end: int, base_tags: str, canvas_w: int, canvas_h: int,
                          ts, text: str, side_margin: int, exit_ms: int, fade_in_ms: int) -> list[str]:
    """ASS events for a keyframed text layer, stepped while anything changes."""
    base_size = max(1.0, float(layer.get("size", 64)))
    span = end - start

    def tags(local: float) -> str:
        s = text_state(layer, local)
        alpha = s["opacity"] / 100
        if fade_in_ms > 0:
            alpha *= min(1.0, max(0.0, local / fade_in_ms))
        if exit_ms > 0:
            alpha *= min(1.0, max(0.0, (span - local) / exit_ms))
        a = int(round(255 * (1 - min(1.0, max(0.0, alpha)))))
        sc = 100 * s["size"] / base_size
        return (r"\pos(%.1f,%.1f)\frz%.2f\fscx%.1f\fscy%.1f\alpha&H%02X&"
                % (s["x"] * canvas_w / 100, s["y"] * canvas_h / 100, -s["rotation"], sc, sc, a))

    bounds = list(range(start, end, TEXT_STEP_MS)) + [end]
    runs: list[tuple[int, int, str]] = []
    for a, b in zip(bounds, bounds[1:]):
        if b <= a:
            continue
        tag = tags(a - start)
        if runs and runs[-1][2] == tag:
            runs[-1] = (runs[-1][0], b, tag)
        else:
            runs.append((a, b, tag))
    return [f"Dialogue: {index + 1},{ts(a)},{ts(b)},Default,,{side_margin},{side_margin},0,,{{{base_tags}{tag}}}{text}\n"
            for a, b, tag in runs if ts(a) != ts(b)]
