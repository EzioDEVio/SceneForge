"""Google Interactions API adapter. No SDK dependency or key in URLs."""
import base64
import requests
from app.providers.openai_image import ImageProviderError


def generate_image(api_key: str, prompt: str, size: str, model: str) -> bytes:
    aspect = {"1024x1024": "1:1", "1536x1024": "3:2", "1024x1536": "2:3"}.get(size, "1:1")
    try:
        response = requests.post("https://generativelanguage.googleapis.com/v1beta/interactions",
            headers={"x-goog-api-key": api_key},
            json={"model": model, "input": prompt, "response_format": {"type": "image", "mime_type": "image/png", "aspect_ratio": aspect}}, timeout=(15, 180))
        if not response.ok:
            raise ImageProviderError(f"Gemini request failed (HTTP {response.status_code}). Check model access, API key and quota in Google AI Studio.")
        def images(node):
            if isinstance(node, dict):
                if node.get("type") == "image" and node.get("data"): yield node["data"]
                for value in node.values(): yield from images(value)
            elif isinstance(node, list):
                for value in node: yield from images(value)
        all_images = list(images(response.json()))
        data = all_images[-1] if all_images else None
        if not data: raise ImageProviderError("Gemini returned no image. Try another prompt or an image-capable model.")
        return base64.b64decode(data, validate=True)
    except requests.RequestException:
        raise ImageProviderError("Could not reach Gemini, or generation timed out. Check your connection before retrying.")
    except (ValueError, TypeError):
        raise ImageProviderError("Gemini returned an invalid image response.")
