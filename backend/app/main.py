from __future__ import annotations

from pathlib import Path
import os
from app.config import RESOURCE_DIR
from app.security.desktop import DesktopSessionMiddleware

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import assets, images, projects, providers, render, scenes, voice, local_speech
from app.db.database import init_db

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
    import os,threading
    if os.name=='nt' and os.environ.get('SCENEFORGE_SD_AUTOSTART')!='0':
        from app.local_images import start
        threading.Thread(target=start,daemon=True).start()


app.include_router(projects.router)
app.include_router(scenes.router)
app.include_router(assets.router)
app.include_router(voice.router)
app.include_router(render.router)
app.include_router(providers.router)
app.include_router(images.router)
app.include_router(local_speech.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "build": "workspace-2.5", "features": ["local_speech", "combined_effects"]}


# Serve the built frontend (npm run build -> frontend/dist) from the same
# origin as the API, per spec section 7. In dev, run Vite separately
# (scripts/dev.*) instead — this mount is a no-op until dist/ exists.
_frontend_dist = RESOURCE_DIR / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
