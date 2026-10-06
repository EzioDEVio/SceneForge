# Local AI installation — Windows test build

The Windows NSIS installer now offers Whisper, Stable Diffusion and Chatterbox
on a component page. All three are selected initially. Review the linked
component terms before continuing. The installer log shows installation stages
and the tools' download/build output. The editor remains usable if an AI
component fails; open **AI Engines → Set up free local AI → Retry**.

The checkpoint ZIP includes source and compiled editor, not a Windows EXE.
Use GitHub Actions → Release → Run workflow after reviewing/pushing the source
to create installer test artifacts. Manual workflow runs use `--publish never`.
No push, tag or publication was performed by this change.

## Components

- Whisper: Faster-Whisper multilingual base, approximately 145 MB. Installed
  through the existing loader, with a real model-load check. No Docker required.
- Stable Diffusion: managed SD 1.5 service compatible with SceneForge's local
  image adapter. Uses Diffusers 0.32.2 and the model repository at revision
  `451f4fe16113bff5a5d2269ed5ad43b0592e9a14`. The model safety checker is retained.
  CPU mode is slow; the NVIDIA option requests Docker GPU access. Existing
  AUTOMATIC1111 connections and installations remain supported.
- Chatterbox: existing isolated multilingual bridge, with a new warmup/model
  load check. CPU runtime; Arabic and English remain available.

Image and voice services use Docker Desktop (Linux containers). If missing,
the Windows installer requests installation through Windows App Installer
(winget). Windows can ask for administrator approval, Docker's initial setup,
WSL configuration or restart. These cannot be silently bypassed. Such cases
show a repair/retry message, rather than claiming installation succeeded.
CPU/GPU models, Python dependencies and Docker images download from upstream;
they are not contained in the small checkpoint ZIP. Allow at least 15 GB free
space (checked before setup); initial runtime/model downloads can take a long
time. Component progress measures completed checks, not fabricated download
percentages. Whisper-only setup needs 500 MB free space.

The fixed Compose project `sceneforge-managed-ai` and named volumes preserve
models across app updates. The image and voice APIs bind only to loopback.
Local providers are registered after successful readiness checks; existing
user provider connections are not overwritten. Startup only starts installed
containers and loads their cached models; it does not install Docker or rebuild
images. The owner can turn automatic startup off in the setup section.

## Terms

- Docker: https://www.docker.com/legal/docker-subscription-service-agreement/
- SD model: https://huggingface.co/spaces/CompVis/stable-diffusion-license
- Chatterbox: https://github.com/resemble-ai/chatterbox/blob/master/LICENSE
- Faster-Whisper: https://github.com/SYSTRAN/faster-whisper/blob/master/LICENSE

Docker eligibility/subscription terms depend on the user's organization.
Stable Diffusion's OpenRAIL-M terms accompany the downloaded model. These
are separate component terms; the editor's GPL license does not replace them.

## Windows acceptance checks (required before publication)

1. Fresh Windows installation: component selection, terms links, cancel/back,
   empty selection/editor-only, and install progress. No cloud key required.
2. Whisper: model installs during setup; disconnect internet, generate English
   and Arabic captions, then restart and repeat without redownloading.
3. Chatterbox: confirm actual model readiness, synthesize English and Arabic,
   restart SceneForge, and verify the voice remains connected.
4. Stable Diffusion: verify actual model readiness and generate an image with
   SD 1.5, hires off. Test CPU and NVIDIA modes on supported hardware. Managed
   SD does not provide WebUI extensions, SDXL or hires refinement; connect a
   separate WebUI for those existing features.
5. Interrupted download/Docker first-run/reboot/insufficient disk/offline:
   show the reason, preserve projects, Retry completes cached work. Do not
   close while installation is active; desktop close readiness blocks exit.
6. Upgrade: keep model volumes, existing WebUI/provider configuration, projects
   and the chosen startup setting. No installer may silently switch it off.
7. Occupied ports: explain the conflict, never replace an unrelated service.
8. Native installer/Batch/PowerShell/credential-store/GPU and live local-model
   acceptance remain untested in the Linux development environment.
