# SceneForge Desktop Alpha — proposed delivery plan

Status: architecture proposal, not an implemented installer. Workspace 2.5 remains the source baseline.

## Product experience
One SceneForge download per supported operating system/architecture. A guided setup checks available disk, RAM and supported GPU, asks which local AI features to install, installs verified runtime packs, downloads selected model weights with progress and resume, runs a short health check, and opens the editor. No terminal, global Python/Node installation, or Docker Desktop is required in the target consumer workflow.

Core editing, importing existing media and exporting video must work without AI engines. Local voice and local image generation are selectable components. A Complete setup option installs both where supported. Show actual download sizes and hardware requirements from a versioned manifest before downloading. Internet is needed for the online setup and hosted providers; an offline bundle can carry the same runtime/model packs where redistribution permits.

## Packaging design
Recommended starting architecture: Tauri desktop shell, existing React UI, packaged FastAPI/Python backend, bundled FFmpeg/ffprobe and fonts, isolated native voice and image workers. Validate MP4 playback in each platform webview before committing to the shell; Electron is a fallback if media compatibility blocks Tauri.

Do not wrap the existing collection of batch scripts as the final installer. Windows-specific process launchers must become a cross-platform service supervisor. Compile the backend separately on each target OS. Pin Python, Python wheels, FFmpeg build, engine versions, models and checksums. Do not run unbounded pip installs or git pulls during customer installation.

Tauri supports platform installers and packaged external executables:
- https://tauri.app/distribute/
- https://tauri.app/develop/sidecar/
- https://pyinstaller.org/en/stable/

## Components
| Component | Desktop handling |
| --- | --- |
| React frontend | Prebuilt assets inside desktop package |
| FastAPI backend | Private packaged Python runtime/executable |
| FFmpeg and ffprobe | Platform-specific binaries with required codecs and subtitle shaping |
| Chatterbox | Native worker with isolated dependency pack; retain Docker adapter for advanced existing installations |
| Stable Diffusion | Versioned native inference worker and selected checkpoint; retain existing AUTOMATIC1111 connection as advanced option |
| Model weights | Shared per-user model directory; downloadable, resumable and hash-verified |
| Credentials | OS credential store; remove reversible obfuscation as the production default |
| Projects and exports | User data directory separate from installed application files |

Docker is a current deployment mechanism for speech, not a requirement of the model itself. Existing image integration uses a local AUTOMATIC1111 installation. Native replacements require testing; do not claim that changing the installer alone provides GPU compatibility.

## Hardware and platforms
Start with Windows x64. Add macOS Apple Silicon and a defined Linux x64 baseline after clean-machine tests. Consider Intel Mac and other architectures only after dependency verification. Choose CUDA, Metal/MPS, or CPU according to the actual supported engine/runtime combination. AMD/Intel acceleration requires separately verified support. A package installing successfully does not prove its selected model will fit memory or run at an acceptable speed. Display CPU performance limitations and permit hosted providers/import-only usage.

Planned output formats: Windows setup EXE and MSI for managed deployment; macOS signed/notarized app in DMG (PKG if needed for a guided installer); Linux AppImage and DEB with distro/runtime requirements documented. Build/test each supported OS in its own CI runner; the Python backend is not cross-compiled by PyInstaller.

## Runtime lifecycle
- Single app instance, controlled child processes, health checks and crash recovery.
- Start AI workers on demand; stop only processes owned by SceneForge.
- Bind API to loopback, use per-launch authentication, restrictive origins and dynamic port negotiation.
- GPU-memory coordination prevents image and voice workers from exhausting VRAM together.
- Component manager supports install, repair, update and remove without deleting projects.
- Install/update uses staging and rollback; preserve old runtime until the replacement passes health checks.
- Uninstall removes application files; deleting user projects/models is an explicit separate choice.

## Release gates
1. Publish reviewed Workspace 2.5 source and preserve history.
2. Build Windows Desktop Alpha with packaged core; test on a machine with no development tools.
3. Deliver native voice/image component packs and guided online installation.
4. Validate render, Arabic shaping, narration, image generation, updates, interrupted downloads and uninstall.
5. Build/test macOS and Linux packages on supported hardware.
6. Sign releases, configure updates and publish installers as GitHub Release assets.

Before redistribution, select a project license and inventory third-party licenses, model redistribution terms, notices and corresponding-source obligations for the chosen FFmpeg build. Signing credentials belong in CI secrets; never in source. The private source repository can remain private, but public customers need an accessible release/update download channel.
