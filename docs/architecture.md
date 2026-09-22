# SceneForge Studio — Architecture Notes (M0/M1)

This is the M0 architecture record required by the specification, updated
as of the M1 delivery. It documents what was actually decided and built,
not the full aspirational architecture from the spec (section 7) — deltas
are called out explicitly.

## Stack

| Layer | Choice | Version (pinned) |
| --- | --- | --- |
| Frontend | React 18 + TypeScript + Vite | see `frontend/package.json` |
| API | Python 3.11+ / FastAPI | `fastapi==0.141.1` (see `backend/requirements.txt`) |
| DB | SQLite via SQLAlchemy 2.0 | `SQLAlchemy==2.0.53` |
| Media | FFmpeg / FFprobe subprocesses | user-installed (see docs/environment.md) |
| Captions | libass + HarfBuzz + FriBidi (via FFmpeg's `ass` filter) | bundled Noto Naskh/Sans Arabic fonts |
| Local narration (no key) | espeak-ng | user-installed |
| Packaging | `.bat` / `.ps1` scripts | see `scripts/` |

## Why these choices

- **SQLite, not Postgres**: M1 is a local single-user application; SQLite
  with WAL mode gives us transactional, file-based persistence with zero
  setup, matching "no mandatory cloud account." Foreign keys are enforced
  via `PRAGMA foreign_keys=ON`.
- **FFmpeg subprocesses, not MoviePy**: MoviePy wraps FFmpeg anyway and
  adds a Python-side frame-buffering layer we don't need; direct subprocess
  control gives us real progress via `-progress`, precise cancellation via
  process-group kill, and argument-array invocation (no shell injection
  surface — see `app/render/ffmpeg_utils.py`).
- **In-process background jobs, not a separate worker process (deviation
  from spec section 7)**: the spec calls for "a separate native Python
  process with durable DB-backed job claims." M1 ships the DB-backed job
  *record*, lease-like cancellation flag, and durable progress/status
  persistence — but the job executes in a background thread within the
  API process, not a separate OS process. This was a deliberate scope cut
  to prioritize a *working, tested* render pipeline over process
  separation for M1. The job table schema (`render_jobs`) was designed so
  a future dedicated worker process can claim rows without a schema
  change — see "Follow-ups" below.
- **espeak-ng for offline narration**: gives us a completely credential-
  free, real TTS engine to prove the full script → narration → timed
  captions → rendered MP4 pipeline without requiring any cloud account for
  M1, as the spec explicitly allows ("Use recorded or licensed sample
  narration to test offline. No provider key is required for this
  milestone"). It is explicitly NOT the Arabic voice-quality deliverable
  from section 6/M4 — see docs/known-limitations.md.

## Render pipeline (implemented)

```
scene shots (image/video) --per-shot--> zoompan motion + effect + fit
                                          (filter_complex, libx264)
        |
        v
  concat shots (if >1) --> scene_visual.mp4
        |
        v
  burn captions (.ass via libass, RTL-correct) --> scene_captioned.mp4
        |
        v
  mux narration audio with lead/trail silence handles --> part_final.mp4
        |
        v
  [Export] concat/xfade parts with per-boundary transitions
           (settb-normalized timebases; SAR pinned to 1:1)
        |
        v
  final MP4 (H.264/AAC), probed+decode-validated before being
  marked as the job's artifact
```

Preview and export share this exact compiler — there is no separate
"cheap preview" code path that could visually diverge from the real
export, per spec section 11.

## Cache keys / invalidation (`app/render/timeline.py`)

Three independent SHA-256 hashes per scene — `visual` (shots + crop +
motion + fit + effect), `audio` (accepted take's audio content hash),
`caption` (subtitle text + font) — combine into one `plan_hash`. A part is
stale iff `scene.rendered_plan_hash != current plan_hash`. This was
verified empirically (`examples/run_m1_workflow.py`): changing a shot's
motion marks only that scene stale; sibling scenes' hashes are untouched.

## Security posture implemented

- FFmpeg/FFprobe are invoked with argument arrays only, never a shell
  string (`app/render/ffmpeg_utils.py`) — user-supplied script text and
  filenames cannot break out into shell metacharacters.
- Uploaded filenames are never used for storage — every asset gets a
  fresh UUID-based filename (`app/security/uploads.py`); the original
  name is kept only as metadata.
- Uploads are validated by actually decoding them with FFprobe (not just
  trusting the extension) before being registered as assets.
- CORS is restricted to the known local dev/prod origins; the API binds
  to `127.0.0.1` by default (see `scripts/start.*`).
- Provider secrets: no cloud provider is wired up yet in M1 (see
  capability-matrix.md), so there is nothing to store yet; the
  `provider_profiles` table exists with a `secret_ref` column (a
  reference key, never a plaintext secret column) ready for the OS-vault
  integration promised for M2.

## Known deviations from the full spec (tracked, not hidden)

1. **Worker process separation** (above) — in-process thread, not a
   separate OS process. Tracked for a post-M1 pass.
2. **No Alembic migrations yet** — `Base.metadata.create_all()` is used
   as the M1 migration mechanism. Fine for a schema that only grows; a
   real migration tool is needed before any backward-incompatible schema
   change ships.
3. **Shot-to-shot transitions within a single scene are hard cuts only**
   — the spec's multi-shot-per-scene transition richness is deferred to
   M4 ("multi-shot scenes"). Inter-*part* transitions (cut/dissolve/fade)
   are fully implemented and tested.
4. **Crash resume is not automatic** — a job's status/progress survive a
   crash (they're persisted after every stage), so an operator can see a
   stuck "running" row, but nothing currently re-claims and resumes it
   automatically on the next startup. Tracked for the worker-process pass.
5. **Pause is not implemented** — only queued/running/cancelling/
   cancelled/failed/succeeded; the spec's "pause at documented stage
   boundaries" is not built in M1.

See `docs/capability-matrix.md` for the full per-feature status table and
`docs/known-limitations.md` for everything not yet validated.
