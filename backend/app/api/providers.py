"""Local provider profiles, one per capability and provider name."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import ProviderProfile
from app.domain import schemas
from app.security.secrets import mask_for_display, obscure, reveal, forget

router = APIRouter(prefix="/api/providers", tags=["providers"])

SUPPORTED = {
    "image": {"openai", "gemini", "cloudflare", "huggingface", "together", "local_sd"},
    "speech": {"kokoro", "chatterbox", "elevenlabs"},
}


def _to_out(p: ProviderProfile) -> schemas.ProviderProfileOut:
    configured = True
    try:
        key = reveal(p.secret_ref or "")
        masked = mask_for_display(key)
    except Exception:
        masked = "Credential unavailable — re-enter key"
        configured = False
    return schemas.ProviderProfileOut(
        id=p.id, capability=p.capability, name=p.name, model=p.model,
        base_url=p.base_url, masked_key=masked, configured=configured,
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
    if body.name == 'elevenlabs':
        if not body.api_key.strip(): raise HTTPException(400, 'ElevenLabs API key is required.')
        body.base_url = 'https://api.elevenlabs.io/v1'
    if body.capability == "speech":
        from urllib.parse import urlsplit
        url = urlsplit(body.base_url or "")
        if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise HTTPException(400, "Enter an HTTP(S) service URL without credentials, query or fragment.")
    existing = db.query(ProviderProfile).filter(ProviderProfile.capability == body.capability, ProviderProfile.name == body.name).first()
    old_ref = existing.secret_ref if existing else ''
    try:
        protected = obscure(body.api_key) if body.api_key.strip() or not existing else old_ref
    except ValueError as exc:
        raise HTTPException(503, str(exc))
    if existing:
        existing.name = body.name
        existing.model = body.model
        existing.base_url = body.base_url
        if body.api_key.strip():
            existing.secret_ref = protected
        profile = existing
    else:
        profile = ProviderProfile(
            capability=body.capability, name=body.name, model=body.model,
            base_url=body.base_url, secret_ref=protected,
        )
        db.add(profile)
    db.commit()
    db.refresh(profile)
    # Old releases shared a vault entry when two profiles used the same key.
    if old_ref and old_ref != profile.secret_ref and not db.query(ProviderProfile).filter(ProviderProfile.secret_ref == old_ref).first():
        try: forget(old_ref)
        except ValueError: pass  # New protected value is committed; an old vault entry is harmless.
    return _to_out(profile)


@router.delete("/{capability}")
def delete_provider(capability: str, db: Session = Depends(get_db)):
    existing = db.query(ProviderProfile).filter(ProviderProfile.capability == capability).first()
    if not existing:
        raise HTTPException(404, "No provider configured for this capability.")
    _forget_unshared(existing, db)
    db.delete(existing)
    db.commit()
    return {"ok": True}


@router.delete("/profile/{profile_id}")
def delete_profile(profile_id: str, db: Session = Depends(get_db)):
    profile = db.get(ProviderProfile, profile_id)
    if not profile: raise HTTPException(404, "Provider not found")
    _forget_unshared(profile, db)
    db.delete(profile)
    db.commit()
    return {"ok": True}


def _forget_unshared(profile, db):
    if not db.query(ProviderProfile).filter(ProviderProfile.id != profile.id, ProviderProfile.secret_ref == profile.secret_ref).first():
        try: forget(profile.secret_ref or '')
        except ValueError as exc: raise HTTPException(503, str(exc))


@router.get("/profile/{profile_id}/voices")
def voices(profile_id: str, db: Session = Depends(get_db)):
    from app.providers.speech_http import list_voice_details
    profile = db.get(ProviderProfile, profile_id)
    if not profile or profile.capability != "speech": raise HTTPException(404, "Speech provider not found")
    try: return {"voices": list_voice_details(profile)}
    except ValueError as exc: raise HTTPException(502, str(exc))
