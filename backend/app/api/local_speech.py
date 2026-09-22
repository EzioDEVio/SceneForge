"""Local speech components; fixed loopback endpoints, no cloud credentials."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import ProviderProfile
from app.api.providers import _to_out
from app.providers.speech_http import list_voices

router = APIRouter(prefix='/api/local-speech', tags=['local speech'])
ENGINES = {'kokoro': ('http://127.0.0.1:8880', 'kokoro'),
           'chatterbox': ('http://127.0.0.1:8881', 'chatterbox')}

@router.post('/{engine}/connect')
def connect(engine: str, db: Session = Depends(get_db)):
    if engine not in ENGINES: raise HTTPException(404, 'Unknown local engine')
    url, model = ENGINES[engine]
    profile = db.query(ProviderProfile).filter_by(capability='speech', name=engine).first()
    if profile is None:
        profile = ProviderProfile(capability='speech',name=engine,base_url=url,model=model,secret_ref='')
    try: voices = list_voices(profile)
    except ValueError:
        raise HTTPException(503, f'{engine.title()} is not running. Run START_{engine.upper()}_VOICE.bat in your app folder, then retry. The first installation downloads the engine and model; later narration runs locally.')
    if not voices: raise HTTPException(503, 'The speech service has no available voices.')
    db.add(profile);db.commit();db.refresh(profile)
    return {'profile': _to_out(profile), 'voices': voices, 'status': 'service_reachable',
            'message': 'Service connected. Run a short audition to verify model readiness.'}
