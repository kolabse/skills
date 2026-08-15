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
        (self.root / "CHANGELOG.md").write_text(
            f"# Changelog\n\n## [{version}] - 2030-01-01\n", encoding="utf-8"
        )
        (self.root / "CONTRIBUTING.md").write_text("# Contributing\n", encoding="utf-8")
        (self.root / "scripts").mkdir()
        for name in ("validate_skills.py", "security_checks.py", "build_release.py"):
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
    def test_public_json_schemas_are_well_formed(self) -> None:
        schemas = ROOT / "skills/release-skill-collection/schemas"
        documents = [json.loads(path.read_text(encoding="utf-8")) for path in schemas.glob("*.json")]

        self.assertEqual(7, len(documents))
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
            self.assertEqual(5, len(result["checks"]))
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
            git(fixture.root, "branch", "feature")
            plan = release_collection.cleanup_plan(fixture.root, fixture.tag, "main", ["feature"])
            audit = release_audit(fixture.tag, str(plan["primary_commit"]))
            with self.assertRaisesRegex(release_collection.ReleaseError, "confirmation"):
                release_collection.cleanup_apply(fixture.root, plan, audit, "wrong", "origin")


if __name__ == "__main__":
    unittest.main()
