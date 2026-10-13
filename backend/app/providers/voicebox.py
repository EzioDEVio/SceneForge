"""Optional connection to Voicebox (github.com/jamiepine/voicebox, MIT), a separate local
voice studio app. When it is installed and running, SceneForge uses its local REST API:
GET /profiles (voices), POST /generate, GET /audio/{id}. Written against Voicebox's
published API reference; Voicebox itself is installed and updated by the user.
"""
from __future__ import annotations

import requests

DEFAULT_URL = "http://127.0.0.1:17493"
_NO_PROXY = {"proxies": {"http": None, "https": None}}   # this computer; never via a system proxy


class VoiceboxError(ValueError):
    pass


def _base(url: str | None) -> str:
    return (url or DEFAULT_URL).rstrip("/")


def running(url: str | None = None) -> bool:
    try:
        return requests.get(_base(url) + "/profiles", timeout=2, **_NO_PROXY).ok
    except requests.RequestException:
        return False


def voice_details(url: str | None) -> list[dict]:
    try:
        res = requests.get(_base(url) + "/profiles", timeout=(5, 15), **_NO_PROXY)
        res.raise_for_status()
        rows = res.json()
    except requests.RequestException as e:
        raise VoiceboxError("Voicebox is not answering. Open the Voicebox app, then click Refresh voices.") from e
    except ValueError as e:
        raise VoiceboxError("Voicebox sent an unexpected reply. Update Voicebox and try again.") from e
    rows = rows.get("profiles", rows.get("items", [])) if isinstance(rows, dict) else rows
    out = []
    for p in rows if isinstance(rows, list) else []:
        if isinstance(p, dict) and p.get("id"):
            out.append({"id": str(p["id"]), "name": str(p.get("name") or p["id"]), "language": str(p.get("language") or ""),
                        "accent": "", "gender": "", "age": "", "description": str(p.get("description") or "Voicebox profile"), "preview_url": ""})
    if not out:
        raise VoiceboxError("Voicebox has no voice profiles yet. Create or clone a voice in Voicebox, then click Refresh voices.")
    return out


def synthesize(url: str | None, text: str, profile_id: str, language: str | None) -> bytes:
    base = _base(url)
    body = {"profile_id": profile_id, "text": text[:5000]}
    if language:
        body["language"] = language
    try:
        res = requests.post(base + "/generate", json=body, timeout=(10, 900), **_NO_PROXY)
        if res.status_code == 422 and "language" in body:   # older builds accept only some languages
            body.pop("language")
            res = requests.post(base + "/generate", json=body, timeout=(10, 900), **_NO_PROXY)
        if not res.ok:
            raise VoiceboxError(f"Voicebox could not generate this narration (HTTP {res.status_code}).")
        if res.headers.get("content-type", "").startswith("audio/"):
            return res.content
        meta = res.json()
        audio = requests.get(f"{base}/audio/{meta['id']}", timeout=(10, 120), **_NO_PROXY)
        audio.raise_for_status()
        return audio.content
    except requests.RequestException as e:
        raise VoiceboxError("Voicebox stopped answering. Check that the Voicebox app is open and try again.") from e
    except (ValueError, KeyError) as e:
        raise VoiceboxError("Voicebox sent an unexpected reply. Update Voicebox and try again.") from e
