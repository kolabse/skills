from __future__ import annotations

import tempfile
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
from pathlib import Path

import test_coordinated_project_releases as fixtures
from test_coordinated_project_releases import COORDINATE, git, initialize_repository, write_json


class RequiredRepositoryTests(unittest.TestCase):
    tearDown = fixtures.CoordinateRepositoriesTests.tearDown

    def setUp(self) -> None:
        fixtures.CoordinateRepositoriesTests.setUp(self)
        self.infrastructure, _ = initialize_repository(self.parent, "infrastructure", "infra.txt")
        self.config["repositories"]["infrastructure"] = {"path": "../infrastructure"}
        write_json(self.config_source, self.config)
        COORDINATE.configure(self.application, self.config_source)
        git(self.application, "add", "--", str(COORDINATE.CONFIG_RELATIVE))
        git(self.application, "commit", "-m", "Require infrastructure coordination")
        git(self.application, "push")
        self.change = {
            "outcome": "Align implementation, infrastructure, and canonical documentation.",
            "documentation_sources": ["canonical/contract.md"],
            "documentation_targets": ["canonical/contract.md"],
            "topics": ["requirement", "validation"],
            "publication_order": ["infrastructure", "implementation", "documentation"],
        }
        self.change_path = self.parent / "change.json"
        self.plan_path = self.parent / "required-plan.json"
        self.evidence_path = self.parent / "required-evidence.json"
        write_json(self.change_path, self.change)

    def publish(self, plan: dict, *, empty_extra: bool = False, publish_extra: bool = True) -> dict:
        commits = {}
        for role, repository, filename in (
            ("infrastructure", self.infrastructure, "infra.txt"),
            ("implementation", self.application, "app.txt"),
            ("documentation", self.documentation, "canonical/contract.md"),
        ):
            if role != "infrastructure" or not empty_extra:
                (repository / filename).write_text("updated\n", encoding="utf-8")
                git(repository, "add", "--", filename)
            git(repository, "commit", "--allow-empty", "-m", "Coordinated change")
            if role != "infrastructure" or publish_extra:
                git(repository, "push")
            commits[role] = git(repository, "rev-parse", "HEAD")
        evidence = {
            "plan_sha256": plan["plan_sha256"],
            "implementation_commit": commits["implementation"],
            "documentation_commit": commits["documentation"],
            "additional_commits": {"infrastructure": commits["infrastructure"]},
            "documentation_evidence": {topic: ["canonical/contract.md"] for topic in self.change["topics"]},
            "validation_results": [
                {"name": "checks", "status": "passed", "evidence_sha256": "a" * 64,
                 "repository": role, "commit": commit}
                for role, commit in commits.items()
            ],
            "traceability": [
                {"method": "change-request", "repository": role, "reference": "change-107", "evidence_sha256": "b" * 64}
                for role in commits
            ],
        }
        return evidence

    def verify(self, evidence: dict) -> dict:
        write_json(self.evidence_path, evidence)
        return COORDINATE.verify_completion(self.application, self.plan_path, self.evidence_path)

    def test_three_required_repositories_publish_and_verify(self) -> None:
        state = COORDINATE.status(self.application)
        self.assertTrue(state["ready"], state["blockers"])
        self.assertEqual(set(self.config["repositories"]), {item["role"] for item in state["repositories"]})
        plan = COORDINATE.build_plan(self.application, self.change_path, self.plan_path)
        self.assertTrue(plan["ready"], plan["blockers"])
        self.assertEqual(self.change["publication_order"], plan["publication_order"])
        result = self.verify(self.publish(plan))
        self.assertTrue(result["passed"], result["blockers"])
        self.assertEqual(set(self.config["repositories"]), set(result["commits"]))
        for report in (state, plan, result):
            with self.subTest(mode=report["mode"]):
                output = StringIO()
                with redirect_stdout(output):
                    COORDINATE.emit(report, False)
                rendered = output.getvalue()
                for role in self.config["repositories"]:
                    self.assertIn(f"{role}: revision=", rendered)
                self.assertIn("publication=", rendered)
                self.assertIn("validation=", rendered)
                self.assertIn("does not fetch", rendered)
        self.assertEqual("passed", result["repository_results"]["infrastructure"]["validation"])

    def test_extra_repository_state_blocks_status_plan_and_verification(self) -> None:
        extra_file = self.infrastructure / "infra.txt"
        extra_file.write_text("dirty\n", encoding="utf-8")
        for report in (COORDINATE.status(self.application), COORDINATE.build_plan(self.application, self.change_path, None)):
            self.assertFalse(report["ready"])
            self.assertIn("infrastructure: worktree is dirty", report["blockers"])
        git(self.infrastructure, "add", "--", "infra.txt")
        git(self.infrastructure, "commit", "-m", "Unpublished infrastructure")
        unpublished = COORDINATE.build_plan(self.application, self.change_path, None)
        self.assertFalse(unpublished["ready"])
        self.assertTrue(any("infrastructure:" in item and "unpublished" in item for item in unpublished["blockers"]))
        git(self.infrastructure, "push")
        plan = COORDINATE.build_plan(self.application, self.change_path, self.plan_path)
        evidence = self.publish(plan, publish_extra=False)
        unpublished_result = self.verify(evidence)
        self.assertFalse(unpublished_result["passed"])
        self.assertIn("infrastructure final commit is not the tracked upstream identity", unpublished_result["blockers"])
        git(self.infrastructure, "push")
        git(self.infrastructure, "push", "origin", "HEAD:alternate")
        git(self.infrastructure, "branch", "--set-upstream-to", "origin/alternate")
        result = self.verify(evidence)
        self.assertFalse(result["passed"])
        self.assertIn("infrastructure tracked upstream changed after the plan", result["blockers"])
        git(self.infrastructure, "branch", "--set-upstream-to", "origin/main")
        extra_file.write_text("dirty again\n", encoding="utf-8")
        self.assertIn("infrastructure: worktree is dirty", self.verify(evidence)["blockers"])
        extra_file.write_text("updated\n", encoding="utf-8")
        moved = self.parent / "infrastructure-moved"
        self.infrastructure.rename(moved)
        try:
            for report in (COORDINATE.status(self.application), COORDINATE.build_plan(self.application, self.change_path, None), self.verify(evidence)):
                self.assertIn("infrastructure: repository path does not exist", report["blockers"])
        finally:
            moved.rename(self.infrastructure)

    def test_evidence_requires_exact_commits_and_each_roles_bound_validation_and_traceability(self) -> None:
        plan = COORDINATE.build_plan(self.application, self.change_path, self.plan_path)
        evidence = self.publish(plan)
        for additional in (None, [], "invalid", {}, {"implementation": evidence["implementation_commit"]}, {"unknown": "a" * 40}, {**evidence["additional_commits"], "unknown": "b" * 40}):
            with self.subTest(additional=additional):
                invalid = deepcopy(evidence)
                if additional is None:
                    del invalid["additional_commits"]
                else:
                    invalid["additional_commits"] = additional
                with self.assertRaisesRegex(COORDINATE.CoordinationError, "additional_commits"):
                    self.verify(invalid)
        invalid = deepcopy(evidence)
        invalid["additional_commits"]["infrastructure"] = "invalid"
        self.assertIn("additional_commits.infrastructure is invalid", self.verify(invalid)["blockers"])
        invalid["additional_commits"]["infrastructure"] = plan["repositories"]["infrastructure"]["head"]
        self.assertIn("infrastructure final commit does not match local HEAD", self.verify(invalid)["blockers"])
        for role in self.config["repositories"]:
            with self.subTest(role=role):
                invalid = deepcopy(evidence)
                invalid["validation_results"] = [item for item in invalid["validation_results"] if item["repository"] != role]
                self.assertIn(f"{role} validation evidence is missing for the final commit", self.verify(invalid)["blockers"])
                invalid = deepcopy(evidence)
                for item in invalid["validation_results"]:
                    if item["repository"] == role:
                        item["commit"] = plan["repositories"][role]["head"]
                result = self.verify(invalid)
                self.assertIn(f"{role} validation result commit does not match the final commit", result["blockers"])
                invalid = deepcopy(evidence)
                invalid["traceability"] = [item for item in invalid["traceability"] if item["repository"] != role]
                self.assertTrue(any("traceability must cover" in item and role in item for item in self.verify(invalid)["blockers"]))
        for field in ("repository", "commit"):
            invalid = deepcopy(evidence)
            del invalid["validation_results"][0][field]
            self.assertFalse(self.verify(invalid)["passed"])
        for role in ("unknown", ["infrastructure"]):
            invalid = deepcopy(evidence)
            invalid["validation_results"][0]["repository"] = role
            self.assertIn("validation result repository must be a configured role", self.verify(invalid)["blockers"])
            invalid = deepcopy(evidence)
            invalid["traceability"][0]["repository"] = role
            self.assertIn("traceability record is invalid or uses the wrong configured method", self.verify(invalid)["blockers"])
        invalid = deepcopy(evidence)
        invalid["validation_results"] = [{"name": "unbound tests", "status": "passed", "evidence_sha256": "a" * 64}]
        self.assertFalse(self.verify(invalid)["passed"])
        for field in ("validation_results", "traceability"):
            invalid = deepcopy(evidence)
            invalid[field][0]["evidence_sha256"] = int("1" * 64)
            self.assertFalse(self.verify(invalid)["passed"])

    def test_extra_empty_commit_is_not_completion(self) -> None:
        plan = COORDINATE.build_plan(self.application, self.change_path, self.plan_path)
        result = self.verify(self.publish(plan, empty_extra=True))
        self.assertFalse(result["passed"])
        self.assertIn("infrastructure content did not change from the plan", result["blockers"])

    def test_role_reporting_keeps_invalid_validation_and_similar_roles_separate(self) -> None:
        api, _ = initialize_repository(self.parent, "infrastructure-api", "api.txt")
        self.config["repositories"]["infrastructure-api"] = {"path": "../infrastructure-api"}
        write_json(self.config_source, self.config)
        COORDINATE.configure(self.application, self.config_source)
        git(self.application, "add", "--", str(COORDINATE.CONFIG_RELATIVE))
        git(self.application, "commit", "-m", "Require API repository coordination")
        git(self.application, "push")
        self.change["publication_order"].append("infrastructure-api")
        write_json(self.change_path, self.change)
        plan = COORDINATE.build_plan(self.application, self.change_path, self.plan_path)
        evidence = self.publish(plan)
        (api / "api.txt").write_text("updated\n", encoding="utf-8")
        git(api, "add", "--", "api.txt")
        git(api, "commit", "-m", "Update API")
        git(api, "push")
        commit = git(api, "rev-parse", "HEAD")
        evidence["additional_commits"]["infrastructure-api"] = commit
        evidence["validation_results"].append({
            "name": "API checks", "status": "passed", "evidence_sha256": "a" * 64,
            "repository": "infrastructure-api", "commit": commit,
        })
        evidence["traceability"].append({
            "method": "change-request", "repository": "infrastructure-api",
            "reference": "change-107", "evidence_sha256": "b" * 64,
        })
        self.assertTrue(self.verify(evidence)["passed"])
        with self.subTest(case="invalid validation name alongside a valid result"):
            invalid = deepcopy(evidence)
            invalid["validation_results"].append({**invalid["validation_results"][0], "name": ""})
            report = self.verify(invalid)
            self.assertFalse(report["passed"])
            role_result = report["repository_results"]["infrastructure"]
            self.assertEqual("invalid", role_result["validation"])
            self.assertTrue(any(item.startswith("infrastructure ") and "validation result name" in item for item in role_result["blockers"]))
        with self.subTest(case="similar role names do not share commit blockers"):
            invalid = deepcopy(evidence)
            invalid["additional_commits"]["infrastructure-api"] = "invalid"
            report = self.verify(invalid)
            self.assertFalse(report["passed"])
            self.assertIn("additional_commits.infrastructure-api is invalid", report["repository_results"]["infrastructure-api"]["blockers"])
            self.assertEqual([], report["repository_results"]["infrastructure"]["blockers"])

    def test_required_roles_publication_order_paths_and_signed_plan_contract(self) -> None:
        for order in (["implementation", "documentation"], ["implementation", "documentation", "documentation"], ["implementation", "documentation", "unknown"], "infrastructure", [[], "documentation", "infrastructure"]):
            with self.subTest(order=order):
                with self.assertRaisesRegex(COORDINATE.CoordinationError, "publication_order"):
                    COORDINATE.validate_change_input({**self.change, "publication_order": order}, self.config, self.documentation)
        with self.assertRaisesRegex(COORDINATE.CoordinationError, "outside the infrastructure"):
            COORDINATE.build_plan(self.application, self.change_path, self.infrastructure / "plan.json")
        plan = COORDINATE.build_plan(self.application, self.change_path, self.plan_path)
        evidence = self.publish(plan)
        for role in self.config["repositories"]:
            invalid = deepcopy(plan)
            del invalid["repositories"][role]
            invalid = COORDINATE.signed({key: value for key, value in invalid.items() if key != "plan_sha256"}, "plan_sha256")
            write_json(self.plan_path, invalid)
            with self.assertRaisesRegex(COORDINATE.CoordinationError, "plan repositories"):
                self.verify(evidence)
        invalid = deepcopy(plan)
        del invalid["repositories"]["infrastructure"]["head"]
        write_json(self.plan_path, COORDINATE.signed({key: value for key, value in invalid.items() if key != "plan_sha256"}, "plan_sha256"))
        with self.assertRaisesRegex(COORDINATE.CoordinationError, "plan repository contract"):
            self.verify(evidence)
        for alias in ("./", "../infrastructure/../application"):
            invalid = deepcopy(self.config)
            invalid["repositories"]["infrastructure"]["path"] = alias
            write_json(self.config_source, invalid)
            COORDINATE.configure(self.application, self.config_source)
            with self.assertRaisesRegex(COORDINATE.CoordinationError, "resolve to separate"):
                COORDINATE.resolve_contract(self.application)


class RequiredRepositoryContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = {
            "version": 1,
            "repositories": {"implementation": {"path": "."}, "documentation": {"path": "../documentation"}},
            "canonical_documentation": {"roots": ["canonical"], "required_topics": ["requirement", "validation"]},
            "traceability": {"method": "change-request"},
        }

    def test_legacy_config_normalization_and_digest_are_preserved(self) -> None:
        normalized = COORDINATE.validate_config(self.config)
        self.assertEqual(self.config, normalized)
        # Captured from the original v1 helper before additional roles were supported.
        self.assertEqual("cb6d0052853a131629ea5b0ea2da2d91decce85f07e65538ffb7bc5ca5bc987c", COORDINATE.canonical_digest(normalized))
        change = {"outcome": "Aligned.", "documentation_sources": ["contract.md"], "documentation_targets": ["contract.md"], "topics": ["requirement", "validation"]}
        # Use an existing file as source without requiring Git setup for normalization.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "contract.md").write_text("source\n", encoding="utf-8")
            config = deepcopy(self.config)
            config["canonical_documentation"]["roots"] = ["."]
            self.assertEqual(change, COORDINATE.validate_change_input(change, config, root))

    def test_role_contract_rejects_invalid_names_and_boolean_version(self) -> None:
        for role in ("infra", "service-2", "x" * 63):
            config = deepcopy(self.config)
            config["repositories"][role] = {"path": "../extra"}
            self.assertIn(role, COORDINATE.validate_config(config)["repositories"])
        for role in ("", "Infra", "infra_ops", "1infra", "x" * 64, "infra\n"):
            config = deepcopy(self.config)
            config["repositories"][role] = {"path": "../extra"}
            with self.assertRaises(COORDINATE.CoordinationError):
                COORDINATE.validate_config(config)
        with self.assertRaises(COORDINATE.CoordinationError):
            COORDINATE.validate_config({**self.config, "version": True})


if __name__ == "__main__":
    unittest.main()
