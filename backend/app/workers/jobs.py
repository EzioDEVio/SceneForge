"""Durable-ish background job runner for M1.

Design notes / honest scope:
  - Jobs run in a daemon thread pool within the same process as the API
    (spec section 7 calls for "a separate native Python process with
    durable DB-backed job claims"; M1 ships the DB-backed job *record*
    and lease/cancel semantics now, but the worker executes in-process
    rather than as a separate OS process — see docs/architecture.md for
    the tracked follow-up). Progress/status/errors are always persisted
    to the render_jobs table, so a restart mid-job leaves a durable
    'running' row an operator can see and requeue; automatic crash
    resume is not yet implemented (also tracked).
  - Real progress: ffmpeg is run with -progress and we translate its
    out_time_ms/frame counters into 0-100 based on the plan's expected
    duration. This is not a simulated/animated bar.
  - Cancellation: cooperative check between ffmpeg invocations *and* a
    hard subprocess-tree kill (SIGKILL / taskkill /T) so no orphan ffmpeg
    process survives a cancel request.
"""
from __future__ import annotations

import queue
import threading
import traceback
from dataclasses import dataclass, field

from app.db.database import session_scope
from app.db.models import Asset, Project, RenderJob, Scene
from app.domain.constants import AssetOrigin, AssetType, JobStatus
from app.render.renderer import RenderContext, render_export, render_part
from app.render.timeline import part_plan_hash

_lock = threading.Lock()
_contexts: dict[str, RenderContext] = {}
_event_queues: dict[str, "queue.Queue"] = {}


def _safe_download_name(title: str) -> str:
    """Turn a project/scene title into a filesystem-safe download filename
    stem (no extension) so 'Download' produces something readable like
    'Part-1.mp4' instead of an opaque UUID."""
    import re as _re
    cleaned = _re.sub(r"[^\w\- ]+", "", title).strip().replace(" ", "-")
    return cleaned or "sceneforge-video"


def _get_queue(job_id: str) -> "queue.Queue":
    with _lock:
        if job_id not in _event_queues:
            _event_queues[job_id] = queue.Queue()
        return _event_queues[job_id]


def _emit(job_id: str, event: dict) -> None:
    _get_queue(job_id).put(event)
    with session_scope() as db:
        job = db.get(RenderJob, job_id)
        if job:
            events = list(job.events_json or [])
            events.append(event)
            job.events_json = events[-200:]  # bounded log
            if "status" in event:
                job.status = event["status"]
            if "stage" in event:
                job.stage = event["stage"]
            if "progress" in event:
                job.progress = event["progress"]
            if "error" in event:
                job.error = event["error"]


def get_events_since(job_id: str) -> list[dict]:
    with session_scope() as db:
        job = db.get(RenderJob, job_id)
        return list(job.events_json or []) if job else []


def subscribe(job_id: str) -> "queue.Queue":
    return _get_queue(job_id)


def request_cancel(job_id: str) -> bool:
    with _lock:
        ctx = _contexts.get(job_id)
    if ctx:
        ctx.cancel_requested = True
        _emit(job_id, {"status": JobStatus.CANCELLING, "stage": "cancelling"})
        return True
    return False


def _run_part_job(job_id: str, project_id: str, scene_id: str) -> None:
    ctx = RenderContext()
    with _lock:
        _contexts[job_id] = ctx
    _emit(job_id, {"status": JobStatus.RUNNING, "stage": "starting", "progress": 1})
    try:
        with session_scope() as db:
            project = db.get(Project, project_id)
            scene = db.get(Scene, scene_id)
            if not project or not scene:
                raise RuntimeError("Project or scene not found")
            # snapshot everything we need while the session is open
            _ = [s.asset for s in scene.shots]
            _ = [t.audio_asset for t in scene.voice_takes]
            db.expunge_all()

        _last_emitted_pct = {"visual": -1}

        def progress_cb(stage: str, pct: int) -> None:
            # FFmpeg's -progress fires many times per second; only emit
            # (and persist to the DB) when the percentage actually moved,
            # so a long render doesn't flood render_jobs with writes.
            if stage == _last_emitted_pct.get("stage") and pct == _last_emitted_pct.get("visual"):
                return
            _last_emitted_pct["stage"] = stage
            _last_emitted_pct["visual"] = pct
            _emit(job_id, {"stage": stage, "progress": pct})

        out_path, total_ms, plan = render_part(scene, project, ctx, progress_cb=progress_cb)

        import os as _os
        from app.config import RENDERS_DIR
        from app.render.renderer import _content_hash_file

        with session_scope() as db:
            asset = Asset(
                project_id=project_id,
                type=AssetType.VIDEO,
                content_hash=_content_hash_file(out_path),
                storage_key=_os.path.relpath(out_path, RENDERS_DIR),
                mime="video/mp4",
                original_filename=_safe_download_name(scene.title or "part") + ".mp4",
                duration_ms=total_ms,
                origin=AssetOrigin.RENDER_OUTPUT,
            )
            db.add(asset)
            db.flush()
            db_scene = db.get(Scene, scene_id)
            db_scene.rendered_plan_hash = plan["combined"]
            db_scene.rendered_asset_id = asset.id
            db_scene.measured_duration_ms = total_ms
            job = db.get(RenderJob, job_id)
            job.artifact_asset_id = asset.id
        for w in ctx.warnings:
            _emit(job_id, {"warning": w})
        _emit(job_id, {"status": JobStatus.SUCCEEDED, "stage": "done", "progress": 100})
    except Exception as exc:  # noqa: BLE001
        status = JobStatus.CANCELLED if ctx.cancel_requested else JobStatus.FAILED
        _emit(job_id, {"status": status, "stage": "error", "error": f"{exc}\n{traceback.format_exc()[-2000:]}"})
    finally:
        with _lock:
            _contexts.pop(job_id, None)


def _run_export_job(job_id: str, project_id: str, selected_ids: list[str] | None = None) -> None:
    ctx = RenderContext()
    with _lock:
        _contexts[job_id] = ctx
    _emit(job_id, {"status": JobStatus.RUNNING, "stage": "checking parts", "progress": 1})
    try:
        from app.config import RENDERS_DIR
        from app.render.timeline import is_stale
        import os as _os

        scene_paths: dict[str, str] = {}
        with session_scope() as db:
            project = db.get(Project, project_id)
            scenes = [s for s in project.scenes if selected_ids is None or s.id in selected_ids]
            canvas = (project.width, project.height)
            stale_scenes = [s for s in scenes if is_stale(s, canvas, project.fps) or not s.rendered_asset_id]
            db.expunge_all()

        n_stale = len(stale_scenes)
        for i, scene_stub in enumerate(stale_scenes):
            if ctx.cancel_check():
                raise RuntimeError("cancelled")
            _emit(job_id, {"stage": f"rendering stale part {i+1}/{n_stale}", "progress": int(5 + 60 * i / max(n_stale, 1))})
            with session_scope() as db:
                project = db.get(Project, project_id)
                scene = db.get(Scene, scene_stub.id)
                _ = [s.asset for s in scene.shots]
                _ = [t.audio_asset for t in scene.voice_takes]
                db.expunge_all()
            out_path, total_ms, plan = render_part(scene, project, ctx)
            with session_scope() as db:
                asset = Asset(
                    project_id=project_id, type=AssetType.VIDEO, content_hash=plan["combined"],
                    storage_key=_os.path.relpath(out_path, RENDERS_DIR), mime="video/mp4",
                    original_filename=_safe_download_name(scene.title or "part") + ".mp4", duration_ms=total_ms,
                    origin=AssetOrigin.RENDER_OUTPUT,
                )
                db.add(asset)
                db.flush()
                db_scene = db.get(Scene, scene_stub.id)
                db_scene.rendered_plan_hash = plan["combined"]
                db_scene.rendered_asset_id = asset.id
                db_scene.measured_duration_ms = total_ms

        with session_scope() as db:
            project = db.get(Project, project_id)
            scenes = [s for s in project.scenes if selected_ids is None or s.id in selected_ids]
            for s in scenes:
                if not s.rendered_asset_id:
                    raise RuntimeError(f"Part '{s.title or s.id}' has no rendered output; generate it first.")
                asset = db.get(Asset, s.rendered_asset_id)
                scene_paths[s.id] = _os.path.join(RENDERS_DIR, asset.storage_key)
            transitions = [s.transition_in_json for s in scenes[1:]]
            canvas = (project.width, project.height)
            db.expunge_all()

        _emit(job_id, {"stage": "compositing export", "progress": 70})
        out_path = render_export(project, scenes, scene_paths, transitions, ctx,
                                  progress_cb=lambda s, p: _emit(job_id, {"stage": s, "progress": 70 + int(p * 0.25)}))

        with session_scope() as db:
            from app.render.ffmpeg_utils import probe as _probe
            from app.render.renderer import _content_hash_file
            info = _probe(out_path)
            asset = Asset(
                project_id=project_id, type=AssetType.VIDEO,
                content_hash=_content_hash_file(out_path), storage_key=_os.path.relpath(out_path, RENDERS_DIR),
                mime="video/mp4", original_filename=_safe_download_name(project.title or "export") + "-export.mp4", duration_ms=info.duration_ms,
                width=info.width, height=info.height, origin=AssetOrigin.RENDER_OUTPUT,
            )
            db.add(asset)
            db.flush()
            job = db.get(RenderJob, job_id)
            job.artifact_asset_id = asset.id
        _emit(job_id, {"status": JobStatus.SUCCEEDED, "stage": "done", "progress": 100})
    except Exception as exc:  # noqa: BLE001
        status = JobStatus.CANCELLED if ctx.cancel_requested else JobStatus.FAILED
        _emit(job_id, {"status": status, "stage": "error", "error": f"{exc}\n{traceback.format_exc()[-2000:]}"})
    finally:
        with _lock:
            _contexts.pop(job_id, None)


def start_part_job(job_id: str, project_id: str, scene_id: str) -> None:
    t = threading.Thread(target=_run_part_job, args=(job_id, project_id, scene_id), daemon=True)
    t.start()


def start_export_job(job_id: str, project_id: str, selected_ids: list[str] | None = None) -> None:
    t = threading.Thread(target=_run_export_job, args=(job_id, project_id, selected_ids), daemon=True)
    t.start()
