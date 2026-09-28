"""The desktop Share dialog may reveal only a render-output asset."""
import hashlib, os, pathlib, sys, tempfile
tmp=tempfile.TemporaryDirectory();root=pathlib.Path(__file__).resolve().parents[2]
os.environ['SCENEFORGE_DATA_DIR']=tmp.name;sys.path.insert(0,str(root/'backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.config import RENDERS_DIR
from app.db.database import SessionLocal, init_db
from app.db.models import Asset
from app.domain.constants import AssetOrigin

client=TestClient(app)
init_db()
project=client.post('/api/projects',json={'title':'Share location'}).json()
folder=pathlib.Path(RENDERS_DIR)/project['id'];folder.mkdir(parents=True,exist_ok=True)
path=folder/'share-test.mp4';data=b'local test render';path.write_bytes(data)
with SessionLocal() as db:
    asset=Asset(project_id=project['id'],type='video',content_hash=hashlib.sha256(data).hexdigest(),storage_key=f'{project["id"]}/share-test.mp4',mime='video/mp4',original_filename='share-test.mp4',origin=AssetOrigin.RENDER_OUTPUT)
    source=Asset(project_id=project['id'],type='image',content_hash='1'*64,storage_key=f'{project["id"]}/source.png',mime='image/png',original_filename='source.png',origin=AssetOrigin.UPLOAD)
    db.add_all([asset,source]);db.commit();db.refresh(asset);db.refresh(source);asset_id=asset.id;source_id=source.id
r=client.get(f'/api/assets/{asset_id}/location')
assert r.status_code==200 and pathlib.Path(r.json()['path'])==path.resolve() and r.json()['name']=='share-test.mp4'
print('PASS exported render location resolves to its file')
assert client.get(f'/api/assets/{source_id}/location').status_code==404
print('PASS location endpoint is scoped to existing render outputs')
