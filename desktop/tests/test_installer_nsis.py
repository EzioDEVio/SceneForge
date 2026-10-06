"""Compile the local AI include in both NSIS passes, with warnings as errors.

Run: MAKENSIS=/path/to/makensis python desktop/tests/test_installer_nsis.py
NSISDIR may also be set for a compiler unpacked outside its normal location.
Temporary compiler outputs are discarded; no application installer is built.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


INCLUDE = Path(__file__).resolve().parents[1] / "installer.nsh"


class InstallerCompileTests(unittest.TestCase):
    def compile_pass(self, uninstaller=False):
        with tempfile.TemporaryDirectory(prefix="sceneforge-nsis-test-") as tmp:
            root = Path(tmp)
            script = root / "test.nsi"
            prefix = "!define BUILD_UNINSTALLER\n" if uninstaller else ""
            pages = (
                'UninstPage instfiles\nSection "Uninstall"\nSectionEnd\n'
                'Section "Bootstrap"\nWriteUninstaller "$TEMP\\sf-test-uninstall.exe"\nSectionEnd\n'
                if uninstaller else
                '!insertmacro customPageAfterChangeDir\nPage instfiles\n'
                'Section "Install"\n!insertmacro customInstall\nSectionEnd\n'
            )
            script.write_text(
                'Unicode true\nName "SceneForge NSIS regression"\n'
                f'OutFile "{(root / "test.exe").as_posix()}"\n'
                'RequestExecutionLevel user\n'
                + prefix + f'!include "{INCLUDE.as_posix()}"\n' + pages,
                encoding="utf-8",
            )
            compiler = os.environ.get("MAKENSIS", "makensis")
            flag = "/WX" if os.name == "nt" else "-WX"
            result = subprocess.run(
                [compiler, flag, str(script)], capture_output=True, text=True,
                timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_ai_setup_page_and_install_callbacks_compile(self):
        self.compile_pass()

    def test_uninstaller_has_no_orphaned_ai_setup_code(self):
        self.compile_pass(uninstaller=True)


if __name__ == "__main__":
    unittest.main()
