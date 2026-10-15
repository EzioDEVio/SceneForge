# Security review — 15 October 2026

GitHub showed 42 Dependabot alerts (mostly critical and high) and 53 code-scanning alerts on
`main`. This review reproduced both locally (pip-audit and `npm audit` on every manifest, and
CodeQL with GitHub's default `code-scanning` query suites for Python, JavaScript/TypeScript and
Actions), fixed what was real, and records why the rest are safe to dismiss.

## Dependencies (Dependabot)

| Manifest | Before | After |
|---|---|---|
| `services/stable-diffusion/requirements.txt` | diffusers 0.32.2, transformers 4.49.0, accelerate 1.4.0, Pillow 11.1.0 — about 38 advisories | diffusers 0.41.0, transformers 5.17.0, accelerate 1.15.0, Pillow 12.3.0, safetensors 0.8.0, FastAPI 0.143.2, Uvicorn 0.54.0 — none known |
| `backend/requirements.txt` | `Pillow>=10,<13` (allowed vulnerable versions) | `Pillow==12.3.0`; the installed environment has no known vulnerabilities |
| `services/chatterbox/requirements.txt` | FastAPI, Uvicorn, soundfile unpinned | pinned to current releases |
| `frontend/package-lock.json` | source-map-js (high) | updated |
| `desktop/package-lock.json` | http-cache-semantics (high), global-agent → roarr → sprintf-js (moderate) | npm `overrides`: http-cache-semantics 4.3.0, global-agent 4.1.3 (same `bootstrap` API, no roarr) |

Why transformers 5.17 and not the newest: from 5.18, transformers calls
`torch.accelerator.current_accelerator()` at import, which with torch 2.6.0 raises when no CUDA
device is available — Stable Diffusion would fail on computers that use the processor. 5.17.0
has no known advisories. The upgraded engine was checked by running `services/stable-diffusion/server.py`
against a small locally built model with the same components as SD 1.5 (health, warmup with
the safety checker, the DPM-Solver scheduler, a 256×256 image, the same seed giving the same
image, hires refused).

Not covered by Dependabot, noted for later:

- **torch 2.6.0** (installed by SceneForge for both engines) has advisories fixed in 2.7–2.13.
  Chatterbox (`chatterbox-tts` 0.1.7) requires exactly 2.6.0. The engines only load pinned
  safetensors weights and listen on 127.0.0.1.
- **chatterbox-tts 0.1.7** pins diffusers 0.29.0 and transformers 5.2.0 internally. They
  change only when Chatterbox publishes a new release.

## Code scanning (CodeQL)

Local scan of the same commit: 49 alerts (GitHub's 53 includes alerts from earlier commits that
close when the code changes). After the fixes: 10, all reviewed below.

Fixed:

- **Path injection (30):** every path built from a project id, file name, sticker id, model id
  or restore-point id now goes through `app/security/paths.py:safe_join`, which refuses
  anything outside its folder (also `..`, absolute paths and NUL bytes); refused requests get 400.
- **Server-side request forgery (2):** the Voicebox address is limited to this computer, both
  when it is set and when it is used.
- **Polynomial ReDoS (2):** stage-direction patterns in the script parser are bounded;
  280 KB of "(pause " took 5 s before and 0.04 s after.
- **Command-line injection (2):** the espeak voice comes from a fixed list; the FFprobe path
  comes from `safe_join`.
- **XSS through DOM / incomplete sanitisation / URL substring (3):** asset ids are URL-encoded
  in stream links; two test helpers use proper escaping and matching.

Safe to dismiss on GitHub (Security → Code scanning → the alert → Dismiss alert):

| Alert | Where | Dismiss as | Reason |
|---|---|---|---|
| Information exposure through an exception (8) | `backend/app/api/images.py` (2), `local_speech.py` (2), `video_cutout.py`, `services/*/server.py` (3) | Won't fix | The message is shown on purpose so people can fix the problem themselves (for example the Chatterbox and Stable Diffusion engine errors). The backend and the engines listen only on 127.0.0.1; the desktop app also requires a per-launch token. No traceback is returned, only the error message. |
| Uncontrolled data used in path expression (1) | `backend/app/local_images.py` | Won't fix | The user chooses the folder of their own AUTOMATIC1111 installation on their own computer; the folder must contain `webui-user.bat`. |
| Clear-text logging of sensitive information (1) | `tests/integration/test_071_usability.py` | Used in tests | The test logs a planted fake key on purpose to check that diagnostics redact it. |
