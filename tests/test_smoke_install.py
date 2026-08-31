from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.dont_write_bytecode = True
sys.path.insert(0, str(SCRIPTS))

from smoke_install import SmokeError, catalog_skills, verify_installation  # noqa: E402
import smoke_install  # noqa: E402


class SmokeInstallTests(unittest.TestCase):
    def test_consumer_smoke_bootstraps_installed_policy_after_verification(self) -> None:
        real_run = subprocess.run
        for agent in smoke_install.SUPPORTED_AGENTS:
            with self.subTest(agent=agent), tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / "source"
                name = "synchronize-git-repositories"
                shutil.copytree(SCRIPTS.parent / "skills" / name, source / "skills" / name)
                (source / "skill-catalog.json").write_text(
                    json.dumps({"skills": [{"name": name}]}), encoding="utf-8"
                )
                events = []

                def run(argv, **kwargs):
                    project = Path(kwargs["cwd"])
                    if argv[0] == "fixture-npx":
                        shutil.copytree(source / "skills" / name, project / smoke_install.AGENT_LAYOUTS[agent] / name)
                        (project / "skills-lock.json").write_text(
                            json.dumps({"skills": {name: {"computedHash": "0" * 64}}}), encoding="utf-8"
                        )
                        other_file = "CLAUDE.md" if agent == "codex" else "AGENTS.md"
                        (project / other_file).write_bytes(b"Custom other-agent rules\r\n")
                        events.append("install")
                        return subprocess.CompletedProcess(argv, 0, "installed", "")
                    self.assertIn("verify", events)
                    events.append("apply" if "--apply" in argv else "plan")
                    self.assertEqual("bootstrap", argv[2])
                    self.assertEqual(agent, argv[argv.index("--agent") + 1])
                    self.assertIn(str(project / smoke_install.AGENT_LAYOUTS[agent]), argv[1])
                    return real_run(argv, **kwargs)

                def verified(*args, **kwargs):
                    verify_installation(*args, **kwargs)
                    events.append("verify")

                with patch.object(smoke_install.subprocess, "run", side_effect=run), patch.object(
                    smoke_install, "verify_installation", side_effect=verified
                ):
                    self.assertEqual(0, smoke_install.run_smoke(source, "fixture-npx", "1.5.22", 30, agent))
                self.assertEqual(["install", "verify", "plan", "apply", "apply"], events)

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

    def test_verifies_claude_code_layout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source, project = self.make_fixture(Path(directory))
            installed = project / ".agents/skills/demo"
            claude = project / ".claude/skills/demo"
            claude.parent.mkdir(parents=True)
            installed.rename(claude)
            verify_installation(source, project, ["demo"], "claude-code")


if __name__ == "__main__":
    unittest.main()
