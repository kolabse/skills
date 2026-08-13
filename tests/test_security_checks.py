from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from security_checks import check_python, check_secrets, check_workflows, validate  # noqa: E402


class SecurityChecksTests(unittest.TestCase):
    def test_repository_passes(self) -> None:
        self.assertEqual([], validate(Path(__file__).resolve().parents[1]))

    def test_detects_secret_shell_and_unpinned_action(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "unsafe.py").write_text(
                "import subprocess\nsubprocess.run(['x'], shell=True)\n",
                encoding="utf-8",
            )
            (root / "secret.txt").write_text(
                "ghp_" + "abcdefghijklmnopqrstuvwxyz123456\n", encoding="utf-8"
            )
            workflows = root / ".github/workflows"
            workflows.mkdir(parents=True)
            (workflows / "ci.yml").write_text(
                "permissions:\n  contents: read\njobs:\n  x:\n    steps:\n      - uses: actions/checkout@v4\n",
                encoding="utf-8",
            )
            self.assertTrue(check_python(root))
            self.assertTrue(check_secrets(root))
            self.assertTrue(check_workflows(root))
