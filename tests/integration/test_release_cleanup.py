"""Deletion integrity and saved local engine setup; no models downloaded."""
import os, pathlib, sys, tempfile
from unittest.mock import patch, Mock
from types import SimpleNamespace
root=pathlib.Path(__file__).resolve().parents[2]
tmp=tempfile.TemporaryDirectory();os.environ['SCENEFORGE_DATA_DIR']=tmp.name;os.environ['SCENEFORGE_SD_AUTOSTART']='0'
sys.path.insert(0,str(root/'backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import SessionLocal
from app.db.models import Asset, Scene, VoiceTake, RenderJob
from app import local_images
with TestClient(app) as c:
 project=c.post('/api/projects',json={'title':'Release test'}).json()
 sid=c.get('/api/projects/'+project['id']).json()['scenes'][0]['id']
 with SessionLocal() as db:
  asset=Asset(project_id=project['id'],type='audio',content_hash='test',storage_key='shared.wav');db.add(asset);db.flush();aid=asset.id
  first=VoiceTake(scene_id=sid,audio_asset_id=aid,spoken_text_hash='',accepted=True)
  second=VoiceTake(scene_id=sid,audio_asset_id=aid,spoken_text_hash='',accepted=False)
  db.add_all([first,second]);db.flush();one,two=first.id,second.id
  scene=db.get(Scene,sid);scene.rendered_asset_id=aid;scene.rendered_plan_hash='old';rev=scene.revision
  db.commit()
 assert c.delete('/api/voice-takes/'+two).status_code==200
 with SessionLocal() as db:assert db.get(VoiceTake,one).accepted and db.get(Scene,sid).revision==rev
 with SessionLocal() as db:
  job=RenderJob(project_id=project['id'],scope='export',status='running');db.add(job);db.commit();jid=job.id
 assert c.delete('/api/voice-takes/'+one).status_code==409
 with SessionLocal() as db:db.get(RenderJob,jid).status='succeeded';db.commit()
 assert c.delete('/api/voice-takes/'+one).status_code==200
 with SessionLocal() as db:
  assert db.get(Asset,aid) is not None
  scene=db.get(Scene,sid);assert not scene.voice_takes and scene.revision==rev+1 and scene.rendered_asset_id is None and scene.rendered_plan_hash is None
 assert c.delete('/api/voice-takes/'+one).status_code==404
 print('PASS take deletion, selected narration invalidation, shared asset preservation and render guard')
 folder=pathlib.Path(tmp.name)/'SD folder';folder.mkdir();(folder/'webui-user.bat').write_text('@echo off')
 assert c.put('/api/local-image-settings',json={'folder':tmp.name,'autostart':True}).status_code==400
 assert c.put('/api/local-image-settings',json={'folder':str(folder),'autostart':False}).status_code==200
 assert c.get('/api/local-image-settings').json()=={'folder':str(folder.resolve()),'autostart':False}
 assert (pathlib.Path(tmp.name)/'local-images.json').exists()
 with patch.object(local_images,'status',return_value={'ready':True,'state':'ready'}),patch.object(local_images.subprocess,'Popen') as spawn:
  assert local_images.start()['ready'];spawn.assert_not_called()
 print('PASS folder validation, persistent autostart choice and reuse of an already running engine')
 if os.name=='nt':
  (folder/'webui-user.bat').write_text('@echo off\npowershell.exe -NoProfile -Command "Start-Sleep -Seconds 60"\n')
  with patch.object(local_images,'status',return_value={'ready':False,'state':'stopped'}):
   result=local_images.start();assert result['state']=='starting',result
   assert local_images._process.poll() is None
   local_images.stop();local_images._process.wait(timeout=5)
  print('PASS Windows background launcher and owned process-tree shutdown')
