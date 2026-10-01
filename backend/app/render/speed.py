"""Speed for video shots: constant speed, speed ramps and freeze frames.

speed_json = {"speed": 0.25-4 (1 = normal),
              "ramp": "none" | "slow_middle" | "fast_middle" | "ease_in" | "ease_out" | "bullet" | "curve",
              "curve": [3-5 speeds, 0.25-4]  (only with ramp "curve"),
              "smooth": bool  (frame interpolation for slow sections),
              "freeze_at_ms": output time within the shot, "freeze_ms": 0-10000 hold}

Every ramp is a piecewise-constant speed profile over the SOURCE clip, rendered
as one piecewise setpts expression (no re-timing tools beyond FFmpeg):
  slow_middle  middle 30 % of the source slow (x0.35), rest at the chosen speed
  fast_middle  middle 30 % fast (x3)
  ease_in      starts slow and speeds up (x0.4 -> x2.4, six steps)
  ease_out     starts fast and slows down (x2.4 -> x0.4)
  bullet       fast - slow - fast ("bullet time": x2.5, x1, x0.3, x1, x2.5)
Ramp speeds multiply the chosen constant speed. With "curve" the 3-5 points are
absolute speeds placed evenly across the source clip (first point at its start,
last at its end); the speed between points is interpolated linearly in twelve
steps and the constant speed setting is not applied.
"smooth" adds FFmpeg minterpolate (motion-compensated interpolation) when any
part plays slower than 1x, so slow motion gets in-between frames instead of
repeated ones; it is much slower to render.
A freeze holds one frame; the shot length does not change.
"""
from __future__ import annotations

# ramp -> list of (fraction of the source clip, speed multiplier)
RAMP_PROFILES: dict[str, list[tuple[float, float]]] = {
    "none": [(1.0, 1.0)],
    "slow_middle": [(0.35, 1.0), (0.30, 0.35), (0.35, 1.0)],
    "fast_middle": [(0.35, 1.0), (0.30, 3.0), (0.35, 1.0)],
    "ease_in": [(1 / 6, m) for m in (0.4, 0.6, 0.85, 1.2, 1.7, 2.4)],
    "ease_out": [(1 / 6, m) for m in (2.4, 1.7, 1.2, 0.85, 0.6, 0.4)],
    "bullet": [(0.25, 2.5), (0.10, 1.0), (0.30, 0.3), (0.10, 1.0), (0.25, 2.5)],
    "curve": [],
}
RAMPS = tuple(RAMP_PROFILES)
CURVE_STEPS = 12
_NEUTRAL = {"speed": 1.0, "ramp": "none", "freeze_at_ms": 0, "freeze_ms": 0}


class SpeedError(ValueError):
    pass


def clean_speed(d) -> dict:
    allowed = {"speed", "ramp", "freeze_at_ms", "freeze_ms", "curve", "smooth"}
    if not isinstance(d, dict) or set(d) - allowed:
        raise SpeedError("Speed settings may only contain speed, ramp, curve, smooth, freeze_at_ms and freeze_ms.")
    d = {"speed": 1, "ramp": "none", "freeze_at_ms": 0, "freeze_ms": 0, **d}
    for key, lo, hi in (("speed", 0.25, 4), ("freeze_at_ms", 0, 3_600_000), ("freeze_ms", 0, 10_000)):
        v = d[key]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi:
            raise SpeedError(f"{key} must be between {lo} and {hi}.")
    if d["ramp"] not in RAMP_PROFILES:
        raise SpeedError("Speed ramp must be one of: " + ", ".join(RAMPS) + ".")
    out = {"speed": round(float(d["speed"]), 3), "ramp": d["ramp"], "freeze_at_ms": int(d["freeze_at_ms"]), "freeze_ms": int(d["freeze_ms"])}
    if d["ramp"] == "curve":
        c = d.get("curve")
        if (not isinstance(c, list) or not 3 <= len(c) <= 5
                or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not 0.25 <= v <= 4 for v in c)):
            raise SpeedError("A speed curve needs 3 to 5 points, each between 0.25 and 4.")
        out["curve"] = [round(float(v), 3) for v in c]
    elif d.get("curve") is not None and not isinstance(d.get("curve"), list):
        raise SpeedError("A speed curve must be a list of speeds.")
    smooth = d.get("smooth", False)
    if not isinstance(smooth, bool):
        raise SpeedError("Smooth slow motion must be true or false.")
    if smooth:
        out["smooth"] = True
    return {} if out == _NEUTRAL else out


def profile(sp: dict | None) -> list[tuple[float, float]]:
    """Absolute speed per source segment: [(fraction, speed), ...]."""
    sp = sp or {}
    ramp = sp.get("ramp", "none")
    if ramp == "curve" and sp.get("curve"):
        pts = [float(v) for v in sp["curve"]]
        n = len(pts) - 1
        segs = []
        for k in range(CURVE_STEPS):
            pos = (k + 0.5) / CURVE_STEPS * n          # midpoint of the step, in point units
            i = min(int(pos), n - 1)
            f = pos - i
            segs.append((1 / CURVE_STEPS, pts[i] + (pts[i + 1] - pts[i]) * f))
        return segs
    s = float(sp.get("speed", 1) or 1)
    return [(frac, s * m) for frac, m in RAMP_PROFILES.get(ramp) or RAMP_PROFILES["none"]]


def plan(sp: dict | None, out_s: float, fps: int) -> tuple[float, str, str]:
    """Return (source seconds needed, filter before fps, filter after fps)."""
    sp = sp or {}
    segs = profile(sp)
    freeze_s = min(sp.get("freeze_ms", 0) / 1000, max(0.0, out_s - 0.1))
    moving = max(0.1, out_s - freeze_s)
    # output length = sum(frac * src / speed)  ->  src = moving / sum(frac / speed)
    src = moving / sum(frac / v for frac, v in segs)
    if len(segs) == 1:
        v = segs[0][1]
        pts = f"setpts=PTS/{v:.4f}" if v != 1 else ""
    else:
        # nested if(): source time T in segment i -> out_i + (T - a_i) / v_i
        expr, a, out_t = "", 0.0, 0.0
        pieces = []
        for frac, v in segs:
            pieces.append((a, out_t, v))
            out_t += frac * src / v
            a += frac * src
        expr = f"{pieces[-1][1]:.4f}+(T-{pieces[-1][0]:.4f})/{pieces[-1][2]:.4f}"
        for (a0, o0, v), (a1, _, _) in zip(reversed(pieces[:-1]), reversed(pieces[1:])):
            expr = f"if(lt(T,{a1:.4f}),{o0:.4f}+(T-{a0:.4f})/{v:.4f},{expr})"
        pts = f"setpts='({expr})/TB'"
    if sp.get("smooth") and pts and min(v for _, v in segs) < 1:
        pts += f",minterpolate=fps={fps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1"
    post = ""
    if freeze_s > 0:
        at = int(round(min(sp.get("freeze_at_ms", 0) / 1000, moving) * fps))
        post = f"loop=loop={int(round(freeze_s * fps))}:size=1:start={at},setpts=N/FRAME_RATE/TB"
    return src, pts, post
