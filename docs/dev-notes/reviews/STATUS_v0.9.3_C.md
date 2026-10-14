# SceneForge 0.9.3 — section C checkpoint (unreleased)

Continues the independent overlay checkpoint `13c5a51607cf977a7f2dc596a18f1d710da9adb7` on `claude/0.9.3`. All earlier source changes are retained. This checkpoint changes release tooling, not editor behaviour.

## Release verification

The Release workflow now ends with **Verify draft release files** for `v*` tags. It waits for the full build matrix, fails if the required builds fail or are cancelled, and then queries the draft associated with the exact tag. macOS remains experimental under the existing matrix policy. Branch and manual non-tag builds do not create a release or claim release readiness.

For a stable 0.9.3 build, the required files are:

| Windows | Linux |
| --- | --- |
| `SceneForge-Studio-0.9.3-Windows-x64-Setup.exe` | `SceneForge-Studio-0.9.3-Linux-x64.AppImage` |
| `SceneForge-Studio-0.9.3-Windows-x64-Setup.exe.blockmap` | `SceneForge-Studio-0.9.3-Linux-x64.deb` |
| `latest.yml` | `latest-linux.yml` |

Names are derived from the actual `desktop/package.json` version and electron-builder filenames. Product versions are still 0.9.2 in this checkpoint, intentionally awaiting section F; the checker therefore expects 0.9.2 when run against this source, and rejects a 0.9.3 tag until the version is updated.

Each required file must appear exactly once, have an `uploaded` state and positive size. Previous-version installers, optional macOS assets, a published release or a missing draft cannot satisfy the check. Release and asset listings are paginated. API errors fail verification rather than implying success. The workflow summary tells the owner to keep the draft unpublished if a check fails.

The checker executes only GitHub GET requests. GitHub documents that listing drafts requires push access, so the job's token retains `contents: write` to see the draft, while the script never edits or publishes it. See [GitHub release API](https://docs.github.com/en/rest/releases/releases) and [electron-builder v26 publishing](https://www.electron.build/v26/docs/publish/).

Workflow artifact uploads now include `.blockmap` files as well as the existing installers and metadata, making the Windows update files available for manual recovery. A green check confirms attachment names, upload completion and nonzero sizes; it does not verify downloaded installer hashes or prevent someone manually publishing an incomplete draft.

**Do not publish the draft until Windows, Linux and Verify draft release files are all green. Publication still requires the owner's explicit instruction.**

## Validation and limits

- 23 offline verifier tests pass. They cover complete/missing drafts, each missing/empty/unfinished required file, version mismatch, duplicate files, published releases, optional macOS files, target-specific filenames, channel configuration, pagination and API failures. No GitHub or paid provider calls occur in those tests.
- All 18 existing desktop lifecycle/session/update tests pass on Linux.
- Both changed workflow YAML files parse, and `git diff --check` passes.
- The live tagged workflow, Windows/Linux installers and Windows UI have not been run in this turn. Editor build/browser tests were not rerun because editor source is unchanged; previous results remain documented in `STATUS_v0.9.3_OVERLAYS.md` and are not presented as new runs.

## Remaining work

- Windows review of the independent image/text tracks and beige caption boxes.
- **D:** stabilisation, AutoCut to beats with Undo, project templates, Script to scenes.
- **E:** requested effects and transitions with real preview/export, controls, search/help and backend tests.
- **F:** final version bump, release documentation, complete backend/frontend/browser checks and installer validation. Earlier legacy browser-suite failures remain recorded in `STATUS_v0.9.3_AB.md`.

No push, merge into main, tag or publication was performed.
