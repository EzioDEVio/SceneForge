"""Offline story tools: reusable templates and transactional beat edits."""
from copy import deepcopy
import json
import hashlib
from pathlib import Path
from typing import Literal
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.config import DATA_DIR
from app.db.database import get_db
from app.db.models import Project, Scene, Shot, RenderJob
from app.domain import schemas, snapshots
from app.api.projects import scene_duration_ms
from app.render.media import selected_shots, shot_natural_ms

router = APIRouter(prefix="/api", tags=["story tools"])
TEMPLATE_DIR = Path(DATA_DIR) / "project-templates"

class TemplateSave(BaseModel):
    project_id: str
    name: str = Field(min_length=1, max_length=80)

class TemplateUse(BaseModel):
    title: str = Field(min_length=1, max_length=255)

class CutRequest(BaseModel):
    times_ms: list[int] = Field(max_length=200)
    revision: int | None = None
    preview_token: str | None = None
    video_mode: Literal['repeat', 'continuous'] = 'repeat'


def editable(db, project_id):
    if db.query(RenderJob).filter(RenderJob.project_id == project_id, RenderJob.status.in_(["queued", "running", "cancelling"])).first():
        raise HTTPException(409, "Wait for rendering to finish or cancel it before editing.")


def template_path(template_id):
    try:
        parsed = str(uuid.UUID(template_id))
    except ValueError:
        raise HTTPException(404, "Template not found.") from None
    return TEMPLATE_DIR / f"{parsed}.json"

@router.get("/project-templates")
def list_templates():
    out = []
    for path in TEMPLATE_DIR.glob('*.json'):
        try:
            saved = json.loads(path.read_text(encoding='utf-8'))
            out.append({'id': path.stem, 'name': saved['name'], 'scenes': len(saved['rows']['scenes']), 'aspect': saved['rows']['project']['aspect']})
        except (OSError, ValueError, KeyError):
            continue
    return {'templates': sorted(out, key=lambda t: t['name'].casefold())}

@router.post("/project-templates")
def save_template(body: TemplateSave, db: Session = Depends(get_db)):
    project = db.get(Project, body.project_id)
    if not project:
        raise HTTPException(404, 'Project not found.')
    if not body.name.strip():
        raise HTTPException(400, 'Give this template a name.')
    editable(db, project.id)
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    ident = str(uuid.uuid4())
    path = template_path(ident)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps({'name': body.name.strip(), 'rows': snapshots.project_rows(db, project)}, default=str), encoding='utf-8')
    temporary.replace(path)
    return {'id': ident, 'name': body.name.strip()}

@router.post("/project-templates/{template_id}/create", response_model=schemas.ProjectOut)
def use_template(template_id: str, body: TemplateUse, db: Session = Depends(get_db)):
    path = template_path(template_id)
    if not path.is_file():
        raise HTTPException(404, 'Template not found.')
    try:
        saved = json.loads(path.read_text(encoding='utf-8'))
        # Durable saved rows survive source-project deletion. Media is shared on disk.
        project = snapshots.restore_rows(db, saved['rows'], {}, title=body.title.strip() or saved['name'])
        db.commit()
        db.refresh(project)
        return project
    except (OSError, ValueError, KeyError) as exc:
        db.rollback()
        raise HTTPException(400, 'This template could not be opened.') from exc

@router.delete("/project-templates/{template_id}", status_code=204)
def delete_template(template_id: str):
    path = template_path(template_id)
    if not path.is_file():
        raise HTTPException(404, 'Template not found.')
    path.unlink()


def cut_plan(scene, times, video_mode='repeat'):
    shots = selected_shots(scene)
    if not shots:
        raise HTTPException(400, 'Add images or videos to this scene first.')
    if (scene.look_json or {}).get('layout'):
        raise HTTPException(400, 'AutoCut needs sequential pictures. Turn off the split-screen layout first.')
    if any((s.speed_json or {}).get('ramp') not in (None, 'none') or (s.speed_json or {}).get('freeze_at_ms') is not None for s in shots):
        raise HTTPException(400, 'Turn off speed ramps and freeze frames before AutoCut.')
    project = scene.project
    if (((project.finishing_json or {}).get('timeline') or {}).get('tracks') or {}).get('V1', {}).get('locked'):
        raise HTTPException(409, 'Unlock the Picture track before AutoCut.')
    if (scene.look_json or {}).get('countdown'):
        raise HTTPException(400, 'Turn off the countdown intro before AutoCut.')
    def timeline_length(s):
        return (s.natural_duration_ms if s.timing_mode != 'fixed' and not any(t.accepted for t in s.voice_takes) else None) or scene_duration_ms(s)
    offset = sum(timeline_length(s) + int(((s.look_json or {}).get('countdown') or {}).get('seconds', 0))*1000 for s in project.scenes if s.order_index < scene.order_index)
    total = timeline_length(scene)
    if video_mode == 'continuous' and (len(shots) != 1 or not shot_natural_ms(shots[0]) or shot_natural_ms(shots[0]) < total):
        raise HTTPException(400, 'Continuous video cuts need one selected video excerpt long enough to cover the whole scene. Select one longer video, shorten the scene, or use Repeat pictures.')
    # Timeline beat times are global; cuts are converted to scene-local frame boundaries.
    frame = 1000 / project.fps
    candidates = sorted(set(round((t-offset)/frame)*frame for t in times if offset < t < offset+total))
    cuts = [0]
    for t in candidates:
        t = round(t)
        if t-cuts[-1] >= max(100, frame) and total-t >= max(100, frame):
            cuts.append(t)
    if len(cuts) == 1:
        raise HTTPException(400, 'No cut markers fall inside this scene. Place markers inside it, or choose music that spans this scene.')
    cuts.append(total)
    result = []
    for i, (start, end) in enumerate(zip(cuts, cuts[1:])):
        source = shots[i % len(shots)]
        natural = shot_natural_ms(source)
        if natural and end-start > natural:
            raise HTTPException(400, 'A beat interval is longer than a trimmed video excerpt. Use closer beat markers, a longer excerpt, or images for this scene.')
        values = snapshots._row(source)
        if video_mode == 'continuous':
            speed = max(0.1, min(4.0, float((source.speed_json or {}).get('speed', 1) or 1)))
            origin = source.source_in_ms or 0
            values.update(source_in_ms=origin + round(start * speed), source_out_ms=origin + round(end * speed))
        values.update(id=str(uuid.uuid4()), order_index=i, duration_ms=end-start, is_selected=True)
        result.append(values)
    digest = hashlib.sha256(json.dumps({'revision': scene.revision, 'offset': offset, 'total': total,
        'fps': project.fps, 'times': times, 'video_mode': video_mode, 'shots': [snapshots._row(s) for s in shots]}, sort_keys=True, default=str).encode()).hexdigest()
    return {'preview_token': digest, 'duration_ms': total, 'cuts_ms': cuts[1:-1], 'shots': result, 'revision': scene.revision,
            'video_mode': video_mode, 'note': ('One video continues through each cut; picture and embedded sound use the same source ranges. ' if video_mode == 'continuous' else 'Pictures repeat in order to fill the scene. Video excerpts restart at their current in-point and keep their trim and speed. ') + 'Narration, captions and overlay timing stay in place.'}

@router.post('/scenes/{scene_id}/autocut/preview')
def preview_cut(scene_id: str, body: CutRequest, db: Session = Depends(get_db)):
    scene = db.get(Scene, scene_id)
    if not scene:
        raise HTTPException(404, 'Scene not found.')
    return cut_plan(scene, body.times_ms, body.video_mode)

@router.post('/scenes/{scene_id}/autocut', response_model=schemas.SceneOut)
def apply_cut(scene_id: str, body: CutRequest, db: Session = Depends(get_db)):
    scene = db.get(Scene, scene_id)
    if not scene:
        raise HTTPException(404, 'Scene not found.')
    editable(db, scene.project_id)
    if body.revision is None or scene.revision != body.revision:
        raise HTTPException(409, 'This scene changed. Preview AutoCut again before applying.')
    plan = cut_plan(scene, body.times_ms, body.video_mode)
    if body.preview_token != plan['preview_token']:
        raise HTTPException(409, 'The timeline changed. Preview AutoCut again before applying.')
    # Keep unselected media available; replace only the active picture sequence.
    chosen = selected_shots(scene)
    unused = [s for s in scene.shots if s not in chosen]
    for shot in chosen:
        db.delete(shot)
    for i, shot in enumerate(unused):
        shot.order_index = len(plan['shots'])+i
    for row in plan['shots']:
        db.add(Shot(**row))
    scene.timing_mode = 'fixed'
    scene.requested_duration_ms = plan['duration_ms']
    scene.revision += 1
    scene.rendered_plan_hash = None
    scene.project.revision += 1
    db.commit()
    db.expire_all()
    return db.get(Scene, scene_id)
