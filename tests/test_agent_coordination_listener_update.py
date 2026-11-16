"""Managed updates activate an already configured Windows AICQ listener."""
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "aicq_update_manager", Path(__file__).resolve().parents[1] / "scripts/manage_installed_skills.py",
)
manager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manager)


class ListenerUpdateTests(unittest.TestCase):
    def test_bootstrap_only_runs_for_configured_windows_codex_updates(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            state = root / "Formika/AICQ/listener"
            state.mkdir(parents=True)
            with patch.dict(manager.os.environ, {"LOCALAPPDATA": folder}), patch.object(
                manager, "run_checked",
            ) as run:
                self.assertIsNone(manager.refresh_aicq_listener(root, "claude-code", 30, platform="nt"))
                self.assertIsNone(manager.refresh_aicq_listener(root, "codex", 30, platform="posix"))
                self.assertIsNone(manager.refresh_aicq_listener(root, "codex", 30, platform="nt"))
                run.assert_not_called()
                (state / "bindings.json").write_text("[]", encoding="utf-8")
                self.assertEqual(manager.refresh_aicq_listener(root, "codex", 30, platform="nt"),
                                 "startup_requested")
                argv, cwd, timeout = run.call_args.args
                self.assertEqual(cwd, root.resolve())
                self.assertEqual(timeout, 30)
                self.assertIn("-NonInteractive", argv)
                self.assertTrue(any(value.endswith("install_room_listener.ps1") for value in argv))

    def test_update_reports_scheduler_denial_without_claiming_startup(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            state = root / "Formika/AICQ/listener"
            state.mkdir(parents=True)
            (state / "bindings.json").write_text('[{}]', encoding="utf-8")
            with patch.dict(manager.os.environ, {"LOCALAPPDATA": folder}), patch.object(
                manager, "run_checked", side_effect=manager.ManagerError("blocked by policy"),
            ):
                self.assertEqual(manager.refresh_aicq_listener(root, "codex", 30, platform="nt"),
                                 "startup_failed")
