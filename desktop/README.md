# SceneForge Windows Desktop Alpha

This milestone packages the working Workspace 2.5 editor as a Windows x64 desktop application. The setup wizard installs the desktop window, a private Python backend, FFmpeg/ffprobe, fonts and prebuilt editor assets. Python, Node.js and FFmpeg are not required on the customer's PATH.

## Scope
- One desktop window, one application instance, automatic backend startup and shutdown.
- OS-selected loopback port and a private per-launch API token; unrelated browsers cannot access the desktop backend.
- Project data stored beneath Electron's per-user application data directory, in `workspace`. Use File → Open workspace folder or Open logs.
- NSIS setup wizard with destination selection, installation progress, shortcuts and uninstaller.
- Uninstall preserves application data. Back up the workspace before testing any update.
- Unsigned private evaluation build. Windows may show publisher/reputation warnings. Production signing is not configured.

This is the **core installer milestone**. Native Chatterbox/Stable Diffusion runtime packs, model download/repair UI, automatic updates, MSI and macOS/Linux installers are not implemented here. Existing local AI endpoints still work when separately installed/running. The desktop shell disables automatic SD startup so it does not own or unexpectedly launch an external developer installation. Start/retry remains an explicit advanced control in the image drawer. Speech fallback requires its existing external setup.

## Existing projects
Close the old web server and desktop app first. Back up both folders. On an empty desktop workspace, copy the contents of the old `backend/data` folder into the desktop workspace. Do not merge two nonempty databases; retain the original backup. Media and rendered files must accompany the database. Reopen the desktop app and check a project before removing any old copy. An automated migration wizard is not part of this alpha.

## Build on Windows
Build tools are required only for developers/CI: Node.js 22, Python 3.12 and internet access.

```powershell
python -m pip install -r desktop/requirements-build.txt
npm --prefix frontend ci
npm --prefix frontend run build
npm --prefix desktop ci
python desktop/scripts/fetch_ffmpeg.py
python desktop/scripts/build_backend.py
python desktop/tests/smoke_backend.py --exe desktop/build/backend/sceneforge-backend/sceneforge-backend.exe --resources "$pwd" --ffmpeg-dir desktop/vendor/ffmpeg/bin
npm --prefix desktop run dist:win
```

The installer appears in `desktop/release`. `fetch_ffmpeg.py` verifies a fixed SHA-256 before extracting the pinned Windows pack, and retains upstream notices. No runtime dependencies are downloaded by the installer itself.

## CI and verification
`.github/workflows/desktop-windows.yml` runs on `desktop-alpha/**` branch pushes. It builds on Windows, runs editor and launcher tests, exercises the frozen backend (authentication, static UI, persistent project creation, real Arabic title rendering and shutdown), builds the installer, silently installs it in a temporary directory, launches the installed desktop executable, and checks uninstall. Only a successful run uploads the installer artifact.

The installer remains alpha even after CI passes: hosted runners have development software installed. A clean Windows machine without Python/Node/FFmpeg must still be tested, along with full editing, export, file dialogs and long-running render cancellation. Native AI acceleration needs separate real hardware testing.

## Architecture choice
This alpha uses Electron's bundled Chromium to reduce video-player differences from the tested browser workflow. Tauri was evaluated as a lighter option; platform-webview media compatibility remains a reason to defer that choice. Renderer Node access is disabled, context isolation and sandboxing are enabled, popup/navigation and permission requests are restricted. The frontend remains the same React application.

Windows is the only packaged target here. The Python resource paths and API session layer also run on Linux for automated tests, but the desktop executable paths and FFmpeg package are explicitly Windows-specific. Do not advertise macOS/Linux installers from this milestone.

Read `THIRD_PARTY.md` before any public redistribution. Production gates include signing, corresponding-source/notices review, OS credential storage, native component supervision, migration and rollback tests.
