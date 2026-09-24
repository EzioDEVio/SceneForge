"""Colour grading baked into a single 3D LUT.

Every per-pixel colour control (exposure, highlights, shadows, contrast,
saturation, vibrance, temperature, tint) and an imported .cube LUT with its
strength are composed in NumPy into one 33^3 table, which FFmpeg applies with
a single lut3d pass. That is several times faster than chaining the matching
FFmpeg filters, and the result is identical wherever it is rendered.
Spatial controls (sharpen, vignette, grain) cannot live in a LUT and stay as
filters (see filters.build_adjust_chain).
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from pathlib import Path

import numpy as np

GRID = 33
MAX_CUBE_BYTES = 12 * 1024 * 1024
COLOR_KEYS = ("exposure", "highlights", "shadows", "contrast", "saturation", "vibrance", "temperature", "tint")
_LUMA = np.array([0.2126, 0.7152, 0.0722])
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


class CubeError(ValueError):
    pass


def parse_cube(text: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Parse and validate an Adobe/Resolve .cube 3D LUT.

    Returns (table[b, g, r, 3], domain_min[3], domain_max[3]). Red varies
    fastest in the file, as the format requires.
    """
    size = None
    dmin, dmax = np.zeros(3), np.ones(3)
    rows: list[list[float]] = []
    text = text.lstrip("\ufeff")  # byte-order mark written by some Windows tools
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        head = line.split()[0].upper()
        if head == "TITLE":
            continue
        if head == "LUT_1D_SIZE":
            raise CubeError("This is a 1D LUT. SceneForge supports 3D .cube LUTs (LUT_3D_SIZE).")
        if head == "LUT_3D_SIZE":
            try:
                size = int(line.split()[1])
            except (IndexError, ValueError):
                raise CubeError("LUT_3D_SIZE is not a whole number.") from None
            if not 2 <= size <= 65:
                raise CubeError("LUT_3D_SIZE must be between 2 and 65.")
            continue
        if head == "LUT_3D_INPUT_RANGE":
            # Resolve/Premiere variant of DOMAIN_MIN/MAX: one range for all channels.
            try:
                lo, hi = (float(v) for v in line.split()[1:3])
            except ValueError:
                raise CubeError("LUT_3D_INPUT_RANGE must contain two numbers.") from None
            dmin, dmax = np.full(3, lo), np.full(3, hi)
            continue
        if head in ("DOMAIN_MIN", "DOMAIN_MAX"):
            try:
                values = np.array([float(v) for v in line.split()[1:4]])
            except ValueError:
                raise CubeError(f"{head} must contain three numbers.") from None
            if values.size != 3:
                raise CubeError(f"{head} must contain three numbers.")
            if head == "DOMAIN_MIN":
                dmin = values
            else:
                dmax = values
            continue
        if head.isalpha() or "_" in head:
            continue  # other keywords (e.g. LUT_IN_VIDEO_RANGE) are informational
        parts = line.split()
        if len(parts) != 3:
            raise CubeError("Each LUT entry must contain exactly three numbers.")
        try:
            rows.append([float(v) for v in parts])
        except ValueError:
            raise CubeError("The LUT contains a value that is not a number.") from None
    if size is None:
        raise CubeError("Missing LUT_3D_SIZE. Is this a 3D .cube file?")
    if len(rows) != size ** 3:
        raise CubeError(f"Expected {size ** 3} entries for a {size}-point LUT, found {len(rows)}.")
    if np.any(dmax <= dmin):
        raise CubeError("DOMAIN_MAX must be greater than DOMAIN_MIN.")
    table = np.asarray(rows, dtype=np.float64)
    if not np.all(np.isfinite(table)):
        raise CubeError("The LUT contains non-finite values.")
    return table.reshape(size, size, size, 3), dmin, dmax


def decode_cube(data: bytes) -> str:
    """.cube files are ASCII by spec, but titles and comments from real tools
    may be UTF-8 (with or without BOM) or Latin-1."""
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def sample_cube(rgb: np.ndarray, table: np.ndarray, dmin: np.ndarray, dmax: np.ndarray) -> np.ndarray:
    """Trilinear lookup of rgb (N,3 in 0..1) through table[b, g, r]."""
    n = table.shape[0]
    x = np.clip((rgb - dmin) / (dmax - dmin), 0, 1) * (n - 1)
    i0 = np.floor(x).astype(int).clip(0, n - 2)
    f = x - i0
    r0, g0, b0 = i0[:, 0], i0[:, 1], i0[:, 2]
    fr, fg, fb = f[:, 0:1], f[:, 1:2], f[:, 2:3]
    out = np.zeros_like(rgb)
    for db in (0, 1):
        wb = fb if db else 1 - fb
        for dg in (0, 1):
            wg = fg if dg else 1 - fg
            for dr in (0, 1):
                wr = fr if dr else 1 - fr
                out += wb * wg * wr * table[b0 + db, g0 + dg, r0 + dr]
    return out


def _to_linear(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _to_srgb(c):
    c = np.clip(c, 0, None)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def apply_adjustments(rgb: np.ndarray, a: dict) -> np.ndarray:
    """rgb: (N,3) sRGB 0..1. `a` holds the COLOR_KEYS in -100..100."""
    v = {k: a.get(k, 0) / 100 for k in COLOR_KEYS}
    if v["exposure"] or v["temperature"] or v["tint"]:
        lin = _to_linear(rgb)
        lin = lin * 2 ** (1.5 * v["exposure"])                    # ±1.5 EV
        # White balance as channel gains, normalised to keep luminance.
        gain = np.array([1 + 0.28 * v["temperature"], 1 - 0.22 * v["tint"], 1 - 0.28 * v["temperature"]])
        gain = gain / float(_LUMA @ gain)
        rgb = _to_srgb(lin * gain)
    if v["shadows"] or v["highlights"]:
        # Smooth bumps centred low / high, zero at black and white.
        x = np.clip(rgb, 0, 1)
        rgb = x + 0.6 * v["shadows"] * x * (1 - x) ** 2 * 27 / 4 / 3 \
                + 0.6 * v["highlights"] * x ** 2 * (1 - x) * 27 / 4 / 3
    if v["contrast"]:
        rgb = (rgb - 0.5) * (1 + v["contrast"]) + 0.5
    if v["saturation"] or v["vibrance"]:
        luma = (rgb @ _LUMA)[:, None]
        chroma = rgb - luma
        factor = 1 + v["saturation"]
        if v["vibrance"]:
            current = np.clip(rgb.max(axis=1) - rgb.min(axis=1), 0, 1)[:, None]
            factor = factor * (1 + v["vibrance"] * (1 - current))
        rgb = luma + chroma * np.maximum(factor, 0)
    return np.clip(rgb, 0, 1)


def grade_is_active(adjust: dict | None, lut_path: str | None, lut_strength: int) -> bool:
    return bool((lut_path and lut_strength > 0) or any((adjust or {}).get(k) for k in COLOR_KEYS))


def build_grade_lut(adjust: dict | None, lut_path: str | None, lut_strength: int, out_dir: Path) -> str | None:
    """Write (or reuse) the combined grade LUT and return its path."""
    adjust = {k: int((adjust or {}).get(k, 0)) for k in COLOR_KEYS}
    lut_strength = max(0, min(100, int(lut_strength)))
    if not grade_is_active(adjust, lut_path, lut_strength):
        return None
    lut_bytes = Path(lut_path).read_bytes() if lut_path and lut_strength else b""
    key = hashlib.sha256(json.dumps([adjust, lut_strength, GRID]).encode() + lut_bytes).hexdigest()[:24]
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"grade_{key}.cube"
    with _locks_guard:
        lock = _locks.setdefault(key, threading.Lock())
    # Preview requests and renders may ask for the same grade at once: one
    # builds it, the others wait and reuse it.
    with lock:
        if out.exists():
            return str(out)
        _write_grade(out, adjust, lut_bytes, lut_strength)
    return str(out)


def _write_grade(out: Path, adjust: dict, lut_bytes: bytes, lut_strength: int) -> None:
    g = np.linspace(0, 1, GRID)
    b, gg, r = np.meshgrid(g, g, g, indexing="ij")
    rgb = np.stack([r, gg, b], axis=-1).reshape(-1, 3)
    graded = apply_adjustments(rgb, adjust)
    if lut_bytes:
        table, dmin, dmax = parse_cube(decode_cube(lut_bytes))
        looked = np.clip(sample_cube(graded, table, dmin, dmax), 0, 1)
        s = lut_strength / 100
        graded = graded * (1 - s) + looked * s
    tmp = out.with_name(f"{out.stem}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
    with open(tmp, "w", encoding="ascii") as fh:
        fh.write(f"TITLE \"SceneForge grade\"\nLUT_3D_SIZE {GRID}\n")
        np.savetxt(fh, graded, fmt="%.6f")
    os.replace(tmp, out)
