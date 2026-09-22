"""Minimal secret storage for provider API keys (M2).

Honest scope note: this is NOT a real secrets vault. It base64-encodes
the key before storing it in SQLite, which only prevents the key from
being immediately human-readable in a casual database browse — it does
NOT protect against anyone with read access to the database file or the
Python process. A real implementation should use the OS credential
store (Windows Credential Manager / macOS Keychain / a proper secrets
manager) — tracked as a known gap in docs/known-limitations.md, not
hidden here.

Never log, return, or echo the decoded key anywhere except the single
call site that needs it to make a provider request.
"""
from __future__ import annotations

import base64


def obscure(secret: str) -> str:
    return base64.b64encode(secret.encode("utf-8")).decode("ascii")


def reveal(stored: str) -> str:
    return base64.b64decode(stored.encode("ascii")).decode("utf-8")


def mask_for_display(secret: str) -> str:
    """Never send the real key to the frontend — only a masked hint like
    'sk-...ab12' so the user can confirm which key is configured."""
    if len(secret) <= 8:
        return "•" * len(secret)
    return f"{secret[:3]}...{secret[-4:]}"
