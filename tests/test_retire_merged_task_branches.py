from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "skills/retire-merged-task-branches/scripts/retire_branches.py"
SPEC = importlib.util.spec_from_file_location("retire_branches", SCRIPT)
assert SPEC and SPEC.loader
RETIRE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RETIRE)


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


class RetireMergedTaskBranchesTests(unittest.TestCase):
    """All deletion targets are disposable local repos; only provider reads are mocked."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / "project"
        self.root.mkdir()
        self.remote = self.base / "remote.git"
        subprocess.run(["git", "init", "--bare", str(self.remote)], check=True, capture_output=True)
        git(self.root, "init", "-b", "main")
        git(self.root, "config", "user.name", "Retirement Tests")
        git(self.root, "config", "user.email", "tests@example.invalid")
        git(self.root, "config", "commit.gpgsign", "false")
        git(self.root, "config", "url." + self.remote.as_posix() + ".insteadOf", "https://github.com/example/project.git")
        git(self.root, "remote", "add", "origin", "https://github.com/example/project.git")
        (self.root / ".gitignore").write_text("ignored.tmp\n", encoding="utf-8")
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "initial")
        git(self.root, "push", "-u", "origin", "main")
        self.initial = git(self.root, "rev-parse", "HEAD")
        git(self.root, "switch", "-c", "feature/completed")
        (self.root / "task.txt").write_text("completed work\n", encoding="utf-8")
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "task")
        git(self.root, "push", "-u", "origin", "feature/completed")
        self.task = git(self.root, "rev-parse", "HEAD")
        git(self.root, "switch", "main")
        self.review = {
            "merged": True,
            "base": {"repo": {"full_name": "example/project"}, "ref": "main"},
            "head": {"repo": {"full_name": "example/project"}, "ref": "feature/completed", "sha": self.task},
            "merge_commit_sha": self.task,
        }
        self.branch_protected = False
        self.options = {
            "project_root": str(self.root), "remote": "origin", "primary": "main",
            "branch": "feature/completed", "provider": "github", "repository": "example/project",
            "review": 1, "host": None, "remove_worktree": [], "allowed_root": [],
            "inactive_worktree": [], "restore_primary": False,
        }
        self.original_execute = RETIRE.execute
        self.provider = mock.patch.object(RETIRE, "execute", side_effect=self.execute)
        self.provider.start()
        self.addCleanup(self.provider.stop)
        # The transport is always a disposable bare repo. Preserve real identity
        # validation for every URL except this exact test transport endpoint.
        original_identity = RETIRE.identity
        identity = mock.patch.object(
            RETIRE, "identity", side_effect=lambda url: ("github.com", "example/project")
            if url.replace("\\", "/") == self.remote.as_posix() else original_identity(url))
        identity.start()
        self.addCleanup(identity.stop)

    def execute(self, argv, cwd, input_text=None):
        if argv[0] == "gh":
            if "/branches/" in argv[-1]:
                return json.dumps({"name": "feature/completed", "protected": self.branch_protected,
                                   "commit": {"sha": self.task}})
            return json.dumps(self.review)
        return self.original_execute(argv, cwd, input_text=input_text)

    def merge(self, method="normal"):
        if method == "normal":
            git(self.root, "merge", "--no-ff", "feature/completed", "-m", "Merge task")
        elif method == "squash":
            git(self.root, "merge", "--squash", "feature/completed")
            git(self.root, "commit", "-m", "Squash task")
        elif method == "rebase":
            git(self.root, "commit", "--allow-empty", "-m", "Advance primary")
            git(self.root, "cherry-pick", self.initial + ".." + self.task)
        git(self.root, "push", "origin", "main")
        self.review["merge_commit_sha"] = git(self.root, "rev-parse", "HEAD")

    def write_plan(self):
        plan = RETIRE.make_plan(self.options)
        path = self.base / "plan.json"
        path.write_text(json.dumps(plan), encoding="utf-8")
        return path, plan

    def assert_retained(self):
        self.assertEqual(self.task, git(self.root, "rev-parse", "refs/heads/feature/completed"))
        self.assertIn(self.task, git(self.root, "ls-remote", "origin", "refs/heads/feature/completed"))

    def test_normal_merge_can_retire_verified_branch(self):
        self.merge()
        path, plan = self.write_plan()
        result = RETIRE.apply_plan(self.root, path, plan["digest"])
        self.assertEqual("applied", result["status"])
        self.assertEqual("", git(self.root, "ls-remote", "origin", "refs/heads/feature/completed"))
        self.assertNotIn("feature/completed", git(self.root, "branch", "--list"))
        self.assertEqual("main", git(self.root, "branch", "--show-current"))

    def test_open_review_blocks_even_ancestor_branch(self):
        self.merge()
        self.review["merged"] = False
        with self.assertRaises(RETIRE.Blocked):
            self.write_plan()
        self.assert_retained()

    def test_wrong_review_target_blocks(self):
        self.merge()
        self.review["base"]["ref"] = "other"
        with self.assertRaises(RETIRE.Blocked):
            self.write_plan()
        self.assert_retained()

    def test_digest_tampering_blocks_before_deletion(self):
        self.merge()
        path, plan = self.write_plan()
        plan["options"]["branch"] = "main"
        path.write_text(json.dumps(plan), encoding="utf-8")
        with self.assertRaises(RETIRE.Blocked):
            RETIRE.apply_plan(self.root, path, plan["digest"])
        self.assert_retained()

    def test_squash_and_rebased_commits_need_provider_proof(self):
        self.merge("squash")
        plan = RETIRE.make_plan(self.options)
        self.assertIn("digest", plan)
        self.assert_retained()

    def test_rebased_commits_have_provider_proof(self):
        git(self.root, "switch", "feature/completed")
        (self.root / "second.txt").write_text("second task commit\n", encoding="utf-8")
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "second task commit")
        git(self.root, "push", "origin", "feature/completed")
        self.task = git(self.root, "rev-parse", "HEAD")
        self.review["head"]["sha"] = self.task
        git(self.root, "switch", "main")
        self.merge("rebase")
        plan = RETIRE.make_plan(self.options)
        self.assertEqual("rebase-patches", plan["snapshot"]["representation"])
        self.assert_retained()

    def test_unknown_integration_proof_blocks(self):
        self.review["merge_commit_sha"] = None
        with self.assertRaises(RETIRE.Blocked):
            self.write_plan()
        self.assert_retained()

    def test_unrelated_target_patch_cannot_prove_merge(self):
        (self.root / "unrelated.txt").write_text("unrelated work\n", encoding="utf-8")
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "Unrelated target work")
        git(self.root, "push", "origin", "main")
        self.review["merge_commit_sha"] = git(self.root, "rev-parse", "HEAD")
        with self.assertRaises(RETIRE.Blocked):
            self.write_plan()
        self.assert_retained()

    def test_whitespace_changed_patch_is_not_integration_proof(self):
        # Git patch-id alone ignores this difference; Python indentation and
        # other whitespace-sensitive content require the exact patch payload.
        (self.root / "task.txt").write_text("    completed work\n", encoding="utf-8")
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "Different whitespace in target")
        git(self.root, "push", "origin", "main")
        self.review["merge_commit_sha"] = git(self.root, "rev-parse", "HEAD")
        with self.assertRaises(RETIRE.Blocked):
            self.write_plan()
        self.assert_retained()

    def test_protected_task_branch_blocks(self):
        self.merge()
        self.branch_protected = True
        with self.assertRaises(RETIRE.Blocked):
            self.write_plan()
        self.assert_retained()

    def test_unknown_branch_protection_blocks(self):
        self.merge()
        self.branch_protected = None
        with self.assertRaises(RETIRE.Blocked):
            self.write_plan()
        self.assert_retained()

    def test_provider_head_mismatch_blocks(self):
        self.merge()
        self.review["head"]["sha"] = self.initial
        with self.assertRaises(RETIRE.Blocked):
            self.write_plan()
        self.assert_retained()

    def test_review_from_fork_blocks(self):
        self.merge()
        self.review["head"]["repo"]["full_name"] = "someone/project"
        with self.assertRaises(RETIRE.Blocked):
            self.write_plan()
        self.assert_retained()

    def test_wrong_review_head_branch_blocks(self):
        self.merge()
        self.review["head"]["ref"] = "feature/someone-else"
        with self.assertRaises(RETIRE.Blocked):
            self.write_plan()
        self.assert_retained()

    def test_conflicting_push_url_blocks(self):
        self.merge()
        git(self.root, "remote", "set-url", "--push", "origin", "https://github.com/other/project.git")
        with self.assertRaises(RETIRE.Blocked):
            self.write_plan()
        self.assert_retained()

    def test_cli_error_json_works_with_ascii_stdout(self):
        environment = os.environ.copy()
        environment["PYTHONIOENCODING"] = "ascii"
        result = subprocess.run([sys.executable, str(SCRIPT), "apply", "--project-root", str(self.root),
                                 "--plan", str(self.base / "несуществующий.json"), "--confirm", "0", "--json"],
                                capture_output=True, env=environment)
        self.assertNotEqual(0, result.returncode)
        output = json.loads(result.stdout.decode("ascii"))
        self.assertEqual("blocked", output["status"])
        self.assertNotIn(b"UnicodeEncodeError", result.stderr)

    def test_local_ref_moved_after_plan_is_preserved(self):
        self.merge()
        path, plan = self.write_plan()
        git(self.root, "update-ref", "refs/heads/feature/completed", self.initial, self.task)
        with self.assertRaises(RETIRE.Blocked):
            RETIRE.apply_plan(self.root, path, plan["digest"])
        self.assertEqual(self.initial, git(self.root, "rev-parse", "refs/heads/feature/completed"))
        self.assertIn(self.task, git(self.root, "ls-remote", "origin", "refs/heads/feature/completed"))

    def test_remote_ref_moved_after_plan_is_preserved(self):
        self.merge()
        path, plan = self.write_plan()
        git(self.remote, "update-ref", "refs/heads/feature/completed", self.initial, self.task)
        with self.assertRaises(RETIRE.Blocked):
            RETIRE.apply_plan(self.root, path, plan["digest"])
        self.assertEqual(self.task, git(self.root, "rev-parse", "refs/heads/feature/completed"))
        self.assertIn(self.initial, git(self.root, "ls-remote", "origin", "refs/heads/feature/completed"))

    def test_primary_advanced_after_plan_blocks(self):
        self.merge()
        path, plan = self.write_plan()
        git(self.root, "commit", "--allow-empty", "-m", "Later primary")
        git(self.root, "push", "origin", "main")
        with self.assertRaises(RETIRE.Blocked):
            RETIRE.apply_plan(self.root, path, plan["digest"])
        self.assert_retained()

    def task_worktree(self):
        path = self.base / "worktrees" / "task"
        git(self.root, "worktree", "add", str(path), "feature/completed")
        self.options.update(remove_worktree=[str(path)], allowed_root=[str(path.parent)],
                            inactive_worktree=[str(path)])
        return path

    def test_clean_explicitly_inactive_worktree_is_removed(self):
        self.merge()
        worktree = self.task_worktree()
        path, plan = self.write_plan()
        RETIRE.apply_plan(self.root, path, plan["digest"])
        self.assertFalse(worktree.exists())
        self.assertEqual("", git(self.root, "ls-remote", "origin", "refs/heads/feature/completed"))

    def test_tracked_dirty_worktree_blocks(self):
        self.merge()
        worktree = self.task_worktree()
        (worktree / "task.txt").write_text("preserve local edits\n", encoding="utf-8")
        with self.assertRaises(RETIRE.Blocked):
            self.write_plan()
        self.assertTrue(worktree.exists())
        self.assert_retained()

    def test_untracked_worktree_blocks(self):
        self.merge()
        worktree = self.task_worktree()
        (worktree / "untracked.txt").write_text("preserve\n", encoding="utf-8")
        with self.assertRaises(RETIRE.Blocked):
            self.write_plan()
        self.assertTrue(worktree.exists())
        self.assert_retained()

    def test_ignored_worktree_blocks(self):
        self.merge()
        worktree = self.task_worktree()
        (worktree / "ignored.tmp").write_text("preserve ignored data\n", encoding="utf-8")
        with self.assertRaises(RETIRE.Blocked):
            self.write_plan()
        self.assertTrue(worktree.exists())
        self.assert_retained()

    def test_worktree_without_inactive_declaration_blocks(self):
        self.merge()
        worktree = self.task_worktree()
        self.options["inactive_worktree"] = []
        with self.assertRaises(RETIRE.Blocked):
            self.write_plan()
        self.assertTrue(worktree.exists())
        self.assert_retained()

    def test_worktree_outside_allowed_root_blocks(self):
        self.merge()
        worktree = self.task_worktree()
        self.options["allowed_root"] = [str(self.root)]
        with self.assertRaises(RETIRE.Blocked):
            self.write_plan()
        self.assertTrue(worktree.exists())
        self.assert_retained()

    def test_locked_worktree_blocks(self):
        self.merge()
        worktree = self.task_worktree()
        git(self.root, "worktree", "lock", str(worktree), "--reason", "another session")
        with self.assertRaises(RETIRE.Blocked):
            self.write_plan()
        self.assertTrue(worktree.exists())
        self.assert_retained()

    def test_current_worktree_cannot_be_removed(self):
        self.merge()
        worktree = self.task_worktree()
        self.options["project_root"] = str(worktree)
        with self.assertRaises(RETIRE.Blocked):
            self.write_plan()
        self.assertTrue(worktree.exists())
        self.assert_retained()

    def test_missing_primary_blocks(self):
        self.merge()
        self.options["primary"] = "absent"
        with self.assertRaises(RETIRE.Blocked):
            self.write_plan()
        self.assert_retained()

    def test_divergent_primary_blocks(self):
        self.merge()
        git(self.root, "commit", "--allow-empty", "-m", "Unpublished local primary")
        remote_commit = git(self.root, "commit-tree", "HEAD^{tree}", "-p", self.initial,
                            "-m", "Different remote primary")
        git(self.root, "push", "origin", remote_commit + ":refs/heads/remote-temp")
        git(self.remote, "update-ref", "refs/heads/main", remote_commit)
        with self.assertRaises(RETIRE.Blocked):
            self.write_plan()
        self.assert_retained()

    def test_remote_rejection_retains_local_ref(self):
        self.merge()
        path, plan = self.write_plan()
        hook = self.remote / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\necho deliberate-test-rejection >&2\nexit 1\n", encoding="utf-8")
        hook.chmod(0o755)
        try:
            result = RETIRE.apply_plan(self.root, path, plan["digest"])
        except RETIRE.Blocked:
            pass
        else:
            self.assertNotEqual("complete", result.get("status"))
            self.assertIn("fail", json.dumps(result).lower())
        self.assert_retained()

    def test_ignored_file_added_after_plan_blocks(self):
        self.merge()
        worktree = self.task_worktree()
        path, plan = self.write_plan()
        (worktree / "ignored.tmp").write_text("appeared after plan\n", encoding="utf-8")
        with self.assertRaises(RETIRE.Blocked):
            RETIRE.apply_plan(self.root, path, plan["digest"])
        self.assertTrue(worktree.exists())
        self.assert_retained()

    def test_remote_lease_rejects_race_during_push(self):
        self.merge()
        path, plan = self.write_plan()
        raced = []

        def execute(argv, cwd, input_text=None):
            if argv[:2] == ["git", "push"] and not raced:
                git(self.remote, "update-ref", "refs/heads/feature/completed", self.initial, self.task)
                raced.append(True)
            return self.execute(argv, cwd, input_text)

        with mock.patch.object(RETIRE, "execute", side_effect=execute):
            result = RETIRE.apply_plan(self.root, path, plan["digest"])
        self.assertTrue(raced)
        self.assertEqual("blocked", result["status"])
        self.assertEqual([], result["completed"])
        self.assertEqual(self.task, git(self.root, "rev-parse", "refs/heads/feature/completed"))
        self.assertIn(self.initial, git(self.root, "ls-remote", "origin", "refs/heads/feature/completed"))

    def test_local_cas_rejects_race_during_delete(self):
        self.merge()
        path, plan = self.write_plan()
        raced = []

        def execute(argv, cwd, input_text=None):
            if argv[:2] == ["git", "update-ref"] and "-d" in argv and not raced:
                git(self.root, "update-ref", "refs/heads/feature/completed", self.initial, self.task)
                raced.append(True)
            return self.execute(argv, cwd, input_text)

        with mock.patch.object(RETIRE, "execute", side_effect=execute):
            result = RETIRE.apply_plan(self.root, path, plan["digest"])
        self.assertTrue(raced)
        self.assertEqual("partial", result["status"])
        self.assertEqual(["delete-remote"], [action["kind"] for action in result["completed"]])
        self.assertEqual("delete-local", result["failed_or_uncertain"]["kind"])
        self.assertEqual(self.initial, result["final_state"]["local_source"])
        self.assertEqual("", result["final_state"]["remote_source"])
        self.assertEqual(self.initial, git(self.root, "rev-parse", "refs/heads/feature/completed"))
        self.assertEqual("", git(self.root, "ls-remote", "origin", "refs/heads/feature/completed"))

    def test_remote_failure_after_worktree_removal_reports_partial_truthfully(self):
        self.merge()
        worktree = self.task_worktree()
        path, plan = self.write_plan()
        hook = self.remote / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        hook.chmod(0o755)
        result = RETIRE.apply_plan(self.root, path, plan["digest"])
        self.assertEqual("partial", result["status"])
        self.assertEqual(["remove-worktree"], [action["kind"] for action in result["completed"]])
        self.assertEqual("delete-remote", result["failed_or_uncertain"]["kind"])
        self.assertEqual(self.task, result["final_state"]["local_source"])
        self.assertIn(self.task, result["final_state"]["remote_source"])
        self.assertFalse(worktree.exists())
        self.assert_retained()

    def test_duplicate_plan_keys_are_rejected(self):
        self.merge()
        path, plan = self.write_plan()
        text = path.read_text(encoding="utf-8")
        path.write_text('{"schema_version": 2, ' + text[1:], encoding="utf-8")
        with self.assertRaises((RETIRE.Blocked, ValueError)):
            RETIRE.apply_plan(self.root, path, plan["digest"])
        self.assert_retained()

    def gitlab(self):
        self.options.update(provider="gitlab", host="gitlab.example")
        record = {"state": "merged", "source_project_id": 7, "target_project_id": 7,
                  "sha": self.task, "merge_commit_sha": self.review["merge_commit_sha"],
                  "target_branch": "main", "source_branch": "feature/completed"}

        def execute(argv, cwd, input_text=None):
            if argv[0] == "glab":
                self.assertIn("gitlab.example", argv)
                if "/merge_requests/" in argv[-1]:
                    return json.dumps(record)
                if "/branches/" in argv[-1]:
                    return json.dumps({"protected": False, "name": "feature/completed", "commit": {"id": self.task}})
                return json.dumps({"id": 7, "path_with_namespace": "example/project"})
            return self.execute(argv, cwd, input_text)

        current_identity = RETIRE.identity
        identity = mock.patch.object(RETIRE, "identity", side_effect=lambda url:
                                     ("gitlab.example", "example/project")
                                     if url.replace("\\", "/") == self.remote.as_posix()
                                     else current_identity(url))
        provider = mock.patch.object(RETIRE, "execute", side_effect=execute)
        identity.start()
        provider.start()
        self.addCleanup(identity.stop)
        self.addCleanup(provider.stop)
        return record

    def test_gitlab_verified_review_can_retire(self):
        self.merge()
        self.gitlab()
        path, plan = self.write_plan()
        result = RETIRE.apply_plan(self.root, path, plan["digest"])
        self.assertEqual("applied", result["status"])
        self.assertEqual("", git(self.root, "ls-remote", "origin", "refs/heads/feature/completed"))

    def test_gitlab_wrong_source_project_blocks(self):
        self.merge()
        record = self.gitlab()
        record["source_project_id"] = 8
        with self.assertRaises(RETIRE.Blocked):
            self.write_plan()
        self.assert_retained()

    def test_gitlab_unknown_source_sha_blocks(self):
        self.merge()
        record = self.gitlab()
        record["sha"] = None
        with self.assertRaises(RETIRE.Blocked):
            self.write_plan()
        self.assert_retained()

    def test_gitlab_wrong_host_blocks(self):
        self.merge()
        self.gitlab()
        self.options["host"] = "other.example"
        with self.assertRaises(RETIRE.Blocked):
            self.write_plan()
        self.assert_retained()

    def test_remote_already_absent_can_retire_local_branch(self):
        self.merge()
        git(self.remote, "update-ref", "-d", "refs/heads/feature/completed", self.task)
        path, plan = self.write_plan()
        result = RETIRE.apply_plan(self.root, path, plan["digest"])
        self.assertEqual("applied", result["status"])
        self.assertEqual(["delete-local"], [action["kind"] for action in result["completed"]])
        self.assertNotIn("feature/completed", git(self.root, "branch", "--list"))

    def race_before_removal(self, action):
        observations = []

        def execute(argv, cwd, input_text=None):
            if argv == ["git", "remote", "get-url", "--all", "origin"]:
                observations.append(True)
                if len(observations) == 3:
                    action()
            return self.execute(argv, cwd, input_text)

        return mock.patch.object(RETIRE, "execute", side_effect=execute)

    def test_tip_moved_immediately_before_worktree_removal_is_preserved(self):
        self.merge()
        worktree = self.task_worktree()
        path, plan = self.write_plan()
        with self.race_before_removal(lambda: git(self.remote, "update-ref", "refs/heads/feature/completed", self.initial, self.task)):
            result = RETIRE.apply_plan(self.root, path, plan["digest"])
        self.assertEqual("blocked", result["status"])
        self.assertEqual([], result["completed"])
        self.assertTrue(worktree.exists())
        self.assertEqual(self.task, git(self.root, "rev-parse", "refs/heads/feature/completed"))
        self.assertIn(self.initial, git(self.root, "ls-remote", "origin", "refs/heads/feature/completed"))

    def test_replaced_worktree_path_is_preserved_before_removal(self):
        self.merge()
        worktree = self.task_worktree()
        path, plan = self.write_plan()
        moved = worktree.with_name("moved")

        def replace():
            git(self.root, "worktree", "move", str(worktree), str(moved))
            worktree.mkdir()
            (worktree / "preserve.txt").write_text("replacement directory\n", encoding="utf-8")

        with self.race_before_removal(replace):
            result = RETIRE.apply_plan(self.root, path, plan["digest"])
        self.assertEqual("blocked", result["status"])
        self.assertEqual([], result["completed"])
        self.assertTrue((worktree / "preserve.txt").exists())
        self.assertTrue(moved.exists())
        self.assert_retained()

    def test_duplicated_context_at_wrong_function_is_not_merge_proof(self):
        body = "\n".join("    value += " + str(number) for number in range(1, 13))
        content = "def first():\n" + body + "\n\ndef second():\n" + body + "\n"
        file = self.root / "duplicated.py"
        file.write_text(content, encoding="utf-8")
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "Two similar functions")
        git(self.root, "switch", "-c", "feature/duplicated-context")
        file.write_text(content.replace("value += 6\n", "value += 60\n", 1), encoding="utf-8")
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "Change first function")
        source = git(self.root, "rev-parse", "HEAD")
        git(self.root, "switch", "main")
        before, separator, after = content.partition("def second():")
        file.write_text(before + separator + after.replace("value += 6\n", "value += 60\n", 1), encoding="utf-8")
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "Change second function only")
        target = git(self.root, "rev-parse", "HEAD")
        self.assertNotEqual(git(self.root, "rev-parse", source + "^{tree}"),
                            git(self.root, "rev-parse", target + "^{tree}"))
        with self.assertRaises(RETIRE.Blocked):
            RETIRE.proof(self.root, source, target, target)

    def test_primary_drift_after_final_observe_retains_worktree_and_refs(self):
        self.merge()
        worktree = self.task_worktree()
        path, plan = self.write_plan()
        original_observe = RETIRE.observe
        observations = []

        def observe(options):
            result = original_observe(options)
            observations.append(True)
            if len(observations) == 2:
                git(self.root, "update-ref", "refs/heads/main", self.initial)
                git(self.root, "restore", "--source=HEAD", "--staged", "--worktree", ".")
                git(self.remote, "update-ref", "refs/heads/main", self.initial)
            return result

        with mock.patch.object(RETIRE, "observe", side_effect=observe):
            try:
                result = RETIRE.apply_plan(self.root, path, plan["digest"])
            except RETIRE.Blocked:
                result = {"status": "blocked", "completed": []}
        self.assertGreaterEqual(len(observations), 2)
        self.assertEqual("blocked", result["status"])
        self.assertEqual([], result["completed"])
        self.assertTrue(worktree.exists())
        self.assert_retained()

    def test_missing_exact_task_ref_preserves_single_child_during_remote_only_retirement(self):
        self.merge()
        parent = "refs/heads/feature/completed"
        child = parent + "/followup"
        git(self.root, "update-ref", "-d", parent, self.task)
        git(self.root, "update-ref", child, self.task)
        self.assertIsNone(RETIRE.oid(self.root, parent))
        path, plan = self.write_plan()
        self.assertIsNone(plan["snapshot"]["local_source"])
        result = RETIRE.apply_plan(self.root, path, plan["digest"])
        self.assertEqual("applied", result["status"])
        self.assertEqual(["delete-remote"], [action["kind"] for action in result["completed"]])
        self.assertEqual(self.task, git(self.root, "rev-parse", child))
        self.assertEqual("", git(self.root, "ls-remote", "origin", parent))

    def test_missing_exact_primary_ref_cannot_be_substituted_by_tracking_child(self):
        self.merge()
        git(self.root, "switch", "-c", "retained-checkout")
        git(self.root, "update-ref", "-d", "refs/heads/main")
        git(self.root, "branch", "main/backup", "HEAD")
        git(self.root, "branch", "--set-upstream-to=origin/main", "main/backup")
        with self.assertRaises(RETIRE.Blocked):
            self.write_plan()
        self.assertEqual(git(self.root, "rev-parse", "HEAD"),
                         git(self.root, "rev-parse", "refs/heads/main/backup"))
        self.assert_retained()

    def test_restore_primary_preserves_ignored_file_tracked_by_primary(self):
        self.merge()
        git(self.root, "switch", "-c", "retained-control", self.initial)
        (self.root / ".gitignore").write_text("ignored.tmp\ntask.txt\n", encoding="utf-8")
        git(self.root, "add", ".gitignore")
        git(self.root, "commit", "-m", "Control checkout ignores task file")
        valuable = "valuable ignored local content\n"
        file = self.root / "task.txt"
        file.write_text(valuable, encoding="utf-8")
        self.assertEqual("", git(self.root, "status", "--porcelain"))
        self.assertIn("task.txt", git(self.root, "ls-tree", "--name-only", "main"))
        self.options["restore_primary"] = True
        try:
            path, plan = self.write_plan()
            result = RETIRE.apply_plan(self.root, path, plan["digest"])
        except RETIRE.Blocked:
            result = {"status": "blocked", "completed": []}
        self.assertEqual(valuable, file.read_text(encoding="utf-8"))
        self.assertEqual("blocked", result["status"])
        self.assertEqual([], result["completed"])
        self.assertEqual("retained-control", git(self.root, "branch", "--show-current"))
        self.assert_retained()


if __name__ == "__main__":
    unittest.main()
