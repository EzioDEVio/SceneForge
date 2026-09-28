"""Automatic captions: speech → text with word timing and language detection.

  ElevenLabs Speech to Text (Scribe v2): POST /v1/speech-to-text, word timestamps, language_code
  OpenAI Whisper (whisper-1): /v1/audio/transcriptions, verbose_json with word timestamps

Local Faster-Whisper is the default and needs no API key. Cloud providers remain optional.
Returns {"language": "en", "text": "...", "words": [[word, start_ms, end_ms], ...], "provider": ...}.
"""
from __future__ import annotations

import requests
import os
from pathlib import Path
from threading import Lock

from app.security.secrets import reveal

TIMEOUT = (10, 300)
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


def _local(path: str, language: str | None) -> dict:
    """Run CPU int8 Whisper. The small multilingual model is fetched once and cached."""
    global _LOCAL_MODEL
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise TranscribeError("Local captions are unavailable because Faster-Whisper is not installed. Reinstall or update SceneForge.") from e
    if _LOCAL_MODEL is None:
        with _LOCAL_LOCK:
            if _LOCAL_MODEL is None:
                model_dir = Path(os.environ.get("SCENEFORGE_MODEL_DIR", Path.home() / ".sceneforge" / "models" / "whisper"))
                model_dir.mkdir(parents=True, exist_ok=True)
                try:
                    _LOCAL_MODEL = WhisperModel("base", device="cpu", compute_type="int8", download_root=str(model_dir))
                except Exception as e:
                    raise TranscribeError(f"Could not download or start the local Whisper model: {e}") from e
    try:
        segments, info = _LOCAL_MODEL.transcribe(path, language=language or None, word_timestamps=True, vad_filter=True)
        words = []
        text = []
        for segment in segments:
            text.append(segment.text.strip())
            for word in segment.words or []:
                value = word.word.strip()
                if value:
                    words.append([value, int(round(word.start * 1000)), int(round(word.end * 1000))])
        return {"language": info.language or language or "", "text": " ".join(text).strip(), "words": words, "provider": "local"}
    except Exception as e:
        raise TranscribeError(f"Local Whisper transcription failed: {e}") from e


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
