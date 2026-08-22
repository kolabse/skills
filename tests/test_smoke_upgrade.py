from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.dont_write_bytecode = True
sys.path.insert(0, str(SCRIPTS))

from smoke_upgrade import UpgradeError, verify_updated_installation  # noqa: E402


class SmokeUpgradeTests(unittest.TestCase):
    def test_verifies_only_skills_present_in_baseline_installation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            project = root / "project"
            installed = project / ".agents/skills"
            for name in ("existing", "new-skill"):
                skill = source / "skills" / name
                skill.mkdir(parents=True)
                (skill / "SKILL.md").write_text(name + "\n", encoding="utf-8")
            copied = installed / "existing"
            copied.mkdir(parents=True)
            (copied / "SKILL.md").write_text("existing\n", encoding="utf-8")
            digest = hashlib.sha256(b"fixture").hexdigest()
            (project / "skills-lock.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "skills": {
                            "existing": {"computedHash": digest},
                        },
                    }
                ),
                encoding="utf-8",
            )

            verify_updated_installation(source, project, ["existing"])
            with self.assertRaisesRegex(UpgradeError, "new-skill"):
                verify_updated_installation(
                    source, project, ["existing", "new-skill"]
                )

    def test_verifies_claude_code_layout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            project = root / "project"
            skill = source / "skills/existing"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("existing\n", encoding="utf-8")
            installed = project / ".claude/skills/existing"
            installed.mkdir(parents=True)
            (installed / "SKILL.md").write_text("existing\n", encoding="utf-8")
            (project / "skills-lock.json").write_text(
                json.dumps({"skills": {"existing": {"computedHash": "0" * 64}}}),
                encoding="utf-8",
            )
            verify_updated_installation(
                source, project, ["existing"], "claude-code"
            )


if __name__ == "__main__":
    unittest.main()
