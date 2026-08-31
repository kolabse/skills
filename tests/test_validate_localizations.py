from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_localizations.py"


class LocalizationValidationTests(unittest.TestCase):
    def run_validator(self, root: Path) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["PYTHONIOENCODING"] = "utf-8"
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--project-root", str(root)],
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
            env=environment,
        )

    def test_repository_localizations_are_valid(self) -> None:
        result = self.run_validator(ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(
            "Validated 50 translation(s) across 10 locale(s): de, es, fr, it, ja, ko, pt-BR, ru, tr, zh-CN.",
            result.stdout,
        )

    def test_validator_output_is_safe_for_legacy_windows_encoding(self) -> None:
        environment = os.environ.copy()
        environment["PYTHONIOENCODING"] = "cp1251"

        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--project-root", str(ROOT)],
            text=True,
            encoding="cp1251",
            capture_output=True,
            check=False,
            env=environment,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("locale(s): de, es, fr, it, ja, ko, pt-BR, ru, tr, zh-CN.", result.stdout)

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

    def test_rejects_broken_table_of_contents_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs/i18n/ru").mkdir(parents=True)
            canonical = "# Project\n\nEnglish | Русский\n\n- [Missing](#missing)\n"
            translation = "# Проект\n\nEnglish | Русский\n\n- [Нет](#missing)\n"
            (root / "README.md").write_text(canonical, encoding="utf-8")
            (root / "docs/i18n/ru/README.md").write_text(
                translation, encoding="utf-8"
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
                    }
                ),
                encoding="utf-8",
            )

            result = self.run_validator(root)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("broken Markdown anchor", result.stdout + result.stderr)

    def test_requires_every_language_in_document_navigation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs/i18n/ru").mkdir(parents=True)
            (root / "docs/i18n/es").mkdir(parents=True)
            (root / "README.md").write_text(
                "# Project\n\nEnglish | [Русский](docs/i18n/ru/README.md)\n",
                encoding="utf-8",
            )
            (root / "docs/i18n/ru/README.md").write_text(
                "# Проект\n\n[English](../../../README.md) | Русский\n",
                encoding="utf-8",
            )
            (root / "docs/i18n/es/README.md").write_text(
                "# Proyecto\n\n[English](../../../README.md) | Español\n",
                encoding="utf-8",
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
                            },
                            "es": {
                                "name": "Español",
                                "documents": [
                                    {
                                        "canonical": "README.md",
                                        "translation": "docs/i18n/es/README.md",
                                    }
                                ],
                            },
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = self.run_validator(root)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("language navigation is missing", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
