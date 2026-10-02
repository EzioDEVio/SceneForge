"""Project snapshots / restore points (0.9.0).

A snapshot is the project's database rows (project, assets, scenes, shots, voice takes) written to
DATA_DIR/snapshots/<project id>/<snapshot id>.json. Media files are not copied: assets point at the
same files, which SceneForge never deletes while a project row still uses them (and deleting a
project keeps media on disk). Rendered parts are not kept; a restored project renders fresh.

Restoring never overwrites anything: it creates a NEW project ("<title> (restored <time>)") with new
ids, exactly like Project → Duplicate. So a restore can always be undone by deleting the copy.

Automatic snapshots are requested by the editor every few minutes while a project is open; a
snapshot is only written when the project changed since the last one (content hash).
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import DATA_DIR
from app.db.models import Asset, Project, Scene, Shot, VoiceTake
from app.domain.project_copy import _remap

SNAP_DIR = Path(DATA_DIR) / "snapshots"
KEEP_AUTO = 20       # automatic restore points kept per project
KEEP_MANUAL = 20     # "Save restore point now" snapshots kept per project
_SKIP = {"created_at", "updated_at"}


class SnapshotError(ValueError):
    pass


def _row(row) -> dict:
    return {c.key: getattr(row, c.key) for c in type(row).__table__.columns if c.key not in _SKIP}


def project_rows(db: Session, project: Project) -> dict:
    assets = db.query(Asset).filter(Asset.project_id == project.id).order_by(Asset.id).all()
    scenes = list(project.scenes)
    return {
        "project": _row(project),
        "assets": [_row(a) for a in assets],
        "scenes": [_row(s) for s in scenes],
        "shots": [_row(sh) for s in scenes for sh in s.shots],
        "takes": [_row(t) for s in scenes for t in s.voice_takes],
    }


def _content_hash(rows: dict) -> str:
    # Ignore render bookkeeping and revision counters; they change without the user editing anything.
    def strip(d: dict) -> dict:
        return {k: v for k, v in d.items() if k not in ("revision", "rendered_asset_id", "rendered_plan_hash")}
    data = {k: ([strip(r) for r in v] if isinstance(v, list) else strip(v)) for k, v in rows.items()}
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()


def _folder(project_id: str) -> Path:
    if not project_id or "/" in project_id or "\\" in project_id or ".." in project_id:
        raise SnapshotError("Invalid project id.")
    return SNAP_DIR / project_id


def list_snapshots(project_id: str) -> list[dict]:
    folder = _folder(project_id)
    out = []
    for f in folder.glob("*.json") if folder.is_dir() else []:
        try:
            meta = json.loads(f.read_text(encoding="utf-8")).get("meta", {})
        except (OSError, ValueError):
            continue
        out.append({"id": f.stem, **meta})
    return sorted(out, key=lambda m: (m.get("created_at", ""), m.get("seq", 0)), reverse=True)


def save_snapshot(db: Session, project: Project, reason: str = "manual", label: str = "") -> dict | None:
    """Write a snapshot. For automatic ones, return None when nothing changed since the last one."""
    rows = project_rows(db, project)
    digest = _content_hash(rows)
    existing = list_snapshots(project.id)
    if reason == "auto" and existing and existing[0].get("hash") == digest:
        return None
    folder = _folder(project.id)
    folder.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    snap_id = now.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    meta = {"created_at": now.isoformat(timespec="seconds"), "reason": "auto" if reason == "auto" else "manual",
            "label": str(label or "")[:80], "title": project.title, "scenes": len(rows["scenes"]),
            "hash": digest, "version": 1, "seq": time.time_ns()}
    tmp = folder / f".{snap_id}.{os.getpid()}.tmp"
    tmp.write_text(json.dumps({"meta": meta, "rows": rows}, default=str), encoding="utf-8")
    tmp.replace(folder / f"{snap_id}.json")
    _prune(project.id)
    return {"id": snap_id, **meta}


def _prune(project_id: str) -> None:
    snaps = list_snapshots(project_id)
    for kind, keep in (("auto", KEEP_AUTO), ("manual", KEEP_MANUAL)):
        for old in [s for s in snaps if s.get("reason") == kind][keep:]:
            try:
                (_folder(project_id) / f"{old['id']}.json").unlink()
            except OSError:
                pass


def delete_snapshot(project_id: str, snap_id: str) -> bool:
    path = _folder(project_id) / f"{snap_id}.json"
    if "/" in snap_id or "\\" in snap_id or not path.is_file():
        return False
    path.unlink()
    return True


def delete_all(project_id: str) -> None:
    folder = _folder(project_id)
    for f in folder.glob("*.json") if folder.is_dir() else []:
        try:
            f.unlink()
        except OSError:
            pass


def restore_snapshot(db: Session, project_id: str, snap_id: str) -> Project:
    path = _folder(project_id) / f"{snap_id}.json"
    if "/" in snap_id or "\\" in snap_id or not path.is_file():
        raise SnapshotError("That restore point no longer exists.")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        rows, meta = data["rows"], data.get("meta", {})
    except (OSError, ValueError, KeyError):
        raise SnapshotError("That restore point could not be read.") from None
    ids: dict[str, str] = {}
    for key in ("project",):
        ids[rows[key]["id"]] = str(uuid.uuid4())
    for key in ("assets", "scenes", "shots", "takes"):
        for r in rows[key]:
            ids[r["id"]] = str(uuid.uuid4())

    def build(cls, values: dict, **overrides):
        known = {c.key for c in cls.__table__.columns}
        clean = {k: _remap(v, ids) if isinstance(v, (dict, list)) else (ids.get(v, v) if isinstance(v, str) else v)
                 for k, v in values.items() if k in known and k != "id"}
        clean.update(overrides)
        return cls(id=ids[values["id"]], **clean)

    when = meta.get("created_at", "")
    try:
        stamp = datetime.fromisoformat(when).astimezone().strftime("%b %d %H:%M")
    except ValueError:
        stamp = "earlier"
    title = f"{rows['project'].get('title') or 'Project'} (restored {stamp})"[:255]
    project = build(Project, rows["project"], title=title, revision=1)
    db.add(project)
    db.flush()
    for a in rows["assets"]:
        db.add(build(Asset, a))
    db.flush()
    for s in rows["scenes"]:
        db.add(build(Scene, s, rendered_asset_id=None, rendered_plan_hash=None, revision=1))
    db.flush()
    for sh in rows["shots"]:
        db.add(build(Shot, sh))
    for t in rows["takes"]:
        db.add(build(VoiceTake, t))
    db.flush()
    db.refresh(project)
    return project
