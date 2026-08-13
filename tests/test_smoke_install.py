from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.dont_write_bytecode = True
sys.path.insert(0, str(SCRIPTS))

from smoke_install import SmokeError, catalog_skills, verify_installation  # noqa: E402


class SmokeInstallTests(unittest.TestCase):
    def make_fixture(self, root: Path) -> tuple[Path, Path]:
        source = root / "source"
        project = root / "project"
        skill = source / "skills/demo/scripts"
        skill.mkdir(parents=True)
        (source / "skills/demo/SKILL.md").write_text("# Demo\n", encoding="utf-8")
        (skill / "helper.py").write_text("print('demo')\n", encoding="utf-8")
        (source / "skill-catalog.json").write_text(
            json.dumps({"skills": [{"name": "demo"}]}), encoding="utf-8"
        )
        installed = project / ".agents/skills/demo"
        shutil.copytree(source / "skills/demo", installed)
        (project / "skills-lock.json").write_text(
            json.dumps({"skills": {"demo": {"computedHash": "0" * 64}}}),
            encoding="utf-8",
        )
        return source, project

    def test_verifies_exact_copied_installation_and_lock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source, project = self.make_fixture(Path(directory))
            self.assertEqual(["demo"], catalog_skills(source))
            verify_installation(source, project, ["demo"])

    def test_rejects_changed_installed_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source, project = self.make_fixture(Path(directory))
            (project / ".agents/skills/demo/SKILL.md").write_text(
                "# Changed\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(SmokeError, "changed=.*SKILL.md"):
                verify_installation(source, project, ["demo"])

    def test_rejects_missing_lock_entry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source, project = self.make_fixture(Path(directory))
            (project / "skills-lock.json").write_text(
                json.dumps({"skills": {}}), encoding="utf-8"
            )
            with self.assertRaisesRegex(SmokeError, "lock does not contain"):
                verify_installation(source, project, ["demo"])


if __name__ == "__main__":
    unittest.main()
