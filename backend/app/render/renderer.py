"""Executes render plans with real FFmpeg subprocesses.

Two entry points:
  - render_part(...)   -> one Part/Scene's standalone MP4 (Generate button)
  - render_export(...) -> concatenates current part revisions with
                           inter-part transitions (Export full video)

Both share render_scene_visual/mux_audio_and_captions so preview and export
use the same timeline compiler, per spec section 11.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from app.config import (
    BUNDLED_FONT_PATH,
    DEFAULT_LEAD_MS,
    DEFAULT_TRAIL_MS,
    RENDERS_DIR,
    TMP_DIR,
    X264_CRF,
    X264_PRESET,
)
from app.db.models import Asset, Project, RenderJob, Scene
from app.domain.constants import AssetOrigin, AssetType, TransitionType
from app.render import filters
from app.render.ffmpeg_utils import (
    FFmpegError,
    escape_path_for_filter,
    probe,
    run_ffmpeg,
    terminate_process_tree,
)
from app.render.subtitles import write_ass_file
from app.render.timeline import part_plan_hash
from app.render.typewriter import DEFAULT_KEY, extract_keystroke, reveal_schedule, write_typing_audio
from app.db.database import SessionLocal

FALLBACK_SCENE_DURATION_MS = 4000  # used only when a scene has no narration and no explicit duration


@dataclass
class RenderContext:
    """Mutable state passed to a running job so the API layer can report
    progress/cancel without polling FFmpeg directly."""
    cancel_requested: bool = False
    current_proc_pid: int | None = None
    warnings: list[str] = field(default_factory=list)

    def cancel_check(self) -> bool:
        return self.cancel_requested


def _content_hash_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _resolve_asset_path(asset: Asset) -> str:
    from app.config import MEDIA_DIR, RENDERS_DIR as _RD

    base = _RD if asset.origin == AssetOrigin.RENDER_OUTPUT else MEDIA_DIR
    return str(base / asset.storage_key)


def _register_output_asset(project_id: str, path: str, asset_type: str) -> Asset:
    p = probe(path)
    return Asset(
        project_id=project_id,
        type=asset_type,
        content_hash=_content_hash_file(path),
        storage_key=os.path.relpath(path, RENDERS_DIR),
        mime="video/mp4" if asset_type == AssetType.VIDEO else "audio/wav",
        original_filename=os.path.basename(path),
        width=p.width,
        height=p.height,
        duration_ms=p.duration_ms,
        origin=AssetOrigin.RENDER_OUTPUT,
    )


def _accepted_take(scene: Scene):
    return next((t for t in scene.voice_takes if t.accepted), None)


def _narration_duration_ms(scene: Scene) -> tuple[int | None, str | None]:
    """Returns (duration_ms, audio_path). duration_ms is None if muted."""
    take = _accepted_take(scene)
    if not take or not take.audio_asset:
        return None, None
    audio_path = _resolve_asset_path(take.audio_asset)
    if take.measured_duration_ms:
        return take.measured_duration_ms, audio_path
    p = probe(audio_path)
    return (p.duration_ms or FALLBACK_SCENE_DURATION_MS), audio_path


def _canvas(project: Project) -> tuple[int, int]:
    return project.width, project.height


def render_scene_visual(
    scene: Scene,
    project: Project,
    total_duration_ms: int,
    ctx: RenderContext,
    work_dir: Path,
    progress_cb=None,
) -> str:
    """Render every shot in the scene, concatenate, return path to a
    video-only mp4 spanning exactly total_duration_ms."""
    out_w, out_h = _canvas(project)
    fps = project.fps
    shots = [s for s in scene.shots if s.is_selected] or list(scene.shots)
    if not shots:
        raise FFmpegError(f"Scene {scene.id} has no media shots; add an image or video before generating.")

    n = len(shots)
    explicit_total = sum(s.duration_ms or 0 for s in shots)
    remaining = max(total_duration_ms - explicit_total, 0)
    n_implicit = sum(1 for s in shots if not s.duration_ms)
    per_implicit = remaining // n_implicit if n_implicit else 0

    shot_paths: list[str] = []
    for idx, shot in enumerate(shots):
        if ctx.cancel_check():
            raise FFmpegError("cancelled")
        shot_ms = shot.duration_ms or per_implicit
        if idx == n - 1:
            # absorb integer-division remainder into the last shot so the
            # sum always matches total_duration_ms exactly
            already = sum((s.duration_ms or per_implicit) for s in shots[:-1])
            shot_ms = max(total_duration_ms - already, 1)
        shot_out = str(work_dir / f"shot_{idx}.mp4")

        def shot_progress(pct: int, _idx=idx) -> None:
            if progress_cb:
                # Map this shot's own 0-100% progress into its slice of
                # the overall visual-stage range, so a single long shot
                # still shows real, continuously-moving progress instead
                # of sitting at one number until the whole shot finishes.
                overall = int(100 * (_idx + pct / 100) / n)
                progress_cb("visual", overall)

        _render_single_shot(shot, scene, out_w, out_h, fps, shot_ms, shot_out, ctx, progress_cb=shot_progress)
        shot_paths.append(shot_out)
        if progress_cb:
            progress_cb("visual", int(100 * (idx + 1) / n))

    if len(shot_paths) == 1:
        return shot_paths[0]

    concat_list = work_dir / "concat.txt"
    with open(concat_list, "w", encoding="utf-8") as fh:
        for p in shot_paths:
            fh.write(f"file '{os.path.abspath(p)}'\n")
    concat_out = str(work_dir / "scene_visual.mp4")
    run_ffmpeg(
        ["-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", concat_out],
        cancel_check=ctx.cancel_check,
    )
    return concat_out


def _grade_lut_for(scene: Scene) -> str | None:
    """Bake the scene's colour sliders and imported LUT into one cached LUT."""
    from app.config import PROXIES_DIR
    from app.db.database import SessionLocal
    from app.render.grade import build_grade_lut
    look = scene.look_json or {}
    lut = look.get("lut") or {}
    lut_path = None
    if lut.get("asset_id"):
        # Render workers hold detached scenes, so look the asset up directly.
        with SessionLocal() as db:
            asset = db.get(Asset, lut["asset_id"])
            if asset is None or asset.type != "lut" or asset.project_id != scene.project_id:
                raise FFmpegError("The LUT chosen for this scene is missing. Choose it again in Effects → Color LUT.")
            lut_path = _resolve_asset_path(asset)
        if not Path(lut_path).exists():
            raise FFmpegError("The LUT file for this scene is missing on disk. Import it again in Effects → Color LUT.")
    return build_grade_lut(look.get("adjust"), lut_path, int(lut.get("strength", 100)), Path(PROXIES_DIR) / "grades")


def _render_single_shot(
    shot, scene: Scene, out_w: int, out_h: int, fps: int, duration_ms: int, out_path: str, ctx: RenderContext,
    progress_cb=None,
) -> None:
    asset = shot.asset
    src_path = _resolve_asset_path(asset)
    duration_s = max(duration_ms / 1000.0, 1 / fps)
    total_frames = max(round(duration_s * fps), 1)

    input_args: list[str] = []
    pre_filters = ""

    if asset.type == AssetType.IMAGE:
        input_args = ["-loop", "1", "-framerate", str(fps), "-t", f"{duration_s:.3f}", "-i", src_path]
    else:
        p = probe(src_path)
        src_dur_ms = p.duration_ms or duration_ms
        in_ms = shot.source_in_ms or 0
        needs_loop = (src_dur_ms - in_ms) < duration_ms
        if needs_loop:
            input_args = ["-stream_loop", "-1", "-ss", f"{in_ms/1000:.3f}", "-i", src_path, "-t", f"{duration_s:.3f}"]
        else:
            input_args = ["-ss", f"{in_ms/1000:.3f}", "-i", src_path, "-t", f"{duration_s:.3f}"]
        if p.rotation in (90, -90, 270, -270):
            pre_filters = "transpose=1," if p.rotation in (90, -270) else "transpose=2,"
        pre_filters += f"fps={fps},"

    if shot.crop_json:
        c = shot.crop_json
        pre_filters += f"crop=w='max(2,trunc(iw*{c['width']}/2)*2)':h='max(2,trunc(ih*{c['height']}/2)*2)':x='iw*{c['x']}':y='ih*{c['y']}',"

    graph, warning = filters.build_shot_video_chain(
        fit=shot.fit,
        motion_json=shot.motion_json,
        out_w=out_w,
        out_h=out_h,
        fps=fps,
        total_frames=total_frames,
        effect_preset=scene.effect_preset,
        effect_intensity=int(scene.effect_intensity),
        look=scene.look_json or {},
        grade_lut_path=_grade_lut_for(scene),
    )
    if pre_filters:
        # prepend a normalization stage (fps/rotation) onto the graph's input
        graph = f"[0:v]{pre_filters.rstrip(',')}[pre];" + graph.replace("[0:v]", "[pre]", 1)
    if warning:
        ctx.warnings.append(f"scene {scene.id} shot {shot.id}: {warning}")

    args = [*input_args, "-filter_complex", graph, "-map", "[vout]", "-an",
            "-r", str(fps), "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", X264_PRESET, "-crf", X264_CRF,
            out_path]

    def on_ffmpeg_progress(key: str, value: str) -> None:
        # ffmpeg's -progress output reports out_time_ms as MICROSECONDS
        # (a long-standing naming quirk) — convert to seconds and compare
        # against this shot's target duration for a real percentage, not
        # a guess.
        if not progress_cb or key != "out_time_ms":
            return
        try:
            elapsed_s = int(value) / 1_000_000
        except ValueError:
            return
        pct = max(0, min(100, int(100 * elapsed_s / duration_s)))
        progress_cb(pct)

    run_ffmpeg(args, cancel_check=ctx.cancel_check, on_progress=on_ffmpeg_progress)


def mux_audio_and_captions(
    scene: Scene,
    project: Project,
    visual_path: str,
    total_duration_ms: int,
    narration_path: str | None,
    lead_ms: int,
    work_dir: Path,
    ctx: RenderContext,
) -> str:
    out_w, out_h = _canvas(project)
    captioned_path = visual_path
    if (scene.font_json.get("captions_enabled", True) and scene.subtitle_text.strip()) or scene.font_json.get("layers"):
        ass_path = write_ass_file(
            scene.id, scene.subtitle_text if scene.font_json.get("captions_enabled", True) else "", total_duration_ms, scene.font_json, out_w, out_h,
            out_path=str(work_dir / f"{scene.id}_captions.ass"),
            typewriter=bool(scene.font_json.get("typewriter", False)),
        )
        fonts_dir = escape_path_for_filter(str(BUNDLED_FONT_PATH.parent))
        ass_escaped = escape_path_for_filter(ass_path)
        captioned_path = str(work_dir / "scene_captioned.mp4")
        run_ffmpeg(
            [
                "-i", visual_path,
                "-vf", f"ass='{ass_escaped}':fontsdir='{fonts_dir}'",
                "-c:v", "libx264", "-preset", X264_PRESET, "-crf", X264_CRF, "-pix_fmt", "yuv420p",
                captioned_path,
            ],
            cancel_check=ctx.cancel_check,
        )

    typing_path = None
    font = scene.font_json
    if font.get('typewriter_sound', False) and font.get('typewriter', False) and font.get('captions_enabled', True) and scene.subtitle_text.strip():
        key_path = DEFAULT_KEY
        sound_id = font.get('typewriter_sound_asset_id')
        if sound_id:
            # Render workers detach scene snapshots before running FFmpeg.
            with SessionLocal() as db:
                sound = db.get(Asset, sound_id)
                if sound: db.expunge(sound)
            if not sound or sound.project_id != scene.project_id or sound.type != AssetType.AUDIO:
                raise ValueError('The selected typewriter sound is unavailable. Select another sound in Text.')
            decoded = str(work_dir / 'typing_source.wav')
            run_ffmpeg(['-i', _resolve_asset_path(sound), '-t', '30', '-ac', '1', '-ar', '48000', '-c:a', 'pcm_s16le', decoded], cancel_check=ctx.cancel_check)
            key_path = extract_keystroke(decoded, work_dir / 'typing_key.wav')
        schedule = reveal_schedule(scene.subtitle_text, total_duration_ms, font)
        typing_path = write_typing_audio(schedule, total_duration_ms, key_path, work_dir / 'typing.wav', float(font.get('typewriter_volume', 50)) / 100)

    final_path = str(work_dir / "part_final.mp4")
    total_s = total_duration_ms / 1000.0
    if typing_path:
        if narration_path:
            inputs = ['-i', captioned_path, '-i', narration_path, '-i', typing_path]
            graph = (f'[1:a]adelay={lead_ms}|{lead_ms},apad,atrim=duration={total_s:.3f}[voice];'
                     f'[2:a]apad,atrim=duration={total_s:.3f}[keys];'
                     '[voice][keys]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95:latency=1[aout]')
            args = [*inputs, '-filter_complex', graph, '-map', '0:v', '-map', '[aout]']
        else:
            args = ['-i', captioned_path, '-i', typing_path, '-map', '0:v', '-map', '1:a']
        args += ['-t', f'{total_s:.3f}', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', final_path]
    elif narration_path:
        trail_s = max(total_s - (lead_ms / 1000.0), 0)
        args = [
            "-i", captioned_path,
            "-i", narration_path,
            "-filter_complex",
            f"[1:a]adelay={lead_ms}|{lead_ms},apad=whole_dur={trail_s:.3f}[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-t", f"{total_s:.3f}",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            final_path,
        ]
    else:
        args = [
            "-i", captioned_path,
            "-f", "lavfi", "-t", f"{total_s:.3f}", "-i", "anullsrc=r=48000:cl=stereo",
            "-map", "0:v", "-map", "1:a",
            "-t", f"{total_s:.3f}",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
            final_path,
        ]
    run_ffmpeg(args, cancel_check=ctx.cancel_check)
    return final_path


def render_part(
    scene: Scene,
    project: Project,
    ctx: RenderContext,
    progress_cb=None,
) -> tuple[str, int, dict]:
    """Renders one part end-to-end. Returns (output_path, total_duration_ms, plan_hashes)."""
    work_dir = Path(TMP_DIR) / f"part_{scene.id}_{uuid.uuid4().hex[:8]}"
    work_dir.mkdir(parents=True, exist_ok=True)
    try:
        narration_ms, narration_path = _narration_duration_ms(scene)
        lead_ms, trail_ms = scene.lead_ms or DEFAULT_LEAD_MS, scene.trail_ms or DEFAULT_TRAIL_MS
        if scene.timing_mode == "fixed" and scene.requested_duration_ms:
            # User explicitly chose a clip duration — this takes priority
            # over narration length. If narration is present it is muxed
            # in as normal (trimmed if longer than the fixed duration,
            # silence-padded if shorter); if there's no narration this is
            # simply a silent clip of the requested length.
            total_ms = scene.requested_duration_ms
            if narration_ms is None:
                lead_ms = 0
        elif narration_ms is not None:
            total_ms = lead_ms + narration_ms + trail_ms
        else:
            total_ms = scene.requested_duration_ms or FALLBACK_SCENE_DURATION_MS
            lead_ms = 0

        if progress_cb:
            progress_cb("visual", 0)
        visual_path = render_scene_visual(scene, project, total_ms, ctx, work_dir, progress_cb)
        if progress_cb:
            progress_cb("captions_audio", 50)
        final_path = mux_audio_and_captions(
            scene, project, visual_path, total_ms, narration_path, lead_ms, work_dir, ctx
        )
        if progress_cb:
            progress_cb("finalize", 90)

        # Validate before publishing (spec: never mark success until the
        # output can be probed and decoded).
        p = probe(final_path)
        if not p.has_video or p.duration_ms is None:
            raise FFmpegError("Rendered part failed validation: no decodable video stream.")

        dest_dir = Path(RENDERS_DIR) / "parts"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / f"{scene.id}_{uuid.uuid4().hex[:8]}.mp4"
        shutil.move(final_path, dest_path)

        plan = part_plan_hash(scene, _canvas(project), project.fps)
        if progress_cb:
            progress_cb("done", 100)
        return str(dest_path), total_ms, plan
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Full export with inter-part transitions
# ---------------------------------------------------------------------------

def render_export(
    project: Project,
    scenes: list[Scene],
    scene_paths: dict[str, str],
    transitions: list[dict],
    ctx: RenderContext,
    progress_cb=None,
) -> str:
    """Concatenate rendered parts (scene_paths[scene.id]) honoring
    per-boundary transitions ('cut' | 'dissolve' | 'fade_through_black').
    Dissolve/fade consume only the silent lead/trail handles baked into
    each part, so narration audio is never overlapped (spec section 11)."""
    work_dir = Path(TMP_DIR) / f"export_{project.id}_{uuid.uuid4().hex[:8]}"
    work_dir.mkdir(parents=True, exist_ok=True)
    try:
        paths = [scene_paths[s.id] for s in scenes]
        durations = [probe(p).duration_ms or 0 for p in paths]

        if all(t.get("type", TransitionType.CUT) == TransitionType.CUT for t in transitions):
            # Decode AAC before concatenation: MP4 stream-copy accumulates padding.
            inputs, graph, pads = [], [], []
            for i, path in enumerate(paths):
                inputs += ['-i', path]
                seconds = durations[i] / 1000.0
                graph += [f'[{i}:v]scale={project.width}:{project.height},setsar=1,fps={project.fps},format=yuv420p,trim=duration={seconds:.3f},setpts=PTS-STARTPTS[v{i}]',
                          f'[{i}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,apad,atrim=duration={seconds:.3f},asetpts=PTS-STARTPTS[a{i}]']
                pads += [f'[v{i}][a{i}]']
            graph.append(''.join(pads) + f'concat=n={len(paths)}:v=1:a=1[vout][aout]')
            out_path = str(Path(RENDERS_DIR) / f"export_{project.id}_{uuid.uuid4().hex[:8]}.mp4")
            run_ffmpeg([*inputs, '-filter_complex', ';'.join(graph), '-map', '[vout]', '-map', '[aout]',
                        '-c:v', 'libx264', '-preset', X264_PRESET, '-crf', X264_CRF, '-pix_fmt', 'yuv420p',
                        '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', out_path], cancel_check=ctx.cancel_check)
            if progress_cb: progress_cb('export', 100)
            return out_path

        # Build a sequential xfade/acrossfade chain.
        inputs: list[str] = []
        for p in paths:
            inputs += ["-i", p]

        # Normalize every input's timebase before concat/xfade, and
        # re-normalize after every stage too. `concat` unconditionally
        # rewrites its output timebase to 1/1000000 regardless of what its
        # inputs used; `settb=AVTB` on a raw input instead resolves to
        # something derived from the input's own rate (e.g. 1/30), so a
        # concat-then-xfade chain still mismatches one stage later. Forcing
        # the *exact* numeric 1/1000000 timebase at every pad (inputs and
        # every intermediate output) sidesteps the ambiguity entirely.
        TB = "1000000"
        filter_parts: list[str] = []
        for idx in range(len(paths)):
            filter_parts.append(f"[{idx}:v]fps={project.fps},settb=1/{TB}[vn{idx}]")
            filter_parts.append(f"[{idx}:a]asettb=1/{TB}[an{idx}]")

        v_label = "vn0"
        a_label = "an0"
        cumulative_ms = durations[0]
        for i in range(1, len(paths)):
            tr = transitions[i - 1] if i - 1 < len(transitions) else {"type": TransitionType.CUT, "duration_ms": 0}
            ttype = tr.get("type", TransitionType.CUT)
            dur_ms = min(tr.get("duration_ms", 0), durations[i - 1] // 2, durations[i] // 2) if ttype != TransitionType.CUT else 0
            dur_s = dur_ms / 1000.0
            offset_s = max((cumulative_ms - dur_ms) / 1000.0, 0)
            vraw, araw = f"v{i}raw", f"a{i}raw"
            vout, aout = f"v{i}", f"a{i}"
            vnext, anext = f"vn{i}", f"an{i}"
            xfade_transition = {
                "fade_through_black": "fadeblack", "dissolve": "dissolve", "slide": "slideleft",
                "slide_right": "slideright", "wipe_left": "wipeleft", "wipe_right": "wiperight",
                "fade_white": "fadewhite", "circle_open": "circleopen",
            }.get(ttype, "fade")
            if dur_ms <= 0:
                filter_parts.append(f"[{v_label}][{vnext}]concat=n=2:v=1:a=0[{vraw}]")
                filter_parts.append(f"[{a_label}][{anext}]concat=n=2:v=0:a=1[{araw}]")
            else:
                filter_parts.append(
                    f"[{v_label}][{vnext}]xfade=transition={xfade_transition}:duration={dur_s:.3f}:offset={offset_s:.3f}[{vraw}]"
                )
                filter_parts.append(
                    f"[{a_label}][{anext}]acrossfade=d={dur_s:.3f}[{araw}]"
                )
            # re-pin the timebase after every stage so the NEXT stage never
            # inherits whatever timebase concat/xfade chose internally.
            filter_parts.append(f"[{vraw}]settb=1/{TB}[{vout}]")
            filter_parts.append(f"[{araw}]asettb=1/{TB}[{aout}]")
            v_label, a_label = vout, aout
            cumulative_ms = cumulative_ms - dur_ms + durations[i]

        graph = ";".join(filter_parts)
        out_path = str(Path(RENDERS_DIR) / f"export_{project.id}_{uuid.uuid4().hex[:8]}.mp4")
        args = [
            *inputs,
            "-filter_complex", graph,
            "-map", f"[{v_label}]", "-map", f"[{a_label}]",
            "-c:v", "libx264", "-preset", X264_PRESET, "-crf", X264_CRF,
            "-c:a", "aac", "-b:a", "192k",
            out_path,
        ]
        run_ffmpeg(args, cancel_check=ctx.cancel_check)
        if progress_cb:
            progress_cb("export", 100)
        return out_path
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def cancel_running(ctx: RenderContext) -> None:
    ctx.cancel_requested = True
