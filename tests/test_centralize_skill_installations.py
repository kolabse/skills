from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/centralize_skill_installations.py"
SPEC = importlib.util.spec_from_file_location("centralize_skill_installations", SCRIPT)
assert SPEC and SPEC.loader
centralize = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(centralize)


class CentralizeSkillInstallationsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.project = self.base / "project"
        self.home = self.base / "home"
        self.local = self.base / "local"
        self.project.mkdir()
        self.home.mkdir()
        self.local.mkdir()
        self.name = "verify-before-push"
        self.project_skill = self.project / ".agents/skills" / self.name
        self.project_skill.mkdir(parents=True)
        self.write_skill(self.project_skill, "1.20.0")
        self.write_project_lock()
        config = self.project / ".agents/verify-before-push/config.json"
        config.parent.mkdir(parents=True)
        config.write_text('{"version": 1}', encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_skill(self, path: Path, version: str) -> None:
        metadata = {
            "schema_version": 2,
            "collection": "kolabse-skills",
            "version": version,
            "skill": path.name,
            "source": "https://github.com/kolabse/skills",
            "canonical_repository": "https://github.com/kolabse/skills",
        }
        (path / "collection-metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        (path / "SKILL.md").write_text("fixture", encoding="utf-8")

    def write_project_lock(self) -> None:
        lock = {
            "version": 1,
            "skills": {
                self.name: {
                    "source": "kolabse/skills",
                    "sourceType": "github",
                    "computedHash": centralize.folder_hash(self.project_skill),
                },
                "unrelated-skill": {"source": "example/skills", "computedHash": "x" * 64},
            },
        }
        (self.project / "skills-lock.json").write_text(json.dumps(lock), encoding="utf-8")

    def make_plan(self):
        with mock.patch.object(centralize.Path, "home", return_value=self.home):
            return centralize.make_plan(self.project, ROOT)

    def test_plan_reports_notice_and_global_installer(self) -> None:
        plan = self.make_plan()
        self.assertTrue(plan["user_notice_required"])
        self.assertEqual([], plan["blockers"])
        self.assertIn("--global", plan["installers"][0]["argv"])
        self.assertEqual([self.name], plan["installers"][0]["skills"])
        self.assertTrue((self.project / ".agents/verify-before-push/config.json").is_file())

    def test_plan_blocks_unverified_project_copy(self) -> None:
        (self.project_skill / "tampered.txt").write_text("changed", encoding="utf-8")
        plan = self.make_plan()
        self.assertIn("codex:verify-before-push:unverified", plan["blockers"])

    def test_existing_backup_stops_before_global_installation(self) -> None:
        plan = self.make_plan()
        backup = self.local / "existing"
        backup.mkdir()
        with mock.patch.object(centralize.Path, "home", return_value=self.home), mock.patch.object(
            centralize, "backup_root", return_value=backup
        ), mock.patch.object(centralize.shutil, "which", return_value="npx"), mock.patch.object(
            centralize.subprocess, "run"
        ) as run:
            with self.assertRaisesRegex(centralize.CentralizeError, "backup already exists"):
                centralize.apply_plan(self.project, ROOT, plan["plan_sha256"], True)
        run.assert_not_called()

    def test_apply_verifies_global_copy_backs_up_and_preserves_configuration(self) -> None:
        plan = self.make_plan()

        def fake_run(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            global_skill = self.home / ".agents/skills" / self.name
            global_skill.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(ROOT / "skills" / self.name, global_skill)
            metadata = json.loads((global_skill / "collection-metadata.json").read_text(encoding="utf-8"))
            metadata["version"] = "1.20.0"
            (global_skill / "collection-metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
            lock = {
                "version": 3,
                "skills": {
                    self.name: {
                        "source": "kolabse/skills",
                        "skillFolderHash": centralize.folder_hash(global_skill),
                    }
                },
            }
            (self.home / ".agents/.skill-lock.json").write_text(json.dumps(lock), encoding="utf-8")
            return subprocess.CompletedProcess(argv, 0, "", "")

        with mock.patch.object(centralize.Path, "home", return_value=self.home), mock.patch.dict(
            centralize.os.environ, {"LOCALAPPDATA": str(self.local)}
        ), mock.patch.object(centralize.shutil, "which", return_value="npx"), mock.patch.object(
            centralize.subprocess, "run", side_effect=fake_run
        ):
            result = centralize.apply_plan(self.project, ROOT, plan["plan_sha256"], True)

        self.assertTrue(result["changed"])
        self.assertFalse(self.project_skill.exists())
        self.assertTrue((self.project / ".agents/verify-before-push/config.json").is_file())
        lock = json.loads((self.project / "skills-lock.json").read_text(encoding="utf-8"))
        self.assertNotIn(self.name, lock["skills"])
        self.assertIn("unrelated-skill", lock["skills"])
        self.assertTrue(Path(result["backup"]).is_dir())


if __name__ == "__main__":
    unittest.main()
