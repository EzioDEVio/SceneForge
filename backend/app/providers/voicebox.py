"""Optional connection to Voicebox (github.com/jamiepine/voicebox, MIT), a separate local
voice studio app. When it is open, SceneForge uses its local REST API (checked against the
Voicebox 0.5.0 and 0.6.0 sources):

  GET  /profiles            voice profiles the user created or cloned in Voicebox
  GET  /profiles/{id}       one profile (its engine and language)
  POST /generate            queues a generation and returns at once with status "generating"
  GET  /history/{id}        generation status: generating / completed / failed (+ error)
  GET  /audio/{id}          the finished audio

/generate defaults to the Qwen engine unless an engine is passed, so SceneForge passes the
profile's own engine (Kokoro and Qwen CustomVoice preset profiles fail validation otherwise).
Voicebox itself is installed and updated by the user.
"""
from __future__ import annotations

import time

import requests

DEFAULT_URL = "http://127.0.0.1:17493"
_NO_PROXY = {"proxies": {"http": None, "https": None}}   # this computer; never via a system proxy
# Languages Voicebox's /generate accepts (its request pattern).
LANGUAGES = {"zh", "en", "ja", "ko", "de", "fr", "ru", "pt", "es", "it", "he", "ar", "da", "el", "fi", "hi", "ms",
             "nl", "no", "pl", "sv", "sw", "tr"}
NO_VOICES = ("Voicebox is open but has no voices yet. In Voicebox, open Voices and create, clone or add a "
             "preset voice, then click Refresh voices here.")
POLL_SECONDS = 1.0
TIMEOUT_SECONDS = 900


class VoiceboxError(ValueError):
    pass


def _base(url: str | None) -> str:
    return (url or DEFAULT_URL).rstrip("/")


def _detail(res: requests.Response) -> str:
    try:
        body = res.json()
    except ValueError:
        return ""
    if isinstance(body, dict):
        d = body.get("detail")
        if not d and isinstance(body.get("error"), dict):
            d = body["error"].get("message")
        if isinstance(d, list):   # FastAPI validation errors
            d = "; ".join(str(x.get("msg", x)) for x in d if isinstance(x, dict))
        return str(d or "")[:300]
    return ""


def _profiles(url: str | None, timeout=(5, 15)) -> list[dict]:
    res = requests.get(_base(url) + "/profiles", timeout=timeout, **_NO_PROXY)
    res.raise_for_status()
    rows = res.json()
    rows = rows.get("profiles", rows.get("items", [])) if isinstance(rows, dict) else rows
    return [p for p in rows if isinstance(p, dict) and p.get("id")] if isinstance(rows, list) else []


def running(url: str | None = None) -> bool:
    return status(url)["running"]


def status(url: str | None = None) -> dict:
    """For the Voices card: is Voicebox answering, how many voices does it have, and if it
    is not answering, why (in words the user can act on)."""
    base = _base(url)
    out = {"running": False, "profiles": 0, "url": base, "reason": ""}
    try:
        rows = _profiles(url, timeout=(3, 10))
    except requests.ConnectionError:
        out["reason"] = (f"Nothing is answering at {base}. Make sure the Voicebox app has finished starting "
                         "(its window shows Voices), or set the address Voicebox uses below.")
    except requests.Timeout:
        out["reason"] = (f"Voicebox at {base} did not reply within 10 seconds. It may still be starting or "
                         "loading a model; wait a moment and click Check again.")
    except requests.HTTPError as e:
        code = e.response.status_code if e.response is not None else "?"
        out["reason"] = f"Something answers at {base}, but not like Voicebox (HTTP {code}). Check the address below."
    except (requests.RequestException, ValueError):
        out["reason"] = f"The program at {base} sent a reply SceneForge does not understand. Update Voicebox, or check the address below."
    else:
        out.update(running=True, profiles=len(rows))
    return out


def _engine(p: dict) -> str:
    return str(p.get("default_engine") or p.get("preset_engine") or "")


def voice_details(url: str | None) -> list[dict]:
    try:
        rows = _profiles(url)
    except requests.RequestException as e:
        raise VoiceboxError("Voicebox is not answering. Open the Voicebox app, then click Refresh voices.") from e
    except ValueError as e:
        raise VoiceboxError("Voicebox sent an unexpected reply. Update Voicebox and try again.") from e
    out = []
    for p in rows:
        kind = {"preset": "Preset voice", "designed": "Designed voice"}.get(str(p.get("voice_type") or ""), "Cloned voice")
        engine = _engine(p)
        out.append({"id": str(p["id"]), "name": str(p.get("name") or p["id"]), "language": str(p.get("language") or ""),
                    "accent": "", "gender": "", "age": "",
                    "description": str(p.get("description") or f"Voicebox · {kind}{' · ' + engine if engine else ''}"),
                    "preview_url": ""})
    if not out:
        raise VoiceboxError(NO_VOICES)
    return out


def synthesize(url: str | None, text: str, profile_id: str, language: str | None) -> bytes:
    base = _base(url)
    try:
        prof = requests.get(f"{base}/profiles/{profile_id}", timeout=(5, 15), **_NO_PROXY)
        if prof.status_code == 404:
            raise VoiceboxError("This voice no longer exists in Voicebox. Click Refresh voices and pick another.")
        prof.raise_for_status()
        profile = prof.json() if isinstance(prof.json(), dict) else {}
        lang = (language or "").split("-")[0].lower()
        if lang not in LANGUAGES:
            lang = str(profile.get("language") or "en")
        body = {"profile_id": profile_id, "text": text[:50000], "language": lang}
        if _engine(profile):
            body["engine"] = _engine(profile)
        res = requests.post(base + "/generate", json=body, timeout=(10, 120), **_NO_PROXY)
        if not res.ok:
            why = _detail(res)
            raise VoiceboxError("Voicebox could not generate this narration" + (f": {why}" if why else f" (HTTP {res.status_code}).")
                                + (" Download that voice's model in Voicebox → Models, then try again." if "not downloaded" in why.lower() or "not cached" in why.lower() else ""))
        if res.headers.get("content-type", "").startswith("audio/"):
            return res.content
        meta = res.json()
        gid = meta["id"]
        state, error = str(meta.get("status") or "completed"), meta.get("error")
        deadline = time.monotonic() + TIMEOUT_SECONDS
        while state not in ("completed", "failed"):
            if time.monotonic() > deadline:
                raise VoiceboxError("Voicebox is still generating after 15 minutes. Check Voicebox, then try again.")
            time.sleep(POLL_SECONDS)
            h = requests.get(f"{base}/history/{gid}", timeout=(5, 15), **_NO_PROXY)
            if h.ok:
                info = h.json()
                state, error = str(info.get("status") or "completed"), info.get("error")
        if state == "failed":
            raise VoiceboxError("Voicebox could not generate this narration" + (f": {str(error)[:300]}" if error else "."))
        audio = requests.get(f"{base}/audio/{gid}", timeout=(10, 120), **_NO_PROXY)
        if not audio.ok:
            raise VoiceboxError("Voicebox finished but its audio file is missing" + (f": {_detail(audio)}" if _detail(audio) else "."))
        return audio.content
    except requests.RequestException as e:
        raise VoiceboxError("Voicebox stopped answering. Check that the Voicebox app is open and try again.") from e
    except (ValueError, KeyError) as e:
        if isinstance(e, VoiceboxError):
            raise
        raise VoiceboxError("Voicebox sent an unexpected reply. Update Voicebox and try again.") from e
