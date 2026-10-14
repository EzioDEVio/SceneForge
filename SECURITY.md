# Security policy

## Reporting a vulnerability

Please report security problems **privately**, not in a public issue:

- use **[Report a vulnerability](https://github.com/EzioDEVio/SceneForge/security/advisories/new)** on the repository's Security tab, or
- if that is not available, open an issue that only asks the maintainer for a private contact, without details.

Include the SceneForge version (**Help → About**), your operating system, and steps to reproduce. Never include live API keys, tokens or private media; if a key was exposed, revoke it with its provider first.

You should hear back within a week. Fixes go into the next release and the changelog credits you unless you prefer otherwise.

## Supported versions

Security fixes are made for the **latest release** and the **latest pre-release**. Please update before reporting.

## How SceneForge protects you

- **Local first.** The editor's backend listens on `127.0.0.1` only. In the desktop app every request must carry a per-launch token and come from the app's own origin, so web pages and other programs cannot drive it. When you run from source, don't expose its port to a network.
- **Provider keys** are kept in the operating system's credential store (Windows Credential Manager, macOS Keychain, Linux Secret Service). The project database only holds references, and there is no plaintext fallback.
- **Uploads** are checked by type and size and stored under generated names.
- **Paid AI requests** need an explicit confirmation of the estimated cost.
- **Downloaded models and engines** come from their upstream sources and are checked against checksums where the source publishes them. Local engines run as separate processes with your user's permissions.
- **What leaves your computer:** nothing, unless you use a cloud provider. Then the prompt, text or media you send to that provider goes to it, under its terms.
