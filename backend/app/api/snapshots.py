"""Project restore points (0.9.0). See app/domain/snapshots.py.

  GET    /api/projects/{id}/snapshots                    newest first
  POST   /api/projects/{id}/snapshots   {auto?, label?}  save one now (auto: only if changed)
  POST   /api/projects/{id}/snapshots/{snap}/restore     -> a NEW project with the snapshot's content
  DELETE /api/projects/{id}/snapshots/{snap}
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Project
from app.domain import schemas
from app.domain import snapshots as snap

router = APIRouter(tags=["snapshots"])


def _project(db: Session, project_id: str) -> Project:
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    return p


@router.get("/api/projects/{project_id}/snapshots")
def list_snapshots(project_id: str, db: Session = Depends(get_db)):
    _project(db, project_id)
    return {"snapshots": [{k: v for k, v in s.items() if k not in ("hash", "seq")} for s in snap.list_snapshots(project_id)]}


@router.post("/api/projects/{project_id}/snapshots")
def save_snapshot(project_id: str, body: dict | None = Body(None), db: Session = Depends(get_db)):
    body = body or {}
    p = _project(db, project_id)
    result = snap.save_snapshot(db, p, reason="auto" if body.get("auto") else "manual", label=str(body.get("label") or ""))
    if result is None:
        return {"saved": False, "reason": "No changes since the last restore point."}
    return {"saved": True, "snapshot": {k: v for k, v in result.items() if k not in ("hash", "seq")}}


@router.post("/api/projects/{project_id}/snapshots/{snap_id}/restore", response_model=schemas.ProjectOut)
def restore_snapshot(project_id: str, snap_id: str, db: Session = Depends(get_db)):
    try:
        project = snap.restore_snapshot(db, project_id, snap_id)
    except snap.SnapshotError as exc:
        raise HTTPException(404, str(exc)) from None
    db.commit()
    db.refresh(project)
    return project


@router.delete("/api/projects/{project_id}/snapshots/{snap_id}", status_code=204)
def delete_snapshot(project_id: str, snap_id: str):
    try:
        ok = snap.delete_snapshot(project_id, snap_id)
    except snap.SnapshotError:
        ok = False
    if not ok:
        raise HTTPException(404, "That restore point no longer exists.")


@router.post("/api/sample-project", response_model=schemas.ProjectOut)
def create_sample_project(db: Session = Depends(get_db)):
    """0.9.0: a ready-made project for new users (Projects page → Try a sample project)."""
    from app.domain.sample_project import create_sample_project as build
    try:
        return build(db)
    except Exception as exc:   # FFmpeg/Pillow problems are reported, not a crash
        db.rollback()
        raise HTTPException(500, f"The sample project could not be created: {exc}") from None
