"""Read-only gate for the Windows/Linux files on a tagged draft release.

Uses the installed GitHub CLI for authenticated GETs. Never publishes a release.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys


class VerificationError(ValueError):
    pass


def expected_assets(package: dict) -> list[str]:
    version = package["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", version):
        raise VerificationError("Invalid desktop version")
    build = package["build"]

    def filename(platform: str, ext: str) -> str:
        settings = build[platform]
        # The target-specific NSIS setting takes precedence over the Windows one.
        template = (build.get("nsis", {}).get("artifactName") if platform == "win" else None)
        template = template or settings.get("artifactName") or build["artifactName"]
        values = {"version": version, "arch": "x64", "ext": ext,
                  "os": "win" if platform == "win" else "linux"}
        for key, value in values.items():
            template = template.replace("${" + key + "}", value)
        if "${" in template or Path(template).name != template or "\\" in template:
            raise VerificationError("Unsupported artifact filename template")
        return template

    # GitHub publishing defaults to latest, even for prereleases. Respect an
    # explicitly configured channel if one is added later.
    publish = build["publish"]
    provider = publish[0] if isinstance(publish, list) else publish
    channel = provider.get("channel", "latest")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", channel):
        raise VerificationError("Invalid update channel")
    windows = filename("win", "exe")
    return [windows, windows + ".blockmap", channel + ".yml",
            filename("linux", "AppImage"), filename("linux", "deb"),
            channel + "-linux.yml"]


def api_pages(endpoint: str) -> list[dict]:
    try:
        result = subprocess.run(
            ["gh", "api", "--method", "GET", "--paginate", "--slurp", endpoint],
            capture_output=True, text=True, check=True, timeout=120,
        )
        pages = json.loads(result.stdout)
        if not isinstance(pages, list) or any(not isinstance(page, list) for page in pages):
            raise VerificationError("Unexpected release API response")
        return [item for page in pages for item in page]
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError) as exc:
        # Avoid echoing authentication data or raw API output into workflow logs.
        raise VerificationError("Could not read GitHub release data; check access and retry") from exc


def verify(package: dict, tag: str, releases: list[dict], get_assets=api_pages,
           repository: str = "") -> list[str]:
    if tag != "v" + package["version"]:
        raise VerificationError("Release tag does not match desktop/package.json")
    matches = [release for release in releases if release.get("tag_name") == tag]
    if len(matches) != 1:
        raise VerificationError("Expected exactly one release for the current tag")
    release = matches[0]
    if release.get("draft") is not True:
        raise VerificationError("Release is already published; this check requires a draft")
    release_id = release.get("id")
    if type(release_id) is not int or release_id <= 0:
        raise VerificationError("Invalid release identifier")
    assets = get_assets(f"repos/{repository}/releases/{release_id}/assets?per_page=100")
    expected = expected_assets(package)
    problems = []
    for name in expected:
        found = [asset for asset in assets if asset.get("name") == name]
        if len(found) != 1:
            problems.append(f"Missing or duplicate file: {name}")
            continue
        asset = found[0]
        if asset.get("state") != "uploaded":
            problems.append(f"Upload incomplete: {name}")
        if type(asset.get("size")) is not int or asset["size"] <= 0:
            problems.append(f"Empty file: {name}")
    if problems:
        raise VerificationError("\n".join(problems))
    return expected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--package", type=Path,
                        default=Path(__file__).resolve().parents[1] / "package.json")
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()
    try:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repository):
            raise VerificationError("Invalid repository name")
        package = json.loads(args.package.read_text(encoding="utf-8"))
        if args.tag != "v" + package["version"]:
            raise VerificationError("Release tag does not match desktop/package.json")
        expected_assets(package)
        releases = api_pages(f"repos/{args.repository}/releases?per_page=100")
        names = verify(package, args.tag, releases, get_assets=api_pages, repository=args.repository)
    except (VerificationError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        print(f"Release verification failed: {exc}", file=sys.stderr)
        if args.summary:
            with args.summary.open("a", encoding="utf-8") as summary:
                summary.write("\n## Release files: FAILED\n\nDo not publish this draft. See the verification log.\n")
        return 1
    report = (f"## Release files verified: {args.tag}\n\n" +
              "\n".join(f"- `{name}`: uploaded and nonempty" for name in names) +
              "\n\nThe release remains a draft. Publish only after Windows and Linux builds "
              "and their installed-app tests are green, and the owner approves publication.\n")
    print(report)
    if args.summary:
        with args.summary.open("a", encoding="utf-8") as summary:
            summary.write("\n" + report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
