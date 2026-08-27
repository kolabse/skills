from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import manage_installed_skills as manager  # noqa: E402


class ManageInstalledSkillsTests(unittest.TestCase):
    NEW_SKILLS = {
        "orchestrate-agent-work",
        "develop-with-test-first-evidence",
        "review-code-changes",
        "diagnose-software-defects",
        "resolve-git-conflicts",
        "execute-verified-development-lifecycle",
    }

    def test_known_skills_match_collection_catalog(self) -> None:
        catalog = json.loads((Path(__file__).resolve().parents[1] / "skill-catalog.json").read_text(encoding="utf-8"))
        self.assertEqual({item["name"] for item in catalog["skills"]}, manager.KNOWN_SKILLS)

    def test_new_issue_53_skills_are_managed(self) -> None:
        self.assertTrue(self.NEW_SKILLS <= manager.KNOWN_SKILLS)

    def test_coordinated_release_skills_are_managed(self) -> None:
        self.assertIn("coordinate-code-documentation-repositories", manager.KNOWN_SKILLS)
        self.assertIn("execute-configured-gitflow-releases", manager.KNOWN_SKILLS)

    def test_coordinated_release_configs_are_migration_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = self.make_project(root, {
                "coordinate-code-documentation-repositories": "1.13.0",
                "execute-configured-gitflow-releases": "1.13.0",
            })
            for name, script in (
                ("coordinate-code-documentation-repositories", "coordinate_change.py"),
                ("execute-configured-gitflow-releases", "gitflow_release.py"),
            ):
                config = project / ".agents" / name / "config.json"
                config.parent.mkdir(parents=True, exist_ok=True)
                config.write_text("{}\n", encoding="utf-8")
                helper = project / ".agents/skills" / name / "scripts" / script
                helper.parent.mkdir(parents=True, exist_ok=True)
                helper.write_text("# fixture\n", encoding="utf-8")

            names = [name for name, _ in manager.migration_commands(project, False)]
            self.assertEqual([
                "coordinate-code-documentation-repositories",
                "execute-configured-gitflow-releases",
            ], names)

    def test_verified_lifecycle_config_is_a_migration_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = self.make_project(Path(directory), {"execute-verified-development-lifecycle": "1.14.0"})
            config = project / ".agents/execute-verified-development-lifecycle/config.json"
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text("{}\n", encoding="utf-8")
            helper = project / ".agents/skills/execute-verified-development-lifecycle/scripts/development_lifecycle.py"
            helper.parent.mkdir(parents=True, exist_ok=True)
            helper.write_text("# fixture\n", encoding="utf-8")
            commands = dict(manager.migration_commands(project, False))
            self.assertIn("execute-verified-development-lifecycle", commands)
            self.assertEqual("migrate", commands["execute-verified-development-lifecycle"][2])

    def test_lifecycle_bootstrap_command_uses_installed_helper_and_shared_project_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = self.make_project(
                Path(directory), {"execute-verified-development-lifecycle": "1.18.1"}
            )
            helper = project / ".agents/skills/execute-verified-development-lifecycle/scripts/development_lifecycle.py"
            helper.parent.mkdir(parents=True)
            helper.write_text("# fixture\n", encoding="utf-8")

            commands = manager.lifecycle_bootstrap_commands(
                project, ["execute-verified-development-lifecycle"], "codex"
            )

            self.assertEqual(1, len(commands))
            name, command = commands[0]
            self.assertEqual("execute-verified-development-lifecycle", name)
            self.assertEqual("bootstrap", command[2])
            self.assertEqual(str(project.resolve()), command[command.index("--project-root") + 1])
            self.assertIn("--apply", command)
            self.assertIn("--yes", command)

    def test_lifecycle_bootstrap_is_not_planned_for_global_or_unselected_updates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = self.make_project(
                Path(directory), {"execute-verified-development-lifecycle": "1.18.1"}
            )
            self.assertEqual([], manager.lifecycle_bootstrap_commands(project, [], "codex"))

    def test_project_update_runs_lifecycle_bootstrap_after_skill_update(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(
            shutil, "which", return_value="npx"
        ), patch.object(manager, "run_checked") as run:
            project = self.make_project(
                Path(directory), {"execute-verified-development-lifecycle": "1.18.1"}
            )
            helper = project / ".agents/skills/execute-verified-development-lifecycle/scripts/development_lifecycle.py"
            helper.parent.mkdir(parents=True)
            helper.write_text("# fixture\n", encoding="utf-8")
            update_result = type("Result", (), {})()
            update_result.stdout = "unchanged"
            update_result.stderr = ""
            bootstrap_result = type("Result", (), {})()
            bootstrap_result.stdout = json.dumps(
                {"configured": True, "created": True, "ready": True}
            )
            bootstrap_result.stderr = ""
            run.side_effect = [update_result, bootstrap_result]

            report = manager.update_skills(
                project,
                ["execute-verified-development-lifecycle"],
                "project",
                "1.5.22",
                True,
                30,
            )

            self.assertEqual("update", run.call_args_list[0].args[0][3])
            self.assertEqual("bootstrap", run.call_args_list[1].args[0][2])
            self.assertEqual("created", report["configuration"][0]["status"])

    def make_project(
        self, root: Path, versions: dict[str, str], agent: str = "codex"
    ) -> Path:
        project = root / "project"
        project.mkdir(parents=True, exist_ok=True)
        layout = ".agents/skills" if agent == "codex" else ".claude/skills"
        entries: dict[str, object] = {}
        for name, version in versions.items():
            skill = project / layout / name
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
                "sourceType": "github",
                "computedHash": "0" * 64,
            }
        (project / "skills-lock.json").write_text(
            json.dumps({"version": 1, "skills": entries}), encoding="utf-8"
        )
        return project

    def make_global(
        self, root: Path, versions: dict[str, str], agent: str = "codex"
    ) -> Path:
        global_root = root / ".agents"
        installed_root = (
            global_root / "skills"
            if agent == "codex"
            else root / ".claude" / "skills"
        )
        entries: dict[str, object] = {}
        for name, version in versions.items():
            skill = installed_root / name
            skill.mkdir(parents=True)
            (skill / "collection-metadata.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "collection": "kolabse-skills",
                        "version": version,
                        "skill": name,
                        "source": "https://github.com/kolabse/skills",
                        "canonical_repository": "https://github.com/kolabse/skills",
                    }
                ),
                encoding="utf-8",
            )
            entries[name] = {
                "source": "kolabse/skills",
                "sourceType": "github",
                "skillFolderHash": "0" * 40,
            }
        global_root.mkdir(parents=True, exist_ok=True)
        (global_root / ".skill-lock.json").write_text(
            json.dumps({"version": 3, "skills": entries}), encoding="utf-8"
        )
        return global_root

    def test_status_reports_installed_collection_versions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = self.make_project(
                Path(directory), {"verify-before-push": "1.2.0"}
            )
            state = manager.read_project_state(project)
            self.assertEqual("1.2.0", state["skills"][0]["version"])
            self.assertTrue(state["skills"][0]["metadata_valid"])
            self.assertEqual("verified", state["skills"][0]["provenance_status"])

    def test_claude_code_status_uses_explicit_claude_layout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = self.make_project(
                Path(directory), {"verify-before-push": "1.14.1"}, "claude-code"
            )
            state = manager.read_project_state(project, agent="claude-code")
            self.assertEqual("claude-code", state["agent"])
            self.assertEqual(".claude/skills", state["layout"])
            self.assertTrue(state["skills"][0]["installed"])

            codex_state = manager.doctor(project)
            self.assertFalse(codex_state["healthy"])
            self.assertIn("locked but not installed", codex_state["problems"][0])

    def test_unknown_agent_is_rejected_without_layout_guessing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(manager.ManagerError, "unsupported agent"):
                manager.read_project_state(Path(directory), agent="claude")

    def test_github_source_variants_normalize_to_canonical_identity(self) -> None:
        variants = [
            "kolabse/skills",
            "kolabse/skills@v1.2.2",
            "https://github.com/kolabse/skills.git",
            "https://github.com/kolabse/skills/tree/v1.2.2",
            "git@github.com:kolabse/skills.git",
        ]
        for source in variants:
            with self.subTest(source=source):
                identity = manager.normalize_github_source(source)
                self.assertIsNotNone(identity)
                self.assertEqual(
                    "https://github.com/kolabse/skills",
                    identity["canonical_repository"],
                )

    def test_same_name_skill_from_another_source_is_a_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = self.make_project(
                Path(directory), {"verify-before-push": "1.2.2"}
            )
            lock_path = project / "skills-lock.json"
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            lock["skills"]["verify-before-push"]["source"] = "someone-else/skills"
            lock_path.write_text(json.dumps(lock), encoding="utf-8")
            state = manager.read_project_state(project)
            self.assertEqual("mismatch", state["skills"][0]["provenance_status"])
            with self.assertRaisesRegex(manager.ManagerError, "provenance mismatch"):
                manager.resolve_update_selection(project, [], "project")

    def test_renamed_local_checkout_is_verified_by_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = self.make_project(root, {"verify-before-push": "1.2.2"})
            checkout = root / "renamed-anything"
            (checkout / ".codex-plugin").mkdir(parents=True)
            (checkout / "skills/verify-before-push").mkdir(parents=True)
            (checkout / ".codex-plugin/plugin.json").write_text(
                json.dumps(
                    {
                        "name": "kolabse-skills",
                        "repository": "https://github.com/kolabse/skills",
                    }
                ),
                encoding="utf-8",
            )
            (checkout / "skill-catalog.json").write_text(
                json.dumps({"skills": [{"name": "verify-before-push"}]}),
                encoding="utf-8",
            )
            (checkout / "skills/verify-before-push/SKILL.md").write_text(
                "fixture", encoding="utf-8"
            )
            lock_path = project / "skills-lock.json"
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            lock["skills"]["verify-before-push"].update(
                {"source": str(checkout), "sourceType": "local"}
            )
            lock_path.write_text(json.dumps(lock), encoding="utf-8")
            state = manager.read_project_state(project)
            self.assertEqual("verified", state["skills"][0]["provenance_status"])
            self.assertEqual("local", state["skills"][0]["source_kind"])

    def test_legacy_install_requires_explicit_adoption(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = self.make_project(
                Path(directory), {"verify-before-push": "1.0.0"}
            )
            (project / ".agents/skills/verify-before-push/collection-metadata.json").unlink()
            state = manager.read_project_state(project)
            self.assertEqual("legacy-unverified", state["skills"][0]["provenance_status"])
            with self.assertRaisesRegex(manager.ManagerError, "--adopt-legacy"):
                manager.resolve_update_selection(project, [], "project")
            self.assertEqual(
                ["verify-before-push"],
                manager.resolve_update_selection(project, [], "project", True),
            )

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

    def test_deep_doctor_reports_unconfigured_runtime_without_failing_installation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = self.make_project(root, {"verify-before-push": "1.5.0"})
            skill = project / ".agents/skills/verify-before-push"
            (skill / "scripts").mkdir()
            (skill / "scripts/status.py").write_text(
                "import json; print(json.dumps({'configured': False, 'valid': True}))\n",
                encoding="utf-8",
            )
            (root / "skill-catalog.json").write_text(
                json.dumps(
                    {
                        "skills": [
                            {
                                "name": "verify-before-push",
                                "configuration": {
                                    "scope": "project",
                                    "status": ["python", "scripts/status.py"],
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            state = manager.doctor(project, deep=True, repository_root=root)

            self.assertTrue(state["healthy"])
            self.assertEqual("unconfigured", state["runtime_checks"][0]["status"])
            self.assertIn(
                "verify-before-push is installed but not configured", state["warnings"]
            )

    def test_deep_doctor_rejects_partial_runtime_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = self.make_project(root, {"verify-before-push": "1.5.0"})
            skill = project / ".agents/skills/verify-before-push"
            (skill / "scripts").mkdir()
            config = project / ".agents/verify-before-push/config.json"
            config.parent.mkdir(parents=True)
            config.write_text("{}", encoding="utf-8")
            (skill / "scripts/status.py").write_text(
                "import json,sys; print(json.dumps({'configured': False, 'valid': True, "
                "'config_file': sys.argv[1]})); raise SystemExit(1)\n",
                encoding="utf-8",
            )
            (root / "skill-catalog.json").write_text(
                json.dumps(
                    {
                        "skills": [
                            {
                                "name": "verify-before-push",
                                "configuration": {
                                    "scope": "project",
                                    "status": [
                                        "python",
                                        "scripts/status.py",
                                        str(config),
                                    ],
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            state = manager.doctor(project, deep=True, repository_root=root)

            self.assertFalse(state["healthy"])
            self.assertEqual("partial", state["runtime_checks"][0]["status"])
            self.assertTrue(any("partially configured" in item for item in state["problems"]))

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
                [
                    "npx", "--yes", "skills@1.5.22", "update",
                    "verify-before-push", "-p", "-y",
                ],
                command,
            )

    def test_claude_code_update_readds_to_verified_agent_layout(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(
            shutil, "which", return_value="npx"
        ), patch.object(manager, "run_checked") as run:
            run.return_value.stdout = "unchanged"
            run.return_value.stderr = ""
            project = self.make_project(
                Path(directory), {"verify-before-push": "1.14.1"}, "claude-code"
            )
            report = manager.update_skills(
                project,
                ["verify-before-push"],
                "project",
                "1.5.22",
                True,
                30,
                agent="claude-code",
            )
            command = run.call_args.args[0]
            self.assertEqual("add", command[3])
            self.assertEqual("claude-code", command[command.index("--agent") + 1])
            self.assertEqual("claude-code", report["agent"])
            self.assertEqual(".claude/skills", report["layout"])

    def test_update_targets_selected_agent_when_skill_is_in_both_layouts(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(
            manager, "run_checked"
        ) as run:
            project = self.make_project(
                Path(directory), {"verify-before-push": "1.14.1"}, "claude-code"
            )
            codex_copy = project / ".agents/skills/verify-before-push"
            shutil.copytree(project / ".claude/skills/verify-before-push", codex_copy)
            run.return_value.stdout = "unchanged"
            run.return_value.stderr = ""

            manager.update_skills(
                project,
                ["verify-before-push"],
                "project",
                "1.5.22",
                True,
                30,
                agent="claude-code",
            )

            command = run.call_args.args[0]
            self.assertEqual("add", command[3])
            self.assertEqual("claude-code", command[command.index("--agent") + 1])

    def test_plan_and_update_selection_include_all_new_locked_skills(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(
            shutil, "which", return_value="npx"
        ), patch.object(manager, "run_checked") as run:
            run.return_value.stdout = "updated"
            run.return_value.stderr = ""
            project = self.make_project(Path(directory), {name: "1.13.0" for name in self.NEW_SKILLS})

            plan = manager.build_update_plan(project, [], "project")
            self.assertEqual(self.NEW_SKILLS, {item["skill"] for item in plan["outcomes"]})
            selected = manager.resolve_update_selection(project, [], "project")
            self.assertEqual(sorted(self.NEW_SKILLS), selected)

            manager.update_skills(project, [], "project", "1.5.22", True, 30)
            command = run.call_args.args[0]
            for name in self.NEW_SKILLS:
                self.assertIn(name, command)

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

    def test_global_status_and_doctor_support_skill_lock_v3(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            global_root = self.make_global(
                Path(directory), {"verify-before-push": "1.4.0"}
            )
            state = manager.read_global_state(global_root)
            self.assertEqual("global", state["scope"])
            self.assertEqual("verified", state["skills"][0]["provenance_status"])
            diagnosis = manager.doctor(
                Path(directory), scope="global", global_root=global_root
            )
            self.assertTrue(diagnosis["healthy"])

    def test_claude_global_status_uses_shared_lock_and_native_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            global_root = self.make_global(
                Path(directory), {"verify-before-push": "1.15.0"}, "claude-code"
            )

            state = manager.read_global_state(global_root, agent="claude-code")

            self.assertEqual(
                (global_root / ".skill-lock.json").resolve(),
                Path(state["lock_file"]),
            )
            self.assertIn(".claude", state["skills"][0]["path"])
            self.assertTrue(state["skills"][0]["installed"])
            self.assertEqual("verified", state["skills"][0]["provenance_status"])

    def test_project_configuration_remains_shared_for_claude(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            self.assertEqual(
                project.resolve() / ".agents",
                manager.project_config_root(project, "claude-code"),
            )

    def test_global_doctor_rejects_unsupported_or_ambiguous_layout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            global_root = Path(directory) / ".agents"
            global_root.mkdir()
            (global_root / ".skill-lock.json").write_text(
                '{"version":3,"skills":{"verify-before-push":{}}}',
                encoding="utf-8",
            )
            diagnosis = manager.doctor(
                Path(directory), scope="global", global_root=global_root
            )
            self.assertFalse(diagnosis["healthy"])
            self.assertTrue(any("provenance mismatch" in item for item in diagnosis["problems"]))

    def test_global_update_uses_explicit_verified_selection(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(
            shutil, "which", return_value="npx"
        ), patch.object(manager, "run_checked") as run, patch.object(
            manager, "default_global_root"
        ) as default_root:
            root = Path(directory)
            global_root = self.make_global(root, {"verify-before-push": "1.4.0"})
            default_root.return_value = global_root
            run.return_value.stdout = "unchanged"
            run.return_value.stderr = ""
            report = manager.update_skills(
                root,
                ["verify-before-push"],
                "global",
                "1.5.22",
                True,
                30,
                global_root=global_root,
                as_json=True,
            )
            self.assertIn("-g", run.call_args.args[0])
            self.assertEqual("unchanged", report["outcomes"][0]["status"])

    def test_relocated_global_update_is_rejected_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(
            manager, "run_checked"
        ) as run:
            root = Path(directory)
            global_root = self.make_global(root, {"verify-before-push": "1.4.0"})
            with self.assertRaisesRegex(manager.ManagerError, "read-only"):
                manager.update_skills(
                    root,
                    ["verify-before-push"],
                    "global",
                    "1.5.22",
                    True,
                    30,
                    global_root=global_root,
                )
            run.assert_not_called()

    def test_plan_is_read_only_and_reports_update_migrations_and_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(
            manager, "run_checked"
        ) as run:
            project = self.make_project(
                Path(directory), {"verify-before-push": "1.3.0"}
            )
            script = project / ".agents/skills/verify-before-push/scripts/verify_before_push.py"
            script.parent.mkdir(parents=True, exist_ok=True)
            script.write_text("", encoding="utf-8")
            config = project / ".agents/verify-before-push/config.json"
            config.parent.mkdir(parents=True)
            config.write_text("{}", encoding="utf-8")
            before = (project / "skills-lock.json").read_bytes()
            plan = manager.build_update_plan(project, [], "project")
            self.assertFalse(plan["mutates"])
            self.assertEqual("1.18.1", plan["target_version"])
            self.assertEqual("update", plan["outcomes"][0]["action"])
            self.assertEqual(["verify-before-push"], plan["migration_candidates"])
            self.assertEqual("codex", plan["agent"])
            self.assertEqual(".agents/skills", plan["layout"])
            self.assertEqual(before, (project / "skills-lock.json").read_bytes())
            run.assert_not_called()

    def test_plan_reports_provenance_block_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = self.make_project(
                Path(directory), {"verify-before-push": "1.3.0"}
            )
            lock_path = project / "skills-lock.json"
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            lock["skills"]["verify-before-push"]["source"] = "other/skills"
            lock_path.write_text(json.dumps(lock), encoding="utf-8")
            plan = manager.build_update_plan(project, [], "project")
            self.assertTrue(plan["blocked"])
            self.assertEqual("blocked", plan["outcomes"][0]["action"])

    def test_json_failure_is_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = StringIO()
            with redirect_stderr(output):
                result = manager.main(
                    [
                        "update",
                        "verify-before-push",
                        "--project-path",
                        directory,
                        "--json",
                    ]
                )
            self.assertEqual(1, result)
            payload = json.loads(output.getvalue())
            self.assertEqual("failed", payload["outcomes"][0]["status"])
            self.assertEqual("update", payload["operation"])

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
        ), patch.object(manager, "run_checked") as run, patch.object(
            manager, "doctor", return_value={"healthy": False, "problems": ["fixture"]}
        ):
            run.return_value.stdout = "updated"
            run.return_value.stderr = ""
            project = self.make_project(
                Path(directory), {"verify-before-push": "1.2.0"}
            )
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

    def test_sync_project_context_config_path_honors_override(self) -> None:
        expected = (Path("private") / "context.json").resolve()
        actual = manager.sync_project_context_config_path(
            {"KOLABSE_SYNC_PROJECT_CONTEXT_CONFIG": str(expected)}
        )
        self.assertEqual(expected, actual)

    def test_migration_discovers_existing_sync_project_context_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = self.make_project(
                root, {"sync-project-context": "1.4.0"}
            ).resolve()
            script = project / ".agents/skills/sync-project-context/scripts/context_sync.py"
            script.parent.mkdir(parents=True)
            script.write_text("", encoding="utf-8")
            config = root / "user-config/context.json"
            config.parent.mkdir()
            config.write_text("{}", encoding="utf-8")

            with patch.object(
                manager, "sync_project_context_config_path", return_value=config
            ):
                disabled = manager.migration_commands(project, False)
                enabled = manager.migration_commands(project, True)

            self.assertEqual([], disabled)
            self.assertEqual(1, len(enabled))
            name, command = enabled[0]
            self.assertEqual("sync-project-context", name)
            self.assertEqual(
                [
                    manager.python_executable(),
                    str(script),
                    "--config-path",
                    str(config),
                    "migrate",
                    "--json",
                ],
                command,
            )


if __name__ == "__main__":
    unittest.main()
