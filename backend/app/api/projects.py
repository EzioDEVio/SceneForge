from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Asset, Project, Scene, RenderJob
from app.domain import schemas
from app.domain.constants import ASPECT_DIMENSIONS, AspectRatio
from app.domain.import_parser import parse_script, parse_paragraphs
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
    project = Project(title=body.title, language=body.language, aspect=body.aspect, fps=body.fps, width=w, height=h)
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
    if body.fps is not None:
        project.fps = body.fps
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
    if body.split_mode not in ("headings", "paragraphs"):
        raise HTTPException(400, "Choose headings or paragraphs.")
    text = body.text
    if len(text) > 200_000:
        raise HTTPException(400, "Script is too long; import it in smaller sections.")
    result = parse_paragraphs(text) if body.split_mode == "paragraphs" else parse_script(text)
    if len(result["scenes"]) > 500:
        raise HTTPException(400, "Import at most 500 scenes at a time.")
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
    from app.workers.jobs import active_job_ids
    live_ids = active_job_ids()
    active = db.query(RenderJob).filter(RenderJob.project_id == project_id,
        RenderJob.status.in_(["queued", "running", "cancelling"])).all()
    live = [job for job in active if job.id in live_ids]
    if live:
        raise HTTPException(409, "Wait for rendering to finish or cancel it before deleting this project.")
    # A worker thread cannot survive a desktop-app restart. Recover any stale
    # rows here as well as at startup so a project does not stay undeletable
    # when the editor has been open since a job crashed or was interrupted.
    for job in active:
        message = "Interrupted when SceneForge last closed. Start the render or generation again if you still need it."
        event = {"status": "failed", "stage": "interrupted", "error": message}
        job.status = "failed"
        job.stage = "interrupted"
        job.error = message
        job.events_json = [*(job.events_json or []), event][-200:]
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
    from app.domain.snapshots import delete_all as _drop_snapshots
    _drop_snapshots(project_id)   # 0.9.0 restore points belong to the project
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


@router.post("/{project_id}/music-fit", response_model=schemas.AssetOut)
def music_fit(project_id: str, body: dict | None = None, db: Session = Depends(get_db)):
    """Beat-aware re-edit of a music track to a target length (default: the
    project's length). Removes or repeats whole bars on the beat grid with
    short crossfades and ends with a fade-out. Creates a NEW audio asset; the
    original file is untouched. Rule-based editing, not AI."""
    import hashlib
    import uuid
    from pathlib import Path
    from app.config import MEDIA_DIR, RENDERS_DIR
    from app.db.models import Asset
    from app.domain.constants import AssetOrigin, AssetType
    from app.render.beats import detect_beats
    from app.render.ffmpeg_utils import probe
    from app.render.music_fit import MusicFitError, render_fit
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    body = body or {}
    if not isinstance(body, dict) or set(body) - {"asset_id", "target_ms"}:
        raise HTTPException(400, "Music fit takes asset_id and target_ms.")
    asset = db.get(Asset, body.get("asset_id")) if isinstance(body.get("asset_id"), str) else None
    if not asset or asset.type != "audio" or asset.project_id != project_id:
        raise HTTPException(400, "Choose a music file from this project.")
    target = body.get("target_ms")
    if target is None:
        target = sum(scene_duration_ms(s) for s in project.scenes if s.shots)
    if isinstance(target, bool) or not isinstance(target, (int, float)) or not 2000 <= target <= 4 * 3600 * 1000:
        raise HTTPException(400, "Target length must be between 2 seconds and 4 hours (add scenes first if the video is empty).")
    src = str(Path(RENDERS_DIR if asset.origin == "render_output" else MEDIA_DIR) / asset.storage_key)
    dur_ms = asset.duration_ms or probe(src).duration_ms
    if not dur_ms:
        raise HTTPException(422, "The length of this music file could not be read.")
    try:
        bpm, beats = detect_beats(src)
    except Exception:
        raise HTTPException(422, "The music could not be analysed.")
    if not beats:
        raise HTTPException(422, "No steady beat was found in this music, so it cannot be re-edited on the beat.")
    folder = Path(MEDIA_DIR) / project_id
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / f"musicfit_{uuid.uuid4().hex[:10]}.wav"
    try:
        render_fit(src, str(out), dur_ms / 1000, target / 1000, beats)
    except MusicFitError as e:
        raise HTTPException(422, str(e))
    stem = Path(asset.original_filename or "music").stem
    new = Asset(project_id=project_id, type=AssetType.AUDIO, content_hash=hashlib.sha256(out.read_bytes()).hexdigest(),
                storage_key=str(out.relative_to(MEDIA_DIR)), mime="audio/wav",
                original_filename=f"{stem} (fit {target / 1000:.1f}s).wav", duration_ms=probe(str(out)).duration_ms or int(target),
                origin=AssetOrigin.GENERATED, generation_metadata_json={"music_fit": {"source_asset_id": asset.id, "target_ms": int(target), "bpm": bpm}})
    db.add(new)
    db.commit()
    db.refresh(new)
    return new


@router.post("/{project_id}/beat-markers")
def beat_markers(project_id: str, body: dict | None = None, db: Session = Depends(get_db)):
    """Beat times on the timeline, for markers that cuts and clips snap to.

    Source: a timeline audio clip (A3–A8, placed at its sequence time and trimmed), or
    the music bed (which starts at 0 and loops). every=1 marks each beat, 2/4 every
    2nd/4th (bars), with downbeats labelled. Nothing is changed here; the editor adds
    the returned markers as one undoable edit.
    """
    from app.render.beats import detect_beats
    from app.render.renderer import _resolve_asset_path
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    body = body or {}
    every = body.get("every", 1)
    if every not in (1, 2, 4):
        raise HTTPException(400, "every must be 1, 2 or 4.")
    fin = project.finishing_json or {}
    clip_id = body.get("clip_id")
    if clip_id:
        clip = next((c for c in fin.get("audio_clips") or [] if c.get("id") == clip_id), None)
        if not clip:
            raise HTTPException(400, "That timeline audio clip was not found.")
        asset_id, offset, start, end = clip["asset_id"], int(clip["start_ms"]) - int(clip["source_in_ms"]), int(clip["source_in_ms"]), int(clip["source_out_ms"])
        loop = False
    elif fin.get("music"):
        asset_id, offset, start, end, loop = fin["music"]["asset_id"], 0, 0, None, True
    else:
        raise HTTPException(400, "Add a music bed or select a timeline audio clip first.")
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(400, "The audio file is missing.")
    try:
        bpm, beats = detect_beats(_resolve_asset_path(asset))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Could not analyse the beat: {e}")
    if not beats or bpm <= 0:
        raise HTTPException(400, "No steady beat was found in this audio.")
    times = [round(b * 1000) for b in beats]
    if loop and asset.duration_ms:
        scene_total = sum(scene_duration_ms(s) for s in project.scenes)
        length = scene_total
        reps, base = [], list(times)
        k = 1
        while base and base[-1] + k * asset.duration_ms < length and len(reps) < 2000:
            reps += [t + k * int(asset.duration_ms) for t in base]
            k += 1
        times = [t for t in base + reps if t < scene_total]
    else:
        times = [t for t in times if start <= t <= (end if end is not None else t)]
    out = [{"time_ms": t + offset, "downbeat": i % 4 == 0} for i, t in enumerate(times) if i % every == 0 and t + offset >= 0]
    return {"bpm": round(bpm, 1), "markers": out[:200], "truncated": len(out) > 200}


@router.get("/{project_id}/layer-preview")
def layer_preview(project_id: str, style: str, db: Session = Depends(get_db)):
    import json
    from fastapi.responses import FileResponse
    from app.render.layer_clips import clean_layer_clips, text_raster
    from app.render.finishing import FinishingError
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if len(style) > 5000:
        raise HTTPException(400, "Text preview settings are too long.")
    try:
        clip = clean_layer_clips([json.loads(style)], project_id, db)[0]
        if clip['kind'] in ('image', 'video'):
            raise FinishingError('This preview is for text clips.')
        path = text_raster(clip, project.width, project.height)
    except (FinishingError, ValueError, TypeError) as exc:
        raise HTTPException(400, str(exc))
    return FileResponse(path, media_type="image/png")
