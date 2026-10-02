"""Typewriter sound preview (0.9.0).

  GET /api/scenes/{scene_id}/typewriter-preview   a short WAV of keystrokes with the scene's
                                                  sound (included or uploaded), speed and volume

Lets the Typewriter box play its sound without rendering the scene. It uses the same keystroke
extraction and schedule code as the renderer, so what you hear is what the render uses.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import FFMPEG_BIN
from app.db.database import get_db
from app.db.models import Asset, Scene
from app.domain.constants import AssetType
from app.render.typewriter import DEFAULT_KEY, extract_keystroke, reveal_schedule, write_typing_audio

router = APIRouter(tags=["typewriter"])
SAMPLE = "Typing preview"


def _cleanup(folder: str) -> None:
    import shutil
    shutil.rmtree(folder, ignore_errors=True)


@router.get("/api/scenes/{scene_id}/typewriter-preview")
def typewriter_preview(scene_id: str, background: BackgroundTasks, db: Session = Depends(get_db)):
    scene = db.get(Scene, scene_id)
    if not scene:
        raise HTTPException(404, "Scene not found")
    font = dict(scene.font_json or {})
    text = (scene.subtitle_text or "").strip() or SAMPLE
    # Preview the first few words at the chosen typing speed (per character), capped at 4 s.
    clusters = max(2, len(text))
    per_char = (int(font.get("typewriter_duration_ms") or (clusters - 1) * 160)) / max(1, clusters - 1)
    words = text[:24]
    span = int(min(3500, max(300, per_char * max(1, len(words) - 1))))
    preview_font = {**font, "typewriter_delay_ms": 100, "typewriter_duration_ms": span}
    total = span + 600
    work = tempfile.mkdtemp(prefix="sf-typing-")
    background.add_task(_cleanup, work)
    key = Path(DEFAULT_KEY)
    sound_id = font.get("typewriter_sound_asset_id")
    if sound_id:
        sound = db.get(Asset, sound_id)
        if not sound or sound.project_id != scene.project_id or sound.type != AssetType.AUDIO:
            raise HTTPException(409, "The uploaded typewriter sound is no longer in this project. Choose Use included keystroke or upload it again.")
        from app.render.renderer import _resolve_asset_path
        decoded = Path(work) / "source.wav"
        try:
            subprocess.run([FFMPEG_BIN, "-hide_banner", "-nostdin", "-loglevel", "error", "-y", "-i", _resolve_asset_path(sound),
                            "-t", "30", "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", str(decoded)], check=True, capture_output=True, timeout=60)
            key = Path(extract_keystroke(decoded, Path(work) / "key.wav"))
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            raise HTTPException(422, "This sound file could not be read. Try a WAV or MP3 recording.") from None
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
    if not key.is_file():
        raise HTTPException(500, "The included keystroke sound is missing from this installation.")
    out = Path(work) / "preview.wav"
    write_typing_audio(reveal_schedule(words, total, preview_font), total, key, out, float(font.get("typewriter_volume", 50)) / 100)
    return FileResponse(out, media_type="audio/wav", headers={"Cache-Control": "no-store"})
