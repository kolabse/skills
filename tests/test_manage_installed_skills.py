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
        project.mkdir(parents=True, exist_ok=True)
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
            run.return_value.stderr = ""
            project = self.make_project(
                Path(directory), {"verify-before-push": "1.2.0"}
            )
            manager.update_skills(
                project,
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

    def test_update_rejects_cli_noop_reported_with_zero_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(
            shutil, "which", return_value="npx"
        ), patch.object(manager, "run_checked") as run:
            run.return_value.stdout = "No installed skills found matching: verify-before-push"
            run.return_value.stderr = ""
            project = self.make_project(
                Path(directory), {"verify-before-push": "1.2.0"}
            )
            with self.assertRaisesRegex(manager.ManagerError, "did not update"):
                manager.update_skills(
                    project,
                    ["verify-before-push"],
                    "project",
                    "1.5.22",
                    True,
                    30,
                )

    def test_collection_update_does_not_select_unrelated_locked_skills(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(
            shutil, "which", return_value="npx"
        ), patch.object(manager, "run_checked") as run:
            run.return_value.stdout = "updated"
            run.return_value.stderr = ""
            project = self.make_project(
                Path(directory), {"verify-before-push": "1.2.0"}
            )
            lock_path = project / "skills-lock.json"
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            lock["skills"]["third-party-skill"] = {
                "source": "elsewhere/skills",
                "computedHash": "1" * 64,
            }
            lock_path.write_text(json.dumps(lock), encoding="utf-8")

            manager.update_skills(project, [], "project", "1.5.22", True, 30)

            command = run.call_args.args[0]
            self.assertIn("verify-before-push", command)
            self.assertNotIn("third-party-skill", command)

    def test_global_update_requires_explicit_collection_skills(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(manager.ManagerError, "explicit skill names"):
                manager.resolve_update_selection(Path(directory), [], "global")

    def test_project_update_rejects_skill_missing_from_lock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = self.make_project(Path(directory), {})
            with self.assertRaisesRegex(manager.ManagerError, "not present"):
                manager.resolve_update_selection(
                    project, ["verify-before-push"], "project"
                )

    def test_update_fails_when_post_update_doctor_is_unhealthy(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(
            shutil, "which", return_value="npx"
        ), patch.object(manager, "run_checked") as run:
            run.return_value.stdout = "updated"
            run.return_value.stderr = ""
            project = self.make_project(
                Path(directory), {"verify-before-push": "1.2.0"}
            )
            (project / ".agents/skills/verify-before-push/collection-metadata.json").unlink()
            with self.assertRaisesRegex(manager.ManagerError, "post-update diagnosis failed"):
                manager.update_skills(
                    project,
                    ["verify-before-push"],
                    "project",
                    "1.5.22",
                    True,
                    30,
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
