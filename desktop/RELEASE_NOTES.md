# SceneForge Desktop 0.2.0 RC1

## Changes
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
