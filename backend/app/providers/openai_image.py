"""OpenAI image-generation adapter (M2 — first BYOK provider).

Uses the user's own API key, entered through the app's Settings screen
(never requested or handled in chat, per the project's security posture).
No key is bundled, defaulted, or shared — every request uses the caller's
own credentials, and the app makes no image-generation calls unless the
user has explicitly configured a key.

Untested against the real OpenAI API in this development session (no
key was available to test with) — the request/response shape matches
OpenAI's documented Images API as of this codebase's writing, and error
handling covers the documented failure shapes (401, 429, 400), but this
should be treated as reviewed-but-unverified until exercised with a real
key. Recorded plainly in docs/known-limitations.md.
"""
from __future__ import annotations

import base64

import requests

DEFAULT_MODEL = "gpt-image-1"
API_URL = "https://api.openai.com/v1/images/generations"
TIMEOUT_S = 90


class ImageProviderError(RuntimeError):
    """Raised with a message safe to show directly to the user — never
    includes the API key."""


def generate_image(api_key: str, prompt: str, size: str = "1024x1024", model: str = DEFAULT_MODEL) -> bytes:
    if not prompt.strip():
        raise ImageProviderError("Image prompt is empty.")
    if not api_key.strip():
        raise ImageProviderError("No OpenAI API key is configured. Add one in Settings.")

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "prompt": prompt, "size": size, "n": 1}

    try:
        resp = requests.post(API_URL, headers=headers, json=payload, timeout=TIMEOUT_S)
    except requests.exceptions.Timeout as exc:
        raise ImageProviderError("OpenAI image request timed out. Try again.") from exc
    except requests.exceptions.ConnectionError as exc:
        raise ImageProviderError("Could not reach OpenAI's API. Check your internet connection.") from exc

    if resp.status_code == 401:
        raise ImageProviderError("OpenAI rejected the API key (401 Unauthorized). Check the key in Settings.")
    if resp.status_code == 429:
        raise ImageProviderError("OpenAI rate-limited this request (429). Wait a moment and try again, or check your usage quota.")
    if resp.status_code == 400:
        try:
            detail = resp.json().get("error", {}).get("message", resp.text)
        except Exception:
            detail = resp.text
        raise ImageProviderError(f"OpenAI rejected the request: {detail[:300]}")
    if resp.status_code >= 500:
        raise ImageProviderError(f"OpenAI's API returned a server error ({resp.status_code}). Try again shortly.")
    if resp.status_code != 200:
        raise ImageProviderError(f"OpenAI's API returned an unexpected status {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    items = data.get("data", [])
    if not items:
        raise ImageProviderError("OpenAI's response contained no image data.")

    b64 = items[0].get("b64_json")
    if not b64:
        url = items[0].get("url")
        if url:
            img_resp = requests.get(url, timeout=TIMEOUT_S)
            if img_resp.status_code != 200:
                raise ImageProviderError("Could not download the generated image from OpenAI.")
            return img_resp.content
        raise ImageProviderError("OpenAI's response had neither image data nor a URL.")

    try:
        return base64.b64decode(b64)
    except Exception as exc:
        raise ImageProviderError("Could not decode the image OpenAI returned.") from exc
