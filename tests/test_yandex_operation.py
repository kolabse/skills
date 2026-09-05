from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIRECTORY = Path(__file__).resolve().parents[1] / "skills/operate-yandex-cloud/scripts"
SCRIPT = SCRIPT_DIRECTORY / "yc_project.py"


class YandexOperationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.project = self.root / "project"
        self.config_path = self.project / ".agents/operate-yandex-cloud/project.yaml"
        self.local_path = self.config_path.with_name("local.yaml")
        self.config_path.parent.mkdir(parents=True)
        self.config_path.write_text('version: 3\ncloud_id: "cloud-a"\nfolder_id: "folder-a"\n', encoding="utf-8")
        self.local_path.write_text('version: 1\nyc_profile: "project-profile"\n', encoding="utf-8")
        with patch.object(sys, "path", [str(SCRIPT_DIRECTORY), *sys.path]):
            spec = importlib.util.spec_from_file_location("yc_project_fixture", SCRIPT)
            self.module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.module)
        self.calls = []
        self.responses = [
            {"id": "subject-a"}, {"id": "cloud-a"}, {"id": "folder-a", "cloud_id": "cloud-a"},
            self.instance("STOPPED"), self.instance("RUNNING"), self.instance("RUNNING"),
        ]

    def instance(self, status="RUNNING", **extra):
        return {"id": "instance-a", "folder_id": "folder-a", "status": status, **extra}

    def runner(self, command, **kwargs):
        self.calls.append((list(command), kwargs))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        if isinstance(response, subprocess.CompletedProcess):
            return response
        return subprocess.CompletedProcess(command, 0, json.dumps(response), "")

    def run_operation(self, arguments=None, runner=None):
        with patch.object(self.module.shutil, "which", return_value=sys.executable):
            return self.module.run_operation(self.project, arguments or ["compute", "instance", "start", "--id", "instance-a"],
                                             runner=runner or self.runner)

    def test_start_proves_identity_and_membership_then_verifies_state_with_explicit_scope(self) -> None:
        result = self.run_operation()
        self.assertEqual("verified", result["status"])
        self.assertEqual([self.instance()], result["instances"])
        self.assertEqual(6, len(self.calls))
        for command, _ in self.calls:
            self.assertEqual(str(Path(sys.executable).resolve()), command[0])
            self.assertIn("--profile=project-profile", command)
            self.assertIn("--cloud-id=cloud-a", command)
            self.assertIn("--folder-id=folder-a", command)
        self.assertIn("start", self.calls[4][0])
        self.assertIn("get", self.calls[5][0])

    def test_unsupported_operations_overrides_and_ambiguous_ids_make_no_calls(self) -> None:
        invalid = [[], ["compute", "instance", "delete", "--id", "instance-a"],
                   ["compute", "instance", "show", "--id", "instance-a"],
                   ["compute", "instance", "list", "--id", "instance-a"],
                   ["compute", "instance", "get", "instance-a"],
                   ["compute", "instance", "get", "--name", "instance-a"]]
        for flag in ("--profile", "--cloud-id", "--folder-id", "--folder-name", "--endpoint", "--token",
                     "--impersonate-service-account-id", "--async", "--jq", "--full", "--format", "--", "-h"):
            invalid.append(["compute", "instance", "start", "--id", "instance-a", flag, "DO-NOT-ECHO"])
        for resource in ("--profile", "--", "-instance", "instance\0", "instance\n", "a" * 51, "id;secret"):
            invalid.append(["compute", "instance", "get", "--id", resource])
        for arguments in invalid:
            with self.subTest(arguments=arguments):
                with patch.object(self.module, "configuration_snapshot") as config:
                    with self.assertRaises(self.module.OperationError) as raised:
                        self.module.run_operation(self.project, arguments, runner=self.runner)
                    self.assertEqual(2, raised.exception.exit_code)
                    self.assertNotIn("DO-NOT-ECHO", json.dumps(raised.exception.as_dict()))
                    config.assert_not_called()
        self.assertEqual([], self.calls)

    def test_missing_folder_profile_or_cli_blocks_without_remote_calls(self) -> None:
        for missing in ("folder", "profile", "cli"):
            with self.subTest(missing=missing):
                original = self.config_path.read_bytes(), self.local_path.read_bytes()
                try:
                    if missing == "folder":
                        self.config_path.write_text('version: 3\ncloud_id: "cloud-a"\n', encoding="utf-8")
                    elif missing == "profile":
                        self.local_path.unlink()
                    with patch.object(self.module.shutil, "which", return_value=None if missing == "cli" else sys.executable):
                        with self.assertRaises(self.module.OperationError) as raised:
                            self.module.run_operation(self.project, ["compute", "instance", "list"], runner=self.runner)
                        self.assertIn("configure" if missing != "cli" else "install", str(raised.exception).lower())
                    self.assertEqual([], self.calls)
                finally:
                    self.config_path.write_bytes(original[0])
                    self.local_path.write_bytes(original[1])

    def test_identity_cloud_folder_and_instance_mismatches_stop_before_mutation(self) -> None:
        original = list(self.responses)
        failures = [(0, {}), (0, {"id": "--bad"}), (1, {"id": "cloud-other"}),
                    (2, {"id": "folder-other", "cloud_id": "cloud-a"}),
                    (2, {"id": "folder-a", "cloud_id": "cloud-other"}),
                    (3, self.instance(folder_id="folder-other")), (3, self.instance(id="instance-other")),
                    (3, self.instance(status="PRIVATE-SECRET"))]
        for index, wrong in failures:
            with self.subTest(index=index, wrong=wrong):
                self.calls = []
                self.responses = list(original)
                self.responses[index] = wrong
                with self.assertRaises(self.module.OperationError) as raised:
                    self.run_operation()
                summary = raised.exception.as_dict()
                self.assertEqual(index + 1, len(self.calls))
                self.assertFalse(summary["mutation_attempted"])
                self.assertEqual("blocked", summary["status"])
                self.assertNotIn("PRIVATE-SECRET", json.dumps(summary))

    def test_each_cli_failure_preserves_exit_code_and_never_leaks_output(self) -> None:
        original = list(self.responses)
        for index in range(6):
            with self.subTest(index=index):
                self.calls = []
                self.responses = list(original)
                self.responses[index] = subprocess.CompletedProcess([], 47, "TOKEN-SECRET", "METADATA-SECRET")
                with self.assertRaises(self.module.OperationError) as raised:
                    self.run_operation()
                summary = raised.exception.as_dict()
                self.assertEqual(47, summary["exit_code"])
                self.assertEqual(index + 1, len(self.calls))
                self.assertEqual(index >= 4, summary["mutation_attempted"])
                self.assertNotIn("SECRET", json.dumps(summary))

    def test_malformed_json_and_duplicate_keys_stop_before_mutation(self) -> None:
        original = list(self.responses)
        for output in ("token=SECRET", '{"id":"cloud-a","id":"cloud-other"}', "null"):
            with self.subTest(output=output):
                self.calls = []
                self.responses = list(original)
                self.responses[1] = subprocess.CompletedProcess([], 0, output, "")
                with self.assertRaises(self.module.OperationError) as raised:
                    self.run_operation()
                self.assertEqual(2, len(self.calls))
                self.assertFalse(raised.exception.as_dict()["mutation_attempted"])

    def test_source_and_local_config_changes_after_target_check_block_action(self) -> None:
        original_responses = list(self.responses)
        for path in (self.config_path, self.local_path):
            with self.subTest(path=path.name):
                self.calls = []
                self.responses = list(original_responses)
                original = path.read_bytes()

                def change_after_target(command, **kwargs):
                    result = self.runner(command, **kwargs)
                    if len(self.calls) == 4:
                        path.write_bytes(original + b"\n# changed while checking\n")
                    return result

                with self.assertRaises(self.module.OperationError) as raised:
                    self.run_operation(runner=change_after_target)
                self.assertEqual("configuration", raised.exception.phase)
                self.assertEqual(4, len(self.calls))
                self.assertFalse(raised.exception.as_dict()["mutation_attempted"])
                path.write_bytes(original)

    def test_environment_and_discovered_executable_are_pinned_for_every_call(self) -> None:
        seen = []

        def change_ambient(command, **kwargs):
            seen.append(dict(kwargs["env"]))
            result = self.runner(command, **kwargs)
            os.environ["YC_IAM_TOKEN"] = "changed-secret"
            os.environ["PATH"] = "changed-path"
            kwargs["env"]["YC_IAM_TOKEN"] = "runner-mutated-copy"
            return result

        with patch.dict(os.environ, {"YC_IAM_TOKEN": "initial-secret"}):
            with patch.object(self.module.shutil, "which", return_value=sys.executable) as which:
                result = self.module.run_operation(self.project, ["compute", "instance", "start", "--id", "instance-a"], runner=change_ambient)
                which.assert_called_once()
        self.assertTrue(all(item["YC_IAM_TOKEN"] == "initial-secret" for item in seen))
        self.assertNotIn("secret", json.dumps(result))

    def test_executable_replacement_before_mutation_blocks_action(self) -> None:
        executable = self.root / "yc-fixture"
        executable.write_bytes(b"initial executable")

        def replace(command, **kwargs):
            result = self.runner(command, **kwargs)
            if len(self.calls) == 4:
                executable.write_bytes(b"replacement executable with changed length")
            return result

        with patch.object(self.module.shutil, "which", return_value=str(executable)):
            with self.assertRaises(self.module.OperationError) as raised:
                self.module.run_operation(self.project, ["compute", "instance", "start", "--id", "instance-a"], runner=replace)
        self.assertEqual(4, len(self.calls))
        self.assertFalse(raised.exception.as_dict()["mutation_attempted"])

    def test_list_and_get_filter_all_metadata_and_reject_foreign_list_members(self) -> None:
        preflight = list(self.responses[:3])
        self.responses = [*preflight, [self.instance(metadata={"password": "SECRET"}, name="SECRET", network_interfaces=["SECRET"])]]
        result = self.run_operation(["compute", "instance", "list"])
        self.assertEqual([self.instance()], result["instances"])
        self.assertNotIn("SECRET", json.dumps(result))
        self.responses = [*preflight, self.instance(metadata={"token": "SECRET"})]
        result = self.run_operation(["compute", "instance", "get", "--id", "instance-a"])
        self.assertEqual([self.instance()], result["instances"])
        self.assertFalse(result["mutation_attempted"])
        for instances in ([self.instance(folder_id="folder-other")], [self.instance(), self.instance()]):
            self.responses = [*preflight, instances]
            with self.assertRaises(self.module.OperationError):
                self.run_operation(["compute", "instance", "list"])

    def test_stop_and_restart_require_fresh_expected_status(self) -> None:
        original = list(self.responses)
        for action, status in (("stop", "STOPPED"), ("restart", "RUNNING")):
            with self.subTest(action=action):
                self.responses = [*original[:4], self.instance(status), self.instance(status)]
                result = self.run_operation(["compute", "instance", action, "--id", "instance-a"])
                self.assertEqual(status, result["instances"][0]["status"])
        self.responses = [*original[:5], self.instance("STOPPED")]
        with self.assertRaises(self.module.OperationError) as raised:
            self.run_operation()
        self.assertEqual("postverify", raised.exception.phase)
        self.assertEqual("unverified", raised.exception.as_dict()["status"])

    def test_action_output_is_discarded_and_fresh_get_is_always_required(self) -> None:
        original = list(self.responses)
        for output in ("", '{"id":"operation-a","done":true}', "PRIVATE-SECRET"):
            with self.subTest(output=output):
                self.calls = []
                self.responses = list(original)
                self.responses[4] = subprocess.CompletedProcess([], 0, output, "PRIVATE-SECRET")
                result = self.run_operation()
                self.assertEqual(6, len(self.calls))
                self.assertIn("get", self.calls[-1][0])
                self.assertEqual([self.instance()], result["instances"])
                self.assertNotIn("SECRET", json.dumps(result))
        self.responses = list(original)
        self.responses[4] = subprocess.CompletedProcess([], 0, "", "")
        self.responses[5] = self.instance(folder_id="folder-other")
        with self.assertRaises(self.module.OperationError) as raised:
            self.run_operation()
        self.assertEqual("postverify", raised.exception.phase)
        self.assertTrue(raised.exception.as_dict()["mutation_attempted"])

    def test_whoami_accepts_safe_plain_and_json_subject_identifiers(self) -> None:
        original = list(self.responses)
        for subject in (json.dumps("subject-a"), "subject-a\n", json.dumps({"id": "subject-a"})):
            self.responses = list(original)
            self.responses[0] = subprocess.CompletedProcess([], 0, subject, "")
            self.assertEqual("verified", self.run_operation()["status"])

    def test_timeout_and_unexpected_runner_errors_are_sanitized(self) -> None:
        original = list(self.responses)
        for failure in (subprocess.TimeoutExpired(["SECRET"], 600, output="SECRET"), RuntimeError("SECRET")):
            self.responses = list(original)
            self.responses[4] = failure
            with self.assertRaises(self.module.OperationError) as raised:
                self.run_operation()
            self.assertTrue(raised.exception.as_dict()["mutation_attempted"])
            self.assertNotIn("SECRET", json.dumps(raised.exception.as_dict()))

    def test_main_preserves_child_nonzero_and_never_echoes_rejected_tokens(self) -> None:
        self.responses[4] = subprocess.CompletedProcess([], 47, "SECRET", "SECRET")
        with patch.object(self.module.shutil, "which", return_value=sys.executable), patch.object(self.module.subprocess, "run", side_effect=self.runner):
            with patch("sys.stdout", new_callable=io.StringIO) as output:
                code = self.module.main(["--project-path", str(self.project), "--", "compute", "instance", "start", "--id", "instance-a"])
            self.assertEqual(47, code)
            self.assertEqual("unverified", json.loads(output.getvalue())["status"])
        with patch("sys.stdout", new_callable=io.StringIO) as output:
            code = self.module.main(["--token=SECRET", "--project-path", str(self.project)])
        self.assertEqual(2, code)
        self.assertNotIn("SECRET", output.getvalue())

    def test_copied_install_cli_runs_with_its_sibling_module(self) -> None:
        installed = self.root / "installed"
        installed.mkdir()
        for name in ("yc_project.py", "cloud_skill.py"):
            shutil.copy2(SCRIPT_DIRECTORY / name, installed / name)
        harness = installed / "fixture_cli.py"
        harness.write_text(
            "import json, subprocess, sys\nimport yc_project\n"
            "responses = [dict(id='subject-a'), dict(id='cloud-a'), dict(id='folder-a', cloud_id='cloud-a'), []]\n"
            "def runner(command, **kwargs):\n"
            "    assert '--folder-id=folder-a' in command\n"
            "    return subprocess.CompletedProcess(command, 0, json.dumps(responses.pop(0)), '')\n"
            "yc_project.shutil.which = lambda *args, **kwargs: sys.executable\n"
            "yc_project.subprocess.run = runner\n"
            "raise SystemExit(yc_project.main())\n", encoding="utf-8")
        result = subprocess.run([sys.executable, str(harness), "--project-path", str(self.project), "--",
                                 "compute", "instance", "list"], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([], json.loads(result.stdout)["instances"])


if __name__ == "__main__":
    unittest.main()
