"""Local, no-key, offline narration via espeak-ng.

This is explicitly the "Use recorded or licensed sample narration to test
offline. No provider key is required for this milestone" path from spec
M1, plus the "Experimental Edge TTS remains optional and is not the
default quality promise" spirit applied to a fully local alternative.

IMPORTANT — this is NOT the Arabic voice-quality gate described in
section 6/M4 of the specification. It is a robotic, formant-synthesis
voice included only so the end-to-end pipeline (script -> narration ->
timed captions -> rendered MP4) can be proven without any cloud
credentials. The UI labels it "Local (offline, robotic) — for pipeline
testing" and never claims production narration quality.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from app.render.ffmpeg_utils import FFmpegError

_LANG_MAP = {"ar": "ar", "en": "en-us"}


def synthesize(text: str, out_path: str, voice: str = "ar", rate_wpm: int = 160) -> None:
    if not text.strip():
        raise FFmpegError("Cannot synthesize empty narration text.")
    if any('\u0600' <= c <= '\u06ff' for c in text) and voice != 'ar':
        raise FFmpegError('Arabic narration requires Arabic language. Select Arabic or use Chatterbox Multilingual.')
    lang = _LANG_MAP.get(voice, voice)
    args = [
        "espeak-ng",
        "-v", lang,
        "-s", str(max(80, min(rate_wpm, 400))),
        "-w", out_path,
        "-b", "1", "--stdin",
    ]
    try:
        proc = subprocess.run(args, input=text.encode("utf-8"), capture_output=True)
    except FileNotFoundError as exc:
        # subprocess.run raises this directly (not a nonzero returncode)
        # when the executable itself can't be found on PATH — this is
        # the actual failure this Windows tester hit. Surface a clear,
        # actionable message instead of letting a raw traceback become a
        # generic "Internal Server Error" in the browser.
        raise FFmpegError(
            "espeak-ng was not found. Install it from "
            "https://github.com/espeak-ng/espeak-ng/releases (Windows .msi) "
            "and make sure it's on your PATH, then try again — or use "
            "'Upload recorded audio' instead, which needs no local TTS engine."
        ) from exc
    if proc.returncode != 0 or not Path(out_path).exists():
        raise FFmpegError(f"Local offline TTS (espeak-ng) failed: {proc.stderr.decode("utf-8", errors="replace")}")


def is_available() -> bool:
    try:
        proc = subprocess.run(["espeak-ng", "--version"], capture_output=True, text=True)
        return proc.returncode == 0
    except FileNotFoundError:
        return False
