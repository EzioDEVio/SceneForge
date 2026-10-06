import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('archive',ROOT/'scripts/verify_checkpoint_zip.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Checkpoint(unittest.TestCase):
 def fixture(self,path,omit=None,extra=None):
  with zipfile.ZipFile(path,'w') as z:
   for name in m.REQUIRED:
    if name==omit:continue
    text='source'
    if name.endswith('package.json'):text=json.dumps({'version':'0.9.3'})
    if name.endswith('package-lock.json'):text=json.dumps({'version':'0.9.3','packages':{'':{'version':'0.9.3'}}})
    if name in ('backend/app/main.py','frontend/src/api.ts'):text='BUILD_ID = "v0.9.3"'
    z.writestr('SceneForge/'+name,text)
   z.writestr('SceneForge/frontend/dist/assets/app.js','compiled fixture')
   if extra:z.writestr(extra,'unexpected')
 def test_valid_synthetic_fixture(self):
  with tempfile.TemporaryDirectory() as temp:
   p=Path(temp)/'test.zip';self.fixture(p);result=m.verify(p);self.assertEqual(result['version'],'0.9.3');self.assertEqual(len(result['sha256']),64)
 def test_each_required_file(self):
  for name in m.REQUIRED:
   with self.subTest(name=name),tempfile.TemporaryDirectory() as temp:
    p=Path(temp)/'test.zip';self.fixture(p,omit=name)
    with self.assertRaises(ValueError):m.verify(p)
 def test_empty(self):
  with tempfile.TemporaryDirectory() as temp:
   p=Path(temp)/'test.zip'
   with zipfile.ZipFile(p,'w'):pass
   with self.assertRaises(ValueError):m.verify(p)
 def test_unsafe_and_runtime_paths(self):
  for extra in ('../escape','/absolute','SceneForge/data/project.db','SceneForge/node_modules/tool','SceneForge/a\\b','outside.txt'):
   with self.subTest(extra=extra),tempfile.TemporaryDirectory() as temp:
    p=Path(temp)/'test.zip';self.fixture(p,extra=extra)
    with self.assertRaises(ValueError):m.verify(p)
 def test_corrupt_and_oversize(self):
  with tempfile.TemporaryDirectory() as temp:
   p=Path(temp)/'test.zip';p.write_bytes(b'not a zip')
   with self.assertRaises(zipfile.BadZipFile):m.verify(p)
   self.fixture(p)
   with self.assertRaises(ValueError):m.verify(p,max_bytes=1)
