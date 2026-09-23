# SceneForge Desktop 0.2.0 RC3

## Close and credential fixes
- X, Alt+F4 and File → Quit ask **Save and exit** or **Cancel**. Pending narration, captions, titles and project-name changes are saved before stopping the backend. Failed saves and active renders keep the app open.
- Provider credentials use the native Windows credential vault (macOS Keychain / Linux Secret Service in source installs). Legacy Base64 keys migrate on startup; failed migration is reported and the legacy key cannot be used. No plaintext fallback is permitted.
- Migration scrubs the active SQLite database and WAL. Older backups remain outside this migration; keep them private or rotate keys if they were shared.
- Linux CI starts a real Secret Service for credential tests. Windows build commands now stop immediately on a failed command.
- Corrects Together image routing and ElevenLabs audio file format. Cloud provider calls are tested with fixtures; live billable generation is not performed in CI.


## Editing fixes
- Title text saves as you type and stays editable when switching inspector tabs.
- Caption typewriter enables captions and can populate an empty caption from the narration script.
- Direct Edit narration and Edit captions & titles actions reopen the editors.
- Render text preview updates the rendered scene after text or animation changes. Title overlays use their own Animation selector.
- Voice generation waits for the latest narration script to save. Regenerate narration after editing its script.
- In-app confirmation dialogs restore editor focus after closing.

## Earlier changes
- Automatically starts an existing Stable Diffusion WebUI installation when enabled. The default folder is your user profile's `stable-diffusion-webui` folder.
- **AI Engines → Choose Stable Diffusion folder** opens the native folder picker, saves the location and starts the service. **Generate image → Local engine setup** contains the automatic startup switch and editable path.
- Reuses an already-running SD API. On exit, stops only an SD process launched by this app.
- Voice takes now have a Delete action with confirmation. Deleting selected narration invalidates its old scene render and leaves narration unselected. Shared media files remain available.
- Prevents audio deletion during an active project render.
- Explains why voice generation is unavailable when narration text is empty.
- Removes source-workspace launch instructions from desktop voice errors and improves selected-take contrast.

## Install and use
Close SceneForge before running the new setup executable. The same application identity and user workspace are retained, preserving saved projects and provider settings. Do not delete your existing workspace.

For SD, select your existing folder containing `webui-user.bat`, with `--api` in its launch options. Model downloads are not required when reusing your installation. Initial model startup can take several minutes; use Check engine or View startup log in Image Studio.

## Release status
This is an unsigned Windows x64 release candidate. The core editor, private Python runtime, FFmpeg and fonts are bundled. AI engines and model downloads are not bundled. Existing Chatterbox installations remain supported. macOS/Linux installers, signing and automatic engine installation are not included. Real SD inference on the user's GPU remains a manual acceptance check; CI checks launching and stopping a fixture service, not model quality.
