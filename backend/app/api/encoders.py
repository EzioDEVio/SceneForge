"""GET /api/system/encoders — hardware video encoders found at startup (render/gpu.py)."""
from __future__ import annotations

from fastapi import APIRouter

from app.render import gpu

router = APIRouter(tags=["system"], on_startup=[gpu.detect_in_background])


@router.get("/api/system/encoders")
def system_encoders(refresh: bool = False):
    info = gpu.detect(refresh=refresh)
    return {**info, "choices": list(gpu.CHOICES), "default": "auto"}
