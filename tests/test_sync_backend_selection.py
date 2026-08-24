from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIRECTORY = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "sync-project-context"
    / "scripts"
)
sys.dont_write_bytecode = True
sys.path.insert(0, str(SCRIPT_DIRECTORY))

import context_sync  # noqa: E402


class SyncBackendSelectionTests(unittest.TestCase):
    def test_configure_cli_requires_explicit_backend(self) -> None:
        parser = context_sync.build_parser()

        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parser.parse_args(["configure", "--project-path", "project"])

    def test_configured_backend_has_precedence(self) -> None:
        plan = context_sync.plan_backend_selection(
            configured_backend="local-folder",
            requested_backend=None,
            google_drive_connected=True,
        )

        self.assertEqual("ready", plan["status"])
        self.assertEqual("local-folder", plan["backend"])
        self.assertEqual("configured", plan["selection_source"])
        self.assertFalse(plan["requires_storage_approval"])

    def test_configured_google_drive_blocks_until_connector_is_available(self) -> None:
        plan = context_sync.plan_backend_selection(
            configured_backend="google-drive",
            requested_backend=None,
            google_drive_connected=False,
        )

        self.assertEqual("blocked", plan["status"])
        self.assertEqual("google-drive", plan["backend"])
        self.assertEqual("configured", plan["selection_source"])
        self.assertEqual("google-drive-unavailable", plan["blocker"])
        self.assertEqual(["connect-google-drive"], plan["next_steps"])
        self.assertNotIn("explicit_alternatives", plan)
        self.assertFalse(plan["requires_storage_approval"])

    def test_explicit_backend_is_honored_for_unconfigured_project(self) -> None:
        plan = context_sync.plan_backend_selection(
            configured_backend=None,
            requested_backend="local-folder",
            google_drive_connected=True,
        )

        self.assertEqual("ready", plan["status"])
        self.assertEqual("local-folder", plan["backend"])
        self.assertEqual("explicit", plan["selection_source"])
        self.assertTrue(plan["requires_storage_approval"])

    def test_connected_google_drive_is_the_unqualified_default(self) -> None:
        plan = context_sync.plan_backend_selection(
            configured_backend=None,
            requested_backend=None,
            google_drive_connected=True,
        )

        self.assertEqual("ready", plan["status"])
        self.assertEqual("google-drive", plan["backend"])
        self.assertEqual("default", plan["selection_source"])
        self.assertTrue(plan["requires_storage_approval"])

    def test_unavailable_google_drive_does_not_select_local_folder(self) -> None:
        plan = context_sync.plan_backend_selection(
            configured_backend=None,
            requested_backend=None,
            google_drive_connected=False,
        )

        self.assertEqual("blocked", plan["status"])
        self.assertIsNone(plan["backend"])
        self.assertEqual("google-drive-unavailable", plan["blocker"])
        self.assertEqual(["local-folder"], plan["explicit_alternatives"])
        self.assertEqual(
            ["connect-google-drive", "request-local-folder-explicitly"],
            plan["next_steps"],
        )

    def test_backend_change_requires_explicit_reconfiguration(self) -> None:
        plan = context_sync.plan_backend_selection(
            configured_backend="local-folder",
            requested_backend="google-drive",
            google_drive_connected=True,
        )

        self.assertEqual("reconfiguration-required", plan["status"])
        self.assertIsNone(plan["backend"])
        self.assertEqual("local-folder", plan["configured_backend"])
        self.assertEqual("google-drive", plan["requested_backend"])
        self.assertTrue(plan["requires_storage_approval"])

    def test_backend_plan_reads_existing_mapping_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            config = root / "config.json"
            project.mkdir()
            config.write_text(
                json.dumps(
                    {
                        "version": 2,
                        "machine_id": "machine-000000000000",
                        "projects": [
                            {
                                "project_id": "proj-existing",
                                "local_root": str(project.resolve()),
                                "backend": "local-folder",
                                "storage_root": str(root / "storage"),
                                "mode": "metadata-only",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            before = config.read_bytes()

            plan = context_sync.command_backend_plan(
                argparse.Namespace(
                    project_path=str(project),
                    config_path=str(config),
                    requested_backend=None,
                    google_drive_connected=True,
                )
            )

            self.assertEqual("local-folder", plan["backend"])
            self.assertEqual("configured", plan["selection_source"])
            self.assertEqual(before, config.read_bytes())

    def test_backend_plan_defaults_to_connected_google_drive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()

            plan = context_sync.command_backend_plan(
                argparse.Namespace(
                    project_path=str(project),
                    config_path=str(root / "missing.json"),
                    requested_backend=None,
                    google_drive_connected=True,
                )
            )

            self.assertEqual("google-drive", plan["backend"])
            self.assertEqual("default", plan["selection_source"])
            self.assertFalse((root / "missing.json").exists())


if __name__ == "__main__":
    unittest.main()
