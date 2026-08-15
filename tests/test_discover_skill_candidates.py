from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIRECTORY = ROOT / "skills" / "discover-skill-candidates" / "scripts"
sys.path.insert(0, str(SCRIPT_DIRECTORY))

import discover_candidates  # noqa: E402


def git(path: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def initialize_project(path: Path, rules: str) -> None:
    path.mkdir(parents=True)
    git(path, "init", "-q")
    git(path, "config", "user.name", "Candidate Tests")
    git(path, "config", "user.email", "candidates@example.invalid")
    (path / "AGENTS.md").write_text(rules, encoding="utf-8")
    git(path, "add", "AGENTS.md")
    git(path, "commit", "-qm", "rules")


def candidate(block_ids: list[str], **overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "name": "verify-deployment-context",
        "title": "Verify deployment context",
        "summary": "Verify repository account and target identities before deployment execution.",
        "source_block_ids": block_ids,
        "triggers": [
            "Verify the deployment target before release.",
            "Check whether this environment is safe to deploy.",
        ],
        "workflow_steps": [
            "Resolve the declared repository.",
            "Resolve the active account.",
            "Resolve the target environment.",
            "Compare every identity.",
            "Block or report success.",
        ],
        "completion_criteria": [
            "Every identity agrees.",
            "A mismatch blocks execution.",
        ],
        "safety_boundaries": [
            "Never change an active account during inspection.",
            "Never deploy as part of discovery.",
        ],
        "resources": ["script", "reference"],
        "scope": "cross-project",
        "stability": "stable",
        "automation": "deterministic",
        "disqualifiers": [],
        "existing_skill_notes": [],
    }
    value.update(overrides)
    return value


def contribution_details(block_ids: list[str], **overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "evidence_summaries": [
            {
                "block_id": block_id,
                "summary": "A reusable rule requires deployment identities to agree.",
            }
            for block_id in block_ids
        ],
        "examples": [
            {
                "prompt": "Verify this deployment context before release.",
                "expected_outcomes": [
                    "Every declared identity is inspected.",
                    "Any mismatch blocks execution.",
                ],
            }
        ],
        "proposed_tests": [
            "Accept matching repository account and environment identities.",
            "Reject a mismatched target environment.",
        ],
        "known_limitations": [],
        "attestations": {
            "right_to_share": True,
            "apache_2_0": True,
            "no_secrets": True,
            "no_confidential_information": True,
        },
    }
    value.update(overrides)
    return value


class DiscoverSkillCandidatesTests(unittest.TestCase):
    def inventory(self, project: Path) -> dict[str, object]:
        return discover_candidates.inventory(
            project.resolve(), set(discover_candidates.DEFAULT_EXCLUDED_DIRECTORIES)
        )

    @staticmethod
    def block_ids(inventory: dict[str, object]) -> list[str]:
        return [
            block["block_id"]
            for file in inventory["files"]
            for block in file["blocks"]
        ]

    def test_inventory_is_read_only_and_records_git_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            initialize_project(
                project,
                "# Deployment verification\n\nResolve the target and compare identities.\n",
            )
            before = git(project, "status", "--porcelain=v1", "--untracked-files=all")

            result = self.inventory(project)

            after = git(project, "status", "--porcelain=v1", "--untracked-files=all")
            self.assertEqual(before, after)
            self.assertTrue(result["read_only"])
            self.assertEqual(1, result["rule_file_count"])
            rule = result["files"][0]
            self.assertTrue(rule["git"]["tracked"])
            self.assertFalse(rule["git"]["modified"])
            self.assertTrue(rule["git"]["blob_oid"])

    def test_managed_blocks_and_skill_references_stay_together(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            initialize_project(
                project,
                "<!-- demo:start -->\n## Demo\n\nUse `$existing-skill` before work.\n<!-- demo:end -->\n",
            )

            first = self.inventory(project)
            second = self.inventory(project)

            self.assertEqual(1, first["block_count"])
            self.assertEqual(first["inventory_sha256"], second["inventory_sha256"])
            block = first["files"][0]["blocks"][0]
            self.assertEqual(["existing-skill"], block["skill_references"])
            self.assertEqual(1, block["start_line"])
            self.assertEqual(5, block["end_line"])

    def test_nested_rules_are_scoped_and_vendored_directories_are_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            initialize_project(project, "# Root\n\nRoot workflow.\n")
            nested = project / "services" / "api"
            nested.mkdir(parents=True)
            (nested / "AGENTS.md").write_text("# API\n\nAPI workflow.\n", encoding="utf-8")
            vendored = project / "node_modules" / "package"
            vendored.mkdir(parents=True)
            (vendored / "AGENTS.md").write_text("# Ignore\n", encoding="utf-8")

            result = self.inventory(project)

            paths = [item["path"] for item in result["files"]]
            self.assertEqual(["AGENTS.md", "services/api/AGENTS.md"], paths)
            self.assertEqual("subtree:services/api", result["files"][1]["scope"])

    def test_secret_bearing_rule_is_rejected_without_text_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            initialize_project(project, "# Credentials\n\napi_key=abcdefgh12345678\n")

            with self.assertRaisesRegex(discover_candidates.DiscoveryError, "Possible secret"):
                self.inventory(project)

    def test_strong_multi_block_candidate_is_recommended(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            initialize_project(
                project,
                "# Before deployment\n\nResolve repository and account identities.\n\n"
                "# Validation\n\nCompare target context and fail closed on mismatch.\n",
            )
            rules = self.inventory(project)
            candidates = discover_candidates.normalize_candidate_input(
                {"candidates": [candidate(self.block_ids(rules))]},
                set(self.block_ids(rules)),
            )

            report = discover_candidates.score_candidates(candidates, rules, [])

            item = report["candidates"][0]
            self.assertEqual("recommended", item["classification"])
            self.assertGreaterEqual(item["score"], 13)
            self.assertEqual(2, len(item["source_evidence"]))
            self.assertNotIn("text", item["source_evidence"][0])

    def test_single_source_is_investigate_even_with_high_raw_score(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            initialize_project(project, "# Deployment\n\nVerify all identities before deployment.\n")
            rules = self.inventory(project)
            ids = self.block_ids(rules)
            candidates = discover_candidates.normalize_candidate_input(
                {"candidates": [candidate(ids)]}, set(ids)
            )

            report = discover_candidates.score_candidates(candidates, rules, [])

            item = report["candidates"][0]
            self.assertEqual("investigate", item["classification"])
            self.assertIn("single-source-block", item["review_flags"])

    def test_existing_skill_and_policy_candidate_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            initialize_project(
                project,
                "# One\n\nVerify identities.\n\n# Two\n\nFail closed.\n",
            )
            rules = self.inventory(project)
            ids = self.block_ids(rules)
            values = {
                "candidates": [
                    candidate(ids),
                    candidate(
                        ids,
                        name="organization-access-policy",
                        title="Organization access policy",
                        disqualifiers=["policy-only"],
                    ),
                ]
            }
            candidates = discover_candidates.normalize_candidate_input(values, set(ids))
            catalog = [
                {
                    "name": "verify-deployment-context",
                    "provides": ["deployment-context-verification"],
                }
            ]

            report = discover_candidates.score_candidates(candidates, rules, catalog)
            by_name = {item["name"]: item for item in report["candidates"]}

            self.assertEqual("reject", by_name["verify-deployment-context"]["classification"])
            self.assertIn(
                "identical-existing-skill",
                by_name["verify-deployment-context"]["rejection_reasons"],
            )
            self.assertEqual("reject", by_name["organization-access-policy"]["classification"])
            self.assertIn("policy-only", by_name["organization-access-policy"]["rejection_reasons"])

    def test_semantically_duplicate_candidate_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            initialize_project(
                project,
                "# One\n\nVerify identities.\n\n# Two\n\nFail closed.\n",
            )
            rules = self.inventory(project)
            ids = self.block_ids(rules)
            duplicate = candidate(
                ids,
                name="verify-deployment-identities",
                title="Verify deployment identities",
            )
            candidates = discover_candidates.normalize_candidate_input(
                {"candidates": [candidate(ids), duplicate]}, set(ids)
            )

            report = discover_candidates.score_candidates(candidates, rules, [])
            by_name = {item["name"]: item for item in report["candidates"]}

            self.assertEqual("reject", by_name["verify-deployment-identities"]["classification"])
            self.assertTrue(
                any(
                    reason.startswith("duplicate-candidate:")
                    for reason in by_name["verify-deployment-identities"]["rejection_reasons"]
                )
            )

    def test_changed_rule_invalidates_candidate_source_reference(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            initialize_project(project, "# Deployment\n\nVerify identities.\n")
            first = self.inventory(project)
            old_ids = self.block_ids(first)
            (project / "AGENTS.md").write_text(
                "# Deployment\n\nVerify identities and regions.\n", encoding="utf-8"
            )
            current = self.inventory(project)
            current_ids = set(self.block_ids(current))

            with self.assertRaisesRegex(discover_candidates.DiscoveryError, "unknown current blocks"):
                discover_candidates.normalize_candidate_input(
                    {"candidates": [candidate(old_ids)]}, current_ids
                )

    def test_default_catalog_is_loaded_and_deduplicated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            initialize_project(project, "# Rules\n\nDo work.\n")
            (project / "skill-catalog.json").write_text(
                json.dumps(
                    {
                        "skills": [
                            {"name": "demo-skill", "provides": ["demo"]},
                            {"name": "demo-skill", "provides": ["demo"]},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            loaded = discover_candidates.load_catalogs(project.resolve(), [])

            self.assertEqual([{"name": "demo-skill", "provides": ["demo"]}], loaded)

    def test_contribution_export_is_portable_and_independently_validated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            initialize_project(
                project,
                "# Deployment\n\nVerify private workstation identities before release.\n",
            )
            rules = self.inventory(project)
            ids = self.block_ids(rules)
            report = discover_candidates.score_candidates(
                discover_candidates.normalize_candidate_input(
                    {"candidates": [candidate(ids)]}, set(ids)
                ),
                rules,
                [],
            )

            package = discover_candidates.export_contribution(
                report, contribution_details(ids), "verify-deployment-context"
            )
            validation = discover_candidates.validate_contribution(package)

            self.assertTrue(validation["valid"])
            self.assertEqual(package["package_sha256"], validation["package_sha256"])
            serialized = json.dumps(package)
            self.assertNotIn(str(project), serialized)
            self.assertNotIn("AGENTS.md", serialized)
            self.assertNotIn("private workstation", serialized)
            self.assertEqual("Apache-2.0", package["license"])

    def test_contribution_export_requires_all_attestations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            initialize_project(project, "# Deployment\n\nVerify identities.\n")
            rules = self.inventory(project)
            ids = self.block_ids(rules)
            report = discover_candidates.score_candidates(
                discover_candidates.normalize_candidate_input(
                    {"candidates": [candidate(ids)]}, set(ids)
                ),
                rules,
                [],
            )
            details = contribution_details(ids)
            details["attestations"]["right_to_share"] = False

            with self.assertRaisesRegex(
                discover_candidates.DiscoveryError, "attestation"
            ):
                discover_candidates.export_contribution(
                    report, details, "verify-deployment-context"
                )

    def test_contribution_export_rejects_nonportable_details(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            initialize_project(project, "# Deployment\n\nVerify identities.\n")
            rules = self.inventory(project)
            ids = self.block_ids(rules)
            report = discover_candidates.score_candidates(
                discover_candidates.normalize_candidate_input(
                    {"candidates": [candidate(ids)]}, set(ids)
                ),
                rules,
                [],
            )
            details = contribution_details(ids)
            details["evidence_summaries"][0]["summary"] = (
                "See https://internal.example.invalid/runbook"
            )

            with self.assertRaisesRegex(
                discover_candidates.DiscoveryError, "URL"
            ):
                discover_candidates.export_contribution(
                    report, details, "verify-deployment-context"
                )

    def test_contribution_validation_rejects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            initialize_project(project, "# Deployment\n\nVerify identities.\n")
            rules = self.inventory(project)
            ids = self.block_ids(rules)
            report = discover_candidates.score_candidates(
                discover_candidates.normalize_candidate_input(
                    {"candidates": [candidate(ids)]}, set(ids)
                ),
                rules,
                [],
            )
            package = discover_candidates.export_contribution(
                report, contribution_details(ids), "verify-deployment-context"
            )
            package["candidate"]["summary"] = "Changed after export."

            with self.assertRaisesRegex(
                discover_candidates.DiscoveryError, "digest"
            ):
                discover_candidates.validate_contribution(package)

    def test_contributor_package_validates_in_clean_maintainer_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contributor = root / "contributor"
            maintainer = root / "maintainer"
            maintainer.mkdir()
            initialize_project(
                contributor,
                "# Before release\n\nVerify identities.\n\n# On mismatch\n\nFail closed.\n",
            )
            rules = self.inventory(contributor)
            ids = self.block_ids(rules)
            report = discover_candidates.score_candidates(
                discover_candidates.normalize_candidate_input(
                    {"candidates": [candidate(ids)]}, set(ids)
                ),
                rules,
                [],
            )
            package = discover_candidates.export_contribution(
                report, contribution_details(ids), "verify-deployment-context"
            )
            transferred = maintainer / "contribution-package.json"
            transferred.write_text(json.dumps(package), encoding="utf-8")

            validation = discover_candidates.validate_contribution(
                json.loads(transferred.read_text(encoding="utf-8"))
            )

            self.assertTrue(validation["valid"])
            self.assertFalse((maintainer / "AGENTS.md").exists())
            self.assertNotIn(str(contributor), transferred.read_text(encoding="utf-8"))

    def test_explicit_output_is_written_and_cannot_mutate_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            output = root / "result.json"
            result = {"valid": True, "value": "portable"}

            discover_candidates.write_explicit_output(
                argparse.Namespace(output=str(output), project_path=str(project)),
                result,
            )

            self.assertEqual(result, json.loads(output.read_text(encoding="utf-8")))
            with self.assertRaisesRegex(
                discover_candidates.DiscoveryError, "outside the analyzed project"
            ):
                discover_candidates.write_explicit_output(
                    argparse.Namespace(
                        output=str(project / "result.json"),
                        project_path=str(project),
                    ),
                    result,
                )


if __name__ == "__main__":
    unittest.main()
