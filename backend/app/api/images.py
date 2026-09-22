"""AI image generation, scoped to a single part's visual brief — the
backend for the "Image chat" drawer. Only proceeds if the user has
configured their own provider key via Settings; otherwise reports that
plainly rather than faking a result.
"""
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import MEDIA_DIR
from app.db.database import get_db
from app.db.models import Asset, ProviderProfile, Scene
from app.domain import schemas
from app.domain.constants import AssetOrigin, AssetType
from app.providers.openai_image import ImageProviderError, generate_image
from app.render.ffmpeg_utils import FFmpegError, probe
from app.security.secrets import reveal

router = APIRouter(tags=["images"])


@router.post("/api/scenes/{scene_id}/generate-image", response_model=schemas.AssetOut)
def generate_image_for_scene(scene_id: str, body: schemas.GenerateImageRequest, db: Session = Depends(get_db)):
    scene = db.get(Scene, scene_id)
    if not scene:
        raise HTTPException(404, "Scene not found")

    query = db.query(ProviderProfile).filter(ProviderProfile.capability == "image")
    profile = query.filter(ProviderProfile.id == body.provider_id).first() if body.provider_id else query.first()
    if not profile:
        raise HTTPException(
            400,
            "No image-generation provider is configured. Add your API key in Settings \u2192 Providers first.",
        )
    if profile.name not in ("openai", "gemini", "cloudflare", "huggingface", "local_sd"):
        raise HTTPException(400, "Unsupported image provider")

    try:
        api_key = reveal(profile.secret_ref or "")
    except Exception:
        raise HTTPException(500, "Stored provider key could not be read. Please re-enter it in Settings.")

    try:
        if profile.name in ("cloudflare", "huggingface", "local_sd"):
            from app.providers.image_options import generate
            image_bytes = generate(profile, api_key, body.prompt, body.size, body.local_options.model_dump() if body.local_options else None)
        elif profile.name == "gemini":
            from app.providers.gemini_image import generate_image as gemini_image
            image_bytes = gemini_image(api_key, body.prompt, body.size, profile.model or "gemini-3.1-flash-image")
        else:
            image_bytes = generate_image(api_key, body.prompt, size=body.size, model=profile.model or "gpt-image-1")
    except ImageProviderError as e:
        raise HTTPException(502, str(e))

    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        extension, mime = "png", "image/png"
    elif image_bytes.startswith(b"\xff\xd8\xff"):
        extension, mime = "jpg", "image/jpeg"
    else:
        raise HTTPException(502, "Provider did not return a PNG or JPEG image.")
    project_dir = Path(MEDIA_DIR) / scene.project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    dest_path = project_dir / f"generated_{uuid.uuid4().hex}.{extension}"
    dest_path.write_bytes(image_bytes)

    try:
        info = probe(str(dest_path))
    except FFmpegError as e:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(502, f"The provider returned data that could not be decoded as an image: {e.stderr[:300]}")
    if not info.has_video:  # images decode through the same "video stream" probe path
        dest_path.unlink(missing_ok=True)
        raise HTTPException(502, "The provider returned data that was not a decodable image.")

    asset = Asset(
        project_id=scene.project_id,
        type=AssetType.IMAGE,
        content_hash=hashlib.sha256(image_bytes).hexdigest(),
        storage_key=str(dest_path.relative_to(MEDIA_DIR)),
        mime=mime,
        original_filename=dest_path.name,
        width=info.width,
        height=info.height,
        origin=AssetOrigin.GENERATED,
        source_url=None,
        creator=profile.name,
        generation_metadata_json={"scene_id": scene.id, "prompt": body.prompt, "model": profile.model, "size": body.size, "local_options": body.local_options.model_dump() if body.local_options else None},
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


@router.get("/api/scenes/{scene_id}/image-history")
def image_history(scene_id: str, db: Session = Depends(get_db)):
    scene = db.get(Scene, scene_id)
    if not scene: raise HTTPException(404, "Scene not found")
    assets = db.query(Asset).filter(Asset.project_id == scene.project_id, Asset.origin == AssetOrigin.GENERATED, Asset.type == AssetType.IMAGE).all()
    return [{"id": a.id, "provider": a.creator, **(a.generation_metadata_json or {})} for a in reversed(assets) if (a.generation_metadata_json or {}).get("scene_id") == scene_id][:50]


@router.get('/api/local-images/{provider_id}/status')
def local_image_status(provider_id: str, db: Session = Depends(get_db)):
    import requests
    from app.providers.image_options import local_url
    profile = db.get(ProviderProfile, provider_id)
    if not profile or profile.name != 'local_sd':
        raise HTTPException(404, 'Local image provider not found')
    if local_url(profile.base_url).rstrip('/') in ('http://127.0.0.1:7860','http://localhost:7860'):
        from app.local_images import status
        return status()
    try:
        session = requests.Session(); session.trust_env = False
        result = session.get(local_url(profile.base_url) + '/sdapi/v1/options', timeout=3, allow_redirects=False)
        result.raise_for_status()
        return {'ready': True, 'model': result.json().get('sd_model_checkpoint', 'current')}
    except Exception:
        return {'ready': False, 'model': '', 'message': 'Local image API is not ready. Wait for startup, then retry. Check backend/data/logs/stable-diffusion.log if it stays unavailable.'}


def _managed_profile(provider_id,db):
    from app.providers.image_options import local_url
    profile=db.get(ProviderProfile,provider_id)
    if not profile or profile.name!='local_sd':raise HTTPException(404,'Local image provider not found')
    if local_url(profile.base_url).rstrip('/') not in ('http://127.0.0.1:7860','http://localhost:7860'):
        raise HTTPException(400,'Startup controls manage only the local WebUI on port 7860.')
    return profile

@router.post('/api/local-images/{provider_id}/start')
def start_local_image(provider_id:str,db:Session=Depends(get_db)):
    from app.local_images import start
    _managed_profile(provider_id,db)
    return start()

@router.get('/api/local-images/{provider_id}/log')
def local_image_log(provider_id:str,db:Session=Depends(get_db)):
    from app.config import LOGS_DIR
    _managed_profile(provider_id,db)
    path=LOGS_DIR/'stable-diffusion.log'
    if not path.exists():return {'text':'No startup log yet. Start the engine first.'}
    with path.open('rb') as f:
        f.seek(0,2);f.seek(max(0,f.tell()-16000));data=f.read()
    return {'text':data.decode('utf-8',errors='replace')}

from pydantic import BaseModel,Field
class TitlePreview(BaseModel):
    text:str=Field(max_length=2000)
    background:str=Field(pattern=r'^#[0-9a-fA-F]{6}$')
    background2:str=Field(default='#000000',pattern=r'^#[0-9a-fA-F]{6}$')
    gradient:bool=False
    duration:float=Field(default=5,ge=.5,le=60)
    layer:schemas.TextLayer
    width:int=Field(default=1920,ge=256,le=4096)
    height:int=Field(default=1080,ge=256,le=4096)

_preview_lock=__import__('threading').Lock()
@router.post('/api/title-preview')
def title_preview(body:TitlePreview):
    import tempfile,subprocess
    from PIL import Image,ImageColor
    from fastapi.responses import Response
    from app.config import FFMPEG_BIN, RESOURCE_DIR
    from app.render.subtitles import write_ass_file
    from app.render.ffmpeg_utils import escape_path_for_filter
    if not _preview_lock.acquire(blocking=False):raise HTTPException(409,'A title preview is already rendering. Please wait.')
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);w=640;h=max(2,round(w*body.height/body.width/2)*2)
            im=Image.new('RGB',(w,h),body.background)
            if body.gradient:
                a=ImageColor.getrgb(body.background);b=ImageColor.getrgb(body.background2)
                # Same diagonal projection as canvas createLinearGradient.
                im.putdata([tuple(round(a[i]+(b[i]-a[i])*(x*w+y*h)/(w*w+h*h)) for i in range(3)) for y in range(h) for x in range(w)])
            im.save(root/'bg.png');layer=body.layer.model_dump();layer['text']=body.text
            for key in ('size','outline_width','shadow'):layer[key]=layer[key]*w/body.width
            layer['size']=max(1,round(layer['size']))
            ass=write_ass_file('preview','',int(body.duration*1000),{'layers':[layer]},w,h,str(root/'title.ass'))
            fonts=RESOURCE_DIR/'assets'/'fonts'
            result=subprocess.run([FFMPEG_BIN,'-v','error','-y','-loop','1','-i',str(root/'bg.png'),'-t',str(body.duration),'-vf',f"ass='{escape_path_for_filter(ass)}':fontsdir='{escape_path_for_filter(str(fonts))}'",'-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p','-movflags','+faststart',str(root/'preview.mp4')],capture_output=True,timeout=90)
            if result.returncode:raise HTTPException(500,'Title preview failed: '+result.stderr.decode(errors='replace')[-1500:])
            return Response((root/'preview.mp4').read_bytes(),media_type='video/mp4')
    finally:_preview_lock.release()
