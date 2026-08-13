from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1] / "scripts"
sys.dont_write_bytecode = True
sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from validate_skills import validate  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
