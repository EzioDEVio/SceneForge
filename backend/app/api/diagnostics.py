"""Help → Export diagnostics: GET /api/diagnostics.zip

A zip for bug reports with versions, platform, model status, Whisper checks, database row
counts (no content), recent job outcomes and recent backend logs. It never contains API
keys or other secrets: provider profiles are reduced to name/capability/model/configured,
environment variables whose names look secret are dropped, and as a final pass every known
secret value (environment secrets, the desktop session token and each provider key that can
be read from the credential store) is replaced with [redacted] in every file of the zip.
"""
from __future__ import annotations

import io
import json
import os
import platform
import re
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import Response
from sqlalchemy import inspect, text

router = APIRouter(tags=["diagnostics"])

SECRET_NAME = re.compile(r"KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|AUTH|COOKIE", re.I)
# Common provider key shapes, scrubbed even if they were not found in the credential store.
SECRET_SHAPES = re.compile(r"\b(?:sk-[A-Za-z0-9_\-]{12,}|hf_[A-Za-z0-9]{12,}|r8_[A-Za-z0-9]{12,}|AIza[0-9A-Za-z_\-]{20,}|xi-[A-Za-z0-9]{16,})\b")
ENV_PREFIXES = ("SCENEFORGE_", "HF_", "PYTHON", "PATH", "LANG", "LC_", "OS", "PROCESSOR_", "NUMBER_OF_PROCESSORS", "CUDA", "OMP_")
LOG_FILES = ("desktop-backend.log", "updates.log")
LOG_TAIL_BYTES = 256 * 1024

README = """SceneForge Studio diagnostics
==============================

Created by Help > Export diagnostics. Attach this zip to a GitHub issue or send it to the
developer. It contains no media, no project text and no API keys.

Files
-----
README.txt            this file
system.json           SceneForge build, OS, Python, FFmpeg/FFprobe versions, CPU/RAM, GPU (if detected)
settings.json         non-secret settings: provider profiles (name, capability, model, configured yes/no
                      only - never the key), local image engine settings, selected environment variables
                      (any variable whose name looks secret, e.g. *KEY*, *TOKEN*, *SECRET*, *PASSWORD*,
                      is left out)
models.json           the AI model manager listing (Whisper, background removal, voice isolation):
                      downloaded or not, bundled or not, size and folder
whisper_check.json    local captions self-check (engine, model folder, write access)
database.json         number of rows per database table (counts only, no content)
jobs.json             the last 20 render/export jobs: status, stage, progress, error message, times
logs/backend-recent.log   recent backend log lines kept in memory by this run
logs/desktop-backend.log  tail of the desktop app's backend log (desktop app only)
logs/updates.log          tail of the desktop updater log (desktop app only)

Privacy
-------
Secrets are removed in two ways: they are never collected, and as a final pass every known
secret value (environment secrets, the desktop session token and saved provider keys) is
replaced with [redacted] in every file. File paths are included because they help find
problems (for example a model folder that cannot be written); they may contain your user name.
"""


def _first_line(cmd: list[str]) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return (r.stdout or r.stderr).splitlines()[0].strip() if (r.stdout or r.stderr) else f"exit code {r.returncode}"
    except Exception as e:  # noqa: BLE001
        return f"unavailable ({type(e).__name__}: {e})"


def _system() -> dict:
    from app.config import FFMPEG_BIN, FFPROBE_BIN, DATA_DIR
    from app.main import BUILD_ID
    info = {
        "build": BUILD_ID, "created": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(), "system": platform.system(), "release": platform.release(),
        "machine": platform.machine(), "python": sys.version.split()[0], "python_implementation": platform.python_implementation(),
        "frozen": bool(getattr(sys, "frozen", False)), "cpu_count": os.cpu_count(),
        "ffmpeg": _first_line([FFMPEG_BIN, "-version"]), "ffprobe": _first_line([FFPROBE_BIN, "-version"]),
        "data_dir": str(DATA_DIR),
    }
    try:
        from app.api.video_generation import local_system
        info["hardware"] = local_system()
    except Exception as e:  # noqa: BLE001
        info["hardware"] = {"error": f"{type(e).__name__}: {e}"}
    return info


def _settings(db) -> dict:
    from app.db.models import ProviderProfile
    out: dict = {"providers": [], "environment": {}}
    for p in db.query(ProviderProfile).all():
        out["providers"].append({"name": p.name, "capability": p.capability, "model": p.model,
                                 "base_url": p.base_url, "configured": bool(p.secret_ref)})
    try:
        from app.local_images import settings
        s = settings()
        out["local_images"] = {"folder": s.get("folder"), "autostart": bool(s.get("autostart"))}
    except Exception as e:  # noqa: BLE001
        out["local_images"] = {"error": str(e)}
    for k in sorted(os.environ):
        if SECRET_NAME.search(k) or not k.upper().startswith(ENV_PREFIXES):
            continue
        out["environment"][k] = os.environ[k]
    return out


def _db_counts(db) -> dict:
    counts = {}
    for name in sorted(inspect(db.get_bind()).get_table_names()):
        try:
            counts[name] = db.execute(text(f'SELECT COUNT(*) FROM "{name}"')).scalar()
        except Exception as e:  # noqa: BLE001
            counts[name] = f"error: {type(e).__name__}"
    return counts


def _jobs(db) -> list[dict]:
    from app.db.models import RenderJob
    rows = db.query(RenderJob).order_by(RenderJob.created_at.desc()).limit(20).all()
    return [{"id": j.id, "scope": j.scope, "status": j.status, "stage": j.stage, "progress": j.progress,
             "error": j.error, "created_at": j.created_at.isoformat() if j.created_at else None,
             "updated_at": j.updated_at.isoformat() if j.updated_at else None} for j in rows]


def _secret_values(db) -> list[str]:
    values = set()
    for k, v in os.environ.items():
        if SECRET_NAME.search(k) and v and len(v) >= 8:
            values.add(v)
    from app.db.models import ProviderProfile
    from app.security.secrets import reveal
    for p in db.query(ProviderProfile).all():
        if p.secret_ref:
            values.add(p.secret_ref)
            try:
                v = reveal(p.secret_ref)
                if v and len(v) >= 4:
                    values.add(v)
            except Exception:  # noqa: BLE001 - a locked store just means nothing to scrub beyond the ref
                pass
    return sorted(values, key=len, reverse=True)


def scrub(textval: str, secrets: list[str]) -> str:
    for s in secrets:
        textval = textval.replace(s, "[redacted]")
    return SECRET_SHAPES.sub("[redacted]", textval)


def _log_tail(path) -> str | None:
    try:
        size = path.stat().st_size
        with open(path, "rb") as fh:
            if size > LOG_TAIL_BYTES:
                fh.seek(size - LOG_TAIL_BYTES)
            return fh.read().decode("utf-8", "replace")
    except OSError:
        return None


def build_zip() -> bytes:
    from app.config import LOGS_DIR
    from app.db.database import SessionLocal
    from app.logbuffer import tail
    from app.api.models_admin import list_models
    from app.providers import transcribe
    files: dict[str, str] = {"README.txt": README}
    with SessionLocal() as db:
        secrets = _secret_values(db)
        sections = {
            "system.json": _system,
            "settings.json": lambda: _settings(db),
            "models.json": list_models,
            "whisper_check.json": transcribe.diagnose,
            "database.json": lambda: _db_counts(db),
            "jobs.json": lambda: _jobs(db),
        }
        for name, fn in sections.items():
            try:
                files[name] = json.dumps(fn(), indent=2, default=str)
            except Exception as e:  # noqa: BLE001 - one failing section must not lose the rest
                files[name] = json.dumps({"error": f"{type(e).__name__}: {e}"}, indent=2)
    files["logs/backend-recent.log"] = "\n".join(tail(2000)) + "\n"
    for f in LOG_FILES:
        content = _log_tail(LOGS_DIR / f)
        if content is not None:
            files[f"logs/{f}"] = content
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, content in files.items():
            z.writestr(name, scrub(content, secrets))
    return buf.getvalue()


@router.get("/api/diagnostics.zip")
def diagnostics_zip():
    data = build_zip()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return Response(data, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="SceneForge-diagnostics-{stamp}.zip"',
                             "Cache-Control": "no-store"})
