"""Auto-reframe: follow the main subject when a landscape shot is shown in a narrower frame.

Data shape (stored on the shot, next to the ordinary manual crop rectangle):

    shot.crop_json = {"x": 0, "y": 0, "width": 1, "height": 1,          # manual crop (unchanged meaning)
                      "reframe": {"mode": "follow" | "center" | "manual",
                                  "track": [[t_ms, x_center_frac], ...],  # follow: subject path, shot time
                                  "x": 0.5,                                # manual: fixed centre
                                  "method": "matte" | "face" | "center",   # how the track was found
                                  "analyzed_ms": 20000}}

x_center_frac is the horizontal centre of the crop window as a fraction of the (manually cropped)
source width. At render time the shot is first cut to a window with the OUTPUT aspect ratio (full
source height), centred on the interpolated track, and then goes through the normal cover fit, so
Ken Burns motion, looks and effects still apply on top. The window position is one FFmpeg crop
filter whose x expression interpolates linearly between keyframes (crop x/y are evaluated per
frame); no sendcmd and no extra decode.

Shots without a "reframe" entry produce exactly the same filter string as before (see
legacy_crop_filter), so existing projects render byte-identically.

Analysis: frames are sampled at TRACK_FPS (max MAX_SECONDS per shot, one frame for images), the
subject centre comes from the centre of mass of the u2netp cutout matte, falling back to the largest
OpenCV Haar face (only when the cascade file is bundled with cv2) and finally to the frame centre.
The path is clamped so the window stays inside the frame, median-filtered, smoothed with a
zero-phase exponential filter, limited to MAX_PAN_SPEED and simplified to few keyframes.
Works best with one main subject; with several people it follows the strongest/largest one.
"""
from __future__ import annotations

import math
import os
import subprocess
import tempfile
from pathlib import Path

MODES = ("center", "follow", "manual")
TRACK_FPS = 4
MAX_SECONDS = 20
ANALYSIS_WIDTH = 320
MAX_PAN_SPEED = 0.5      # source widths per second
SMOOTH_TAU_S = 0.5       # exponential smoothing time constant
SIMPLIFY_TOL = 0.004     # max deviation (source widths) when dropping keyframes
MAX_KEYFRAMES = 60


class ReframeError(ValueError):
    pass


# ---------------------------------------------------------------------------------------------
# Data validation
# ---------------------------------------------------------------------------------------------

def clean_reframe(raw) -> dict | None:
    """Validate a reframe dict; None/{} means 'no reframe'."""
    if raw in (None, {}):
        return None
    if not isinstance(raw, dict):
        raise ReframeError("Reframe settings must be an object.")
    mode = raw.get("mode", "follow")
    if mode not in MODES:
        raise ReframeError("Reframe mode must be center, follow or manual.")
    out: dict = {"mode": mode}
    x = raw.get("x", 0.5)
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or not 0 <= x <= 1:
        raise ReframeError("Reframe position must be between 0 and 1.")
    out["x"] = round(float(x), 4)
    track = raw.get("track") or []
    if not isinstance(track, list) or len(track) > 400:
        raise ReframeError("Reframe track must be a list of [time_ms, x] points.")
    clean_track = []
    last_t = -1
    for p in track:
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            raise ReframeError("Reframe track points are [time_ms, x].")
        t, v = p
        if isinstance(t, bool) or isinstance(v, bool) or not isinstance(t, (int, float)) or not isinstance(v, (int, float)):
            raise ReframeError("Reframe track points are numbers.")
        if not math.isfinite(t) or not math.isfinite(v) or t < 0 or not 0 <= v <= 1 or t <= last_t:
            raise ReframeError("Reframe track times must increase and positions stay between 0 and 1.")
        last_t = t
        clean_track.append([int(round(t)), round(float(v), 4)])
    if clean_track:
        out["track"] = clean_track
    for key in ("method", "analyzed_ms", "confidence"):
        if key in raw:
            out[key] = raw[key]
    return out


def with_reframe(crop_json: dict | None, reframe: dict | None) -> dict | None:
    """Return a new crop_json carrying `reframe` (keeps the manual crop rectangle)."""
    base = {k: v for k, v in (crop_json or {}).items() if k != "reframe"}
    if reframe is None:
        if not base or base == {"x": 0, "y": 0, "width": 1, "height": 1}:
            return None
        return base
    if not all(k in base for k in ("x", "y", "width", "height")):
        base = {"x": 0, "y": 0, "width": 1, "height": 1}
    return {**base, "reframe": reframe}


# ---------------------------------------------------------------------------------------------
# Render: FFmpeg filter fragments
# ---------------------------------------------------------------------------------------------

def legacy_crop_filter(c: dict) -> str:
    """The manual crop exactly as renderer.py has always written it (keep byte-identical)."""
    return f"crop=w='max(2,trunc(iw*{c['width']}/2)*2)':h='max(2,trunc(ih*{c['height']}/2)*2)':x='iw*{c['x']}':y='ih*{c['y']}',"


def _num(v: float) -> str:
    return f"{v:.4f}".rstrip("0").rstrip(".") if v != int(v) else str(int(v))


def track_x_expr(track: list, fps: int) -> str:
    """FFmpeg expression: piecewise-linear interpolation of the track at output frame n."""
    if not track:
        return "0.5"
    if len(track) == 1:
        return _num(track[0][1])
    t0, tn = track[0][0] / 1000, track[-1][0] / 1000
    T = f"clip(n/{int(fps)},{_num(t0)},{_num(tn)})"
    terms = []
    for (ta, xa), (tb, xb) in zip(track, track[1:]):
        a, b = ta / 1000, tb / 1000
        if xa == xb:
            seg = _num(xa)
        else:
            seg = f"({_num(xa)}+{_num(xb - xa)}*({T}-{_num(a)})/{_num(b - a)})"
        terms.append(f"gte({T},{_num(a)})*lt({T},{_num(b)})*{seg}")
    terms.append(f"gte({T},{_num(tn)})*{_num(track[-1][1])}")
    return "+".join(terms)


def reframe_filter(reframe: dict, out_w: int, out_h: int, fps: int) -> str:
    """Crop window with the output aspect (full height), positioned per the reframe mode."""
    mode = reframe.get("mode", "follow")
    if mode == "center":
        return ""          # cover fit already centres the frame
    if mode == "manual":
        x = _num(float(reframe.get("x", 0.5)))
    else:
        track = reframe.get("track") or []
        if not track:
            return ""
        x = track_x_expr(track, fps)
    ar = f"{out_w / out_h:.6f}"
    return (f"crop=w='trunc(min(iw,ih*{ar})/2)*2':h='trunc(min(ih,iw/{ar})/2)*2'"
            f":x='clip(({x})*iw-ow/2,0,iw-ow)':y='(ih-oh)/2',")


def shot_crop_prefilter(crop_json: dict | None, out_w: int, out_h: int, fps: int) -> str:
    """Pre-filter for a shot's crop_json: manual crop (legacy, unchanged) then the reframe window."""
    if not crop_json:
        return ""
    reframe = crop_json.get("reframe")
    rect = {k: crop_json[k] for k in ("x", "y", "width", "height") if k in crop_json}
    out = ""
    if len(rect) == 4:
        full = rect["x"] == 0 and rect["y"] == 0 and rect["width"] == 1 and rect["height"] == 1
        if not (reframe and full):   # a full-frame rect is a no-op; only skip it when reframing
            out += legacy_crop_filter(crop_json)
    if reframe:
        out += reframe_filter(reframe, out_w, out_h, fps)
    return out


# ---------------------------------------------------------------------------------------------
# Analysis: subject centre per frame
# ---------------------------------------------------------------------------------------------

def window_fraction(src_w: int, src_h: int, out_w: int, out_h: int) -> float:
    """Width of the reframe window as a fraction of the source width."""
    if not src_w or not src_h:
        return 1.0
    return min(1.0, (src_h * out_w / out_h) / src_w)


def _matte_centre(img) -> tuple[float, float] | None:
    from app.render import cutout
    try:
        if not cutout.model_path("u2netp").is_file():
            return None
        import numpy as np
        a = np.asarray(cutout.predict_matte(img, "u2netp"), dtype=np.float32) / 255.0
    except Exception:  # noqa: BLE001 - analysis must never break the project copy
        return None
    a = np.where(a > 0.35, a, 0.0)
    mass = float(a.sum())
    coverage = mass / a.size
    if coverage < 0.004:
        return None
    cols = a.sum(axis=0)
    x = float((cols * (np.arange(a.shape[1]) + 0.5)).sum() / mass / a.shape[1])
    # A matte that covers most of the frame says little about where the subject is.
    conf = max(0.1, min(1.0, 1.4 - coverage * 1.5))
    return x, conf


_cascade = None


def _face_centre(img) -> tuple[float, float] | None:
    global _cascade
    try:
        import cv2
        import numpy as np
        if _cascade is None:
            base = getattr(getattr(cv2, "data", None), "haarcascades", "") or ""
            path = os.path.join(base, "haarcascade_frontalface_default.xml")
            _cascade = cv2.CascadeClassifier(path) if base and os.path.isfile(path) else False
        if _cascade is False:
            return None
        gray = cv2.cvtColor(np.asarray(img.convert("RGB")), cv2.COLOR_RGB2GRAY)
        faces = _cascade.detectMultiScale(gray, 1.1, 5, minSize=(16, 16))
        if len(faces) == 0:
            return None
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        return (x + w / 2) / gray.shape[1], 0.8
    except Exception:  # noqa: BLE001
        return None


def subject_centre(img) -> tuple[float | None, float, str]:
    """(x_frac or None, confidence, method) for one PIL frame."""
    r = _matte_centre(img)
    if r:
        return r[0], r[1], "matte"
    r = _face_centre(img)
    if r:
        return r[0], r[1], "face"
    return None, 0.0, "center"


# ---------------------------------------------------------------------------------------------
# Path smoothing
# ---------------------------------------------------------------------------------------------

def smooth_path(times_s: list[float], xs: list[float | None], win: float,
                max_speed: float = MAX_PAN_SPEED, tau: float = SMOOTH_TAU_S) -> list[float]:
    """Clamp, fill gaps, median-filter, zero-phase exponential smoothing, then rate-limit."""
    n = len(xs)
    if n == 0:
        return []
    half = win / 2
    lo, hi = (0.5, 0.5) if win >= 1 else (half, 1 - half)
    known = [i for i, v in enumerate(xs) if v is not None]
    if not known:
        return [round(min(max(0.5, lo), hi), 4)] * n
    filled = []
    for i in range(n):
        if xs[i] is not None:
            filled.append(xs[i]); continue
        prev = max((k for k in known if k < i), default=None)
        nxt = min((k for k in known if k > i), default=None)
        if prev is None:
            filled.append(xs[nxt])
        elif nxt is None:
            filled.append(xs[prev])
        else:
            f = (times_s[i] - times_s[prev]) / max(times_s[nxt] - times_s[prev], 1e-6)
            filled.append(xs[prev] + (xs[nxt] - xs[prev]) * f)
    v = [min(max(x, lo), hi) for x in filled]
    if n >= 3:   # median of 3 removes single-frame detector glitches
        v = [v[0]] + [sorted(v[i - 1:i + 2])[1] for i in range(1, n - 1)] + [v[-1]]
    # centred moving average (window shrinks symmetrically at the ends: no lag, keeps linear moves)
    k = 2
    v = [sum(v[i - min(k, i, n - 1 - i):i + min(k, i, n - 1 - i) + 1]) / (2 * min(k, i, n - 1 - i) + 1) for i in range(n)]
    # zero-phase exponential smoothing (forward then backward: no lag)
    for order in (range(1, n), range(n - 2, -1, -1)):
        for i in order:
            j = i - 1 if order.step == 1 else i + 1
            dt = abs(times_s[i] - times_s[j])
            a = 1 - math.exp(-dt / tau) if tau > 0 else 1
            v[i] = v[j] + a * (v[i] - v[j])
    # rate limit in both directions so every step respects max_speed
    for i in range(1, n):
        lim = max_speed * (times_s[i] - times_s[i - 1])
        v[i] = min(max(v[i], v[i - 1] - lim), v[i - 1] + lim)
    for i in range(n - 2, -1, -1):
        lim = max_speed * (times_s[i + 1] - times_s[i])
        v[i] = min(max(v[i], v[i + 1] - lim), v[i + 1] + lim)
    return [min(max(x, lo), hi) for x in v]


def simplify(points: list[list], tol: float = SIMPLIFY_TOL) -> list[list]:
    """Ramer-Douglas-Peucker on (t_ms, x): drop keyframes linear interpolation reproduces."""
    if len(points) <= 2:
        return [list(p) for p in points]

    def rdp(pts):
        (t0, x0), (t1, x1) = pts[0], pts[-1]
        best, idx = -1.0, 0
        for i in range(1, len(pts) - 1):
            t, x = pts[i]
            pred = x0 + (x1 - x0) * (t - t0) / max(t1 - t0, 1e-9)
            d = abs(x - pred)
            if d > best:
                best, idx = d, i
        if best <= tol:
            return [pts[0], pts[-1]]
        return rdp(pts[:idx + 1])[:-1] + rdp(pts[idx:])

    out = rdp([list(p) for p in points])
    if len(out) == 2 and abs(out[0][1] - out[1][1]) < 1e-4:
        return [out[0]]
    return out


def build_track(times_s: list[float], xs: list[float | None], win: float) -> list[list]:
    sm = smooth_path(times_s, xs, win)
    pts = [[int(round(t * 1000)), round(x, 4)] for t, x in zip(times_s, sm)]
    tol = SIMPLIFY_TOL
    track = simplify(pts, tol)
    while len(track) > MAX_KEYFRAMES:
        tol *= 1.6
        track = simplify(pts, tol)
    return track


# ---------------------------------------------------------------------------------------------
# Frame sampling + shot analysis
# ---------------------------------------------------------------------------------------------

def _apply_rect(img, rect: dict | None):
    if not rect or not all(k in rect for k in ("x", "y", "width", "height")):
        return img
    w, h = img.size
    cw, ch = max(2, int(w * rect["width"] / 2) * 2), max(2, int(h * rect["height"] / 2) * 2)
    x, y = int(w * rect["x"]), int(h * rect["y"])
    return img.crop((x, y, min(w, x + cw), min(h, y + ch)))


def sample_frames(src: str, is_image: bool, in_ms: int, seconds: float, rect: dict | None,
                  speed_json: dict | None = None, src_duration_ms: int | None = None,
                  rotation: int = 0, cancel_check=None) -> list[tuple[float, object]]:
    """[(shot_time_s, PIL RGB frame)] at TRACK_FPS, max MAX_SECONDS, downscaled for analysis."""
    from PIL import Image
    if is_image:
        with Image.open(src) as im:
            img = _apply_rect(im.convert("RGB"), rect)
        img.thumbnail((ANALYSIS_WIDTH * 2, ANALYSIS_WIDTH * 2))
        return [(0.0, img)]
    from app.config import FFMPEG_BIN
    seconds = max(0.25, min(seconds, MAX_SECONDS))
    speed_pre = ""
    src_s = seconds
    if speed_json:
        try:
            from app.render.speed import plan as speed_plan
            src_s, speed_pre, _ = speed_plan(speed_json, seconds, TRACK_FPS)
        except Exception:  # noqa: BLE001
            speed_pre = ""
    loop = bool(src_duration_ms) and (src_duration_ms - in_ms) < src_s * 1000
    vf = []
    if rotation in (90, -270):
        vf.append("transpose=1")
    elif rotation in (-90, 270):
        vf.append("transpose=2")
    if speed_pre:
        vf.append(speed_pre)
    vf.append(f"fps={TRACK_FPS}")
    if rect and all(k in rect for k in ("x", "y", "width", "height")) and rect != {"x": 0, "y": 0, "width": 1, "height": 1}:
        vf.append(legacy_crop_filter(rect).rstrip(","))
    vf.append(f"scale={ANALYSIS_WIDTH}:-2")
    with tempfile.TemporaryDirectory(prefix="reframe_") as tmp:
        args = [FFMPEG_BIN, "-v", "error", "-nostdin", "-y"]
        if loop:
            args += ["-stream_loop", "-1"]
        args += ["-ss", f"{in_ms / 1000:.3f}", "-i", src, "-t", f"{seconds:.3f}", "-an", "-vf", ",".join(vf),
                 "-frames:v", str(int(seconds * TRACK_FPS) + 1), str(Path(tmp) / "f_%04d.png")]
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0  # type: ignore[attr-defined]
        proc = subprocess.run(args, capture_output=True, timeout=600, creationflags=flags)
        if proc.returncode != 0:
            raise ReframeError("Could not read frames for reframing: " + proc.stderr.decode(errors="replace")[-300:])
        out = []
        for i, f in enumerate(sorted(Path(tmp).glob("f_*.png"))):
            with Image.open(f) as im:
                out.append((i / TRACK_FPS, im.convert("RGB")))
        return out


def analyze_frames(frames: list[tuple[float, object]], out_w: int, out_h: int, progress=None, cancel_check=None) -> dict:
    """Reframe dict ("follow" with a track) for sampled frames."""
    if not frames:
        return {"mode": "center", "x": 0.5, "method": "center"}
    w, h = frames[0][1].size
    win = window_fraction(w, h, out_w, out_h)
    times, xs, methods, confs = [], [], [], []
    for i, (t, img) in enumerate(frames):
        if cancel_check and cancel_check():
            raise ReframeError("cancelled")
        x, conf, method = subject_centre(img)
        times.append(t); xs.append(x); methods.append(method); confs.append(conf)
        if progress:
            progress((i + 1) / len(frames))
    found = [m for m in methods if m != "center"]
    method = max(set(found), key=found.count) if found else "center"
    track = build_track(times, xs, win)
    conf = round(sum(confs) / len(confs), 2)
    return {"mode": "follow", "x": track[0][1], "track": track, "method": method, "confidence": conf,
            "analyzed_ms": int(round(times[-1] * 1000))}


def analyze_shot(shot, project, resolve_path, progress=None, cancel_check=None) -> dict:
    """Analyse one shot (ORM object or stand-in with .asset) for the project's canvas."""
    from app.render.ffmpeg_utils import probe
    asset = shot.asset
    src = resolve_path(asset)
    rect = shot.crop_json if isinstance(shot.crop_json, dict) else None
    if asset.type == "image":
        frames = sample_frames(src, True, 0, 0, rect)
    else:
        p = probe(src)
        in_ms = int(shot.source_in_ms or 0)
        src_dur = p.duration_ms or asset.duration_ms or 0
        if shot.duration_ms:
            seconds = shot.duration_ms / 1000
        elif shot.source_out_ms:
            seconds = max(0.25, (shot.source_out_ms - in_ms) / 1000)
        else:
            seconds = max(0.25, (src_dur - in_ms) / 1000) if src_dur else MAX_SECONDS
        frames = sample_frames(src, False, in_ms, seconds, rect, getattr(shot, "speed_json", None), src_dur,
                               p.rotation or 0, cancel_check)
    return analyze_frames(frames, project.width, project.height, progress, cancel_check)
