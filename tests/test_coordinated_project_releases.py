from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


COORDINATE = load_module(
    "coordinate_change",
    "skills/coordinate-code-documentation-repositories/scripts/coordinate_change.py",
)
GITFLOW = load_module(
    "gitflow_release",
    "skills/execute-configured-gitflow-releases/scripts/gitflow_release.py",
)


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, text=True, encoding="utf-8", errors="replace",
        capture_output=True, check=False,
    )
    if result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {result.stderr}")
    return result.stdout.strip()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def initialize_repository(parent: Path, name: str, initial_file: str) -> tuple[Path, Path]:
    remote = parent / f"{name}.git"
    repository = parent / name
    remote.mkdir()
    git(remote, "init", "--bare")
    repository.mkdir()
    git(repository, "init", "-b", "main")
    git(repository, "config", "user.name", "Test User")
    git(repository, "config", "user.email", "test@example.invalid")
    target = repository / initial_file
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("initial\n", encoding="utf-8")
    git(repository, "add", "--", initial_file)
    git(repository, "commit", "-m", "Initial")
    git(repository, "remote", "add", "origin", str(remote))
    git(repository, "push", "-u", "origin", "main")
    return repository, remote


class CoordinateRepositoriesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.parent = Path(self.temporary.name)
        self.application, _ = initialize_repository(self.parent, "application", "app.txt")
        self.documentation, _ = initialize_repository(self.parent, "documentation", "canonical/contract.md")
        self.config = {
            "version": 1,
            "repositories": {
                "implementation": {"path": "."},
                "documentation": {"path": "../documentation"},
            },
            "canonical_documentation": {
                "roots": ["canonical"],
                "required_topics": ["requirement", "validation"],
            },
            "traceability": {"method": "change-request"},
        }
        self.config_source = self.parent / "coordinate-config.json"
        write_json(self.config_source, self.config)
        first = COORDINATE.configure(self.application, self.config_source)
        second = COORDINATE.configure(self.application, None)
        self.assertTrue(first["changed"])
        self.assertFalse(second["changed"])
        git(self.application, "add", "--", str(COORDINATE.CONFIG_RELATIVE))
        git(self.application, "commit", "-m", "Configure paired repositories")
        git(self.application, "push")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def plan(self) -> dict:
        change_input = self.parent / "change.json"
        plan_path = self.parent / "paired-plan.json"
        write_json(change_input, {
            "outcome": "Keep behavior and canonical documentation aligned.",
            "documentation_sources": ["canonical/contract.md"],
            "documentation_targets": ["canonical/contract.md"],
            "topics": ["requirement", "validation"],
        })
        return COORDINATE.build_plan(self.application, change_input, plan_path)

    def evidence(
        self,
        plan: dict,
        implementation_commit: str,
        documentation_commit: str,
        documentation_evidence: dict[str, list[str]] | None = None,
        name: str = "paired-extra-evidence.json",
    ) -> Path:
        path = self.parent / name
        write_json(path, {
            "plan_sha256": plan["plan_sha256"],
            "implementation_commit": implementation_commit,
            "documentation_commit": documentation_commit,
            "documentation_evidence": documentation_evidence or {
                "requirement": ["canonical/contract.md"],
                "validation": ["canonical/contract.md"],
            },
            "validation_results": [
                {"name": "tests", "status": "passed", "evidence_sha256": "a" * 64}
            ],
            "traceability": [
                {"method": "change-request", "repository": "implementation", "reference": "change-1", "evidence_sha256": "b" * 64},
                {"method": "change-request", "repository": "documentation", "reference": "change-1", "evidence_sha256": "c" * 64},
            ],
        })
        return path

    def test_configure_status_plan_and_verify_published_pair(self) -> None:
        state = COORDINATE.status(self.application)
        self.assertTrue(state["ready"])
        plan = self.plan()
        self.assertTrue(plan["ready"])

        (self.application / "app.txt").write_text("implemented\n", encoding="utf-8")
        git(self.application, "add", "--", "app.txt")
        git(self.application, "commit", "-m", "Implement change")
        git(self.application, "push")
        implementation_commit = git(self.application, "rev-parse", "HEAD")

        (self.documentation / "canonical/contract.md").write_text(
            "Requirement: aligned.\nValidation: passed.\n", encoding="utf-8"
        )
        git(self.documentation, "add", "--", "canonical/contract.md")
        git(self.documentation, "commit", "-m", "Document change")
        git(self.documentation, "push")
        documentation_commit = git(self.documentation, "rev-parse", "HEAD")

        evidence_path = self.parent / "paired-evidence.json"
        write_json(evidence_path, {
            "plan_sha256": plan["plan_sha256"],
            "implementation_commit": implementation_commit,
            "documentation_commit": documentation_commit,
            "documentation_evidence": {
                "requirement": ["canonical/contract.md"],
                "validation": ["canonical/contract.md"],
            },
            "validation_results": [
                {"name": "tests", "status": "passed", "evidence_sha256": "a" * 64}
            ],
            "traceability": [
                {"method": "change-request", "repository": "implementation", "reference": "change-1", "evidence_sha256": "b" * 64},
                {"method": "change-request", "repository": "documentation", "reference": "change-1", "evidence_sha256": "c" * 64},
            ],
        })
        result = COORDINATE.verify_completion(
            self.application, self.parent / "paired-plan.json", evidence_path
        )
        self.assertTrue(result["passed"])
        self.assertEqual([], result["blockers"])

    def test_plan_blocks_dirty_or_unpublished_repository(self) -> None:
        (self.documentation / "canonical/contract.md").write_text("dirty\n", encoding="utf-8")
        plan = self.plan()
        self.assertFalse(plan["ready"])
        self.assertIn("documentation: worktree is dirty", plan["blockers"])

    def test_missing_repository_role_blocks_status(self) -> None:
        changed = dict(self.config)
        changed["repositories"] = {
            "implementation": {"path": "."},
            "documentation": {"path": "../missing-documentation"},
        }
        write_json(self.config_source, changed)
        COORDINATE.configure(self.application, self.config_source)
        state = COORDINATE.status(self.application)
        self.assertFalse(state["ready"])
        self.assertTrue(any("path does not exist" in item for item in state["blockers"]))

    def test_plan_rejects_missing_topic_and_repository_output(self) -> None:
        change_input = self.parent / "bad-change.json"
        write_json(change_input, {
            "outcome": "Incomplete",
            "documentation_sources": ["canonical/contract.md"],
            "documentation_targets": ["canonical/contract.md"],
            "topics": ["requirement"],
        })
        with self.assertRaisesRegex(COORDINATE.CoordinationError, "omits required topics"):
            COORDINATE.build_plan(self.application, change_input, None)
        write_json(change_input, {
            "outcome": "Complete",
            "documentation_sources": ["canonical/contract.md"],
            "documentation_targets": ["canonical/contract.md"],
            "topics": ["requirement", "validation"],
        })
        with self.assertRaisesRegex(COORDINATE.CoordinationError, "outside the implementation"):
            COORDINATE.build_plan(self.application, change_input, self.application / "plan.json")

    def test_rejects_absolute_paths_and_unknown_versions(self) -> None:
        invalid = dict(self.config)
        invalid["repositories"] = {
            "implementation": {"path": "C:/private/application"},
            "documentation": {"path": "../documentation"},
        }
        with self.assertRaisesRegex(COORDINATE.CoordinationError, "must not be absolute"):
            COORDINATE.validate_config(invalid)
        future = dict(self.config)
        future["version"] = 2
        with self.assertRaisesRegex(COORDINATE.CoordinationError, "unknown newer"):
            COORDINATE.validate_config(future)
        malformed_topics = json.loads(json.dumps(self.config))
        malformed_topics["canonical_documentation"]["required_topics"] = [{"topic": "requirement"}]
        with self.assertRaisesRegex(COORDINATE.CoordinationError, "unsupported topic"):
            COORDINATE.validate_config(malformed_topics)
        with self.assertRaisesRegex(COORDINATE.CoordinationError, "contains a URL"):
            COORDINATE.validate_change_input({
                "outcome": "Document https://internal.example.invalid/change",
                "documentation_sources": ["canonical/contract.md"],
                "documentation_targets": ["canonical/contract.md"],
                "topics": ["requirement", "validation"],
            }, COORDINATE.validate_config(self.config), self.documentation)

    def test_resolved_repository_roles_must_be_distinct(self) -> None:
        same_repository = json.loads(json.dumps(self.config))
        same_repository["repositories"] = {
            "implementation": {"path": "."},
            "documentation": {"path": "./"},
        }
        write_json(self.config_source, same_repository)
        COORDINATE.configure(self.application, self.config_source)
        with self.assertRaisesRegex(COORDINATE.CoordinationError, "resolve to separate"):
            COORDINATE.resolve_contract(self.application)

    def test_verification_requires_changed_planned_documentation_targets(self) -> None:
        plan = self.plan()
        (self.application / "app.txt").write_text("implemented\n", encoding="utf-8")
        git(self.application, "add", "--", "app.txt")
        git(self.application, "commit", "-m", "Implement change")
        git(self.application, "push")
        implementation_commit = git(self.application, "rev-parse", "HEAD")

        unrelated = self.documentation / "canonical/other.md"
        unrelated.write_text("unrelated\n", encoding="utf-8")
        git(self.documentation, "add", "--", "canonical/other.md")
        git(self.documentation, "commit", "-m", "Change unrelated documentation")
        git(self.documentation, "push")
        documentation_commit = git(self.documentation, "rev-parse", "HEAD")

        result = COORDINATE.verify_completion(
            self.application,
            self.parent / "paired-plan.json",
            self.evidence(plan, implementation_commit, documentation_commit),
        )
        self.assertFalse(result["passed"])
        self.assertIn(
            "planned documentation target did not change: canonical/contract.md",
            result["blockers"],
        )

    def test_verification_reports_repository_that_disappeared_after_plan(self) -> None:
        plan = self.plan()
        moved = self.parent / "documentation-moved"
        self.documentation.rename(moved)
        evidence = self.evidence(
            plan,
            plan["repositories"]["implementation"]["head"],
            plan["repositories"]["documentation"]["head"],
            name="missing-repository-evidence.json",
        )

        result = COORDINATE.verify_completion(
            self.application, self.parent / "paired-plan.json", evidence
        )
        self.assertFalse(result["passed"])
        self.assertIn("documentation: repository path does not exist", result["blockers"])

    def test_verification_enforces_planned_topics_and_traceability_method(self) -> None:
        plan = self.plan()
        plan["topics"].append("behavior")
        plan = COORDINATE.signed(
            {key: value for key, value in plan.items() if key != "plan_sha256"},
            "plan_sha256",
        )
        write_json(self.parent / "paired-plan.json", plan)
        evidence = self.evidence(
            plan,
            plan["repositories"]["implementation"]["head"],
            plan["repositories"]["documentation"]["head"],
            name="contract-evidence.json",
        )
        value = json.loads(evidence.read_text(encoding="utf-8"))
        value["traceability"][0]["method"] = "release-evidence"
        write_json(evidence, value)

        result = COORDINATE.verify_completion(
            self.application, self.parent / "paired-plan.json", evidence
        )
        self.assertFalse(result["passed"])
        self.assertIn("documentation evidence is missing for topic: behavior", result["blockers"])
        self.assertIn(
            "traceability record is invalid or uses the wrong configured method",
            result["blockers"],
        )

    def test_verification_rejects_unplanned_evidence_and_rewritten_history(self) -> None:
        plan = self.plan()
        tree = git(self.application, "rev-parse", "HEAD^{tree}")
        unrelated_commit = git(self.application, "commit-tree", tree, "-m", "Replacement history")
        git(self.application, "update-ref", "refs/heads/main", unrelated_commit)
        git(self.application, "push", "--force", "origin", "main")

        other = self.documentation / "canonical/other.md"
        other.write_text("existing evidence\n", encoding="utf-8")
        (self.documentation / "canonical/contract.md").write_text("updated target\n", encoding="utf-8")
        git(self.documentation, "add", "--", "canonical/contract.md", "canonical/other.md")
        git(self.documentation, "commit", "-m", "Update documentation")
        git(self.documentation, "push")
        documentation_commit = git(self.documentation, "rev-parse", "HEAD")

        result = COORDINATE.verify_completion(
            self.application,
            self.parent / "paired-plan.json",
            self.evidence(
                plan,
                unrelated_commit,
                documentation_commit,
                {"requirement": ["canonical/other.md"], "validation": ["canonical/contract.md"]},
                "rewritten-evidence.json",
            ),
        )
        self.assertFalse(result["passed"])
        self.assertIn("implementation final commit does not descend from the planned commit", result["blockers"])
        self.assertIn("documentation evidence is not a planned target: canonical/other.md", result["blockers"])


class ConfiguredGitFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.parent = Path(self.temporary.name)
        self.repository, _ = initialize_repository(self.parent, "service", "service.txt")
        git(self.repository, "branch", "-m", "main", "production")
        git(self.repository, "push", "origin", ":main")
        git(self.repository, "push", "-u", "origin", "production")
        git(self.repository, "switch", "-c", "development")
        git(self.repository, "push", "-u", "origin", "development")
        self.config = {
            "version": 1,
            "remote": "origin",
            "branches": {
                "development": "development",
                "production": "production",
                "hotfix_prefix": "hotfix/",
            },
            "protected_production": True,
            "default_route": "standard",
            "gates": {
                "common": ["tests"],
                "standard": ["documentation"],
                "hotfix": ["regression"],
            },
            "deployment": {"evidence_required": True},
            "reintegration": {"required": True},
        }
        self.config_source = self.parent / "gitflow-config.json"
        write_json(self.config_source, self.config)
        first = GITFLOW.configure(self.repository, self.config_source)
        second = GITFLOW.configure(self.repository, None)
        self.assertTrue(first["changed"])
        self.assertFalse(second["changed"])
        git(self.repository, "add", "--", str(GITFLOW.CONFIG_RELATIVE))
        git(self.repository, "commit", "-m", "Configure GitFlow")
        git(self.repository, "push")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def route_plan(self, value: dict, name: str = "release-plan.json") -> dict:
        input_path = self.parent / f"{name}.input.json"
        output_path = self.parent / name
        write_json(input_path, value)
        return GITFLOW.build_plan(self.repository, input_path, output_path)

    def evidence(self, plan: dict, *, reintegration: dict) -> Path:
        path = self.parent / f"evidence-{plan['route']}.json"
        write_json(path, {
            "plan_sha256": plan["plan_sha256"],
            "source_commit": plan["source_commit"],
            "gate_evidence": {
                gate: {"status": "passed", "commit": plan["source_commit"], "evidence_sha256": "a" * 64}
                for gate in plan["gates"]
            },
            "review": {
                "status": "passed",
                "source_branch": plan["source_branch"],
                "target_branch": plan["target_branch"],
                "evidence_sha256": "b" * 64,
            },
            "production_commit": plan["source_commit"],
            "deployment": {
                "status": "passed",
                "production_commit": plan["source_commit"],
                "evidence_sha256": "c" * 64,
            },
            "reintegration": reintegration,
        })
        return path

    def publish_to_production(self, source_branch: str) -> None:
        git(self.repository, "switch", "production")
        git(self.repository, "merge", "--ff-only", source_branch)
        git(self.repository, "push")

    def test_standard_release_plan_and_remote_verification(self) -> None:
        state = GITFLOW.status(self.repository)
        self.assertTrue(state["ready"])
        plan = self.route_plan({
            "release_id": "1.0.0",
            "source_branch": "development",
            "explicit_hotfix": False,
        })
        self.assertTrue(plan["ready"])
        self.assertEqual(["tests", "documentation"], plan["gates"])
        self.publish_to_production("development")
        evidence = self.evidence(plan, reintegration={
            "status": "not-required", "target_branch": "development",
            "commit": None, "evidence_sha256": None,
        })
        result = GITFLOW.verify_completion(
            self.repository, self.parent / "release-plan.json", evidence
        )
        self.assertTrue(result["passed"])
        self.assertTrue(result["production_published"])

    def test_unmerged_source_is_not_reported_as_published(self) -> None:
        plan = self.route_plan({
            "release_id": "not-published",
            "source_branch": "development",
            "explicit_hotfix": False,
        }, "not-published-plan.json")
        production_commit = plan["remote_identities"]["production"]
        evidence = self.evidence(plan, reintegration={
            "status": "not-required", "target_branch": "development",
            "commit": None, "evidence_sha256": None,
        })
        value = json.loads(evidence.read_text(encoding="utf-8"))
        value["production_commit"] = production_commit
        value["deployment"]["production_commit"] = production_commit
        write_json(evidence, value)

        result = GITFLOW.verify_completion(
            self.repository, self.parent / "not-published-plan.json", evidence
        )
        self.assertFalse(result["passed"])
        self.assertFalse(result["production_published"])

    def test_hotfix_requires_intent_ancestry_and_reintegration(self) -> None:
        self.publish_to_production("development")
        git(self.repository, "switch", "-c", "hotfix/urgent")
        (self.repository / "service.txt").write_text("fixed\n", encoding="utf-8")
        git(self.repository, "add", "--", "service.txt")
        git(self.repository, "commit", "-m", "Urgent fix")
        git(self.repository, "push", "-u", "origin", "hotfix/urgent")
        with self.assertRaisesRegex(GITFLOW.GitFlowError, "explicit hotfix intent"):
            self.route_plan({
                "release_id": "hotfix-1",
                "route": "hotfix",
                "source_branch": "hotfix/urgent",
                "explicit_hotfix": False,
            }, "rejected-hotfix.json")
        plan = self.route_plan({
            "release_id": "hotfix-1",
            "route": "hotfix",
            "source_branch": "hotfix/urgent",
            "explicit_hotfix": True,
        }, "hotfix-plan.json")
        self.assertTrue(plan["ready"])
        self.assertEqual(["tests", "regression"], plan["gates"])
        self.publish_to_production("hotfix/urgent")
        git(self.repository, "switch", "development")
        git(self.repository, "merge", "--ff-only", "hotfix/urgent")
        git(self.repository, "push")
        evidence = self.evidence(plan, reintegration={
            "status": "passed", "target_branch": "development",
            "commit": plan["source_commit"], "evidence_sha256": "d" * 64,
        })
        result = GITFLOW.verify_completion(
            self.repository, self.parent / "hotfix-plan.json", evidence
        )
        self.assertTrue(result["passed"])
        self.assertEqual("passed", result["reintegration_status"])

    def test_blocked_hotfix_reintegration_is_not_completion(self) -> None:
        self.publish_to_production("development")
        git(self.repository, "switch", "-c", "hotfix/blocked")
        (self.repository / "service.txt").write_text("blocked fix\n", encoding="utf-8")
        git(self.repository, "add", "--", "service.txt")
        git(self.repository, "commit", "-m", "Blocked fix")
        git(self.repository, "push", "-u", "origin", "hotfix/blocked")
        plan = self.route_plan({
            "release_id": "hotfix-blocked", "route": "hotfix",
            "source_branch": "hotfix/blocked", "explicit_hotfix": True,
        }, "blocked-plan.json")
        self.publish_to_production("hotfix/blocked")
        evidence = self.evidence(plan, reintegration={
            "status": "blocked", "target_branch": "development",
            "commit": None, "evidence_sha256": None,
        })
        result = GITFLOW.verify_completion(
            self.repository, self.parent / "blocked-plan.json", evidence
        )
        self.assertFalse(result["passed"])
        self.assertTrue(any("reintegration is blocked" in item for item in result["blockers"]))

    def test_verification_requires_production_to_contain_planned_source(self) -> None:
        plan = self.route_plan({
            "release_id": "unrelated-production",
            "source_branch": "development",
            "explicit_hotfix": False,
        }, "unrelated-production-plan.json")
        production_tree = git(self.repository, "rev-parse", "origin/production^{tree}")
        unrelated = git(self.repository, "commit-tree", production_tree, "-m", "Unrelated production")
        git(self.repository, "push", "--force", "origin", f"{unrelated}:production")
        evidence = self.evidence(plan, reintegration={
            "status": "not-required", "target_branch": "development",
            "commit": None, "evidence_sha256": None,
        })
        value = json.loads(evidence.read_text(encoding="utf-8"))
        value["production_commit"] = unrelated
        value["deployment"]["production_commit"] = unrelated
        write_json(evidence, value)

        result = GITFLOW.verify_completion(
            self.repository, self.parent / "unrelated-production-plan.json", evidence
        )
        self.assertFalse(result["passed"])
        self.assertIn("remote production does not contain the planned source commit", result["blockers"])

    def test_verification_preserves_planned_production_history(self) -> None:
        git(self.repository, "switch", "production")
        (self.repository / "production-only.txt").write_text("published\n", encoding="utf-8")
        git(self.repository, "add", "--", "production-only.txt")
        git(self.repository, "commit", "-m", "Advance production independently")
        git(self.repository, "push")
        git(self.repository, "switch", "development")
        plan = self.route_plan({
            "release_id": "preserve-production",
            "source_branch": "development",
            "explicit_hotfix": False,
        }, "preserve-production-plan.json")
        git(self.repository, "push", "--force", "origin", f"{plan['source_commit']}:production")
        evidence = self.evidence(plan, reintegration={
            "status": "not-required", "target_branch": "development",
            "commit": None, "evidence_sha256": None,
        })

        result = GITFLOW.verify_completion(
            self.repository, self.parent / "preserve-production-plan.json", evidence
        )
        self.assertFalse(result["passed"])
        self.assertIn("remote production discarded the planned production history", result["blockers"])

    def test_hotfix_reintegration_must_contain_planned_source(self) -> None:
        self.publish_to_production("development")
        git(self.repository, "switch", "-c", "hotfix/not-reintegrated")
        (self.repository / "service.txt").write_text("hotfix\n", encoding="utf-8")
        git(self.repository, "add", "--", "service.txt")
        git(self.repository, "commit", "-m", "Hotfix")
        git(self.repository, "push", "-u", "origin", "hotfix/not-reintegrated")
        plan = self.route_plan({
            "release_id": "not-reintegrated", "route": "hotfix",
            "source_branch": "hotfix/not-reintegrated", "explicit_hotfix": True,
        }, "not-reintegrated-plan.json")
        self.publish_to_production("hotfix/not-reintegrated")
        git(self.repository, "switch", "development")
        (self.repository / "development-only.txt").write_text("independent\n", encoding="utf-8")
        git(self.repository, "add", "--", "development-only.txt")
        git(self.repository, "commit", "-m", "Independent development")
        git(self.repository, "push")
        development_commit = git(self.repository, "rev-parse", "HEAD")
        evidence = self.evidence(plan, reintegration={
            "status": "passed", "target_branch": "development",
            "commit": development_commit, "evidence_sha256": "d" * 64,
        })

        result = GITFLOW.verify_completion(
            self.repository, self.parent / "not-reintegrated-plan.json", evidence
        )
        self.assertFalse(result["passed"])
        self.assertIn("remote development does not contain the planned hotfix commit", result["blockers"])

    def test_hotfix_reintegration_preserves_planned_development_history(self) -> None:
        (self.repository / "development-only.txt").write_text("planned development\n", encoding="utf-8")
        git(self.repository, "add", "--", "development-only.txt")
        git(self.repository, "commit", "-m", "Advance planned development")
        git(self.repository, "push")
        config_text = (self.repository / GITFLOW.CONFIG_RELATIVE).read_text(encoding="utf-8")
        git(self.repository, "switch", "production")
        git(self.repository, "switch", "-c", "hotfix/preserve-development")
        config_path = self.repository / GITFLOW.CONFIG_RELATIVE
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(config_text, encoding="utf-8")
        (self.repository / "service.txt").write_text("hotfix\n", encoding="utf-8")
        git(self.repository, "add", "--", str(GITFLOW.CONFIG_RELATIVE), "service.txt")
        git(self.repository, "commit", "-m", "Independent hotfix")
        git(self.repository, "push", "-u", "origin", "hotfix/preserve-development")
        plan = self.route_plan({
            "release_id": "preserve-development", "route": "hotfix",
            "source_branch": "hotfix/preserve-development", "explicit_hotfix": True,
        }, "preserve-development-plan.json")
        self.publish_to_production("hotfix/preserve-development")
        git(self.repository, "push", "--force", "origin", f"{plan['source_commit']}:development")
        evidence = self.evidence(plan, reintegration={
            "status": "passed", "target_branch": "development",
            "commit": plan["source_commit"], "evidence_sha256": "d" * 64,
        })

        result = GITFLOW.verify_completion(
            self.repository, self.parent / "preserve-development-plan.json", evidence
        )
        self.assertFalse(result["passed"])
        self.assertIn("remote development discarded the planned development history", result["blockers"])

    def test_malformed_reintegration_returns_blocker(self) -> None:
        plan = self.route_plan({
            "release_id": "malformed-reintegration",
            "source_branch": "development",
            "explicit_hotfix": False,
        }, "malformed-reintegration-plan.json")
        self.publish_to_production("development")
        evidence = self.evidence(plan, reintegration={
            "status": "not-required", "target_branch": "development",
            "commit": None, "evidence_sha256": None,
        })
        value = json.loads(evidence.read_text(encoding="utf-8"))
        value["reintegration"] = []
        write_json(evidence, value)

        result = GITFLOW.verify_completion(
            self.repository, self.parent / "malformed-reintegration-plan.json", evidence
        )
        self.assertFalse(result["passed"])
        self.assertIn("reintegration evidence is invalid", result["blockers"])

    def test_not_required_deployment_requires_null_digest(self) -> None:
        optional = json.loads(json.dumps(self.config))
        optional["deployment"]["evidence_required"] = False
        write_json(self.config_source, optional)
        GITFLOW.configure(self.repository, self.config_source)
        git(self.repository, "add", "--", str(GITFLOW.CONFIG_RELATIVE))
        git(self.repository, "commit", "-m", "Make deployment evidence optional")
        git(self.repository, "push")
        plan = self.route_plan({
            "release_id": "optional-deployment",
            "source_branch": "development",
            "explicit_hotfix": False,
        }, "optional-deployment-plan.json")
        self.publish_to_production("development")
        evidence = self.evidence(plan, reintegration={
            "status": "not-required", "target_branch": "development",
            "commit": None, "evidence_sha256": None,
        })
        value = json.loads(evidence.read_text(encoding="utf-8"))
        value["deployment"]["status"] = "not-required"
        value["deployment"]["evidence_sha256"] = "malformed"
        write_json(evidence, value)

        result = GITFLOW.verify_completion(
            self.repository, self.parent / "optional-deployment-plan.json", evidence
        )
        self.assertFalse(result["passed"])
        self.assertIn("not-required deployment evidence digest must be null", result["blockers"])

    def test_missing_production_identity_is_not_reported_as_published(self) -> None:
        plan = self.route_plan({
            "release_id": "missing-production",
            "source_branch": "development",
            "explicit_hotfix": False,
        }, "missing-production-plan.json")
        git(self.repository, "update-ref", "-d", "refs/remotes/origin/production")
        evidence = self.evidence(plan, reintegration={
            "status": "not-required", "target_branch": "development",
            "commit": None, "evidence_sha256": None,
        })
        value = json.loads(evidence.read_text(encoding="utf-8"))
        value["production_commit"] = None
        value["deployment"]["production_commit"] = None
        write_json(evidence, value)

        result = GITFLOW.verify_completion(
            self.repository, self.parent / "missing-production-plan.json", evidence
        )
        self.assertFalse(result["passed"])
        self.assertFalse(result["production_published"])

    def test_ambiguous_route_and_duplicate_gate_are_rejected(self) -> None:
        no_default = dict(self.config)
        no_default["default_route"] = None
        with self.assertRaisesRegex(GITFLOW.GitFlowError, "route is ambiguous"):
            GITFLOW.validate_route_input({
                "release_id": "1.0", "source_branch": "development", "explicit_hotfix": False,
            }, GITFLOW.validate_config(no_default))
        duplicate = json.loads(json.dumps(self.config))
        duplicate["gates"]["hotfix"] = ["tests"]
        with self.assertRaisesRegex(GITFLOW.GitFlowError, "unique across"):
            GITFLOW.validate_config(duplicate)
        with self.assertRaisesRegex(GITFLOW.GitFlowError, "contains a URL"):
            GITFLOW.validate_route_input({
                "release_id": "https://internal.example.invalid/release",
                "source_branch": "development", "explicit_hotfix": False,
            }, GITFLOW.validate_config(self.config))

    def test_plan_rejects_output_inside_repository(self) -> None:
        input_path = self.parent / "route.json"
        write_json(input_path, {
            "release_id": "1.0.0", "source_branch": "development", "explicit_hotfix": False,
        })
        with self.assertRaisesRegex(GITFLOW.GitFlowError, "outside the repository"):
            GITFLOW.build_plan(self.repository, input_path, self.repository / "plan.json")

    def test_plan_compares_source_with_the_configured_remote(self) -> None:
        fork = self.parent / "fork.git"
        fork.mkdir()
        git(fork, "init", "--bare")
        git(self.repository, "remote", "add", "fork", str(fork))
        git(self.repository, "push", "-u", "fork", "development")
        git(self.repository, "switch", "-c", "origin-ahead")
        (self.repository / "service.txt").write_text("remote update\n", encoding="utf-8")
        git(self.repository, "add", "--", "service.txt")
        git(self.repository, "commit", "-m", "Advance configured remote")
        git(self.repository, "push", "origin", "HEAD:development")
        git(self.repository, "switch", "development")

        plan = self.route_plan({
            "release_id": "stale", "source_branch": "development", "explicit_hotfix": False,
        }, "stale-plan.json")
        self.assertFalse(plan["ready"])
        self.assertIn("source branch is behind the configured remote", plan["blockers"])


if __name__ == "__main__":
    unittest.main()
