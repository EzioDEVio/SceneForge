import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('versions',ROOT/'scripts/check_release_versions.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class Versions(unittest.TestCase):
 def test_source(self):self.assertEqual(module.check(ROOT,'v0.9.3'),'0.9.3')
 def test_wrong_tag(self):
  with self.assertRaises(ValueError):module.check(ROOT,'v0.9.2')
 def test_each_manifest_drift(self):
  for folder in ('frontend','desktop'):
   for name in ('package.json','package-lock.json'):
    with self.subTest(folder=folder,name=name),tempfile.TemporaryDirectory() as temp:
     root=Path(temp)
     for file in ('frontend/package.json','frontend/package-lock.json','desktop/package.json','desktop/package-lock.json','backend/app/main.py','frontend/src/api.ts'):
      destination=root/file;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/file,destination)
     p=root/folder/name;body=json.loads(p.read_text());body['version']='0.0.1';p.write_text(json.dumps(body))
     with self.assertRaises(ValueError):module.check(root)
