"""Project copy and auto-reframe (16:9 -> 9:16 that follows the subject).

POST /api/projects/{id}/duplicate        {title?}                 -> project (plain copy)
POST /api/projects/{id}/reframe          {aspect?: "9:16", title?} -> {job_id, project_id}
GET  /api/reframe/jobs/{job_id}                                    -> progress / result
PUT  /api/shots/{shot_id}/reframe        {mode, x?, reanalyze?}    -> shot
See render/reframe.py for the data shape and how it renders.
"""
from __future__ import annotations

import threading
import time
import traceback

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db, session_scope
from app.db.models import Project, Shot
from app.domain import schemas
from app.domain.constants import ASPECT_DIMENSIONS, AspectRatio
from app.domain.project_copy import copy_project
from app.render import reframe as rf

router = APIRouter(tags=["reframe"])

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _resolve_path(asset) -> str:
    from app.render.renderer import _resolve_asset_path
    return _resolve_asset_path(asset)


@router.post("/api/projects/{project_id}/duplicate", response_model=schemas.ProjectOut)
def duplicate_project(project_id: str, body: dict | None = Body(None), db: Session = Depends(get_db)):
    src = db.get(Project, project_id)
    if not src:
        raise HTTPException(404, "Project not found")
    title = str((body or {}).get("title") or f"{src.title} (copy)")[:255]
    copy = copy_project(db, src, title=title)
    db.commit()
    db.refresh(copy)
    return copy


def _job_update(job_id: str, **kw) -> None:
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id].update(kw)


def _run_reframe(job_id: str, project_id: str, shot_ids: list[str]) -> None:
    from app.workers import jobs as job_worker
    warnings: list[str] = []
    try:
        total = max(len(shot_ids), 1)
        for i, shot_id in enumerate(shot_ids):
            if _jobs.get(job_id, {}).get("cancel"):
                raise rf.ReframeError("cancelled")
            with session_scope() as db:
                shot = db.get(Shot, shot_id)
                project = db.get(Project, project_id)
                if not shot or not project:
                    continue
                _ = shot.asset
                label = shot.asset.original_filename or f"media {i + 1}"
                db.expunge_all()
            _job_update(job_id, stage=f"analysing {label} ({i + 1}/{len(shot_ids)})", done=i,
                        progress=int(100 * i / total))
            try:
                result = rf.analyze_shot(shot, project, _resolve_path,
                                         progress=lambda f, i=i: _job_update(job_id, progress=int(100 * (i + f) / total)),
                                         cancel_check=lambda: bool(_jobs.get(job_id, {}).get("cancel")))
            except Exception as e:  # noqa: BLE001 - one bad clip falls back to centre, never fails the copy
                if str(e) == "cancelled":
                    raise
                warnings.append(f"{label}: could not follow the subject ({str(e)[:160]}); centred instead.")
                result = {"mode": "center", "x": 0.5, "method": "center"}
            if result.get("method") == "center" and result.get("mode") == "follow":
                warnings.append(f"{label}: no clear subject found; the frame stays centred.")
            with session_scope() as db:
                db_shot = db.get(Shot, shot_id)
                if db_shot:
                    db_shot.crop_json = rf.with_reframe(db_shot.crop_json, rf.clean_reframe(result))
                    db_shot.fit = "cover"
                    db_shot.scene.revision += 1
        _job_update(job_id, status="succeeded", stage="done", progress=100, done=len(shot_ids), warnings=warnings)
    except Exception as e:  # noqa: BLE001
        cancelled = str(e) == "cancelled"
        _job_update(job_id, status="cancelled" if cancelled else "failed", stage="error",
                    error=None if cancelled else f"{e}\n{traceback.format_exc()[-1200:]}", warnings=warnings)
    finally:
        job_worker.release_job_id(job_id)


@router.post("/api/projects/{project_id}/reframe")
def reframe_project(project_id: str, body: dict | None = Body(None), db: Session = Depends(get_db)):
    """Copy the project with a new aspect (default 9:16) and follow the subject in every shot."""
    body = body or {}
    aspect = body.get("aspect", "9:16")
    if aspect not in [a.value for a in AspectRatio]:
        raise HTTPException(400, f"Unsupported aspect '{aspect}'")
    src = db.get(Project, project_id)
    if not src:
        raise HTTPException(404, "Project not found")
    w, h = ASPECT_DIMENSIONS[AspectRatio(aspect)]
    title = str(body.get("title") or f"{src.title} ({aspect} reframe)")[:255]
    copy = copy_project(db, src, title=title, aspect=aspect, width=w, height=h)
    shot_ids = [sh.id for s in copy.scenes for sh in s.shots if sh.asset and sh.asset.type in ("image", "video")]
    db.commit()
    from app.workers import jobs as job_worker
    job_id = job_worker.reserve_job_id()   # counts as live work for close/delete guards
    with _jobs_lock:
        _jobs[job_id] = {"job_id": job_id, "project_id": copy.id, "source_project_id": project_id, "status": "running",
                         "stage": "starting", "progress": 0, "done": 0, "total": len(shot_ids), "warnings": [],
                         "error": None, "started_at": time.time()}
    threading.Thread(target=_run_reframe, args=(job_id, copy.id, shot_ids), daemon=True, name=f"reframe-{job_id[:8]}").start()
    return {"job_id": job_id, "project_id": copy.id, "total": len(shot_ids)}


@router.get("/api/reframe/jobs/{job_id}")
def reframe_job(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            raise HTTPException(404, "Reframe job not found")
        return {k: v for k, v in job.items() if k != "cancel"}


@router.post("/api/reframe/jobs/{job_id}/cancel")
def cancel_reframe_job(job_id: str):
    _job_update(job_id, cancel=True)
    return {"ok": True}


@router.put("/api/shots/{shot_id}/reframe", response_model=schemas.ShotOut)
def set_shot_reframe(shot_id: str, body: dict = Body(...), db: Session = Depends(get_db)):
    """Per-shot override: center | follow (analyses the clip when it has no path yet) | manual x."""
    shot = db.get(Shot, shot_id)
    if not shot:
        raise HTTPException(404, "Shot not found")
    mode = body.get("mode")
    if mode in (None, "off"):
        shot.crop_json = rf.with_reframe(shot.crop_json, None)
    else:
        current = (shot.crop_json or {}).get("reframe") or {}
        try:
            if mode == "follow" and (body.get("reanalyze") or not current.get("track")):
                project = db.get(Project, shot.scene.project_id)
                try:
                    result = rf.analyze_shot(shot, project, _resolve_path)
                except rf.ReframeError as e:
                    raise HTTPException(400, str(e))
                reframe = rf.clean_reframe(result)
            else:
                reframe = rf.clean_reframe({**current, "mode": mode, **({"x": body["x"]} if "x" in body else {})})
        except rf.ReframeError as e:
            raise HTTPException(400, str(e))
        shot.crop_json = rf.with_reframe(shot.crop_json, reframe)
        shot.fit = "cover"
    shot.scene.revision += 1
    db.commit()
    db.refresh(shot)
    return shot
