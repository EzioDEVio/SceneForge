# M0 — Environment Confirmation & Scoped Backlog

## Environment confirmed (development sandbox)

| Tool | Version found | Notes |
| --- | --- | --- |
| Python | 3.12.3 | Spec requires 3.11+ |
| Node.js | 22.22.2 | Spec requires 18+ LTS |
| FFmpeg | 6.1.1 | Built with libass, libfribidi, libharfbuzz, libx264, libx265 — all required for RTL captions and H.264 export |
| FFprobe | 6.1.1 | Same build as FFmpeg |
| espeak-ng | 1.51 | Optional; enables credential-free narration for M1 proof |

Windows-specific installation steps and prerequisite links are in the
root `README.md`. This development session ran on Linux (see
`docs/test-report.md` for exact CPU/OS details) — Windows itself was not
available to test against in this session; the `.bat`/`.ps1` scripts and
Windows-specific code paths (process-tree kill via `taskkill /F /T`,
`CREATE_NEW_PROCESS_GROUP`) were written correctly per documented Windows
subprocess semantics but **not executed on real Windows** this session.
Please verify `scripts\setup.bat` and `scripts\start.bat` on an actual
Windows machine before relying on them.

## Dependency pinning

- Backend: `backend/requirements.txt`, generated from an actual working
  `pip freeze`, then hand-edited to remove `uvloop` (Unix/macOS-only —
  confirmed by testing a from-scratch install without it).
- Frontend: `frontend/package.json` uses caret ranges (`^18.3.1` etc.),
  with a committed nature via `package-lock.json` — regenerate the lock
  file if dependencies change (`npm install` in `frontend/`).

## License obligations

- **MoneyPrinterTurbo** (MIT) — reviewed for architectural ideas only,
  per the project brief; no code copied. If any code is copied in a
  future milestone, its original copyright/license notice must travel
  with it (MIT requirement).
- **Noto Naskh Arabic / Noto Sans Arabic** fonts — SIL OFL 1.1, bundled
  under `assets/fonts/`, license file included alongside.
- **espeak-ng** — GPL-3.0-or-later, used as an external system tool (the
  user installs it separately), not bundled/vendored into this
  repository, so its license does not propagate to this codebase.
- **FFmpeg** — LGPL/GPL depending on build configuration; not bundled —
  the user installs their own build per the README, so the specific
  build's license terms are the user's responsibility to check (a
  concern the spec explicitly calls out: "Handle codecs according to the
  chosen distributable FFmpeg build and its notices").
- No bundled stock music or stock footage is included anywhere in this
  repository.

## Scoped backlog (beyond M1)

See `docs/capability-matrix.md` for the full per-feature status and
`docs/known-limitations.md` for what's explicitly deferred. Backlog is
otherwise ordered per the spec's own milestone sequence (M2 BYOK
image/voice → M3 online media/provider expansion → M4 documentary editing
quality → M5 Windows packaging/installer → M6 optional hosted product).

Immediate next-milestone scope (M2), bounded per spec section 17 ("Do not
require a new architecture discussion unless evidence reveals a real
blocker"):
1. Secure settings UI + OS-vault-backed `ProviderProfile` storage.
2. One documented image-generation adapter (`ImageProvider`).
3. One documented Arabic-capable cloud TTS adapter (`SpeechProvider`).
4. Wire the existing image-chat drawer and voice panel UI to these real
   adapters (both UIs already exist and correctly report "not
   configured" today — M2 is about making that configuration possible
   and real, not building new UI surface).
