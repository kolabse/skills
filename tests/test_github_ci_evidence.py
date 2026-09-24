from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "skills/verify-before-push/scripts/verify_before_push.py"
SPEC = importlib.util.spec_from_file_location("github_ci_verifier", SCRIPT)
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


class GitHubCIEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.remote = self.root / "remote.git"
        self.project = self.root / "project"
        self.git(self.root, "init", "--bare", str(self.remote))
        self.git(self.root, "clone", str(self.remote), str(self.project))
        self.git(self.project, "config", "user.name", "Fixture")
        self.git(self.project, "config", "user.email", "fixture@example.test")
        self.git(self.project, "checkout", "-b", "main")
        self.config = {
            "version": 1,
            "repositories": [{"name": "project", "path": "."}],
            "checks": [{"name": "unit", "command": [sys.executable, "-c", "print('local check')"]},
                       {"name": "disabled", "command": ["unused"], "enabled": False,
                        "required": False, "skip_reason": "not part of this project"}],
            "github_ci": {"repository": "example/project", "remote": "origin", "branch": "main",
                          "event": "push", "checks": {"unit": {"workflow": ".github/workflows/test.yml", "jobs": ["Unit tests"]}}},
        }
        self.config_path = self.project / verifier.CONFIG_RELATIVE
        self.config_path.parent.mkdir(parents=True)
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")
        (self.project / ".gitignore").write_text(".agents/verify-before-push/evidence.json\n", encoding="utf-8")
        (self.project / "tracked.txt").write_text("initial\n", encoding="utf-8")
        self.git(self.project, "add", ".")
        self.git(self.project, "commit", "-m", "fixture")
        self.git(self.project, "push", "-u", "origin", "main")
        self.head = self.git(self.project, "rev-parse", "HEAD").strip()
        self.run = {"id": 100, "run_number": 10, "run_attempt": 1,
                    "head_sha": self.head, "head_branch": "main", "event": "push",
                    "path": ".github/workflows/test.yml", "repository": {"full_name": "example/project"},
                    "head_repository": {"full_name": "example/project"}, "status": "completed", "conclusion": "success"}
        self.job = {"id": 200, "run_id": 100, "run_attempt": 1, "name": "Unit tests",
                    "head_sha": self.head, "status": "completed", "conclusion": "success"}
        self.runs = [self.run]
        self.jobs = [self.job]
        self.endpoints = []
        self.api_hook = None
        actual_git = verifier.git

        def fixture_git(repo, *args, **kwargs):
            # Exercise real fetch/advertisement/state against an isolated bare
            # repository; only its transport identity is represented as GitHub.
            if args[:2] == ("remote", "get-url"):
                return b"https://github.com/example/project.git\n"
            return actual_git(repo, *args, **kwargs)

        self.addCleanup(patch.stopall)
        patch.object(verifier, "git", side_effect=fixture_git).start()
        patch.object(verifier, "github_api", side_effect=self.api).start()

    @staticmethod
    def git(root, *args):
        result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stderr)
        return result.stdout

    def api(self, root, endpoint):
        self.endpoints.append(endpoint)
        if self.api_hook:
            self.api_hook(endpoint)
        if "/workflows/" in endpoint:
            return {"total_count": len(self.runs), "workflow_runs": copy.deepcopy(self.runs)}
        if "/jobs?" in endpoint:
            return {"total_count": len(self.jobs), "jobs": copy.deepcopy(self.jobs)}
        return copy.deepcopy(self.run)

    @property
    def receipt(self):
        return self.project / verifier.DEFAULT_EVIDENCE

    def collect(self):
        return verifier.collect_github_ci(self.config, self.project, verifier.capture_states(self.config, self.project))

    def test_ci_receipt_binds_observations_and_revalidates_without_restamping(self):
        with patch.object(verifier, "execute_checks", side_effect=AssertionError("must not run local checks")):
            verifier.run_github_ci_verification(self.project)
            original, modified = self.receipt.read_bytes(), self.receipt.stat().st_mtime_ns
            evidence = json.loads(original)
            self.assertEqual(evidence["version"], 3)
            self.assertEqual(evidence["source"], "github-ci")
            self.assertEqual(evidence["checks"][0], {"name": "unit", "status": "passed", "source": "github-ci"})
            self.assertEqual(evidence["github_ci"]["workflows"][0]["jobs"][0]["id"], 200)
            self.assertTrue(verifier.verify_evidence(self.project))
            self.assertTrue(verifier.verify_evidence(self.project, self.project))
            verifier.run_github_ci_verification(self.project)
            self.assertEqual(self.receipt.read_bytes(), original)
            self.assertEqual(self.receipt.stat().st_mtime_ns, modified)
            self.assertTrue(any("/attempts/1/jobs?" in endpoint for endpoint in self.endpoints))

    def test_local_remains_default_even_with_ci_policy(self):
        with patch.object(verifier, "github_api", side_effect=AssertionError("local run must not call CI")):
            self.assertEqual(verifier.main(["run", "--project-root", str(self.project)]), 0)
            self.assertEqual(json.loads(self.receipt.read_text())["version"], 1)

    def test_cli_explicit_ci_source(self):
        self.assertEqual(verifier.main(["run", "--source", "github-ci", "--project-root", str(self.project)]), 0)
        self.assertEqual(json.loads(self.receipt.read_text())["version"], 3)

    def test_wrong_run_identities_fail_closed(self):
        for key, value in [("head_sha", "b" * 40), ("head_branch", "elsewhere"), ("event", "pull_request"),
                           ("path", ".github/workflows/untrusted.yml"),
                           ("repository", {"full_name": "other/project"}),
                           ("repository", {"full_name": 42}),
                           ("head_repository", {"full_name": "other/project"}), ("run_attempt", True)]:
            with self.subTest(key=key):
                original = self.run[key]
                self.run[key] = value
                with self.assertRaises(verifier.VerificationError):
                    self.collect()
                self.run[key] = original

    def test_workflow_path_may_include_ref(self):
        self.run["path"] += "@refs/heads/main"
        self.collect()

    def test_latest_run_is_selected_before_success(self):
        older = copy.deepcopy(self.run)
        older.update(id=99, run_number=9)
        self.runs.insert(0, older)
        for status, conclusion in [("queued", None), ("in_progress", None), ("completed", "failure"),
                                   ("completed", "skipped"), ("completed", "cancelled")]:
            with self.subTest(status=status, conclusion=conclusion):
                self.run.update(status=status, conclusion=conclusion)
                with self.assertRaises(verifier.VerificationError):
                    self.collect()

    def test_later_failed_attempt_invalidates_successful_receipt(self):
        verifier.run_github_ci_verification(self.project)
        self.run.update(run_attempt=2, conclusion="failure")
        with self.assertRaises(verifier.VerificationError):
            verifier.verify_evidence(self.project)
        with self.assertRaises(verifier.VerificationError):
            verifier.run_github_ci_verification(self.project)
        self.assertFalse(self.receipt.exists())

    def test_later_successful_attempt_cannot_validate_original_receipt(self):
        verifier.run_github_ci_verification(self.project)
        self.run["run_attempt"] = 2
        self.job.update(run_attempt=2, id=201)
        with self.assertRaisesRegex(verifier.VerificationError, "observations changed"):
            verifier.verify_evidence(self.project)

    def test_expected_jobs_must_be_unique_complete_and_successful(self):
        for key, value in [("id", True), ("head_sha", "b" * 40), ("run_id", 99), ("run_attempt", 2), ("run_attempt", True),
                           ("status", "queued"), ("conclusion", "skipped"), ("conclusion", "failure")]:
            with self.subTest(key=key, value=value):
                original = self.job[key]
                self.job[key] = value
                with self.assertRaises(verifier.VerificationError):
                    self.collect()
                self.job[key] = original
        self.jobs = []
        with self.assertRaises(verifier.VerificationError):
            self.collect()
        self.jobs = [self.job, {**self.job, "id": 201}]
        with self.assertRaises(verifier.VerificationError):
            self.collect()

    def test_truncated_and_malformed_pages_fail(self):
        for value in [{"total_count": 101, "jobs": []}, {"total_count": 2, "jobs": [self.job]},
                      {"total_count": True, "jobs": [self.job]}, {"total_count": 1, "jobs": [None]}]:
            with self.subTest(value=value), self.assertRaises(verifier.VerificationError):
                verifier.ci_page(value, "jobs")

    def test_api_failure_never_preserves_previous_receipt_on_rerun(self):
        verifier.run_github_ci_verification(self.project)
        with patch.object(verifier, "github_api", side_effect=verifier.VerificationError("API unavailable")):
            with self.assertRaises(verifier.VerificationError):
                verifier.run_github_ci_verification(self.project)
        self.assertFalse(self.receipt.exists())

    def test_receipt_tampering_and_extra_fields_fail(self):
        verifier.run_github_ci_verification(self.project)
        original = json.loads(self.receipt.read_text())
        for edit in [lambda e: e.update(extra=True), lambda e: e["checks"][0].update(exit_code=0),
                     lambda e: e["github_ci"]["workflows"][0].update(run_id=True),
                     lambda e: e.update(checked_at="yesterday")]:
            evidence = copy.deepcopy(original)
            edit(evidence)
            evidence["receipt_sha256"] = verifier.digest({k: v for k, v in evidence.items() if k != "receipt_sha256"})
            self.receipt.write_text(json.dumps(evidence))
            with self.assertRaises(verifier.VerificationError):
                verifier.verify_evidence(self.project)

    def test_ci_requires_clean_exact_advertised_head(self):
        (self.project / "tracked.txt").write_text("different\n")
        with self.assertRaises(verifier.VerificationError):
            verifier.run_github_ci_verification(self.project)
        self.git(self.project, "add", "tracked.txt")
        self.git(self.project, "commit", "-m", "not published")
        with self.assertRaisesRegex(verifier.VerificationError, "advertised"):
            self.collect()

    def test_config_and_worktree_races_fail_without_receipt(self):
        def change_worktree(endpoint):
            if "/jobs?" in endpoint:
                (self.project / "tracked.txt").write_text("race\n")
        self.api_hook = change_worktree
        with self.assertRaises(verifier.VerificationError):
            verifier.run_github_ci_verification(self.project)
        self.assertFalse(self.receipt.exists())
        (self.project / "tracked.txt").write_text("initial\n")
        # Even an ignored configuration race is caught by reloading its digest.
        config = copy.deepcopy(self.config)
        config["repositories"][0]["require_clean"] = False
        self.config_path.write_text(json.dumps(config))
        self.git(self.project, "add", ".")
        self.git(self.project, "commit", "-m", "allow dirty local checks")
        self.git(self.project, "push")
        self.head = self.git(self.project, "rev-parse", "HEAD").strip()
        self.run["head_sha"] = self.job["head_sha"] = self.head
        self.git(self.project, "update-index", "--assume-unchanged", str(verifier.CONFIG_RELATIVE))
        def change_config(endpoint):
            if "/jobs?" in endpoint:
                updated = copy.deepcopy(config)
                updated["checks"][0]["timeout_seconds"] = 12
                self.config_path.write_text(json.dumps(updated))
        self.api_hook = change_config
        with self.assertRaisesRegex(verifier.VerificationError, "Configuration changed"):
            verifier.run_github_ci_verification(self.project)
        self.assertFalse(self.receipt.exists())

    def test_policy_must_be_complete_strict_and_unambiguous(self):
        policy = self.config["github_ci"]
        changes = [lambda p: p.pop("remote"), lambda p: p.update(unknown=True),
                   lambda p: p.update(event="pull_request"), lambda p: p.update(checks={}),
                   lambda p: p["checks"]["unit"].update(jobs=["Unit tests", "Unit tests"]),
                   lambda p: p["checks"]["unit"].update(workflow="test.yml")]
        for edit in changes:
            self.config["github_ci"] = copy.deepcopy(policy)
            edit(self.config["github_ci"])
            with self.assertRaises(verifier.VerificationError):
                verifier.validate_config_document(self.config, self.project)
        self.config["github_ci"] = policy
        with self.assertRaises(verifier.VerificationError):
            verifier.run_github_ci_verification(self.project, self.root / "map.json")

    def test_remote_identity_and_tracking_policy_must_match(self):
        with patch.object(verifier, "tracking_identity", return_value={"branch": "refs/heads/other", "remote": "origin", "merge": "refs/heads/main"}):
            with self.assertRaisesRegex(verifier.VerificationError, "tracking remote"):
                self.collect()
        actual_git = verifier.git
        def wrong_remote(repo, *args, **kwargs):
            if args[:2] == ("remote", "get-url"):
                return b"https://github.com/other/project.git\n"
            return actual_git(repo, *args, **kwargs)
        with patch.object(verifier, "git", side_effect=wrong_remote):
            with self.assertRaisesRegex(verifier.VerificationError, "remote repository"):
                self.collect()

    def test_new_attempt_during_collection_fails(self):
        def start_rerun(endpoint):
            if endpoint.endswith("/runs/100"):
                self.run["run_attempt"] = 2
        self.api_hook = start_rerun
        with self.assertRaisesRegex(verifier.VerificationError, "attempt changed"):
            verifier.run_github_ci_verification(self.project)
        self.assertFalse(self.receipt.exists())

    def test_rerun_started_while_reading_old_attempt_jobs_blocks_verify_and_gate(self):
        verifier.run_github_ci_verification(self.project)
        original = self.receipt.read_bytes()
        for repository in (None, self.project):
            with self.subTest(repository=repository):
                self.run.update(run_attempt=1, status="completed", conclusion="success")
                def start_rerun(endpoint):
                    if "/jobs?" in endpoint:
                        self.run.update(run_attempt=2, status="queued", conclusion=None)
                self.api_hook = start_rerun
                with self.assertRaisesRegex(verifier.VerificationError, "not completed successfully"):
                    verifier.verify_evidence(self.project, repository)
                self.assertEqual(self.receipt.read_bytes(), original)

    def test_new_successful_run_started_during_jobs_invalidates_snapshot(self):
        def new_run(endpoint):
            if "/jobs?" in endpoint:
                self.run.update(id=101, run_number=11)
        self.api_hook = new_run
        with self.assertRaisesRegex(verifier.VerificationError, "changed after collecting jobs"):
            self.collect()

    def test_final_pass_rechecks_earlier_workflows_after_later_job_queries(self):
        self.config["checks"].append({"name": "integration", "command": ["unused"]})
        self.config["github_ci"]["checks"]["integration"] = {"workflow": ".github/workflows/z.yml", "jobs": ["Integration"]}
        later = {**self.run, "id": 300, "path": ".github/workflows/z.yml"}
        job = {**self.job, "id": 400, "run_id": 300, "name": "Integration"}
        def two_workflows(root, endpoint):
            if "workflows/" in endpoint and "z.yml" in endpoint:
                return {"total_count": 1, "workflow_runs": [copy.deepcopy(later)]}
            if "/runs/300/attempts/" in endpoint:
                self.run.update(run_attempt=2, status="queued", conclusion=None)
                return {"total_count": 1, "jobs": [job]}
            if endpoint.endswith("/runs/300"):
                return copy.deepcopy(later)
            return self.api(root, endpoint)
        with patch.object(verifier, "github_api", side_effect=two_workflows):
            with self.assertRaisesRegex(verifier.VerificationError, "not completed successfully"):
                self.collect()

    def test_remote_branch_move_during_job_queries_invalidates_snapshot(self):
        # Construct another commit without changing this worktree or its HEAD.
        successor = self.git(self.project, "commit-tree", "HEAD^{tree}", "-p", "HEAD", "-m", "remote move").strip()
        def move_remote(endpoint):
            if "/jobs?" in endpoint:
                self.git(self.project, "push", "origin", successor + ":refs/heads/main")
        self.api_hook = move_remote
        with self.assertRaisesRegex(verifier.VerificationError, "advertised"):
            self.collect()

    def test_missing_policy_multi_repo_and_duplicate_configuration_are_rejected(self):
        del self.config["github_ci"]
        with self.assertRaises(verifier.VerificationError):
            verifier.validate_github_ci_policy(self.config)
        self.config = json.loads(self.config_path.read_text())
        self.config["repositories"].append({"name": "second", "path": "../other"})
        with self.assertRaisesRegex(verifier.VerificationError, "exactly one"):
            verifier.validate_github_ci_policy(self.config)
        self.config_path.write_text('{"version":1,"version":1}')
        with self.assertRaisesRegex(verifier.VerificationError, "duplicate JSON"):
            verifier.load_config(self.project)

    def test_nonmember_gate_does_not_call_ci(self):
        other = self.root / "other"
        other.mkdir()
        self.git(other, "init")
        with patch.object(verifier, "github_api", side_effect=AssertionError("outside gate called CI")):
            self.assertFalse(verifier.verify_evidence(self.project, other))


class GitHubAPITransportTests(unittest.TestCase):
    def test_pins_official_host_and_rejects_errors_and_malformed_data(self):
        for code, output in [(1, b"{}"), (0, b"no JSON"), (0, b"[]"), (0, b'{"id":1,"id":2}')]:
            with self.subTest(code=code, output=output):
                with patch.object(verifier, "run_process", return_value=subprocess.CompletedProcess([], code, output, b"")) as process:
                    with self.assertRaises(verifier.VerificationError):
                        verifier.github_api(Path.cwd(), "repos/example/project/actions/runs")
                    self.assertIn("github.com", process.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
