## SceneForge Studio 0.7.1

A security and usability update to 0.7.0.

### Download
| System | File |
|---|---|
| Windows 10/11 (64-bit) | `SceneForge-Studio-0.7.1-Windows-x64-Setup.exe` |
| Linux | `.AppImage` or `.deb` |
| macOS (Apple Silicon, experimental) | `.dmg` |

Existing users are offered this update automatically.

### Security
- `urllib3` 2.8.0 is now bundled. It fixes three high-severity and three moderate-severity advisories.
- The developer build tools move to Vite 7, with patched esbuild; these tools are not part of the installer.
- `npm audit` reports 0 vulnerabilities.

### Usability
- **Inspector tabs** sit in one tidy row with a **More ▾** menu, so they no longer wrap.
- **Workspaces:** Edit, Color, Audio and Review, under View → Workspace.
- **Timeline tracks** can be collapsed, and **Compact tracks** gives a smaller timeline.
- **Keyboard shortcuts:** press `?` for the list, and a short first-run tour (Help → Show tour).
- **Help → AI models:** see, download or delete the Whisper, background-removal and voice-isolation models.
- **Help → Export diagnostics:** creates one zip to attach to bug reports. Keys and secrets are never included.
