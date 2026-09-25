"""Per-launch local API authentication, enabled only by the desktop shell."""
import secrets
from starlette.responses import JSONResponse
class DesktopSessionMiddleware:
    def __init__(self,app,token):self.app=app;self.token=token
    async def __call__(self,scope,receive,send):
        if scope['type']=='http' and self.token:
            headers=dict(scope.get('headers',[]))
            candidate=headers.get(b'x-sceneforge-token',b'')
            origin=headers.get(b'origin',b'').decode('latin1')
            host=headers.get(b'host',b'').decode('latin1')
            if not secrets.compare_digest(candidate,self.token.encode('utf8')) or (origin and origin!='http://'+host):
                await JSONResponse({'detail':'Desktop session required'},status_code=403)(scope,receive,send);return
        await self.app(scope,receive,send)
