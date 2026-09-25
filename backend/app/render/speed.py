"""Speed for video shots: constant speed, speed ramps and freeze frames.

speed_json = {"speed": 0.25-4 (1 = normal), "ramp": "none" | "slow_middle" | "fast_middle",
              "freeze_at_ms": output time within the shot, "freeze_ms": 0-10000 hold}
A ramp plays the middle 30 % of the source slow (x0.35) or fast (x3) with the
rest at the chosen speed, so a moment can be stretched into slow motion or
whipped past. A freeze holds one frame; the shot length does not change.
"""
from __future__ import annotations

RAMPS = {"none": 1.0, "slow_middle": 0.35, "fast_middle": 3.0}
A, B = 0.35, 0.65          # source fractions where the ramp begins and ends


class SpeedError(ValueError):
    pass


def clean_speed(d) -> dict:
    if not isinstance(d, dict) or set(d) - {"speed", "ramp", "freeze_at_ms", "freeze_ms"}:
        raise SpeedError("Speed settings may only contain speed, ramp, freeze_at_ms and freeze_ms.")
    d = {"speed": 1, "ramp": "none", "freeze_at_ms": 0, "freeze_ms": 0, **d}
    for key, lo, hi in (("speed", 0.25, 4), ("freeze_at_ms", 0, 3_600_000), ("freeze_ms", 0, 10_000)):
        v = d[key]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi:
            raise SpeedError(f"{key} must be between {lo} and {hi}.")
    if d["ramp"] not in RAMPS:
        raise SpeedError("Speed ramp must be one of: " + ", ".join(RAMPS) + ".")
    out = {"speed": round(float(d["speed"]), 3), "ramp": d["ramp"], "freeze_at_ms": int(d["freeze_at_ms"]), "freeze_ms": int(d["freeze_ms"])}
    return {} if out == {"speed": 1.0, "ramp": "none", "freeze_at_ms": 0, "freeze_ms": 0} else out


def plan(sp: dict | None, out_s: float, fps: int) -> tuple[float, str, str]:
    """Return (source seconds needed, filter before fps, filter after fps)."""
    sp = sp or {}
    s, m = float(sp.get("speed", 1) or 1), RAMPS.get(sp.get("ramp", "none"), 1.0)
    freeze_s = min(sp.get("freeze_ms", 0) / 1000, max(0.0, out_s - 0.1))
    moving = max(0.1, out_s - freeze_s)
    if m == 1.0:
        src = moving * s
        pts = f"setpts=PTS/{s:.4f}" if s != 1 else ""
    else:
        src = moving * s / ((1 - (B - A)) + (B - A) / m)
        a, b = A * src, B * src
        pts = (f"setpts='if(lt(T,{a:.4f}),T/{s:.4f},if(lt(T,{b:.4f}),{a / s:.4f}+(T-{a:.4f})/{s * m:.4f},"
               f"{a / s + (b - a) / (s * m):.4f}+(T-{b:.4f})/{s:.4f}))/TB'")
    post = ""
    if freeze_s > 0:
        at = int(round(min(sp.get("freeze_at_ms", 0) / 1000, moving) * fps))
        post = f"loop=loop={int(round(freeze_s * fps))}:size=1:start={at},setpts=N/FRAME_RATE/TB"
    return src, pts, post
