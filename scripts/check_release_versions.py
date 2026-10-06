"""Offline source gate. Does not build, package or contact GitHub."""
import argparse
import ast
import json
from pathlib import Path
import re

def check(root: Path, tag=None):
    labels = {}
    for folder in ('frontend','desktop'):
        for file in ('package.json','package-lock.json'):
            value=json.loads((root/folder/file).read_text())
            labels[f'{folder}/{file}']=value['version']
            if file=='package-lock.json': labels[f'{folder}/lock root']=value['packages']['']['version']
    tree=ast.parse((root/'backend/app/main.py').read_text())
    for node in ast.walk(tree):
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='BUILD_ID' for t in node.targets):
            build=ast.literal_eval(node.value)
            if not build.startswith('v'): raise ValueError('Backend BUILD_ID needs v prefix.')
            labels['backend build']=build[1:]
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='FastAPI':
            labels['API version']=ast.literal_eval(next(k.value for k in node.keywords if k.arg=='version'))
    found=re.search(r'^export const BUILD_ID = "v([^"]+)";', (root/'frontend/src/api.ts').read_text(),re.M)
    if not found or 'backend build' not in labels or 'API version' not in labels: raise ValueError('Missing build/version label.')
    labels['frontend build']=found[1]
    version=labels['frontend/package.json']
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?',version):raise ValueError('Invalid version.')
    if any(v!=version for v in labels.values()):raise ValueError('Version drift: '+str(labels))
    if tag and tag!='v'+version:raise ValueError('Tag does not match source version.')
    return version

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);parser.add_argument('--tag');args=parser.parse_args()
    try:print('Release labels agree: '+check(args.root,args.tag))
    except (ValueError,KeyError,OSError,StopIteration) as e:parser.exit(1,str(e)+'\n')
