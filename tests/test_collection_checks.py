from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_release_skill_collection import ReleaseFixture, git, passing_result
import release_collection
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_collection


class SharedCollectionChecksTests(unittest.TestCase):
    def program(self, root):
        value = {"schema_version": 1, "checks": {"fast": {"command": ["{python}", "fast.py"], "timeout_seconds": 10}, "slow": {"command": ["{python}", "slow.py"], "timeout_seconds": 20}}, "profiles": {"preflight": ["fast"], "full": ["fast", "slow"]}}
        (root / "collection-checks.json").write_text(json.dumps(value), encoding="utf-8")
        return value

    def test_plan_is_ordered_read_only_and_resolves_python(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.program(root)
            before = (root / "collection-checks.json").read_bytes()
            with patch.object(check_collection.subprocess, "run", side_effect=AssertionError("plan must not execute")):
                result = check_collection.plan(root, "full")
            self.assertEqual(["fast", "slow"], [item["name"] for item in result["steps"]])
            self.assertEqual(sys.executable, result["steps"][0]["command"][0])
            self.assertEqual(before, (root / "collection-checks.json").read_bytes())

    def test_fail_fast_and_timeout(self):
        import subprocess
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.program(root)
            for response in (subprocess.CompletedProcess([], 1, b"failure", b""), subprocess.TimeoutExpired([], 1)):
                kwargs = {"side_effect": response} if isinstance(response, Exception) else {"return_value": response}
                with patch.object(check_collection.subprocess, "run", **kwargs) as execute:
                    result = check_collection.run(root, "full")
                self.assertFalse(result["passed"])
                self.assertEqual(1, execute.call_count)
                self.assertNotIn("shell", execute.call_args.kwargs)
                self.assertEqual("1", execute.call_args.kwargs["env"]["PYTHONUTF8"])

    def test_invalid_programs_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for mutation in (lambda p: p["profiles"].update(full=["slow", "fast"]), lambda p: p["profiles"].update(full=["fast", "fast"]), lambda p: p["checks"]["fast"].update(command="python fast.py"), lambda p: p["checks"]["fast"].update(timeout_seconds=True), lambda p: p.update(schema_version=True)):
                value = self.program(root)
                mutation(value)
                (root / "collection-checks.json").write_text(json.dumps(value), encoding="utf-8")
                with self.assertRaises(ValueError):
                    check_collection.plan(root, "full")

    def test_duplicate_program_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.program(root)
            path = root / "collection-checks.json"
            value = path.read_text(encoding="utf-8").replace('"schema_version": 1', '"schema_version": 99, "schema_version": 1')
            path.write_text(value, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                check_collection.plan(root, "full")

    def test_repository_profile_runs_bootstrap_before_unit_tests(self):
        root = Path(__file__).resolve().parents[1]
        names = [item["name"] for item in check_collection.plan(root, "full")["steps"]]
        for name in ("versions", "localizations", "security", "bootstrap-codex", "bootstrap-claude"):
            self.assertLess(names.index(name), names.index("unit-tests"))

    def test_version_mismatch_fails_without_importing_manager(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scripts").mkdir()
            (root / "skill-catalog.json").write_text('{"collection_version":"1.0.0"}', encoding="utf-8")
            for name in (".codex-plugin", ".claude-plugin"):
                (root / name).mkdir()
                (root / name / "plugin.json").write_text('{"version":"1.0.0"}', encoding="utf-8")
            (root / "scripts/manage_installed_skills.py").write_text('COLLECTION_VERSION = "0.9.0"\nraise RuntimeError("never execute")', encoding="utf-8")
            self.assertFalse(check_collection.versions(root)["passed"])

    def test_release_uses_declared_shared_full_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = ReleaseFixture(Path(directory))
            (fixture.root / "collection-checks.json").write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
            (fixture.root / "scripts/check_collection.py").write_text("# fixture runner\n", encoding="utf-8")
            git(fixture.root, "add", ".")
            git(fixture.root, "commit", "-qm", "declare shared checks")
            commands = []

            def run(root, name, command, timeout):
                commands.append(command)
                return passing_result(name)

            with patch.object(release_collection, "run_command", side_effect=run):
                result = release_collection.check(fixture.root, fixture.tag, Path(directory) / "output")
            self.assertTrue(result["passed"])
            self.assertIn([sys.executable, "scripts/check_collection.py", "run", "--profile", "full"], commands)


if __name__ == "__main__":
    unittest.main()
