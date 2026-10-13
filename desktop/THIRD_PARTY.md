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
| Poppins, Bebas Neue, Anton, Pacifico, Amiri, Tajawal, Lalezar (from github.com/google/fonts) | SIL Open Font License 1.1 | `assets/fonts/licenses/OFL-*.txt` |
| Synthetic typewriter sound | Generated for SceneForge | `assets/sfx/SOURCE.md` |
| Twemoji emoji graphics (322 emoji in `assets/stickers/emoji/`, rasterised to PNG from Twemoji v17.0.3 SVGs) | CC-BY 4.0 — Copyright Twitter, Inc. and other contributors; https://github.com/jdecked/twemoji | `assets/stickers/LICENSE-TWEMOJI-GRAPHICS.txt`. Fetched and rasterised by `scripts/build_sticker_library.py`. |
| Route artwork (plane, ship, car, pin) | Twemoji graphics, CC-BY 4.0 | Reused bundled PNGs; `assets/route-icons/SOURCE.md` and the existing Twemoji license. |
| Graphic stickers (badges, arrows, speech bubbles, shapes, social buttons in `assets/stickers/graphics/`) | Drawn for SceneForge (GPL-3.0-or-later) with the bundled OFL fonts | `scripts/build_sticker_library.py` |

## Not bundled
The installer build fetches and verifies U2-Net small (`u2netp.onnx`, approximately 4.6 MB, Apache-2.0) for subject cutout; see `desktop/scripts/fetch_models.py`. Large generative AI engines and their models are not bundled. Optional local engines (Stable Diffusion
via AUTOMATIC1111, Chatterbox, Kokoro) and any models you download keep their own licenses, which may
restrict commercial use. Cloud providers (OpenAI, Google Gemini, ElevenLabs, Together, Cloudflare,
Hugging Face) are used only with your own account and are subject to their terms.

## Warranty
SceneForge Studio comes with ABSOLUTELY NO WARRANTY, to the extent permitted by law (GPL-3.0 sections 15–16).

## Additional bundled fonts

DejaVu Sans/Serif/Mono retain their upstream notices in
assets/fonts/licenses/DejaVu-LICENSE.txt (Bitstream/DejaVu terms).
Latin Modern Sans/Roman/Mono/Slanted/Demi Cond/Caps retain their original
font names and GUST Font License/LPPL notices in
assets/fonts/licenses/Latin-Modern-LICENSE.txt. Unmodified font files and
notices are also included in frontend/public/fonts.

The local AI installer downloads SD 1.5 and Chatterbox components after terms
review (0.9.4-beta.3: no Docker). It fetches uv 0.13.0 (Astral, MIT or
Apache-2.0, pinned SHA-256 per platform), which installs a private CPython 3.11
(python-build-standalone, PSF license) and the services' Python packages,
including PyTorch (BSD-3-Clause), into SceneForge's engines folder.

Built-in Kokoro voices (0.9.4-beta.3) bundle kokoro-onnx (MIT), phonemizer
(GPL-3.0) and espeakng-loader with the espeak-ng library (GPL-3.0); the
Kokoro-82M model (Apache-2.0) and voice pack download once from the
kokoro-onnx release, checked by SHA-256. Optional Voicebox (MIT) is a separate
app installed by the user; SceneForge only talks to its local API. Gemini voices
are a Google service used with the user's own API key. See LOCAL_AI_INSTALLER.md for their sources,
terms, storage, GPU/CPU behavior and Windows validation requirements.

psutil (BSD-3-Clause, 0.9.4-beta.7) identifies which program holds an engine port, so
SceneForge replaces only its own leftover engines and never closes other programs.
