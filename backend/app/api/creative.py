"""Subject cutout (beta) and textured text titles.

  GET  /api/cutout/status                      model folder, which models are downloaded
  POST /api/assets/{asset_id}/cutout           {model?, edge?, feather?} -> new RGBA image asset
  POST /api/scenes/{scene_id}/subject-layer    {model?, edge?, feather?} -> "text behind subject" overlay
  POST /api/scenes/{scene_id}/textured-title   {text, texture: {preset}|{asset_id}|{prompt, provider_id?}, ...}
"""
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import MEDIA_DIR
from app.db.database import get_db
from app.db.models import Asset, Scene
from app.domain import schemas
from app.domain.constants import AssetOrigin

router = APIRouter(tags=["creative"])


class CutoutRequest(BaseModel):
    model: Literal["isnet", "u2netp"] = "isnet"
    edge: Literal["soft", "crisp"] = "soft"
    feather: int = Field(default=0, ge=0, le=20)


def _asset_file(asset: Asset) -> Path:
    from app.render.renderer import _resolve_asset_path
    return Path(_resolve_asset_path(asset))


def _store_png(db: Session, project_id: str, path: Path, name: str, meta: dict) -> Asset:
    from PIL import Image
    data = path.read_bytes()
    with Image.open(path) as im:
        w, h = im.size
    asset = Asset(project_id=project_id, type="image", content_hash=hashlib.sha256(data).hexdigest(),
                  storage_key=str(path.relative_to(MEDIA_DIR)), mime="image/png", original_filename=name[:255],
                  width=w, height=h, origin=AssetOrigin.UPLOAD, generation_metadata_json=meta)
    db.add(asset)
    db.flush()
    return asset


def _cached(db: Session, project_id: str, key: str, value: str) -> Asset | None:
    for a in db.query(Asset).filter(Asset.project_id == project_id, Asset.type == "image").all():
        if (a.generation_metadata_json or {}).get(key) == value and _asset_file(a).is_file():
            return a
    return None


def _make_cutout(db: Session, src: Asset, body: CutoutRequest) -> Asset:
    from app.render.cutout import CutoutError, cutout_file
    if src.type != "image":
        raise HTTPException(400, "Background removal works on still images. Choose a PNG, JPEG or WebP image.")
    if not _asset_file(src).is_file():
        raise HTTPException(404, "This image is missing on disk.")
    key = hashlib.sha256(f"{src.content_hash}|{body.model}|{body.edge}|{body.feather}".encode()).hexdigest()
    hit = _cached(db, src.project_id, "cutout_key", key)
    if hit:
        return hit
    folder = Path(MEDIA_DIR) / src.project_id
    dest = folder / f"cutout_{uuid.uuid4().hex[:10]}.png"
    try:
        cutout_file(str(_asset_file(src)), str(dest), body.model, body.edge, body.feather)
    except CutoutError as e:
        dest.unlink(missing_ok=True)
        raise HTTPException(503 if "download" in str(e) else 422, str(e))
    stem = Path(src.original_filename or "image").stem
    return _store_png(db, src.project_id, dest, f"{stem} (cutout).png",
                      {"cutout_key": key, "cutout": {"source_asset_id": src.id, "model": body.model, "edge": body.edge, "feather": body.feather}})


@router.get("/api/cutout/status")
def cutout_status():
    from app.render.cutout import status
    return status()


@router.post("/api/assets/{asset_id}/cutout", response_model=schemas.AssetOut)
def cutout_asset(asset_id: str, body: CutoutRequest | None = None, db: Session = Depends(get_db)):
    src = db.get(Asset, asset_id)
    if not src:
        raise HTTPException(404, "Asset not found")
    asset = _make_cutout(db, src, body or CutoutRequest())
    db.commit()
    db.refresh(asset)
    return asset


def _scene_out(scene: Scene):
    from app.api.scenes import _out
    return _out(scene)


def _add_overlay(db: Session, scene: Scene, overlay: dict, replace_kind: str | None = None) -> list[dict]:
    from app.render.overlays import MAX_OVERLAYS, OverlayError, clean_overlays
    current = [o for o in (scene.overlays_json or []) if not (replace_kind and o.get("kind") == replace_kind)]
    if len(current) >= MAX_OVERLAYS:
        raise HTTPException(400, f"This scene already has {MAX_OVERLAYS} overlays. Remove one in the Overlays tab first.")
    try:
        cleaned = clean_overlays([*current, overlay], scene.project_id, db)
    except OverlayError as e:
        raise HTTPException(400, str(e))
    scene.overlays_json = cleaned
    scene.revision += 1
    return cleaned


@router.post("/api/scenes/{scene_id}/subject-layer")
def subject_layer(scene_id: str, body: CutoutRequest | None = None, db: Session = Depends(get_db)):
    """Cut the subject out of the scene's image and put it on top of captions and titles."""
    from app.render.cutout import frame_layer
    from app.render.filters import is_static_plan, resolve_motion
    from app.render.media import selected_shots
    body = body or CutoutRequest()
    scene = db.get(Scene, scene_id)
    if not scene:
        raise HTTPException(404, "Scene not found")
    shots = selected_shots(scene)
    if not shots:
        raise HTTPException(400, "Add an image to this scene first.")
    shot, look = shots[0], scene.look_json or {}
    if shot.asset.type != "image":
        raise HTTPException(400, "Text behind subject works on still images. This scene's media is a video.")
    if len(shots) > 1 or look.get("layout"):
        raise HTTPException(400, f"Text behind subject needs a scene with one image; this scene shows {len(shots)} media items. Move the others to their own scenes first.")
    if shot.fit == "cover" and not is_static_plan(resolve_motion(shot.motion_json or {})):
        raise HTTPException(400, "This image has camera movement (zoom/pan). The cutout layer is static and would drift off the subject. Set Camera movement to Static in the Motion tab, then try again.")
    moving = [label for key, label in (("parallax", "2.5D parallax"), ("wiggle", "wiggle"), ("shake", "camera shake")) if look.get(key)]
    if moving:
        raise HTTPException(400, f"This scene uses {', '.join(moving)}, which moves the picture under a static cutout. Turn it off in Effects, then try again.")
    cut = _make_cutout(db, shot.asset, body)
    project = scene.project
    crop = shot.crop_json or None
    key = hashlib.sha256(f"{cut.id}|{shot.fit}|{crop}|{project.width}x{project.height}".encode()).hexdigest()
    layer = _cached(db, scene.project_id, "subject_layer_key", key)
    if not layer:
        from PIL import Image
        src = _asset_file(cut)
        folder = Path(MEDIA_DIR) / scene.project_id
        if crop:
            # Same crop as the renderer (fractions of the source, even sizes) before fitting.
            with Image.open(src) as im:
                cw, ch = max(2, int(im.width * crop["width"] / 2) * 2), max(2, int(im.height * crop["height"] / 2) * 2)
                x, y = int(im.width * crop["x"]), int(im.height * crop["y"])
                cropped = folder / f"subjcrop_{uuid.uuid4().hex[:8]}.png"
                im.crop((x, y, x + cw, y + ch)).save(cropped)
            src = cropped
        dest = folder / f"subject_{uuid.uuid4().hex[:10]}.png"
        frame_layer(str(src), str(dest), shot.fit, project.width, project.height)
        if crop:
            Path(src).unlink(missing_ok=True)
        layer = _store_png(db, scene.project_id, dest, f"{Path(cut.original_filename).stem} (subject layer).png",
                           {"subject_layer_key": key, "hidden_from_pool": True, "cutout_asset_id": cut.id})
    overlay = {"id": "subject", "asset_id": layer.id, "kind": "subject", "above_text": True, "x": 50, "y": 50, "width": 100,
               "rotation": 0, "opacity": 100, "radius": 0, "border": 0, "shadow": 0, "start_ms": 0, "end_ms": None,
               "anim_in": "none", "anim_out": "none", "anim_ms": 0, "loop": "none"}
    cleaned = _add_overlay(db, scene, overlay, replace_kind="subject")
    notes = []
    if scene.effect_preset != "original" or any(look.get(k) for k in ("adjust", "lut", "film", "tone", "wheels", "glitch")):
        notes.append("Colour looks and effects are applied to the picture but not to the cutout layer, so the subject may look slightly different. Check the render.")
    if shot.fit != "cover":
        notes.append("The image is letterboxed (Fit inside frame); the cutout follows the same placement.")
    db.commit()
    db.refresh(scene)
    return {"scene": _scene_out(scene), "overlay": next(o for o in cleaned if o["kind"] == "subject"),
            "cutout_asset": schemas.AssetOut.model_validate(cut), "notes": notes}


class TextureSource(BaseModel):
    preset: str | None = None
    asset_id: str | None = None
    prompt: str | None = Field(default=None, max_length=1000)
    provider_id: str | None = None


class TexturedTitleRequest(BaseModel):
    text: str = Field(min_length=1, max_length=80)
    texture: TextureSource
    font: str = "Anton"
    font_size: int = Field(default=160, ge=24, le=400)
    outline: int = Field(default=0, ge=0, le=30)
    outline_color: str = Field(default="#FFFFFF", pattern=r"^#[0-9A-Fa-f]{6}$")
    glow: int = Field(default=0, ge=0, le=100)
    glow_color: str = Field(default="#FFD25A", pattern=r"^#[0-9A-Fa-f]{6}$")
    shadow: bool = True
    x: float = Field(default=50, ge=-50, le=150)
    y: float = Field(default=30, ge=-50, le=150)
    width: float | None = Field(default=None, ge=3, le=100)


@router.post("/api/scenes/{scene_id}/textured-title")
def textured_title(scene_id: str, body: TexturedTitleRequest, db: Session = Depends(get_db)):
    from PIL import Image
    from app.render.textured_text import PRESETS, TexturedTextError, render_textured_text
    scene = db.get(Scene, scene_id)
    if not scene:
        raise HTTPException(404, "Scene not found")
    from app.render.overlays import MAX_OVERLAYS
    if len(scene.overlays_json or []) >= MAX_OVERLAYS:
        raise HTTPException(400, f"This scene already has {MAX_OVERLAYS} overlays. Remove one in the Overlays tab first.")
    tex = body.texture
    chosen = [k for k in ("preset", "asset_id", "prompt") if getattr(tex, k)]
    if len(chosen) != 1:
        raise HTTPException(400, "Choose exactly one texture: a preset, an image from the Media Pool, or a prompt.")
    texture_asset = None
    if tex.preset:
        if tex.preset not in PRESETS:
            raise HTTPException(400, f"Texture preset must be one of: {', '.join(PRESETS)}.")
        texture = tex.preset
    else:
        if tex.prompt:
            from app.api.images import generate_image_for_scene
            req = schemas.GenerateImageRequest(prompt=f"Seamless full-frame surface texture, no text, no letters, no objects: {tex.prompt.strip()}",
                                               size="1024x1024", provider_id=tex.provider_id)
            texture_asset = generate_image_for_scene(scene.id, req, db)
        else:
            texture_asset = db.get(Asset, tex.asset_id)
            if not texture_asset or texture_asset.project_id != scene.project_id or texture_asset.type != "image":
                raise HTTPException(400, "Choose an image from this project's Media Pool as the texture.")
        try:
            texture = Image.open(_asset_file(texture_asset))
            texture.load()
        except Exception:
            raise HTTPException(400, "The texture image could not be read.")
    try:
        img = render_textured_text(body.text, texture, body.font, body.font_size, body.outline, body.outline_color,
                                   body.glow, body.glow_color, body.shadow)
    except TexturedTextError as e:
        raise HTTPException(400, str(e))
    folder = Path(MEDIA_DIR) / scene.project_id
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / f"textured_{uuid.uuid4().hex[:10]}.png"
    img.save(dest)
    label = "".join(ch for ch in body.text if ch.isalnum() or ch in " -")[:30].strip() or "title"
    meta = {"textured_title": {"text": body.text, "preset": tex.preset, "texture_asset_id": texture_asset.id if texture_asset else None,
                               "font": body.font, "font_size": body.font_size}}
    asset = _store_png(db, scene.project_id, dest, f"sticker-textured-{label}.png", meta)
    project = scene.project
    # font_size is px at 1080p; keep that scale on any canvas unless a width is given.
    width = body.width or max(3.0, min(100.0, round(img.width * project.height / 1080 / project.width * 100, 2)))
    overlay = {"id": "tt" + uuid.uuid4().hex[:6], "asset_id": asset.id, "kind": "sticker", "x": body.x, "y": body.y, "width": width,
               "rotation": 0, "opacity": 100, "radius": 0, "border": 0, "shadow": 0, "anim_in": "zoom", "anim_out": "fade", "anim_ms": 500}
    cleaned = _add_overlay(db, scene, overlay)
    db.commit()
    db.refresh(scene)
    return {"scene": _scene_out(scene), "overlay": cleaned[-1], "asset": schemas.AssetOut.model_validate(asset),
            "texture_asset": schemas.AssetOut.model_validate(texture_asset) if texture_asset else None}
