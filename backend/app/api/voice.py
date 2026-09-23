from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import MEDIA_DIR
from app.db.database import get_db
from app.db.models import Asset, Scene, VoiceTake
from app.domain import schemas
from app.domain.constants import AssetOrigin, AssetType, VoiceTakeSource
from app.providers import local_offline_tts
from app.render.ffmpeg_utils import FFmpegError, probe
from app.security.uploads import UploadValidationError, classify_extension, safe_generated_filename

router = APIRouter(tags=["voice"])


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@router.post("/api/scenes/{scene_id}/voice-preview")
def voice_preview(scene_id: str, body: dict, db: Session = Depends(get_db)):
    """Short, non-persisted audition — does not create a VoiceTake or
    accepted asset; just synthesizes to a temp file the client can play."""
    scene = db.get(Scene, scene_id)
    if not scene:
        raise HTTPException(404, "Scene not found")
    text = body.get("text") or scene.spoken_text
    if not text.strip():
        raise HTTPException(400, "No text to audition.")
    voice = body.get("voice", "ar")
    project_dir = Path(MEDIA_DIR) / scene.project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    out_path = project_dir / f"preview_{uuid.uuid4().hex}.wav"
    try:
        local_offline_tts.synthesize(text, str(out_path), voice=voice)
    except FFmpegError as e:
        raise HTTPException(500, str(e))
    info = probe(str(out_path))
    asset = Asset(
        project_id=scene.project_id, type=AssetType.AUDIO,
        content_hash=hashlib.sha256(out_path.read_bytes()).hexdigest(),
        storage_key=str(out_path.relative_to(MEDIA_DIR)), mime="audio/wav",
        original_filename=out_path.name, duration_ms=info.duration_ms,
        origin=AssetOrigin.LOCAL_TTS,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return {"asset": schemas.AssetOut.model_validate(asset).model_dump(), "stream_url": f"/api/assets/{asset.id}/stream"}


@router.post("/api/scenes/{scene_id}/voice-takes/local-tts", response_model=schemas.VoiceTakeOut)
def create_local_tts_take(scene_id: str, body: schemas.VoiceTakeCreate, db: Session = Depends(get_db)):
    scene = db.get(Scene, scene_id)
    if not scene:
        raise HTTPException(404, "Scene not found")
    if not scene.spoken_text.strip():
        raise HTTPException(400, "Scene has no spoken_text to synthesize. Edit the script first.")

    project_dir = Path(MEDIA_DIR) / scene.project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    out_path = project_dir / f"narration_{uuid.uuid4().hex}.wav"
    try:
        local_offline_tts.synthesize(
            scene.spoken_text, str(out_path), voice=body.voice or "ar", rate_wpm=body.rate_wpm or 160
        )
    except FFmpegError as e:
        raise HTTPException(500, str(e))
    info = probe(str(out_path))

    asset = Asset(
        project_id=scene.project_id, type=AssetType.AUDIO,
        content_hash=hashlib.sha256(out_path.read_bytes()).hexdigest(),
        storage_key=str(out_path.relative_to(MEDIA_DIR)), mime="audio/wav",
        original_filename=out_path.name, duration_ms=info.duration_ms,
        origin=AssetOrigin.LOCAL_TTS,
    )
    db.add(asset)
    db.flush()
    take = VoiceTake(
        scene_id=scene_id,
        spoken_text_hash=_text_hash(scene.spoken_text),
        source=VoiceTakeSource.LOCAL_OFFLINE_TTS,
        provider="local-espeak-ng",
        voice=body.voice or "ar",
        settings_json={"rate_wpm": body.rate_wpm or 160},
        audio_asset_id=asset.id,
        measured_duration_ms=info.duration_ms,
        accepted=True,
    )
    # A freshly generated take is the one the user almost always wants
    # used immediately — requiring a separate "Use this take" click
    # before Generate produced a confusingly silent (but technically
    # valid, muted) render for anyone who skipped that step. Auto-accept
    # the new take and mark any previous one on this scene as no longer
    # accepted; a user can still switch takes explicitly afterward.
    for t in scene.voice_takes:
        t.accepted = False
    db.add(take)
    db.commit()
    db.refresh(take)
    return take


@router.post("/api/scenes/{scene_id}/voice-takes/upload", response_model=schemas.VoiceTakeOut)
async def upload_voice_take(scene_id: str, file: UploadFile, db: Session = Depends(get_db)):
    scene = db.get(Scene, scene_id)
    if not scene:
        raise HTTPException(404, "Scene not found")
    try:
        asset_type = classify_extension(file.filename or "")
    except UploadValidationError as e:
        raise HTTPException(400, str(e))
    if asset_type != AssetType.AUDIO:
        raise HTTPException(400, "Expected an audio file for a voice take.")

    project_dir = Path(MEDIA_DIR) / scene.project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    dest_path = project_dir / safe_generated_filename(file.filename or "narration.wav")
    hasher = hashlib.sha256()
    with open(dest_path, "wb") as out:
        while True:
            chunk = await file.read(1 << 20)
            if not chunk:
                break
            hasher.update(chunk)
            out.write(chunk)

    try:
        info = probe(str(dest_path))
    except FFmpegError as e:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(400, f"Could not decode uploaded audio: {e.stderr[:300]}")
    if not info.has_audio:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(400, "Uploaded file has no decodable audio stream.")

    asset = Asset(
        project_id=scene.project_id, type=AssetType.AUDIO, content_hash=hasher.hexdigest(),
        storage_key=str(dest_path.relative_to(MEDIA_DIR)), mime=file.content_type or "audio/wav",
        original_filename=file.filename or dest_path.name, duration_ms=info.duration_ms,
        origin=AssetOrigin.UPLOAD,
    )
    db.add(asset)
    db.flush()
    take = VoiceTake(
        scene_id=scene_id,
        spoken_text_hash=_text_hash(scene.spoken_text),
        source=VoiceTakeSource.UPLOAD,
        audio_asset_id=asset.id,
        measured_duration_ms=info.duration_ms,
        accepted=True,
    )
    for t in scene.voice_takes:
        t.accepted = False
    db.add(take)
    db.commit()
    db.refresh(take)
    return take


@router.post("/api/voice-takes/{take_id}/select", response_model=schemas.VoiceTakeOut)
def select_take(take_id: str, db: Session = Depends(get_db)):
    take = db.get(VoiceTake, take_id)
    if not take:
        raise HTTPException(404, "Voice take not found")
    for t in take.scene.voice_takes:
        t.accepted = t.id == take_id
    db.commit()
    db.refresh(take)
    return take


class SpeechRequest(schemas.BaseModel):
    provider_id: str
    voice: str = 'af_heart'
    language: str = 'en'
    speed: float = schemas.Field(default=0.9, ge=0.5, le=2.0)
    audition: bool = False


@router.post('/api/scenes/{scene_id}/voice-takes/service')
def create_service_take(scene_id: str, body: SpeechRequest, db: Session = Depends(get_db)):
    from app.db.models import ProviderProfile
    from app.providers.speech_http import synthesize
    scene = db.get(Scene, scene_id)
    if not scene: raise HTTPException(404, 'Scene not found')
    profile = db.get(ProviderProfile, body.provider_id)
    if not profile or profile.capability != 'speech': raise HTTPException(400, 'Select a configured speech provider.')
    if not scene.spoken_text.strip(): raise HTTPException(400, 'Write narration first.')
    text = scene.spoken_text[:250] if body.audition else scene.spoken_text
    if len(text) > 10000: raise HTTPException(400, 'Split narration longer than 10,000 characters into scenes.')
    try: audio = synthesize(profile, text, body.voice, body.language, body.speed)
    except ValueError as exc: raise HTTPException(502, str(exc))
    folder = Path(MEDIA_DIR) / scene.project_id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f'narration_{uuid.uuid4().hex}.wav'
    path.write_bytes(audio)
    try:
        info = probe(str(path))
        if not info.has_audio or not info.duration_ms: raise ValueError('No audio stream')
    except (FFmpegError, ValueError):
        path.unlink(missing_ok=True)
        raise HTTPException(502, 'Voice service returned invalid audio.')
    asset = Asset(project_id=scene.project_id, type=AssetType.AUDIO, content_hash=hashlib.sha256(audio).hexdigest(),
        storage_key=str(path.relative_to(MEDIA_DIR)), mime='audio/wav', original_filename=path.name,
        duration_ms=info.duration_ms, origin=AssetOrigin.LOCAL_TTS, creator=profile.name)
    db.add(asset); db.flush()
    if body.audition:
        db.commit(); db.refresh(asset)
        return {'asset': schemas.AssetOut.model_validate(asset).model_dump()}
    for take in scene.voice_takes: take.accepted = False
    take = VoiceTake(scene_id=scene.id, spoken_text_hash=_text_hash(scene.spoken_text), source=VoiceTakeSource.CLOUD_TTS,
        provider=profile.name, voice=body.voice, settings_json={'language':body.language, 'speed':body.speed},
        audio_asset_id=asset.id, measured_duration_ms=info.duration_ms, accepted=True)
    db.add(take); scene.revision += 1; db.commit(); db.refresh(take)
    return schemas.VoiceTakeOut.model_validate(take)

@router.post('/api/scenes/{scene_id}/voice-takes/from-asset',response_model=schemas.VoiceTakeOut)
def voice_from_asset(scene_id:str,body:dict,db:Session=Depends(get_db)):
    scene=db.get(Scene,scene_id)
    if not scene:raise HTTPException(404,'Scene not found')
    asset=db.get(Asset,body.get('asset_id'))
    if not asset or asset.project_id!=scene.project_id or asset.type!='audio':
        raise HTTPException(400,'Select an audio file from this project.')
    for take in scene.voice_takes:take.accepted=False
    take=VoiceTake(scene_id=scene_id,source='upload',audio_asset_id=asset.id,spoken_text_hash=_text_hash(scene.spoken_text),measured_duration_ms=asset.duration_ms,accepted=True)
    db.add(take);scene.revision+=1;db.commit();db.refresh(take);return take

@router.delete('/api/voice-takes/{take_id}')
def delete_voice_take(take_id: str, db: Session = Depends(get_db)):
    from app.db.models import RenderJob
    take = db.get(VoiceTake, take_id)
    if not take: raise HTTPException(404, 'Voice take not found')
    scene = take.scene
    active = db.query(RenderJob).filter(RenderJob.project_id == scene.project_id, RenderJob.status.in_(['queued','running'])).first()
    if active: raise HTTPException(409, 'Wait for the project render to finish before deleting audio.')
    if take.accepted:
        scene.revision += 1
        scene.rendered_asset_id = None
        scene.rendered_plan_hash = None
        scene.measured_duration_ms = None
    # Retain the asset: it may also be used by another scene or the media pool.
    db.delete(take)
    db.commit()
    return {'deleted': True}
