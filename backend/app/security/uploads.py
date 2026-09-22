"""Upload validation: extension allow-list, size limits, safe filenames.

Spec section 13: "Uploads need byte/dimension/duration limits, MIME/decoder
validation, safe generated filenames and disk-quota checks." and "Do not
interpolate user input into shell commands."
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path

from app.config import ALLOWED_AUDIO_EXT, ALLOWED_IMAGE_EXT, ALLOWED_VIDEO_EXT, MAX_UPLOAD_BYTES
from app.domain.constants import AssetType

_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


class UploadValidationError(ValueError):
    pass


def classify_extension(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext in ALLOWED_IMAGE_EXT:
        return AssetType.IMAGE
    if ext in ALLOWED_VIDEO_EXT:
        return AssetType.VIDEO
    if ext in ALLOWED_AUDIO_EXT:
        return AssetType.AUDIO
    raise UploadValidationError(
        f"Unsupported file extension '{ext}'. Allowed: "
        f"{sorted(ALLOWED_IMAGE_EXT | ALLOWED_VIDEO_EXT | ALLOWED_AUDIO_EXT)}"
    )


def safe_generated_filename(original_filename: str) -> str:
    """Never trusts the client filename for storage — generates a fresh
    UUID-based name, keeping only a sanitized extension, so path traversal
    or shell-special characters in the original name can't matter."""
    ext = Path(original_filename).suffix.lower()
    ext = _SAFE_CHARS.sub("", ext) or ".bin"
    return f"{uuid.uuid4().hex}{ext}"


def enforce_size_limit(num_bytes: int) -> None:
    if num_bytes > MAX_UPLOAD_BYTES:
        raise UploadValidationError(
            f"File too large ({num_bytes} bytes); limit is {MAX_UPLOAD_BYTES} bytes."
        )
