from __future__ import annotations

import importlib.util
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "skills/verify-before-push/scripts/verify_before_push.py"


class VerificationWorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.canonical = self.root / "canonical"
        self.docs_source = self.root / "docs-source"
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        for repo in (self.canonical, self.docs_source):
            repo.mkdir()
            self.git(repo, "init")
            self.git(repo, "config", "user.name", "Fixture")
            self.git(repo, "config", "user.email", "fixture@example.test")
            (repo / "subject.txt").write_text("initial\n", encoding="utf-8")
            self.git(repo, "add", ".")
            self.git(repo, "commit", "-m", "initial")
        self.config_path = self.canonical / ".agents/verify-before-push/config.json"
        self.config_path.parent.mkdir(parents=True)
        self.config = {
            "version": 1,
            "repositories": [
                {"name": "application", "path": ".", "require_upstream_current": False},
                {"name": "documentation", "path": "../missing-docs", "require_upstream_current": False},
            ],
            "checks": [
                {"name": role, "cwd": cwd, "command": [sys.executable, "-c",
                 f"from pathlib import Path; assert Path.cwd().name == {role!r}"]}
                for role, cwd in (("application", "."), ("documentation", "../missing-docs"))
            ],
        }
        self.save_config()
        self.git(self.canonical, "add", ".")
        self.git(self.canonical, "commit", "-m", "configure")
        self.application = self.workspace / "application"
        self.documentation = self.workspace / "documentation"
        self.git(self.canonical, "worktree", "add", "-b", "task", str(self.application))
        self.git(self.docs_source, "worktree", "add", "-b", "task", str(self.documentation))
        self.mapping = {"version": 1, "workspace_root": str(self.workspace),
                        "repositories": {"application": "application", "documentation": "documentation"}}
        self.map_path = self.root / "workspace-map.json"
        self.save_map()

    def git(self, repo: Path, *args: str) -> str:
        result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)
        self.assertEqual(0, result.returncode, result.stderr)
        return result.stdout.strip()

    def save_config(self) -> None:
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")

    def save_map(self) -> None:
        self.map_path.write_text(json.dumps(self.mapping), encoding="utf-8")

    def helper(self, command: str, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(SCRIPT), command, "--project-root", str(self.canonical),
                               "--workspace-map", str(self.map_path), *extra], capture_output=True, text=True)

    def module(self):
        spec = importlib.util.spec_from_file_location("workspace_verifier", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_linked_worktrees_run_with_dirty_canonical_and_missing_original_sibling(self) -> None:
        (self.canonical / "subject.txt").write_text("unrelated dirty work\n", encoding="utf-8")
        before = self.config_path.read_bytes()
        result = self.helper("run")
        self.assertEqual(0, result.returncode, result.stderr)
        receipts = list((self.workspace / ".verify-before-push-evidence").glob("*.json"))
        self.assertEqual(1, len(receipts))
        receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
        self.assertEqual([str(self.application), str(self.documentation)],
                         [entry["path"] for entry in receipt["repositories"]])
        self.assertEqual(before, self.config_path.read_bytes())
        self.assertEqual(0, self.helper("verify").returncode)
        self.assertEqual(0, self.helper("gate", "--repository", str(self.application)).returncode)

    def test_paired_repository_change_invalidates_application_gate(self) -> None:
        self.assertEqual(0, self.helper("run").returncode)
        (self.documentation / "subject.txt").write_text("changed\n", encoding="utf-8")
        result = self.helper("gate", "--repository", str(self.application))
        self.assertNotEqual(0, result.returncode)
        self.assertIn("not clean", result.stderr)

    def test_same_sha_alternate_worktree_cannot_use_other_map_receipt(self) -> None:
        verifier = self.module()
        old = verifier.run_verification(self.canonical, workspace_map=self.map_path)
        alternate = self.workspace / "alternate"
        self.git(self.canonical, "worktree", "add", "-b", "alternate", str(alternate), "task")
        self.assertEqual(self.git(self.application, "rev-parse", "HEAD"), self.git(alternate, "rev-parse", "HEAD"))
        self.mapping["repositories"]["application"] = "alternate"
        self.save_map()
        new = verifier.load_execution_context(self.canonical, self.map_path)[3]
        self.assertNotEqual(old, new)
        new.write_bytes(old.read_bytes())
        with self.assertRaisesRegex(verifier.VerificationError, "configuration"):
            verifier.verify_evidence(self.canonical, workspace_map=self.map_path)

    def test_source_config_change_invalidates_existing_receipt(self) -> None:
        verifier = self.module()
        old = verifier.run_verification(self.canonical, workspace_map=self.map_path)
        self.config["checks"][0]["timeout_seconds"] = 601
        self.save_config()
        new = verifier.load_execution_context(self.canonical, self.map_path)[3]
        self.assertNotEqual(old, new)
        new.write_bytes(old.read_bytes())
        with self.assertRaisesRegex(verifier.VerificationError, "configuration"):
            verifier.verify_evidence(self.canonical, workspace_map=self.map_path)

    def test_identical_config_from_another_canonical_root_has_distinct_binding(self) -> None:
        verifier = self.module()
        old = verifier.run_verification(self.canonical, workspace_map=self.map_path)
        other = self.root / "another-canonical"
        target = other / ".agents/verify-before-push/config.json"
        target.parent.mkdir(parents=True)
        target.write_bytes(self.config_path.read_bytes())
        new = verifier.load_execution_context(other, self.map_path)[3]
        self.assertNotEqual(old, new)
        new.write_bytes(old.read_bytes())
        with self.assertRaisesRegex(verifier.VerificationError, "configuration"):
            verifier.verify_evidence(other, workspace_map=self.map_path)

    def test_map_and_config_mutation_during_checks_never_write_receipt(self) -> None:
        verifier = self.module()
        execute = verifier.execute_checks
        original_config = json.loads(json.dumps(self.config))
        original_map = json.loads(json.dumps(self.mapping))
        alternate = self.workspace / "alternate"
        self.git(self.canonical, "worktree", "add", "-b", "alternate", str(alternate), "task")
        for change in ("configuration", "map"):
            with self.subTest(change=change):
                self.config = json.loads(json.dumps(original_config))
                self.mapping = json.loads(json.dumps(original_map))
                self.save_config()
                self.save_map()
                receipt = verifier.load_execution_context(self.canonical, self.map_path)[3]

                def execute_and_change(*args, **kwargs):
                    results = execute(*args, **kwargs)
                    if change == "configuration":
                        self.config["checks"][0]["timeout_seconds"] = 700
                        self.save_config()
                    else:
                        self.mapping["repositories"]["application"] = "alternate"
                        self.save_map()
                    return results

                with patch.object(verifier, "execute_checks", side_effect=execute_and_change):
                    with self.assertRaisesRegex(verifier.VerificationError, "changed while checks"):
                        verifier.run_verification(self.canonical, workspace_map=self.map_path)
                self.assertFalse(receipt.exists())

    def test_invalid_roles_and_paths_fail_before_checks(self) -> None:
        verifier = self.module()
        valid = json.loads(json.dumps(self.mapping))
        invalid_roles = [
            {"application": "application"},
            {**valid["repositories"], "unknown": "documentation"},
            {"application": "application", "documentation": "application"},
        ]
        invalid_paths = ["../canonical", "application/../documentation", "/absolute", "C:/absolute",
                         "C:relative", "//server/share", "..\\canonical", "application\\child", "", "application//child",
                         "application/./child", "application/colon:name", "a" * 301, "application\0"]
        for roles in invalid_roles + [{**valid["repositories"], "application": value} for value in invalid_paths]:
            with self.subTest(roles=roles):
                self.mapping = {**valid, "repositories": roles}
                self.save_map()
                with patch.object(verifier, "execute_checks") as execute:
                    with self.assertRaises(verifier.VerificationError):
                        verifier.run_verification(self.canonical, workspace_map=self.map_path)
                    execute.assert_not_called()

    def test_duplicate_json_keys_and_unknown_map_fields_fail_closed(self) -> None:
        verifier = self.module()
        for text in ('{"version":1,"version":1}', json.dumps({**self.mapping, "unknown": True}),
                     json.dumps({**self.mapping, "version": True}),
                     json.dumps({**self.mapping, "workspace_root": "relative"})):
            with self.subTest(text=text):
                self.map_path.write_text(text, encoding="utf-8")
                with self.assertRaises(verifier.VerificationError):
                    verifier.load_execution_context(self.canonical, self.map_path)

    def test_non_exact_git_root_and_ambiguous_cwd_owner_fail(self) -> None:
        verifier = self.module()
        (self.application / "nested").mkdir()
        self.mapping["repositories"]["application"] = "application/nested"
        self.save_map()
        with self.assertRaisesRegex(verifier.VerificationError, "Git root"):
            verifier.load_execution_context(self.canonical, self.map_path)
        self.mapping["repositories"]["application"] = "application"
        self.save_map()
        self.config["repositories"][1]["path"] = "nested"
        self.config["checks"][1]["cwd"] = "nested"
        self.save_config()
        with self.assertRaisesRegex(verifier.VerificationError, "unambiguous"):
            verifier.load_execution_context(self.canonical, self.map_path)

    def test_mapped_subdirectory_cwd_preserves_suffix_and_check_flags(self) -> None:
        verifier = self.module()
        (self.application / "nested").mkdir()
        self.config["checks"][0].update(cwd="nested", enabled=False, required=False,
                                         skip_reason="fixture", timeout_seconds=12)
        self.save_config()
        source, effective, root, _, _ = verifier.load_execution_context(self.canonical, self.map_path)
        self.assertEqual(self.workspace, root)
        expected = dict(source["checks"][0], cwd="application/nested")
        self.assertEqual(expected, effective["checks"][0])
        self.assertEqual(source["repositories"][0]["require_upstream_current"],
                         effective["repositories"][0]["require_upstream_current"])

    def test_mapped_upstream_requirement_is_enforced(self) -> None:
        self.config["repositories"][0]["require_upstream_current"] = True
        self.save_config()
        result = self.helper("run")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("no fetchable upstream remote", result.stderr)

    def test_absolute_old_root_command_is_rejected_without_rewriting(self) -> None:
        verifier = self.module()
        for argument in (str(self.canonical / "check.py"), "../../canonical/check.py"):
            with self.subTest(argument=argument):
                self.config["checks"][0]["command"] = [sys.executable, argument]
                self.save_config()
                with self.assertRaisesRegex(verifier.VerificationError, "old canonical root"):
                    verifier.load_execution_context(self.canonical, self.map_path)

    def test_mapped_version_two_reuse_preserves_receipt(self) -> None:
        verifier = self.module()
        for index, repo in enumerate((self.application, self.documentation)):
            remote = self.root / f"remote-{index}.git"
            self.git(self.root, "init", "--bare", str(remote))
            self.git(repo, "remote", "add", "origin", str(remote))
            self.git(repo, "push", "-u", "origin", "task")
            self.config["repositories"][index]["require_upstream_current"] = True
        self.config["reuse_verified_results"] = True
        self.save_config()
        trusted = hashlib.sha256(str(self.root).encode()).hexdigest()
        clean_path = os.pathsep.join(entry for entry in os.get_exec_path() if Path(entry).is_absolute())
        with patch.dict(os.environ, {"PATH": clean_path}):
            receipt = verifier.run_verification(self.canonical, trusted, self.map_path)
            before = receipt.read_bytes()
            self.assertEqual(2, json.loads(before)["version"])
            with patch.object(verifier, "execute_checks", side_effect=AssertionError("reuse executed checks")):
                self.assertEqual(receipt, verifier.run_verification(self.canonical, trusted, self.map_path))
            self.assertEqual(before, receipt.read_bytes())
            self.assertTrue(verifier.verify_evidence(self.canonical, self.application, trusted, self.map_path))

    def test_receipt_cannot_be_inside_canonical_or_mapped_repository(self) -> None:
        verifier = self.module()
        nested = self.canonical / "nested-docs"
        self.git(self.docs_source, "worktree", "add", "-b", "receipt-test", str(nested))
        self.mapping["workspace_root"] = str(self.canonical)
        self.mapping["repositories"] = {"application": ".", "documentation": "nested-docs"}
        self.save_map()
        with self.assertRaisesRegex(verifier.VerificationError, "outside canonical and mapped repositories"):
            verifier.load_execution_context(self.canonical, self.map_path)

    def make_directory_link(self, link: Path, target: Path) -> None:
        if os.name == "nt":
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True)
            if result.returncode:
                self.skipTest("Directory junction creation is unavailable")
            self.addCleanup(lambda: os.rmdir(link) if link.exists() else None)
        else:
            os.symlink(target, link, target_is_directory=True)
            self.addCleanup(lambda: link.unlink(missing_ok=True))

    def test_descendant_junction_or_symlink_is_rejected_even_for_inside_target(self) -> None:
        verifier = self.module()
        self.make_directory_link(self.workspace / "alias", self.application)
        self.mapping["repositories"]["application"] = "alias"
        self.save_map()
        with self.assertRaisesRegex(verifier.VerificationError, "symlinks or junctions"):
            verifier.load_execution_context(self.canonical, self.map_path)

    def test_receipt_junction_or_symlink_is_rejected(self) -> None:
        verifier = self.module()
        target = self.root / "external-evidence"
        target.mkdir()
        self.make_directory_link(self.workspace / ".verify-before-push-evidence", target)
        with self.assertRaisesRegex(verifier.VerificationError, "symlinks or junctions"):
            verifier.load_execution_context(self.canonical, self.map_path)

    def test_cwd_parent_traversal_cannot_hide_a_junction_or_symlink(self) -> None:
        verifier = self.module()
        (self.application / "nested").mkdir()
        self.make_directory_link(self.application / "alias", self.documentation)
        self.config["checks"][0]["cwd"] = "alias/../nested"
        self.save_config()
        with self.assertRaisesRegex(verifier.VerificationError, "internal parent traversal"):
            verifier.load_execution_context(self.canonical, self.map_path)

    def test_workspace_under_unrelated_git_ancestor_cannot_hold_receipts(self) -> None:
        verifier = self.module()
        self.git(self.root, "init")
        with self.assertRaisesRegex(verifier.VerificationError, "outside every Git worktree"):
            verifier.load_execution_context(self.canonical, self.map_path)

    def test_receipt_git_inspection_error_fails_closed(self) -> None:
        verifier = self.module()
        receipt = self.workspace / ".verify-before-push-evidence" / "receipt.json"
        failed = subprocess.CompletedProcess([], 128, b"", b"fatal: detected dubious ownership in repository")
        with patch.object(verifier, "run_process", return_value=failed):
            with self.assertRaisesRegex(verifier.VerificationError, "Could not establish Git ownership"):
                verifier.validate_workspace_receipt(self.workspace, receipt, [self.application, self.documentation])

    def test_mapped_gate_does_not_authorize_canonical_repository(self) -> None:
        verifier = self.module()
        self.assertFalse(verifier.verify_evidence(self.canonical, repository=self.canonical,
                                                 workspace_map=self.map_path))
        self.assertFalse((self.canonical / ".agents/verify-before-push/evidence.json").exists())


if __name__ == "__main__":
    unittest.main()
