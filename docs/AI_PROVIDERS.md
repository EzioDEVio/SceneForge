# AI providers and prices

Back to the [README](../README.md) · [Feature guide](FEATURES.md)

AI is optional. You can build a complete video from your own photos, clips and recordings without any account.

| Purpose | Cloud (your own account and key) | Local (free, on your computer) |
|---|---|---|
| Images | OpenAI, Google Gemini, Cloudflare Workers AI, Hugging Face | Stable Diffusion 1.5 (one-click install in **AI Engines**, no Docker), or your own AUTOMATIC1111 |
| Voice | ElevenLabs (with exact word timing), Gemini voices, Together AI | Kokoro (built in), Chatterbox (one-click, no Docker), Voicebox (optional app); espeak as an optional robotic diagnostic voice |
| Captions | OpenAI Whisper, ElevenLabs Scribe | Faster-Whisper (model downloads once) |
| Voice isolation, subject cutout | — | Local ONNX models (see above) |
| Text-to-video | Google Veo 3.1, Runway Gen-4.5 and WAN 3.0 | ComfyUI workflows for LTX-2.5, Wan 2.1, Wan 2.2 and custom workflows |

## Text-to-video prices

This table shows the provider's published USD rate per generated second, as listed in the app's catalog. The prices were **checked on 2026-09-29** and can change. Provider billing, taxes, credits, retries and regional terms can change the final charge. Local generation has no API fee, but it uses your hardware and electricity. Check each model's license before you publish or use its output commercially.

| Provider and model | Published price | Output options in SceneForge |
|---|---:|---|
| Google Veo 3.1 Lite | $0.05/sec at 720p; $0.08/sec at 1080p | 4, 6 or 8 s; 16:9 or 9:16; 1080p only at 8 s |
| Google Veo 3.1 Fast | $0.10/sec at 720p; $0.12/sec at 1080p; $0.30/sec at 4K | 4, 6 or 8 s; 16:9 or 9:16; 1080p and 4K only at 8 s |
| Google Veo 3.1 Standard | $0.40/sec at 720p or 1080p; $0.60/sec at 4K | 4, 6 or 8 s; 16:9 or 9:16; 1080p and 4K only at 8 s |
| Runway Gen-4.5 | $0.12/sec (12 credits/sec at $0.01 per credit) | 2–10 s at 720p; 16:9 or 9:16 |
| Runway WAN 3.0 | $0.05/sec at 480p; $0.10/sec at 720p; $0.20/sec at 1080p | 2–30 s; 16:9 or 9:16; native audio |

Price references: [Google Veo pricing](https://ai.google.dev/gemini-api/docs/pricing#veo), [Veo API options](https://ai.google.dev/gemini-api/docs/veo), [Runway API pricing](https://docs.dev.runwayml.com/guides/pricing/), [Runway API changelog](https://docs.dev.runwayml.com/api-details/api_changelog/). Key setup: [Google AI Studio API keys](https://aistudio.google.com/app/apikey) ([instructions](https://ai.google.dev/gemini-api/docs/api-key)), [Runway API setup](https://docs.dev.runwayml.com/guides/setup/) ([Dev console](https://dev.runwayml.com/)).

**Local setup notes**

- Install and start ComfyUI yourself, then connect its loopback address under **AI Engines → AI providers · API keys**.
- In ComfyUI, load the model's workflow and export it with **File → Export Workflow (API)**. Older versions call this **Save (API Format)**. Import the JSON into Generate video.
- Custom ComfyUI nodes run inside ComfyUI with your user permissions. Only import workflows and nodes you trust.
- Custom local dimensions must be multiples of 16.
- On an 8 GB GPU, start at 480p with Wan 2.2 5B (ComfyUI's native offloading) or the lighter Wan 2.1 1.3B. See the [Wan 2.2 setup](https://docs.comfy.org/tutorials/video/wan/wan2_2) and the [LTX ComfyUI setup](https://docs.ltx.io/open-source-model/integration-tools/comfy-ui).
- Takes are generated one after another. Each finished take is saved in the Media Pool, and completed takes are kept if a later one fails.
- Vast.ai remote GPUs are only a proposal and are not connected to the app. See [docs/VAST_GPU_RELAY_PROPOSAL.md](dev-notes/reviews/VAST_GPU_RELAY_PROPOSAL.md).

## What is bundled and what downloads on first use

| Component | Size | How you get it |
|---|---|---|
| App, private Python backend, FFmpeg | — | Bundled in the installer |
| Fonts (Noto, Poppins, Bebas Neue, Anton, Pacifico, Amiri, Tajawal, Lalezar) and 400 stickers | — | Bundled |
| Cutout model U²-Net small (`u2netp`) | ~4.6 MB | Bundled *(0.7.0)* |
| Local Whisper captions (Faster-Whisper `base`) | ~145 MB | Downloads on first use |
| Cutout model IS-Net general use | ~170 MB | Downloads on first use, checked by checksum *(0.7.0)* |
| Cutout model People (U²-Net human) | ~176 MB | Downloads on first use, checked by checksum *(0.7.0)* |
| Voice isolation model (MDX-Net Kim_Vocal_2) | ~67 MB | Downloads on first use, checked by checksum *(0.7.0)* |
| Kokoro voices (built in) | ~120 MB | Downloads once, checked by checksum *(0.9.4)* |
| Chatterbox voices, Stable Diffusion | ~3 GB / ~6 GB | One-click install in AI Engines, in SceneForge's own folder, no Docker *(0.9.4)* |
| AUTOMATIC1111 (optional), ComfyUI and video models | varies | Installed separately by you |

Downloaded models are kept in `%USERPROFILE%\.sceneforge\models\{whisper,cutout,voice}` (or `~/.sceneforge/models/…`). Provider keys are stored in the operating system's credential store (Windows Credential Manager, macOS Keychain, Linux Secret Service), never in project files.
