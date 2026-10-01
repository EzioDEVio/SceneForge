from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Body, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Asset, Project, RenderJob, Scene
from app.domain import schemas
from app.domain.constants import JobScope, JobStatus
from app.workers import jobs as job_worker

router = APIRouter(tags=["render"])


@router.post("/api/scenes/{scene_id}/render", response_model=schemas.JobCreateResponse)
def render_part_endpoint(scene_id: str, db: Session = Depends(get_db)):
    scene = db.get(Scene, scene_id)
    if not scene:
        raise HTTPException(404, "Scene not found")
    if not scene.shots:
        raise HTTPException(400, "This part has no media yet — add an image or video before generating.")

    job_id = job_worker.reserve_job_id()
    try:
        job = RenderJob(id=job_id, project_id=scene.project_id, scene_id=scene_id, scope=JobScope.PART, status=JobStatus.QUEUED)
        db.add(job)
        db.commit()
        db.refresh(job)
        job_worker.start_part_job(job.id, scene.project_id, scene_id)
    except Exception:
        job_worker.release_job_id(job_id)
        raise
    return {"job_id": job.id}


@router.post("/api/projects/{project_id}/export", response_model=schemas.JobCreateResponse)
def export_project_endpoint(project_id: str, skip_empty: bool = False, body: dict | None = Body(None), db: Session = Depends(get_db)):
    from app.render import delivery
    try:
        settings = delivery.clean((body or {}).get("settings"))
    except delivery.DeliveryError as e:
        raise HTTPException(400, str(e))
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if not project.scenes:
        raise HTTPException(400, "Project has no parts to export.")

    empty = [s.title or f"Scene {s.order_index + 1}" for s in project.scenes if not s.shots]
    if empty and not skip_empty:
        raise HTTPException(400, "These scenes have no media: " + ", ".join(empty) + ". Add media, or choose to export only scenes with media.")
    selected_ids = [s.id for s in project.scenes if s.shots]
    if not selected_ids: raise HTTPException(400, "Add media to at least one scene before exporting.")
    job_id = job_worker.reserve_job_id()
    try:
        job = RenderJob(id=job_id, project_id=project_id, scene_id=None, scope=JobScope.FULL_EXPORT, status=JobStatus.QUEUED)
        db.add(job)
        db.commit()
        db.refresh(job)
        job_worker.start_export_job(job.id, project_id, selected_ids, settings)
    except Exception:
        job_worker.release_job_id(job_id)
        raise
    return {"job_id": job.id}


@router.get("/api/projects/{project_id}/captions")
def project_captions(project_id: str, format: str = "srt", db: Session = Depends(get_db)):
    """Caption file (SRT or VTT) for the whole video, for uploading to YouTube and others."""
    from fastapi.responses import PlainTextResponse
    from app.render import delivery
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if format not in ("srt", "vtt"):
        raise HTTPException(400, "Caption format must be srt or vtt.")
    timed, cursor, prev = [], 0, None
    for s in [s for s in project.scenes if s.shots]:
        length = s.measured_duration_ms or s.natural_duration_ms or s.requested_duration_ms or 4000
        t = s.transition_in_json or {}
        overlap = min(int(t.get("duration_ms") or 0), prev // 2, length // 2) if prev and t.get("type", "cut") != "cut" else 0
        start = cursor - overlap
        timed.append((s, start, length)); cursor, prev = start + length, length
    text = delivery.captions_file(delivery.caption_cues(timed), format)
    name = "".join(ch for ch in (project.title or "captions") if ch.isalnum() or ch in " -_").strip() or "captions"
    return PlainTextResponse(text, media_type="text/vtt" if format == "vtt" else "application/x-subrip",
                             headers={"Content-Disposition": f'attachment; filename="{name}.{format}"'})


@router.get("/api/jobs/{job_id}", response_model=schemas.JobOut)
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(RenderJob, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    result = schemas.JobOut.model_validate(job).model_dump()
    result["result_asset_ids"] = (job.plan_json or {}).get("result_asset_ids", [])
    return result


@router.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(RenderJob, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    ok = job_worker.request_cancel(job_id)
    if not ok:
        raise HTTPException(409, "Job is not currently running")
    return {"ok": True}


@router.get("/api/jobs/{job_id}/events")
async def job_events(job_id: str, db: Session = Depends(get_db)):
    job = db.get(RenderJob, job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    async def event_generator():
        for evt in job_worker.get_events_since(job_id):
            yield {"event": "progress", "data": json.dumps(evt)}
        q = job_worker.subscribe(job_id)
        while True:
            try:
                evt = await asyncio.get_event_loop().run_in_executor(None, q.get, True, 1.0)
                yield {"event": "progress", "data": json.dumps(evt)}
                if evt.get("status") in (JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED):
                    break
            except Exception:
                # queue.Empty from the 1s timeout — send a heartbeat so
                # proxies/browsers don't time out the connection.
                yield {"event": "heartbeat", "data": "{}"}

    return EventSourceResponse(event_generator())


def _scene_start_ms(project, scene_id: str) -> int:
    """Start of a scene on the editor timeline (mirrors frontend sequenceClips)."""
    from app.api.projects import scene_duration_ms
    cursor, previous = 0, None
    for scene in sorted(project.scenes, key=lambda s: s.order_index):
        duration = scene_duration_ms(scene)
        overlap = 0
        transition = scene.transition_in_json or {}
        if previous is not None and previous[0].shots and scene.shots and transition.get("type", "cut") != "cut":
            overlap = min(int(transition.get("duration_ms") or 0), previous[1] / 2, duration / 2)
        start = cursor - overlap
        if scene.id == scene_id:
            return int(start)
        cursor = start + duration
        previous = (scene, duration)
    return 0


def _project_length_ms(project) -> int:
    from app.api.projects import scene_duration_ms
    ordered = sorted(project.scenes, key=lambda s: s.order_index)
    return _scene_start_ms(project, ordered[-1].id) + scene_duration_ms(ordered[-1]) if ordered else 0


@router.get("/api/scenes/{scene_id}/preview-media")
def scene_preview_media(scene_id: str, db: Session = Depends(get_db)):
    """The rendered scene with the timeline audio and music that play under it.

    Cached by content, so it is rebuilt only when the render, the scene's position or the
    project audio changes. Falls back to the plain rendered part when nothing plays under it.
    """
    import hashlib
    import json
    from fastapi.responses import FileResponse, RedirectResponse
    from app.config import RENDERS_DIR
    from app.render import finishing
    from app.render.renderer import _resolve_asset_path
    scene = db.get(Scene, scene_id)
    if not scene or not scene.rendered_asset_id:
        raise HTTPException(404, "Render this scene first.")
    part = db.get(Asset, scene.rendered_asset_id)
    if not part:
        raise HTTPException(404, "The rendered scene file is missing. Render the scene again.")
    project = scene.project
    part_ms = int(part.duration_ms or scene.measured_duration_ms or 0)
    plan = finishing.scene_preview_plan(project.finishing_json or {}, _scene_start_ms(project, scene.id), part_ms, _project_length_ms(project))
    if not plan:
        return RedirectResponse(f"/api/assets/{part.id}/stream", status_code=307)
    key = hashlib.sha256(json.dumps({"part": part.id, "plan": plan}, sort_keys=True).encode()).hexdigest()[:24]
    folder = RENDERS_DIR / "scene_previews"
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / f"{scene.id}_{key}.mp4"
    # One build per scene at a time: the player can request the same mix twice while a
    # render finishes, and two writers on one file produced an unplayable (black) video.
    with _preview_lock(scene.id):
        if not out.exists():
            import uuid as _uuid
            tmp = folder / f"{scene.id}_{key}.{_uuid.uuid4().hex[:8]}.partial.mp4"
            try:
                finishing.mix_scene_preview(_resolve_asset_path(part), plan, str(tmp))
                tmp.replace(out)
            except finishing.FinishingError as e:
                raise HTTPException(400, str(e))
            finally:
                tmp.unlink(missing_ok=True)
            for stale in folder.glob(f"{scene.id}_*.mp4"):
                if stale != out and ".partial." not in stale.name:
                    try:
                        stale.unlink()
                    except OSError:
                        pass  # still being streamed on Windows; removed next time
    return FileResponse(out, media_type="video/mp4")


_PREVIEW_LOCKS: dict = {}


def _preview_lock(scene_id: str):
    import threading
    return _PREVIEW_LOCKS.setdefault(scene_id, threading.Lock())
