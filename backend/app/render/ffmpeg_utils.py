"""Safe FFmpeg/FFprobe subprocess wrappers.

Security note (spec section 13): every invocation below builds an argument
*array* — never a shell string — so user-supplied filenames, scene text or
filter parameters cannot break out into shell metacharacters. Text that is
interpolated into FFmpeg *filter* strings (drawtext/ass paths, force_style)
is escaped with `escape_filter_value` / `escape_path_for_filter`.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
from dataclasses import dataclass

from app.config import FFMPEG_BIN, FFPROBE_BIN


class FFmpegError(RuntimeError):
    def __init__(self, message: str, stderr: str = ""):
        super().__init__(message + ("\nFFmpeg diagnostic:\n" + stderr[-3000:] if stderr else ""))
        self.stderr = stderr


@dataclass
class ProbeResult:
    duration_ms: int | None
    width: int | None
    height: int | None
    has_audio: bool
    has_video: bool
    fps: float | None
    rotation: int
    is_vfr: bool
    raw: dict


def probe(path: str) -> ProbeResult:
    args = [
        FFPROBE_BIN,
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        path,
    ]
    try:
        proc = subprocess.run(args, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise FFmpegError(
            f"'{FFPROBE_BIN}' was not found on PATH. Install FFmpeg "
            "(https://www.gyan.dev/ffmpeg/builds/) and add its bin folder to PATH."
        ) from exc
    if proc.returncode != 0:
        raise FFmpegError(f"ffprobe failed for {path}", proc.stderr)
    data = json.loads(proc.stdout or "{}")

    fmt = data.get("format", {})
    duration_ms = None
    if fmt.get("duration"):
        duration_ms = int(round(float(fmt["duration"]) * 1000))

    width = height = None
    has_audio = has_video = False
    fps = None
    rotation = 0
    is_vfr = False

    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video" and not has_video:
            has_video = True
            width = stream.get("width")
            height = stream.get("height")
            avg = stream.get("avg_frame_rate", "0/1")
            r_rate = stream.get("r_frame_rate", "0/1")
            try:
                num, den = avg.split("/")
                fps = float(num) / float(den) if float(den) != 0 else None
            except Exception:
                fps = None
            if avg != r_rate:
                is_vfr = True
            for side in stream.get("side_data_list", []) or []:
                if "rotation" in side:
                    rotation = int(side["rotation"])
            tags = stream.get("tags", {}) or {}
            if "rotate" in tags:
                try:
                    rotation = int(tags["rotate"])
                except ValueError:
                    pass
            if duration_ms is None and stream.get("duration"):
                duration_ms = int(round(float(stream["duration"]) * 1000))
        if stream.get("codec_type") == "audio":
            has_audio = True
            if duration_ms is None and stream.get("duration"):
                duration_ms = int(round(float(stream["duration"]) * 1000))

    return ProbeResult(
        duration_ms=duration_ms,
        width=width,
        height=height,
        has_audio=has_audio,
        has_video=has_video,
        fps=fps,
        rotation=rotation,
        is_vfr=is_vfr,
        raw=data,
    )


def run_ffmpeg(
    args: list[str],
    log_path: str | None = None,
    on_progress=None,
    cancel_check=None,
) -> None:
    """Run ffmpeg with -progress piped to stdout so we can report real,
    stage-accurate progress (not a simulated bar). `args` must NOT include
    the leading binary name or `-progress` — this wrapper adds both.

    stderr is ALWAYS redirected to a file (never PIPE-and-ignored): ffmpeg
    can write more than a pipe's OS buffer (~64KB) to stderr (warnings,
    filter graph diagnostics), and if that pipe is never drained while we
    only read stdout, the process blocks on write() forever. That exact
    deadlock was hit during development with a filter graph that produced
    verbose per-frame diagnostics; routing stderr to a file sidesteps it
    unconditionally rather than relying on remembering to drain it.
    """
    import tempfile

    full_args = [
        FFMPEG_BIN,
        "-y",
        "-hide_banner",
        "-nostdin",
        "-filter_threads", "1", "-filter_complex_threads", "1",
        "-progress", "pipe:1",
        "-loglevel", "error",
        *args,
    ]
    owns_log_file = log_path is None
    if owns_log_file:
        fd, log_path = tempfile.mkstemp(prefix="ffmpeg_stderr_", suffix=".log")
        import os as _os
        _os.close(fd)
    stderr_fh = open(log_path, "w", encoding="utf-8")
    try:
        creationflags = 0
        preexec_fn = None
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        else:
            preexec_fn = os.setsid

        try:
            proc = subprocess.Popen(
                full_args,
                stdout=subprocess.PIPE,
                stderr=stderr_fh,
                text=True,
                bufsize=1,
                preexec_fn=preexec_fn,
                creationflags=creationflags,
            )
        except FileNotFoundError as exc:
            raise FFmpegError(
                f"'{FFMPEG_BIN}' was not found on PATH. Install FFmpeg "
                "(https://www.gyan.dev/ffmpeg/builds/) and add its bin folder to PATH."
            ) from exc
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                if cancel_check and cancel_check():
                    terminate_process_tree(proc)
                    raise FFmpegError("cancelled")
                line = line.strip()
                if "=" in line and on_progress:
                    key, _, value = line.partition("=")
                    on_progress(key, value)
            proc.wait()
        finally:
            pass
        if proc.returncode not in (0, None):
            stderr_fh.flush()
            stderr_text = open(log_path, encoding="utf-8", errors="replace").read()
            raise FFmpegError(f"ffmpeg exited with code {proc.returncode}", stderr_text)
    finally:
        stderr_fh.close()
        if owns_log_file:
            try:
                os.remove(log_path)
            except OSError:
                pass


def terminate_process_tree(proc: subprocess.Popen) -> None:
    """Cross-platform: kill ffmpeg and any children so cancellation never
    leaves an orphaned encoder running (spec section 11)."""
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
            )
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def escape_filter_value(text: str) -> str:
    """Escape a value used inside an ffmpeg filtergraph option, e.g.
    drawtext text= or ass force_style. FFmpeg filter escaping rules:
    backslash, single quote, and colon are special inside filter args."""
    return (
        text.replace("\\", "\\\\\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
    )


def escape_path_for_filter(path: str) -> str:
    """Escape a filesystem path for use as an ffmpeg filter argument
    (subtitles=filename, ass=filename). Colons and backslashes (Windows
    drive letters / separators) must be escaped or the filter parser
    misreads them as option separators."""
    p = path.replace("\\", "/")
    p = p.replace(":", "\\:")
    return p
