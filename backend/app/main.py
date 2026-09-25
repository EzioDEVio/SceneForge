from __future__ import annotations

from pathlib import Path
import os
from app.config import RESOURCE_DIR
from app.security.desktop import DesktopSessionMiddleware

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import assets, images, projects, providers, render, scenes, voice, local_speech
from app.db.database import init_db, SessionLocal
from app.db.models import ProviderProfile
from app.security.secrets import migrate_credentials

app = FastAPI(title="SceneForge Studio API", version="0.1.0-m1")

# Local-first: bind loopback by default (see scripts/start.*), but still
# validate allowed origins rather than treating "runs on localhost" alone
# as a security boundary.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.add_middleware(DesktopSessionMiddleware,token=os.environ.get("SCENEFORGE_DESKTOP_TOKEN", ""))

@app.on_event("startup")
def on_startup():
    init_db()
    app.state.credential_migration_failures = migrate_credentials()
    import os,threading
    if os.name=='nt' and os.environ.get('SCENEFORGE_SD_AUTOSTART')!='0':
        from app.local_images import start, settings
        if settings()['autostart']:
            threading.Thread(target=start,daemon=True).start()


app.include_router(projects.router)
app.include_router(scenes.router)
app.include_router(assets.router)
app.include_router(voice.router)
app.include_router(render.router)
app.include_router(providers.router)
app.include_router(images.router)
app.include_router(local_speech.router)


# Must match BUILD_ID in frontend/src/api.ts. Bump on any API change so a
# new interface connected to an old backend (e.g. a still-running old
# start.bat window) shows "Backend update required" instead of silently
# losing settings the old backend does not know.
BUILD_ID = "rc5-effects-6"


@app.get("/api/health")
def health():
    return {"status": "ok", "build": BUILD_ID, "credential_warning": 'Some saved credentials could not be secured. Unlock your OS credential store, restart, or re-enter the keys in Settings.' if getattr(app.state,'credential_migration_failures',0) else '', "features": ["local_speech", "combined_effects"]}


@app.get('/api/close-status')
def close_status():
    from app.db.models import RenderJob
    with SessionLocal() as db:
        active = db.query(RenderJob).filter(RenderJob.status.in_(['queued','running','cancelling'])).count()
    return {'ready': active == 0}


# Serve the built frontend (npm run build -> frontend/dist) from the same
# origin as the API, per spec section 7. In dev, run Vite separately
# (scripts/dev.*) instead — this mount is a no-op until dist/ exists.
_frontend_dist = RESOURCE_DIR / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")

@app.on_event("shutdown")
def stop_owned_image_engine():
    from app.local_images import stop
    stop()
