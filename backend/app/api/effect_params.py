"""GET /api/effects/schema — per-effect settings schema (render/effect_params.py),
so the editor's "Effect settings" panel is generated from the same definitions
the renderer validates and builds with."""
from fastapi import APIRouter

from app.render.effect_params import schema

router = APIRouter(prefix="/api/effects", tags=["effects"])


@router.get("/schema")
def effects_schema() -> dict:
    return schema()
