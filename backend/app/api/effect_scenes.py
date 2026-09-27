"""Insert ready-made effect scenes (cinema countdown leaders) anywhere in a project."""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import FFMPEG_BIN, MEDIA_DIR
from app.db.database import get_db
from app.db.models import Asset, Project, Scene, Shot, VoiceTake
from app.domain import schemas
from app.domain.constants import AssetOrigin, AssetType, VoiceTakeSource
from app.render import countdowns

router = APIRouter(prefix="/api/projects", tags=["effect scenes"])


@router.post("/{project_id}/insert-countdown", response_model=schemas.SceneOut)
def insert_countdown(project_id: str, body: dict, db: Session = Depends(get_db)):
    """Render a countdown leader at the project's size and insert it as a scene: the video
    is the scene's picture and its sound becomes the scene's audio clip (Narration lane), so it
    can be trimmed, moved, duplicated, given effects and have its volume changed."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    try:
        opts = countdowns.clean({k: v for k, v in (body or {}).items() if k != "after_scene_id"})
        src = countdowns.render(opts, project.width, project.height, project.fps)
    except countdowns.CountdownError as e:
        raise HTTPException(400, str(e))
    folder = Path(MEDIA_DIR) / project_id
    folder.mkdir(parents=True, exist_ok=True)
    tag = uuid.uuid4().hex[:10]
    video = folder / f"countdown_{opts['style']}_{tag}.mp4"
    audio = folder / f"countdown_{opts['style']}_{tag}.wav"
    shutil.copyfile(src, video)
    subprocess.run([FFMPEG_BIN, "-y", "-v", "error", "-i", str(video), "-vn", "-ar", "48000", "-ac", "2", str(audio)],
                   check=True, capture_output=True, timeout=120)
    ms = opts["seconds"] * 1000
    label = {"film": "Film leader", "modern": "Modern countdown", "minimal": "Minimal countdown"}[opts["style"]]
    v_asset = Asset(project_id=project_id, type=AssetType.VIDEO, content_hash=hashlib.sha256(video.read_bytes()).hexdigest(),
                    storage_key=str(video.relative_to(MEDIA_DIR)), mime="video/mp4", original_filename=f"{label}.mp4",
                    width=project.width, height=project.height, duration_ms=ms, origin=AssetOrigin.GENERATED)
    a_asset = Asset(project_id=project_id, type=AssetType.AUDIO, content_hash=hashlib.sha256(audio.read_bytes()).hexdigest(),
                    storage_key=str(audio.relative_to(MEDIA_DIR)), mime="audio/wav", original_filename=f"{label} sound.wav",
                    duration_ms=ms, origin=AssetOrigin.GENERATED)
    db.add_all([v_asset, a_asset]); db.flush()
    after = db.get(Scene, (body or {}).get("after_scene_id")) if (body or {}).get("after_scene_id") else None
    if after and after.project_id != project_id:
        raise HTTPException(400, "That scene belongs to another project.")
    position = (after.order_index + 1) if after else 0          # default: at the very start
    for s in project.scenes:
        if s.order_index >= position:
            s.order_index += 1
    scene = Scene(project_id=project_id, order_index=position, title=label, timing_mode="fixed", requested_duration_ms=ms)
    db.add(scene); db.flush()
    db.add(Shot(scene_id=scene.id, asset_id=v_asset.id, order_index=0, fit="cover", duration_ms=ms, is_selected=True))
    db.add(VoiceTake(scene_id=scene.id, spoken_text_hash="", source=VoiceTakeSource.UPLOAD, provider="sceneforge-countdown",
                     voice=opts["style"], settings_json={"countdown": opts}, audio_asset_id=a_asset.id,
                     measured_duration_ms=ms, accepted=True))
    project.revision += 1
    db.commit(); db.refresh(scene)
    return scene
