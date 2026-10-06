from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
router = APIRouter(tags=['route artwork'])
from app.render.route_artwork import ICON_DIR
@router.get('/api/route-icons/{kind}')
def route_icon(kind: str):
    if kind not in ('plane', 'ship', 'car', 'pin'):
        raise HTTPException(404, 'Route icon not found.')
    return FileResponse(ICON_DIR / (kind + '.png'), media_type='image/png')
