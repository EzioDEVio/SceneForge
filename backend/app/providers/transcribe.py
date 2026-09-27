"""Automatic captions: speech → text with word timing and language detection.

  ElevenLabs Speech to Text (Scribe v2): POST /v1/speech-to-text, word timestamps, language_code
  OpenAI Whisper (whisper-1): /v1/audio/transcriptions, verbose_json with word timestamps

Uses the keys already saved in SceneForge (provider profiles named "elevenlabs" / "openai").
Returns {"language": "en", "text": "...", "words": [[word, start_ms, end_ms], ...], "provider": ...}.
"""
from __future__ import annotations

import requests

from app.security.secrets import reveal

TIMEOUT = (10, 300)


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
    return [n for n in ("elevenlabs", "openai") if _key(db, n)]


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
    names = available(db)
    if not names:
        raise TranscribeError("Automatic captions need an ElevenLabs or OpenAI key. Add one in AI Engines → Cloud providers.")
    if provider == "auto":
        provider = names[0]
    if provider not in names:
        raise TranscribeError(f"No {provider} key is saved. Add it in AI Engines → Cloud providers.")
    key = _key(db, provider)
    return (_elevenlabs if provider == "elevenlabs" else _openai)(key, path, language or None)
