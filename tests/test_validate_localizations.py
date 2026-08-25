from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_localizations.py"


class LocalizationValidationTests(unittest.TestCase):
    def run_validator(self, root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--project-root", str(root)],
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )

    def test_repository_localizations_are_valid(self) -> None:
        result = self.run_validator(ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Validated 5 Russian translation(s)", result.stdout)

    def test_rejects_changed_shell_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs/i18n/ru").mkdir(parents=True)
            (root / "README.md").write_text(
                "# Project\n\n```shell\ncommand --safe\n```\n", encoding="utf-8"
            )
            (root / "docs/i18n/ru/README.md").write_text(
                "# Проект\n\n```shell\ncommand --unsafe\n```\n", encoding="utf-8"
            )
            (root / "docs/i18n/locales.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "canonical_locale": "en",
                        "locales": {
                            "ru": {
                                "name": "Русский",
                                "documents": [
                                    {
                                        "canonical": "README.md",
                                        "translation": "docs/i18n/ru/README.md",
                                    }
                                ],
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = self.run_validator(root)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("shell code blocks differ", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
