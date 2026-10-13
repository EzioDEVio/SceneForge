"""Gemini text-to-speech (Google AI Studio key). Cloud, 100+ languages including Arabic.

Uses the Interactions API documented for the current TTS models (October 2026), and
falls back to the older generateContent audio output when an account or model does not
offer Interactions yet. Requests go only to generativelanguage.googleapis.com with the
user's own key; nothing is sent unless the user generates narration.
"""
from __future__ import annotations

import base64
import io
import subprocess
import tempfile
import wave
from pathlib import Path

import requests

BASE = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "gemini-3.8-flash-tts"
FALLBACK_MODEL = "gemini-2.5-flash-preview-tts"
VOICES = [  # name, character (from Google's voice list)
    ("Kore", "Firm"), ("Puck", "Upbeat"), ("Charon", "Informative"), ("Zephyr", "Bright"), ("Fenrir", "Excitable"),
    ("Leda", "Youthful"), ("Orus", "Firm"), ("Aoede", "Breezy"), ("Callirrhoe", "Easy-going"), ("Autonoe", "Bright"),
    ("Enceladus", "Breathy"), ("Iapetus", "Clear"), ("Umbriel", "Easy-going"), ("Algieba", "Smooth"), ("Despina", "Smooth"),
    ("Erinome", "Clear"), ("Algenib", "Gravelly"), ("Rasalgethi", "Informative"), ("Laomedeia", "Upbeat"), ("Achernar", "Soft"),
    ("Alnilam", "Firm"), ("Schedar", "Even"), ("Gacrux", "Mature"), ("Pulcherrima", "Forward"), ("Achird", "Friendly"),
    ("Zubenelgenubi", "Casual"), ("Vindemiatrix", "Gentle"), ("Sadachbia", "Lively"), ("Sadaltager", "Knowledgeable"), ("Sulafat", "Warm"),
]


class GeminiTTSError(ValueError):
    pass


def voice_details() -> list[dict]:
    return [{"id": name, "name": name, "language": "", "accent": "", "gender": "", "age": "",
             "description": f"{character} · speaks the language of the text", "preview_url": ""} for name, character in VOICES]


def _find_audio(node):
    """Return base64 audio data from an Interactions response, wherever it sits."""
    if isinstance(node, dict):
        kind = str(node.get("type") or node.get("mime_type") or node.get("mimeType") or "")
        if isinstance(node.get("data"), str) and ("audio" in kind or kind == ""):
            return node["data"]
        for value in node.values():
            found = _find_audio(value)
            if found:
                return found
    elif isinstance(node, list):
        for value in reversed(node):   # the last audio item is the model's answer
            found = _find_audio(value)
            if found:
                return found
    return None


def _wav_from_pcm(pcm: bytes, rate: int = 24000) -> bytes:
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(pcm)
    return out.getvalue()


def _error(res) -> GeminiTTSError:
    try:
        detail = res.json().get("error", {}).get("message", "")
    except ValueError:
        detail = ""
    if res.status_code in (401, 403):
        return GeminiTTSError("Google rejected the API key. Check it in AI Engines → Gemini voices." + (f" ({detail[:200]})" if detail else ""))
    if res.status_code == 429:
        return GeminiTTSError("Gemini's free limit for text-to-speech is used up for now. Try again later or use a local voice.")
    return GeminiTTSError(f"Gemini voices returned HTTP {res.status_code}." + (f" {detail[:300]}" if detail else ""))


def _speed(wav: bytes, speed: float) -> bytes:
    if abs(speed - 1.0) < 0.01:
        return wav
    from app.config import FFMPEG_BIN
    with tempfile.TemporaryDirectory(prefix="sf-gemini-") as d:
        src, dst = Path(d) / "in.wav", Path(d) / "out.wav"
        src.write_bytes(wav)
        subprocess.run([FFMPEG_BIN, "-y", "-v", "error", "-i", str(src), "-af", f"atempo={speed:.3f}", str(dst)],
                       check=True, capture_output=True, timeout=300)
        return dst.read_bytes()


def synthesize(key: str, model: str | None, text: str, voice: str, language: str | None, speed: float) -> bytes:
    if not key:
        raise GeminiTTSError("Add your Google AI Studio API key in AI Engines → Gemini voices first.")
    if voice not in {name for name, _ in VOICES}:
        raise GeminiTTSError("Choose a Gemini voice.")
    if not 0.5 <= speed <= 2.0:
        raise GeminiTTSError("Speaking speed must be between 0.5 and 2.0.")
    headers = {"x-goog-api-key": key, "Content-Type": "application/json"}
    model = model or DEFAULT_MODEL
    try:
        res = requests.post(f"{BASE}/interactions", headers=headers, timeout=(15, 300), json={
            "model": model,
            "input": [{"type": "user_input", "content": [{"type": "text", "text": text}]}],
            "response_format": {"type": "audio"},
            "generation_config": {"speech_config": [{"voice": voice}]},
        })
        if res.ok:
            data = _find_audio(res.json())
            if not data:
                raise GeminiTTSError("Gemini answered without audio. Try again or pick another voice.")
            audio = base64.b64decode(data)
            wav = audio if audio[:4] == b"RIFF" else _wav_from_pcm(audio)
            return _speed(wav, speed)
        if res.status_code not in (400, 404):
            raise _error(res)
        # Older accounts/models: generateContent with audio output (raw 24 kHz PCM).
        res = requests.post(f"{BASE}/models/{FALLBACK_MODEL}:generateContent", headers=headers, timeout=(15, 300), json={
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}},
        })
        if not res.ok:
            raise _error(res)
        parts = res.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
        data = next((p.get("inlineData", {}).get("data") for p in parts if p.get("inlineData")), None)
        if not data:
            raise GeminiTTSError("Gemini answered without audio. Try again or pick another voice.")
        return _speed(_wav_from_pcm(base64.b64decode(data)), speed)
    except requests.RequestException as e:
        raise GeminiTTSError("Could not reach Gemini voices. Check the internet connection.") from e
