"""Validated, atomic editor transactions and isolated renderer snapshots."""
from copy import deepcopy
from pydantic import ValidationError

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Scene, Shot, RenderJob
from app.domain import schemas
from app.domain.constants import JobScope, JobStatus
from app.api.scenes import update_scene, update_shot, _out

router = APIRouter(prefix='/api/scenes', tags=['editor drafts'])


class TransactionSession:
    """Reuse established validators without their per-operation commits."""
    def __init__(self, db): self.db = db
    def __getattr__(self, key): return getattr(self.db, key)
    def commit(self): self.db.flush()
    def refresh(self, obj): pass


def apply_edits(scene, body, db):
    if not isinstance(body, dict) or set(body) - {'revision', 'scene', 'shots', 'replace'}:
        raise HTTPException(400, 'Invalid editor transaction.')
    if body.get('revision') is not None and body['revision'] != scene.revision:
        raise HTTPException(409, 'The saved scene changed. Cancel and start from its latest settings.')
    patch = body.get('scene', {})
    if not isinstance(patch, dict) or set(patch) - set(schemas.SceneUpdate.model_fields):
        raise HTTPException(400, 'Invalid scene settings.')
    shots = body.get('shots', [])
    if not isinstance(shots, list) or len(shots) > len(scene.shots):
        raise HTTPException(400, 'Invalid media settings.')
    allowed = {'fit', 'crop', 'motion', 'speed'}
    seen = set()
    for row in shots:
        if not isinstance(row, dict) or set(row) != {'id', 'patch'} or row['id'] in seen:
            raise HTTPException(400, 'Invalid or repeated media clip.')
        seen.add(row['id'])
        shot = db.get(Shot, row['id'])
        if not shot or shot.scene_id != scene.id:
            raise HTTPException(400, 'Media must belong to this scene.')
        if not isinstance(row['patch'], dict) or set(row['patch']) - allowed:
            raise HTTPException(400, 'Only framing, crop, movement and speed are draft media settings.')
    proxy = TransactionSession(db)
    if body.get('replace'):
        if 'font' in patch: scene.font_json = {}
        if 'look' in patch: scene.look_json = {}
    if patch:
        try:
            validated = schemas.SceneUpdate.model_validate(patch)
        except ValidationError as exc:
            raise HTTPException(422, 'Invalid scene setting values.') from exc
        update_scene(scene.id, validated, proxy)
    for row in shots:
        # Exact crop restoration includes removal of an old reframe track.
        if body.get('replace') and 'crop' in row['patch']: db.get(Shot, row['id']).crop_json = None
        update_shot(row['id'], deepcopy(row['patch']), proxy)
    return scene


@router.post('/{scene_id}/editor-state', response_model=schemas.SceneOut)
def save_state(scene_id: str, body: dict, db: Session = Depends(get_db)):
    scene = db.get(Scene, scene_id)
    if not scene: raise HTTPException(404, 'Scene not found.')
    try:
        apply_edits(scene, body, db)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(scene)
    return _out(scene)


@router.post('/{scene_id}/draft-preview', response_model=schemas.JobCreateResponse)
def preview(scene_id: str, body: dict, db: Session = Depends(get_db)):
    scene = db.get(Scene, scene_id)
    if not scene: raise HTTPException(404, 'Scene not found.')
    if not scene.shots: raise HTTPException(400, 'Add media before previewing.')
    try:
        apply_edits(scene, body, db)
        project = scene.project
        # Load every renderer dependency before detaching the isolated snapshot.
        _ = [(s.asset, s.scene) for s in scene.shots]
        _ = [t.audio_asset for t in scene.voice_takes]
        _ = project.scenes
        db.expunge_all()
        snapshot = deepcopy((scene, project))
    finally:
        db.rollback()
    from app.workers import jobs
    job_id = jobs.reserve_job_id()
    try:
        db.add(RenderJob(id=job_id, project_id=project.id, scene_id=scene_id,
                         scope=JobScope.PART, status=JobStatus.QUEUED))
        db.commit()
        jobs.start_part_job(job_id, project.id, scene_id, snapshot)
    except Exception:
        db.rollback()
        jobs.release_job_id(job_id)
        raise
    return {'job_id': job_id}
