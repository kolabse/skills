from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


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
        return subprocess.run(
            [PYTHON, str(SCRIPT), command, "--project-root", str(self.project), *extra],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

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


if __name__ == "__main__":
    unittest.main()
