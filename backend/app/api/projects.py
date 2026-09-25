from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Project, Scene, RenderJob
from app.domain import schemas
from app.domain.constants import ASPECT_DIMENSIONS, AspectRatio
from app.domain.import_parser import parse_script
from app.render.timeline import is_stale

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _scene_to_out(scene: Scene, canvas: tuple[int, int], fps: int) -> schemas.SceneOut:
    out = schemas.SceneOut.model_validate(scene)
    out.is_stale = is_stale(scene, canvas, fps) if scene.shots else True
    return out


@router.post("", response_model=schemas.ProjectOut)
def create_project(body: schemas.ProjectCreate, db: Session = Depends(get_db)):
    if body.aspect not in [a.value for a in AspectRatio]:
        raise HTTPException(400, f"Unsupported aspect '{body.aspect}'")
    w, h = ASPECT_DIMENSIONS[AspectRatio(body.aspect)]
    project = Project(title=body.title, language=body.language, aspect=body.aspect, width=w, height=h)
    db.add(project)
    db.flush()
    # Spec: "Start a new project with three editable rows, labeled
    # Part-1, Part-2, Part-3."
    for i in range(3):
        db.add(Scene(project_id=project.id, order_index=i, title=f"Part-{i+1}"))
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=list[schemas.ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return db.query(Project).order_by(Project.updated_at.desc()).all()


@router.get("/{project_id}", response_model=dict)
def get_project(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    canvas = (project.width, project.height)
    return {
        **schemas.ProjectOut.model_validate(project).model_dump(),
        "scenes": [_scene_to_out(s, canvas, project.fps).model_dump() for s in project.scenes],
    }


@router.patch("/{project_id}", response_model=schemas.ProjectOut)
def update_project(project_id: str, body: schemas.ProjectUpdate, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if body.aspect is not None:
        if body.aspect not in [a.value for a in AspectRatio]:
            raise HTTPException(400, f"Unsupported aspect '{body.aspect}'")
        project.aspect = body.aspect
        project.width, project.height = ASPECT_DIMENSIONS[AspectRatio(body.aspect)]
    if body.title is not None:
        project.title = body.title
    if body.language is not None:
        project.language = body.language
    if body.finishing is not None:
        from app.render.finishing import FinishingError, clean_finishing
        try:
            project.finishing_json = clean_finishing(body.finishing, project.id, db)
        except FinishingError as e:
            raise HTTPException(400, str(e))
    project.revision += 1
    db.commit()
    db.refresh(project)
    return project


@router.post("/{project_id}/scenes", response_model=schemas.SceneOut)
def add_scene(project_id: str, body: schemas.SceneCreate, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    max_order = max([s.order_index for s in project.scenes], default=-1)
    n = len(project.scenes) + 1
    scene = Scene(
        project_id=project_id,
        order_index=max_order + 1,
        title=body.title or f"Part-{n}",
        original_text=body.original_text,
        spoken_text=body.original_text,
        subtitle_text=body.original_text,
        font_json=project.default_font_json.copy(),
    )
    db.add(scene)
    db.commit()
    db.refresh(scene)
    return scene


@router.put("/{project_id}/scene-order")
def reorder_scenes(project_id: str, body: schemas.ReorderRequest, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    scene_ids = set(s.id for s in project.scenes)
    if set(body.scene_ids) != scene_ids:
        raise HTTPException(400, "scene_ids must be a permutation of the project's current scenes")
    for idx, sid in enumerate(body.scene_ids):
        scene = db.get(Scene, sid)
        scene.order_index = idx
    project.revision += 1
    db.commit()
    return {"ok": True}


@router.post("/{project_id}/import", response_model=schemas.ImportPreviewResponse)
def import_preview(project_id: str, body: schemas.ImportPreviewRequest, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    result = parse_script(body.text)
    return schemas.ImportPreviewResponse(**result)


@router.post("/{project_id}/import/apply", response_model=list[schemas.SceneOut])
def import_apply(project_id: str, body: schemas.ImportApplyRequest, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if body.replace_existing:
        for s in list(project.scenes):
            db.delete(s)
        db.flush()
        start_index = 0
    else:
        start_index = max([s.order_index for s in project.scenes], default=-1) + 1

    created = []
    for i, sc in enumerate(body.scenes):
        scene = Scene(
            project_id=project_id,
            order_index=start_index + i,
            title=sc.title,
            original_text=sc.original_text,
            spoken_text=sc.spoken_text,
            subtitle_text=sc.subtitle_text,
            source_refs_json=sc.source_refs,
            font_json=project.default_font_json.copy(),
        )
        db.add(scene)
        created.append(scene)
    db.commit()
    for s in created:
        db.refresh(s)
    return created


@router.delete("/{project_id}")
def delete_project(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    active = db.query(RenderJob).filter(RenderJob.project_id == project_id,
        RenderJob.status.in_(["queued", "running", "cancelling"])).first()
    if active:
        raise HTTPException(409, "Wait for rendering to finish or cancel it before deleting this project.")
    # Clear cross-table references before cascading the owning rows.
    for scene in project.scenes:
        scene.rendered_asset_id = None
    for job in project.jobs:
        job.artifact_asset_id = None
    db.flush()
    for job in list(project.jobs): db.delete(job)
    db.flush()
    for scene in list(project.scenes): db.delete(scene)
    db.flush()
    db.expire(project, ["jobs", "scenes"])
    db.delete(project)
    db.commit()
    return {"ok": True, "media_retained": True}


def scene_duration_ms(scene) -> int:
    """Current scene length, matching the editor timeline (frontend duration.ts)."""
    from app.render.audio_edit import effective_ms
    if scene.timing_mode == "fixed" and scene.requested_duration_ms:
        return int(scene.requested_duration_ms)
    take = next((t for t in scene.voice_takes if t.accepted), None)
    audio = effective_ms(take.measured_duration_ms, take.edit_json) if take and take.measured_duration_ms else None
    if audio:
        lead = 250 if scene.lead_ms is None else scene.lead_ms
        trail = 400 if scene.trail_ms is None else scene.trail_ms
        return int(audio + lead + trail)
    return int(scene.measured_duration_ms or scene.requested_duration_ms or 4000)


@router.post("/{project_id}/beat-sync")
def beat_sync(project_id: str, db: Session = Depends(get_db)):
    """Find the beats in the background music and change fixed-length scenes
    so each cut lands on a beat. Scenes that follow their narration keep
    their length."""
    from pathlib import Path
    from app.config import MEDIA_DIR
    from app.db.models import Asset
    from app.render.beats import detect_beats, snap_durations
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    music = (project.finishing_json or {}).get("music")
    asset = db.get(Asset, music["asset_id"]) if music else None
    if not asset:
        raise HTTPException(400, "Choose background music first (Audio → Music & finishing).")
    bpm, beats = detect_beats(str(Path(MEDIA_DIR) / asset.storage_key))
    if not beats:
        raise HTTPException(422, "No steady beat was found in this music.")
    scenes = [s for s in project.scenes if s.shots]
    durations = [scene_duration_ms(s) for s in scenes]
    fixed = [s.timing_mode == "fixed" for s in scenes]
    new = snap_durations(durations, fixed, beats)
    changed = 0
    for s, old_ms, new_ms, is_fixed in zip(scenes, durations, new, fixed):
        if is_fixed and new_ms != old_ms:
            s.requested_duration_ms = new_ms; s.revision += 1; changed += 1
    project.revision += 1
    db.commit()
    return {"bpm": bpm, "beats": beats[:2000], "scenes_changed": changed, "scenes_kept": sum(not f for f in fixed)}
