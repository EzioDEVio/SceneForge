from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Project, RenderJob, Scene
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

    job = RenderJob(project_id=scene.project_id, scene_id=scene_id, scope=JobScope.PART, status=JobStatus.QUEUED)
    db.add(job)
    db.commit()
    db.refresh(job)
    job_worker.start_part_job(job.id, scene.project_id, scene_id)
    return {"job_id": job.id}


@router.post("/api/projects/{project_id}/export", response_model=schemas.JobCreateResponse)
def export_project_endpoint(project_id: str, skip_empty: bool = False, db: Session = Depends(get_db)):
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
    job = RenderJob(project_id=project_id, scene_id=None, scope=JobScope.FULL_EXPORT, status=JobStatus.QUEUED)
    db.add(job)
    db.commit()
    db.refresh(job)
    job_worker.start_export_job(job.id, project_id, selected_ids)
    return {"job_id": job.id}


@router.get("/api/jobs/{job_id}", response_model=schemas.JobOut)
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(RenderJob, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


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
