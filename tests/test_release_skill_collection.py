from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIRECTORY = ROOT / "skills" / "release-skill-collection" / "scripts"
sys.dont_write_bytecode = True
sys.path.insert(0, str(SCRIPT_DIRECTORY))

import release_collection  # noqa: E402


def git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


class ReleaseFixture:
    def __init__(self, parent: Path, version: str = "9.9.9") -> None:
        self.root = parent / "project"
        self.remote = parent / "remote.git"
        self.version = version
        self.root.mkdir()
        subprocess.run(["git", "init", "--bare", "-q", str(self.remote)], check=True)
        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "config", "user.name", "Release Tests")
        git(self.root, "config", "user.email", "release-tests@example.invalid")
        holdout = {"schema_version": 1, "name": "release-holdout-v1", "skills": {}}
        (self.root / "evals").mkdir()
        (self.root / "evals/release-holdout-v1.json").write_text(
            json.dumps(holdout), encoding="utf-8"
        )
        skill = self.root / "skills/demo"
        skill.mkdir(parents=True)
        (skill / "collection-metadata.json").write_text(
            json.dumps({"version": version}), encoding="utf-8"
        )
        catalog = {
            "collection_version": version,
            "release_holdout": {
                "name": "release-holdout-v1",
                "path": "evals/release-holdout-v1.json",
                "sha256": release_collection.canonical_digest(holdout),
            },
            "skills": [{"name": "demo", "path": "skills/demo"}],
        }
        (self.root / "skill-catalog.json").write_text(
            json.dumps(catalog), encoding="utf-8"
        )
        plugin = self.root / ".codex-plugin"
        plugin.mkdir()
        (plugin / "plugin.json").write_text(
            json.dumps({"version": version}), encoding="utf-8"
        )
        claude_plugin = self.root / ".claude-plugin"
        claude_plugin.mkdir()
        (claude_plugin / "plugin.json").write_text(
            json.dumps({"version": version}), encoding="utf-8"
        )
        (claude_plugin / "marketplace.json").write_text(
            json.dumps(
                {"name": "fixture", "owner": {"name": "fixture"}, "plugins": []}
            ),
            encoding="utf-8",
        )
        codex_marketplace = self.root / ".agents/plugins"
        codex_marketplace.mkdir(parents=True)
        (codex_marketplace / "marketplace.json").write_text(
            json.dumps({"name": "fixture", "plugins": []}), encoding="utf-8"
        )
        (self.root / "CHANGELOG.md").write_text(
            f"# Changelog\n\n## [{version}] - 2030-01-01\n", encoding="utf-8"
        )
        (self.root / "CONTRIBUTING.md").write_text("# Contributing\n", encoding="utf-8")
        (self.root / "scripts").mkdir()
        for name in (
            "validate_skills.py",
            "smoke_marketplaces.py",
            "security_checks.py",
            "build_release.py",
        ):
            (self.root / "scripts" / name).write_text("# fixture\n", encoding="utf-8")
        workflow = self.root / ".github/workflows"
        workflow.mkdir(parents=True)
        (workflow / "release.yml").write_text("name: fixture\n", encoding="utf-8")
        git(self.root, "add", ".")
        git(self.root, "commit", "-qm", "fixture")
        git(self.root, "remote", "add", "origin", str(self.remote))
        git(self.root, "push", "-qu", "origin", "main")

    @property
    def tag(self) -> str:
        return f"v{self.version}"


def passing_result(name: str) -> dict[str, object]:
    return {
        "name": name,
        "returncode": 0,
        "timed_out": False,
        "output_sha256": "a" * 64,
        "output_tail": "ok",
        "passed": True,
    }


def signed_gate(commit: str, **fields: object) -> dict[str, object]:
    gate: dict[str, object] = {"passed": True, "commit": commit, **fields}
    gate["evidence_sha256"] = release_collection.canonical_digest(gate)
    return gate


def release_audit(tag: str, commit: str) -> dict[str, object]:
    value: dict[str, object] = {
        "schema_version": 2,
        "mode": "audit-release",
        "passed": True,
        "repository": "kolabse/skills",
        "tag": tag,
        "commit": commit,
        "release_url": f"https://github.com/kolabse/skills/releases/tag/{tag}",
        "assets": [
            {"name": name, "sha256": "a" * 64}
            for name in ("archive.zip", "archive.tar.gz", "release-manifest.json", "SHA256SUMS")
        ],
        "attestation_verified": True,
        "mutates_repository": False,
    }
    value["report_sha256"] = release_collection.canonical_digest(value)
    return value


class ReleaseSkillCollectionTests(unittest.TestCase):
    def setUp(self) -> None:
        identity = patch.object(release_collection, "remote_repository", return_value="kolabse/skills")
        identity.start()
        self.addCleanup(identity.stop)

    def test_public_json_schemas_are_well_formed(self) -> None:
        schemas = ROOT / "skills/release-skill-collection/schemas"
        documents = [json.loads(path.read_text(encoding="utf-8")) for path in schemas.glob("*.json")]

        self.assertEqual(9, len(documents))
        self.assertTrue(all(document.get("$schema") for document in documents))

    def test_status_is_read_only_and_reports_aligned_fixture_versions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = ReleaseFixture(Path(directory))

            result = release_collection.inspect(fixture.root)

            self.assertEqual(2, result["schema_version"])
            self.assertEqual("status", result["mode"])
            self.assertFalse(result["mutates_repository"])
            self.assertFalse(result["blockers"])
            self.assertEqual(fixture.version, result["versions"]["catalog"])
            self.assertRegex(result["report_sha256"], r"^[0-9a-f]{64}$")

    def test_plan_rejects_invalid_or_existing_tag(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = ReleaseFixture(Path(directory))
            invalid = release_collection.inspect(fixture.root, "release-latest")
            git(fixture.root, "tag", "-a", fixture.tag, "-m", "fixture release")
            existing = release_collection.inspect(fixture.root, fixture.tag)

            self.assertIn("invalid release tag: release-latest", invalid["blockers"])
            self.assertTrue(any("already exists" in item for item in existing["blockers"]))

    def test_catalog_path_escape_and_detached_head_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = ReleaseFixture(Path(directory))
            catalog_path = fixture.root / "skill-catalog.json"
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            catalog["skills"][0]["path"] = "../outside"
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            escaped = release_collection.inspect(fixture.root)
            git(fixture.root, "checkout", "-q", "--detach", "HEAD")
            detached = release_collection.inspect(fixture.root)

            self.assertTrue(any("escapes the repository" in item for item in escaped["blockers"]))
            self.assertIn("repository is on a detached HEAD", detached["blockers"])

    def test_check_rejects_dirty_or_nonempty_repository_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = ReleaseFixture(Path(directory))
            (fixture.root / "dirty.txt").write_text("dirty", encoding="utf-8")
            inside = fixture.root / "dist"
            inside.mkdir()

            result = release_collection.check(fixture.root, fixture.tag, inside)

            self.assertFalse(result["passed"])
            self.assertFalse(result["checks"])
            self.assertTrue(any("clean worktree" in item for item in result["blockers"]))
            self.assertIn("explicit output root must be outside the repository", result["blockers"])

    def test_check_runs_all_gates_and_returns_sha_bound_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            fixture = ReleaseFixture(parent)
            output = parent / "artifacts"

            def fake_run(_root: Path, name: str, _command: list[str], _timeout: int) -> dict[str, object]:
                return passing_result(name)

            with patch.object(release_collection, "run_command", side_effect=fake_run):
                result = release_collection.check(fixture.root, fixture.tag, output)

            self.assertTrue(result["passed"])
            self.assertEqual(6, len(result["checks"]))
            self.assertEqual(git(fixture.root, "rev-parse", "HEAD"), result["evidence"]["commit"])
            self.assertRegex(result["report_sha256"], r"^[0-9a-f]{64}$")

    def test_check_fails_if_a_gate_mutates_the_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            fixture = ReleaseFixture(parent)

            def mutating_run(root: Path, name: str, _command: list[str], _timeout: int) -> dict[str, object]:
                if name == "structural-validation":
                    (root / "unexpected.txt").write_text("mutation", encoding="utf-8")
                return passing_result(name)

            with patch.object(release_collection, "run_command", side_effect=mutating_run):
                result = release_collection.check(fixture.root, fixture.tag, parent / "output")

            self.assertFalse(result["passed"])
            self.assertIn("local release checks mutated the repository worktree", result["blockers"])

    def test_run_command_disables_python_bytecode_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module = root / "sample.py"
            module.write_text("VALUE = 1\n", encoding="utf-8")

            result = release_collection.run_command(
                root,
                "import",
                [sys.executable, "-c", "import sample"],
                10,
            )

            self.assertTrue(result["passed"])
            self.assertFalse((root / "__pycache__").exists())

    def test_run_command_times_out_and_redacts_output(self) -> None:
        timed_out = release_collection.run_command(
            ROOT,
            "timeout",
            [sys.executable, "-c", "import time; time.sleep(2)"],
            1,
        )
        redacted = release_collection.run_command(
            ROOT,
            "redaction",
            [sys.executable, "-c", "print('token=supersecretvalue')"],
            10,
        )

        self.assertTrue(timed_out["timed_out"])
        self.assertFalse(timed_out["passed"])
        self.assertNotIn("supersecretvalue", redacted["output_tail"])
        self.assertIn("[REDACTED]", redacted["output_tail"])

    def test_verify_evidence_accepts_current_complete_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            fixture = ReleaseFixture(parent)
            commit = git(fixture.root, "rev-parse", "HEAD")
            gates = {name: signed_gate(commit) for name in release_collection.REQUIRED_GATES}
            gates["locked_holdout"] = signed_gate(commit, assertion_digest="c" * 64)
            gates["supported_platform_ci"] = signed_gate(
                commit, platforms=["linux", "macos", "windows"]
            )
            gates["consumer_smoke"] = signed_gate(
                commit, agents=["claude-code", "codex"]
            )
            evidence = {
                "schema_version": 1,
                "tag": fixture.tag,
                "commit": commit,
                "gates": gates,
            }
            evidence["evidence_sha256"] = release_collection.canonical_digest(evidence)
            evidence_path = parent / "evidence.json"
            evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

            result = release_collection.verify_evidence(fixture.root, fixture.tag, evidence_path)

            self.assertTrue(result["valid"])
            self.assertEqual(commit, result["commit"])

    def test_verify_evidence_rejects_tampering_stale_sha_and_missing_platform(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            fixture = ReleaseFixture(parent)
            commit = git(fixture.root, "rev-parse", "HEAD")
            gates = {name: signed_gate(commit) for name in release_collection.REQUIRED_GATES}
            gates["locked_holdout"] = signed_gate(commit, assertion_digest="c" * 64)
            gates["supported_platform_ci"] = signed_gate(commit, platforms=["linux", "macos"])
            gates["consumer_smoke"] = signed_gate(
                commit, agents=["claude-code", "codex"]
            )
            evidence = {"schema_version": 1, "tag": fixture.tag, "commit": commit, "gates": gates}
            evidence["evidence_sha256"] = release_collection.canonical_digest(evidence)
            path = parent / "evidence.json"
            path.write_text(json.dumps(evidence), encoding="utf-8")
            with self.assertRaisesRegex(release_collection.ReleaseError, "incomplete"):
                release_collection.verify_evidence(fixture.root, fixture.tag, path)
            evidence["gates"]["supported_platform_ci"] = signed_gate(
                commit, platforms=["linux", "macos", "windows"]
            )
            path.write_text(json.dumps(evidence), encoding="utf-8")
            with self.assertRaisesRegex(release_collection.ReleaseError, "digest"):
                release_collection.verify_evidence(fixture.root, fixture.tag, path)

    def test_verify_evidence_rejects_missing_claude_consumer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            fixture = ReleaseFixture(parent)
            commit = git(fixture.root, "rev-parse", "HEAD")
            gates = {name: signed_gate(commit) for name in release_collection.REQUIRED_GATES}
            gates["locked_holdout"] = signed_gate(commit, assertion_digest="c" * 64)
            gates["supported_platform_ci"] = signed_gate(
                commit, platforms=["linux", "macos", "windows"]
            )
            gates["consumer_smoke"] = signed_gate(commit, agents=["codex"])
            evidence = {"schema_version": 1, "tag": fixture.tag, "commit": commit, "gates": gates}
            evidence["evidence_sha256"] = release_collection.canonical_digest(evidence)
            path = parent / "evidence.json"
            path.write_text(json.dumps(evidence), encoding="utf-8")

            with self.assertRaisesRegex(release_collection.ReleaseError, "Claude Code"):
                release_collection.verify_evidence(fixture.root, fixture.tag, path)

    def test_cleanup_plan_accepts_patch_equivalence_and_rejects_unique_work(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = ReleaseFixture(Path(directory))
            git(fixture.root, "switch", "-qc", "represented")
            (fixture.root / "represented.txt").write_text("represented", encoding="utf-8")
            git(fixture.root, "add", "represented.txt")
            git(fixture.root, "commit", "-qm", "represented")
            represented_commit = git(fixture.root, "rev-parse", "HEAD")
            git(fixture.root, "switch", "-q", "main")
            (fixture.root / "divergence.txt").write_text("main", encoding="utf-8")
            git(fixture.root, "add", "divergence.txt")
            git(fixture.root, "commit", "-qm", "diverge main")
            git(fixture.root, "cherry-pick", represented_commit)
            (fixture.root / "main-only.txt").write_text("main", encoding="utf-8")
            git(fixture.root, "add", "main-only.txt")
            git(fixture.root, "commit", "-qm", "main only")
            git(fixture.root, "switch", "-qc", "unique")
            (fixture.root / "unique.txt").write_text("unique", encoding="utf-8")
            git(fixture.root, "add", "unique.txt")
            git(fixture.root, "commit", "-qm", "unique")
            git(fixture.root, "switch", "-q", "main")
            git(fixture.root, "tag", "-a", fixture.tag, "-m", "release")

            result = release_collection.cleanup_plan(
                fixture.root, fixture.tag, "main", ["represented", "unique"]
            )

            by_name = {item["branch"]: item for item in result["branches"]}
            self.assertTrue(by_name["represented"]["safe_to_delete"])
            self.assertEqual("patch-equivalent", by_name["represented"]["reason"])
            self.assertFalse(by_name["unique"]["safe_to_delete"])
            self.assertEqual("unrepresented-commits", by_name["unique"]["reason"])
            self.assertFalse(result["safe_to_delete"])

    def test_audit_requires_annotated_local_tag_before_network(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = ReleaseFixture(Path(directory))
            git(fixture.root, "tag", fixture.tag)

            with self.assertRaisesRegex(release_collection.ReleaseError, "annotated"):
                release_collection.audit_release(fixture.root, fixture.tag, "kolabse/skills")

    def test_cleanup_apply_requires_audited_plan_and_removes_proven_branches(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = ReleaseFixture(Path(directory))
            git(fixture.root, "switch", "-c", "feature")
            (fixture.root / "feature.txt").write_text("done\n", encoding="utf-8")
            git(fixture.root, "add", "feature.txt")
            git(fixture.root, "commit", "-qm", "feature")
            git(fixture.root, "push", "-qu", "origin", "feature")
            git(fixture.root, "switch", "main")
            git(fixture.root, "merge", "--ff-only", "feature")
            git(fixture.root, "push", "-q", "origin", "main")
            git(fixture.root, "tag", "-am", "release", fixture.tag)
            git(fixture.root, "push", "-q", "origin", fixture.tag)
            plan = release_collection.cleanup_plan(fixture.root, fixture.tag, "main", ["feature"])
            audit = release_audit(fixture.tag, str(plan["primary_commit"]))

            result = release_collection.cleanup_apply(
                fixture.root, plan, audit, fixture.tag, "origin"
            )

            self.assertTrue(result["passed"])
            self.assertEqual(["feature"], result["deleted_local"])
            self.assertEqual(["feature"], result["deleted_remote"])
            self.assertEqual("main", git(fixture.root, "branch", "--show-current"))

    def test_cleanup_apply_rejects_missing_exact_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = ReleaseFixture(Path(directory))
            git(fixture.root, "tag", "-am", "release", fixture.tag)
            git(fixture.root, "push", "-q", "origin", fixture.tag)
            git(fixture.root, "branch", "feature")
            plan = release_collection.cleanup_plan(fixture.root, fixture.tag, "main", ["feature"])
            audit = release_audit(fixture.tag, str(plan["primary_commit"]))
            with self.assertRaisesRegex(release_collection.ReleaseError, "confirmation"):
                release_collection.cleanup_apply(fixture.root, plan, audit, "wrong", "origin")


class ReleaseRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        # Fixture remotes are local bare repositories; provider identity is mocked,
        # while every remote ref and conditional deletion uses real Git.
        identity = patch.object(release_collection, "remote_repository", return_value="kolabse/skills", create=True)
        identity.start()
        self.addCleanup(identity.stop)

    def policy(self, parent: Path, method: str = "squash") -> Path:
        path = parent / "route-policy.json"
        path.write_text(json.dumps({"schema_version": 1, "repository": "kolabse/skills",
                                    "remote": "origin", "primary": "main",
                                    "merge_method": method}), encoding="utf-8")
        return path

    def observation(self, fixture: ReleaseFixture) -> dict[str, object]:
        commit = git(fixture.root, "rev-parse", "HEAD")
        return {"repository": {"full_name": "kolabse/skills", "allow_merge_commit": True,
                               "allow_squash_merge": True, "allow_rebase_merge": True},
                "protection": {"required_linear_history": {"enabled": True}},
                "rules": [], "pull_request": {"number": 1, "state": "open", "merged": False,
                "head": {"sha": commit}, "base": {"sha": commit, "ref": "main",
                "repo": {"full_name": "kolabse/skills"}}}}

    def test_route_plan_honors_classic_linear_history_even_with_empty_rules(self) -> None:
        self.assertTrue(callable(getattr(release_collection, "route_plan", None)),
                        "read-only route-plan capability is required")
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            fixture = ReleaseFixture(parent)
            with patch.object(release_collection, "github_route_observation", return_value=self.observation(fixture)):
                result = release_collection.route_plan(fixture.root, fixture.tag, self.policy(parent, "merge"), 1)
            self.assertFalse(result["ready"])
            self.assertTrue(any("linear" in text for text in result["blockers"]))
            self.assertFalse(result["mutates_repository"])

    def test_route_plan_squash_requires_fresh_integrated_commit_evidence(self) -> None:
        self.assertTrue(callable(getattr(release_collection, "route_plan", None)),
                        "read-only route-plan capability is required")
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            fixture = ReleaseFixture(parent)
            with patch.object(release_collection, "github_route_observation", return_value=self.observation(fixture)):
                result = release_collection.route_plan(fixture.root, fixture.tag, self.policy(parent), 1)
            self.assertTrue(result["ready"], result["blockers"])
            self.assertEqual("actual-integrated-primary", result["tag_target"])
            self.assertTrue(result["new_commit_requires_new_evidence"])

    def evidence(self, parent: Path, tag: str, commit: str) -> Path:
        gates = {name: signed_gate(commit) for name in release_collection.REQUIRED_GATES}
        gates["locked_holdout"] = signed_gate(commit, assertion_digest="c" * 64)
        gates["supported_platform_ci"] = signed_gate(commit, platforms=["linux", "macos", "windows"])
        gates["consumer_smoke"] = signed_gate(commit, agents=["claude-code", "codex"])
        value = {"schema_version": 1, "tag": tag, "commit": commit, "gates": gates}
        value["evidence_sha256"] = release_collection.canonical_digest(value)
        path = parent / "release-evidence.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def squash_fixture(self, parent: Path) -> tuple[ReleaseFixture, str]:
        fixture = ReleaseFixture(parent)
        git(fixture.root, "switch", "-qc", "feature")
        (fixture.root / "feature.txt").write_text("done\n", encoding="utf-8")
        git(fixture.root, "add", "feature.txt")
        git(fixture.root, "commit", "-qm", "candidate")
        candidate = git(fixture.root, "rev-parse", "HEAD")
        git(fixture.root, "push", "-qu", "origin", "feature")
        git(fixture.root, "tag", "-am", "release", fixture.tag)
        git(fixture.root, "push", "-q", "origin", fixture.tag)
        git(fixture.root, "switch", "-q", "main")
        git(fixture.root, "merge", "--squash", "feature")
        git(fixture.root, "commit", "-qm", "integrated squash")
        git(fixture.root, "push", "-q", "origin", "main")
        return fixture, candidate

    def test_cleanup_tree_identical_tag_preserves_separate_audit_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            fixture, candidate = self.squash_fixture(parent)
            evidence = self.evidence(parent, fixture.tag, candidate)
            plan = release_collection.cleanup_plan(fixture.root, fixture.tag, "main", ["feature"],
                                                  release_evidence=evidence)
            self.assertEqual(candidate, plan["release_commit"])
            self.assertNotEqual(candidate, plan["primary_commit"])
            self.assertEqual("identical-tree", plan["representation"])
            result = release_collection.cleanup_apply(fixture.root, plan, release_audit(fixture.tag, candidate),
                                                     fixture.tag, "origin", release_evidence=evidence)
            self.assertTrue(result["passed"])
            self.assertEqual(candidate, result["release_commit"])

    def test_route_plan_rejects_incomplete_and_conflicting_provider_constraints(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            fixture = ReleaseFixture(parent)
            for rule in ({"type": "merge_queue"}, {"type": "pull_request", "parameters": {"allowed_merge_methods": ["rebase"]}}):
                facts = self.observation(fixture)
                facts["rules"] = [rule]
                with patch.object(release_collection, "github_route_observation", return_value=facts):
                    result = release_collection.route_plan(fixture.root, fixture.tag, self.policy(parent), 1)
                self.assertFalse(result["ready"])
            facts = self.observation(fixture)
            facts["repository"].pop("allow_squash_merge")
            with patch.object(release_collection, "github_route_observation", return_value=facts):
                with self.assertRaisesRegex(release_collection.ReleaseError, "incomplete"):
                    release_collection.route_plan(fixture.root, fixture.tag, self.policy(parent), 1)

    def test_route_plan_requires_explicit_policy_and_matching_pr(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            fixture = ReleaseFixture(parent)
            path = self.policy(parent)
            policy = json.loads(path.read_text())
            policy.pop("merge_method")
            path.write_text(json.dumps(policy))
            with patch.object(release_collection, "github_route_observation") as provider:
                with self.assertRaises(release_collection.ReleaseError):
                    release_collection.route_plan(fixture.root, fixture.tag, path, 1)
                provider.assert_not_called()
            facts = self.observation(fixture)
            facts["pull_request"]["head"]["sha"] = "f" * 40
            with patch.object(release_collection, "github_route_observation", return_value=facts):
                result = release_collection.route_plan(fixture.root, fixture.tag, self.policy(parent, "rebase"), 1)
            self.assertFalse(result["ready"])
            self.assertTrue(any("head/base" in reason for reason in result["blockers"]))

    def test_route_plan_merge_when_no_linear_constraint_and_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            fixture = ReleaseFixture(parent)
            facts = self.observation(fixture)
            facts["protection"] = {}
            before = git(fixture.root, "show-ref")
            with patch.object(release_collection, "github_route_observation", return_value=facts):
                result = release_collection.route_plan(fixture.root, fixture.tag, self.policy(parent, "merge"), 1)
            self.assertTrue(result["ready"], result["blockers"])
            self.assertEqual(before, git(fixture.root, "show-ref"))
            self.assertEqual("", git(fixture.root, "status", "--porcelain=v1"))

    def test_cleanup_different_sha_rejects_missing_wrong_or_tampered_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            fixture, candidate = self.squash_fixture(parent)
            with self.assertRaisesRegex(release_collection.ReleaseError, "require release evidence"):
                release_collection.cleanup_plan(fixture.root, fixture.tag, "main", ["feature"])
            path = self.evidence(parent, fixture.tag, git(fixture.root, "rev-parse", "HEAD"))
            with self.assertRaisesRegex(release_collection.ReleaseError, "required commit"):
                release_collection.cleanup_plan(fixture.root, fixture.tag, "main", ["feature"], release_evidence=path)
            path = self.evidence(parent, fixture.tag, candidate)
            value = json.loads(path.read_text())
            value["gates"]["review"]["passed"] = False
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(release_collection.ReleaseError, "digest"):
                release_collection.cleanup_plan(fixture.root, fixture.tag, "main", ["feature"], release_evidence=path)

    def test_cleanup_rejects_nonidentical_tree_and_primary_as_deletion_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            fixture, candidate = self.squash_fixture(parent)
            path = self.evidence(parent, fixture.tag, candidate)
            with self.assertRaisesRegex(release_collection.ReleaseError, "primary branch"):
                release_collection.cleanup_plan(fixture.root, fixture.tag, "main", ["main"], release_evidence=path)
            (fixture.root / "new.txt").write_text("new")
            git(fixture.root, "add", "new.txt")
            git(fixture.root, "commit", "-qm", "more work")
            with self.assertRaisesRegex(release_collection.ReleaseError, "identical trees"):
                release_collection.cleanup_plan(fixture.root, fixture.tag, "main", ["feature"], release_evidence=path)

    def test_cleanup_remote_race_is_conditional_and_reports_partial_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            fixture, candidate = self.squash_fixture(parent)
            path = self.evidence(parent, fixture.tag, candidate)
            for branch in ("first", "second"):
                git(fixture.root, "branch", branch, "feature")
                git(fixture.root, "push", "-q", "origin", branch)
            plan = release_collection.cleanup_plan(fixture.root, fixture.tag, "main", ["first", "second"], release_evidence=path)
            original = release_collection.run_git
            leases = []
            def race(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
                if args[:2] == ("push", "origin") and args[-1] == ":refs/heads/second":
                    leases.append(args[-2])
                    git(fixture.remote, "update-ref", "refs/heads/second", plan["primary_commit"])
                return original(root, *args)
            with patch.object(release_collection, "run_git", side_effect=race):
                result = release_collection.cleanup_apply(fixture.root, plan, release_audit(fixture.tag, candidate),
                                                         fixture.tag, "origin", release_evidence=path)
            self.assertFalse(result["passed"])
            self.assertEqual(["first"], result["deleted_remote"])
            self.assertEqual(["first"], result["deleted_local"])
            self.assertEqual(["second"], result["retained_local"])
            self.assertEqual([f"--force-with-lease=refs/heads/second:{candidate}"], leases)
            self.assertEqual(plan["primary_commit"], git(fixture.remote, "rev-parse", "refs/heads/second"))

    def test_cleanup_remote_primary_change_after_planning_fails_before_delete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            fixture, candidate = self.squash_fixture(parent)
            path = self.evidence(parent, fixture.tag, candidate)
            plan = release_collection.cleanup_plan(fixture.root, fixture.tag, "main", ["feature"], release_evidence=path)
            git(fixture.remote, "update-ref", "refs/heads/main", candidate)
            with self.assertRaisesRegex(release_collection.ReleaseError, "remote primary"):
                release_collection.cleanup_apply(fixture.root, plan, release_audit(fixture.tag, candidate),
                                                 fixture.tag, "origin", release_evidence=path)
            self.assertEqual(candidate, git(fixture.remote, "rev-parse", "refs/heads/feature"))

    def test_route_plan_rejects_remote_mutation_during_provider_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            fixture = ReleaseFixture(parent)
            facts = self.observation(fixture)
            original = release_collection.remote_observation
            calls = 0
            def changed(*args: object) -> dict[str, object]:
                nonlocal calls
                result = original(*args)
                calls += 1
                if calls == 2:
                    result["refs"]["refs/heads/main"] = "b" * 40
                return result
            with patch.object(release_collection, "remote_observation", side_effect=changed), patch.object(release_collection, "github_route_observation", return_value=facts):
                result = release_collection.route_plan(fixture.root, fixture.tag, self.policy(parent), 1)
            self.assertFalse(result["ready"])
            self.assertTrue(any("changed during" in reason for reason in result["blockers"]))

    def test_cleanup_plan_is_not_safe_with_missing_published_remote_tag(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = ReleaseFixture(Path(directory))
            git(fixture.root, "tag", "-am", "release", fixture.tag)
            git(fixture.root, "branch", "feature")
            plan = release_collection.cleanup_plan(fixture.root, fixture.tag, "main", ["feature"])
            self.assertFalse(plan["safe_to_delete"], "unpublished tag cannot authorize cleanup")

    def test_remote_observation_rejects_multiple_push_destinations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = ReleaseFixture(Path(directory))
            git(fixture.root, "config", "--add", "remote.origin.pushurl", str(fixture.remote))
            git(fixture.root, "config", "--add", "remote.origin.pushurl", str(fixture.root.parent / "other.git"))
            with self.assertRaisesRegex(release_collection.ReleaseError, "destination"):
                release_collection.remote_observation(fixture.root, "origin", ["refs/heads/main"])

    def test_route_plan_rejects_policy_for_another_remote_repository(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            fixture = ReleaseFixture(parent)
            with patch.object(release_collection, "remote_repository", return_value="other/collection"), patch.object(release_collection, "github_route_observation", return_value=self.observation(fixture)):
                result = release_collection.route_plan(fixture.root, fixture.tag, self.policy(parent), 1)
            self.assertFalse(result["ready"], "policy repository must match the selected remote")

    def test_github_observation_reads_classic_protection_and_paginated_rules(self) -> None:
        pr = {"number": 3, "state": "open", "merged": False, "body": "not a routing input",
              "head": {"sha": "a" * 40}, "base": {"sha": "b" * 40, "ref": "main",
              "repo": {"full_name": "kolabse/skills"}}}
        repo = {"full_name": "kolabse/skills", "allow_merge_commit": True,
                "allow_squash_merge": True, "allow_rebase_merge": True}
        with patch.object(release_collection, "run_json_command", side_effect=[repo,
                          {"protected": True}, {"required_linear_history": {"enabled": True}}, [[]], pr]) as read:
            result = release_collection.github_route_observation("kolabse/skills", "main", 3)
        self.assertTrue(result["protection"]["required_linear_history"]["enabled"])
        self.assertEqual([], result["rules"])
        self.assertNotIn("body", result["pull_request"])
        commands = [call.args[0] for call in read.call_args_list]
        self.assertTrue(any(command[-1].endswith("/protection") for command in commands))
        self.assertTrue(any("--paginate" in command and "--slurp" in command for command in commands))

    def test_github_unknown_classic_protection_never_becomes_unprotected(self) -> None:
        with patch.object(release_collection, "run_json_command", side_effect=[{}, {"protected": True},
                          release_collection.ReleaseError("classic protection unavailable")]):
            with self.assertRaisesRegex(release_collection.ReleaseError, "unavailable"):
                release_collection.github_route_observation("kolabse/skills", "main", 3)

    def test_cleanup_rejects_changed_tag_object_and_plan_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            fixture, candidate = self.squash_fixture(parent)
            path = self.evidence(parent, fixture.tag, candidate)
            plan = release_collection.cleanup_plan(fixture.root, fixture.tag, "main", ["feature"], release_evidence=path)
            altered = dict(plan, release_commit="f" * 40)
            with self.assertRaisesRegex(release_collection.ReleaseError, "digest"):
                release_collection.cleanup_apply(fixture.root, altered, release_audit(fixture.tag, candidate),
                                                 fixture.tag, "origin", release_evidence=path)
            # A distinct annotated object at the same commit is still a moved tag.
            git(fixture.root, "tag", "-f", "-am", "different annotation", fixture.tag, candidate)
            with self.assertRaisesRegex(release_collection.ReleaseError, "stale"):
                release_collection.cleanup_apply(fixture.root, plan, release_audit(fixture.tag, candidate),
                                                 fixture.tag, "origin", release_evidence=path)
            self.assertEqual(candidate, git(fixture.remote, "rev-parse", "refs/heads/feature"))

    def test_cleanup_local_race_retains_unproved_local_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            fixture, candidate = self.squash_fixture(parent)
            path = self.evidence(parent, fixture.tag, candidate)
            plan = release_collection.cleanup_plan(fixture.root, fixture.tag, "main", ["feature"], release_evidence=path)
            original = release_collection.run_git
            def race(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
                if args[:2] == ("push", "origin") and args[-1] == ":refs/heads/feature":
                    git(root, "update-ref", "refs/heads/feature", plan["primary_commit"])
                return original(root, *args)
            with patch.object(release_collection, "run_git", side_effect=race):
                result = release_collection.cleanup_apply(fixture.root, plan, release_audit(fixture.tag, candidate),
                                                         fixture.tag, "origin", release_evidence=path)
            self.assertFalse(result["passed"], "a local advance must not be removed")
            self.assertEqual([], result["deleted_local"])
            self.assertEqual(["feature"], result["deleted_remote"])
            self.assertEqual(plan["primary_commit"], git(fixture.root, "rev-parse", "refs/heads/feature"))

    def test_cleanup_rejects_other_repository_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            fixture, candidate = self.squash_fixture(parent)
            path = self.evidence(parent, fixture.tag, candidate)
            plan = release_collection.cleanup_plan(fixture.root, fixture.tag, "main", ["feature"], release_evidence=path)
            audit = release_audit(fixture.tag, candidate)
            audit["repository"] = "other/skills"
            audit["release_url"] = f"https://github.com/other/skills/releases/tag/{fixture.tag}"
            audit.pop("report_sha256")
            audit["report_sha256"] = release_collection.canonical_digest(audit)
            with self.assertRaisesRegex(release_collection.ReleaseError, "repository"):
                release_collection.cleanup_apply(fixture.root, plan, audit, fixture.tag, "origin", release_evidence=path)

    def test_route_policy_rejects_boolean_version_and_duplicate_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            fixture = ReleaseFixture(parent)
            path = self.policy(parent)
            original = path.read_text(encoding="utf-8")
            malformed = [original.replace('"schema_version": 1', '"schema_version": true'),
                         original.replace('"merge_method": "squash"', '"merge_method": "merge", "merge_method": "squash"')]
            for raw in malformed:
                with self.subTest(raw=raw):
                    path.write_text(raw, encoding="utf-8")
                    with patch.object(release_collection, "github_route_observation", return_value=self.observation(fixture)):
                        with self.assertRaises(release_collection.ReleaseError):
                            release_collection.route_plan(fixture.root, fixture.tag, path, 1)
            path.write_text('{"outer": {"method": "merge", "method": "squash"}}', encoding="utf-8")
            with self.assertRaisesRegex(release_collection.ReleaseError, "duplicate"):
                release_collection.load_object(path, "route policy")


if __name__ == "__main__":
    unittest.main()
