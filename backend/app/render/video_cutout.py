"""Video subject cutout ("text behind a moving subject").

For a scene whose single shot is a video, every frame the renderer shows is decoded
exactly as render_part decodes it (same -ss/-t, rotation, fps, shot crop and the
cover/contain fit in the source pixel format), so the layer lines up pixel for pixel
with the picture underneath. Per frame:

  1. the AI model (render/cutout.py MODELS, native input size) predicts a matte
     for the visible picture (letterbox bars excluded);
  2. TEMPORAL smoothing: a centred median over the raw mattes of frames i-1, i, i+1
     (no lag for moving subjects, removes single-frame dropouts and pops);
  3. cutout.refine(): guided filter against frame i (edges snap to the current
     frame), speck/hole cleanup, optional edge shift / crisp edges;
  4. motion-gated smoothing: where the picture itself did not change since the
     previous frame, the alpha is blended 40 % with the previous alpha, which
     calms edge shimmer on still parts without dragging moving edges.

The layer is encoded as VP9 with an alpha channel (WebM, yuva420p, decoded with
libvpx-vp9 by overlays.build_overlay_pass) because it is ~10x smaller than
QuickTime Animation for natural footage; if this FFmpeg lacks libvpx-vp9 the layer
falls back to QuickTime Animation (qtrle, ARGB .mov), which every FFmpeg decodes
with alpha.

Limits: one video shot, speed 1.0 (no ramps/freeze), static camera movement, no
parallax/shake/wiggle; at most MAX_FRAMES frames (20 s at 30 fps). Colour looks are
applied to the picture but not to the layer (same as the still-image cutout).
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
import time
from pathlib import Path

from app.render.cutout import MODELS, CutoutError

MAX_SECONDS = 20
MAX_FRAMES = 600
WORK_PIXELS = 1280 * 720
DEFAULT_VIDEO_MODEL = "u2netp"
# ms per 1080p frame (model + refine + encode) measured on a 2-CPU laptop-class VM;
# replaced by the real speed after the first run on this computer.
DEFAULT_MS_PER_FRAME = {"u2netp": 400, "human": 750, "isnet": 1950}

_measured: dict[str, float] = {}
_codec_cache: dict[str, bool] = {}
_run_lock = threading.Lock()


class VideoCutoutError(CutoutError):
    pass


# ---------------------------------------------------------------------------------- planning
def _scene_total_ms(scene) -> int:
    """Same scene length rule as renderer.render_part."""
    from app.render.renderer import DEFAULT_LEAD_MS, DEFAULT_TRAIL_MS, FALLBACK_SCENE_DURATION_MS, _narration_duration_ms
    narration_ms, _ = _narration_duration_ms(scene)
    if scene.timing_mode == "fixed" and scene.requested_duration_ms:
        return int(scene.requested_duration_ms)
    if narration_ms is not None:
        lead = DEFAULT_LEAD_MS if scene.lead_ms is None else scene.lead_ms
        trail = DEFAULT_TRAIL_MS if scene.trail_ms is None else scene.trail_ms
        return int(lead + narration_ms + trail)
    from app.render.media import media_duration_ms
    return int(media_duration_ms(scene) or scene.requested_duration_ms or FALLBACK_SCENE_DURATION_MS)


def plan_for_scene(scene) -> dict:
    """Validate the scene and describe exactly which frames the layer must cover.
    Raises VideoCutoutError with a user-facing message."""
    from app.render.filters import is_static_plan, resolve_motion
    from app.render.ffmpeg_utils import probe
    from app.render.media import selected_shots
    from app.render.renderer import _resolve_asset_path
    shots = selected_shots(scene)
    if not shots:
        raise VideoCutoutError("Add a video to this scene first.")
    shot, look = shots[0], scene.look_json or {}
    if str(getattr(shot.asset.type, "value", shot.asset.type)) != "video":
        raise VideoCutoutError("This scene's media is a still image. Use “Put text behind subject” for images.")
    if len(shots) > 1 or look.get("layout"):
        raise VideoCutoutError(f"Text behind a moving subject needs a scene with one video; this scene shows {len(shots)} media items. Move the others to their own scenes first.")
    sj = shot.speed_json or {}
    if float(sj.get("speed", 1) or 1) != 1.0 or (sj.get("ramp") or "none") != "none":
        raise VideoCutoutError("This clip uses a speed change or speed ramp. The cutout follows the clip at normal speed. Set Speed to 1x with no ramp, then try again.")
    if int(sj.get("freeze_ms", 0) or 0) > 0:
        raise VideoCutoutError("This clip has a freeze frame. Remove the freeze in Speed, then try again.")
    if shot.fit == "cover" and not is_static_plan(resolve_motion(shot.motion_json or {})):
        raise VideoCutoutError("This clip has camera movement (zoom/pan). The cutout layer would drift off the subject. Set Camera movement to Static in the Motion tab, then try again.")
    moving = [label for key, label in (("parallax", "2.5D parallax"), ("wiggle", "wiggle"), ("shake", "camera shake")) if look.get(key)]
    if moving:
        raise VideoCutoutError(f"This scene uses {', '.join(moving)}, which moves the picture under the cutout. Turn it off in Effects, then try again.")
    project = scene.project
    src = _resolve_asset_path(shot.asset)
    if not Path(src).is_file():
        raise VideoCutoutError("This video is missing on disk.")
    info = probe(src)
    fps = int(project.fps)
    in_ms = int(shot.source_in_ms or 0)
    src_ms = int(info.duration_ms or shot.asset.duration_ms or 0)
    scene_ms = _scene_total_ms(scene)
    notes = []
    # The renderer plays the source from in_ms for the whole scene (looping only when the
    # file runs out); the layer covers the first pass.
    used_ms = scene_ms
    if src_ms and src_ms - in_ms < scene_ms:
        used_ms = max(1, src_ms - in_ms)
        notes.append(f"The scene is longer than the clip, so the clip loops; the subject layer covers the first {used_ms / 1000:.1f} s.")
    frames = max(1, round(used_ms / 1000 * fps))
    if frames > MAX_FRAMES or used_ms > MAX_SECONDS * 1000 + 50:
        raise VideoCutoutError(f"This scene shows {used_ms / 1000:.1f} s of video. Text behind a moving subject works on up to {MAX_SECONDS} s "
                               f"({MAX_FRAMES} frames). Trim the clip or split the scene, then try again.")
    crop = shot.crop_json or None
    plan = {"src": src, "content_hash": shot.asset.content_hash, "asset_id": shot.asset.id, "asset_name": shot.asset.original_filename,
            "in_ms": in_ms, "frames": frames, "fps": fps, "fit": shot.fit, "crop": crop, "w": int(project.width), "h": int(project.height),
            "rotation": int(info.rotation or 0), "loop": bool(src_ms and src_ms - in_ms < frames * 1000 / fps), "layer_ms": int(round(frames * 1000 / fps)),
            "notes": notes}
    if scene.effect_preset != "original" or any(look.get(k) for k in ("adjust", "lut", "film", "tone", "wheels", "glitch")):
        notes.append("Colour looks and effects are applied to the picture but not to the cutout layer, so the subject may look slightly different. Check the render.")
    if shot.fit != "cover":
        notes.append("The video is letterboxed (Fit inside frame); the cutout follows the same placement.")
    return plan


def layer_key(plan: dict, model: str, edge: str, shift: int) -> str:
    parts = ["vcut1", plan["content_hash"], plan["in_ms"], plan["frames"], plan["fps"], plan["fit"], json.dumps(plan["crop"], sort_keys=True),
             f"{plan['w']}x{plan['h']}", plan["rotation"], model, edge, shift]
    return hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()


def ms_per_frame(model: str, w: int = 1920, h: int = 1080) -> float:
    """Measured speed on this computer when known, else the built-in estimate (scaled by frame size)."""
    if model in _measured:
        return _measured[model]
    stored = _load_speeds().get(model)
    if stored:
        return float(stored)
    base = DEFAULT_MS_PER_FRAME[model]
    model_part = {"u2netp": 230, "human": 580, "isnet": 1700}[model]
    return model_part + (base - model_part) * (w * h) / (1920 * 1080)


def _speeds_file() -> Path:
    from app.render.cutout import model_dir
    return model_dir() / "video_cutout_speed.json"


def _load_speeds() -> dict:
    try:
        return json.loads(_speeds_file().read_text())
    except Exception:  # noqa: BLE001
        return {}


def _save_speed(model: str, value: float) -> None:
    _measured[model] = value
    try:
        data = _load_speeds()
        data[model] = round(value, 1)
        _speeds_file().parent.mkdir(parents=True, exist_ok=True)
        _speeds_file().write_text(json.dumps(data))
    except Exception:  # noqa: BLE001 - the estimate is best-effort
        pass


# ---------------------------------------------------------------------------------- ffmpeg
def _ff() -> str:
    from app.config import FFMPEG_BIN
    return FFMPEG_BIN


def has_vp9_alpha() -> bool:
    """libvpx-vp9 encoder AND decoder present (the native vp9 decoder drops alpha)."""
    if "vp9" not in _codec_cache:
        try:
            enc = subprocess.run([_ff(), "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=30).stdout
            dec = subprocess.run([_ff(), "-hide_banner", "-decoders"], capture_output=True, text=True, timeout=30).stdout
            _codec_cache["vp9"] = " libvpx-vp9 " in enc and " libvpx-vp9 " in dec
        except Exception:  # noqa: BLE001
            _codec_cache["vp9"] = False
    return _codec_cache["vp9"]


def decode_args(plan: dict) -> tuple[list[str], int]:
    """FFmpeg args producing the shot's frames as the renderer sees them after fitting:
    rgb24 for cover, rgba (transparent letterbox) for contain. Returns (args, channels)."""
    fps, w, h = plan["fps"], plan["w"], plan["h"]
    dur = plan["frames"] / fps
    pre = ""
    rot = plan["rotation"]
    if rot in (90, -90, 270, -270):
        pre = "transpose=1," if rot in (90, -270) else "transpose=2,"
    pre += f"fps={fps},"
    if plan["crop"]:
        c = plan["crop"]
        pre += f"crop=w='max(2,trunc(iw*{c['width']}/2)*2)':h='max(2,trunc(ih*{c['height']}/2)*2)':x='iw*{c['x']}':y='ih*{c['y']}',"
    if plan["fit"] == "cover":
        # filters.build_cover_static_chain, in the source pixel format (same crop rounding), then RGB
        chain, ch = pre + f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},format=rgb24", 3
    else:
        # filters.build_contain_chain foreground: centred; pad rounds x/y like the renderer's yuv420p pad
        chain, ch = pre + (f"scale={w}:{h}:force_original_aspect_ratio=decrease,format=yuva420p,"
                           f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black@0,format=rgba"), 4
    loop = ["-stream_loop", "-1"] if plan["loop"] else []
    args = [_ff(), "-v", "error", "-nostdin", *loop, "-ss", f"{plan['in_ms'] / 1000:.3f}", "-i", plan["src"], "-t", f"{dur:.3f}",
            "-vf", chain, "-frames:v", str(plan["frames"]), "-an", "-f", "rawvideo", "-pix_fmt", "rgb24" if ch == 3 else "rgba", "-"]
    return args, ch


def encode_args(plan: dict, dest: str) -> list[str]:
    head = [_ff(), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{plan['w']}x{plan['h']}", "-r", str(plan["fps"]), "-i", "-"]
    if dest.endswith(".webm"):
        return [*head, "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "24", "-deadline", "realtime", "-cpu-used", "8",
                "-row-mt", "1", "-auto-alt-ref", "0", "-metadata:s:v:0", "alpha_mode=1", dest]
    return [*head, "-c:v", "qtrle", "-pix_fmt", "argb", dest]


# ---------------------------------------------------------------------------------- model
def _drop_other_sessions(keep: str) -> None:
    """Keep at most one model in memory while a long video job runs."""
    from app.render import cutout
    for k in list(cutout._sessions):
        if k != keep:
            cutout._sessions.pop(k, None)


def _session(model: str):
    from app.render import cutout
    path = cutout.ensure_model(model)
    _drop_other_sessions(str(path))
    return cutout._session(model)


def predict_raw(sess, rgb, model: str):
    """Model matte (float32 0..1, model resolution) for an RGB uint8 array.
    Same normalisation as cutout.predict_matte (rembg); the min-max stretch is
    limited so frames without a subject do not blow noise up to full opacity."""
    import cv2
    import numpy as np
    m = MODELS[model]
    s = m["size"]
    x = cv2.resize(rgb, (s, s), interpolation=cv2.INTER_AREA).astype(np.float32)
    x /= max(float(x.max()), 1e-6)
    x = (x - np.array(m["mean"], np.float32)) / np.array(m["std"], np.float32)
    x = np.ascontiguousarray(x.transpose(2, 0, 1)[None])
    pred = sess.run(None, {sess.get_inputs()[0].name: x})[0][0, 0].astype(np.float32)
    lo, hi = float(pred.min()), float(pred.max())
    hi = max(hi, lo + 0.3)
    return np.clip((pred - lo) / (hi - lo), 0, 1)


def _content_box(alpha) -> tuple[int, int, int, int]:
    import numpy as np
    ys, xs = np.nonzero(alpha > 127)
    if not len(xs):
        return 0, 0, alpha.shape[1], alpha.shape[0]
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def build_layer(plan: dict, dest: str, model: str = DEFAULT_VIDEO_MODEL, edge: str = "soft", shift: int = 0,
                progress=None, cancelled=lambda: False, temporal: bool = True) -> dict:
    """Write the frame-sized alpha layer to dest (.webm VP9+alpha or .mov qtrle).
    progress(done, total, ms_per_frame) is called after each frame. Returns stats."""
    import cv2
    import numpy as np
    from PIL import Image
    from app.render.cutout import refine
    if model not in MODELS:
        raise VideoCutoutError(f"Unknown cutout model '{model}'. Choose one of: {', '.join(MODELS)}.")
    sess = _session(model)
    w, h, total = plan["w"], plan["h"], plan["frames"]
    dargs, ch = decode_args(plan)
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    err_dec = open(os.devnull, "wb")
    dec = subprocess.Popen(dargs, stdout=subprocess.PIPE, stderr=err_dec, stdin=subprocess.DEVNULL)
    enc_log = Path(dest).with_suffix(".log")
    enc_err = open(enc_log, "wb")
    enc = subprocess.Popen(encode_args(plan, dest), stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=enc_err)
    frame_bytes = w * h * ch
    dilate = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (17, 17))
    box = None
    window: list = []          # [(frame, valid_alpha, pred)] for i-1, i, i+1
    prev_alpha = prev_gray = None
    done = 0
    t0 = time.perf_counter()

    def read_frame():
        buf = bytearray()
        while len(buf) < frame_bytes:
            chunk = dec.stdout.read(frame_bytes - len(buf))
            if not chunk:
                return None
            buf += chunk
        return np.frombuffer(bytes(buf), np.uint8).reshape(h, w, ch)

    def emit(idx: int):
        nonlocal prev_alpha, prev_gray, done
        frame, valid, pred = window[idx]
        if temporal and len(window) > 1:
            smoothed = np.median(np.stack([p for _, _, p in window]), axis=0) if len(window) == 3 else np.mean(np.stack([p for _, _, p in window]), axis=0)
        else:
            smoothed = pred
        x0, y0, x1, y1 = box
        content = np.ascontiguousarray(frame[y0:y1, x0:x1, :3])
        cw, chh = x1 - x0, y1 - y0
        # Refine at up to ~1280x720 (the model matte is 320-1024 px anyway), then upscale.
        k = min(1.0, (WORK_PIXELS / (cw * chh)) ** 0.5)
        ww, wh = max(2, round(cw * k)), max(2, round(chh * k))
        work = content if k == 1.0 else cv2.resize(content, (ww, wh), interpolation=cv2.INTER_AREA)
        m8 = (cv2.resize(smoothed, (ww, wh), interpolation=cv2.INTER_CUBIC).clip(0, 1) * 255).astype(np.uint8)
        a = np.asarray(refine(Image.fromarray(m8, "L"), edge, 0, image=Image.fromarray(work, "RGB"),
                              shift=int(round(shift * k)) if shift else 0)).astype(np.float32) / 255
        gray = cv2.cvtColor(work, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255
        if temporal and prev_alpha is not None:
            diff = cv2.blur(np.abs(gray - prev_gray), (9, 9))
            still = np.clip(1 - diff / 0.04, 0, 1) * 0.4
            a = a * (1 - still) + prev_alpha * still
        prev_alpha, prev_gray = a, gray
        if k != 1.0:
            a = cv2.resize(a, (cw, chh), interpolation=cv2.INTER_LINEAR)
        alpha = np.zeros((h, w), np.uint8)
        alpha[y0:y1, x0:x1] = (a * 255 + 0.5).astype(np.uint8)
        if valid is not None:
            alpha = np.minimum(alpha, valid)
        keep = cv2.dilate((alpha > 0).astype(np.uint8), dilate)[..., None]
        rgba = np.empty((h, w, 4), np.uint8)
        rgba[..., :3] = frame[..., :3] * keep          # transparent areas black: much smaller file
        rgba[..., 3] = alpha
        enc.stdin.write(rgba.tobytes())
        done += 1
        if progress:
            progress(done, total, (time.perf_counter() - t0) * 1000 / done)

    try:
        while True:
            if cancelled():
                raise VideoCutoutError("cancelled")
            frame = read_frame()
            if frame is None:
                break
            valid = frame[..., 3].copy() if ch == 4 else None
            if box is None:
                box = _content_box(valid) if valid is not None else (0, 0, w, h)
            x0, y0, x1, y1 = box
            pred = predict_raw(sess, np.ascontiguousarray(frame[y0:y1, x0:x1, :3]), model)
            window.append((frame, valid, pred))
            if len(window) == 2 and done == 0:
                emit(0)                                   # first frame: mean of (0, 1)
            elif len(window) == 3:
                emit(1)
                window.pop(0)
        if cancelled():
            raise VideoCutoutError("cancelled")
        if window:
            emit(len(window) - 1 if done else 0)      # last frame: mean of (n-2, n-1)
        if done == 0:
            raise VideoCutoutError("No frames could be read from this video.")
        enc.stdin.close()
        if enc.wait(timeout=600) != 0:
            raise VideoCutoutError("FFmpeg could not write the cutout layer: " + enc_log.read_text(errors="replace")[-400:])
        dec.wait(timeout=60)
    except BaseException:
        for p in (dec, enc):
            try:
                p.kill()
            except Exception:  # noqa: BLE001
                pass
        # Windows keeps the output locked until FFmpeg has really exited (0.9.1: a cancelled
        # cutout crashed here with WinError 32 and the job stayed "running" for ever).
        for p in (dec, enc):
            try:
                p.wait(timeout=15)
            except Exception:  # noqa: BLE001
                pass
        for f in (err_dec, enc_err):
            try:
                f.close()
            except Exception:  # noqa: BLE001
                pass
        safe_unlink(dest)
        raise
    finally:
        for f in (err_dec, enc_err):
            try:
                f.close()
            except Exception:  # noqa: BLE001
                pass
        safe_unlink(enc_log)
        try:
            dec.stdout.close()
        except Exception:  # noqa: BLE001
            pass
    per = (time.perf_counter() - t0) * 1000 / max(done, 1)
    if done >= min(total, 10):
        _save_speed(model, per)
    return {"frames": done, "ms_per_frame": round(per, 1), "codec": "vp9-alpha" if dest.endswith(".webm") else "qtrle"}


def safe_unlink(path) -> None:
    """Delete a temp file without ever raising; retry briefly while Windows still holds it."""
    if not path:
        return
    for attempt in range(6):
        try:
            Path(path).unlink(missing_ok=True)
            return
        except PermissionError:
            time.sleep(0.25 * (attempt + 1))
        except OSError:
            return


# ---------------------------------------------------------------------------------- job
_status: dict[str, dict] = {}


def job_status(job_id: str) -> dict | None:
    return _status.get(job_id)


def running_job_for_scene(scene_id: str) -> str | None:
    for jid, s in _status.items():
        if s.get("scene_id") == scene_id and s["status"] in ("queued", "running", "cancelling"):
            return jid
    return None


def any_running() -> str | None:
    for jid, s in _status.items():
        if s["status"] in ("queued", "running", "cancelling"):
            return jid
    return None


def start_job(job_id: str, scene_id: str, model: str, edge: str, shift: int, frames: int) -> None:
    _status[job_id] = {"job_id": job_id, "scene_id": scene_id, "status": "queued", "frames_done": 0, "frames_total": frames,
                       "ms_per_frame": None, "model": model, "notes": [], "error": None, "stage": "queued"}
    threading.Thread(target=_run_job, args=(job_id, scene_id, model, edge, shift), daemon=True).start()


def _run_job(job_id: str, scene_id: str, model: str, edge: str, shift: int) -> None:
    import uuid
    from app.config import MEDIA_DIR
    from app.db.database import session_scope
    from app.db.models import Asset, RenderJob, Scene
    from app.domain.constants import AssetOrigin, AssetType, JobStatus
    from app.render.renderer import RenderContext, _content_hash_file
    from app.workers import jobs
    ctx = RenderContext()
    with jobs._lock:
        jobs._contexts[job_id] = ctx
        jobs._active_jobs.add(job_id)
    st = _status[job_id]
    dest = None
    try:
        with _run_lock:            # one video cutout at a time (CPU + memory)
            st.update(status="running", stage="loading the model")
            jobs._emit(job_id, {"status": JobStatus.RUNNING, "stage": "loading the cutout model", "progress": 1})
            with session_scope() as db:
                scene = db.get(Scene, scene_id)
                if not scene:
                    raise VideoCutoutError("Scene not found.")
                plan = plan_for_scene(scene)
                project_id = scene.project_id
            key = layer_key(plan, model, edge, shift)
            st.update(frames_total=plan["frames"], notes=plan["notes"])
            ext = ".webm" if has_vp9_alpha() else ".mov"
            folder = Path(MEDIA_DIR) / project_id
            dest = str(folder / f"subject_video_{uuid.uuid4().hex[:10]}{ext}")
            last = {"t": 0.0}

            def progress(done: int, total: int, per: float) -> None:
                st.update(frames_done=done, frames_total=total, ms_per_frame=round(per, 1), stage="cutting out")
                now = time.monotonic()
                if now - last["t"] >= 0.5 or done == total:
                    last["t"] = now
                    left = (total - done) * per / 1000
                    jobs._emit(job_id, {"stage": f"Cutting out frame {done} of {total} · about {left:.0f} s left",
                                        "progress": int(2 + 95 * done / total), "frames_done": done, "frames_total": total})

            stats = build_layer(plan, dest, model, edge, shift, progress=progress, cancelled=lambda: ctx.cancel_requested)
            st.update(ms_per_frame=stats["ms_per_frame"], codec=stats["codec"], stage="saving")
            from app.render.ffmpeg_utils import probe
            info = probe(dest)
            with session_scope() as db:
                scene = db.get(Scene, scene_id)
                if not scene:
                    raise VideoCutoutError("The scene was deleted while cutting out.")
                if layer_key(plan_for_scene(scene), model, edge, shift) != key:
                    raise VideoCutoutError("The scene's clip changed while cutting out. Run the cutout again.")
                asset = Asset(project_id=project_id, type=AssetType.VIDEO, content_hash=_content_hash_file(dest),
                              storage_key=os.path.relpath(dest, MEDIA_DIR), mime="video/webm" if ext == ".webm" else "video/quicktime",
                              original_filename=f"{Path(plan['asset_name'] or 'clip').stem} (subject layer){ext}"[:255],
                              width=plan["w"], height=plan["h"], duration_ms=info.duration_ms or plan["layer_ms"], origin=AssetOrigin.UPLOAD,
                              generation_metadata_json={"subject_video_layer_key": key, "hidden_from_pool": True,
                                                        "subject_video": {"source_asset_id": plan["asset_id"], "model": model, "edge": edge,
                                                                          "shift": shift, "frames": stats["frames"], "codec": stats["codec"],
                                                                          "ms_per_frame": stats["ms_per_frame"]}})
                db.add(asset)
                db.flush()
                apply_overlay(db, scene, asset, plan)
                job = db.get(RenderJob, job_id)
                if job:
                    job.artifact_asset_id = asset.id
                    job.plan_json = {"result_asset_ids": [asset.id], "notes": plan["notes"], **stats}
                st["asset_id"] = asset.id
            dest = None
        st.update(status="succeeded", stage="done")
        jobs._emit(job_id, {"status": JobStatus.SUCCEEDED, "stage": "Subject layer ready", "progress": 100})
    except Exception as exc:  # noqa: BLE001
        safe_unlink(dest)
        cancelled = ctx.cancel_requested
        msg = "Cancelled." if cancelled else (str(exc) if isinstance(exc, CutoutError) else f"Video cutout failed: {exc}")
        if not cancelled and hasattr(exc, "detail"):
            msg = str(exc.detail)
        st.update(status="cancelled" if cancelled else "failed", error=msg, stage="cancelled" if cancelled else "failed")
        jobs._emit(job_id, {"status": JobStatus.CANCELLED if cancelled else JobStatus.FAILED, "stage": st["stage"], "error": msg})
    finally:
        with jobs._lock:
            jobs._contexts.pop(job_id, None)
            jobs._active_jobs.discard(job_id)


def apply_overlay(db, scene, asset, plan: dict) -> list[dict]:
    from app.api.creative import _add_overlay
    overlay = {"id": "subject", "asset_id": asset.id, "kind": "subject", "above_text": True, "x": 50, "y": 50, "width": 100,
               "rotation": 0, "opacity": 100, "radius": 0, "border": 0, "shadow": 0, "start_ms": 0, "end_ms": plan["layer_ms"],
               "anim_in": "none", "anim_out": "none", "anim_ms": 0, "loop": "none"}
    return _add_overlay(db, scene, overlay, replace_kind="subject")
