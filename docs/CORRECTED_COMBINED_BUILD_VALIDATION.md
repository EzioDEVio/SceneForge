# Approved corrected combined checkpoint — October 5, 2026

Owner instruction: “create the corrected combined build and ZIP.” Approval date
is recorded in America/New_York; execution/check records use UTC.

This update includes all previous combined stages, owner fixes, free placement,
timeline sizing and inline provider settings, plus the text-runtime and render
cancellation repairs reviewed in TEXT_OVERLAY_STABILITY_VALIDATION.md.
The source repair is commit 7f7a437. This approval adds the production checks and
cached-preview status and delayed-error fixes caught while exercising the compiled frontend.

## Production checks

- TypeScript/Vite build passes at 0.9.3. The compiled main asset is
  `index-KzOA_ptf.js`; CSS is `index-Bj95OTz6.css`. The existing bundle-size
  advisory does not prevent compilation. Unused earlier index bundles are
  excluded from this checkpoint's staging folder.
- All eight regular Chromium harnesses pass with development mode OFF, using
  the compiled frontend served by the backend. Coverage includes scene-specific
  media insertion, title dialog behavior, independent media/text, timed captions,
  AutoCut, Script → Scenes, templates, stabilization, Apply/Cancel, routes,
  mouse selection, free placement/range edits, resizing and provider forms.
- Text preview regression injects a 503, verifies the recovery message and
  unchanged saved text, then restores the real endpoint. Cached recovered text
  now clears Loading correctly. The test retains its actual loaded-image and
  cleared-status assertions; the production cause was fixed.
- A delayed error-detail response could overwrite a successfully loaded retry
  of the same URL. A deterministic browser regression failed against the prior
  compiled app and passes after assigning each preview attempt an identity,
  replacing the image element per URL, and invalidating older errors on load.
  Error messages remain visible for the current failed attempt.
- The extracted regression also exposed a test-injection race: its wildcard
  503 could hit the preceding preview before the requested draft was debounced.
  The test now verifies that the actual FONT ERROR TEST preview has failed
  before removing the mock and checking real recovery. All image/status and
  saved-project assertions remain intact.
- Full frontend tests pass again after the cached-preview repair. Offline
  version/release/ZIP unit gates: 31 pass. Earlier fresh desktop lifecycle
  tests: 18 pass. Version labels remain 0.9.3.
- The source validation record covers 51 backend suites, including real
  textured/knockout titles, 72 text previews, Arabic, exports, cancellation,
  and full-resolution finishing. No renderer or provider behavior changed
  during these final preview-status frontend fixes.

## Checkpoint delivery gates

Before delivery the created ZIP must pass the updated file/size/corruption gate,
clean extraction, all manifest hashes, case-insensitive Windows filename checks,
compiled asset references and recovery-bundle verification. The extracted app
is then tested with production timeline-layers/free-timeline browser harnesses
and the font/title/cancellation regressions. Final gate results and the ZIP hash
are reported with the delivered file.

The ZIP contains complete sources, freshly compiled frontend, assets, setup/start
scripts and START_HERE_WINDOWS.md. It is not a Windows installer. The incremental
Git bundle requires the preceding Timeline-Resize-Providers source commit 65e612c;
Git is not needed to use the included complete source.

Actual Windows launch, DLL loading, native credentials, hardware GPU and live
provider testing still require the owner's platform. No paid provider calls,
real credentials, GitHub push, tag or publication occurred.
