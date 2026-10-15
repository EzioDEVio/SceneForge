"""Paths built from request values stay inside the folder they belong to.

Every file SceneForge writes for a project lives under a known data folder (media, renders,
snapshots, workflows). Request values such as a project id or a library item id are checked
elsewhere (they must exist in the database or an allow-list), but the final path is also
checked here, so a value that slipped through validation still cannot reach a file outside
its folder.
"""
from __future__ import annotations

import os
from pathlib import Path


class UnsafePathError(ValueError):
    """A path built from request values would leave its base folder."""


def safe_join(base: str | os.PathLike, *parts: str | os.PathLike) -> Path:
    """Join ``parts`` onto ``base`` and return the result, refusing anything outside ``base``.

    Uses lexical normalisation (no symlink resolution) so results stay comparable with the
    configured data folders, which callers use with ``Path.relative_to``.
    """
    root = os.path.abspath(os.fspath(base))
    for part in parts:
        text = os.fspath(part)
        if not text or "\x00" in text or os.path.isabs(text):
            raise UnsafePathError("Invalid path component.")
    candidate = os.path.normpath(os.path.join(root, *(os.fspath(p) for p in parts)))
    if not candidate.startswith(root + os.sep):
        raise UnsafePathError("Path leaves its folder.")
    return Path(candidate)
