"""Local provider profiles, one per capability and provider name."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import ProviderProfile
from app.domain import schemas
from app.security.secrets import mask_for_display, obscure, reveal

router = APIRouter(prefix="/api/providers", tags=["providers"])

SUPPORTED = {
    "image": {"openai", "gemini", "cloudflare", "huggingface", "local_sd"},
    "speech": {"kokoro", "chatterbox"},
}


def _to_out(p: ProviderProfile) -> schemas.ProviderProfileOut:
    try:
        key = reveal(p.secret_ref or "")
        masked = mask_for_display(key)
    except Exception:
        masked = "•••"
    return schemas.ProviderProfileOut(
        id=p.id, capability=p.capability, name=p.name, model=p.model,
        base_url=p.base_url, masked_key=masked, configured=True,
    )


@router.get("", response_model=list[schemas.ProviderProfileOut])
def list_providers(db: Session = Depends(get_db)):
    return [_to_out(p) for p in db.query(ProviderProfile).all()]


@router.post("", response_model=schemas.ProviderProfileOut)
def upsert_provider(body: schemas.ProviderProfileCreate, db: Session = Depends(get_db)):
    if body.capability not in SUPPORTED:
        raise HTTPException(400, f"Unsupported capability '{body.capability}'. Supported: {list(SUPPORTED)}")
    if body.name not in SUPPORTED[body.capability]:
        raise HTTPException(400, f"Unsupported provider '{body.name}' for {body.capability}. Supported: {list(SUPPORTED[body.capability])}")
    if body.capability == "image" and body.name != "local_sd" and not body.api_key.strip():
        raise HTTPException(400, "API key is required.")

    if body.name == "cloudflare":
        import re
        if not re.fullmatch(r"[a-fA-F0-9]{32}", body.base_url or ""):
            raise HTTPException(400, "Enter your 32-character Cloudflare account ID.")
        body.model = "@cf/black-forest-labs/flux-1-schnell"
    if body.name == "local_sd":
        from app.providers.image_options import local_url
        try: body.base_url = local_url(body.base_url)
        except ValueError as exc: raise HTTPException(400, str(exc))
    if body.capability == "speech":
        from urllib.parse import urlsplit
        url = urlsplit(body.base_url or "")
        if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise HTTPException(400, "Enter an HTTP(S) service URL without credentials, query or fragment.")
    existing = db.query(ProviderProfile).filter(ProviderProfile.capability == body.capability, ProviderProfile.name == body.name).first()
    if existing:
        existing.name = body.name
        existing.model = body.model
        existing.base_url = body.base_url
        existing.secret_ref = obscure(body.api_key)
        profile = existing
    else:
        profile = ProviderProfile(
            capability=body.capability, name=body.name, model=body.model,
            base_url=body.base_url, secret_ref=obscure(body.api_key),
        )
        db.add(profile)
    db.commit()
    db.refresh(profile)
    return _to_out(profile)


@router.delete("/{capability}")
def delete_provider(capability: str, db: Session = Depends(get_db)):
    existing = db.query(ProviderProfile).filter(ProviderProfile.capability == capability).first()
    if not existing:
        raise HTTPException(404, "No provider configured for this capability.")
    db.delete(existing)
    db.commit()
    return {"ok": True}


@router.delete("/profile/{profile_id}")
def delete_profile(profile_id: str, db: Session = Depends(get_db)):
    profile = db.get(ProviderProfile, profile_id)
    if not profile: raise HTTPException(404, "Provider not found")
    db.delete(profile)
    db.commit()
    return {"ok": True}


@router.get("/profile/{profile_id}/voices")
def voices(profile_id: str, db: Session = Depends(get_db)):
    from app.providers.speech_http import list_voices
    profile = db.get(ProviderProfile, profile_id)
    if not profile or profile.capability != "speech": raise HTTPException(404, "Speech provider not found")
    try: return {"voices": list_voices(profile)}
    except ValueError as exc: raise HTTPException(502, str(exc))
