"""AI voice isolation (dialogue isolation, local MDX-Net model).

  GET  /api/voice-isolation/status               model folder, downloaded?, size, download progress
  POST /api/assets/{asset_id}/isolate-voice      {strength: 0..100 = 100, wait?: bool}
       -> {status: "done", asset} (cached or wait=true) or {status: "running", job_id}
  GET  /api/voice-isolation/jobs/{job_id}        {status: running|done|error, progress, stage, asset?, error?}

The result is a NEW audio asset (48 kHz stereo WAV, "<orig> (voice isolated).wav");
the original is never modified. Results are cached per source content hash + strength.
Works on audio and video assets (the video's first audio stream is used).
"""
from __future__ import annotations

import hashlib
import threading
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import MEDIA_DIR
from app.db.database import get_db, session_scope
from app.db.models import Asset
from app.domain import schemas
from app.domain.constants import AssetOrigin

router = APIRouter(tags=["voice-isolation"])

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()
_run_lock = threading.Lock()  # one isolation at a time: it uses every CPU core


class IsolateRequest(BaseModel):
    strength: int = Field(default=100, ge=0, le=100)
    wait: bool = False


def _asset_file(asset: Asset) -> Path:
    from app.render.renderer import _resolve_asset_path
    return Path(_resolve_asset_path(asset))


def _cache_key(src: Asset, strength: int) -> str:
    from app.render.voice_isolation import MODEL
    return hashlib.sha256(f"{src.content_hash}|{strength}|{MODEL['md5']}".encode()).hexdigest()


def _cached(db: Session, project_id: str, key: str) -> Asset | None:
    for a in db.query(Asset).filter(Asset.project_id == project_id, Asset.type == "audio").all():
        if (a.generation_metadata_json or {}).get("voice_iso_key") == key and _asset_file(a).is_file():
            return a
    return None


def _out(asset: Asset) -> dict:
    return schemas.AssetOut.model_validate(asset).model_dump()


def _isolate(asset_id: str, strength: int, key: str, job: dict | None) -> str:
    """Run the model and register the new asset. Returns the new asset id."""
    from app.render.ffmpeg_utils import probe
    from app.render.voice_isolation import VoiceIsolationError, isolate_file
    with session_scope() as db:
        src = db.get(Asset, asset_id)
        project_id, src_path = src.project_id, str(_asset_file(src))
        stem = Path(src.original_filename or "audio").stem
    folder = Path(MEDIA_DIR) / project_id
    dest = folder / f"voiceiso_{uuid.uuid4().hex[:10]}.wav"

    def progress(f: float):
        if job is not None:
            job["stage"] = "isolating"
            job["progress"] = round(5 + 90 * f, 1)

    with _run_lock:
        with session_scope() as db:  # a concurrent identical request may have finished meanwhile
            hit = _cached(db, project_id, key)
            if hit:
                return hit.id
        if job is not None:
            from app.render.voice_isolation import status
            job["stage"] = "downloading model" if not status()["downloaded"] else "loading"
        try:
            info = isolate_file(src_path, str(dest), strength, progress)
        except VoiceIsolationError:
            dest.unlink(missing_ok=True)
            raise
    data = dest.read_bytes()
    p = probe(str(dest))
    with session_scope() as db:
        asset = Asset(project_id=project_id, type="audio", content_hash=hashlib.sha256(data).hexdigest(),
                      storage_key=str(dest.relative_to(MEDIA_DIR)), mime="audio/wav",
                      original_filename=f"{stem} (voice isolated).wav"[:255], duration_ms=p.duration_ms,
                      origin=AssetOrigin.UPLOAD, creator="AI voice isolation",
                      generation_metadata_json={"voice_iso_key": key, "voice_isolation": {
                          "source_asset_id": asset_id, "strength": strength, "model": "Kim_Vocal_2",
                          "seconds": info["seconds"], "elapsed": info["elapsed"]}})
        db.add(asset)
        db.flush()
        return asset.id


def _error_status(msg: str) -> int:
    return 503 if "download" in msg else 422


def _worker(job_id: str, asset_id: str, strength: int, key: str):
    from app.render.voice_isolation import VoiceIsolationError
    from app.workers import jobs as job_worker
    job = _jobs[job_id]
    try:
        new_id = _isolate(asset_id, strength, key, job)
        with session_scope() as db:
            job["asset"] = _out(db.get(Asset, new_id))
        job.update(status="done", progress=100, stage="done")
    except VoiceIsolationError as e:
        job.update(status="error", error=str(e), code=_error_status(str(e)))
    except Exception as e:  # pragma: no cover - unexpected
        job.update(status="error", error=f"Voice isolation failed: {type(e).__name__}: {e}", code=500)
    finally:
        job["finished"] = time.time()
        job_worker.release_job_id(job_id)


@router.get("/api/voice-isolation/status")
def voice_isolation_status():
    from app.render.voice_isolation import status
    out = status()
    with _jobs_lock:
        out["running"] = [{"job_id": k, "asset_id": j["asset_id"], "progress": j["progress"]}
                          for k, j in _jobs.items() if j["status"] == "running"]
    return out


@router.post("/api/assets/{asset_id}/isolate-voice")
def isolate_voice(asset_id: str, body: IsolateRequest | None = None, db: Session = Depends(get_db)):
    from app.render.voice_isolation import VoiceIsolationError
    from app.workers import jobs as job_worker
    body = body or IsolateRequest()
    src = db.get(Asset, asset_id)
    if not src:
        raise HTTPException(404, "Asset not found")
    if src.type not in ("audio", "video"):
        raise HTTPException(400, "Voice isolation works on audio files and videos with sound.")
    if not _asset_file(src).is_file():
        raise HTTPException(404, "This file is missing on disk.")
    key = _cache_key(src, body.strength)
    hit = _cached(db, src.project_id, key)
    if hit:
        return {"status": "done", "cached": True, "asset": _out(hit)}
    if body.wait:
        try:
            new_id = _isolate(asset_id, body.strength, key, None)
        except VoiceIsolationError as e:
            raise HTTPException(_error_status(str(e)), str(e))
        db.expire_all()
        return {"status": "done", "cached": False, "asset": _out(db.get(Asset, new_id))}
    with _jobs_lock:
        for jid, j in _jobs.items():
            if j["key"] == key and j["status"] == "running":
                return {"status": "running", "job_id": jid, "progress": j["progress"]}
        # forget finished jobs older than an hour
        for jid in [k for k, j in _jobs.items() if j.get("finished") and time.time() - j["finished"] > 3600]:
            _jobs.pop(jid, None)
        job_id = job_worker.reserve_job_id()
        _jobs[job_id] = {"status": "running", "progress": 0, "stage": "queued", "asset_id": asset_id,
                         "key": key, "strength": body.strength}
    threading.Thread(target=_worker, args=(job_id, asset_id, body.strength, key), daemon=True).start()
    return {"status": "running", "job_id": job_id, "progress": 0}


@router.get("/api/voice-isolation/jobs/{job_id}")
def isolate_voice_job(job_id: str):
    j = _jobs.get(job_id)
    if not j:
        raise HTTPException(404, "This voice isolation job is no longer known. Start it again.")
    return {k: v for k, v in j.items() if k not in ("key",)} | {"job_id": job_id}
