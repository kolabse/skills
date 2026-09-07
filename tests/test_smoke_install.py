from __future__ import annotations

import json
import os
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
    def test_global_rejects_root_symlink_metadata_before_manifest_comparison(self) -> None:
        for linked_root in ("skill", "skills"):
            with self.subTest(linked_root=linked_root), tempfile.TemporaryDirectory() as directory:
                source, project = self.make_fixture(Path(directory))
                root = project / ".agents/skills"
                link = root / "demo" if linked_root == "skill" else root
                original = Path.is_symlink
                with patch.object(Path, "is_symlink", lambda path: path == link or original(path)):
                    with self.assertRaisesRegex(SmokeError, "copied, not linked"):
                        verify_installation(source, project, ["demo"], scope="global")

    def test_global_rejects_linked_installation_roots(self) -> None:
        for linked_root in ("skill", "skills"):
            with self.subTest(linked_root=linked_root), tempfile.TemporaryDirectory() as directory:
                source, project = self.make_fixture(Path(directory))
                root = project / ".agents/skills"
                link = root / "demo" if linked_root == "skill" else root
                target = source / "skills/demo" if linked_root == "skill" else source / "skills"
                shutil.rmtree(link)
                try:
                    link.symlink_to(target, target_is_directory=True)
                except OSError as error:
                    self.skipTest(f"Directory symlinks unavailable: {error}")
                with self.assertRaisesRegex(SmokeError, "copied, not linked"):
                    verify_installation(source, project, ["demo"], scope="global")

    def test_cli_resolves_npx_before_global_child_environment(self) -> None:
        before = dict(os.environ)
        events = []
        def resolve(name):
            self.assertEqual("npx", name)
            self.assertEqual(before, dict(os.environ))
            events.append("resolve")
            return "resolved-npx"
        def run(source, npx, version, timeout, agent, *, scope):
            self.assertEqual(["resolve"], events)
            self.assertEqual("resolved-npx", npx)
            self.assertEqual("global", scope)
            self.assertEqual(before, dict(os.environ))
            return 0
        with patch.object(smoke_install.shutil, "which", side_effect=resolve), patch.object(
            smoke_install, "run_smoke", side_effect=run
        ):
            self.assertEqual(0, smoke_install.main(["--scope", "global"]))

    def test_global_isolates_child_homes_and_preserves_parent_even_on_failure(self) -> None:
        keys = ("HOME", "USERPROFILE", "CODEX_HOME", "CLAUDE_CONFIG_DIR", "XDG_STATE_HOME")
        for agent in smoke_install.SUPPORTED_AGENTS:
            for failure in (False, True):
                with self.subTest(agent=agent, failure=failure), tempfile.TemporaryDirectory() as directory:
                    source, _ = self.make_fixture(Path(directory))
                    with patch.dict(os.environ, {key: str(Path(directory) / "poison" / key) for key in keys}):
                        before = dict(os.environ)
                        def install(argv, **kwargs):
                            self.assertIn("--global", argv)
                            self.assertIn("--copy", argv)
                            project = Path(kwargs["cwd"])
                            environment = kwargs["env"]
                            home = Path(environment["HOME"])
                            self.assertEqual(home, Path(environment["USERPROFILE"]))
                            self.assertNotEqual(project, home)
                            self.assertEqual(project.parent, home.parent)
                            for key in keys:
                                self.assertNotEqual(before[key], environment[key])
                                self.assertTrue(Path(environment[key]).is_relative_to(home))
                            self.assertEqual(home / ".codex", Path(environment["CODEX_HOME"]))
                            self.assertEqual(home / ".claude", Path(environment["CLAUDE_CONFIG_DIR"]))
                            self.assertEqual([], list(project.iterdir()))
                            self.assertEqual(before, dict(os.environ))
                            if failure:
                                raise subprocess.TimeoutExpired(argv, 30)
                            shutil.copytree(source / "skills/demo", home / smoke_install.AGENT_LAYOUTS[agent] / "demo")
                            return subprocess.CompletedProcess(argv, 0, "installed", "")
                        with patch.object(smoke_install.subprocess, "run", side_effect=install), patch.object(
                            smoke_install, "verify_git_policy_bootstrap"
                        ) as bootstrap:
                            if failure:
                                with self.assertRaises(subprocess.TimeoutExpired):
                                    smoke_install.run_smoke(source, "fixture-npx", "1.5.22", 30, agent, scope="global")
                            else:
                                self.assertEqual(0, smoke_install.run_smoke(source, "fixture-npx", "1.5.22", 30, agent, scope="global"))
                            bootstrap.assert_not_called()
                        self.assertEqual(before, dict(os.environ))

    def test_global_rejects_payload_differences_and_any_project_mutation(self) -> None:
        for agent in smoke_install.SUPPORTED_AGENTS:
            for defect in ("changed", "missing", "extra", "extra-skill", "project-file", "project-directory"):
                with self.subTest(agent=agent, defect=defect), tempfile.TemporaryDirectory() as directory:
                    source, _ = self.make_fixture(Path(directory))
                    def install(argv, **kwargs):
                        root = Path(kwargs["env"]["HOME"]) / smoke_install.AGENT_LAYOUTS[agent]
                        shutil.copytree(source / "skills/demo", root / "demo")
                        if defect == "changed":
                            (root / "demo/SKILL.md").write_text("wrong", encoding="utf-8")
                        elif defect == "missing":
                            (root / "demo/SKILL.md").unlink()
                        elif defect == "extra":
                            (root / "demo/extra.txt").write_text("extra", encoding="utf-8")
                        elif defect == "extra-skill":
                            (root / "extra").mkdir()
                        elif defect == "project-file":
                            (Path(kwargs["cwd"]) / "AGENTS.md").write_text("rules", encoding="utf-8")
                        else:
                            (Path(kwargs["cwd"]) / ".agents").mkdir()
                        return subprocess.CompletedProcess(argv, 0, "installed", "")
                    with patch.object(smoke_install.subprocess, "run", side_effect=install), patch.object(
                        smoke_install, "verify_git_policy_bootstrap"
                    ) as bootstrap:
                        with self.assertRaises(SmokeError):
                            smoke_install.run_smoke(source, "fixture-npx", "1.5.22", 30, agent, scope="global")
                        bootstrap.assert_not_called()

    def test_global_never_bootstraps_even_when_policy_skill_is_installed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source, _ = self.make_fixture(Path(directory))
            name = "synchronize-git-repositories"
            (source / "skills/demo").rename(source / "skills" / name)
            (source / "skill-catalog.json").write_text(json.dumps({"skills": [{"name": name}]}), encoding="utf-8")
            def install(argv, **kwargs):
                shutil.copytree(source / "skills" / name, Path(kwargs["env"]["HOME"]) / ".agents/skills" / name)
                return subprocess.CompletedProcess(argv, 0, "installed", "")
            with patch.object(smoke_install.subprocess, "run", side_effect=install), patch.object(
                smoke_install, "verify_git_policy_bootstrap"
            ) as bootstrap:
                smoke_install.run_smoke(source, "fixture-npx", "1.5.22", 30, scope="global")
                bootstrap.assert_not_called()

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
                        self.assertNotIn("--global", argv)
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
