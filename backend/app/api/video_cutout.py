"""Video subject cutout ("text behind a moving subject"), see render/video_cutout.py.

  GET  /api/scenes/{scene_id}/subject-video-layer?model=   eligibility, frame count, time estimate
  POST /api/scenes/{scene_id}/subject-video-layer          {model?, edge?, shift?} -> background job (or cached layer)
  GET  /api/cutout/video-jobs/{job_id}                     frames done/total, ms per frame, status, notes
  cancel with POST /api/jobs/{job_id}/cancel (shared job infrastructure)
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Asset, RenderJob, Scene

router = APIRouter(tags=["creative"])


class VideoCutoutRequest(BaseModel):
    model: Literal["human", "isnet", "u2netp"] = "u2netp"
    edge: Literal["soft", "crisp"] = "soft"
    shift: int = Field(default=0, ge=-10, le=10)


def _scene(db: Session, scene_id: str) -> Scene:
    scene = db.get(Scene, scene_id)
    if not scene:
        raise HTTPException(404, "Scene not found")
    return scene


def _plan(scene: Scene) -> dict:
    from app.render.video_cutout import VideoCutoutError, plan_for_scene
    try:
        return plan_for_scene(scene)
    except VideoCutoutError as e:
        raise HTTPException(400, str(e))


def _cached_layer(db: Session, project_id: str, key: str) -> Asset | None:
    from app.api.creative import _asset_file
    for a in db.query(Asset).filter(Asset.project_id == project_id, Asset.type == "video").all():
        if (a.generation_metadata_json or {}).get("subject_video_layer_key") == key and _asset_file(a).is_file():
            return a
    return None


def _estimate(plan: dict, model: str) -> dict:
    from app.render.video_cutout import ms_per_frame, _measured, _load_speeds
    per = ms_per_frame(model, plan["w"], plan["h"])
    return {"frames": plan["frames"], "seconds_of_video": round(plan["frames"] / plan["fps"], 2), "ms_per_frame": round(per),
            "estimate_s": round(plan["frames"] * per / 1000), "measured": model in _measured or model in _load_speeds()}


@router.get("/api/scenes/{scene_id}/subject-video-layer")
def subject_video_estimate(scene_id: str, model: Literal["human", "isnet", "u2netp"] = "u2netp", db: Session = Depends(get_db)):
    from app.render.video_cutout import VideoCutoutError, layer_key, plan_for_scene, running_job_for_scene
    scene = _scene(db, scene_id)
    try:
        plan = plan_for_scene(scene)
    except VideoCutoutError as e:
        return {"ok": False, "reason": str(e)}
    hit = _cached_layer(db, scene.project_id, layer_key(plan, model, "soft", 0))
    return {"ok": True, **_estimate(plan, model), "cached_soft": bool(hit), "running_job_id": running_job_for_scene(scene_id), "notes": plan["notes"]}


@router.post("/api/scenes/{scene_id}/subject-video-layer")
def subject_video_layer(scene_id: str, body: VideoCutoutRequest | None = None, db: Session = Depends(get_db)):
    """Start cutting the moving subject out of the scene's video (or reuse a cached layer)."""
    from app.render import video_cutout as vc
    from app.workers import jobs as job_worker
    body = body or VideoCutoutRequest()
    scene = _scene(db, scene_id)
    plan = _plan(scene)
    key = vc.layer_key(plan, body.model, body.edge, body.shift)
    hit = _cached_layer(db, scene.project_id, key)
    if hit:
        from app.api.creative import _scene_out
        cleaned = vc.apply_overlay(db, scene, hit, plan)
        db.commit()
        db.refresh(scene)
        return {"status": "done", "cached": True, "scene": _scene_out(scene), "overlay": next(o for o in cleaned if o["kind"] == "subject"),
                "notes": plan["notes"]}
    existing = vc.running_job_for_scene(scene_id)
    if existing:
        return {"status": "running", "job_id": existing, **_estimate(plan, body.model)}
    if vc.any_running():
        raise HTTPException(409, "Another video cutout is running. Wait for it to finish or cancel it, then try again.")
    job_id = job_worker.reserve_job_id()
    try:
        db.add(RenderJob(id=job_id, project_id=scene.project_id, scene_id=scene_id, scope="cutout", status="queued", stage="queued"))
        db.commit()
        vc.start_job(job_id, scene_id, body.model, body.edge, body.shift, plan["frames"])
    except Exception:
        job_worker.release_job_id(job_id)
        raise
    return {"status": "running", "job_id": job_id, **_estimate(plan, body.model), "notes": plan["notes"]}


@router.get("/api/cutout/video-jobs/{job_id}")
def video_cutout_job(job_id: str, db: Session = Depends(get_db)):
    from app.render.video_cutout import job_status
    st = job_status(job_id)
    if st:
        return st
    job = db.get(RenderJob, job_id)
    if not job or job.scope != "cutout":
        raise HTTPException(404, "This cutout job is no longer known. Start it again.")
    plan = job.plan_json or {}
    return {"job_id": job_id, "scene_id": job.scene_id, "status": job.status, "stage": job.stage, "error": job.error,
            "frames_done": plan.get("frames"), "frames_total": plan.get("frames"), "ms_per_frame": plan.get("ms_per_frame"),
            "notes": plan.get("notes", [])}
