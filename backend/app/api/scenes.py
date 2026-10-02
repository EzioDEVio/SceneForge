from __future__ import annotations

from copy import deepcopy

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Project, Scene
from app.domain import schemas
from app.domain.constants import EffectPreset, TransitionType
from app.render.timeline import is_stale

router = APIRouter(prefix="/api/scenes", tags=["scenes"])


def _out(scene: Scene) -> schemas.SceneOut:
    project = scene.project
    out = schemas.SceneOut.model_validate(scene)
    out.is_stale = is_stale(scene, (project.width, project.height), project.fps) if scene.shots else True
    return out


@router.get("/{scene_id}", response_model=schemas.SceneOut)
def get_scene(scene_id: str, db: Session = Depends(get_db)):
    scene = db.get(Scene, scene_id)
    if not scene:
        raise HTTPException(404, "Scene not found")
    return _out(scene)


@router.patch("/{scene_id}", response_model=schemas.SceneOut)
def update_scene(scene_id: str, body: schemas.SceneUpdate, db: Session = Depends(get_db)):
    scene = db.get(Scene, scene_id)
    if not scene:
        raise HTTPException(404, "Scene not found")

    if body.title is not None:
        scene.title = body.title
    if body.original_text is not None:
        scene.original_text = body.original_text
    if body.spoken_text is not None:
        scene.spoken_text = body.spoken_text
        # Existing accepted takes no longer match the current spoken text.
        for t in scene.voice_takes:
            t.stale = True
    if body.subtitle_text is not None:
        scene.subtitle_text = body.subtitle_text
    if body.effect_preset is not None:
        if body.effect_preset not in [e.value for e in EffectPreset]:
            raise HTTPException(400, f"Unknown effect preset '{body.effect_preset}'")
        scene.effect_preset = body.effect_preset
    if body.effect_intensity is not None:
        scene.effect_intensity = max(0, min(100, body.effect_intensity))
    if body.transition_in is not None:
        if body.transition_in.get("type") not in [t.value for t in TransitionType]:
            raise HTTPException(400, "Unknown transition type")
        duration = body.transition_in.get("duration_ms", 0)
        if isinstance(duration, bool) or not isinstance(duration, int) or not 0 <= duration <= 30000:
            raise HTTPException(400, "Transition duration must be an integer from 0 to 30000 milliseconds.")
        scene.transition_in_json = {"type": body.transition_in["type"], "duration_ms": duration}
    if body.look is not None:
        scene.look_json = _validated_look(scene, body.look, db)
    if body.overlays is not None:
        from app.render.overlays import OverlayError, clean_overlays
        try:
            scene.overlays_json = clean_overlays(body.overlays, scene.project_id, db)
        except OverlayError as e:
            raise HTTPException(400, str(e))
    if body.font is not None:
        from app.db.models import Asset
        for key, low, high in [('typewriter_volume', 0, 100), ('typewriter_delay_ms', 0, 120000), ('typewriter_duration_ms', 100, 120000)]:
            if key in body.font:
                try:
                    value = float(body.font[key])
                    if not low <= value <= high: raise ValueError()
                    body.font[key] = int(value)
                except (ValueError, TypeError, OverflowError):
                    raise HTTPException(400, f'{key} must be between {low} and {high}.')
        for key in ('typewriter_sound', 'typewriter', 'captions_enabled'):
            if key in body.font and not isinstance(body.font[key], bool):
                raise HTTPException(400, f'{key} must be true or false.')
        sound_id = body.font.get('typewriter_sound_asset_id')
        if sound_id:
            if not isinstance(sound_id, str): raise HTTPException(400, 'Invalid sound asset.')
            sound = db.get(Asset, sound_id)
            if not sound or sound.project_id != scene.project_id or sound.type != 'audio':
                raise HTTPException(400, 'Choose an audio asset belonging to this project.')
        _validate_caption_style(body.font)
        if 'caption_animation' in body.font and body.font['caption_animation'] not in CAPTION_ANIMATIONS:
            raise HTTPException(400, 'Caption animation must be one of: ' + ', '.join(CAPTION_ANIMATIONS) + '.')
        if 'caption_animation_ms' in body.font:
            v = body.font['caption_animation_ms']
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not 100 <= v <= 10000:
                raise HTTPException(400, 'Caption animation length must be between 100 and 10000 ms.')
            body.font['caption_animation_ms'] = int(v)
        if 'layers' in body.font:
            from pydantic import ValidationError
            try:
                layers = body.font['layers']
                if not isinstance(layers, list) or len(layers) > 12: raise ValueError()
                from app.render.keyframes import KeyframeError, with_text_keyframes
                try:
                    body.font['layers'] = [with_text_keyframes(layer, schemas.TextLayer.model_validate(layer).model_dump()) for layer in layers]
                except KeyframeError as e:
                    raise HTTPException(400, str(e)) from None
                if any(l['end_ms'] and l['end_ms'] <= l['start_ms'] for l in body.font['layers']): raise ValueError()
            except (ValidationError, ValueError, TypeError):
                raise HTTPException(400, 'Text layers need valid positions, colors, sizes and end times after start times (maximum 12 layers).')
        if 'caption_segments' in body.font:
            try:
                segments = body.font['caption_segments']
                if not isinstance(segments, list) or len(segments) > 2000: raise ValueError()
                clean = []
                for segment in segments:
                    if not isinstance(segment, dict): raise ValueError()
                    sid, text = segment.get('id'), segment.get('text')
                    start, end = segment.get('start_ms'), segment.get('end_ms')
                    if not isinstance(sid, str) or len(sid) > 80 or not isinstance(text, str) or len(text) > 2000: raise ValueError()
                    if isinstance(start, bool) or not isinstance(start, int) or isinstance(end, bool) or not isinstance(end, int) or start < 0 or end <= start or end > 3_600_000: raise ValueError()
                    clean.append({'id': sid, 'text': text, 'start_ms': start, 'end_ms': end})
                body.font['caption_segments'] = clean
            except (ValueError, TypeError):
                raise HTTPException(400, 'Caption segments need text and valid start/end times (maximum 2,000 segments).')
        scene.font_json = {**scene.font_json, **body.font}
    if body.lead_ms is not None:
        scene.lead_ms = body.lead_ms
    if body.trail_ms is not None:
        scene.trail_ms = body.trail_ms
    if body.requested_duration_ms is not None:
        scene.requested_duration_ms = body.requested_duration_ms
    if body.timing_mode is not None:
        scene.timing_mode = body.timing_mode

    scene.revision += 1
    db.commit()
    db.refresh(scene)
    return _out(scene)


@router.delete("/{scene_id}")
def delete_scene(scene_id: str, db: Session = Depends(get_db)):
    from app.db.models import RenderJob

    scene = db.get(Scene, scene_id)
    if not scene:
        raise HTTPException(404, "Scene not found")
    project = scene.project
    # RenderJob.scene_id has no cascade relationship (a job is a log of
    # what happened, not owned data the way shots/voice_takes are) — so
    # deleting a scene that was ever rendered violates the foreign key
    # constraint unless we clear those references first. We keep the job
    # rows (useful history) but detach them from the deleted scene rather
    # than deleting the history outright.
    for job in db.query(RenderJob).filter(RenderJob.scene_id == scene_id).all():
        job.scene_id = None
    db.delete(scene)
    db.flush()
    remaining = sorted((s for s in project.scenes if s.id != scene_id), key=lambda s: s.order_index)
    for idx, s in enumerate(remaining):
        s.order_index = idx
    db.commit()
    return {"ok": True}


@router.post("/{scene_id}/restore", response_model=schemas.SceneOut)
def restore_scene(scene_id: str, body: dict, db: Session = Depends(get_db)):
    """Restore a scene snapshot for timeline undo while preserving media IDs."""
    from app.db.models import Asset, RenderJob, Shot, VoiceTake

    project_id = body.get("project_id")
    project = db.get(Project, project_id) if isinstance(project_id, str) else None
    if not project:
        raise HTTPException(404, "Project not found")
    if body.get("id") != scene_id:
        raise HTTPException(400, "Scene snapshot ID does not match the restore path")
    shots, takes = body.get("shots") or [], body.get("voice_takes") or []
    if not isinstance(shots, list) or not isinstance(takes, list):
        raise HTTPException(400, "Scene clips and narration takes must be lists")
    if any(not isinstance(row, dict) or not isinstance(row.get("id"), str) for row in shots):
        raise HTTPException(400, "Every restored clip needs its original ID")
    if any(not isinstance(row, dict) or not isinstance(row.get("id"), str) for row in takes):
        raise HTTPException(400, "Every restored narration take needs its original ID")
    for row in shots:
        asset = db.get(Asset, row.get("asset_id"))
        if not asset or asset.project_id != project.id:
            raise HTTPException(400, "Scene media must belong to this project")
    for row in takes:
        asset_id = row.get("audio_asset_id")
        asset = db.get(Asset, asset_id) if asset_id else None
        if asset_id and (not asset or asset.project_id != project.id or asset.type != "audio"):
            raise HTTPException(400, "Narration audio must belong to this project")
    rendered_id = body.get("rendered_asset_id")
    rendered = db.get(Asset, rendered_id) if rendered_id else None
    if rendered_id and (not rendered or rendered.project_id != project.id):
        raise HTTPException(400, "Rendered media must belong to this project")

    current = db.get(Scene, scene_id)
    if current and current.project_id != project.id:
        raise HTTPException(400, "Scene belongs to another project")
    order = max(0, int(body.get("order_index", 0)))
    if current:
        previous_order = current.order_index
        order = min(order, previous_order)
        for job in db.query(RenderJob).filter(RenderJob.scene_id == scene_id).all():
            job.scene_id = None
        db.delete(current)
        db.flush()
        if order < previous_order:
            siblings = db.query(Scene).filter(Scene.project_id == project.id, Scene.order_index >= order, Scene.order_index < previous_order).all()
            for sibling in siblings: sibling.order_index += 1
        elif order > previous_order:
            siblings = db.query(Scene).filter(Scene.project_id == project.id, Scene.order_index > previous_order, Scene.order_index <= order).all()
            for sibling in siblings: sibling.order_index -= 1
    else:
        for sibling in db.query(Scene).filter(Scene.project_id == project.id, Scene.order_index >= order).all():
            sibling.order_index += 1

    scene_fields = ("title", "original_text", "spoken_text", "subtitle_text", "source_refs_json", "timing_mode",
        "requested_duration_ms", "lead_ms", "trail_ms", "effect_preset", "effect_intensity", "transition_in_json",
        "font_json", "look_json", "overlays_json", "revision", "rendered_plan_hash", "rendered_asset_id", "measured_duration_ms")
    scene = Scene(id=scene_id, project_id=project.id, order_index=order, **{k: body[k] for k in scene_fields if k in body})
    db.add(scene); db.flush()
    shot_fields = ("order_index", "asset_id", "is_selected", "source_in_ms", "source_out_ms", "duration_ms", "speed_json", "audio_json", "fit", "crop_json", "motion_json")
    for row in shots:
        db.add(Shot(id=row["id"], scene_id=scene_id, **{k: row[k] for k in shot_fields if k in row}))
    take_fields = ("spoken_text_hash", "source", "provider", "model", "voice", "settings_json", "audio_asset_id", "measured_duration_ms", "edit_json", "accepted", "stale")
    for row in takes:
        db.add(VoiceTake(id=row["id"], scene_id=scene_id, **{k: row[k] for k in take_fields if k in row}))
    db.commit(); db.refresh(scene)
    return _out(scene)


@router.post("/{scene_id}/shots", response_model=schemas.ShotOut)
def add_shot(scene_id: str, body: schemas.ShotIn, db: Session = Depends(get_db)):
    from app.db.models import Asset, Shot

    scene = db.get(Scene, scene_id)
    if not scene:
        raise HTTPException(404, "Scene not found")
    asset = db.get(Asset, body.asset_id)
    if not asset:
        raise HTTPException(404, "Asset not found")
    if asset.type not in ("image", "video") or asset.project_id != scene.project_id:
        raise HTTPException(400, "Only images and videos from this project can be added to the picture track.")
    order = body.order_index if body.order_index else len(scene.shots)
    fit = body.fit
    if "fit" not in body.model_fields_set and asset.width and asset.height:
        # Landscape media in a vertical project (or the reverse) keeps the whole picture over a
        # blurred copy instead of being cropped to a thin strip — the CapCut default look.
        project = db.get(Project, scene.project_id)
        media_landscape, project_landscape = asset.width > asset.height * 1.1, project.width > project.height * 1.1
        media_portrait, project_portrait = asset.height > asset.width * 1.1, project.height > project.width * 1.1
        if (media_landscape and project_portrait) or (media_portrait and project_landscape):
            fit = "contain_blur"
    shot = Shot(
        scene_id=scene_id,
        asset_id=body.asset_id,
        order_index=order,
        fit=fit,
        motion_json=body.motion,
        source_in_ms=body.source_in_ms,
        source_out_ms=body.source_out_ms,
        duration_ms=body.duration_ms,
        crop_json=body.crop,
    )
    db.add(shot)
    scene.revision += 1
    db.commit()
    db.refresh(shot)
    return shot


@router.patch("/shots/{shot_id}", response_model=schemas.ShotOut)
def update_shot(shot_id: str, body: dict, db: Session = Depends(get_db)):
    from app.db.models import Shot

    shot = db.get(Shot, shot_id)
    if not shot:
        raise HTTPException(404, "Shot not found")
    if "crop" in body and body["crop"] is not None:
        import math
        crop = body["crop"]
        try:
            x, y, w, h = [float(crop[k]) for k in ("x", "y", "width", "height")]
            if not all(math.isfinite(v) for v in (x,y,w,h)) or min(x,y)<0 or min(w,h)<0.05 or x+w>1.00001 or y+h>1.00001: raise ValueError()
            body["crop"] = dict(x=x,y=y,width=w,height=h)
            if isinstance(shot.crop_json, dict) and shot.crop_json.get("reframe"):  # keep auto-reframe (render/reframe.py)
                body["crop"]["reframe"] = shot.crop_json["reframe"]
        except (KeyError, TypeError, ValueError):
            raise HTTPException(400, "Crop must stay within the image and retain at least 5% of its width and height.")
    for field in ("fit", "source_in_ms", "source_out_ms", "duration_ms", "is_selected", "order_index"):
        if field in body:
            setattr(shot, field, body[field])
    if "audio" in body:
        a = body["audio"]
        if not isinstance(a, dict) or set(a) - {"volume", "mute", "duck", "fade_in_ms", "fade_out_ms"}:
            raise HTTPException(400, "Clip sound settings are volume, mute, ducking, and fade durations.")
        v = a.get("volume", 100)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 200:
            raise HTTPException(400, "Clip volume must be between 0 and 200%.")
        if not isinstance(a.get("mute", False), bool) or not isinstance(a.get("duck", True), bool):
            raise HTTPException(400, "Clip mute and duck must be true or false.")
        fades = {}
        for key in ("fade_in_ms", "fade_out_ms"):
            value = a.get(key, 0)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 10000:
                raise HTTPException(400, "Clip fade durations must be between 0 and 10000 ms.")
            fades[key] = int(round(value))
        shot.audio_json = {"volume": round(float(v), 1), "mute": a.get("mute", False), "duck": a.get("duck", True), **fades}
    if "motion" in body:
        from app.render.filters import EASINGS
        motion = body["motion"]
        if not isinstance(motion, dict) or motion.get("easing", "ease_in_out") not in EASINGS:
            raise HTTPException(400, "Motion easing must be one of: " + ", ".join(EASINGS) + ".")
        shot.motion_json = motion
    if "crop" in body:
        shot.crop_json = body["crop"]
    if "speed" in body:
        from app.render.speed import SpeedError, clean_speed
        try:
            shot.speed_json = clean_speed(body["speed"])
        except SpeedError as e:
            raise HTTPException(400, str(e))
    shot.scene.revision += 1
    db.commit()
    db.refresh(shot)
    return shot


@router.delete("/shots/{shot_id}")
def delete_shot(shot_id: str, db: Session = Depends(get_db)):
    from app.db.models import Shot

    shot = db.get(Shot, shot_id)
    if not shot:
        raise HTTPException(404, "Shot not found")
    scene = shot.scene
    db.delete(shot)
    scene.revision += 1
    db.commit()
    return {"ok": True}


@router.post('/{scene_id}/voice-takes/clear-selection')
def clear_voice_selection(scene_id: str, db: Session = Depends(get_db)):
    scene = db.get(Scene, scene_id)
    if not scene: raise HTTPException(404, 'Scene not found')
    for take in scene.voice_takes: take.accepted = False
    scene.revision += 1
    db.commit()
    return {'ok': True}

@router.post('/{scene_id}/split', response_model=schemas.SceneOut)
def split_scene(scene_id: str, body: dict, db: Session = Depends(get_db)):
    """Split a single source shot in place; use the rendered path for multi-shot or animated scenes."""
    from copy import deepcopy
    from app.db.models import Shot
    scene = db.get(Scene, scene_id)
    if not scene: raise HTTPException(404, 'Scene not found')
    if body.get('baked') is True:
        return _split_rendered(scene, body, db)
    if len(scene.shots) != 1 or any(t.accepted for t in scene.voice_takes):
        raise HTTPException(400, 'This scene has multiple shots or a separate narration track. Render it before splitting so its audio and picture stay in sync.')
    shot = scene.shots[0]
    speed = float((shot.speed_json or {}).get('speed', 1) or 1)
    if (shot.motion_json or {}).get('type', 'static') != 'static' or abs(speed - 1) > 0.001 or (shot.speed_json or {}).get('freeze_at_ms') is not None:
        raise HTTPException(400, 'Render this animated or speed-adjusted scene before splitting.')
    from app.render.media import media_duration_ms
    if scene.timing_mode == 'fixed' and scene.requested_duration_ms:
        total = scene.requested_duration_ms
    else:
        total = media_duration_ms(scene) or scene.measured_duration_ms or scene.requested_duration_ms or 4000
    at = body.get('at_ms')
    frame = max(1, round(1000 / scene.project.fps))
    if isinstance(at, bool) or not isinstance(at, int) or not frame <= at <= total-frame:
        raise HTTPException(400, 'Place the playhead inside the selected scene, at least one frame from either edge.')
    if shot.asset.type == 'video' and (shot.asset.duration_ms or 0) < (shot.source_in_ms or 0)+total:
        raise HTTPException(400, 'Split a video within its source duration; looped videos cannot be split yet.')
    left_font, right_font = _split_scene_font(scene.font_json or {}, at, total)
    left_overlays, right_overlays = _split_scene_overlays(scene.overlays_json or [], at, total)
    for sibling in scene.project.scenes:
        if sibling.order_index > scene.order_index: sibling.order_index += 1
    has_timed_captions = bool((scene.font_json or {}).get('caption_segments'))
    right = Scene(project_id=scene.project_id, order_index=scene.order_index+1, title=scene.title+' · B',
                  original_text=scene.original_text, spoken_text=scene.spoken_text, subtitle_text=_caption_text(right_font, scene.subtitle_text, has_timed_captions),
                  timing_mode='fixed', requested_duration_ms=total-at, lead_ms=0, trail_ms=0,
                  effect_preset=scene.effect_preset, effect_intensity=scene.effect_intensity, font_json=right_font,
                  look_json=deepcopy(scene.look_json or {}), overlays_json=right_overlays,
                  transition_in_json={'type':'cut','duration_ms':0})
    db.add(right);db.flush()
    right_source_in = (shot.source_in_ms or 0)+(at if shot.asset.type=='video' else 0)
    right_source_out = shot.source_out_ms
    db.add(Shot(scene_id=right.id,asset_id=shot.asset_id,order_index=0,fit=shot.fit,motion_json=deepcopy(shot.motion_json),crop_json=deepcopy(shot.crop_json),audio_json=deepcopy(shot.audio_json or {}),speed_json=deepcopy(shot.speed_json or {}),source_in_ms=right_source_in,source_out_ms=right_source_out,duration_ms=total-at))
    if shot.asset.type == 'video':
        original_out = shot.source_out_ms or shot.asset.duration_ms or (shot.source_in_ms or 0)+at
        shot.source_out_ms = min(original_out, (shot.source_in_ms or 0)+at)
    shot.duration_ms=at
    scene.timing_mode='fixed';scene.requested_duration_ms=at;scene.font_json=left_font
    scene.subtitle_text=_caption_text(left_font, scene.subtitle_text, has_timed_captions);scene.overlays_json=left_overlays
    scene.rendered_asset_id=None;scene.rendered_plan_hash=None;scene.measured_duration_ms=None;scene.revision+=1
    db.commit();db.refresh(right)
    return _out(right)


def _caption_text(font: dict, fallback: str, has_timed_captions: bool = False) -> str:
    rows = font.get('caption_segments') or []
    return ' '.join(str(row.get('text') or '').strip() for row in rows if str(row.get('text') or '').strip()) if has_timed_captions else fallback


def _slice_timed_rows(rows: list, at_ms: int, total_ms: int, *, scene_end_is_zero: bool = False) -> tuple[list, list]:
    left, right = [], []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        row = deepcopy(raw)
        try:
            start = max(0, int(row.get('start_ms') or 0))
            raw_end = row.get('end_ms')
            end = total_ms if raw_end is None or (scene_end_is_zero and raw_end == 0) else int(raw_end)
        except (TypeError, ValueError):
            continue
        end = max(start, min(total_ms, end))
        if start < at_ms and min(end, at_ms) > start:
            part = deepcopy(row);part['start_ms']=start;part['end_ms']=min(end, at_ms);left.append(part)
        if end > at_ms and max(start, at_ms) < end:
            part = deepcopy(row);part['start_ms']=max(start, at_ms)-at_ms
            part['end_ms']=(0 if scene_end_is_zero and (raw_end is None or raw_end == 0 or end == total_ms) else end-at_ms)
            right.append(part)
    return left, right


def _split_scene_font(raw: dict, at_ms: int, total_ms: int) -> tuple[dict, dict]:
    original = deepcopy(raw or {})
    left, right = deepcopy(original), deepcopy(original)
    segments = original.get('caption_segments') or []
    if segments:
        left_rows, right_rows = _slice_timed_rows(segments, at_ms, total_ms)
        left['caption_segments'], right['caption_segments'] = left_rows, right_rows
        for font, rows in ((left, left_rows), (right, right_rows)):
            transcript = deepcopy(font.get('transcript') or {})
            words = transcript.get('words')
            if isinstance(words, list):
                if font is left:
                    clipped = []
                    for word in words:
                        if not isinstance(word, (list, tuple)) or len(word) < 3 or int(word[1]) >= at_ms:
                            continue
                        sliced = list(deepcopy(word));sliced[2] = min(at_ms, int(sliced[2]));clipped.append(sliced)
                    transcript['words'] = clipped
                else:
                    sliced = []
                    for word in words:
                        if not isinstance(word, (list, tuple)) or len(word) < 3 or int(word[2]) <= at_ms:
                            continue
                        sliced.append([word[0], max(0, int(word[1])-at_ms), max(0, int(word[2])-at_ms)])
                    transcript['words'] = sliced
            font['transcript'] = transcript
    layers = original.get('layers') or []
    if layers:
        left['layers'], right['layers'] = _slice_timed_rows(layers, at_ms, total_ms, scene_end_is_zero=True)
    return left, right


def _split_scene_overlays(raw: list, at_ms: int, total_ms: int) -> tuple[list, list]:
    return _slice_timed_rows(raw if isinstance(raw, list) else [], at_ms, total_ms, scene_end_is_zero=True)


def _split_rendered(scene, body, db):
    """Cut a current rendered scene; baked visuals and extracted audio preserve timing."""
    from pathlib import Path
    import uuid
    from app.db.models import Asset, Shot, VoiceTake
    from app.config import RENDERS_DIR
    from app.render.renderer import _resolve_asset_path, _register_output_asset
    from app.render.ffmpeg_utils import run_ffmpeg, probe
    if not scene.rendered_asset_id or is_stale(scene, (scene.project.width, scene.project.height), scene.project.fps):
        raise HTTPException(409, 'Render this scene first so the cut includes the latest motion, text and sound.')
    rendered = db.get(Asset, scene.rendered_asset_id)
    if not rendered or rendered.project_id != scene.project_id:
        raise HTTPException(409, 'Rendered scene is unavailable. Render again before splitting.')
    source = _resolve_asset_path(rendered)
    info = probe(source)
    total = info.duration_ms or 0
    at = body.get('at_ms')
    frame = max(1, round(1000/scene.project.fps))
    if isinstance(at,bool) or not isinstance(at,int) or not frame <= at <= total-frame:
        raise HTTPException(400, 'Cut must be at least one frame from either end of the rendered scene.')
    # Produce audio before mutating scene rows. Original assets remain intact.
    paths=[]; audio_assets=[]
    try:
        if info.has_audio:
            for offset,duration in ((0,at),(at,total-at)):
                path=RENDERS_DIR / f'split_audio_{uuid.uuid4().hex}.wav';paths.append(path)
                run_ffmpeg(['-ss',f'{offset/1000:.6f}','-i',source,'-t',f'{duration/1000:.6f}','-vn','-ar','48000','-ac','2','-c:a','pcm_s16le',str(path)])
                asset=_register_output_asset(scene.project_id,str(path),'audio');db.add(asset);audio_assets.append(asset)
        for sibling in scene.project.scenes:
            if sibling.order_index>scene.order_index:sibling.order_index+=1
        right=Scene(project_id=scene.project_id,order_index=scene.order_index+1,title=scene.title+' · B',timing_mode='fixed',requested_duration_ms=total-at,lead_ms=0,trail_ms=0,effect_preset='original',font_json={'captions_enabled':False,'typewriter':False,'layers':[]},transition_in_json={'type':'cut','duration_ms':0})
        db.add(right);db.flush()
        for shot in list(scene.shots):db.delete(shot)
        for take in scene.voice_takes:take.accepted=False
        scene.subtitle_text='';scene.font_json={'captions_enabled':False,'typewriter':False,'layers':[]}
        scene.effect_preset='original';scene.effect_intensity=100;scene.look_json={};scene.overlays_json=[];scene.lead_ms=0;scene.trail_ms=0
        scene.timing_mode='fixed';scene.requested_duration_ms=at;scene.revision+=1
        scene.rendered_asset_id=None;scene.rendered_plan_hash=None;scene.measured_duration_ms=None
        for i,(target,offset,duration) in enumerate(((scene,0,at),(right,at,total-at))):
            db.add(Shot(scene_id=target.id,asset_id=rendered.id,order_index=0,fit='contain',motion_json={'type':'static'},source_in_ms=offset,duration_ms=duration))
            if audio_assets:
                db.add(VoiceTake(scene_id=target.id,source='upload',voice='Rendered scene audio',spoken_text_hash='',audio_asset_id=audio_assets[i].id,measured_duration_ms=duration,accepted=True))
        db.commit();db.refresh(right)
        return _out(right)
    except Exception:
        db.rollback()
        for path in paths:path.unlink(missing_ok=True)
        raise


# Entrance animations available for captions (titles have more: slides, typewriter, …).
CAPTION_ANIMATIONS = ("none", "fade", "zoom", "blur", "glitch", "bounce", "wobble", "neon", "letters-pop", "letters-fade",
                      "letters-flip", "letters-blur", "words-pop", "words-fade", "words-flip", "shine")


_CAPTION_CHOICES = {"case": ("none", "upper", "lower", "title"), "position": ("bottom", "middle", "top"),
                    "halign": ("left", "center", "right"), "background": ("none", "box"),
                    "exit_animation": ("none", "fade", "pop"), "loop": ("none", "pulse"), "split": ("full", "phrases"),
                    "karaoke_style": ("fill", "pop", "glow", "box", "color", "underline")}
_CAPTION_RANGES = {"spacing": (-5, 40), "shadow": (0, 10), "shadow_opacity": (0, 100), "box_opacity": (0, 100),
                   "box_padding": (0, 40), "offset_y": (-40, 40), "max_width": (30, 100), "exit_ms": (50, 5000),
                   "phrase_words": (1, 8), "outline_width": (0, 12)}
_CAPTION_COLORS = ("shadow_color", "box_color", "outline_color", "highlight_color", "color")


def _validate_caption_style(font: dict) -> None:
    """Caption style settings (Captions Pro): clear 400 errors for bad values."""
    import re as _re
    for key in ("bold", "italic", "underline"):
        if key in font and not isinstance(font[key], bool):
            raise HTTPException(400, f"Caption {key} must be true or false.")
    for key, options in _CAPTION_CHOICES.items():
        if key in font and font[key] not in options:
            raise HTTPException(400, f"Caption {key} must be one of: " + ", ".join(options) + ".")
    for key, (lo, hi) in _CAPTION_RANGES.items():
        if key in font:
            v = font[key]
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi:
                raise HTTPException(400, f"Caption {key} must be between {lo} and {hi}.")
    for key in _CAPTION_COLORS:
        if key in font and (not isinstance(font[key], str) or not _re.fullmatch(r"#[0-9A-Fa-f]{6}", font[key])):
            raise HTTPException(400, f"Caption {key} must look like #RRGGBB.")


def _validated_look(scene, look: dict, db) -> dict:
    """Merge a partial look update. Each section ("glitch", "adjust", "lut")
    is replaced as a whole when present; null removes it."""
    from copy import deepcopy
    from app.db.models import Asset
    from app.render.filters import ADJUST_RANGES, GLITCH_BLOCKS, clean_adjust
    from app.render.scene_fx import CLEANERS, SceneFxError
    allowed = {"glitch", "adjust", "lut", "film", *CLEANERS}
    if not isinstance(look, dict) or set(look) - allowed:
        raise HTTPException(400, "Look settings may only contain: " + ", ".join(sorted(allowed)) + ".")
    merged = deepcopy(scene.look_json or {})
    if "glitch" in look:
        g = look["glitch"]
        if g is None:
            merged.pop("glitch", None)
        else:
            if not isinstance(g, dict):
                raise HTTPException(400, "Glitch settings must be an object.")
            speed = g.get("speed", 1.0)
            if isinstance(speed, bool) or not isinstance(speed, (int, float)) or not 0.25 <= speed <= 4:
                raise HTTPException(400, "Glitch speed must be between 0.25 and 4.")
            block = g.get("block", "medium")
            if block not in GLITCH_BLOCKS:
                raise HTTPException(400, f"Glitch block size must be one of: {', '.join(GLITCH_BLOCKS)}.")
            merged["glitch"] = {"speed": round(float(speed), 2), "block": block}
    if "adjust" in look:
        a = look["adjust"]
        if a is None:
            merged.pop("adjust", None)
        else:
            if not isinstance(a, dict):
                raise HTTPException(400, "Adjustments must be an object.")
            unknown = set(a) - set(ADJUST_RANGES)
            if unknown:
                raise HTTPException(400, f"Unknown adjustment: {', '.join(sorted(unknown))}.")
            for key, value in a.items():
                lo, hi = ADJUST_RANGES[key]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not lo <= value <= hi:
                    raise HTTPException(400, f"{key} must be between {lo} and {hi}.")
            cleaned = clean_adjust(a)
            if cleaned:
                merged["adjust"] = cleaned
            else:
                merged.pop("adjust", None)
    for key, clean in CLEANERS.items():
        if key in look:
            if look[key] is None or look[key] == []:
                merged.pop(key, None)
            else:
                try:
                    merged[key] = clean(look[key])
                except SceneFxError as e:
                    raise HTTPException(400, str(e))
    if "film" in look:
        from app.render.filters import FILM_AMOUNTS, FILM_FPS, FILM_TONES, FILM_DEFAULTS
        f = look["film"]
        if f is None:
            merged.pop("film", None)
        else:
            if not isinstance(f, dict) or set(f) - set(FILM_DEFAULTS):
                raise HTTPException(400, "Old film settings may only contain: " + ", ".join(FILM_DEFAULTS) + ".")
            for key in FILM_AMOUNTS:
                v = f.get(key, FILM_DEFAULTS[key])
                if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 100:
                    raise HTTPException(400, f"Old film {key} must be between 0 and 100.")
            if f.get("fps", FILM_DEFAULTS["fps"]) not in FILM_FPS:
                raise HTTPException(400, "Old film frame rate must be 16, 18, 24, or 0 to keep the project rate.")
            if f.get("tone", FILM_DEFAULTS["tone"]) not in FILM_TONES:
                raise HTTPException(400, "Old film tone must be one of: " + ", ".join(FILM_TONES) + ".")
            merged["film"] = {**FILM_DEFAULTS, **{k: (int(v) if k != "tone" else v) for k, v in f.items()}}
    if "lut" in look:
        l = look["lut"]
        if l is None:
            merged.pop("lut", None)
        else:
            if not isinstance(l, dict):
                raise HTTPException(400, "LUT settings must be an object.")
            asset = db.get(Asset, l.get("asset_id"))
            if not asset or asset.type != "lut" or asset.project_id != scene.project_id:
                raise HTTPException(400, "Choose a LUT imported into this project.")
            strength = l.get("strength", 100)
            if isinstance(strength, bool) or not isinstance(strength, (int, float)) or not 0 <= strength <= 100:
                raise HTTPException(400, "LUT strength must be between 0 and 100.")
            merged["lut"] = {"asset_id": asset.id, "strength": int(strength)}
    return merged


@router.get("/{scene_id}/graded-frame")
def graded_frame_endpoint(scene_id: str, w: int = 1280, shot_id: str | None = None, db: Session = Depends(get_db)):
    """A still of the scene's media with its colour grade (adjustment
    sliders + LUT) applied exactly as the renderer will, for the editor
    preview. Look presets, glitch, sharpen, vignette and grain are not
    included; the editor previews those separately."""
    from pathlib import Path
    import hashlib
    from fastapi.responses import FileResponse
    from app.config import MEDIA_DIR, PROXIES_DIR, RENDERS_DIR
    from app.db.models import Asset
    from app.render.grade import CubeError, build_grade_lut
    from app.render.thumbnails import ThumbnailError, graded_frame, thumbnail_path
    scene = db.get(Scene, scene_id)
    if not scene:
        raise HTTPException(404, "Scene not found")
    shots = [s for s in scene.shots if s.asset and s.asset.type in ("image", "video")]
    shot = next((s for s in shots if s.id == shot_id), shots[0] if shots else None)
    if not shot:
        raise HTTPException(404, "This scene has no image or video to preview.")
    look = scene.look_json or {}
    lut = look.get("lut") or {}
    lut_path = None
    if lut.get("asset_id"):
        lut_asset = db.get(Asset, lut["asset_id"])
        if not lut_asset or lut_asset.type != "lut":
            raise HTTPException(404, "The LUT chosen for this scene is missing.")
        lut_path = str(Path(MEDIA_DIR) / lut_asset.storage_key)
    try:
        grade = build_grade_lut(look.get("adjust"), lut_path, int(lut.get("strength", 100)), Path(PROXIES_DIR) / "grades", look.get("tone"), look.get("wheels"))
    except CubeError as e:
        raise HTTPException(422, f"The LUT could not be read: {e}")
    asset = shot.asset
    base = Path(RENDERS_DIR if asset.origin == "render_output" else MEDIA_DIR)
    try:
        thumb = thumbnail_path(asset.id, base / asset.storage_key, asset.type, asset.duration_ms, w)
        if not grade:
            return FileResponse(thumb, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})
        key = hashlib.sha256(f"{thumb.name}|{thumb.stat().st_mtime}|{Path(grade).name}".encode()).hexdigest()[:24]
        out = graded_frame(thumb, grade, key)
    except ThumbnailError as e:
        raise HTTPException(422, str(e))
    return FileResponse(out, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})


def _copy_row(row, **overrides):
    """A new ORM object of the same class with every column copied (JSON deep-copied),
    except its id and whatever is overridden. New columns are included automatically."""
    from copy import deepcopy
    cls = type(row)
    values = {}
    for col in cls.__table__.columns:
        if col.key == "id":
            continue
        v = getattr(row, col.key)
        values[col.key] = deepcopy(v) if isinstance(v, (dict, list)) else v
    values.update(overrides)
    return cls(**values)


@router.post("/{scene_id}/duplicate", response_model=schemas.SceneOut)
def duplicate_scene(scene_id: str, db: Session = Depends(get_db)):
    """Exact copy placed right after the original: pictures, effects, looks, captions,
    titles, overlays and audio takes, so the copy can be given different effects."""
    from app.db.models import Shot, VoiceTake
    scene = db.get(Scene, scene_id)
    if not scene:
        raise HTTPException(404, "Scene not found")
    project = db.get(Project, scene.project_id)
    for s in project.scenes:
        if s.order_index > scene.order_index:
            s.order_index += 1
    copy = _copy_row(scene, order_index=scene.order_index + 1, title=(scene.title or "Scene") + " (copy)",
                     rendered_asset_id=None, revision=1)
    db.add(copy); db.flush()
    for shot in scene.shots:
        db.add(_copy_row(shot, scene_id=copy.id))
    for take in scene.voice_takes:
        db.add(_copy_row(take, scene_id=copy.id))
    project.revision += 1
    db.commit(); db.refresh(copy)
    return copy


@router.post("/{scene_id}/paste-audio", response_model=schemas.SceneOut)
def paste_audio(scene_id: str, body: dict, db: Session = Depends(get_db)):
    """Copy an audio take (narration or any audio clip) from another scene of the same
    project into this scene, with its trim, volume and fades, and make it the selected take."""
    from app.db.models import VoiceTake
    scene = db.get(Scene, scene_id)
    take = db.get(VoiceTake, (body or {}).get("take_id"))
    if not scene or not take:
        raise HTTPException(404, "Scene or audio clip not found")
    source = db.get(Scene, take.scene_id)
    if not source or source.project_id != scene.project_id:
        raise HTTPException(400, "Audio can only be pasted within the same project.")
    for t in scene.voice_takes:
        t.accepted = False
    db.add(_copy_row(take, scene_id=scene.id, accepted=True))
    scene.revision += 1
    db.commit(); db.refresh(scene)
    return scene



@router.post("/{scene_id}/auto-captions", response_model=schemas.SceneOut)
def auto_captions(scene_id: str, body: dict | None = None, db: Session = Depends(get_db)):
    """Captions from the speech in this scene: the narration if there is one, otherwise the
    video clips' own sound (cut exactly as they play). Language is detected automatically
    unless given. The words and their times become the captions (editable)."""
    import tempfile
    from pathlib import Path as _P
    from app.config import FFMPEG_BIN, MEDIA_DIR, DEFAULT_LEAD_MS
    from app.providers import transcribe as tr
    from app.render.media import clip_audio, selected_shots, shot_durations, media_duration_ms
    body = body or {}
    scene = db.get(Scene, scene_id)
    if not scene:
        raise HTTPException(404, "Scene not found")
    provider = body.get("provider", "auto")
    language = (body.get("language") or "").strip() or None
    if provider not in ("auto", "local", "elevenlabs", "openai") or (language and len(language) > 8):
        raise HTTPException(400, "Provider must be local, elevenlabs or openai; language a short code like en or ar.")
    take = next((t for t in scene.voice_takes if t.accepted), None)
    work = _P(tempfile.mkdtemp(prefix="sf-stt-"))
    offset = 0
    try:
        if take and take.audio_asset and body.get("source", "auto") != "clips":
            src = _P(MEDIA_DIR) / take.audio_asset.storage_key
            edit = take.edit_json or {}
            wav = work / "speech.wav"
            args = [FFMPEG_BIN, "-y", "-v", "error"]
            if edit.get("in_ms"):
                args += ["-ss", f"{int(edit['in_ms'])/1000:.3f}"]
            args += ["-i", str(src)]
            if edit.get("out_ms"):
                args += ["-t", f"{(int(edit['out_ms'])-int(edit.get('in_ms') or 0))/1000:.3f}"]
            import subprocess
            subprocess.run(args + ["-ac", "1", "-ar", "16000", str(wav)], check=True, capture_output=True, timeout=300)
            offset = DEFAULT_LEAD_MS if scene.lead_ms is None else scene.lead_ms
            source = "narration"
        else:
            shots = selected_shots(scene)
            total = media_duration_ms(scene)
            if not shots or not total:
                raise HTTPException(400, "This scene has no narration or video with sound to transcribe.")
            wav = clip_audio(scene, shots, shot_durations(scene, shots, total), MEDIA_DIR, work, FFMPEG_BIN, has_narration=False, original=True)
            if not wav:
                raise HTTPException(400, "The videos in this scene have no sound to transcribe.")
            source = "clips"
        translate = body.get("translate") or None   # 0.9.0: None | "english" | "bilingual"
        if translate not in (None, "english", "bilingual"):
            raise HTTPException(400, "translate must be english or bilingual.")
        english = None
        try:
            if translate == "english":
                result = tr.transcribe(db, str(wav), "local", None, task="translate")
            else:
                result = tr.transcribe(db, str(wav), provider, language)
                if translate == "bilingual":
                    english = tr.transcribe(db, str(wav), "local", None, task="translate")
        except tr.TranscribeError as e:
            raise HTTPException(400, str(e))
    finally:
        import shutil
        shutil.rmtree(work, ignore_errors=True)
    if not result["words"]:
        raise HTTPException(400, "No speech was recognised in this scene.")
    words = [[w, s + offset, e + offset] for w, s, e in result["words"]]
    try: phrase_words = max(1, min(8, int(body.get('phrase_words', 3))))
    except (TypeError, ValueError, OverflowError): phrase_words = 3
    import uuid
    caption_segments = []
    for index in range(0, len(words), phrase_words):
        chunk = words[index:index + phrase_words]
        caption_segments.append({'id': str(uuid.uuid4()), 'text': ' '.join(row[0] for row in chunk),
                                 'start_ms': max(0, int(chunk[0][1])), 'end_ms': max(int(chunk[0][1]) + 100, int(chunk[-1][2]))})
    if english is not None:
        # Bilingual: each caption gets a second line with the English words spoken in the same time span.
        en_words = [[w, s + offset, e + offset] for w, s, e in english.get("words", [])]
        if english.get("language") == "en" and result.get("language") == "en":
            en_words = []   # already English: nothing to add
        extra: dict[int, list[str]] = {}
        for w, ws, we in en_words:   # every English word goes to the caption nearest its middle
            mid = (ws + we) / 2
            best = min(range(len(caption_segments)), key=lambda i: 0 if caption_segments[i]["start_ms"] <= mid <= caption_segments[i]["end_ms"]
                       else min(abs(mid - caption_segments[i]["start_ms"]), abs(mid - caption_segments[i]["end_ms"])))
            extra.setdefault(best, []).append(w)
        for i, seg in enumerate(caption_segments):
            if extra.get(i):
                seg["text"] = seg["text"] + "\n" + " ".join(extra[i])
    scene.subtitle_text = " ".join(w for w, _, _ in words)
    font = dict(scene.font_json or {})
    font["transcript"] = {"language": result["language"], "provider": result["provider"], "source": source,
                          "word_timing": result.get("word_timing", "provider"), "words": words,
                          **({"translated": translate} if translate else {})}
    font['caption_segments'] = caption_segments
    font["captions_enabled"] = True
    scene.font_json = font
    scene.revision += 1
    db.commit(); db.refresh(scene)
    return scene


_POSITIONAL_LOOK = ("route", "annotations", "layout", "parallax", "redact")   # tied to one picture's layout


@router.post("/{scene_id}/apply-to")
def apply_to_scenes(scene_id: str, body: dict, db: Session = Depends(get_db)):
    """Copy this scene's settings to other scenes (multi-select on the timeline):
    effects = look preset + look settings (except position-specific ones),
    captions = caption style (not the caption text or transcript), titles = text overlays,
    transition = incoming transition."""
    from copy import deepcopy
    src = db.get(Scene, scene_id)
    if not src:
        raise HTTPException(404, "Scene not found")
    targets = (body or {}).get("targets") or []
    parts = set((body or {}).get("parts") or [])
    if not isinstance(targets, list) or not targets or not parts or parts - {"effects", "captions", "titles", "transition"}:
        raise HTTPException(400, "Choose target scenes and what to copy: effects, captions, titles, transition.")
    changed = 0
    for tid in targets:
        t = db.get(Scene, tid)
        if not t or t.id == src.id:
            continue
        if t.project_id != src.project_id:
            raise HTTPException(400, "Scenes must be in the same project.")
        if "effects" in parts:
            t.effect_preset = src.effect_preset
            look = {k: deepcopy(v) for k, v in (src.look_json or {}).items() if k not in _POSITIONAL_LOOK}
            keep = {k: v for k, v in (t.look_json or {}).items() if k in _POSITIONAL_LOOK}
            t.look_json = {**look, **keep}
        if "captions" in parts or "titles" in parts:
            font = dict(t.font_json or {})
            if "captions" in parts:
                style = {k: deepcopy(v) for k, v in (src.font_json or {}).items() if k not in ("layers", "transcript", "caption_segments")}
                font = {**style, **({"layers": font["layers"]} if "layers" in font else {}), **({"transcript": font["transcript"]} if "transcript" in font else {}), **({"caption_segments": font["caption_segments"]} if "caption_segments" in font else {})}
            if "titles" in parts:
                font["layers"] = deepcopy((src.font_json or {}).get("layers", []))
            t.font_json = font
        if "transition" in parts:
            t.transition_in_json = deepcopy(src.transition_in_json)
        t.revision += 1
        changed += 1
    db.commit()
    return {"changed": changed}


@router.post("/{scene_id}/detach-audio")
def detach_audio(scene_id: str, body: dict, db: Session = Depends(get_db)):
    """Copy a scene's narration (A1) or a shot's embedded sound (A2) into a new project
    audio file so it can be placed, cut and deleted on the timeline audio tracks.

    The narration is baked with its trim, voice effect, level and fades, so the new clip
    sounds the same at volume 100. Original media and takes are never modified here;
    the editor mutes/removes the source in the same undoable step.
    """
    import uuid as _uuid
    from app.config import RENDERS_DIR
    from app.db.models import Shot
    from app.render.audio_edit import effective_ms, narration_filter
    from app.render.ffmpeg_utils import run_ffmpeg
    from app.render.renderer import _register_output_asset, _resolve_asset_path
    scene = db.get(Scene, scene_id)
    if not scene:
        raise HTTPException(404, "Scene not found")
    source = (body or {}).get("source")
    out = RENDERS_DIR / f"detached_audio_{_uuid.uuid4().hex}.wav"
    if source == "narration":
        take = next((t for t in scene.voice_takes if t.accepted), None)
        if not take or not take.audio_asset_id:
            raise HTTPException(400, "This scene has no narration to move.")
        from app.db.models import Asset
        asset = db.get(Asset, take.audio_asset_id)
        clip_ms = effective_ms(take.measured_duration_ms, take.edit_json) or asset.duration_ms or 0
        chain = narration_filter(take.edit_json, clip_ms) or "anull"
        run_ffmpeg(["-i", _resolve_asset_path(asset), "-af", chain, "-vn", "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(out)])
        name = f"{scene.title} narration"
        offset = 250 if scene.lead_ms is None else int(scene.lead_ms)
    elif source == "shot":
        shot = db.get(Shot, (body or {}).get("shot_id"))
        if not shot or shot.scene_id != scene.id or not shot.asset or shot.asset.type != "video":
            raise HTTPException(400, "Choose a video clip in this scene.")
        speed = float((shot.speed_json or {}).get("speed", 1) or 1)
        if abs(speed - 1) > 0.001 or (shot.speed_json or {}).get("ramp", "none") not in (None, "none") or (shot.speed_json or {}).get("freeze_at_ms") is not None:
            raise HTTPException(400, "Detaching sound from a speed-changed clip is not supported yet. Reset its speed first, or render the scene and use its audio.")
        duration = body.get("duration_ms")
        if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not 100 <= duration <= 86_400_000:
            raise HTTPException(400, "duration_ms must be between 100 ms and 24 hours.")
        start = int(shot.source_in_ms or 0)
        end = min(int(shot.source_out_ms or shot.asset.duration_ms or start + duration), start + int(duration))
        if end - start < 100:
            raise HTTPException(400, "The clip is too short to detach its sound.")
        try:
            run_ffmpeg(["-ss", f"{start/1000:.6f}", "-i", _resolve_asset_path(shot.asset), "-t", f"{(end-start)/1000:.6f}", "-vn",
                        "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(out)])
        except Exception:
            raise HTTPException(400, "This video clip has no sound to detach.")
        name = f"{shot.asset.original_filename or scene.title} sound"
        offset = 0
    else:
        raise HTTPException(400, "source must be narration or shot.")
    if not out.exists() or out.stat().st_size < 1000:
        out.unlink(missing_ok=True)
        raise HTTPException(400, "No sound was found to detach.")
    asset = _register_output_asset(scene.project_id, str(out), "audio")
    asset.original_filename = f"{name[:180]}.wav"
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return {"asset": schemas.AssetOut.model_validate(asset).model_dump(mode="json"), "offset_ms": offset}
