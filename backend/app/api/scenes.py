from __future__ import annotations

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
        if 'layers' in body.font:
            from pydantic import ValidationError
            try:
                layers = body.font['layers']
                if not isinstance(layers, list) or len(layers) > 12: raise ValueError()
                body.font['layers'] = [schemas.TextLayer.model_validate(layer).model_dump() for layer in layers]
                if any(l['end_ms'] and l['end_ms'] <= l['start_ms'] for l in body.font['layers']): raise ValueError()
            except (ValidationError, ValueError, TypeError):
                raise HTTPException(400, 'Text layers need valid positions, colors, sizes and end times after start times (maximum 12 layers).')
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
    shot = Shot(
        scene_id=scene_id,
        asset_id=body.asset_id,
        order_index=order,
        fit=body.fit,
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
        except (KeyError, TypeError, ValueError):
            raise HTTPException(400, "Crop must stay within the image and retain at least 5% of its width and height.")
    for field in ("fit", "source_in_ms", "source_out_ms", "duration_ms", "is_selected", "order_index"):
        if field in body:
            setattr(shot, field, body[field])
    if "motion" in body:
        from app.render.filters import EASINGS
        motion = body["motion"]
        if not isinstance(motion, dict) or motion.get("easing", "ease_in_out") not in EASINGS:
            raise HTTPException(400, "Motion easing must be one of: " + ", ".join(EASINGS) + ".")
        shot.motion_json = motion
    if "crop" in body:
        shot.crop_json = body["crop"]
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
    """Split a single static visual. Complex scenes require a rendered editor pipeline."""
    from copy import deepcopy
    from app.db.models import Shot
    scene = db.get(Scene, scene_id)
    if not scene: raise HTTPException(404, 'Scene not found')
    if body.get('baked') is True:
        return _split_rendered(scene, body, db)
    if len(scene.shots) != 1 or any(t.accepted for t in scene.voice_takes) or scene.subtitle_text or scene.font_json.get('layers') or scene.shots[0].motion_json.get('type', 'static') != 'static':
        raise HTTPException(400, 'Split currently supports a single static image/video without narration or text. Split before adding those elements.')
    total = scene.requested_duration_ms or scene.measured_duration_ms or 4000
    at = body.get('at_ms')
    frame = max(1, round(1000 / scene.project.fps))
    if isinstance(at, bool) or not isinstance(at, int) or not frame <= at <= total-frame:
        raise HTTPException(400, 'Place the playhead inside the selected scene, at least one frame from either edge.')
    shot = scene.shots[0]
    if shot.asset.type == 'video' and (shot.asset.duration_ms or 0) < (shot.source_in_ms or 0)+total:
        raise HTTPException(400, 'Split a video within its source duration; looped videos cannot be split yet.')
    for sibling in scene.project.scenes:
        if sibling.order_index > scene.order_index: sibling.order_index += 1
    right = Scene(project_id=scene.project_id, order_index=scene.order_index+1, title=scene.title+' · B', timing_mode='fixed', requested_duration_ms=total-at,
                  effect_preset=scene.effect_preset, effect_intensity=scene.effect_intensity, font_json=deepcopy(scene.font_json), look_json=deepcopy(scene.look_json or {}), overlays_json=deepcopy(scene.overlays_json or []), transition_in_json={'type':'cut','duration_ms':0})
    db.add(right);db.flush()
    db.add(Shot(scene_id=right.id,asset_id=shot.asset_id,order_index=0,fit=shot.fit,motion_json=deepcopy(shot.motion_json),crop_json=deepcopy(shot.crop_json),source_in_ms=(shot.source_in_ms or 0)+(at if shot.asset.type=='video' else 0),duration_ms=total-at))
    scene.timing_mode='fixed';scene.requested_duration_ms=at;shot.duration_ms=at;scene.revision+=1
    db.commit();db.refresh(right)
    return _out(right)


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


def _validated_look(scene, look: dict, db) -> dict:
    """Merge a partial look update. Each section ("glitch", "adjust", "lut")
    is replaced as a whole when present; null removes it."""
    from copy import deepcopy
    from app.db.models import Asset
    from app.render.filters import ADJUST_RANGES, GLITCH_BLOCKS, clean_adjust
    if not isinstance(look, dict) or set(look) - {"glitch", "adjust", "lut", "film"}:
        raise HTTPException(400, "Look settings may only contain glitch, adjust, lut and film.")
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
        grade = build_grade_lut(look.get("adjust"), lut_path, int(lut.get("strength", 100)), Path(PROXIES_DIR) / "grades")
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
