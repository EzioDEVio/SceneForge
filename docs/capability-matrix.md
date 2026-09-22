# Capability Matrix

Status legend: ✅ implemented & tested this session · 🚧 partially built ·
⛔ not started (planned milestone noted) · N/A not applicable to M1.

## Editor / workspace (spec section 5)

| Capability | Status | Notes |
| --- | --- | --- |
| Horizontal part-row layout (Part-1/2/3, script/add+/motion/effects/font/generate) | ✅ | Matches the supplied `UI_FOR_VIDEO_GENERATOR.png` mockup structure exactly |
| Add script (multiline, RTL/mixed-language) | ✅ | `dir="auto"` textarea; Arabic verified in fixture |
| Add + media (upload / existing asset / search / generate) | 🚧 | Upload ✅. "Existing asset library" browse UI not built (data model supports it — every asset already belongs to the project). Online search ⛔ (M3). AI image generation ⛔ (M2, no provider yet) |
| Multiple shots per part, reorder | 🚧 | Backend fully supports N shots/scene with order_index; UI shows a thumbnail strip but has no drag-reorder yet (add/remove only) |
| Motion controls (zoom in/out, close-up, pan ×4, Ken Burns) | ✅ | Real, deterministic `zoompan`-based rendering, verified on both image and video shot types |
| Image effects (2×4 grid, 8 presets) | ✅ | Real FFmpeg color-grade filters (sepia, B&W, warm, cool, vintage, vignette, soft glow), selectable with intensity; "Original" disables others |
| Font + (family/size/color/outline/background/position) | ✅ | Burned via libass `.ass` file; bundled Arabic-capable fonts (Noto Naskh/Sans Arabic) |
| Generate (per-part, independent) | ✅ | Verified: generating Part-2 does not touch Part-1/3's stored hash or asset |
| Export full video (assembles current part revisions + transitions) | ✅ | Verified with a mixed cut + dissolve export, decodable start/mid/end |
| Voice settings / audition per part | ✅ (local offline only) | espeak-ng audition + take generation + accept; cloud TTS ⛔ (M2) |
| Image-only mini chat drawer | 🚧 | UI present, scoped correctly (visual brief only, no narration access), but reports "no provider configured" rather than faking a result — no image-generation provider exists yet (M2) |
| Reorder parts, add part, delete part | ✅ | |
| Aspect ratio selection (16:9 / 9:16 / 1:1) | ✅ | |

## Import / script handling (section 9)

| Capability | Status |
| --- | --- |
| TXT/Markdown import with heading detection (Arabic + English) | ✅ |
| Preserves unmatched text (never silently drops) | ✅ |
| Citation markers preserved, stripped from spoken/subtitle text | ✅ |
| Manual scene creation without import | ✅ |
| LLM-assisted splitting | ⛔ (M2+, needs a text provider) |

## Rendering & jobs (section 11)

| Capability | Status | Notes |
| --- | --- | --- |
| Audio-driven scene duration + lead/trail handles | ✅ | |
| Motion (Ken Burns family) on images AND real video | ✅ | Verified on both in the fixture |
| Fit modes: cover / contain / contain+blur | ✅ | cover exercised in fixture; contain paths implemented, not covered by an automated test this session |
| Effects with intensity blending | ✅ | |
| RTL caption burn-in, correct shaping | ✅ | libass+HarfBuzz+FriBidi; bundled fonts |
| Per-part independent regeneration | ✅ | |
| Full export with inter-part transitions (cut/dissolve/fade) | ✅ | cut + dissolve both exercised; fade_through_black implemented via the same xfade path, not separately tested |
| Dependency-aware invalidation (crop change ≠ re-synthesize audio) | ✅ | Verified: changing motion marks only that part stale |
| Real job progress via FFmpeg `-progress` | ✅ | |
| Cancellation kills the process tree (no orphan ffmpeg) | ✅ | Verified: cancelled job reaches `cancelled` status; confirmed-PID ffmpeg process is gone afterward |
| Persistence across process restart | ✅ | Verified: killed and restarted the backend process; project/scenes/shots/voice takes/rendered assets all reloaded and rendered files still decode |
| Pause | ⛔ | Not implemented in M1 |
| Automatic crash-resume of a stuck "running" job | ⛔ | Status/progress persist for an operator to see; no auto-reclaim yet |
| Separate durable worker OS process | ⛔ | Runs in-process (background thread) in M1 — see architecture.md |

## Providers (section 10)

| Capability | Status |
| --- | --- |
| Uploaded media (image/video/audio) | ✅ |
| Local offline TTS (espeak-ng) — explicitly NOT the Arabic quality gate | ✅ |
| Cloud image generation adapter | ⛔ (M2) |
| Cloud Arabic-capable TTS adapter | ⛔ (M2) |
| Pexels / Pixabay stock search | ⛔ (M3) |
| Local ComfyUI | ⛔ (M3) |
| Provider credential storage (OS vault) | ⛔ (M2) — `provider_profiles` table schema exists with a `secret_ref` column, no vault wired up yet |

## Validation performed this session (spec section 16)

| # | Check | Result |
| - | --- | --- |
| 1 | Import Arabic/English format without reading prompts/citations aloud | ✅ (parser strips bracket stage-directions and citation markers from spoken/subtitle text; not run against the specific 14-scene sample document, since none was supplied) |
| 2 | Malformed import retains all text for repair | ✅ (unit-level: parser returns full original block as `original_text` with a warning when no template matches) |
| 3 | RTL captions render correctly (names, punctuation, numbers) | 🚧 Rendered and visually spot-checked via libass; not put through an automated glyph-level shaping assertion |
| 4 | Two differently sized images + a variable-frame-rate video → correct canvas/fps | 🚧 Two differently-sized synthetic images ✅ (1600×1000 → project canvas); VFR-specific source not tested this session (fps-normalization code path exists and runs on every video shot regardless) |
| 5 | Audio-driven timings with transitions and multiple shots | ✅ (single-shot parts, both cut and dissolve transitions); multi-shot-per-scene timing not covered by an automated test this session |
| 6 | Probe MP4 streams; decode start/middle/boundary/end; listen to audio | ✅ | 
| 7 | Simulate missing codec / zero-byte media / full disk / invalid key / timeout / 429 / invalid media | ⛔ Not run this session (see known-limitations.md) |
| 8 | Cancel rendering, verify no orphan FFmpeg | ✅ |
| 9 | Restart during a job; avoid duplicate remote generations; recover durable state | 🚧 Restart-after-completion ✅; restart-*during*-an-active-job was not tested this session, and duplicate-remote-generation avoidance is N/A until a cloud provider exists (M2) |
| 10 | Change one scene, verify dependency-aware regeneration | ✅ |
| 11 | Export/import project, verify hashes/order/selected takes/provenance | ⛔ Portable project export/import is not implemented in M1 (see known-limitations.md) |
| 12 | No credentials in export/logs/frontend responses | ✅ by construction (no cloud credentials exist yet in M1 to leak) |
| 13 | Browser E2E: create/edit/preview/export/reopen | ⛔ Not run — no browser automation tool was available in this environment this session; the same workflow was proven via direct HTTP calls against the real API instead (see docs/test-report.md) |
| 14 | Human evaluation of a real voice audition before accepting Arabic quality | N/A this milestone — local offline TTS is explicitly not the quality-gated voice; that evaluation applies starting M2/M4 with a real cloud provider |
