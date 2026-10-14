# Developing SceneForge

Back to the [README](../README.md) · [Contributing](../CONTRIBUTING.md)

## Run from source

Requirements:

- **Python 3.12.** The backend pins `numpy==2.5.3`, which needs 3.12.
- **Node.js 22.12 or later.** CI uses Node 22.
- **FFmpeg** on your PATH.

The desktop installer bundles its own Python runtime and FFmpeg. You only need these tools to run from source.

**Windows**
```bat
git clone https://github.com/EzioDEVio/SceneForge.git
cd SceneForge
scripts\setup.bat
scripts\start.bat          :: serves the built app at http://127.0.0.1:8000
scripts\dev.bat            :: or: backend with --reload on :8000 + Vite dev server on :5173
```

Windows setup keeps each checkout's Python runtime under
`%LOCALAPPDATA%\SceneForge\runtimes\<checkout-id>` so DLLs are not loaded from
an excessively long Downloads path. Setup and startup draw Latin and Arabic
text before reporting success. Projects and media remain in `backend\data`.
If a text preview reports a font-runtime error, close the app, rerun setup,
and restart. See [text-runtime recovery](dev-notes/reviews/TEXT_RUNTIME_RECOVERY.md).

**macOS / Linux**
```bash
git clone https://github.com/EzioDEVio/SceneForge.git && cd SceneForge
python3.12 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
npm --prefix frontend ci && npm --prefix frontend run build
cd backend && ../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# open http://127.0.0.1:8000 (FastAPI serves frontend/dist on the same origin)
```

For frontend work, run `npm --prefix frontend run dev`. Vite then serves on port 5173 and proxies `/api` to the backend on port 8000.

Useful environment variables:

| Variable | Use |
|---|---|
| `SCENEFORGE_DATA_DIR` | A separate data folder, for tests |
| `SCENEFORGE_MODEL_DIR` | An existing Whisper model folder, for offline runs |
| `SCENEFORGE_CUTOUT_MODEL_DIR` | An existing cutout model folder, for offline runs |
| `SCENEFORGE_VOICE_MODEL_DIR` | An existing voice-isolation model folder, for offline runs |

**Build the desktop installers yourself**
```bash
pip install -r desktop/requirements-build.txt
npm --prefix frontend ci && npm --prefix frontend run build
npm --prefix desktop ci
python desktop/scripts/fetch_ffmpeg.py        # downloads and verifies FFmpeg for your OS
python desktop/scripts/fetch_models.py        # the bundled cutout model (u2netp)
python desktop/scripts/build_backend.py       # bundles the Python backend (PyInstaller)
npm --prefix desktop run dist:win             # or dist:mac / dist:linux
```

| Folder | What it is |
|---|---|
| `frontend/` | React 18 + TypeScript + Vite editor |
| `backend/app/` | FastAPI server, SQLite database, FFmpeg rendering (`render/`) and providers |
| `desktop/` | Electron shell, updater, packaging and build scripts |
| `assets/` | Bundled fonts, sounds, stickers and look packs |
| `tests/` | Integration tests that render real video and measure the result |

## Tests

```bash
npm --prefix frontend run build && npm --prefix frontend test   # editor, units, timeline, video-generation and share-dialog checks
ELECTRON_SKIP_BINARY_DOWNLOAD=1 npm --prefix desktop ci && npm --prefix desktop test
python tests/integration/test_combined.py                       # each integration test is a standalone script
```

- **Build and render checks** (`.github/workflows/checks.yml`) run on every push. They run the frontend build and tests, then the Python integration scripts that render real media with FFmpeg.
- On Linux, the credential tests need a Secret Service keyring. Run them under `dbus-run-session` with `gnome-keyring-daemon` unlocked, as CI does.
- Tests never call paid providers. Those calls are mocked.
- `tests/browser/` holds Playwright walkthroughs of the real editor (they need a running backend; see each file's header), and `tests/browser/layout_audit.cjs` checks five window sizes. Screenshots they take go to `tests/output/`, which git ignores.
- Passing tests here do not replace a check of the installed app on Windows, macOS and Linux.

## Releasing (maintainers)

1. Set the version everywhere it appears (`python scripts/check_release_versions.py` lists and checks them), for example `0.9.5`, or `0.9.5-beta.1` for a beta.
2. Commit, then tag and push: `git tag -a v0.9.5 -m "SceneForge 0.9.5" && git push origin v0.9.5`.
3. The **Release** workflow tests everything and builds the Windows, Linux and macOS installers. It attaches them to a **draft** release.
4. Wait for **Windows**, **Linux**, and **Verify draft release files** to pass. The final check requires the Windows installer, its blockmap and update metadata, plus the Linux AppImage, deb and update metadata. Missing, empty or unfinished uploads fail the check. macOS is still experimental.
5. With the owner's approval, review the draft and click **Publish release**. Users' apps offer the update only after that. Do not publish the draft while either required build or the final file check is pending or red.

**Test builds.** Pushing a `release/**` or `claude/0.*` branch, or **Actions → Release → Run workflow**, builds and tests the Windows, Linux and macOS installers as temporary workflow artifacts without creating a release. Releases are made only from `v*` tags.
