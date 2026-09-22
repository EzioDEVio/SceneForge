"""Exercise actual preview encoding, validation, and local launcher guardrails."""
import os,sys,tempfile,pathlib,subprocess,json
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'backend'))
tmp=tempfile.TemporaryDirectory();os.environ['SCENEFORGE_DATA_DIR']=tmp.name
from fastapi.testclient import TestClient
from app.main import app
from app import local_images
with TestClient(app) as c:
 for mode in ['none','fade','slide','slide-right','slide-up','slide-down','zoom','reveal','typewriter','blur','glitch']:
  payload={'text':'بداية الحكاية','background':'#000000','gradient':True,'background2':'#352041','duration':1.2,'layer':{'id':'title','text':'بداية الحكاية','animation':mode,'animation_ms':400,'exit_ms':200,'size':150,'outline_width':2,'shadow':2}}
  r=c.post('/api/title-preview',json=payload);assert r.status_code==200,r.text
  dest=pathlib.Path(tmp.name)/(mode+'.mp4');dest.write_bytes(r.content)
  info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-of','json',str(dest)]));assert abs(float(info['format']['duration'])-1.2)<.1
  print('PASS rendered preview',mode)
 payload['layer']['family']='bad{font}';assert c.post('/api/title-preview',json=payload).status_code==422
 with patch.object(local_images,'status',return_value={'ready':True,'state':'ready'}),patch.object(local_images.subprocess,'Popen') as spawn:
  assert local_images.start()['ready'];spawn.assert_not_called()
 print('PASS validation and already-running engine guard')
from types import SimpleNamespace
with tempfile.TemporaryDirectory() as install:
 pathlib.Path(install,'webui-user.bat').write_text('@echo off')
 with patch.object(local_images,'os',SimpleNamespace(name='nt',environ={'SCENEFORGE_SD_DIR':install})),patch.object(local_images,'status',return_value={'ready':False}),patch.object(local_images.socket,'create_connection',side_effect=OSError),patch.object(local_images.subprocess,'CREATE_NO_WINDOW',0,create=True),patch.object(local_images.subprocess,'Popen') as launch:
  launch.return_value.poll.return_value=None
  assert local_images.start()['state']=='starting'
  assert launch.call_args.args[0]==['cmd.exe','/d','/c','webui-user.bat']
  assert launch.call_args.kwargs['cwd']==install
  local_images.start();assert launch.call_count==1
 print('PASS mocked Windows launch and duplicate prevention')
