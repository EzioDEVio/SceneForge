# Windows text rendering recovery

The owner's logs show `ImportError: DLL load failed while importing _imagingft:
The filename or extension is too long.` Pillow could read ordinary images but
could not load its FreeType DLL. This affected Text/Text Box/Text+ raster previews,
textured titles and video-inside-text titles.

The source fix installs an isolated Python environment per checkout beneath
`%LOCALAPPDATA%\SceneForge\runtimes\<checkout-id>` instead of the deeply nested
`backend\.venv`. Both Windows setup/start entry points use the same launcher.
Setup and startup verify real Latin and shaped Arabic text drawing before
continuing. Projects, media and database location remain unchanged. Existing
old environments are left in place and are not used by the new launchers.

All Pillow font loaders use the bundled font bytes, avoiding native font filename
handling for long/Unicode paths. Unavailable DLLs or fonts return HTTP 503 with
recovery instructions rather than an unexplained Internal Server Error. The
draft text preview displays that message. Failed title insertion preserves the
saved scene. A broken runtime is reported, not replaced with a substitute font.

## With the updated package

1. Close the old server.
2. Run `scripts\setup.bat` (or `scripts\setup.ps1`). Wait for the Latin/Arabic
   text check to succeed and for frontend setup to finish.
3. Run `scripts\start.bat` (or `scripts\start.ps1`), then refresh the app.
4. Test Text, Text Box and Text+ in the preview; Apply, render and export.
5. Add a textured title and a video-inside-text title. Render a short scene.
6. Test an Arabic title and reopen the saved project.

If setup still cannot load Pillow, use a shorter extraction path such as
`C:\SceneForge`, then run setup there. Preserve/copy the existing `backend\data`
folder to retain projects. Do not copy the old virtual environment.

The short-path launcher is validated with mocked Windows subprocess calls.
Actual Windows DLL loading, PowerShell/Batch execution and native credential
storage still require the owner's Windows test. No installer or new ZIP is
created as part of this source repair.
