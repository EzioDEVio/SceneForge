# Crash diagnostic review · October 6, 2026

Archive: SceneForge-diagnostics-20261006-185715.zip, from the frozen Windows 0.9.3 app.

## Recorded evidence

- All 18 recorded jobs are scene renders and succeeded. No full-project export jobs
  are included. This does not prove that all UI operations worked or that an earlier
  failure was absent from bounded logs.
- Recent backend errors are asyncio ConnectionResetError / WinError 10054 callbacks.
  Closed browser/preview connections could account for them, but that has not been
  established. No fatal backend exit is shown in this archive.
- Chatterbox setup received HTTP 404 from POST http://127.0.0.1:8881/warmup.
  The service at that port did not expose the expected setup endpoint. This is an
  API compatibility issue; its underlying service/version cause is still unverified.
- Whisper's five recorded readiness checks passed. No voice generation or caption
  generation success is established by those readiness checks alone.

## Limited source correction

Missing POST /warmup endpoints (404/405) are now described accurately rather than
reported as a model-download failure. This condition is not automatically retried;
model caches are retained. Targeted mocked tests passed for 404/405 and real model
memory-error classification. No network, Docker, model downloads or Windows execution
were used. This improves diagnosis and does not fix the owner's running service.

The broader managed-AI test could not complete because this environment lacks
Faster-Whisper. Full Windows/local AI verification remains open.

## Source continuity blocker

This turn's workspace is at commit 6850579, an older source checkpoint than the
ab85c7f checkpoint inspected in the preceding reliability work. The preceding
Creator/draft reliability changes and its report are absent here. They must be
recovered before combining changes or preparing another package. Do not interpret
this turn as a new validation of that missing source state.

No application build, ZIP, GitHub push, tag or publication was performed.
