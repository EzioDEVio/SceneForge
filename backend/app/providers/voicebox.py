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

import re
import time
from urllib.parse import quote

import requests

DEFAULT_URL = "http://127.0.0.1:17493"
_NO_PROXY = {"proxies": {"http": None, "https": None}}   # this computer; never via a system proxy
# Languages Voicebox's /generate accepts (its request pattern).
LANGUAGES = {"zh", "en", "ja", "ko", "de", "fr", "ru", "pt", "es", "it", "he", "ar", "da", "el", "fi", "hi", "ms",
             "nl", "no", "pl", "sv", "sw", "tr"}
NO_VOICES = ("Voicebox is open but has no voices yet. In Voicebox, open Voices and create, clone or add a "
             "preset voice, then click Refresh voices here.")
POLL_SECONDS = 1.0


class VoiceboxError(ValueError):
    pass


_LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")


def _base(url: str | None) -> str:
    """Voicebox runs on this computer: only loopback addresses are used, so a stored or edited
    address cannot point SceneForge's requests at another machine or service."""
    from urllib.parse import urlsplit
    parts = urlsplit((url or DEFAULT_URL).rstrip("/"))
    host = next((h for h in _LOCAL_HOSTS if h == (parts.hostname or "")), None)
    try:
        port = parts.port
    except ValueError:
        port = None
    if parts.scheme not in ("http", "https") or host is None or parts.username or parts.password or parts.path not in ("", "/"):
        raise VoiceboxError(f"Voicebox must be on this computer, for example {DEFAULT_URL}.")
    scheme = "https" if parts.scheme == "https" else "http"
    netloc = f"[{host}]" if host == "::1" else host
    return f"{scheme}://{netloc}" + (f":{int(port)}" if port else "")


_PROFILE_ID = re.compile(r"[A-Za-z0-9_-]{1,128}")


def _profile_ref(profile_id: str) -> str:
    """A Voicebox voice id goes into a URL path: only plain ids (letters, digits, - and _) are
    accepted, so a request value cannot change which Voicebox endpoint is called."""
    if not isinstance(profile_id, str) or not _PROFILE_ID.fullmatch(profile_id):
        raise VoiceboxError("This voice id is not valid. Click Refresh voices and pick a voice again.")
    return quote(profile_id, safe="")


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
    try:
        base = _base(url)
    except VoiceboxError:   # an address saved by an earlier version that is not on this computer
        return {"running": False, "profiles": 0, "url": DEFAULT_URL, "stuck": 0,
                "reason": f"Voicebox must be on this computer, for example {DEFAULT_URL}. Set the address below."}
    out = {"running": False, "profiles": 0, "url": base, "reason": "", "stuck": 0}
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
        try:
            out["stuck"] = len(stuck_jobs(url, timeout=(3, 10)))
        except (requests.RequestException, ValueError):
            out["stuck"] = 0
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


# Voicebox model names (GET /models/status) -> (engine, model_size for /generate).
MODELS = {"qwen-tts-1.7B": ("qwen", "1.7B"), "qwen-tts-0.6B": ("qwen", "0.6B"),
          "qwen-custom-voice-1.7B": ("qwen_custom_voice", "1.7B"), "qwen-custom-voice-0.6B": ("qwen_custom_voice", "0.6B"),
          "chatterbox-tts": ("chatterbox", None), "chatterbox-turbo": ("chatterbox_turbo", None),
          "luxtts": ("luxtts", None), "tada-1b": ("tada", "1B"), "tada-3b-ml": ("tada", "3B"), "kokoro": ("kokoro", None)}
CLONING = ("qwen", "chatterbox", "chatterbox_turbo", "luxtts", "tada")
ACTIVE = ("generating", "loading_model")
STUCK_SECONDS = 600            # an earlier Voicebox job still "Generating…" after this blocks its queue
                               # (10 min: Voicebox on a processor needs minutes for a long narration)
LOADING_SECONDS = 120          # stop waiting while Voicebox loads or downloads a model
TIMEOUT_SECONDS = 600


def _utc(value) -> float | None:
    from datetime import datetime, timezone
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()


def stuck_jobs(url: str | None = None, timeout=(3, 10)) -> list[dict]:
    """Voicebox jobs still "Generating…"/"Loading model" after a few minutes. Voicebox runs one
    job at a time, so one stuck job (for example a hidden model download, or Voicebox 0.5's
    "orphaned" jobs) keeps every later narration waiting forever."""
    res = requests.get(_base(url) + "/history", params={"limit": 50}, timeout=timeout, **_NO_PROXY)
    res.raise_for_status()
    rows = res.json().get("items", []) if isinstance(res.json(), dict) else []
    now = time.time()
    out = []
    for r in rows:
        started = _utc(r.get("created_at"))
        if isinstance(r, dict) and r.get("status") in ACTIVE and started and now - started > STUCK_SECONDS:
            out.append({"id": r.get("id"), "profile": r.get("profile_name") or "", "status": r.get("status"),
                        "minutes": int((now - started) // 60), "text": str(r.get("text") or "")[:60]})
    return out


def clear_stuck(url: str | None = None) -> int:
    """Cancel stuck Voicebox jobs through Voicebox's own cancel endpoint (it also clears
    "orphaned" jobs). Returns how many were cleared."""
    cleared = 0
    for job in stuck_jobs(url):
        try:
            r = requests.post(f"{_base(url)}/generate/{job['id']}/cancel", timeout=(5, 30), **_NO_PROXY)
            cleared += r.ok
        except requests.RequestException:
            pass
    return cleared


def _models(base: str) -> list[dict] | None:
    try:
        res = requests.get(base + "/models/status", timeout=(5, 30), **_NO_PROXY)
        res.raise_for_status()
        rows = res.json().get("models", [])
        return [r for r in rows if isinstance(r, dict) and r.get("model_name") in MODELS]
    except (requests.RequestException, ValueError, AttributeError):
        return None


def _pick_model(base: str, profile: dict) -> tuple[str | None, str | None, str]:
    """Engine and model size for this voice, preferring a model Voicebox already has loaded
    or downloaded, so a narration does not start a hidden multi-GB download (Voicebox's
    /generate otherwise uses Qwen 1.7B). Returns (engine, size, note); when Voicebox reports
    nothing usable on disk, still asks for the voice's own engine (Voicebox may know better)
    and says so in the note."""
    fixed = _engine(profile)
    kind = str(profile.get("voice_type") or "cloned")
    allowed = [fixed] if fixed else (list(CLONING) if kind == "cloned" else list(dict.fromkeys(e for e, _ in MODELS.values())))
    rows = _models(base)
    if rows is None:
        return (fixed or None), None, ""
    order = list(MODELS)
    have = sorted((r for r in rows if MODELS[r["model_name"]][0] in allowed and (r.get("loaded") or (r.get("downloaded") and not r.get("downloading")))),
                  key=lambda r: (not r.get("loaded"), allowed.index(MODELS[r["model_name"]][0]), order.index(r["model_name"])))
    if have:
        engine, size = MODELS[have[0]["model_name"]]
        return engine, size, ""
    busy = [r.get("display_name") or r["model_name"] for r in rows if r.get("downloading") and MODELS[r["model_name"]][0] in allowed]
    if busy:
        raise VoiceboxError(f"Voicebox is still downloading {busy[0]}. Wait until Voicebox → Models shows it as downloaded, then generate again.")
    engine = fixed or allowed[0]
    return engine, None, (f"Voicebox did not report a downloaded model for the {engine} engine, so it may need to download one first "
                          "(watch Voicebox → Models).")


def synthesize(url: str | None, text: str, profile_id: str, language: str | None) -> bytes:
    base = _base(url)
    gid = None
    try:
        try:
            stuck = stuck_jobs(url)
        except (requests.RequestException, ValueError):
            stuck = []
        if stuck:
            oldest = max(j["minutes"] for j in stuck)
            raise VoiceboxError(f"Voicebox has {len(stuck)} earlier narration{'s' if len(stuck) != 1 else ''} stuck at "
                                f"\u201cGenerating\u2026\u201d (the oldest for {oldest} minutes). Voicebox makes one narration at a time, "
                                "so new ones wait behind them. Click \u201cClear stuck Voicebox jobs\u201d on the Voicebox card "
                                "(or restart Voicebox), then generate again.")
        prof = requests.get(f"{base}/profiles/{_profile_ref(profile_id)}", timeout=(5, 15), **_NO_PROXY)
        if prof.status_code == 404:
            raise VoiceboxError("This voice no longer exists in Voicebox. Click Refresh voices and pick another.")
        prof.raise_for_status()
        profile = prof.json() if isinstance(prof.json(), dict) else {}
        lang = (language or "").split("-")[0].lower()
        if lang not in LANGUAGES:
            lang = str(profile.get("language") or "en")
        body = {"profile_id": profile_id, "text": text[:50000], "language": lang}
        engine, size, note = _pick_model(base, profile)
        if engine:
            body["engine"] = engine
        if size:
            body["model_size"] = size
        what = f"voice \u201c{profile.get('name') or profile_id}\u201d with {engine or 'its default engine'}{' ' + size if size else ''}"
        res = requests.post(base + "/generate", json=body, timeout=(10, 120), **_NO_PROXY)
        if not res.ok:
            why = _detail(res)
            raise VoiceboxError(f"Voicebox could not generate this narration ({what})" + (f": {why}" if why else f" (HTTP {res.status_code}).")
                                + (" Download that model in Voicebox \u2192 Models, then try again." if "not downloaded" in why.lower() or "not cached" in why.lower() else ""))
        if res.headers.get("content-type", "").startswith("audio/"):
            return res.content
        meta = res.json()
        gid = meta["id"]
        state, error = str(meta.get("status") or "completed"), meta.get("error")
        started = time.monotonic()
        # Voicebox on a processor (no GPU) takes far longer for long text: allow ~2 s per character, 10–45 min.
        limit = TIMEOUT_SECONDS if TIMEOUT_SECONDS < 60 else min(2700, max(TIMEOUT_SECONDS, len(text) * 2))
        loading_since = started if state == "loading_model" else None
        while state not in ("completed", "failed"):
            now = time.monotonic()
            if loading_since and now - loading_since > LOADING_SECONDS:
                gid = None   # leave the model download running in Voicebox
                raise VoiceboxError(f"Voicebox is still loading the model for {what} after {LOADING_SECONDS // 60} minutes. "
                                    + (note + " " if note else "") + "The narration will finish in Voicebox; generate again here once Voicebox is idle.")
            if now - started > limit:
                raise VoiceboxError(f"Voicebox did not finish {what} within {int(limit // 60)} minutes. SceneForge cancelled it; "
                                    "check Voicebox and try a shorter text.")
            time.sleep(POLL_SECONDS)
            h = requests.get(f"{base}/history/{gid}", timeout=(5, 15), **_NO_PROXY)
            if h.ok:
                info = h.json()
                state, error = str(info.get("status") or "completed"), info.get("error")
                if state == "loading_model" and loading_since is None:
                    loading_since = time.monotonic()
                elif state != "loading_model":
                    loading_since = None
        done, gid = gid, None
        if state == "failed":
            raise VoiceboxError(f"Voicebox could not generate this narration ({what})" + (f": {str(error)[:300]}" if error else "."))
        audio = requests.get(f"{base}/audio/{done}", timeout=(10, 120), **_NO_PROXY)
        if not audio.ok:
            raise VoiceboxError("Voicebox finished but its audio file is missing" + (f": {_detail(audio)}" if _detail(audio) else "."))
        return audio.content
    except requests.RequestException as e:
        raise VoiceboxError("Voicebox stopped answering. Check that the Voicebox app is open and try again.") from e
    except (ValueError, KeyError) as e:
        if isinstance(e, VoiceboxError):
            raise
        raise VoiceboxError("Voicebox sent an unexpected reply. Update Voicebox and try again.") from e
    finally:
        if gid:   # never leave our own job blocking Voicebox's queue
            try:
                requests.post(f"{base}/generate/{gid}/cancel", timeout=(5, 15), **_NO_PROXY)
            except requests.RequestException:
                pass
