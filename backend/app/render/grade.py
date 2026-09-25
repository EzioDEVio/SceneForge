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
# A 65-point 3D table (274,625 rows) plus a 65,536-row 1D shaper, written
# with long decimals as some camera vendors do, stays well under this.
MAX_CUBE_BYTES = 32 * 1024 * 1024
COLOR_KEYS = ("exposure", "highlights", "shadows", "contrast", "saturation", "vibrance", "temperature", "tint")
_LUMA = np.array([0.2126, 0.7152, 0.0722])
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


class CubeError(ValueError):
    pass


class Lut:
    """A parsed .cube: optional 1D curve (per channel), optional 3D table.

    Supports the three layouts found in the wild, including DaVinci Resolve's
    own LUT folder:
      * 3D only (LUT_3D_SIZE)
      * 1D only (LUT_1D_SIZE), e.g. gamma/log conversions
      * 1D "shaper" + 3D (both sizes), Resolve's HDR/ACES format: the 1D rows
        come first and reshape the input before the 3D lookup.
    """

    def __init__(self, shaper, shaper_range, table, domain):
        self.shaper = shaper              # (n, 3) or None
        self.shaper_range = shaper_range  # (lo[3], hi[3])
        self.table = table                # (n, n, n, 3) indexed [b, g, r] or None
        self.domain = domain              # (lo[3], hi[3]) for the 3D table

    @property
    def kind(self) -> str:
        if self.shaper is not None and self.table is not None:
            return "1D shaper + 3D"
        return "3D" if self.table is not None else "1D"

    @property
    def size(self) -> int:
        return self.table.shape[0] if self.table is not None else self.shaper.shape[0]

    def apply(self, rgb: np.ndarray) -> np.ndarray:
        out = rgb
        if self.shaper is not None:
            lo, hi = self.shaper_range
            x = np.clip((out - lo) / (hi - lo), 0, 1)
            grid = np.linspace(0, 1, self.shaper.shape[0])
            out = np.stack([np.interp(x[:, c], grid, self.shaper[:, c]) for c in range(3)], axis=1)
        if self.table is not None:
            out = sample_cube(out, self.table, *self.domain)
        return out


def _three(line: str, head: str) -> np.ndarray:
    try:
        values = np.array([float(v) for v in line.split()[1:4]])
    except ValueError:
        raise CubeError(f"{head} must contain three numbers.") from None
    if values.size != 3:
        raise CubeError(f"{head} must contain three numbers.")
    return values


def parse_lut(text: str) -> Lut:
    """Parse and validate a .cube file (see Lut for supported layouts)."""
    size1 = size3 = None
    r1 = (np.zeros(3), np.ones(3))
    r3 = [np.zeros(3), np.ones(3)]
    rows: list[list[float]] = []
    text = text.lstrip("\ufeff")  # byte-order mark written by some Windows tools
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        head = line.split()[0].upper()
        if head == "TITLE":
            continue
        if head in ("LUT_1D_SIZE", "LUT_3D_SIZE"):
            try:
                n = int(line.split()[1])
            except (IndexError, ValueError):
                raise CubeError(f"{head} is not a whole number.") from None
            if head == "LUT_3D_SIZE":
                if not 2 <= n <= 65:
                    raise CubeError("LUT_3D_SIZE must be between 2 and 65.")
                size3 = n
            else:
                if not 2 <= n <= 65536:
                    raise CubeError("LUT_1D_SIZE must be between 2 and 65536.")
                size1 = n
            continue
        if head in ("LUT_1D_INPUT_RANGE", "LUT_3D_INPUT_RANGE"):
            # Resolve/Premiere: one range for all channels.
            try:
                lo, hi = (float(v) for v in line.split()[1:3])
            except ValueError:
                raise CubeError(f"{head} must contain two numbers.") from None
            rng = (np.full(3, lo), np.full(3, hi))
            if head == "LUT_1D_INPUT_RANGE":
                r1 = rng
            else:
                r3 = list(rng)
            continue
        if head == "DOMAIN_MIN":
            r3[0] = _three(line, head)
            continue
        if head == "DOMAIN_MAX":
            r3[1] = _three(line, head)
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
    if size1 is None and size3 is None:
        raise CubeError("Missing LUT_3D_SIZE or LUT_1D_SIZE. Is this a .cube LUT?")
    expected = (size1 or 0) + (size3 or 0) ** 3
    if len(rows) != expected:
        raise CubeError(f"Expected {expected} entries, found {len(rows)}.")
    data = np.asarray(rows, dtype=np.float64)
    if not np.all(np.isfinite(data)):
        raise CubeError("The LUT contains non-finite values.")
    for lo, hi in (r1, r3):
        if np.any(hi <= lo):
            raise CubeError("The LUT input range maximum must be greater than its minimum.")
    shaper = data[:size1] if size1 else None
    table = data[size1 or 0:].reshape(size3, size3, size3, 3) if size3 else None
    return Lut(shaper, r1, table, (r3[0], r3[1]))


def parse_cube(text: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """3D-only view used by older callers: (table[b, g, r, 3], dmin, dmax)."""
    lut = parse_lut(text)
    if lut.table is None or lut.shaper is not None:
        raise CubeError("This is a 1D or shaper LUT; use parse_lut().")
    return lut.table, lut.domain[0], lut.domain[1]


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


def grade_is_active(adjust: dict | None, lut_path: str | None, lut_strength: int, tone: dict | None = None) -> bool:
    return bool((lut_path and lut_strength > 0) or any((adjust or {}).get(k) for k in COLOR_KEYS) or (tone or {}).get("amount"))


def apply_split_tone(rgb: np.ndarray, tone: dict | None) -> np.ndarray:
    """Tint shadows and highlights with two colours (Lightroom-style split
    toning). Balance moves the crossover point; luminance is preserved."""
    if not tone or not tone.get("amount"):
        return rgb
    def col(h):
        return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], dtype=np.float64) / 255
    amt = tone["amount"] / 100 * 0.5
    pivot = 0.5 + 0.35 * tone.get("balance", 0) / 100
    luma = (rgb @ _LUMA)[:, None]
    w_hi = np.clip((luma - pivot) / (1 - pivot + 1e-6), 0, 1) ** 0.8
    w_sh = np.clip((pivot - luma) / (pivot + 1e-6), 0, 1) ** 0.8
    shifted = rgb + amt * (w_sh * (col(tone["shadow"]) - 0.5) + w_hi * (col(tone["highlight"]) - 0.5))
    # keep brightness where it was
    shifted += luma - (shifted @ _LUMA)[:, None]
    return np.clip(shifted, 0, 1)


def build_grade_lut(adjust: dict | None, lut_path: str | None, lut_strength: int, out_dir: Path, tone: dict | None = None) -> str | None:
    """Write (or reuse) the combined grade LUT and return its path."""
    adjust = {k: int((adjust or {}).get(k, 0)) for k in COLOR_KEYS}
    lut_strength = max(0, min(100, int(lut_strength)))
    if not grade_is_active(adjust, lut_path, lut_strength, tone):
        return None
    lut_bytes = Path(lut_path).read_bytes() if lut_path and lut_strength else b""
    key = hashlib.sha256(json.dumps([adjust, lut_strength, GRID, tone or {}], sort_keys=True).encode() + lut_bytes).hexdigest()[:24]
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"grade_{key}.cube"
    with _locks_guard:
        lock = _locks.setdefault(key, threading.Lock())
    # Preview requests and renders may ask for the same grade at once: one
    # builds it, the others wait and reuse it.
    with lock:
        if out.exists():
            return str(out)
        _write_grade(out, adjust, lut_bytes, lut_strength, tone)
    return str(out)


def _write_grade(out: Path, adjust: dict, lut_bytes: bytes, lut_strength: int, tone: dict | None = None) -> None:
    g = np.linspace(0, 1, GRID)
    b, gg, r = np.meshgrid(g, g, g, indexing="ij")
    rgb = np.stack([r, gg, b], axis=-1).reshape(-1, 3)
    graded = apply_adjustments(rgb, adjust)
    if lut_bytes:
        looked = np.clip(parse_lut(decode_cube(lut_bytes)).apply(graded), 0, 1)
        s = lut_strength / 100
        graded = graded * (1 - s) + looked * s
    graded = apply_split_tone(graded, tone)
    tmp = out.with_name(f"{out.stem}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
    with open(tmp, "w", encoding="ascii") as fh:
        fh.write(f"TITLE \"SceneForge grade\"\nLUT_3D_SIZE {GRID}\n")
        np.savetxt(fh, graded, fmt="%.6f")
    os.replace(tmp, out)
