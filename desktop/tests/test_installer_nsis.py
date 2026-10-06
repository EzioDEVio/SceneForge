"""Compile the local AI include in both NSIS passes, with warnings as errors.

Run: MAKENSIS=/path/to/makensis python desktop/tests/test_installer_nsis.py
NSISDIR may also be set for a compiler unpacked outside its normal location.
Temporary compiler outputs are discarded; no application installer is built.
"""
import os
import re
from pathlib import Path
import subprocess
import tempfile
import unittest


INCLUDE = Path(__file__).resolve().parents[1] / "installer.nsh"


class InstallerCompileTests(unittest.TestCase):
    def test_all_ai_page_controls_fit_the_custom_dialog(self):
        # Modern UI custom page 1018 is 140 dialog units high. Controls beyond
        # it are clipped rather than scrollable (the original terms box ended
        # at 176u). Check every control, including the acceptance checkbox.
        page = INCLUDE.read_text().split("Function SFLocalAIPage", 1)[1].split("FunctionEnd", 1)[0]
        controls = [line for line in page.splitlines() if "${NSD_Create" in line]
        self.assertEqual(len(controls), 10)
        for control in controls:
            bounds = re.search(r"\$\{NSD_Create\w+\}\s+\S+\s+(\d+)(?:u)?\s+\S+\s+(\d+)u", control)
            self.assertIsNotNone(bounds, control)
            top, height = map(int, bounds.groups())
            self.assertGreater(height, 0, control)
            self.assertLessEqual(top + height, 140, control)
        self.assertIn("I accept the terms for the selected AI components.", page)

    def compile_pass(self, uninstaller=False):
        with tempfile.TemporaryDirectory(prefix="sceneforge-nsis-test-") as tmp:
            root = Path(tmp)
            script = root / "test.nsi"
            prefix = "!define BUILD_UNINSTALLER\n" if uninstaller else ""
            pages = (
                '!insertmacro MUI_UNPAGE_INSTFILES\nSection "Uninstall"\nSectionEnd\n'
                'Section "Bootstrap"\nWriteUninstaller "$TEMP\\sf-test-uninstall.exe"\nSectionEnd\n'
                if uninstaller else
                '!insertmacro customPageAfterChangeDir\n!insertmacro MUI_PAGE_INSTFILES\n'
                'Section "Install"\n!insertmacro customInstall\nSectionEnd\n'
            )
            script.write_text(
                'Unicode true\nName "SceneForge NSIS regression"\n'
                f'OutFile "{(root / "test.exe").as_posix()}"\n'
                'RequestExecutionLevel user\n!include "MUI2.nsh"\n'
                + prefix + f'!include "{INCLUDE.as_posix()}"\n' + pages
                + '!insertmacro MUI_LANGUAGE "English"\n',
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
