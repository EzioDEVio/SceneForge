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


def _noise_sigma(gray: np.ndarray) -> float:
    """Immerkaer's fast noise estimate: the photo's own grain level."""
    cv2 = _cv2()
    kernel = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], np.float32)
    r = cv2.filter2D(gray.astype(np.float32), -1, kernel)[1:-1, 1:-1]
    return float(np.sqrt(np.pi / 2) * np.abs(r).mean() / 6)


def dust_mask(gray: np.ndarray, sigma: float, max_fraction: float = 0.005) -> np.ndarray:
    """Conservative dust detection. A pixel is only called dust when it is a
    tiny isolated speck that stands out strongly against a SMOOTH area (sky,
    smoke, walls). Anything inside texture (ground, clothing, foliage) is real
    detail and left alone. Never marks more than max_fraction of the photo."""
    cv2 = _cv2()
    med = cv2.medianBlur(gray, 5)
    diff = np.abs(gray.astype(np.int16) - med.astype(np.int16)).astype(np.float32)
    # local texture of the smoothed picture: dust in texture is not worth the risk
    m32 = med.astype(np.float32)
    local_std = np.sqrt(np.maximum(cv2.blur(m32 * m32, (15, 15)) - cv2.blur(m32, (15, 15)) ** 2, 0))
    cand = ((diff > max(35.0, 4.5 * sigma)) & (local_std < 10)).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(cand, connectivity=8)
    max_area = max(4, int(gray.size * 0.00002))
    keep = np.zeros(n, bool)
    strength = np.zeros(n, np.float32)
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if area <= max_area and w <= 7 and h <= 7:
            keep[i] = True
            strength[i] = diff[labels == i].max()
    # cap the total: keep only the strongest specks if there are too many
    budget = int(gray.size * max_fraction)
    order = np.argsort(-strength)
    total = 0
    for i in order:
        if not keep[i]:
            continue
        if total + stats[i][4] > budget:
            keep[i] = False
        else:
            total += stats[i][4]
    mask = keep[labels].astype(np.uint8) * 255
    return cv2.dilate(mask, np.ones((3, 3), np.uint8))


def restore_photo(src: str, dest: str) -> dict:
    """Careful restoration: remove isolated dust specks, reduce grain in
    proportion to the photo's measured noise, gently recover contrast, mildly
    sharpen and upscale small scans. Black-and-white photos stay black and
    white. When in doubt a pixel is left alone."""
    cv2 = _cv2()
    img = _load(src)
    h, w = img.shape[:2]
    mono = float(np.abs(img[..., 0].astype(np.int16) - img[..., 2]).mean()) < 3 and \
        float(np.abs(img[..., 1].astype(np.int16) - img[..., 2]).mean()) < 3
    work = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if mono else img
    gray = work if mono else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    sigma = _noise_sigma(gray)
    report = {"size_before": [w, h], "black_and_white": mono, "noise_level": round(sigma, 1)}
    # 1. dust first, on the original pixels
    mask = dust_mask(gray, sigma)
    report["dust_pixels_fixed"] = int((mask > 0).sum())
    report["dust_fraction"] = round(float((mask > 0).mean()), 5)
    if report["dust_pixels_fixed"]:
        work = cv2.inpaint(work, mask, 3, cv2.INPAINT_TELEA)
    # 2. grain reduction scaled to the measured noise (light touch keeps texture)
    hstr = float(np.clip(0.8 * sigma, 2.0, 10.0))
    work = cv2.fastNlMeansDenoising(work, None, hstr, 7, 21) if mono else \
        cv2.fastNlMeansDenoisingColored(work, None, hstr, hstr, 7, 21)
    # 3. gentle local contrast, blended back so it never looks processed
    if mono:
        eq = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8)).apply(work)
        work = cv2.addWeighted(work, 0.4, eq, 0.6, 0)
    else:
        lab = cv2.cvtColor(work, cv2.COLOR_BGR2LAB)
        eq = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8)).apply(lab[..., 0])
        lab[..., 0] = cv2.addWeighted(lab[..., 0], 0.4, eq, 0.6, 0)
        work = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    # 4. upscale small scans, then mild sharpening (small radius avoids halos)
    if max(w, h) < 1600:
        f = min(2.0, 1600 / max(w, h))
        work = cv2.resize(work, None, fx=f, fy=f, interpolation=cv2.INTER_LANCZOS4)
    blur = cv2.GaussianBlur(work, (0, 0), 1.0)
    work = cv2.addWeighted(work, 1.35, blur, -0.35, 0)
    ok, buf = cv2.imencode(".png", work)
    if not ok:
        raise PhotoError("The restored photo could not be saved.")
    buf.tofile(dest)
    report["size_after"] = [work.shape[1], work.shape[0]]
    return report
