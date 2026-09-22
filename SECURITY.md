# Security notes

SceneForge is a localhost development application, not a hardened multi-user web service. It has no production authentication boundary. Do not expose port 8000 publicly.

Provider credentials currently use reversible local obfuscation in the data store. They are not encrypted with Windows Credential Manager. Protect and exclude backend/data and all backups from source control. OS-backed credential storage is planned before general desktop distribution.

Hosted image generation sends the entered prompt to the selected provider. Local narration and image engines are separate processes. Download models from sources you trust and follow their licenses.

Report vulnerabilities privately to the repository owner. Do not include live credentials or private media in issues. Rotate credentials if they have been exposed.
