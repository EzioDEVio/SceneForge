# Third-party components in SceneForge Studio

SceneForge Studio is free software under the **GNU General Public License v3.0 or later** (see `LICENSE`).
It bundles the components below, each under its own license. SceneForge's source code, including
the build scripts that fetch these components, is at https://github.com/EzioDEVio/SceneForge.

## Bundled in the installers
| Component | License | Notes |
|---|---|---|
| FFmpeg / ffprobe (separate executables) | GPL-3.0 builds (FFmpeg is LGPL/GPL; these builds enable GPL parts such as libx264) | Windows: Gyan "essentials" 8.1.2 (https://www.gyan.dev/ffmpeg/builds/). Linux: BtbN FFmpeg-Builds n8.1 linux64 GPL (https://github.com/BtbN/FFmpeg-Builds). macOS: ffmpeg-static (https://github.com/eugeneware/ffmpeg-static). The exact download URL and SHA-256 are recorded in `resources/ffmpeg/DOWNLOAD.txt`; upstream license files accompany the binaries where provided. **Corresponding source:** FFmpeg source for every release is at https://ffmpeg.org/download.html and each builder publishes its build scripts at the links above. On request we will provide the corresponding source for the exact FFmpeg build shipped with a SceneForge release (open an issue on GitHub). |
| Electron (Chromium, Node.js) | MIT, plus Chromium's notices shipped by Electron (`LICENSES.chromium.html`) | https://www.electronjs.org |
| Python runtime | PSF License | Bundled privately by PyInstaller |
| FastAPI, Starlette, Uvicorn, Pydantic, SQLAlchemy | MIT / BSD | Backend web server and database |
| NumPy | BSD-3-Clause | Colour grading, audio analysis |
| OpenCV (opencv-python-headless) | Apache-2.0 | 3D photo and photo restore |
| Pillow | MIT-CMU (HPND) | Image handling |
| keyring, requests and other Python dependencies | MIT / Apache-2.0 / BSD | See `backend/requirements.txt` |
| React, lucide-react and frontend dependencies | MIT / ISC | See `frontend/package.json` |
| electron-updater | MIT | Automatic updates from GitHub Releases |
| Noto Sans, Noto Naskh Arabic, Noto Sans Arabic | SIL Open Font License 1.1 | `assets/fonts/OFL-LICENSE.txt` |
| Synthetic typewriter sound | Generated for SceneForge | `assets/sfx/SOURCE.md` |

## Not bundled
AI models and engines are **not** included in the installers. Optional local engines (Stable Diffusion
via AUTOMATIC1111, Chatterbox, Kokoro) and any models you download keep their own licenses, which may
restrict commercial use. Cloud providers (OpenAI, Google Gemini, ElevenLabs, Together, Cloudflare,
Hugging Face) are used only with your own account and are subject to their terms.

## Warranty
SceneForge Studio comes with ABSOLUTELY NO WARRANTY, to the extent permitted by law (GPL-3.0 sections 15–16).
