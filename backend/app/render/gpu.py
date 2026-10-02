"""Hardware (GPU) video encoders for export delivery.

Detection (cached for the life of the backend, started in the background at startup):
  1. `ffmpeg -hide_banner -encoders` lists what the FFmpeg build was compiled with;
  2. every listed candidate gets a real 1-frame test encode, because a build can list h264_nvenc
     on a PC without an NVIDIA GPU or driver;
  3. the GPU name comes from `nvidia-smi` when it is present (display only).

Export settings carry encoder = "auto" | "cpu" | "gpu". auto uses NVENC when its test encode
worked, otherwise libx264/libx265. Only the final MP4 delivery (H.264 / H.265) uses the GPU; the
scene parts and the master stay on the CPU (they are short, filter-bound renders whose output is
re-encoded anyway, so a GPU there would save little and add risk). QSV and AMF encoders are
detected and reported but not used for export yet. A GPU encode that fails for any reason is
retried on the CPU and reported as a warning: the GPU never makes an export fail.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

CANDIDATES = {
    "h264_nvenc": ("nvidia", "h264"), "hevc_nvenc": ("nvidia", "hevc"),
    "h264_qsv": ("intel", "h264"), "hevc_qsv": ("intel", "hevc"),
    "h264_amf": ("amd", "h264"), "hevc_amf": ("amd", "hevc"),
}
USED_FOR_EXPORT = ("h264_nvenc", "hevc_nvenc")
CHOICES = ("auto", "cpu", "gpu")
GPU_FORMATS = {"mp4_h264": "h264_nvenc", "mp4_h265": "hevc_nvenc"}
NVENC_PRESET = ("p4", "p5", "p6", "p7")            # draft, standard, high, max
NVENC_CQ = {"h264_nvenc": (28, 23, 20, 17), "hevc_nvenc": (30, 26, 23, 20)}

_cache: dict | None = None
_lock = threading.Lock()


def _flags() -> int:
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0  # type: ignore[attr-defined]


def parse_encoders(text: str) -> set[str]:
    """Video encoder names from `ffmpeg -encoders` output (lines like ' V....D h264_nvenc  NVIDIA ...')."""
    names = set()
    for line in text.splitlines():
        m = re.match(r"^\s*V[A-Z.]{5}\s+(\S+)\s", line)
        if m and m.group(1) != "=":
            names.add(m.group(1))
    return names


def test_encode_args(ffmpeg_bin: str, encoder: str) -> list[str]:
    return [ffmpeg_bin, "-hide_banner", "-nostdin", "-loglevel", "error", "-f", "lavfi",
            "-i", "color=c=black:s=256x256:r=25:d=0.04", "-frames:v", "1", "-pix_fmt", "yuv420p",
            "-c:v", encoder, "-f", "null", "-"]


def _gpu_name(run) -> str | None:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        p = run([exe, "--query-gpu=name", "--format=csv,noheader"], capture_output=True, text=True, timeout=5,
                creationflags=_flags())
        name = (p.stdout or "").strip().splitlines()
        return name[0].strip() if p.returncode == 0 and name else None
    except Exception:  # noqa: BLE001
        return None


def detect(ffmpeg_bin: str | None = None, refresh: bool = False, run=subprocess.run) -> dict:
    """Detected encoders (cached). `run` is injectable for tests."""
    global _cache
    with _lock:
        if _cache is not None and not refresh:
            return _cache
        if ffmpeg_bin is None:
            from app.config import FFMPEG_BIN as ffmpeg_bin  # noqa: N811
        result: dict = {"checked_at": time.time(), "ffmpeg_ok": True, "encoders": {}, "notes": []}
        try:
            p = run([ffmpeg_bin, "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=20,
                    creationflags=_flags())
            listed = parse_encoders(p.stdout or "")
        except Exception as e:  # noqa: BLE001
            listed = set()
            result["ffmpeg_ok"] = False
            result["notes"].append(f"Could not list FFmpeg encoders: {type(e).__name__}")
        for name, (vendor, codec) in CANDIDATES.items():
            entry = {"vendor": vendor, "codec": codec, "listed": name in listed, "works": False, "error": None,
                     "used_for_export": name in USED_FOR_EXPORT}
            if entry["listed"]:
                try:
                    t = run(test_encode_args(ffmpeg_bin, name), capture_output=True, text=True, timeout=30,
                            creationflags=_flags())
                    entry["works"] = t.returncode == 0
                    if not entry["works"]:
                        entry["error"] = (t.stderr or "").strip()[-300:] or f"exit code {t.returncode}"
                except Exception as e:  # noqa: BLE001
                    entry["error"] = f"test encode failed: {type(e).__name__}"
            result["encoders"][name] = entry
        enc = result["encoders"]
        h264 = "h264_nvenc" if enc["h264_nvenc"]["works"] else None
        hevc = "hevc_nvenc" if enc["hevc_nvenc"]["works"] else None
        result["gpu"] = {"available": bool(h264 or hevc), "vendor": "nvidia" if (h264 or hevc) else None,
                         "name": _gpu_name(run) if (h264 or hevc) else None, "h264": h264, "hevc": hevc}
        others = [n for n, e in enc.items() if e["works"] and n not in USED_FOR_EXPORT]
        if others:
            result["notes"].append("Also detected (not used for export yet): " + ", ".join(others))
        if not result["gpu"]["available"]:
            result["notes"].append("No working NVIDIA NVENC encoder; exports use the CPU (libx264 / libx265).")
        _cache = result
        return result


def set_cache(value: dict | None) -> None:
    """Replace the cached detection (tests, or after a driver change with refresh)."""
    global _cache
    with _lock:
        _cache = value


def detect_in_background() -> None:
    threading.Thread(target=lambda: _safe_detect(), daemon=True, name="gpu-encoder-detect").start()


def _safe_detect() -> None:
    try:
        detect()
    except Exception:  # noqa: BLE001
        pass


def resolve(choice: str, fmt: str, info: dict | None = None) -> tuple[str | None, str | None]:
    """(gpu encoder name or None for CPU, warning or None) for an export."""
    if fmt not in GPU_FORMATS or choice == "cpu":
        if choice == "gpu" and fmt not in GPU_FORMATS:
            return None, f"GPU encoding is only used for MP4 (H.264 / H.265); {fmt} was encoded on the CPU."
        return None, None
    info = info if info is not None else detect()
    wanted = GPU_FORMATS[fmt]
    entry = (info.get("encoders") or {}).get(wanted) or {}
    if entry.get("works"):
        return wanted, None
    if choice == "gpu":
        return None, f"No working GPU encoder ({wanted}) was found, so this export was encoded on the CPU."
    return None, None


def nvenc_args(encoder: str, quality_index: int) -> list[str]:
    q = max(0, min(3, quality_index))
    cq = NVENC_CQ.get(encoder, NVENC_CQ["h264_nvenc"])[q]
    return ["-c:v", encoder, "-preset", NVENC_PRESET[q], "-tune", "hq", "-rc", "vbr", "-cq", str(cq), "-b:v", "0",
            "-spatial-aq", "1"]


def to_gpu_args(cpu_args: list[str], encoder: str, quality_index: int) -> list[str]:
    """Swap the CPU video codec section (-c:v libx26x -preset .. -crf ..) of a delivery command for
    the GPU one; pixel format (yuv420p), profile/hvc1 tag, faststart and audio stay as they are."""
    i = cpu_args.index("-c:v")
    j = cpu_args.index("-pix_fmt", i)
    rest = list(cpu_args[j:])
    if "-x265-params" in rest:
        k = rest.index("-x265-params")
        del rest[k:k + 2]
    return cpu_args[:i] + nvenc_args(encoder, quality_index) + rest


def deliver_with_fallback(cpu_args: list[str], settings: dict, quality_index: int, out: str, encode,
                          cancel_check=None, warnings: list | None = None, info: dict | None = None) -> str:
    """Run the delivery encode: GPU first when chosen/available, CPU on any GPU failure."""
    warn = warnings if warnings is not None else []
    choice = settings.get("encoder", "auto")
    try:
        encoder, note = resolve(choice, settings.get("format", ""), info)
    except Exception as e:  # noqa: BLE001 - detection trouble must never fail an export
        encoder, note = None, f"GPU detection failed ({type(e).__name__}); exported on the CPU."
    if note:
        warn.append(note)
    if encoder:
        try:
            return encode(to_gpu_args(cpu_args, encoder, quality_index), out, cancel_check)
        except Exception as e:  # noqa: BLE001
            if str(e) == "cancelled":
                raise
            Path(out).unlink(missing_ok=True)
            detail = str(e).strip().splitlines()[-1][-200:] if str(e).strip() else type(e).__name__
            warn.append(f"The GPU encoder ({encoder}) failed, so the export was encoded on the CPU instead. ({detail})")
    return encode(cpu_args, out, cancel_check)
