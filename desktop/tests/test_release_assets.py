"""Offline regressions for the draft release gate; no provider/GitHub calls."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("release_gate", ROOT / "scripts/verify_release_assets.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class ReleaseAssetsTest(unittest.TestCase):
    def setUp(self):
        self.package = json.loads((ROOT / "package.json").read_text())
        self.package["version"] = "0.9.3"
        self.names = gate.expected_assets(self.package)
        self.assets = [{"name": name, "state": "uploaded", "size": 100} for name in self.names]
        self.releases = [{"tag_name": "v0.9.3", "draft": True, "id": 17}]

    def verify(self):
        return gate.verify(self.package, "v0.9.3", self.releases,
                           lambda endpoint: self.assets, "EzioDEVio/SceneForge")

    def test_exact_current_configuration(self):
        self.assertEqual(self.names, [
            "SceneForge-Studio-0.9.3-Windows-x64-Setup.exe",
            "SceneForge-Studio-0.9.3-Windows-x64-Setup.exe.blockmap", "latest.yml",
            "SceneForge-Studio-0.9.3-Linux-x64.AppImage",
            "SceneForge-Studio-0.9.3-Linux-x64.deb", "latest-linux.yml",
        ])

    def test_complete_draft(self):
        self.assertEqual(self.verify(), self.names)

    def test_beta_draft_must_be_marked_prerelease(self):
        # GitHub builds write latest.yml even for betas; electron-updater falls back to it.
        self.package["version"] = "0.9.4-beta.1"
        names = gate.expected_assets(self.package)
        self.assertIn("latest.yml", names)
        assets = [{"name": n, "state": "uploaded", "size": 1} for n in names]
        draft = {"tag_name": "v0.9.4-beta.1", "draft": True, "id": 18}
        with self.assertRaisesRegex(gate.VerificationError, "Pre-release flag"):
            gate.verify(self.package, "v0.9.4-beta.1", [draft], lambda e: assets, "EzioDEVio/SceneForge")
        self.assertEqual(gate.verify(self.package, "v0.9.4-beta.1", [{**draft, "prerelease": True}],
                                     lambda e: assets, "EzioDEVio/SceneForge"), names)

    def test_duplicate_releases_for_one_tag_fail(self):
        self.releases.append({"tag_name": "v0.9.3", "draft": True, "id": 19})
        with self.assertRaisesRegex(gate.VerificationError, "exactly one"):
            self.verify()

    def test_each_required_file_missing(self):
        for name in self.names:
            with self.subTest(name=name):
                self.assets = [a for a in self.assets if a["name"] != name]
                with self.assertRaisesRegex(gate.VerificationError, "Missing"):
                    self.verify()
                self.setUp()

    def test_each_required_file_empty(self):
        for asset in self.assets:
            with self.subTest(name=asset["name"]):
                asset["size"] = 0
                with self.assertRaisesRegex(gate.VerificationError, "Empty"):
                    self.verify()
                asset["size"] = 100

    def test_each_required_file_still_uploading(self):
        for asset in self.assets:
            with self.subTest(name=asset["name"]):
                asset["state"] = "starter"
                with self.assertRaisesRegex(gate.VerificationError, "incomplete"):
                    self.verify()
                asset["state"] = "uploaded"

    def test_missing_draft(self):
        self.releases = []
        with self.assertRaisesRegex(gate.VerificationError, "exactly one"):
            self.verify()

    def test_published_release_is_not_ready_draft(self):
        self.releases[0]["draft"] = False
        with self.assertRaisesRegex(gate.VerificationError, "already published"):
            self.verify()

    def test_previous_release_cannot_satisfy_tag(self):
        self.releases[0]["tag_name"] = "v0.9.2"
        with self.assertRaises(gate.VerificationError):
            self.verify()

    def test_previous_version_assets_cannot_satisfy_gate(self):
        for asset in self.assets:
            asset["name"] = asset["name"].replace("0.9.3", "0.9.2")
        with self.assertRaises(gate.VerificationError):
            self.verify()

    def test_duplicate_names_fail(self):
        self.assets.append(copy.deepcopy(self.assets[0]))
        with self.assertRaisesRegex(gate.VerificationError, "duplicate"):
            self.verify()

    def test_optional_mac_files_do_not_replace_required_files(self):
        self.assets = [{"name": "SceneForge-Studio-0.9.3-macOS-arm64.dmg",
                        "size": 100, "state": "uploaded"}]
        with self.assertRaises(gate.VerificationError):
            self.verify()

    def test_extra_mac_files_allowed(self):
        self.assets.append({"name": "extra-mac.dmg", "size": 100, "state": "uploaded"})
        self.assertEqual(self.verify(), self.names)

    def test_wrong_tag_fails_before_assets_are_requested(self):
        with self.assertRaisesRegex(gate.VerificationError, "does not match"):
            gate.verify(self.package, "v0.9.4", self.releases,
                        lambda _: self.fail("Must not request assets for a mismatched tag"))

    def test_beta_default_github_update_manifest(self):
        self.package["version"] = "0.9.3-beta.1"
        names = gate.expected_assets(self.package)
        self.assertIn("latest.yml", names)
        self.assertIn("latest-linux.yml", names)
        self.assertIn("SceneForge-Studio-0.9.3-beta.1-Windows-x64-Setup.exe", names)

    def test_explicit_channel(self):
        self.package["build"]["publish"][0]["channel"] = "beta"
        names = gate.expected_assets(self.package)
        self.assertIn("beta.yml", names)
        self.assertIn("beta-linux.yml", names)

    def test_nsis_target_artifact_name_takes_precedence(self):
        self.package["build"]["nsis"]["artifactName"] = "Setup-${version}.${ext}"
        self.assertEqual(gate.expected_assets(self.package)[0], "Setup-0.9.3.exe")

    def test_invalid_filename_templates_fail(self):
        for value in ("../installer.exe", "${unknown}.exe", "folder\\setup.exe"):
            with self.subTest(value=value):
                self.package["build"]["nsis"]["artifactName"] = value
                with self.assertRaises(gate.VerificationError):
                    gate.expected_assets(self.package)

    def test_invalid_asset_size_fails(self):
        for size in (None, -1, "100", True):
            with self.subTest(size=size):
                self.assets[0]["size"] = size
                with self.assertRaises(gate.VerificationError):
                    self.verify()

    def test_paginated_releases_and_assets_are_combined(self):
        response = subprocess.CompletedProcess([], 0, json.dumps([[{"id": 1}], [{"id": 2}]]), "")
        with patch.object(gate.subprocess, "run", return_value=response) as run:
            self.assertEqual(gate.api_pages("repos/owner/repo/releases"), [{"id": 1}, {"id": 2}])
        command = run.call_args.args[0]
        self.assertIn("GET", command)
        self.assertIn("--paginate", command)
        self.assertIn("--slurp", command)

    def test_cli_failure_does_not_echo_raw_output(self):
        error = subprocess.CalledProcessError(1, ["gh"], stderr="private auth detail")
        with patch.object(gate.subprocess, "run", side_effect=error):
            with self.assertRaises(gate.VerificationError) as caught:
                gate.api_pages("repos/owner/repo/releases")
        self.assertNotIn("private auth detail", str(caught.exception))

    def test_invalid_api_json_fails(self):
        for data in ("{", '{"message":"denied"}', '[{"id":1}]'):
            with self.subTest(data=data):
                with patch.object(gate.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, data)):
                    with self.assertRaises(gate.VerificationError):
                        gate.api_pages("repos/owner/repo/releases")

    def test_command_success_writes_draft_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            package_path = Path(directory) / "package.json"
            summary_path = Path(directory) / "summary.md"
            package_path.write_text(json.dumps(self.package))
            argv = ["verify", "--repository", "EzioDEVio/SceneForge", "--tag", "v0.9.3",
                    "--package", str(package_path), "--summary", str(summary_path)]
            with patch.object(gate.sys, "argv", argv), redirect_stdout(StringIO()):
                with patch.object(gate, "api_pages", side_effect=[self.releases, self.assets]) as api:
                    self.assertEqual(gate.main(), 0)
            report = summary_path.read_text()
            self.assertIn("release remains a draft", report)
            for name in self.names:
                self.assertIn(name, report)
            self.assertEqual(api.call_count, 2)

    def test_command_failure_writes_do_not_publish_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            package_path = Path(directory) / "package.json"
            summary_path = Path(directory) / "summary.md"
            package_path.write_text(json.dumps(self.package))
            argv = ["verify", "--repository", "EzioDEVio/SceneForge", "--tag", "v0.9.3",
                    "--package", str(package_path), "--summary", str(summary_path)]
            with patch.object(gate.sys, "argv", argv), redirect_stderr(StringIO()):
                with patch.object(gate, "api_pages", side_effect=[self.releases, self.assets[:-1]]):
                    self.assertEqual(gate.main(), 1)
            self.assertIn("Do not publish this draft", summary_path.read_text())


if __name__ == "__main__":
    unittest.main()
