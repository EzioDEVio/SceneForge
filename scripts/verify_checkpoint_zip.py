"""Read-only gate for the future owner-approved combined source package."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import zipfile

REQUIRED = ('README.md','LICENSE','backend/app/main.py','backend/requirements.txt',
 'backend/app/api/editor_drafts.py','backend/app/api/route_icons.py','backend/app/render/route_artwork.py',
 'frontend/package.json','frontend/package-lock.json','frontend/src/App.tsx',
 'frontend/src/api.ts','frontend/src/editorDraft.ts','frontend/src/EditorDraftPreview.tsx',
 'frontend/src/InspectorSections.tsx','frontend/src/AutoCutSequence.tsx','frontend/src/recovery.css','frontend/src/SafeMenus.tsx',
 'frontend/dist/index.html','desktop/package.json','desktop/package-lock.json',
 'scripts/start.bat','scripts/setup.bat','scripts/windows_runtime.py','backend/app/render/font_runtime.py',
 'backend/app/managed_ai.py','backend/app/api/managed_ai.py','services/stable-diffusion/server.py',
 'desktop/installer.nsh','docs/LOCAL_AI_INSTALLER.md',
 'docs/TEXT_RUNTIME_RECOVERY.md','scripts/check_release_versions.py',
 'scripts/verify_checkpoint_zip.py','docs/manual.html','docs/STAGE6_RELEASE_READINESS.md',
 'assets/route-icons/plane.png','assets/route-icons/ship.png','assets/route-icons/car.png','assets/route-icons/pin.png')

def verify(path, max_bytes=40_000_000):
    path=Path(path)
    if path.stat().st_size>max_bytes:raise ValueError('Checkpoint exceeds the size limit.')
    with zipfile.ZipFile(path) as z:
        files=[i for i in z.infolist() if not i.is_dir()]
        if not files:raise ValueError('Empty checkpoint ZIP.')
        names=[i.filename for i in files]
        if len(names)!=len(set(names)):raise ValueError('Duplicate archive paths.')
        for i in files:
            p=PurePosixPath(i.filename)
            if p.is_absolute() or '\\' in i.filename or '..' in p.parts or any(':' in v for v in p.parts):raise ValueError('Unsafe archive path.')
            if set(p.parts)&{'.venv','node_modules','data','.git'}:raise ValueError('Runtime/private directories are excluded.')
            if stat.S_ISLNK(i.external_attr>>16) or i.flag_bits&1:raise ValueError('Symlink or encrypted entry.')
        roots=[n[:-len('frontend/package.json')] for n in names if n.endswith('frontend/package.json')]
        if len(roots)!=1:raise ValueError('Expected one source root.')
        root=roots[0]
        if any(not n.startswith(root) for n in names):raise ValueError('Files outside the source root.')
        for name in REQUIRED:
            if root+name not in names or not z.getinfo(root+name).file_size:raise ValueError('Missing/empty '+name)
        for folder in ('frontend','desktop'):
            package=json.loads(z.read(root+folder+'/package.json'))
            lock=json.loads(z.read(root+folder+'/package-lock.json'))
            if [package['version'],lock['version'],lock['packages']['']['version']]!=['0.9.3']*3:raise ValueError('Package version drift.')
        for name in ('backend/app/main.py','frontend/src/api.ts'):
            if 'BUILD_ID = "v0.9.3"' not in z.read(root+name).decode():raise ValueError('Build version drift.')
        if not any(n.startswith(root+'frontend/dist/assets/') and n.endswith('.js') and z.getinfo(n).file_size for n in names):raise ValueError('Missing compiled frontend JavaScript.')
        if z.testzip():raise ValueError('Corrupt archive content.')
    return {'version':'0.9.3','files':len(files),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'root':root}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('zip',type=Path);args=parser.parse_args()
    try:print(json.dumps(verify(args.zip),indent=2))
    except (ValueError,KeyError,OSError,zipfile.BadZipFile) as e:parser.exit(1,str(e)+'\n')
