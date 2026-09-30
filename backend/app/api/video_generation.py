"""Text-to-video generation catalog, local workflow setup and job creation."""
from __future__ import annotations

import os
import ctypes
import subprocess
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Project, ProviderProfile, RenderJob
from app.domain import schemas
from app.domain.constants import JobStatus
from app.providers import video_generation as video
from app.security.secrets import reveal
from app.workers import jobs as job_worker

router = APIRouter(prefix="/api/video-generation", tags=["video-generation"])


@router.get("/catalog")
def get_catalog():
    return {"models": video.catalog(), "prices_checked": "2026-09-29"}


@router.get("/local/status")
def local_status(db: Session = Depends(get_db)):
    profile = db.query(ProviderProfile).filter(ProviderProfile.capability == "video", ProviderProfile.name == "local_comfy").first()
    if not profile:
        return {"ready": False, "message": "Connect local ComfyUI in Settings → Providers."}
    try:
        return video.local_comfy_status(profile.base_url or "http://127.0.0.1:8188")
    except video.VideoGenerationError as exc:
        raise HTTPException(400, str(exc))


@router.get("/local/system")
def local_system():
    """Return optional NVIDIA GPU and RAM details to tailor local model guidance."""
    system_ram_gb = None
    try:
        if os.name == "nt":
            class MemoryStatusEx(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            memory = MemoryStatusEx()
            memory.dwLength = ctypes.sizeof(memory)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
                system_ram_gb = round(memory.ullTotalPhys / (1024 ** 3), 1)
        else:
            system_ram_gb = round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / (1024 ** 3), 1)
    except (AttributeError, OSError, ValueError):
        pass
    try:
        command = ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=4, check=False)
        except FileNotFoundError:
            # NVIDIA's Windows installer may not add the standard NVSMI path to PATH.
            nvsmis = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "NVIDIA Corporation" / "NVSMI" / "nvidia-smi.exe"
            if os.name != "nt" or not nvsmis.is_file():
                raise
            result = subprocess.run([str(nvsmis), *command[1:]], capture_output=True, text=True, timeout=4, check=False)
        detected_gpus = []
        for line in result.stdout.splitlines():
            try:
                name, memory = (part.strip() for part in line.split(",", 1))
                detected_gpus.append((name, int(float(memory))))
            except (ValueError, TypeError):
                continue
        if not detected_gpus:
            raise ValueError("No NVIDIA GPU details were returned")
        name, vram_mb = max(detected_gpus, key=lambda item: item[1])
        vram_gb = round(vram_mb / 1024, 1)
        if vram_gb >= 32.0 and system_ram_gb is not None and system_ram_gb >= 32.0:
            recommended = ["ltx-2.5-fast", "wan2.2-ti2v-5b", "wan2.1-t2v-1.3b"]
            note = "This computer meets LTX-2.5's listed VRAM and system-RAM minimums. Wan 2.2 5B remains a lighter first test."
        elif vram_gb >= 8.0:
            recommended = ["wan2.2-ti2v-5b", "wan2.1-t2v-1.3b"]
            note = "Wan 2.2 TI2V 5B is a reasonable first test. Choose 480p and use ComfyUI native offloading if memory is tight."
        else:
            recommended = ["wan2.1-t2v-1.3b"]
            note = "This GPU is below the listed 8 GB VRAM guidance for the Wan workflows. The 1.3B workflow is the lightest option but may still run out of memory."
        return {"detected": True, "gpu_name": name, "vram_gb": vram_gb,
                "system_ram_gb": system_ram_gb, "gpu_count": len(detected_gpus),
                "recommended_model_ids": recommended, "message": note}
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return {"detected": False, "gpu_name": None, "vram_gb": None,
                "system_ram_gb": system_ram_gb, "gpu_count": 0,
                "recommended_model_ids": ["wan2.1-t2v-1.3b"],
                "message": "GPU memory could not be detected automatically. SceneForge cannot verify whether a local model fits this computer; start with the lightest workflow and check its requirements before downloading it."}


@router.post("/local/workflows/{model_id}")
async def import_local_workflow(model_id: str, file: UploadFile = File(...)):
    try:
        path = video.workflow_path(model_id)
    except video.VideoGenerationError as exc:
        raise HTTPException(404, str(exc))
    if Path(file.filename or "").suffix.lower() != ".json":
        raise HTTPException(400, "Choose the ComfyUI workflow JSON file saved using Save (API Format).")
    raw = await file.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        raise HTTPException(413, "Workflow files must be 2 MB or smaller.")
    try:
        graph = video.parse_workflow(raw)
    except video.VideoGenerationError as exc:
        raise HTTPException(400, str(exc))
    # Store the normalized API graph only. No client filename becomes a path.
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(__import__("json").dumps(graph, ensure_ascii=False), encoding="utf-8")
    os.replace(temp, path)
    return {"ok": True, "model_id": model_id, "node_count": len(graph)}


@router.post("/projects/{project_id}/generate", response_model=schemas.JobCreateResponse)
def start_video_generation(project_id: str, body: schemas.GenerateVideoRequest, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    try:
        model, width, height = video.validate_request(body.model_dump())
    except video.VideoGenerationError as exc:
        raise HTTPException(400, str(exc))
    if body.provider != "local_comfy" and not body.confirm_paid:
        raise HTTPException(400, "Confirm the displayed provider cost estimate before starting this paid generation.")
    profile = db.query(ProviderProfile).filter(
        ProviderProfile.capability == "video", ProviderProfile.name == body.provider
    ).first()
    if not profile:
        label = {"local_comfy": "Local ComfyUI", "google_veo": "Google Veo", "runway": "Runway"}[body.provider]
        raise HTTPException(400, f"Connect {label} in Settings → Providers first.")
    if body.provider == "local_comfy":
        try:
            video.validate_local_comfy_url(profile.base_url)
            if not video.workflow_path(model["id"]).is_file():
                raise video.VideoGenerationError(f"Import the {model['name']} ComfyUI API workflow first.")
        except video.VideoGenerationError as exc:
            raise HTTPException(400, str(exc))
    else:
        try:
            if not reveal(profile.secret_ref or "").strip():
                raise ValueError("empty credential")
        except Exception:
            raise HTTPException(400, "The saved provider key is unavailable. Re-enter it in Settings → Providers.")

    cost = video.estimate_cost(model, body.duration_seconds, body.resolution)
    if cost.get("usd") is not None:
        cost["usd"] = round(cost["usd"] * body.candidate_count, 4)
    if cost.get("credits") is not None:
        cost["credits"] = round(cost["credits"] * body.candidate_count, 2)
    cost["candidate_count"] = body.candidate_count
    job = RenderJob(
        project_id=project_id,
        scene_id=None,
        scope="video_generation",
        status=JobStatus.QUEUED,
        plan_json={"provider": body.provider, "model": body.model, "cost_estimate": cost},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    job_worker.start_video_generation_job(job.id, project_id, body.model_dump())
    return {"job_id": job.id}
