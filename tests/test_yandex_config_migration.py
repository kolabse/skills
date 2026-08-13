from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/operate-yandex-cloud/scripts"
PYTHON = shutil.which("python") or sys.executable
sys.path.insert(0, str(SCRIPTS))
from cloud_skill import configure_project, config_path  # noqa: E402


class YandexConfigMigrationTests(unittest.TestCase):
    def test_migration_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            configure_project(project, "cloud-id", "folder-id", "profile")
            path = config_path(project)
            path.write_text('version: 1\ncloud_id: "cloud-id"\nfolder_id: "folder-id"\n', encoding="utf-8")
            command = [
                PYTHON,
                str(SCRIPTS / "migrate_config.py"),
                "--project-path",
                str(project),
                "--json",
            ]
            first = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(0, first.returncode, first.stderr)
            self.assertTrue(json.loads(first.stdout)["changed"])
            migrated = path.read_bytes()
            second = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(0, second.returncode, second.stderr)
            self.assertFalse(json.loads(second.stdout)["changed"])
            self.assertEqual(migrated, path.read_bytes())

    def test_migration_rejects_unknown_newer_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            path = config_path(project)
            path.parent.mkdir(parents=True)
            original = b'version: 99\ncloud_id: "cloud-id"\n'
            path.write_bytes(original)
            result = subprocess.run(
                [PYTHON, str(SCRIPTS / "migrate_config.py"), "--project-path", str(project), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(1, result.returncode)
            self.assertEqual(original, path.read_bytes())


if __name__ == "__main__":
    unittest.main()
