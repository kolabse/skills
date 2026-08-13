from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import manage_installed_skills as manager  # noqa: E402


class ManageInstalledSkillsTests(unittest.TestCase):
    def make_project(self, root: Path, versions: dict[str, str]) -> Path:
        project = root / "project"
        entries: dict[str, object] = {}
        for name, version in versions.items():
            skill = project / ".agents/skills" / name
            skill.mkdir(parents=True)
            (skill / "collection-metadata.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "collection": "kolabse-skills",
                        "version": version,
                        "skill": name,
                        "source": "https://github.com/kolabse/skills",
                    }
                ),
                encoding="utf-8",
            )
            entries[name] = {
                "source": "kolabse/skills",
                "computedHash": "0" * 64,
            }
        (project / "skills-lock.json").write_text(
            json.dumps({"version": 1, "skills": entries}), encoding="utf-8"
        )
        return project

    def test_status_reports_installed_collection_versions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = self.make_project(
                Path(directory), {"verify-before-push": "1.2.0"}
            )
            state = manager.read_project_state(project)
            self.assertEqual("1.2.0", state["skills"][0]["version"])
            self.assertTrue(state["skills"][0]["metadata_valid"])

    def test_doctor_rejects_mixed_versions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = self.make_project(
                Path(directory),
                {"verify-before-push": "1.2.0", "maintain-work-log": "1.1.0"},
            )
            state = manager.doctor(project)
            self.assertFalse(state["healthy"])
            self.assertTrue(any("mixed collection versions" in item for item in state["problems"]))

    def test_doctor_rejects_empty_collection_lock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "skills-lock.json").write_text(
                '{"version":1,"skills":{}}', encoding="utf-8"
            )
            state = manager.doctor(project)
            self.assertFalse(state["healthy"])
            self.assertIn("no kolabse skills were found in skills-lock.json", state["problems"])

    def test_update_delegates_to_pinned_cli_without_shell(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(
            shutil, "which", return_value="npx"
        ), patch.object(manager, "run_checked") as run:
            run.return_value.stdout = "updated"
            manager.update_skills(
                Path(directory),
                ["verify-before-push"],
                "project",
                "1.5.22",
                True,
                30,
            )
            command = run.call_args.args[0]
            self.assertEqual(
                ["npx", "--yes", "skills@1.5.22", "update", "verify-before-push", "-p", "-y"],
                command,
            )

    def test_migration_discovery_does_not_create_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = self.make_project(
                Path(directory), {"verify-before-push": "1.2.0"}
            )
            script = project / ".agents/skills/verify-before-push/scripts/verify_before_push.py"
            script.parent.mkdir()
            script.write_text("", encoding="utf-8")
            self.assertEqual([], manager.migration_commands(project, False))
            self.assertFalse((project / ".agents/verify-before-push").exists())


if __name__ == "__main__":
    unittest.main()
