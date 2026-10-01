"""Automatic captions: speech → text with word timing and language detection.

  ElevenLabs Speech to Text (Scribe v2): POST /v1/speech-to-text, word timestamps, language_code
  OpenAI Whisper (whisper-1): /v1/audio/transcriptions, verbose_json with word timestamps

Local Faster-Whisper is the default and needs no API key. Cloud providers remain optional.
Returns {"language": "en", "text": "...", "words": [[word, start_ms, end_ms], ...], "provider": ...}.
"""
from __future__ import annotations

import requests
import os
import subprocess
import tempfile
from pathlib import Path
from threading import Lock

from app.security.secrets import reveal

TIMEOUT = (10, 300)
# Plain HTTPS model downloads: the Xet transfer backend is a separate native client
# that proxies/antivirus on Windows often block, and symlinks need Developer Mode.
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
WHISPER_MODEL = "base"
_LOCAL_LOCK = Lock()
_LOCAL_MODEL = None


class TranscribeError(ValueError):
    pass


def _key(db, name: str) -> str | None:
    from app.db.models import ProviderProfile
    for p in db.query(ProviderProfile).filter(ProviderProfile.name == name).all():
        k = reveal(p.secret_ref or "")
        if k:
            return k
    return None


def available(db) -> list[str]:
    return ["local", *[n for n in ("elevenlabs", "openai") if _key(db, n)]]


def _normalize_local_audio(path: str, work_dir: str) -> str:
    """Give Faster-Whisper consistent mono 16 kHz input and lift quiet speech."""
    from app.config import FFMPEG_BIN
    target = Path(work_dir) / "whisper-input.wav"
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0  # type: ignore[attr-defined]
    args = [FFMPEG_BIN, "-y", "-hide_banner", "-nostdin", "-loglevel", "error", "-i", path,
            "-map", "0:a:0", "-vn", "-af", "dynaudnorm=f=150:g=15:p=0.95",
            "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(target)]
    subprocess.run(args, check=True, capture_output=True, timeout=300, creationflags=flags)
    return str(target)


def model_dir() -> Path:
    return Path(os.environ.get("SCENEFORGE_MODEL_DIR", Path.home() / ".sceneforge" / "models" / "whisper"))


def _load_local_model(WhisperModel):
    """Load (downloading once) the local model, recovering from the usual Windows failures:
    a half-downloaded cache from an interrupted first run, and CPUs or builds without int8."""
    folder = model_dir()
    folder.mkdir(parents=True, exist_ok=True)
    errors = []
    for attempt in ("int8", "reset", "float32"):
        if attempt == "reset":
            # A partial snapshot keeps failing forever; clear it and download again.
            reset_model_cache()
            folder.mkdir(parents=True, exist_ok=True)
        try:
            return WhisperModel(WHISPER_MODEL, device="cpu", compute_type="float32" if attempt == "float32" else "int8",
                                download_root=str(folder))
        except Exception as e:  # noqa: BLE001 - reported to the user below
            errors.append(f"{attempt}: {type(e).__name__}: {e}")
    raise TranscribeError("Could not download or start the local Whisper model. SceneForge needs internet access once "
                          f"to download it (about 145 MB) into {folder}. Details: " + " | ".join(errors)[-900:])


def reset_model_cache() -> bool:
    """Delete the downloaded local Whisper model so the next caption run downloads it again."""
    import shutil
    global _LOCAL_MODEL
    _LOCAL_MODEL = None
    folder = model_dir()
    if folder.exists():
        shutil.rmtree(folder, ignore_errors=True)
        return True
    return False


def diagnose() -> dict:
    """What local captions need, checked without downloading anything."""
    report: dict = {"model": WHISPER_MODEL, "model_dir": str(model_dir()), "checks": []}
    def add(name, ok, detail=""):
        report["checks"].append({"name": name, "ok": bool(ok), "detail": str(detail)[:400]})
    try:
        import ctranslate2
        add("CTranslate2 engine", True, f"version {ctranslate2.__version__}; CPU compute types: {', '.join(sorted(ctranslate2.get_supported_compute_types('cpu')))}")
    except Exception as e:  # noqa: BLE001
        add("CTranslate2 engine", False, f"{type(e).__name__}: {e}. On Windows this usually means the Microsoft Visual C++ Redistributable (x64) is missing.")
    try:
        import faster_whisper
        vad = Path(faster_whisper.__file__).parent / "assets"
        add("Faster-Whisper", True, f"version {getattr(faster_whisper, '__version__', '?')}; VAD model {'present' if any(vad.glob('*.onnx')) else 'missing'}")
    except Exception as e:  # noqa: BLE001
        add("Faster-Whisper", False, f"{type(e).__name__}: {e}")
    try:
        import onnxruntime
        add("Voice activity detection (onnxruntime)", True, f"version {onnxruntime.__version__}")
    except Exception as e:  # noqa: BLE001
        add("Voice activity detection (onnxruntime)", False, f"{type(e).__name__}: {e} (captions still work without it)")
    folder = model_dir()
    cached = any(folder.rglob("model.bin")) if folder.exists() else False
    add("Model downloaded", cached, str(folder) if cached else f"Not yet. The first caption run downloads it into {folder}.")
    try:
        folder.mkdir(parents=True, exist_ok=True)
        probe = folder / ".write-test"; probe.write_text("ok"); probe.unlink()
        add("Model folder writable", True, str(folder))
    except Exception as e:  # noqa: BLE001
        add("Model folder writable", False, f"{e}")
    report["ok"] = all(c["ok"] for c in report["checks"] if c["name"] in ("CTranslate2 engine", "Faster-Whisper", "Model folder writable"))
    return report


def _decode_pcm16k(path: str):
    """Mono 16 kHz float32 samples via FFmpeg (no PyAV)."""
    import numpy as np
    from app.config import FFMPEG_BIN
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0  # type: ignore[attr-defined]
    proc = subprocess.run([FFMPEG_BIN, "-nostdin", "-hide_banner", "-loglevel", "error", "-i", path, "-map", "0:a:0",
                           "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-acodec", "pcm_s16le", "-"],
                          capture_output=True, timeout=600, creationflags=flags)
    if proc.returncode != 0 or not proc.stdout:
        raise TranscribeError("Local captions could not read the audio: " + proc.stderr.decode(errors="replace")[-300:])
    return np.frombuffer(proc.stdout, np.int16).astype(np.float32) / 32768.0


def _local(path: str, language: str | None) -> dict:
    """Run CPU int8 Whisper. The small multilingual model is fetched once and cached."""
    global _LOCAL_MODEL
    try:
        from faster_whisper import WhisperModel
    except (ImportError, OSError) as e:
        raise TranscribeError(f"Local captions could not load Faster-Whisper ({e}). Reinstall or update SceneForge, then try again.") from e
    if _LOCAL_MODEL is None:
        with _LOCAL_LOCK:
            if _LOCAL_MODEL is None:
                _LOCAL_MODEL = _load_local_model(WhisperModel)
    # Normalize both video-extracted audio and narration uploads before local
    # inference. Quiet embedded dialogue and stereo/downmixed sources otherwise
    # behave differently from cloud transcription, even with a manual language.
    temp = tempfile.TemporaryDirectory(prefix="sceneforge-whisper-")
    try:
        try:
            input_path = _normalize_local_audio(path, temp.name)
        except Exception:
            # Keep transcription available if an optional normalization filter
            # is unavailable in a user's FFmpeg build.
            input_path = path

        # Decode with SceneForge's own FFmpeg and hand Whisper the samples. Faster-Whisper's
        # file decoder uses PyAV, whose newer releases rejected its arguments
        # ("open() got an unexpected keyword argument 'metadata_errors'").
        audio = _decode_pcm16k(input_path)

        def recognize(use_vad: bool) -> dict:
            segments, info = _LOCAL_MODEL.transcribe(audio, language=language or None,
                                                      word_timestamps=True, vad_filter=use_vad,
                                                      condition_on_previous_text=False)
            words = []
            text = []
            estimated_timing = False
            for segment in segments:
                phrase = (segment.text or "").strip()
                if phrase:
                    text.append(phrase)
                before = len(words)
                for word in list(segment.words or []):
                    value = (word.word or "").strip()
                    if value:
                        words.append([value, int(round(word.start * 1000)), int(round(word.end * 1000))])
                # Some short or low-volume clips return recognized segment text
                # but no usable word alignment. Preserve editable captions with
                # approximate timings across the recognized phrase.
                if phrase and len(words) == before:
                    tokens = phrase.split()
                    if tokens:
                        estimated_timing = True
                        start = max(0, int(round(float(segment.start) * 1000)))
                        end = max(start + 1, int(round(float(segment.end) * 1000)))
                        span = end - start
                        for index, token in enumerate(tokens):
                            words.append([token, start + span * index // len(tokens), start + span * (index + 1) // len(tokens)])
            return {"language": info.language or language or "", "text": " ".join(text).strip(), "words": words,
                    "provider": "local", "word_timing": "estimated" if estimated_timing else "whisper"}

        try:
            result = recognize(True)
            # VAD can reject quiet dialogue or clean, short lines. Retry once
            # without it before reporting that speech was not found.
            if not result["text"] and not result["words"]:
                result = recognize(False)
            return result
        except Exception as e:
            try:
                return recognize(False)
            except Exception as retry_error:
                raise TranscribeError(f"Local Whisper transcription failed: {retry_error}") from e
    finally:
        temp.cleanup()


def _elevenlabs(key: str, path: str, language: str | None) -> dict:
    data = {"model_id": "scribe_v2", "timestamps_granularity": "word", "tag_audio_events": "false"}
    if language:
        data["language_code"] = language
    with open(path, "rb") as fh:
        r = requests.post("https://api.elevenlabs.io/v1/speech-to-text", headers={"xi-api-key": key},
                          data=data, files={"file": ("audio.wav", fh, "audio/wav")}, timeout=TIMEOUT)
    if not r.ok:
        raise TranscribeError(f"ElevenLabs transcription failed (HTTP {r.status_code}): {r.text[:200]}")
    j = r.json()
    words = [[w["text"].strip(), int(round(float(w["start"]) * 1000)), int(round(float(w["end"]) * 1000))]
             for w in j.get("words", []) if w.get("type", "word") == "word" and str(w.get("text", "")).strip()]
    return {"language": j.get("language_code") or language or "", "text": (j.get("text") or "").strip(), "words": words, "provider": "elevenlabs"}


def _openai(key: str, path: str, language: str | None) -> dict:
    data = [("model", "whisper-1"), ("response_format", "verbose_json"), ("timestamp_granularities[]", "word")]
    if language:
        data.append(("language", language))
    with open(path, "rb") as fh:
        r = requests.post("https://api.openai.com/v1/audio/transcriptions", headers={"Authorization": f"Bearer {key}"},
                          data=data, files={"file": ("audio.wav", fh, "audio/wav")}, timeout=TIMEOUT)
    if not r.ok:
        raise TranscribeError(f"OpenAI transcription failed (HTTP {r.status_code}): {r.text[:200]}")
    j = r.json()
    words = [[str(w["word"]).strip(), int(round(float(w["start"]) * 1000)), int(round(float(w["end"]) * 1000))]
             for w in j.get("words", []) if str(w.get("word", "")).strip()]
    return {"language": j.get("language") or language or "", "text": (j.get("text") or "").strip(), "words": words, "provider": "openai"}


def transcribe(db, path: str, provider: str = "auto", language: str | None = None) -> dict:
    if provider == "auto":
        provider = "local"
    if provider == "local":
        return _local(path, language)
    if provider not in ("elevenlabs", "openai"):
        raise TranscribeError("Choose Local Whisper, ElevenLabs, or OpenAI.")
    if provider not in available(db):
        raise TranscribeError(f"No {provider} key is saved. Add it in AI Engines → Cloud providers.")
    key = _key(db, provider)
    return (_elevenlabs if provider == "elevenlabs" else _openai)(key, path, language or None)
