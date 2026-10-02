"""Whole-project copy: project row, assets, scenes, shots and voice takes.

Assets are project-scoped rows (shots may only use assets of their own project), so the copy gets
its own asset rows that point at the SAME media files (storage_key); deleting a project keeps media
on disk, so sharing files between the two projects is safe. Every id the copy references —
foreign keys and ids inside JSON (overlays, LUTs, stickers, music and audio clips, cutout sources)
— is remapped to the copy's rows. Rendered parts and render jobs are not copied: the copy renders
fresh. New columns added to these tables later are copied automatically.
"""
from __future__ import annotations

import uuid
from copy import deepcopy

from sqlalchemy.orm import Session

from app.db.models import Asset, Project, Scene, Shot, VoiceTake

_SKIP = {"id", "created_at", "updated_at"}


def _remap(value, ids: dict[str, str]):
    if isinstance(value, str):
        if value in ids:
            return ids[value]
        if len(value) > 36 and any(k in value for k in ids):
            for old, new in ids.items():
                if old in value:
                    value = value.replace(old, new)
        return value
    if isinstance(value, dict):
        return {_remap(k, ids): _remap(v, ids) for k, v in value.items()}
    if isinstance(value, list):
        return [_remap(v, ids) for v in value]
    return value


def _clone(row, new_id: str, ids: dict[str, str], **overrides):
    cls = type(row)
    values = {"id": new_id}
    for col in cls.__table__.columns:
        if col.key in _SKIP:
            continue
        v = getattr(row, col.key)
        if isinstance(v, (dict, list)):
            v = _remap(deepcopy(v), ids)
        elif isinstance(v, str) and v in ids:
            v = ids[v]
        values[col.key] = v
    values.update(overrides)
    return cls(**values)


def copy_project(db: Session, src: Project, title: str | None = None, **project_overrides) -> Project:
    """Copy `src` into a new project (not committed). Returns the new Project."""
    ids: dict[str, str] = {src.id: str(uuid.uuid4())}
    assets = db.query(Asset).filter(Asset.project_id == src.id).all()
    for a in assets:
        ids[a.id] = str(uuid.uuid4())
    for s in src.scenes:
        ids[s.id] = str(uuid.uuid4())
        for sh in s.shots:
            ids[sh.id] = str(uuid.uuid4())
        for t in s.voice_takes:
            ids[t.id] = str(uuid.uuid4())

    project = _clone(src, ids[src.id], ids, title=title or f"{src.title} (copy)", revision=1, **project_overrides)
    db.add(project)
    db.flush()
    for a in assets:
        db.add(_clone(a, ids[a.id], ids))
    db.flush()
    for s in src.scenes:
        db.add(_clone(s, ids[s.id], ids, rendered_asset_id=None, rendered_plan_hash=None, revision=1))
    db.flush()
    for s in src.scenes:
        for sh in s.shots:
            db.add(_clone(sh, ids[sh.id], ids))
        for t in s.voice_takes:
            db.add(_clone(t, ids[t.id], ids))
    db.flush()
    db.refresh(project)
    project._copy_id_map = ids  # type: ignore[attr-defined]  # for callers that need old -> new ids
    return project
