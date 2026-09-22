"""Build on the target OS; package Python privately, not into the system PATH."""
import pathlib,subprocess,sys
root=pathlib.Path(__file__).resolve().parents[2]
subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--name','sceneforge-backend',
 '--distpath',str(root/'desktop/build/backend'),'--workpath',str(root/'desktop/build/pyinstaller'),'--specpath',str(root/'desktop/build'),
 '--paths',str(root/'backend'),'--collect-submodules','app','--collect-submodules','uvicorn',
 '--hidden-import','PIL.PngImagePlugin','--hidden-import','PIL.JpegImagePlugin',str(root/'backend/desktop_entry.py')],check=True,cwd=root)
