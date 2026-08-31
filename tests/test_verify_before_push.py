from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills/verify-before-push/scripts/verify_before_push.py"
)
PYTHON = shutil.which("python") or sys.executable


class VerifyBeforePushTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.remote = self.root / "remote.git"
        self.project = self.root / "project"
        self.other = self.root / "other"
        self.git(self.root, "init", "--bare", str(self.remote))
        self.git(self.root, "clone", str(self.remote), str(self.project))
        self.configure_identity(self.project)
        (self.project / "tracked.txt").write_text("initial\n", encoding="utf-8")
        self.git(self.project, "add", "tracked.txt")
        self.git(self.project, "commit", "-m", "initial")
        self.git(self.project, "branch", "-M", "main")
        self.git(self.project, "push", "-u", "origin", "main")
        self.write_config()
        self.git(self.project, "add", ".agents", ".gitignore")
        self.git(self.project, "commit", "-m", "configure verification")
        self.git(self.project, "push")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def configure_identity(self, repository: Path) -> None:
        self.git(repository, "config", "user.name", "Test User")
        self.git(repository, "config", "user.email", "test@example.test")

    def write_config(self) -> None:
        directory = self.project / ".agents/verify-before-push"
        directory.mkdir(parents=True)
        config = {
            "version": 1,
            "evidence_file": ".agents/verify-before-push/evidence.json",
            "repositories": [
                {
                    "name": "project",
                    "path": ".",
                    "require_clean": True,
                    "require_upstream_current": True,
                }
            ],
            "checks": [
                {
                    "name": "pass",
                    "cwd": ".",
                    "command": [PYTHON, "-c", "print('ok')"],
                    "required": True,
                },
                {
                    "name": "optional",
                    "cwd": ".",
                    "command": [PYTHON, "-c", "raise SystemExit(1)"],
                    "enabled": False,
                    "required": False,
                    "skip_reason": "fixture does not enable this check",
                },
            ],
        }
        (directory / "config.json").write_text(
            json.dumps(config, indent=2) + "\n", encoding="utf-8"
        )
        (self.project / ".gitignore").write_text(
            ".agents/verify-before-push/evidence.json\n", encoding="utf-8"
        )

    def helper(self, command: str, *extra: str) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment.pop("VERIFY_BEFORE_PUSH_TRUSTED_ENVIRONMENT_SHA256", None)
        if getattr(self, "environment_fingerprint", None) is not None:
            environment["VERIFY_BEFORE_PUSH_TRUSTED_ENVIRONMENT_SHA256"] = self.environment_fingerprint
        if getattr(self, "path_override", None) is not None:
            environment["PATH"] = self.path_override
        return subprocess.run(
            [PYTHON, str(getattr(self, "helper_script", SCRIPT)), command, "--project-root", str(self.project), *extra],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            env=environment,
        )

    @property
    def evidence_path(self) -> Path:
        return self.project / ".agents/verify-before-push/evidence.json"

    def enable_reuse(self, *, trusted: bool = True, require_clean: bool = True) -> None:
        # Positive reuse fixtures deliberately attest an unambiguous PATH.
        # Developer shells may have trailing empty/current-directory entries.
        self.path_override = os.pathsep.join(entry for entry in os.get_exec_path() if Path(entry).is_absolute())
        config_path = self.project / ".agents/verify-before-push/config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["reuse_verified_results"] = True
        config["repositories"][0]["require_clean"] = require_clean
        self.counter = self.root / "check-count.txt"
        config["checks"][0]["command"] = [
            PYTHON, "-c",
            "from pathlib import Path; "
            f"p = Path({str(self.counter)!r}); "
            "p.write_text(str(int(p.read_text()) + 1) if p.exists() else '1')",
        ]
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        self.git(self.project, "add", ".agents/verify-before-push/config.json")
        self.git(self.project, "commit", "-m", "opt into isolated fixture reuse")
        # This fixture attests only its isolated temporary checks; never use a
        # fixed digest as an attestation for an actual project environment.
        self.environment_fingerprint = (
            hashlib.sha256(str(self.root).encode()).hexdigest() if trusted else None
        )

    def assert_success(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(0, result.returncode, result.stderr)

    def test_reuse_after_delivery_preserves_receipt_and_does_not_execute_checks(self) -> None:
        self.enable_reuse()
        self.assert_success(self.helper("run"))
        original = self.evidence_path.read_bytes()
        timestamp = self.evidence_path.stat().st_mtime_ns
        self.git(self.project, "push")
        self.assert_success(self.helper("gate", "--repository", str(self.project)))
        self.assert_success(self.helper("run"))
        self.assertEqual("1", self.counter.read_text())
        self.assertEqual(original, self.evidence_path.read_bytes())
        self.assertEqual(timestamp, self.evidence_path.stat().st_mtime_ns)

    def test_exact_state_reuse_requires_opt_in_and_trusted_environment(self) -> None:
        self.enable_reuse()
        self.assert_success(self.helper("run"))
        self.assert_success(self.helper("run"))
        self.assertEqual("1", self.counter.read_text())
        self.environment_fingerprint = None
        self.assert_success(self.helper("run"))
        self.assertEqual("2", self.counter.read_text())
        self.assertEqual(1, json.loads(self.evidence_path.read_text())["version"])

    def test_same_tree_new_commit_is_not_reused(self) -> None:
        self.enable_reuse()
        self.assert_success(self.helper("run"))
        self.git(self.project, "commit", "--allow-empty", "-m", "same tree, new identity")
        self.assertNotEqual(0, self.helper("verify").returncode)
        self.assert_success(self.helper("run"))
        self.assertEqual("2", self.counter.read_text())

    def test_environment_change_blocks_gate_and_forces_full_run(self) -> None:
        self.enable_reuse()
        self.assert_success(self.helper("run"))
        original = self.evidence_path.read_bytes()
        self.environment_fingerprint = hashlib.sha256(b"changed fixture environment").hexdigest()
        self.assertNotEqual(0, self.helper("verify").returncode)
        self.assertEqual(original, self.evidence_path.read_bytes())
        self.assert_success(self.helper("run"))
        self.assertEqual("2", self.counter.read_text())

    def test_v2_gate_requires_environment_even_without_git_changes(self) -> None:
        self.enable_reuse()
        self.assert_success(self.helper("run"))
        self.environment_fingerprint = None
        self.assertNotEqual(0, self.helper("verify").returncode)

    def test_remote_identity_change_blocks_same_sha_evidence(self) -> None:
        self.enable_reuse()
        self.assert_success(self.helper("run"))
        second_remote = self.root / "second.git"
        self.git(self.root, "clone", "--bare", str(self.remote), str(second_remote))
        self.git(self.project, "remote", "set-url", "origin", str(second_remote))
        self.assertNotEqual(0, self.helper("verify").returncode)

    def test_tracking_branch_change_blocks_same_sha_evidence(self) -> None:
        self.enable_reuse()
        self.assert_success(self.helper("run"))
        self.git(self.project, "branch", "-m", "renamed")
        self.assertNotEqual(0, self.helper("verify").returncode)

    def test_push_url_change_blocks_same_sha_evidence(self) -> None:
        self.enable_reuse()
        self.assert_success(self.helper("run"))
        self.git(self.project, "remote", "set-url", "--push", "origin", str(self.root / "elsewhere.git"))
        self.assertNotEqual(0, self.helper("verify").returncode)

    def test_reuse_requires_fresh_remote_on_every_gate(self) -> None:
        self.enable_reuse()
        self.assert_success(self.helper("run"))
        self.git(self.project, "push")
        self.assert_success(self.helper("verify"))
        self.git(self.remote, "update-ref", "refs/heads/main", "refs/heads/main~2")
        self.assertNotEqual(0, self.helper("verify").returncode)

    def test_partial_delivery_cannot_reuse(self) -> None:
        self.enable_reuse()
        self.git(self.project, "commit", "--allow-empty", "-m", "second ahead commit")
        self.assert_success(self.helper("run"))
        self.git(self.project, "push", "origin", "HEAD~1:refs/heads/main")
        self.assertNotEqual(0, self.helper("verify").returncode)

    def test_legacy_receipt_never_reuses_after_delivery(self) -> None:
        self.enable_reuse(trusted=False)
        self.assert_success(self.helper("run"))
        self.assertEqual(1, json.loads(self.evidence_path.read_text())["version"])
        self.environment_fingerprint = hashlib.sha256(str(self.root).encode()).hexdigest()
        self.git(self.project, "push")
        self.assertNotEqual(0, self.helper("verify").returncode)
        self.assert_success(self.helper("run"))
        self.assertEqual("2", self.counter.read_text())

    def test_configure_rejects_non_boolean_reuse(self) -> None:
        config_path = self.project / ".agents/verify-before-push/config.json"
        config = json.loads(config_path.read_text())
        config["reuse_verified_results"] = "true"
        config_path.write_text(json.dumps(config))
        self.assertNotEqual(0, self.helper("configure").returncode)

    def test_malformed_legacy_check_results_fail_closed(self) -> None:
        self.assert_success(self.helper("run"))
        original = json.loads(self.evidence_path.read_text())
        mutations = [
            lambda checks: checks.append(dict(checks[0])),
            lambda checks: checks[0].update(exit_code=7),
            lambda checks: checks[0].update(exit_code=False),
            lambda checks: checks.pop(),
            lambda checks: checks[1].update(reason="not the approved reason"),
            lambda checks: checks.append({"name": "unknown", "status": "passed", "exit_code": 0}),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutations.index(mutate)):
                evidence = json.loads(json.dumps(original))
                mutate(evidence["checks"])
                self.evidence_path.write_text(json.dumps(evidence))
                self.assertNotEqual(0, self.helper("verify").returncode)

    def test_malformed_receipt_structure_fails_closed(self) -> None:
        self.assert_success(self.helper("run"))
        original = self.evidence_path.read_text()
        malformed = []
        altered = json.loads(original)
        altered["repositories"][0]["clean"] = 1
        malformed.append(json.dumps(altered))
        altered = json.loads(original)
        altered["unexpected"] = "invalid evidence field"
        malformed.append(json.dumps(altered))
        malformed.append(original.replace('"version": 1', '"version": 2, "version": 1'))
        for index, content in enumerate(malformed):
            with self.subTest(mutation=index):
                self.evidence_path.write_text(content)
                self.assertNotEqual(0, self.helper("verify").returncode)

    def test_changed_runtime_helper_forces_full_run(self) -> None:
        self.enable_reuse()
        self.helper_script = self.root / "isolated-verifier.py"
        self.helper_script.write_bytes(SCRIPT.read_bytes())
        self.assert_success(self.helper("run"))
        self.helper_script.write_bytes(self.helper_script.read_bytes() + b"\n# changed runtime identity\n")
        self.assertNotEqual(0, self.helper("verify").returncode)
        self.assert_success(self.helper("run"))
        self.assertEqual("2", self.counter.read_text())

    def test_reuse_tracks_dirty_index_and_untracked_content(self) -> None:
        self.enable_reuse(require_clean=False)
        tracked = self.project / "tracked.txt"
        untracked = self.project / "scratch.txt"
        tracked.write_text("dirty one\n")
        untracked.write_text("untracked one\n")
        self.assert_success(self.helper("run"))
        self.assert_success(self.helper("verify"))
        original = self.evidence_path.read_bytes()
        untracked.write_text("untracked two\n")
        self.assertNotEqual(0, self.helper("verify").returncode)
        untracked.write_text("untracked one\n")
        self.git(self.project, "add", "tracked.txt")
        self.assertNotEqual(0, self.helper("verify").returncode)
        self.assertEqual(original, self.evidence_path.read_bytes())

    def test_disabled_reuse_runs_checks_even_with_trusted_environment(self) -> None:
        self.enable_reuse()
        config_path = self.project / ".agents/verify-before-push/config.json"
        config = json.loads(config_path.read_text())
        config["reuse_verified_results"] = False
        config_path.write_text(json.dumps(config))
        self.git(self.project, "add", ".agents/verify-before-push/config.json")
        self.git(self.project, "commit", "-m", "disable reuse")
        self.assert_success(self.helper("run"))
        self.assert_success(self.helper("run"))
        self.assertEqual("2", self.counter.read_text())
        self.assertEqual(1, json.loads(self.evidence_path.read_text())["version"])
        self.git(self.project, "push")
        self.assertNotEqual(0, self.helper("verify").returncode)

    def test_optional_failed_check_never_authorizes_reuse(self) -> None:
        self.enable_reuse()
        config_path = self.project / ".agents/verify-before-push/config.json"
        config = json.loads(config_path.read_text())
        config["checks"][1]["enabled"] = True
        config_path.write_text(json.dumps(config))
        self.git(self.project, "add", ".agents/verify-before-push/config.json")
        self.git(self.project, "commit", "-m", "enable optional failing check")
        self.assert_success(self.helper("run"))
        self.assert_success(self.helper("verify"))
        self.assert_success(self.helper("run"))
        self.assertEqual("2", self.counter.read_text())
        self.assertEqual(1, json.loads(self.evidence_path.read_text())["version"])

    def test_malformed_v2_receipt_forces_full_run(self) -> None:
        self.enable_reuse()
        self.assert_success(self.helper("run"))
        data = json.loads(self.evidence_path.read_text())
        data["receipt_sha256"] = "not a valid digest"
        self.evidence_path.write_text(json.dumps(data))
        self.assertNotEqual(0, self.helper("verify").returncode)
        self.assert_success(self.helper("run"))
        self.assertEqual("2", self.counter.read_text())

    def test_unavailable_remote_fails_without_cached_success(self) -> None:
        self.enable_reuse()
        self.assert_success(self.helper("run"))
        original = self.evidence_path.read_bytes()
        self.remote.rename(self.root / "offline-remote.git")
        self.assertNotEqual(0, self.helper("verify").returncode)
        self.assertEqual(original, self.evidence_path.read_bytes())
        self.assertNotEqual(0, self.helper("run").returncode)
        self.assertEqual("1", self.counter.read_text())
        self.assertFalse(self.evidence_path.exists())

    def test_deleted_upstream_never_uses_stale_tracking(self) -> None:
        self.enable_reuse()
        self.assert_success(self.helper("run"))
        self.git(self.remote, "update-ref", "-d", "refs/heads/main")
        self.assertNotEqual(0, self.helper("verify").returncode)

    def test_explicit_environment_argument_overrides_environment_variable(self) -> None:
        self.enable_reuse()
        original_fingerprint = self.environment_fingerprint
        self.assert_success(self.helper("run"))
        self.environment_fingerprint = hashlib.sha256(b"different environment variable").hexdigest()
        self.assert_success(self.helper("verify", "--trusted-environment-fingerprint", original_fingerprint))
        self.assertNotEqual(0, self.helper("verify", "--trusted-environment-fingerprint", "placeholder").returncode)

    def test_changed_second_repository_invalidates_shared_receipt(self) -> None:
        self.enable_reuse()
        self.git(self.root, "clone", str(self.remote), str(self.other))
        self.configure_identity(self.other)
        self.git(self.other, "switch", "main")
        config_path = self.project / ".agents/verify-before-push/config.json"
        config = json.loads(config_path.read_text())
        config["repositories"].append({"name": "other", "path": "../other", "require_clean": True, "require_upstream_current": True})
        config_path.write_text(json.dumps(config))
        self.git(self.project, "add", ".agents/verify-before-push/config.json")
        self.git(self.project, "commit", "-m", "verify both repositories")
        self.assert_success(self.helper("run"))
        self.git(self.other, "commit", "--allow-empty", "-m", "other repository changes")
        self.assertNotEqual(0, self.helper("gate", "--repository", str(self.project)).returncode)

    def test_unrelated_gate_skips_malformed_checks_but_protected_gate_rejects_them(self) -> None:
        unrelated = self.root / "unrelated"
        self.git(self.root, "init", str(unrelated))
        config_path = self.project / ".agents/verify-before-push/config.json"
        config = json.loads(config_path.read_text())
        config["checks"][0]["command"] = []
        config_path.write_text(json.dumps(config))
        self.assert_success(self.helper("gate", "--repository", str(unrelated)))
        self.assertNotEqual(0, self.helper("gate", "--repository", str(self.project)).returncode)

    def test_relative_path_disables_reuse_without_changing_full_checks(self) -> None:
        self.enable_reuse()
        self.path_override = os.environ.get("PATH", "") + os.pathsep + "relative-tools"
        self.assert_success(self.helper("run"))
        self.assertEqual(1, json.loads(self.evidence_path.read_text())["version"])
        self.assert_success(self.helper("run"))
        self.assertEqual("2", self.counter.read_text())

    def test_run_and_verify_current_evidence(self) -> None:
        run = self.helper("run")
        self.assertEqual(0, run.returncode, run.stderr)
        verified = self.helper("verify")
        self.assertEqual(0, verified.returncode, verified.stderr)
        evidence = json.loads(
            (self.project / ".agents/verify-before-push/evidence.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual("passed", evidence["checks"][0]["status"])
        self.assertEqual("skipped", evidence["checks"][1]["status"])

    def test_configure_and_status_are_idempotent(self) -> None:
        first = self.helper("configure", "--json")
        self.assertEqual(0, first.returncode, first.stderr)
        agents = (self.project / "AGENTS.md").read_bytes()
        config = (self.project / ".agents/verify-before-push/config.json").read_bytes()
        second = self.helper("configure", "--json")
        self.assertEqual(0, second.returncode, second.stderr)
        self.assertFalse(json.loads(second.stdout)["changed"])
        self.assertEqual(agents, (self.project / "AGENTS.md").read_bytes())
        self.assertEqual(config, (self.project / ".agents/verify-before-push/config.json").read_bytes())
        status = self.helper("status", "--json")
        self.assertEqual(0, status.returncode, status.stderr)
        self.assertTrue(json.loads(status.stdout)["configured"])

    def test_evidence_stales_after_worktree_or_commit_change(self) -> None:
        run = self.helper("run")
        self.assertEqual(0, run.returncode, run.stderr)
        (self.project / "untracked.txt").write_text("new\n", encoding="utf-8")
        self.assertNotEqual(0, self.helper("verify").returncode)
        (self.project / "untracked.txt").unlink()
        (self.project / "tracked.txt").write_text("changed\n", encoding="utf-8")
        self.git(self.project, "add", "tracked.txt")
        self.git(self.project, "commit", "-m", "change")
        self.assertNotEqual(0, self.helper("verify").returncode)

    def test_dirty_allowed_fingerprint_tracks_content_changes(self) -> None:
        config_path = self.project / ".agents/verify-before-push/config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["repositories"][0]["require_clean"] = False
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        self.git(self.project, "add", ".agents/verify-before-push/config.json")
        self.git(self.project, "commit", "-m", "allow dirty worktree")
        self.git(self.project, "push")
        (self.project / "tracked.txt").write_text("dirty one\n", encoding="utf-8")
        (self.project / "untracked.txt").write_text("untracked one\n", encoding="utf-8")
        run = self.helper("run")
        self.assertEqual(0, run.returncode, run.stderr)
        (self.project / "tracked.txt").write_text("dirty two\n", encoding="utf-8")
        self.assertNotEqual(0, self.helper("verify").returncode)
        (self.project / "tracked.txt").write_text("dirty one\n", encoding="utf-8")
        (self.project / "untracked.txt").write_text("untracked two\n", encoding="utf-8")
        self.assertNotEqual(0, self.helper("verify").returncode)

    def test_upstream_change_invalidates_evidence(self) -> None:
        run = self.helper("run")
        self.assertEqual(0, run.returncode, run.stderr)
        self.git(self.root, "clone", str(self.remote), str(self.other))
        self.configure_identity(self.other)
        self.git(self.other, "switch", "main")
        (self.other / "remote.txt").write_text("remote\n", encoding="utf-8")
        self.git(self.other, "add", "remote.txt")
        self.git(self.other, "commit", "-m", "remote change")
        self.git(self.other, "push")
        result = self.helper("verify")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("behind upstream", result.stderr)

    def test_gate_ignores_unconfigured_repository(self) -> None:
        unrelated = self.root / "unrelated"
        self.git(self.root, "init", str(unrelated))
        result = self.helper("gate", "--repository", str(unrelated))
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("not gated", result.stdout)

    def test_failed_rerun_invalidates_previous_evidence(self) -> None:
        run = self.helper("run")
        self.assertEqual(0, run.returncode, run.stderr)
        config_path = self.project / ".agents/verify-before-push/config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["checks"][0]["command"] = [PYTHON, "-c", "raise SystemExit(7)"]
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        self.git(self.project, "add", ".agents/verify-before-push/config.json")
        self.git(self.project, "commit", "-m", "make check fail")
        failed = self.helper("run")
        self.assertNotEqual(0, failed.returncode)
        self.assertFalse(
            (self.project / ".agents/verify-before-push/evidence.json").exists()
        )

    @staticmethod
    def git(directory: Path, *args: str) -> None:
        subprocess.run(
            ["git", "-C", str(directory), *args],
            capture_output=True,
            check=True,
        )


class ExecutableIdentityTests(unittest.TestCase):
    def test_relative_path_entries_disable_reuse(self) -> None:
        spec = importlib.util.spec_from_file_location("isolated_verification", SCRIPT)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            caller, check = root / "caller", root / "check"
            for parent in (caller, check):
                (parent / "bin").mkdir(parents=True)
                tool = parent / "bin/check-tool.exe"
                tool.write_bytes(parent.name.encode())
                tool.chmod(0o755)
            previous = Path.cwd()
            try:
                os.chdir(caller)
                with patch.dict(os.environ, {"PATH": "bin"}):
                    with self.assertRaisesRegex(module.VerificationError, "PATH"):
                        module.executable_identity("check-tool.exe", check)
            finally:
                os.chdir(previous)


if __name__ == "__main__":
    unittest.main()
