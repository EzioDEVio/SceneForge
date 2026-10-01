"""Model manager: list, download and delete the local AI models SceneForge uses.

  GET    /api/models                          every model: purpose, size on disk, downloaded, bundled, folder
  POST   /api/models/{kind}/{id}/download     start the existing download/loader in a background thread
  GET    /api/models/{kind}/{id}/download     progress of that download {status, done, total, error}
  DELETE /api/models/{kind}/{id}              delete a downloaded (never a bundled) model

Kinds: whisper (local captions), cutout (background removal), voice (voice isolation).
Downloads reuse the modules' own ensure/loader functions, so checksums, atomic writes and
progress dictionaries stay in one place. Deleting refuses bundled models and models that a
running job is using, and drops the in-memory sessions so the next use reloads from disk.
"""
from __future__ import annotations

import shutil
import threading
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["models"])

WHISPER_APPROX_MB = 145
_dl: dict[str, dict] = {}          # "kind/id" -> {status: running|done|error, error, started, finished}
_dl_lock = threading.Lock()


def _size(p: Path) -> int:
    try:
        if p.is_file():
            return p.stat().st_size
        if p.is_dir():
            return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    except OSError:
        pass
    return 0


def _download_state(key: str, live: dict | None, approx_bytes: int) -> dict | None:
    st = _dl.get(key)
    if not st and not live:
        return None
    out = dict(st or {"status": "running"})
    if live:
        out.update(done=int(live.get("done", 0)), total=int(live.get("total", 0) or approx_bytes))
    out.setdefault("done", 0)
    out.setdefault("total", approx_bytes)
    return out


# ------------------------------------------------------------------ per-kind facts
def _whisper_entries() -> list[dict]:
    from app.providers import transcribe
    folder = transcribe.model_dir()
    downloaded = folder.exists() and any(folder.rglob("model.bin"))
    key = f"whisper/{transcribe.WHISPER_MODEL}"
    st = _dl.get(key)
    live = None
    if st and st.get("status") == "running":
        # The Hugging Face loader has no progress callback; the folder size is the honest measure.
        live = {"done": _size(folder), "total": WHISPER_APPROX_MB * 1_000_000}
    return [{
        "kind": "whisper", "id": transcribe.WHISPER_MODEL, "name": f"Whisper {transcribe.WHISPER_MODEL} (faster-whisper)",
        "purpose": "Local speech-to-text for automatic captions (works offline after the first download).",
        "bytes": _size(folder) if folder.exists() else 0, "approx_mb": WHISPER_APPROX_MB,
        "downloaded": bool(downloaded), "bundled": False, "folder": str(folder), "path": str(folder),
        "source": "huggingface.co (Systran faster-whisper)",
        "download": _download_state(key, live, WHISPER_APPROX_MB * 1_000_000),
        "in_use": _whisper_busy(),
    }]


def _whisper_busy() -> bool:
    from app.providers import transcribe
    return transcribe.local_busy()


def _is_bundled_cutout(model: str) -> bool:
    from app.render import cutout
    return cutout.model_path(model) != cutout.model_dir() / cutout.MODELS[model]["file"]


def _cutout_entries() -> list[dict]:
    from app.render import cutout
    out = []
    for key, m in cutout.MODELS.items():
        p = cutout.model_path(key)
        ok = p.is_file() and p.stat().st_size > 1_000_000
        bundled = _is_bundled_cutout(key)
        out.append({
            "kind": "cutout", "id": key, "name": m["label"],
            "purpose": "Background removal for subject cutouts on images and video clips.",
            "bytes": p.stat().st_size if ok else 0, "approx_mb": m["approx_mb"], "downloaded": ok, "bundled": bundled,
            "folder": str(p.parent if bundled else cutout.model_dir()), "path": str(p), "source": "github.com (rembg releases)",
            "download": _download_state(f"cutout/{key}", cutout._progress.get(key), int(m["approx_mb"] * 1_000_000)),
            "in_use": _cutout_busy(key),
        })
    return out


def _cutout_busy(model: str) -> bool:
    from app.render import cutout
    try:
        from app.render import video_cutout
        if any(s.get("model") == model and s.get("status") in ("queued", "running", "cancelling") for s in video_cutout._status.values()):
            return True
    except Exception:  # noqa: BLE001
        pass
    return model in cutout._progress or cutout._locks[model].locked()


def _voice_entries() -> list[dict]:
    from app.render import voice_isolation as vi
    p = vi.model_path()
    ok = vi._is_ready(p)
    return [{
        "kind": "voice", "id": "kim_vocal_2", "name": vi.MODEL["label"],
        "purpose": "Voice isolation: separates speech from music and background noise.",
        "bytes": p.stat().st_size if p.is_file() else 0, "approx_mb": vi.MODEL["approx_mb"], "downloaded": ok, "bundled": False,
        "folder": str(vi.model_dir()), "path": str(p), "source": "github.com (Ultimate Vocal Remover model repository)",
        "download": _download_state("voice/kim_vocal_2", vi._progress.get("model"), vi.MODEL["bytes"]),
        "in_use": _voice_busy(),
    }]


def _voice_busy() -> bool:
    from app.render import voice_isolation as vi
    try:
        from app.api import voice_isolation as api_vi
        with api_vi._jobs_lock:
            if any(j.get("status") == "running" for j in api_vi._jobs.values()):
                return True
    except Exception:  # noqa: BLE001
        pass
    return "model" in vi._progress or vi._lock.locked()


def list_models() -> dict:
    models = _whisper_entries() + _cutout_entries() + _voice_entries()
    # Bundled models ship inside the installer; only downloaded files count as removable disk use.
    total = sum(m["bytes"] for m in models)
    removable = sum(m["bytes"] for m in models if not m["bundled"])
    folders = sorted({m["folder"] for m in models})
    return {"models": models, "total_bytes": total, "downloaded_bytes": removable, "folders": folders}


def _find(kind: str, model_id: str) -> dict:
    for m in list_models()["models"]:
        if m["kind"] == kind and m["id"] == model_id:
            return m
    raise HTTPException(404, f"Unknown model {kind}/{model_id}.")


@router.get("/api/models")
def get_models():
    return list_models()


@router.delete("/api/models/{kind}/{model_id}")
def delete_model(kind: str, model_id: str):
    m = _find(kind, model_id)
    if m["bundled"]:
        raise HTTPException(409, f"{m['name']} is bundled with SceneForge and cannot be deleted.")
    if m["in_use"] or (_dl.get(f"{kind}/{model_id}") or {}).get("status") == "running":
        raise HTTPException(409, f"{m['name']} is in use by a running job or download. Wait for it to finish, then try again.")
    if not m["downloaded"] and not m["bytes"]:
        return {"removed": False, "freed_bytes": 0, "message": f"{m['name']} is not downloaded."}
    freed = m["bytes"]
    if kind == "whisper":
        from app.providers import transcribe
        transcribe.reset_model_cache()          # also drops the in-memory model
    elif kind == "cutout":
        from app.render import cutout
        p = cutout.model_dir() / cutout.MODELS[model_id]["file"]
        cutout._sessions.pop(str(p), None)
        p.unlink(missing_ok=True)
    elif kind == "voice":
        from app.render import voice_isolation as vi
        p = vi.model_path()
        with vi._session_lock:
            vi._sessions.pop(str(p), None)
        p.unlink(missing_ok=True)
    _dl.pop(f"{kind}/{model_id}", None)
    return {"removed": True, "freed_bytes": freed, "message": f"{m['name']} was deleted. It downloads again the next time it is needed."}


def _run_download(key: str, kind: str, model_id: str) -> None:
    try:
        if kind == "whisper":
            from app.providers import transcribe
            from faster_whisper import WhisperModel
            with transcribe._LOCAL_LOCK:
                if transcribe._LOCAL_MODEL is None:
                    transcribe._LOCAL_MODEL = transcribe._load_local_model(WhisperModel)
        elif kind == "cutout":
            from app.render import cutout
            cutout.ensure_model(model_id)
        elif kind == "voice":
            from app.render import voice_isolation as vi
            vi.ensure_model()
        _dl[key].update(status="done", finished=time.time())
    except Exception as e:  # noqa: BLE001 - shown to the user
        _dl[key].update(status="error", error=str(e) or type(e).__name__, finished=time.time())


@router.post("/api/models/{kind}/{model_id}/download")
def download_model(kind: str, model_id: str):
    m = _find(kind, model_id)
    key = f"{kind}/{model_id}"
    if m["downloaded"]:
        return {"status": "done", "message": f"{m['name']} is already downloaded."}
    with _dl_lock:
        if (_dl.get(key) or {}).get("status") == "running":
            return {"status": "running"}
        _dl[key] = {"status": "running", "error": None, "started": time.time()}
    threading.Thread(target=_run_download, args=(key, kind, model_id), daemon=True).start()
    return {"status": "running"}


@router.get("/api/models/{kind}/{model_id}/download")
def download_status(kind: str, model_id: str):
    m = _find(kind, model_id)
    st = m["download"] or {"status": "done" if m["downloaded"] else "idle", "done": 0, "total": 0}
    return {**st, "downloaded": m["downloaded"], "bytes": m["bytes"]}
