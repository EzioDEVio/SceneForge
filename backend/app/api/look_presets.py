"""Look preset packs: Premiere-style shareable look presets.

A pack file (.json or .sflook) looks like:

  {"format": "sceneforge-look-pack", "version": 1,
   "presets": [{"name": "Noir", "description": "optional",
                "effect_preset": "noir", "effect_intensity": 100,
                "look": {...subset of scene.look_json...}}]}

Only portable look keys are allowed (PRESET_LOOK_KEYS); media- or
position-specific keys (overlays, route, annotations, redact, spotlight,
LUT asset ids, layouts, parallax, countdown) are rejected. Every preset is
validated through the same validators as PATCH /api/scenes (scenes._validated_look).

Imported / saved presets are stored per user in SCENEFORGE_DATA_DIR/look_presets.json.
The built-in starter pack ships in assets/look-packs/.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Scene
from app.domain.constants import EffectPreset

router = APIRouter(prefix="/api/look-presets", tags=["look-presets"])

PACK_FORMAT = "sceneforge-look-pack"
PACK_VERSION = 1
MAX_PRESETS = 200
MAX_NAME = 60
MAX_DESCRIPTION = 200
# Portable look settings. Applying a preset replaces exactly these keys on the scene.
PRESET_LOOK_KEYS = ("adjust", "tone", "wheels", "film", "glitch", "focus", "mosaic", "rgbsplit",
                    "leak", "flare", "wiggle", "shake", "vignette", "letterbox", "sharpen", "fx_order", "fx_bypass", "fx_params")
MEDIA_KEYS = {"overlays", "route", "annotations", "redact", "spotlight", "lut", "layout", "parallax", "countdown"}
_lock = threading.Lock()


class PackError(ValueError):
    pass


def _store_path() -> Path:
    from app.config import DATA_DIR
    return Path(DATA_DIR) / "look_presets.json"


def starter_pack_path() -> Path | None:
    from app.config import RESOURCE_DIR
    for base in (Path(RESOURCE_DIR), Path(__file__).resolve().parents[3]):
        p = base / "assets" / "look-packs" / "sceneforge-starter-pack.json"
        if p.exists():
            return p
    return None


def clean_preset(raw, index: int = 0) -> dict:
    """Validate one preset; returns the cleaned preset (without id)."""
    from app.api.scenes import _validated_look
    where = f"Preset {index + 1}"
    if not isinstance(raw, dict):
        raise PackError(f"{where} must be an object.")
    unknown = set(raw) - {"name", "description", "effect_preset", "effect_intensity", "look", "id", "created_at"}
    if unknown:
        raise PackError(f"{where}: unknown field(s) {', '.join(sorted(unknown))}.")
    name = raw.get("name")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > MAX_NAME:
        raise PackError(f"{where} needs a name of 1-{MAX_NAME} characters.")
    name = name.strip()
    where = f"Preset {index + 1} (“{name}”)"
    desc = raw.get("description", "")
    if not isinstance(desc, str) or len(desc) > MAX_DESCRIPTION:
        raise PackError(f"{where}: description must be text of at most {MAX_DESCRIPTION} characters.")
    preset = raw.get("effect_preset", EffectPreset.ORIGINAL.value)
    if preset not in [e.value for e in EffectPreset]:
        raise PackError(f"{where}: unknown effect preset '{preset}'.")
    intensity = raw.get("effect_intensity", 100)
    if isinstance(intensity, bool) or not isinstance(intensity, (int, float)) or not 0 <= intensity <= 100:
        raise PackError(f"{where}: effect intensity must be between 0 and 100.")
    look = raw.get("look", {})
    if not isinstance(look, dict):
        raise PackError(f"{where}: look must be an object.")
    look = {k: v for k, v in look.items() if v is not None}
    media = sorted(set(look) & MEDIA_KEYS)
    if media:
        raise PackError(f"{where}: {', '.join(media)} {'is' if len(media) == 1 else 'are'} specific to a scene's media and can't be part of a look preset.")
    other = sorted(set(look) - set(PRESET_LOOK_KEYS))
    if other:
        raise PackError(f"{where}: unknown look setting(s) {', '.join(other)}.")
    try:
        cleaned = _validated_look(SimpleNamespace(look_json={}, project_id=None), look, None)
    except HTTPException as e:
        raise PackError(f"{where}: {e.detail}") from None
    out = {"name": name, "effect_preset": preset, "effect_intensity": int(round(intensity)), "look": cleaned}
    if desc:
        out["description"] = desc
    return out


def clean_pack(pack) -> list[dict]:
    if not isinstance(pack, dict):
        raise PackError("This file is not a SceneForge look pack (expected a JSON object).")
    if pack.get("format") != PACK_FORMAT:
        raise PackError(f"This file is not a SceneForge look pack (format must be \"{PACK_FORMAT}\").")
    if pack.get("version") != PACK_VERSION:
        raise PackError(f"Unsupported look pack version {pack.get('version')!r}; this SceneForge reads version {PACK_VERSION}.")
    presets = pack.get("presets")
    if not isinstance(presets, list) or not presets:
        raise PackError("The look pack has no presets.")
    if len(presets) > MAX_PRESETS:
        raise PackError(f"A look pack can hold at most {MAX_PRESETS} presets.")
    return [clean_preset(p, i) for i, p in enumerate(presets)]


def make_pack(presets: list[dict]) -> dict:
    keep = ("name", "description", "effect_preset", "effect_intensity", "look")
    return {"format": PACK_FORMAT, "version": PACK_VERSION, "presets": [{k: p[k] for k in keep if k in p} for p in presets]}


def preset_from_scene(scene: Scene, name: str) -> dict:
    look = {k: v for k, v in (scene.look_json or {}).items() if k in PRESET_LOOK_KEYS and v not in (None, [], {})}
    return {"name": name, "effect_preset": scene.effect_preset, "effect_intensity": int(scene.effect_intensity), "look": look}


def _load() -> list[dict]:
    p = _store_path()
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return [x for x in data.get("presets", []) if isinstance(x, dict) and x.get("id")]
    except (OSError, ValueError, AttributeError):
        return []


def _save(presets: list[dict]) -> None:
    p = _store_path()
    tmp = p.with_suffix(f".{uuid.uuid4().hex[:6]}.tmp")
    tmp.write_text(json.dumps({"format": PACK_FORMAT, "version": PACK_VERSION, "presets": presets}, indent=2), encoding="utf-8")
    os.replace(tmp, p)


def _builtin() -> list[dict]:
    p = starter_pack_path()
    if not p:
        return []
    try:
        presets = clean_pack(json.loads(p.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return []
    return [{**x, "id": f"builtin-{i}", "builtin": True} for i, x in enumerate(presets)]


def _unique_name(name: str, taken: set[str]) -> str:
    if name not in taken:
        return name
    n = 2
    while (candidate := f"{name[:MAX_NAME - len(f' ({n})')]} ({n})") in taken:
        n += 1
    return candidate


@router.get("")
def list_presets():
    return {"presets": _load(), "builtin": _builtin(), "look_keys": list(PRESET_LOOK_KEYS), "format": PACK_FORMAT, "version": PACK_VERSION}


@router.post("/validate")
def validate_pack(body: dict):
    try:
        return {"ok": True, "presets": clean_pack(body)}
    except PackError as e:
        raise HTTPException(400, str(e))


@router.post("")
def import_presets(body: dict):
    """Store presets: body is a whole pack, or {"preset": {...}} for one preset."""
    try:
        cleaned = [clean_preset(body["preset"])] if isinstance(body, dict) and "preset" in body and "format" not in body else clean_pack(body)
    except PackError as e:
        raise HTTPException(400, str(e))
    with _lock:
        presets = _load()
        if len(presets) + len(cleaned) > MAX_PRESETS:
            raise HTTPException(400, f"You can keep at most {MAX_PRESETS} presets. Delete some first.")
        taken = {p["name"] for p in presets}
        added = []
        for c in cleaned:
            c = {**c, "name": _unique_name(c["name"], taken), "id": uuid.uuid4().hex[:12], "created_at": int(time.time())}
            taken.add(c["name"]); presets.append(c); added.append(c)
        _save(presets)
    return {"added": added, "presets": presets}


@router.delete("/{preset_id}")
def delete_preset(preset_id: str):
    with _lock:
        presets = _load()
        left = [p for p in presets if p.get("id") != preset_id]
        if len(left) == len(presets):
            raise HTTPException(404, "Preset not found.")
        _save(left)
    return {"presets": left}


@router.get("/export")
def export_presets(ids: str | None = None):
    """The stored presets (all, or a comma-separated id list) as a pack file."""
    presets = _load()
    if ids:
        wanted = set(ids.split(","))
        presets = [p for p in presets if p["id"] in wanted]
    return make_pack(presets)


@router.get("/scene/{scene_id}")
def export_scene_look(scene_id: str, name: str = "My look", db: Session = Depends(get_db)):
    """This scene's portable look as a one-preset pack (validated)."""
    scene = db.get(Scene, scene_id)
    if not scene:
        raise HTTPException(404, "Scene not found")
    try:
        preset = clean_preset(preset_from_scene(scene, (name or "My look").strip()[:MAX_NAME] or "My look"))
    except PackError as e:
        raise HTTPException(400, str(e))
    return make_pack([preset])
