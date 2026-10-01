"""Bundled sticker & emoji library (assets/stickers/, built by scripts/build_sticker_library.py).

  GET  /api/stickers                                   manifest: categories, items, attribution
  GET  /api/stickers/{sticker_id}/image                the sticker PNG (picker thumbnails)
  POST /api/projects/{project_id}/stickers/{sticker_id} copy the sticker into the project's Media Pool
                                                       (re-used if already imported) and return the asset

A placed sticker is an ordinary project image asset, so projects never depend on the library after
the sticker is added (old projects with browser-drawn stickers keep working unchanged).
"""
from __future__ import annotations

import hashlib
import json
import shutil
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import MEDIA_DIR, RESOURCE_DIR
from app.db.database import get_db
from app.db.models import Asset, Project
from app.domain import schemas
from app.domain.constants import AssetOrigin

router = APIRouter(tags=["stickers"])
TWEMOJI_LICENSE = "CC-BY 4.0 (Twemoji by Twitter, Inc. and contributors)"


def library_dir() -> Path:
    for base in (Path(RESOURCE_DIR), Path(__file__).resolve().parents[3]):
        p = base / "assets" / "stickers"
        if (p / "library.json").is_file():
            return p
    return Path(RESOURCE_DIR) / "assets" / "stickers"


@lru_cache(maxsize=1)
def library() -> dict:
    path = library_dir() / "library.json"
    if not path.is_file():
        return {"categories": [], "items": [], "attribution": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def sticker(sticker_id: str) -> dict:
    for item in library()["items"]:
        if item["id"] == sticker_id:
            return item
    raise HTTPException(404, f"Unknown sticker: {sticker_id}")


def sticker_file(item: dict) -> Path:
    base = library_dir().resolve()
    path = (base / item["file"]).resolve()
    if base not in path.parents or not path.is_file():
        raise HTTPException(404, f"The sticker image is missing: {item['file']}")
    return path


@router.get("/api/stickers")
def list_stickers():
    lib = library()
    return {"categories": lib.get("categories", []), "attribution": lib.get("attribution", {}),
            "items": [{k: v for k, v in it.items() if k != "file"} for it in lib.get("items", [])]}


@router.get("/api/stickers/{sticker_id}/image")
def sticker_image(sticker_id: str):
    return FileResponse(sticker_file(sticker(sticker_id)), media_type="image/png",
                        headers={"Cache-Control": "public, max-age=86400"})


@router.post("/api/projects/{project_id}/stickers/{sticker_id}", response_model=schemas.AssetOut)
def import_sticker(project_id: str, sticker_id: str, db: Session = Depends(get_db)):
    from PIL import Image
    from app.render.renderer import _resolve_asset_path
    if not db.get(Project, project_id):
        raise HTTPException(404, "Project not found")
    item = sticker(sticker_id)
    src = sticker_file(item)
    for a in db.query(Asset).filter(Asset.project_id == project_id, Asset.type == "image").all():
        if (a.generation_metadata_json or {}).get("library_sticker") == sticker_id and Path(_resolve_asset_path(a)).is_file():
            return a
    data = src.read_bytes()
    folder = Path(MEDIA_DIR) / project_id
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / f"sticker_{sticker_id}_{hashlib.sha256(data).hexdigest()[:8]}.png"
    shutil.copyfile(src, dest)
    with Image.open(dest) as im:
        w, h = im.size
    twemoji = item.get("source") == "twemoji"
    asset = Asset(project_id=project_id, type="image", content_hash=hashlib.sha256(data).hexdigest(),
                  storage_key=str(dest.relative_to(MEDIA_DIR)), mime="image/png",
                  original_filename=f"sticker-{sticker_id}.png"[:255], width=w, height=h, origin=AssetOrigin.UPLOAD,
                  creator="Twemoji contributors" if twemoji else "SceneForge",
                  license_note=TWEMOJI_LICENSE if twemoji else "GPL-3.0-or-later (SceneForge sticker library)",
                  source_url="https://github.com/jdecked/twemoji" if twemoji else None,
                  generation_metadata_json={"library_sticker": sticker_id, "name": item["name"]})
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset
