"""Photo tools with local computer vision (OpenCV), no AI download needed.

* 2.5D parallax: the subject area is cut out with a soft edge; the background
  behind it is filled in (inpainting); the two layers then move at different
  depths, so a still photo gains depth. look.parallax =
  {"x","y","w","h" (subject box, % of frame), "shape": "ellipse"|"rect", "direction": "in"|"out"|"left"|"right", "amount": 0-100}
* Photo restore: denoise, remove dust and scratches, recover contrast,
  sharpen and upscale small scans. Creates a new image in the Media Pool.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import uuid
from pathlib import Path

import numpy as np

from app.config import FFMPEG_BIN

PARALLAX_DEFAULT = {"x": 50, "y": 55, "w": 40, "h": 70, "shape": "ellipse", "direction": "in", "amount": 50}


class PhotoError(ValueError):
    pass


MISSING_CV = ("Photo tools are not installed yet. Close SceneForge and every start.bat window, "
              "run scripts\\setup.bat in the SceneForge folder, then start SceneForge again.")


def _cv2():
    try:
        import cv2
        return cv2
    except ImportError:
        raise PhotoError(MISSING_CV) from None


def clean_parallax(d) -> dict:
    if not isinstance(d, dict) or set(d) - set(PARALLAX_DEFAULT):
        raise PhotoError("Parallax settings may only contain: " + ", ".join(PARALLAX_DEFAULT) + ".")
    d = {**PARALLAX_DEFAULT, **d}
    out = {}
    for k, lo, hi in (("x", 0, 100), ("y", 0, 100), ("w", 5, 100), ("h", 5, 100), ("amount", 0, 100)):
        v = d[k]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi:
            raise PhotoError(f"Parallax {k} must be between {lo} and {hi}.")
        out[k] = round(float(v), 2)
    if d["shape"] not in ("ellipse", "rect") or d["direction"] not in ("in", "out", "left", "right"):
        raise PhotoError("Parallax shape must be ellipse or rect; direction in, out, left or right.")
    out["shape"], out["direction"] = d["shape"], d["direction"]
    return out


def _load(path: str):
    cv2 = _cv2()
    img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)   # handles non-ASCII Windows paths
    if img is None:
        raise PhotoError("This image could not be read.")
    return img


def parallax_layers(src: str, px: dict, cache: Path) -> tuple[str, str]:
    """(background with the subject filled in, subject with soft alpha) PNGs."""
    cv2 = _cv2()
    key = hashlib.sha256(f"v1|{src}|{os.path.getmtime(src)}|{sorted(px.items())}".encode()).hexdigest()[:20]
    cache.mkdir(parents=True, exist_ok=True)
    bg_p, fg_p = cache / f"plx_bg_{key}.png", cache / f"plx_fg_{key}.png"
    if bg_p.exists() and fg_p.exists():
        return str(bg_p), str(fg_p)
    img = _load(src)
    h, w = img.shape[:2]
    mask = np.zeros((h, w), np.uint8)
    cx, cy, bw, bh = px["x"] / 100 * w, px["y"] / 100 * h, px["w"] / 100 * w, px["h"] / 100 * h
    if px["shape"] == "ellipse":
        cv2.ellipse(mask, (int(cx), int(cy)), (int(bw / 2), int(bh / 2)), 0, 0, 360, 255, -1)
    else:
        cv2.rectangle(mask, (int(cx - bw / 2), int(cy - bh / 2)), (int(cx + bw / 2), int(cy + bh / 2)), 255, -1)
    # Background: fill the (slightly grown) subject area from its surroundings, at reduced size for speed.
    grow = cv2.dilate(mask, np.ones((int(0.03 * max(w, h)) | 1,) * 2, np.uint8))
    small = 900 / max(w, h) if max(w, h) > 900 else 1.0
    s_img, s_mask = cv2.resize(img, None, fx=small, fy=small, interpolation=cv2.INTER_AREA), cv2.resize(grow, None, fx=small, fy=small)
    filled = cv2.inpaint(s_img, s_mask, 9, cv2.INPAINT_TELEA)
    filled = cv2.resize(filled, (w, h), interpolation=cv2.INTER_CUBIC)
    bg = np.where(grow[..., None] > 0, cv2.GaussianBlur(filled, (0, 0), 3), img)
    cv2.imencode(".png", bg)[1].tofile(str(bg_p))
    soft = cv2.GaussianBlur(mask, (0, 0), max(2, 0.02 * max(w, h)))
    fg = np.dstack([img, soft])
    cv2.imencode(".png", fg)[1].tofile(str(fg_p))
    return str(bg_p), str(fg_p)


def parallax_clip(src: str, px: dict, w: int, h: int, fps: int, seconds: float, cache: Path) -> str:
    """Render the two layers moving at different depths into a video clip."""
    bg, fg = parallax_layers(src, px, cache)
    out = cache / f"plx_{hashlib.sha256(f'{bg}|{w}x{h}|{fps}|{seconds:.3f}|{sorted(px.items())}'.encode()).hexdigest()[:20]}.mp4"
    if out.exists():
        return str(out)
    a = px["amount"] / 100
    n = max(2, int(round(seconds * fps)))
    t = f"(on/{n - 1})"
    ease = f"(0.5-0.5*cos(PI*{t}))"
    if px["direction"] in ("in", "out"):
        zb0, zb1, zf0, zf1 = 1.08, 1.08 + 0.06 * a, 1.0, 1.0 + 0.22 * a
        if px["direction"] == "out":
            zb0, zb1, zf0, zf1 = zb1, zb0, zf1, zf0
        zb, zf = f"{zb0}+({zb1 - zb0:.4f})*{ease}", f"{zf0}+({zf1 - zf0:.4f})*{ease}"
        xb = xf = "iw/2-(iw/zoom/2)"
    else:
        sign = -1 if px["direction"] == "left" else 1
        zb, zf = "1.12", "1.12"
        xb = f"iw/2-(iw/zoom/2)+{sign}*iw*{0.015 * a:.4f}*({ease}-0.5)*2"
        xf = f"iw/2-(iw/zoom/2)+{sign}*iw*{0.055 * a:.4f}*({ease}-0.5)*2"
    common = f"d={n}:s={w}x{h}:fps={fps}"
    graph = (f"[0:v]scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase,crop={w * 2}:{h * 2},"
             f"zoompan=z='{zb}':x='{xb}':y='ih/2-(ih/zoom/2)':{common}[b];"
             f"[1:v]scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase,crop={w * 2}:{h * 2},format=rgba,"
             f"zoompan=z='{zf}':x='{xf}':y='ih/2-(ih/zoom/2)':{common}[f];"
             f"[b][f]overlay=format=auto,format=yuv420p[v]")
    tmp = out.with_name(f"{out.stem}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp.mp4")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0  # type: ignore[attr-defined]
    r = subprocess.run([FFMPEG_BIN, "-y", "-hide_banner", "-nostdin", "-loglevel", "error", "-i", bg, "-i", fg,
                        "-filter_complex", graph, "-map", "[v]", "-frames:v", str(n), "-c:v", "libx264", "-preset", "veryfast",
                        "-crf", "16", str(tmp)], capture_output=True, timeout=900, creationflags=flags)
    if r.returncode != 0:
        tmp.unlink(missing_ok=True)
        raise PhotoError("The parallax animation could not be made: " + r.stderr.decode(errors="replace")[-200:])
    os.replace(tmp, out)
    return str(out)


def restore_photo(src: str, dest: str) -> dict:
    """Denoise, remove dust/scratches, recover contrast, sharpen, upscale small
    scans. Returns a short report."""
    cv2 = _cv2()
    img = _load(src)
    h, w = img.shape[:2]
    report = {"size_before": [w, h]}
    img = cv2.fastNlMeansDenoisingColored(img, None, 6, 6, 7, 21)
    # dust and thin scratches: small bright/dark features that stand out from their surroundings
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    spots = cv2.max(cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, k), cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, k))
    _, mask = cv2.threshold(spots, 40, 255, cv2.THRESH_BINARY)
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8))
    report["dust_pixels_fixed"] = int((mask > 0).sum())
    if report["dust_pixels_fixed"]:
        img = cv2.inpaint(img, mask, 3, cv2.INPAINT_TELEA)
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    lab[..., 0] = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(lab[..., 0])
    img = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    if max(w, h) < 1600:
        f = min(2.0, 1600 / max(w, h))
        img = cv2.resize(img, None, fx=f, fy=f, interpolation=cv2.INTER_LANCZOS4)
    blur = cv2.GaussianBlur(img, (0, 0), 1.2)
    img = cv2.addWeighted(img, 1.5, blur, -0.5, 0)
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise PhotoError("The restored photo could not be saved.")
    buf.tofile(dest)
    report["size_after"] = [img.shape[1], img.shape[0]]
    return report
