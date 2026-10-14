# Contributing to SceneForge Studio

Thanks for helping! Bug reports, ideas, translations, docs fixes and code are all welcome.

SceneForge Studio is licensed under the **GNU GPL v3.0 or later**. By contributing you agree that your contribution is licensed under the same terms. Everyone taking part follows the [code of conduct](CODE_OF_CONDUCT.md).

## Reporting bugs and ideas

Use **[New issue](https://github.com/EzioDEVio/SceneForge/issues/new/choose)** and pick *Bug report* or *Feature idea*. For a bug, the most useful things are:

- the SceneForge version (**Help → About**) and your operating system,
- the steps that lead to the problem and what you expected instead,
- for render problems: the aspect ratio, scene length, effects used, and whether narration is present,
- **Help → Export diagnostics** (a zip with logs and settings). Look through it and remove anything private before attaching it.

Security problems go to [SECURITY.md](SECURITY.md), not to a public issue.

## Development setup

See [Developing SceneForge](docs/DEVELOPMENT.md) for running from source, the development server and building installers. Before opening a pull request, run:

```bash
npm --prefix frontend run build && npm --prefix frontend test
npm --prefix desktop test
python tests/integration/<the test for the area you changed>.py
```

Every push runs the full **Build and render checks** (listed in `.github/workflows/checks.yml`): the frontend build and tests, and Python integration tests that render real video with FFmpeg and measure the result.

## Guidelines

- **Keep user data safe.** Database changes are additive (new columns via `backend/app/db/database.py:_ADDED_COLUMNS`); never drop or rewrite user data.
- **Test what you render.** Rendering changes need a test that renders real media and checks the output (see `tests/integration/test_trending_fx.py` for pixel checks, `test_trend_transitions.py` for exports).
- **Never call paid providers in tests.** Mock them.
- **Keep the UI plain-spoken.** Buttons say what they do; errors say what happened and what to do next.
- Bump `BUILD_ID` in `backend/app/main.py` and `frontend/src/api.ts` together when the API changes.
- Never commit API keys, tokens, personal media, model files or `backend/data`.
