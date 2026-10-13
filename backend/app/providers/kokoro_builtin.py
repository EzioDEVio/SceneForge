"""Kokoro voices built into SceneForge (0.9.4-beta.3): no Docker, no separate app.

Kokoro-82M (Apache-2.0) runs through kokoro-onnx (MIT) and ONNX Runtime on the CPU.
The int8 model (about 92 MB) and the voice pack (about 28 MB) download once from the
kokoro-onnx GitHub release into the SceneForge model folder and are checked against
pinned SHA-256 digests. Pronunciation uses the espeak-ng copy bundled by espeakng-loader.
"""
from __future__ import annotations

import hashlib
import io
import os
import threading
import wave
from pathlib import Path

import requests

RELEASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
FILES = {
    "kokoro-v1.0.int8.onnx": ("6e742170d309016e5891a994e1ce1559c702a2ccd0075e67ef7157974f6406cb", 92_361_271),
    "voices-v1.0.bin": ("bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d", 28_214_398),
}
DOWNLOAD_MB = round(sum(size for _, size in FILES.values()) / 1_000_000)

# Voice id prefix → language (Kokoro's naming: a=American, b=British, e=Spanish, f=French,
# h=Hindi, i=Italian, p=Brazilian Portuguese). Japanese and Chinese need extra g2p
# packages for good results and are left out.
LANGS = {"a": ("en", "en-us", "English (US)"), "b": ("en", "en-gb", "English (UK)"), "e": ("es", "es", "Spanish"),
         "f": ("fr", "fr-fr", "French"), "h": ("hi", "hi", "Hindi"), "i": ("it", "it", "Italian"),
         "p": ("pt", "pt-br", "Portuguese (Brazil)")}
LANGUAGES = sorted({code for code, _, _ in LANGS.values()})

_lock = threading.Lock()
_engine = None
_progress = {"state": "idle", "done": 0, "total": sum(size for _, size in FILES.values()), "error": ""}


class KokoroError(ValueError):
    pass


def model_dir() -> Path:
    # Next to the Whisper model (…/.sceneforge/models/kokoro), overridable for tests.
    if os.environ.get("SCENEFORGE_KOKORO_DIR"):
        return Path(os.environ["SCENEFORGE_KOKORO_DIR"])
    from app.providers.transcribe import model_dir as whisper_dir
    return whisper_dir().parent / "kokoro"


def installed() -> bool:
    folder = model_dir()
    return all((folder / name).is_file() and (folder / name).stat().st_size == size for name, (_, size) in FILES.items())


def status() -> dict:
    return {"installed": installed(), "download_mb": DOWNLOAD_MB, "languages": LANGUAGES, **_progress}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(report=None) -> None:
    """Fetch and verify the model files (resumes nothing; small enough to fetch whole)."""
    folder = model_dir()
    folder.mkdir(parents=True, exist_ok=True)
    _progress.update(state="downloading", done=0, error="")
    try:
        with requests.Session() as http:
            for name, (digest, size) in FILES.items():
                target = folder / name
                if target.is_file() and target.stat().st_size == size and _sha256(target) == digest:
                    _progress["done"] += size
                    continue
                part = target.with_suffix(target.suffix + ".part")
                if report:
                    report(f"Downloading Kokoro {name} ({size / 1_000_000:.0f} MB).")
                with http.get(RELEASE + name, stream=True, timeout=(15, 120)) as r:
                    r.raise_for_status()
                    with part.open("wb") as out:
                        for chunk in r.iter_content(1 << 20):
                            out.write(chunk)
                            _progress["done"] += len(chunk)
                if _sha256(part) != digest:
                    part.unlink(missing_ok=True)
                    raise KokoroError(f"The downloaded {name} did not match its checksum and was discarded. Try again.")
                part.replace(target)
        _progress.update(state="ready")
    except requests.RequestException as e:
        _progress.update(state="error", error="Could not download the Kokoro voice model. Check the internet connection and try again.")
        raise KokoroError(_progress["error"]) from e
    except KokoroError as e:
        _progress.update(state="error", error=str(e))
        raise


def _load():
    global _engine
    if _engine is None:
        with _lock:
            if _engine is None:
                if not installed():
                    raise KokoroError(f"The built-in Kokoro voices are not downloaded yet ({DOWNLOAD_MB} MB). "
                                      "Click Install next to Kokoro in AI Engines, or Download voices in Voice & narration.")
                try:
                    from kokoro_onnx import Kokoro
                except (ImportError, OSError) as e:
                    raise KokoroError(f"Kokoro could not start on this computer ({e}). Reinstall or update SceneForge.") from e
                folder = model_dir()
                _engine = Kokoro(str(folder / "kokoro-v1.0.int8.onnx"), str(folder / "voices-v1.0.bin"))
    return _engine


def voice_details() -> list[dict]:
    voices = _load().get_voices() if installed() else []
    out = []
    for v in voices:
        lang = LANGS.get(v[:1])
        if not lang:
            continue
        gender = {"f": "female", "m": "male"}.get(v[1:2], "")
        out.append({"id": v, "name": v.split("_", 1)[-1].replace("_", " ").title(), "language": lang[0],
                    "accent": lang[2], "gender": gender, "age": "", "description": "", "preview_url": ""})
    return out


def synthesize(text: str, voice: str, language: str, speed: float) -> bytes:
    lang = LANGS.get((voice or "")[:1])
    if not lang:
        raise KokoroError("Choose a Kokoro voice.")
    if language and language != lang[0]:
        raise KokoroError(f"The voice {voice} speaks {lang[2]}. Pick a {language} voice or change the language.")
    if any("؀" <= c <= "ۿ" for c in text):
        raise KokoroError("Kokoro does not speak Arabic. Use Chatterbox or Gemini voices for Arabic narration.")
    if not 0.5 <= speed <= 2.0:
        raise KokoroError("Speaking speed must be between 0.5 and 2.0.")
    import numpy as np
    engine = _load()
    with _lock:   # ONNX Runtime sessions are thread-safe, but one narration at a time keeps CPU use sane.
        samples, rate = engine.create(text, voice=voice, speed=float(speed), lang=lang[1])
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2").tobytes()
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buffer.getvalue()
