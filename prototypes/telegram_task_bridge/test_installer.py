"""Transaction tests use real temporary files and a simulated scheduler; no API calls."""
import tempfile
import json
import subprocess
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

from installer import FILES, Installer, SetupError


class SimulatedInstaller(Installer):
    def __init__(self, *args):
        super().__init__(*args)
        self.events = []
        self.installed = True
        self.running = True
        self.bad_preflight = False
        self.bad_health = False
        self.bad_deploy = False

    def environment(self, candidate):
        self.events.append("environment")

    def validate(self, candidate):
        self.events.append("validate")
        if self.bad_preflight:
            raise SetupError("bad preflight")

    def manager(self, action):
        self.events.append(action)
        if action == "stop":
            self.running = False
        elif action == "start":
            self.running = True
        elif action == "install":
            self.installed = True
        elif action == "uninstall":
            self.running = self.installed = False
        return {"installed": self.installed, "scheduler_state": "Running" if self.running else "Ready"}

    def wait_ready(self, started_at):
        self.events.append("health")
        if self.bad_health:
            self.bad_health = False
            raise SetupError("bad new receiver")

    def deploy(self, candidate):
        if self.bad_deploy:
            (self.runtime / FILES[0]).write_text("partial")
            raise OSError("disk failure")
        super().deploy(candidate)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        root, bundle, config = base / "root", base / "bundle", base / "config.json"
        (root / "runtime").mkdir(parents=True)
        bundle.mkdir()
        config.write_text("private credential content")
        for name in FILES:
            (bundle / name).write_text("mcp==2.2.0" if name == "requirements.txt" else "new " + name)
            (root / "runtime" / name).write_text("old " + name)
        (root / "live.sqlite3").write_bytes(b"database unchanged")
        (root / "runtime/custom.txt").write_text("preserved")
        self.install = SimulatedInstaller(root, bundle, config)

    def assert_preserved(self):
        self.assertEqual(self.install.database.read_bytes(), b"database unchanged")
        self.assertEqual(self.install.config.read_text(), "private credential content")
        self.assertEqual((self.install.runtime / "custom.txt").read_text(), "preserved")

    def assert_old(self):
        for name in FILES:
            self.assertEqual((self.install.runtime / name).read_text(), "old " + name)
        self.assert_preserved()

    def test_update_validates_before_stop_and_preserves_data(self):
        result = self.install.execute("update")
        self.assertEqual(result["state"], "ready")
        self.assertLess(self.install.events.index("validate"), self.install.events.index("stop"))
        self.assertEqual((self.install.runtime / "server.py").read_text(), "new server.py")
        self.assertTrue((Path(result["backup"]) / "server.py").is_file())
        self.assert_preserved()

    def test_failed_preflight_never_stops_existing_receiver(self):
        self.install.bad_preflight = True
        with self.assertRaises(SetupError):
            self.install.execute("update")
        self.assertNotIn("stop", self.install.events)
        self.assertTrue(self.install.running)
        self.assert_old()

    def test_failed_health_restores_runtime_and_restarts_old_receiver(self):
        self.install.bad_health = True
        with self.assertRaisesRegex(SetupError, "restored"):
            self.install.execute("update")
        self.assertEqual(self.install.events.count("start"), 2)
        self.assertTrue(self.install.running)
        self.assert_old()

    def test_partial_copy_failure_restores_every_file(self):
        self.install.bad_deploy = True
        with self.assertRaisesRegex(SetupError, "restored"):
            self.install.execute("update")
        self.assertTrue(self.install.running)
        self.assert_old()

    def test_paused_update_does_not_start_or_clear_marker(self):
        self.install.pause.write_bytes(b"pause intent")
        self.install.running = False
        self.assertEqual(self.install.execute("update")["state"], "paused")
        self.assertNotIn("start", self.install.events)
        self.assertEqual(self.install.pause.read_bytes(), b"pause intent")
        self.assert_preserved()

    def test_new_install_failure_removes_new_task_and_files(self):
        self.install.installed = self.install.running = False
        for name in FILES:
            (self.install.runtime / name).unlink()
        self.install.bad_health = True
        with self.assertRaisesRegex(SetupError, "restored"):
            self.install.execute("install")
        self.assertFalse(self.install.installed)
        self.assertFalse(any((self.install.runtime / name).exists() for name in FILES))
        self.assert_preserved()

    def test_uninstall_preserves_files_and_data(self):
        self.install.execute("uninstall")
        self.assertFalse(self.install.installed)
        self.assertTrue(self.install.pause.exists())
        self.assert_old()

    def test_missing_config_does_not_touch_receiver(self):
        self.install.config.unlink()
        with self.assertRaisesRegex(SetupError, "config is missing"):
            self.install.execute("install")
        self.assertEqual(self.install.events, [])

    def test_fresh_health_required(self):
        states = [{"receiver_state": "ready", "health": {"updated_at": 9}},
                  {"receiver_state": "ready", "health": {"updated_at": 11}}]
        with patch.object(self.install, "manager", side_effect=states) as manager, patch("installer.time.sleep"):
            Installer.wait_ready(self.install, 10)
        self.assertEqual(manager.call_count, 2)

    def test_existing_environment_never_installs_dependencies(self):
        self.install.python.parent.mkdir(parents=True)
        self.install.python.write_bytes(b"fake interpreter")
        with patch("installer.run", return_value="") as child:
            Installer.environment(self.install, self.install.bundle)
        self.assertEqual(child.call_count, 1)
        self.assertNotIn("pip", child.call_args.args[0])

    def interrupt_update(self):
        def crash(candidate):
            self.install.deployment_marker.write_text("interrupted")
            (self.install.runtime / "server.py").write_text("partial new code")
            raise KeyboardInterrupt()
        with patch.object(self.install, "deploy", side_effect=crash):
            with self.assertRaises(KeyboardInterrupt):
                self.install.execute("update")
        self.assertTrue(self.install.journal.exists())

    def test_interrupted_update_restores_on_next_setup_before_preflight(self):
        self.interrupt_update()
        self.install.bad_preflight = True
        with self.assertRaisesRegex(SetupError, "bad preflight"):
            self.install.execute("update")
        self.assert_old()
        self.assertTrue(self.install.running)
        self.assertFalse(self.install.journal.exists())
        self.assertFalse(self.install.deployment_marker.exists())

    def test_recovery_can_itself_be_interrupted_and_repeated(self):
        self.interrupt_update()
        with patch.object(self.install, "restore", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.install.recover()
        self.assertTrue(self.install.journal.exists())
        self.assertTrue(self.install.recover())
        self.assertFalse(self.install.recover())
        self.assert_old()

    def test_recovery_respects_pause_added_after_interruption(self):
        self.interrupt_update()
        self.install.pause.write_text("user pause")
        self.install.events.clear()
        self.install.recover()
        self.assertNotIn("start", self.install.events)
        self.assertEqual(self.install.pause.read_text(), "user pause")
        self.assert_old()

    def test_corrupt_backup_refuses_recovery_before_scheduler_changes(self):
        self.interrupt_update()
        record = json.loads(self.install.journal.read_text())
        (self.install.root / record["backup"] / "server.py").write_text("corruption")
        self.install.events.clear()
        with self.assertRaisesRegex(SetupError, "invalid"):
            self.install.recover()
        self.assertEqual(self.install.events, [])
        self.assertTrue(self.install.journal.exists())

    def test_recovery_rejects_backup_path_escape(self):
        self.interrupt_update()
        record = json.loads(self.install.journal.read_text())
        record["backup"] = "../outside"
        self.install.journal.write_text(json.dumps(record))
        self.install.events.clear()
        with self.assertRaisesRegex(SetupError, "invalid"):
            self.install.recover()
        self.assertEqual(self.install.events, [])

    def test_interrupted_first_install_removes_partial_task_and_runtime(self):
        self.install.installed = self.install.running = False
        for name in FILES:
            (self.install.runtime / name).unlink()
        with patch.object(self.install, "wait_ready", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.install.execute("install")
        self.install.recover()
        self.assertFalse(self.install.installed)
        self.assertFalse(any((self.install.runtime / name).exists() for name in FILES))
        self.assert_preserved()

    def test_legacy_marker_is_not_silently_discarded(self):
        self.install.deployment_marker.write_text("legacy")
        with self.assertRaisesRegex(SetupError, "legacy"):
            self.install.execute("update")
        self.assertEqual(self.install.events, [])

    def test_abrupt_process_exit_leaves_recoverable_transaction(self):
        script = """
import os, sys
from pathlib import Path
from test_installer import SimulatedInstaller
instance = SimulatedInstaller(*map(Path, sys.argv[1:]))
def crash(candidate):
    instance.deployment_marker.write_text('interrupted')
    (instance.runtime / 'server.py').write_text('partial process write')
    os._exit(73)
instance.deploy = crash
instance.execute('update')
"""
        result = subprocess.run([sys.executable, "-c", script, str(self.install.root),
                                 str(self.install.bundle), str(self.install.config)],
                                cwd=Path(__file__).parent, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 73, result.stderr)
        self.assertTrue(self.install.recover())
        self.assert_old()


if __name__ == "__main__":
    unittest.main()
