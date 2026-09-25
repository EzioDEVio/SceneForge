# Contributing to SceneForge Studio

Thanks for helping! SceneForge Studio is licensed under the **GNU GPL v3.0 or later**. By contributing
you agree that your contribution is licensed under the same terms.

## Reporting bugs
Open an issue with: the SceneForge version (Help → About), your OS, steps to reproduce, and what you expected.
For render problems include the aspect ratio, scene length, effects used, and whether narration is present.
Logs are in the workspace folder (File → Open logs); remove anything private before attaching them.

## Development setup
See "Build from source" in the README. Before opening a pull request, run:
```
npm --prefix frontend run build && npm --prefix frontend test
npm --prefix desktop test
python tests/integration/test_combined.py     # plus the suite for the area you changed
```
The full backend suite is listed in `.github/workflows/checks.yml` and runs on every pull request.

## Guidelines
- Keep database changes additive (new columns via `backend/app/db/database.py:_ADDED_COLUMNS`); never drop user data.
- Rendering changes need a real-render test that measures the output (see `tests/integration/test_effects_pack.py`).
- Bump `BUILD_ID` in `backend/app/main.py` and `frontend/src/api.ts` together when the API changes.
- Never commit API keys, tokens or personal media.
