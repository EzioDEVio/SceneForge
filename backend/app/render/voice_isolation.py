"""AI voice isolation (dialogue isolation) with a local MDX-Net ONNX model.

Model: "Kim_Vocal_2.onnx" (MDX-Net vocal model by Kimberley Jensen), the ONNX file
published in the Ultimate Vocal Remover model repository (TRvlvr/model_repo) on
GitHub releases. Ultimate Vocal Remover and python-audio-separator, which ship and
run this model, are MIT-licensed; the weights themselves are distributed there
without a separate license file. It downloads once, on first use, into
~/.sceneforge/models/voice (or SCENEFORGE_VOICE_MODEL_DIR). The download is atomic:
written to <name>.partial, checked (size and MD5), then renamed.

Inference is the standard MDX-Net procedure used by UVR / python-audio-separator,
re-implemented with numpy + onnxruntime (CPU):
  44.1 kHz stereo -> chunks of hop*(dim_t-1) samples, overlapping, Hann-weighted
  overlap-add -> STFT (n_fft 7680, hop 1024, periodic Hann, centred/reflect pad)
  -> [L.re, L.im, R.re, R.im] x first dim_f (3072) bins -> model -> zero-pad the
  bins above dim_f -> iSTFT -> vocals * compensation (1.009 for Kim_Vocal_2).
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable

MODEL = {
    "file": "Kim_Vocal_2.onnx",
    "url": "https://github.com/TRvlvr/model_repo/releases/download/all_public_uvr_models/Kim_Vocal_2.onnx",
    "md5": "fa29b9d118ba4ad14a000254a60114b8",
    "bytes": 66_759_214,
    "approx_mb": 67,
    "label": "MDX-Net Kim Vocal 2",
    "license": "Distributed with Ultimate Vocal Remover (MIT); model by Kimberley Jensen",
    "compensate": 1.009,
    "n_fft": 7680,
    "hop": 1024,
    "dim_f": 3072,
    "dim_t": 256,
}
SAMPLE_RATE = 44100
OUT_RATE = 48000
OVERLAP = 0.25
MAX_SECONDS = 3 * 60 * 60

_lock = threading.Lock()
_session_lock = threading.Lock()
_sessions: dict[str, object] = {}
_progress: dict[str, dict] = {}


class VoiceIsolationError(RuntimeError):
    pass


def model_dir() -> Path:
    return Path(os.environ.get("SCENEFORGE_VOICE_MODEL_DIR", Path.home() / ".sceneforge" / "models" / "voice"))


def model_path() -> Path:
    return model_dir() / MODEL["file"]


def _is_ready(p: Path) -> bool:
    return p.is_file() and p.stat().st_size == MODEL["bytes"]


def status() -> dict:
    p = model_path()
    ok = _is_ready(p)
    return {"folder": str(model_dir()), "file": MODEL["file"], "label": MODEL["label"], "url": MODEL["url"],
            "approx_mb": MODEL["approx_mb"], "bytes": p.stat().st_size if ok else 0, "expected_bytes": MODEL["bytes"],
            "downloaded": ok, "download": _progress.get("model"), "license": MODEL["license"],
            "source": "github.com (Ultimate Vocal Remover model repository)"}


def _md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_model() -> Path:
    """Return the model path, downloading it on first use (atomic, verified)."""
    dest = model_path()
    with _lock:
        if _is_ready(dest):
            return dest
        import requests
        folder = dest.parent
        partial = dest.with_name(dest.name + ".partial")
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise VoiceIsolationError(f"Could not create the models folder {folder}: {e}")
        _progress["model"] = {"done": 0, "total": MODEL["bytes"]}
        try:
            with requests.get(MODEL["url"], stream=True, timeout=(15, 60)) as r:
                r.raise_for_status()
                with open(partial, "wb") as fh:
                    for chunk in r.iter_content(1 << 20):
                        fh.write(chunk)
                        _progress["model"]["done"] += len(chunk)
            if partial.stat().st_size != MODEL["bytes"]:
                raise VoiceIsolationError("the downloaded file has the wrong size")
            if _md5(partial) != MODEL["md5"]:
                raise VoiceIsolationError("the downloaded file failed its checksum")
            os.replace(partial, dest)
        except Exception as e:
            partial.unlink(missing_ok=True)
            reason = str(e) if isinstance(e, VoiceIsolationError) else type(e).__name__
            raise VoiceIsolationError(
                f"Could not download the voice isolation model ({MODEL['file']}, ~{MODEL['approx_mb']} MB) from github.com: {reason}. "
                f"Check your internet connection and try again, or download {MODEL['url']} yourself and place it in {folder}.")
        finally:
            _progress.pop("model", None)
    return dest


def _session():
    path = ensure_model()
    key = str(path)
    with _session_lock:
        if key not in _sessions:
            import onnxruntime as ort
            opts = ort.SessionOptions()
            opts.log_severity_level = 3
            try:
                _sessions[key] = ort.InferenceSession(key, sess_options=opts, providers=["CPUExecutionProvider"])
            except Exception as e:
                raise VoiceIsolationError(f"The voice isolation model in {path.parent} could not be loaded ({e}). "
                                          f"Delete {path.name} there and try again to re-download it.")
        return _sessions[key]


# ---------------------------------------------------------------- STFT (torch.stft compatible)

def _window(n_fft: int):
    import numpy as np
    return (0.5 - 0.5 * np.cos(2 * np.pi * np.arange(n_fft) / n_fft)).astype(np.float32)  # periodic Hann


def _stft(x, n_fft: int, hop: int):
    """x: [C, N] -> complex [C, n_fft//2+1, 1 + N//hop] (center=True, reflect pad)."""
    import numpy as np
    pad = n_fft // 2
    xp = np.pad(x, ((0, 0), (pad, pad)), mode="reflect")
    frames = 1 + (xp.shape[1] - n_fft) // hop
    idx = np.arange(n_fft)[None, :] + hop * np.arange(frames)[:, None]
    seg = xp[:, idx] * _window(n_fft)  # [C, T, n_fft]
    return np.fft.rfft(seg, axis=-1).transpose(0, 2, 1)


def _istft(spec, n_fft: int, hop: int, length: int):
    """complex [C, F, T] -> [C, length] (inverse of _stft, window-sum normalised)."""
    import numpy as np
    win = _window(n_fft)
    frames = np.fft.irfft(spec.transpose(0, 2, 1), n=n_fft, axis=-1) * win  # [C, T, n_fft]
    c, t, _ = frames.shape
    total = n_fft + hop * (t - 1)
    out = np.zeros((c, total), dtype=np.float64)
    norm = np.zeros(total, dtype=np.float64)
    w2 = win.astype(np.float64) ** 2
    for i in range(t):
        s = i * hop
        out[:, s:s + n_fft] += frames[:, i]
        norm[s:s + n_fft] += w2
    pad = n_fft // 2
    out = out[:, pad:pad + length]
    norm = norm[pad:pad + length]
    return (out / np.where(norm > 1e-8, norm, 1.0)).astype(np.float32)


def _run_chunk(sess, chunk):
    """chunk: float32 [2, chunk_size] -> isolated vocals [2, chunk_size]."""
    import numpy as np
    n_fft, hop, dim_f = MODEL["n_fft"], MODEL["hop"], MODEL["dim_f"]
    spec = _stft(chunk, n_fft, hop)                          # [2, 3841, 256]
    x = np.stack([spec.real, spec.imag], axis=1)              # [2, 2, F, T] (re/im per channel)
    x = x.reshape(4, spec.shape[1], spec.shape[2])[:, :dim_f].astype(np.float32)
    x[:, :3] = 0                                              # UVR zeroes the lowest bins
    y = sess.run(None, {sess.get_inputs()[0].name: x[None]})[0][0]  # [4, dim_f, T]
    full = np.zeros((4, spec.shape[1], spec.shape[2]), dtype=np.float32)
    full[:, :dim_f] = y
    full = full.reshape(2, 2, spec.shape[1], spec.shape[2])
    return _istft(full[:, 0] + 1j * full[:, 1], n_fft, hop, chunk.shape[1])


def separate(mix, progress: Callable[[float], None] | None = None, cancelled: Callable[[], bool] | None = None):
    """mix: float32 [2, N] at 44.1 kHz -> isolated voice [2, N]."""
    import numpy as np
    sess = _session()
    n_fft, hop, dim_t = MODEL["n_fft"], MODEL["hop"], MODEL["dim_t"]
    chunk_size = hop * (dim_t - 1)
    trim = n_fft // 2
    gen_size = chunk_size - 2 * trim
    n = mix.shape[1]
    pad = gen_size + trim - (n % gen_size)
    padded = np.concatenate([np.zeros((2, trim), np.float32), mix.astype(np.float32), np.zeros((2, pad), np.float32)], axis=1)
    step = int((1 - OVERLAP) * chunk_size)
    result = np.zeros(padded.shape, np.float64)
    divider = np.zeros(padded.shape[1], np.float64)
    win = np.hanning(chunk_size).astype(np.float64)
    starts = list(range(0, padded.shape[1], step))
    for k, start in enumerate(starts):
        if cancelled and cancelled():
            raise VoiceIsolationError("Voice isolation was cancelled.")
        end = min(start + chunk_size, padded.shape[1])
        part = padded[:, start:end]
        if part.shape[1] < chunk_size:
            part = np.pad(part, ((0, 0), (0, chunk_size - part.shape[1])))
        out = _run_chunk(sess, part)
        w = win[:end - start]
        result[:, start:end] += out[:, :end - start] * w
        divider[start:end] += w
        if progress:
            progress((k + 1) / len(starts))
    est = result / np.where(divider > 1e-8, divider, 1.0)
    return (est[:, trim:trim + n] * MODEL["compensate"]).astype(np.float32)


# ---------------------------------------------------------------- file I/O via ffmpeg

def _ffmpeg() -> str:
    from app.config import FFMPEG_BIN
    return FFMPEG_BIN


def read_audio(path: str, rate: int = SAMPLE_RATE):
    """Decode any audio/video file's first audio stream to float32 [2, N]."""
    import numpy as np
    cmd = [_ffmpeg(), "-v", "error", "-nostdin", "-i", path, "-vn", "-map", "0:a:0", "-ac", "2", "-ar", str(rate),
           "-f", "f32le", "-acodec", "pcm_f32le", "-"]
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=600)
    except FileNotFoundError:
        raise VoiceIsolationError("FFmpeg was not found. Install FFmpeg and try again.")
    if p.returncode != 0:
        raise VoiceIsolationError(f"This file's sound could not be read: {p.stderr.decode(errors='replace')[-300:].strip() or 'no audio stream'}")
    data = np.frombuffer(p.stdout, dtype=np.float32)
    if data.size < 2:
        raise VoiceIsolationError("This file has no sound to isolate.")
    return data[: data.size // 2 * 2].reshape(-1, 2).T.copy()


def write_wav(path: str, audio, in_rate: int = SAMPLE_RATE, out_rate: int = OUT_RATE) -> None:
    """Write float32 [2, N] as 16-bit PCM WAV at out_rate (resampled by ffmpeg)."""
    import numpy as np
    raw = np.ascontiguousarray(np.clip(audio, -1.0, 1.0).T.astype(np.float32)).tobytes()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    cmd = [_ffmpeg(), "-v", "error", "-nostdin", "-y", "-f", "f32le", "-ar", str(in_rate), "-ac", "2", "-i", "-",
           "-ar", str(out_rate), "-ac", "2", "-c:a", "pcm_s16le", path]
    p = subprocess.run(cmd, input=raw, capture_output=True, timeout=600)
    if p.returncode != 0:
        raise VoiceIsolationError(f"Could not write the isolated audio: {p.stderr.decode(errors='replace')[-300:]}")


def isolate_file(src: str, dest: str, strength: int = 100, progress: Callable[[float], None] | None = None,
                 cancelled: Callable[[], bool] | None = None) -> dict:
    """Isolate the voice in src (audio or video) and write a 48 kHz stereo WAV to dest.

    strength 0..100 blends the isolated voice with the original:
    out = iso + (1 - s) * (mix - iso)."""
    import numpy as np
    s = int(strength)
    if not 0 <= s <= 100:
        raise VoiceIsolationError("Strength must be between 0 and 100.")
    t0 = time.monotonic()
    mix = read_audio(src)
    seconds = mix.shape[1] / SAMPLE_RATE
    if seconds > MAX_SECONDS:
        raise VoiceIsolationError("This sound is longer than 3 hours. Split it before isolating the voice.")
    if s == 0:
        out = mix
    else:
        iso = separate(mix, progress, cancelled)
        out = iso + (1 - s / 100) * (mix - iso)
    peak = float(np.max(np.abs(out))) if out.size else 0.0
    if peak > 1.0:
        out = out / peak
    write_wav(dest, out)
    return {"seconds": round(seconds, 3), "elapsed": round(time.monotonic() - t0, 3)}
