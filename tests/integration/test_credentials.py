"""Exercise real native keyring and legacy database migration; no paid APIs."""
import base64, os, pathlib, sys, tempfile
from unittest.mock import patch
root=pathlib.Path(__file__).resolve().parents[2]
tmp=tempfile.TemporaryDirectory()
os.environ['SCENEFORGE_DATA_DIR']=tmp.name
os.environ['SCENEFORGE_SD_AUTOSTART']='0'
sys.path.insert(0,str(root/'backend'))
from app.security import secrets
from app.db.database import init_db, SessionLocal, engine
from app.db.models import ProviderProfile
init_db()
plain='fixture-credential-never-a-real-api-key'
legacy=base64.b64encode(plain.encode()).decode()
with SessionLocal() as db:
    p=ProviderProfile(capability='image',name='openai',secret_ref=legacy)
    db.add(p);db.commit();pid=p.id
with patch.object(secrets,'vault',side_effect=RuntimeError('locked')):
    assert secrets.migrate_credentials()==1
    try: secrets.obscure(plain)
    except ValueError: pass
    else: raise AssertionError('Insecure storage fallback')
try: secrets.reveal(legacy)
except ValueError: pass
else: raise AssertionError('Legacy key used without migration')
assert secrets.migrate_credentials()==0
with SessionLocal() as db:
    ref=db.get(ProviderProfile,pid).secret_ref
assert ref.startswith('keyring:') and secrets.reveal(ref)==plain
assert secrets.migrate_credentials()==0
for f in pathlib.Path(tmp.name).glob('sceneforge.db*'):
    data=f.read_bytes()
    assert plain.encode() not in data and legacy.encode() not in data
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as c:
    result=c.get('/api/providers')
    assert plain not in result.text and legacy not in result.text
    assert result.json()[0]['configured']
    assert c.get('/api/close-status').json()['ready']
    assert c.delete('/api/providers/profile/'+pid).status_code==200
assert secrets.vault().get_password(secrets.SERVICE,ref[8:]) is None
engine.dispose();tmp.cleanup()
print('PASS native vault round trip, fail-closed migration, database scrubbing, masked API and credential deletion')
