from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1] / "scripts"
sys.dont_write_bytecode = True
sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from validate_skills import (  # noqa: E402
    canonical_digest,
    validate,
    validate_marketplace_manifests,
    validate_documentation,
    validate_publication_materials,
    validate_release_holdout,
)


class CollectionValidationTests(unittest.TestCase):
    def test_repository_is_valid(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        self.assertEqual([], validate(repository))

    def test_reports_skill_missing_from_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            skill = repository / "skills/demo-skill"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                "---\nname: demo-skill\ndescription: Demo workflow.\n---\n\n# Demo\n",
                encoding="utf-8",
            )
            (repository / "README.md").write_text(
                "### `demo-skill`\n", encoding="utf-8"
            )
            (repository / "skill-catalog.json").write_text(
                json.dumps(
                    {"schema_version": 1, "license": "Apache-2.0", "skills": []}
                ),
                encoding="utf-8",
            )
            (repository / "LICENSE").write_text("test license\n", encoding="utf-8")

            errors = validate(repository)

            self.assertTrue(
                any("skill 'demo-skill' is missing from the catalog" in error for error in errors)
            )

    def test_reports_missing_plugin_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)

            errors = validate(repository)

            self.assertTrue(
                any("required plugin manifest is missing" in error for error in errors)
            )

    def test_reports_missing_marketplace_manifests(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)

            errors = validate_marketplace_manifests(repository)

            self.assertTrue(
                any("Codex marketplace manifest is missing" in error for error in errors)
            )
            self.assertTrue(
                any(
                    "Claude Code marketplace manifest is missing" in error
                    for error in errors
                )
            )

    def test_reports_noncanonical_marketplace_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            codex_marketplace = repository / ".agents/plugins/marketplace.json"
            claude_marketplace = repository / ".claude-plugin/marketplace.json"
            codex_marketplace.parent.mkdir(parents=True)
            claude_marketplace.parent.mkdir(parents=True)
            codex_marketplace.write_text(
                json.dumps(
                    {
                        "name": "kolabse",
                        "interface": {"displayName": "kolabse"},
                        "plugins": [
                            {
                                "name": "kolabse-skills",
                                "source": {
                                    "source": "url",
                                    "url": "https://example.test/skills.git",
                                    "ref": "main",
                                },
                                "policy": {
                                    "installation": "AVAILABLE",
                                    "authentication": "ON_INSTALL",
                                },
                                "category": "Developer Tools",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            claude_marketplace.write_text(
                json.dumps(
                    {
                        "name": "kolabse",
                        "owner": {"name": "kolabse"},
                        "plugins": [
                            {
                                "name": "kolabse-skills",
                                "source": {
                                    "source": "github",
                                    "repo": "someone/else",
                                    "ref": "main",
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            errors = validate_marketplace_manifests(repository)

            self.assertTrue(any("canonical Git URL" in error for error in errors))
            self.assertTrue(
                any("canonical GitHub repository" in error for error in errors)
            )

    def test_publication_materials_reject_incomplete_submission_cases(self) -> None:
        source = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            for name in ("PRIVACY.md", "TERMS.md", "SUPPORT.md"):
                shutil.copy2(source / name, repository / name)
            shutil.copytree(source / "assets", repository / "assets")
            submission_directory = repository / "docs/marketplace-submissions"
            submission_directory.parent.mkdir(parents=True)
            shutil.copytree(
                source / "docs/marketplace-submissions", submission_directory
            )
            submission_path = submission_directory / "openai-submission.json"
            submission = json.loads(submission_path.read_text(encoding="utf-8"))
            del submission["positive_test_cases"][0]["expected_result"]
            submission_path.write_text(json.dumps(submission), encoding="utf-8")

            errors = validate_publication_materials(repository)

            self.assertTrue(any("expected_result is required" in error for error in errors))

    def test_reports_invalid_catalog_root_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            skill = repository / "skills/demo-skill"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                "---\nname: demo-skill\ndescription: Demo workflow.\n---\n\n# Demo\n",
                encoding="utf-8",
            )
            (repository / "README.md").write_text(
                "### `demo-skill`\n", encoding="utf-8"
            )
            (repository / "skill-catalog.json").write_text("[]\n", encoding="utf-8")

            errors = validate(repository)

            self.assertTrue(any("catalog root must be an object" in error for error in errors))

    def test_reports_missing_trigger_eval_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            skill = repository / "skills/demo-skill"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                "---\nname: demo-skill\ndescription: Demo workflow.\n---\n\n# Demo\n",
                encoding="utf-8",
            )
            (repository / "README.md").write_text(
                "### `demo-skill`\n", encoding="utf-8"
            )
            (repository / "LICENSE").write_text("test license\n", encoding="utf-8")
            catalog = {
                "schema_version": 1,
                "license": "Apache-2.0",
                "skills": [
                    {
                        "name": "demo-skill",
                        "path": "skills/demo-skill",
                        "status": "experimental",
                        "maintainers": ["@owner"],
                        "platforms": ["linux"],
                        "license": "Apache-2.0",
                        "trigger_evals": "evals/demo-skill.json",
                        "provenance": {
                            "kind": "original",
                            "source": "this repository",
                            "canonical_repository": "https://example.test/skills",
                        },
                    }
                ],
            }
            (repository / "skill-catalog.json").write_text(
                json.dumps(catalog), encoding="utf-8"
            )

            errors = validate(repository)

            self.assertTrue(any("trigger eval file is missing" in error for error in errors))

    def test_release_holdout_digest_is_locked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            (repository / "evals").mkdir()
            data = {
                "schema_version": 1,
                "name": "release-holdout-v1",
                "skills": {
                    "demo-skill": {
                        "positive": [
                            {"prompt": "p1", "reason": "r"},
                            {"prompt": "p2", "reason": "r"},
                        ],
                        "negative": [
                            {"prompt": "n1", "reason": "r"},
                            {"prompt": "n2", "reason": "r"},
                        ],
                    }
                },
            }
            path = repository / "evals/release-holdout-v1.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            assertions = []
            for branch, expected in (("positive", True), ("negative", False)):
                for case in data["skills"]["demo-skill"][branch]:
                    prompt = case["prompt"]
                    identifier = hashlib.sha256(
                        f"demo-skill\0{branch}\0{prompt}".encode()
                    ).hexdigest()[:16]
                    assertions.append(
                        {
                            "id": identifier,
                            "prompt": prompt,
                            "target_skill": "demo-skill",
                            "expected": expected,
                        }
                    )
            assertion_digest = canonical_digest(
                sorted(assertions, key=lambda item: item["id"])
            )
            baseline_path = (
                repository / "evals/baselines/release-holdout-v1-v1.0.0.json"
            )
            baseline_path.parent.mkdir()
            baseline_path.write_text(
                json.dumps(
                    {
                        "assertion_digest": assertion_digest,
                        "selector": {"method": "majority-vote", "run_count": 3},
                    }
                ),
                encoding="utf-8",
            )
            catalog = {
                "release_holdout": {
                    "name": "release-holdout-v1",
                    "path": "evals/release-holdout-v1.json",
                    "sha256": canonical_digest(data),
                    "baseline_release": "v1.0.0",
                    "baseline_report": (
                        "evals/baselines/release-holdout-v1-v1.0.0.json"
                    ),
                }
            }
            self.assertEqual(
                [], validate_release_holdout(repository, catalog, {"demo-skill"})
            )
            data["skills"]["demo-skill"]["positive"][0]["prompt"] = "changed"
            path.write_text(json.dumps(data), encoding="utf-8")
            errors = validate_release_holdout(repository, catalog, {"demo-skill"})
            self.assertTrue(any("digest does not match" in error for error in errors))

    def test_documentation_requires_catalog_before_compositions_and_release_links(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            (repository / "README.md").write_text(
                "## Available skills\n\n## Supported compositions\n\n"
                "### `demo-skill`\n\n## Add a skill\n",
                encoding="utf-8",
            )
            (repository / "CHANGELOG.md").write_text(
                "## [1.2.3] - 2030-01-01\n", encoding="utf-8"
            )
            errors = validate_documentation(repository, {"demo-skill"})
            self.assertTrue(any("Supported compositions" in error for error in errors))
            self.assertTrue(any("1.2.3" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
