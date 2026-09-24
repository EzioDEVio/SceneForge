from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.config import MAX_UPLOAD_BYTES, MEDIA_DIR, RENDERS_DIR
from app.db.database import get_db
from app.db.models import Asset, Project
from app.domain import schemas
from app.domain.constants import AssetOrigin
from app.render.ffmpeg_utils import FFmpegError, probe
from app.render.thumbnails import ThumbnailError, thumbnail_path
from app.security.uploads import UploadValidationError, classify_extension, safe_generated_filename

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.post("/upload", response_model=schemas.AssetOut)
async def upload_asset(project_id: str, file: UploadFile, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    try:
        asset_type = classify_extension(file.filename or "")
    except UploadValidationError as e:
        raise HTTPException(400, str(e))

    dest_name = safe_generated_filename(file.filename or "upload.bin")
    project_dir = Path(MEDIA_DIR) / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    dest_path = project_dir / dest_name

    hasher = hashlib.sha256()
    size = 0
    with open(dest_path, "wb") as out:
        while True:
            chunk = await file.read(1 << 20)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                out.close()
                dest_path.unlink(missing_ok=True)
                raise HTTPException(400, f"File exceeds {MAX_UPLOAD_BYTES} byte limit")
            hasher.update(chunk)
            out.write(chunk)

    try:
        info = probe(str(dest_path))
    except FFmpegError as e:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(400, f"File could not be decoded by FFmpeg: {e.stderr[:400]}")

    if asset_type == "image" and not info.has_video:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(400, "File extension suggests an image but no decodable image stream was found.")
    if asset_type == "video" and not info.has_video:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(400, "File extension suggests a video but no decodable video stream was found.")
    if asset_type == "audio" and not info.has_audio:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(400, "File extension suggests audio but no decodable audio stream was found.")

    asset = Asset(
        project_id=project_id,
        type=asset_type,
        content_hash=hasher.hexdigest(),
        storage_key=str(dest_path.relative_to(MEDIA_DIR)),
        mime=file.content_type or "",
        original_filename=file.filename or dest_name,
        width=info.width,
        height=info.height,
        duration_ms=info.duration_ms,
        origin=AssetOrigin.UPLOAD,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")


@router.get("/{asset_id}/stream")
def stream_asset(asset_id: str, request: Request, db: Session = Depends(get_db), download: int = 0):
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404, "Asset not found")
    base = RENDERS_DIR if asset.origin == AssetOrigin.RENDER_OUTPUT else MEDIA_DIR
    path = Path(base) / asset.storage_key
    if not path.exists():
        raise HTTPException(404, "Asset file missing on disk")

    file_size = path.stat().st_size
    range_header = request.headers.get("range")
    start, end = 0, file_size - 1
    status_code = 200
    headers = {"Accept-Ranges": "bytes", "Content-Type": asset.mime or "application/octet-stream"}
    if download:
        # A friendly, real filename for the "Download" button — the
        # on-disk name is an opaque UUID so users don't want that in
        # their downloads folder.
        ext = Path(asset.storage_key).suffix or ".mp4"
        safe_name = (asset.original_filename or f"sceneforge-video{ext}").replace('"', "")
        headers["Content-Disposition"] = f'attachment; filename="{safe_name}"'

    if range_header:
        m = RANGE_RE.match(range_header)
        if m:
            if m.group(1):
                start = int(m.group(1))
            if m.group(2):
                end = int(m.group(2))
            status_code = 206
            headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"

    length = end - start + 1

    def iterfile():
        with open(path, "rb") as f:
            f.seek(start)
            remaining = length
            chunk_size = 1 << 20
            while remaining > 0:
                chunk = f.read(min(chunk_size, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    headers["Content-Length"] = str(length)
    return StreamingResponse(iterfile(), status_code=status_code, headers=headers)


@router.get("/{asset_id}/thumbnail")
def asset_thumbnail(asset_id: str, w: int = 320, db: Session = Depends(get_db)):
    """Cached JPEG thumbnail (image) or poster frame (video)."""
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404, "Asset not found")
    if asset.type not in ("image", "video"):
        raise HTTPException(415, "Thumbnails are available for images and videos only.")
    base = Path(RENDERS_DIR if asset.origin == AssetOrigin.RENDER_OUTPUT else MEDIA_DIR).resolve()
    path = (base / asset.storage_key).resolve()
    if base not in path.parents or not path.exists():
        raise HTTPException(404, "Asset file missing on disk")
    try:
        thumb = thumbnail_path(asset.id, path, asset.type, asset.duration_ms, w)
    except ThumbnailError as e:
        raise HTTPException(422, str(e))
    return FileResponse(thumb, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})


@router.get("/{asset_id}", response_model=schemas.AssetOut)
def get_asset(asset_id: str, db: Session = Depends(get_db)):
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404, "Asset not found")
    return asset

@router.get('', response_model=list[schemas.AssetOut])
def list_project_assets(project_id: str, db: Session = Depends(get_db)):
    if not db.get(Project, project_id): raise HTTPException(404, 'Project not found')
    return [a for a in db.query(Asset).filter(Asset.project_id==project_id,Asset.origin.in_(['upload','generated','stock_search'])).order_by(Asset.created_at).all()
            if not (a.generation_metadata_json or {}).get('hidden_from_pool')]

@router.post('/{asset_id}/hide-from-pool')
def hide_from_pool(asset_id: str, db: Session = Depends(get_db)):
    a=db.get(Asset,asset_id)
    if not a:raise HTTPException(404,'Asset not found')
    a.generation_metadata_json={**(a.generation_metadata_json or {}),'hidden_from_pool':True}
    db.commit();return {'ok':True}
