import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from owned_task_manager import OwnedTaskManager


class ManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.codex = self.base / "codex.exe"
        self.database = self.base / "bridge.db"
        self.config = self.base / "config.json"
        for path in (self.codex, self.database, self.config):
            path.touch()
        self.health = Path(str(self.database) + ".receiver-health.json")
        self.health.write_text(json.dumps({"state": "ready", "updated_at": time.time()}))
        self.manager = self.new_manager()
        self.run = self.enterContext(patch("owned_task_manager.subprocess.run"))
        self.run.side_effect = lambda argv, **kw: subprocess.CompletedProcess(
            argv, 0, "codex-cli 0.155.0-alpha.16.3\n" if argv[-1] == "--version" else "",
            "" if argv[-1] == "--version" else "Logged in using ChatGPT\n")
        self.spawn = self.enterContext(patch("owned_task_manager.subprocess.Popen"))
        self.spawn.return_value.poll.return_value = None
        self.enterContext(patch("telegram.state_dir", return_value=self.base / "locks"))

    def new_manager(self):
        return OwnedTaskManager(self.base / "runs", self.codex, self.database, self.config)

    def report(self, **changes):
        data = {"status": "running", "phase": "waiting_reply", "updated_at": time.time()}
        data.update(changes)
        (self.base / "runs" / "task" / "result.json").write_text(json.dumps(data))

    def test_start_is_bounded_and_duplicate_never_relaunches(self):
        self.assertEqual(self.manager.start("task")["execution_state"], "running")
        original = (self.base / "runs/task/launch.json").read_bytes()
        self.manager.start("task")
        restarted = self.new_manager()
        self.assertEqual(restarted.start("task")["execution_state"], "unknown")
        self.assertEqual((self.base / "runs/task/launch.json").read_bytes(), original)
        self.spawn.assert_called_once()
        command = self.spawn.call_args.args[0]
        self.assertIn("--live", command)
        self.assertIn("--cancel-file", command)
        self.assertTrue(command[1].endswith("owned_task.py"))
        self.assertFalse(self.spawn.call_args.kwargs["shell"])
        for key in ("stdin", "stdout", "stderr"):
            self.assertEqual(self.spawn.call_args.kwargs[key], subprocess.DEVNULL)

    def test_spawn_failure_retains_reservation(self):
        self.spawn.side_effect = OSError("SECRET")
        self.assertEqual(self.manager.start("task")["status"], "failed")
        self.assertEqual(self.new_manager().start("task")["status"], "unknown")
        self.spawn.assert_called_once()

    def test_preflight_rejects_unsupported_version_and_login(self):
        for output, error in (("codex-cli 0.156.0", "unsupported_codex_version"),
                              ("codex-cli 0.155.0-alpha.16.3 injected", "unsupported_codex_version")):
            self.run.side_effect = None
            self.run.return_value = subprocess.CompletedProcess([], 0, output, "")
            self.assertEqual(self.manager.start("task")["error"], error)
        self.run.side_effect = [subprocess.CompletedProcess([], 0, "codex-cli 0.155.0-alpha.16.3", ""),
                                subprocess.CompletedProcess([], 0, "", "Logged in using API key: SECRET")]
        self.assertEqual(self.manager.start("task")["error"], "chatgpt_login_required")
        self.spawn.assert_not_called()

    def test_current_schema_compatible_version_is_explicitly_allowed(self):
        self.run.side_effect = [subprocess.CompletedProcess([], 0, "codex-cli 0.158.0-alpha.2.1", ""),
                               subprocess.CompletedProcess([], 0, "", "Logged in using ChatGPT")]
        self.assertEqual(self.manager.preflight(), {"ready": True})

    def test_receiver_health_and_pause_are_required(self):
        for state, timestamp in (("ready", time.time() - 91), ("ready", time.time() + 100),
                                 ("failed", time.time())):
            self.health.write_text(json.dumps({"state": state, "updated_at": timestamp}))
            self.assertEqual(self.manager.preflight()["error"], "receiver_not_ready")
        self.health.write_text(json.dumps({"state": "ready", "updated_at": time.time()}))
        (self.base / "receiver-paused").touch()
        self.assertEqual(self.manager.preflight()["error"], "receiver_not_ready")
        self.run.assert_not_called()

    def test_explicit_executable_and_existing_config_required(self):
        self.manager.codex = Path("codex.exe")
        self.assertEqual(self.manager.preflight()["error"], "invalid_codex_executable")
        self.manager.codex = self.codex
        self.config.unlink()
        self.assertEqual(self.manager.preflight()["error"], "missing_receiver_configuration")

    def test_cancel_marker_no_kill_and_terminal_receipt_respected(self):
        self.manager.start("task")
        self.report()
        self.assertEqual(self.manager.cancel("task")["status"], "cancel_requested")
        self.assertTrue((self.base / "runs/task/cancel-requested").is_file())
        self.spawn.return_value.kill.assert_not_called()
        self.spawn.return_value.terminate.assert_not_called()
        self.report(status="completed", phase="completed")
        self.assertEqual(self.manager.cancel("task")["status"], "completed")

    def test_restart_unknown_and_report_allowlist(self):
        self.manager.start("task")
        self.report(secret="SECRET", text="PRIVATE", reply_dispatched=True)
        status = self.new_manager().status("task")
        self.assertEqual(status["execution_state"], "unknown")
        self.assertEqual(status["status"], "unknown")
        self.assertEqual(status["report"]["phase"], "waiting_reply")
        self.assertNotIn("SECRET", json.dumps(status))
        self.assertNotIn("PRIVATE", json.dumps(status))
        self.spawn.return_value.poll.return_value = 1
        self.assertEqual(self.manager.status("task")["execution_state"], "exited")
        self.assertEqual(self.manager.status("task")["status"], "unknown")

    def test_invalid_ids_cannot_create_paths_or_spawn(self):
        for task_id in ("", "../task", "task/name", "x" * 101, "a\\b", "é", None):
            for operation in (self.manager.start, self.manager.status, self.manager.cancel):
                self.assertEqual(operation(task_id)["status"], "error")
        self.spawn.assert_not_called()

    def test_preflight_timeout_does_not_disclose_exception(self):
        self.run.side_effect = subprocess.TimeoutExpired("SECRET", 10)
        self.assertEqual(self.manager.preflight(), {"ready": False, "error": "codex_preflight_failed"})

    def discovery_candidate(self, name, timestamp):
        path = self.base / "OpenAI/Codex/bin" / name / "codex.exe"
        path.parent.mkdir(parents=True)
        path.touch()
        os.utime(path, (timestamp, timestamp))
        return path

    def auto_manager(self):
        self.enterContext(patch.dict(os.environ, {"LOCALAPPDATA": str(self.base)}))
        return OwnedTaskManager(self.base / "runs", None, self.database, self.config)

    def test_discovery_is_lazy_and_start_passes_verified_candidate(self):
        candidate = self.discovery_candidate("installed", 100)
        manager = self.auto_manager()
        self.run.assert_not_called()
        self.assertIsNone(manager.codex)
        self.assertEqual(manager.start("task")["execution_state"], "running")
        self.assertEqual(manager.codex, candidate)
        self.assertIn(str(candidate), self.spawn.call_args.args[0])
        self.assertEqual([call.args[0][1:] for call in self.run.call_args_list],
                         [["--version"], ["login", "status"]])

    def test_discovery_selects_supported_older_candidate(self):
        older = self.discovery_candidate("older", 100)
        newer = self.discovery_candidate("newer", 200)
        manager = self.auto_manager()
        self.run.side_effect = [
            subprocess.CompletedProcess([], 0, "codex-cli 0.999.0", ""),
            subprocess.CompletedProcess([], 0, manager.SUPPORTED_VERSION, ""),
            subprocess.CompletedProcess([], 0, "", "Logged in using ChatGPT")]
        self.assertEqual(manager.preflight(), {"ready": True})
        self.assertEqual([call.args[0][0] for call in self.run.call_args_list],
                         [str(newer), str(older), str(older)])

    def test_discovery_missing_has_no_launch_or_path_fallback(self):
        manager = self.auto_manager()
        # An executable directly in LOCALAPPDATA is outside the known layout.
        self.assertTrue(self.codex.exists())
        self.assertEqual(manager.start("task")["error"], "codex_not_found")
        self.run.assert_not_called()
        self.spawn.assert_not_called()
        self.assertFalse((self.base / "runs/task").exists())

    def test_discovery_candidate_count_and_probe_options_are_bounded(self):
        for index in range(10):
            self.discovery_candidate(str(index), 100 + index)
        manager = self.auto_manager()
        self.run.side_effect = None
        self.run.return_value = subprocess.CompletedProcess([], 0, "unsupported SECRET", "")
        self.assertEqual(manager.preflight(), {"ready": False, "error": "unsupported_codex_version"})
        self.assertEqual(self.run.call_count, 8)
        self.assertEqual([Path(call.args[0][0]).parent.name for call in self.run.call_args_list],
                         [str(index) for index in range(9, 1, -1)])
        for call in self.run.call_args_list:
            self.assertGreater(call.kwargs["timeout"], 0)
            self.assertLessEqual(call.kwargs["timeout"], 10)
            self.assertFalse(call.kwargs["shell"])
            self.assertEqual(call.kwargs["stdin"], subprocess.DEVNULL)
        self.spawn.assert_not_called()

    def test_discovery_total_probe_budget(self):
        self.discovery_candidate("one", 100)
        self.discovery_candidate("two", 200)
        manager = self.auto_manager()
        self.run.side_effect = subprocess.TimeoutExpired("SECRET", 10)
        with patch("owned_task_manager.time.monotonic", side_effect=[100, 100, 111]):
            self.assertEqual(manager.preflight(), {"ready": False, "error": "codex_preflight_failed"})
        self.run.assert_called_once()
        self.spawn.assert_not_called()

    def test_discovery_requires_receiver_before_probing(self):
        self.discovery_candidate("supported", 100)
        manager = self.auto_manager()
        self.health.unlink()
        self.assertEqual(manager.preflight()["error"], "receiver_not_ready")
        self.run.assert_not_called()

    def test_discovery_rejects_missing_or_relative_install_root(self):
        manager = self.auto_manager()
        for value in ("", "relative/path"):
            with patch.dict(os.environ, {"LOCALAPPDATA": value}):
                self.assertEqual(manager.preflight()["error"], "codex_not_found")
        self.run.assert_not_called()

    def test_explicit_override_never_falls_back(self):
        self.discovery_candidate("supported", 100)
        self.enterContext(patch.dict(os.environ, {"LOCALAPPDATA": str(self.base)}))
        self.run.side_effect = None
        self.run.return_value = subprocess.CompletedProcess([], 0, "unsupported", "")
        self.assertEqual(self.manager.preflight()["error"], "unsupported_codex_version")
        self.assertEqual(self.run.call_args.args[0][0], str(self.codex))
        self.run.assert_called_once()
        self.codex.unlink()
        self.run.reset_mock()
        self.assertEqual(self.manager.preflight()["error"], "invalid_codex_executable")
        self.run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
