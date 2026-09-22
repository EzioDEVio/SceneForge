# Contributing to SceneForge

Use a feature branch and keep changes focused. Include the problem, resulting behaviour, and relevant test evidence in pull requests.

For editor changes run the TypeScript build and component tests. For filter, timing or transition changes, also render a small fixture through real FFmpeg. Never replace render validation with a simulated progress bar.

Do not commit backend/data, provider keys, .env files, virtual environments, node_modules, generated user videos or model weights. Keep examples synthetic. Hosted provider tests should mock responses unless the tester explicitly opts into live account usage.

Bug reports should include OS, /api/health build, reproduction steps and redacted errors. Explain expected versus actual results. Check the effects guide before proposing a new preset to avoid overlapping names.
