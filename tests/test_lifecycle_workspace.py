from __future__ import annotations

from argparse import Namespace
import copy
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import unittest
from unittest import mock

import test_verified_development_lifecycle as fixtures

LIFECYCLE, SCRIPT = fixtures.LIFECYCLE, fixtures.SCRIPT
git, write_json = fixtures.git, fixtures.write_json


class LifecycleWorkspaceTests(unittest.TestCase):
    make_config = fixtures.VerifiedDevelopmentLifecycleTests.make_config
    configure = fixtures.VerifiedDevelopmentLifecycleTests.configure
    checkpoint = fixtures.VerifiedDevelopmentLifecycleTests.checkpoint
    advance = fixtures.VerifiedDevelopmentLifecycleTests.advance
    tearDown = fixtures.VerifiedDevelopmentLifecycleTests.tearDown

    def setUp(self):
        fixtures.VerifiedDevelopmentLifecycleTests.setUp(self)
        self.workspace = self.base / "workspace"
        self.mapped = self.workspace / "checkout"
        self.workspace.mkdir()
        git(self.repository, "worktree", "add", "--track", "-b", "feature/workspace", str(self.mapped), "origin/main")
        git(self.repository, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
        self.mapping = {"version": 1, "workspace_root": str(self.workspace), "repositories": {"app": "checkout"}}
        self.map_path = self.artifacts / "workspace.json"
        write_json(self.map_path, self.mapping)
        self.configure()
        fixtures.VerifiedDevelopmentLifecycleTests.make_plan(self)

    def plan(self, **overrides):
        values = dict(project_root=str(self.project), input=str(self.artifacts / "input.json"),
                      output=str(self.artifacts / "mapped-plan.json"), state_output=str(self.artifacts / "mapped-state.json"),
                      workspace_map=str(self.map_path))
        values.update(overrides)
        return LIFECYCLE.cmd_plan(Namespace(**values))

    def test_mapped_clean_worktree_overrides_dirty_canonical_and_binds_map(self):
        (self.repository / "dirty.txt").write_text("preserve me")
        original_config = LIFECYCLE.project_config(self.project).read_bytes()
        plan = self.plan()
        self.assertTrue(plan["ready"], plan["blockers"])
        self.assertEqual({**self.mapping, "workspace_root": str(self.workspace.resolve())}, plan["workspace_map"])
        self.assertEqual("feature/workspace", plan["repositories"][0]["branch"])
        self.assertEqual(original_config, LIFECYCLE.project_config(self.project).read_bytes())
        self.assertEqual("preserve me", (self.repository / "dirty.txt").read_text())

    def test_map_rejects_unknown_missing_duplicate_and_escaping_paths(self):
        bad_maps = []
        for repositories in ({}, {"other": "checkout"}, {"app": "checkout", "other": "checkout"}):
            bad_maps.append({**self.mapping, "repositories": repositories})
        for path in ("../project/app", "..\\project\\app", "/tmp/app", "C:/app", "C:app", "\\\\server\\share", "checkout\\nested", "checkout//nested", "check\x00out"):
            bad_maps.append({**self.mapping, "repositories": {"app": path}})
        bad_maps.extend([{**self.mapping, "version": True}, {**self.mapping, "extra": 1}, {**self.mapping, "workspace_root": "relative"}])
        for mapping in bad_maps:
            with self.subTest(mapping=mapping):
                write_json(self.map_path, mapping)
                with self.assertRaises(LIFECYCLE.LifecycleError):
                    self.plan()
        write_json(self.map_path, {**self.mapping, "repositories": {"app": "checkout/docs"}})
        with self.assertRaisesRegex(LIFECYCLE.LifecycleError, "exact Git root"):
            self.plan()

    def test_duplicate_resolved_roots_are_rejected(self):
        config = copy.deepcopy(self.config)
        config["repositories"].append({**config["repositories"][0], "name": "docs"})
        write_json(LIFECYCLE.project_config(self.project), config)
        write_json(self.map_path, {**self.mapping, "repositories": {"app": "checkout", "docs": "checkout"}})
        with self.assertRaisesRegex(LIFECYCLE.LifecycleError, "duplicate"):
            self.plan()

    def test_no_canonical_fallback_for_missing_mapped_reference(self):
        git(self.mapped, "rm", "docs/requirements.md")
        git(self.mapped, "commit", "-m", "Remove mapped reference")
        git(self.mapped, "push", "origin", "HEAD:main")
        request = LIFECYCLE.read_json(self.artifacts / "input.json")
        request["repositories"][0].update(start_commit=git(self.mapped, "rev-parse", "HEAD"), upstream_commit=git(self.mapped, "rev-parse", "HEAD"))
        write_json(self.artifacts / "input.json", request)
        plan = self.plan()
        self.assertFalse(plan["ready"])
        self.assertTrue(any("declared references file requirements" in item for item in plan["blockers"]))
        self.assertTrue((self.repository / "docs/requirements.md").is_file())

    def test_bootstrap_normalizes_sibling_or_absolute_declarations_without_rewriting(self):
        LIFECYCLE.project_config(self.project).unlink()
        for original in ("../canonical/app", str(self.repository)):
            with self.subTest(original=original):
                write_json(self.project / LIFECYCLE.VERIFY_CONFIG_REL, {"repositories": [{"name": "App Service", "path": original}], "checks": []})
                write_json(self.map_path, {**self.mapping, "repositories": {"app-service": "checkout"}})
                result = LIFECYCLE.cmd_bootstrap(Namespace(project_root=str(self.project), workspace_map=str(self.map_path), apply=True, yes=True))
                self.assertTrue(result["ready"], result["blockers"])
                self.assertEqual("workspace-map", result["repository_path_frame"])
                self.assertTrue(result["config"]["workspace_map_required"])
                self.assertEqual("checkout", result["config"]["repositories"][0]["path"])
                before = LIFECYCLE.project_config(self.project).read_bytes()
                repeated = LIFECYCLE.cmd_bootstrap(Namespace(project_root=str(self.project), workspace_map=str(self.map_path), apply=True, yes=True))
                self.assertFalse(repeated["created"])
                self.assertEqual(before, LIFECYCLE.project_config(self.project).read_bytes())
                LIFECYCLE.project_config(self.project).unlink()

    def test_map_required_config_fails_closed_for_root_consumers(self):
        self.config["workspace_map_required"] = True
        write_json(LIFECYCLE.project_config(self.project), self.config)
        status = LIFECYCLE.cmd_status(Namespace(project_root=str(self.project)))
        self.assertTrue(status["workspace_map_required"])
        for command in (LIFECYCLE.cmd_bootstrap, LIFECYCLE.cmd_rules_status, LIFECYCLE.cmd_configure_rules):
            with self.subTest(command=command.__name__):
                with self.assertRaisesRegex(LIFECYCLE.LifecycleError, "workspace.map.*required"):
                    command(Namespace(project_root=str(self.project), apply=True, yes=True))
        with self.assertRaisesRegex(LIFECYCLE.LifecycleError, "workspace.map.*required"):
            self.plan(workspace_map=None)

    def test_rules_are_installed_only_in_mapped_worktree(self):
        (self.mapped / "AGENTS.md").write_text("Mapped rules\n")
        before = (self.repository / "AGENTS.md").read_bytes()
        args = Namespace(project_root=str(self.project), workspace_map=str(self.map_path), apply=True, yes=True)
        result = LIFECYCLE.cmd_configure_rules(args)
        self.assertTrue(result["passed"])
        self.assertIn("Mapped rules", (self.mapped / "AGENTS.md").read_text())
        self.assertEqual(before, (self.repository / "AGENTS.md").read_bytes())
        self.assertFalse(LIFECYCLE.cmd_configure_rules(args)["mutates_repository"])

    def test_artifacts_cannot_enter_canonical_mapped_or_other_git_worktrees(self):
        # Map-required configs have no canonical checkout path; the nearest named
        # output parent must still detect its enclosing canonical Git worktree.
        self.config["workspace_map_required"] = True
        self.config["repositories"][0]["path"] = "checkout"
        write_json(LIFECYCLE.project_config(self.project), self.config)
        for repository in (self.repository, self.mapped):
            target = repository / "new/artifacts/plan.json"
            with self.subTest(repository=repository):
                with self.assertRaisesRegex(LIFECYCLE.LifecycleError, "artifact must be outside"):
                    self.plan(output=str(target))
                self.assertFalse(target.exists())

    def test_bound_map_replays_after_worktree_and_source_map_cleanup(self):
        plan = self.plan()
        self.assertIn("workspace_map", plan)
        plan_path, state_path = self.artifacts / "mapped-plan.json", self.artifacts / "mapped-state.json"
        for name in LIFECYCLE.ORDER:
            self.advance(plan_path, state_path, self.checkpoint(plan, name))
        git(self.repository, "worktree", "remove", str(self.mapped))
        self.map_path.unlink()
        before = state_path.read_bytes()
        result = LIFECYCLE.cmd_verify(Namespace(project_root=str(self.project), plan=str(plan_path), state=str(state_path)))
        self.assertTrue(result["passed"])
        self.assertEqual(before, state_path.read_bytes())

    def test_bound_map_tampering_fails_digest_and_invalid_rebound_map(self):
        self.plan()
        plan_path, state_path = self.artifacts / "mapped-plan.json", self.artifacts / "mapped-state.json"
        plan = LIFECYCLE.read_json(plan_path)
        plan["workspace_map"]["repositories"]["app"] = "../escape"
        write_json(plan_path, plan)
        args = Namespace(project_root=str(self.project), plan=str(plan_path), state=str(state_path))
        with self.assertRaisesRegex(LIFECYCLE.LifecycleError, "plan_sha256"):
            LIFECYCLE.cmd_verify(args)
        plan["plan_sha256"] = LIFECYCLE.digest(plan, "plan_sha256")
        state = LIFECYCLE.read_json(state_path)
        state["plan_sha256"] = plan["plan_sha256"]
        state["state_sha256"] = LIFECYCLE.digest(state, "state_sha256")
        write_json(plan_path, plan)
        write_json(state_path, state)
        with self.assertRaisesRegex(LIFECYCLE.LifecycleError, "workspace"):
            LIFECYCLE.cmd_verify(args)

    def test_mapped_symlink_or_junction_is_rejected_including_replay(self):
        alias = self.workspace / "alias"
        try:
            alias.symlink_to(self.mapped, target_is_directory=True)
        except OSError:
            if os.name != "nt":
                self.skipTest("directory symlinks are unavailable")
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(alias), str(self.mapped)], capture_output=True)
            if result.returncode:
                self.skipTest("directory symlinks and junctions are unavailable")
        try:
            write_json(self.map_path, {**self.mapping, "repositories": {"app": "alias"}})
            with self.assertRaisesRegex(LIFECYCLE.LifecycleError, "symlink|junction"):
                self.plan()
        finally:
            if alias.is_symlink():
                alias.unlink()
            else:
                alias.rmdir()

    def test_workspace_schema_is_portable_and_plan_binding_is_declared(self):
        schema = json.loads((SCRIPT.parent.parent / "schemas/workspace-map.schema.json").read_text())
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual({"version", "workspace_root", "repositories"}, set(schema["required"]))
        plan_schema = json.loads((SCRIPT.parent.parent / "schemas/plan.schema.json").read_text())
        self.assertIn("workspace_map", plan_schema["properties"])

    def test_copied_skill_cli_accepts_shared_map_without_sibling_imports(self):
        copied = self.artifacts / "installed-lifecycle"
        shutil.copytree(SCRIPT.parent.parent, copied)
        result = subprocess.run([
            sys.executable, "-B", str(copied / "scripts/development_lifecycle.py"), "plan",
            "--project-root", str(self.project), "--workspace-map", str(self.map_path),
            "--input", str(self.artifacts / "input.json"), "--output", str(self.artifacts / "copied-plan.json"),
            "--state-output", str(self.artifacts / "copied-state.json"), "--json",
        ], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr or result.stdout)
        self.assertTrue(json.loads(result.stdout)["ready"])

    def test_retained_evidence_cannot_enter_canonical_or_mapped_worktree(self):
        self.config["workspace_map_required"] = True
        self.config["repositories"][0]["path"] = "checkout"
        write_json(LIFECYCLE.project_config(self.project), self.config)
        plan = self.plan()
        for repository in (self.repository, self.mapped):
            checkpoint = self.checkpoint(plan, "task-claimed")
            target = repository / "evidence.json"
            target.write_bytes(Path(checkpoint["evidence_ref"]).read_bytes())
            checkpoint["evidence_ref"] = str(target)
            try:
                with self.subTest(repository=repository):
                    with self.assertRaisesRegex(LIFECYCLE.LifecycleError, "artifact must be outside"):
                        self.advance(self.artifacts / "mapped-plan.json", self.artifacts / "mapped-state.json", checkpoint)
            finally:
                target.unlink()

    def test_mapped_multi_repository_bootstrap_does_not_infer_integration_role(self):
        LIFECYCLE.project_config(self.project).unlink()
        docs = self.workspace / "docs"
        git(self.repository, "worktree", "add", "--track", "-b", "feature/docs", str(docs), "origin/main")
        write_json(self.project / LIFECYCLE.VERIFY_CONFIG_REL, {"repositories": [{"name": "app", "path": "../app"}, {"name": "docs", "path": "../docs"}]})
        write_json(self.map_path, {**self.mapping, "repositories": {"app": "checkout", "docs": "docs"}})
        result = LIFECYCLE.cmd_bootstrap(Namespace(project_root=str(self.project), workspace_map=str(self.map_path), apply=True, yes=True))
        self.assertFalse(result["ready"])
        self.assertTrue(any("development integration repository" in item for item in result["blockers"]))
        self.assertFalse(LIFECYCLE.project_config(self.project).exists())

    @unittest.skipUnless(os.name == "nt", "Windows junction regression")
    def test_replay_rejects_junction_inserted_after_mapped_worktree_cleanup(self):
        self.plan()
        git(self.repository, "worktree", "remove", str(self.mapped))
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(self.mapped), str(self.repository)], capture_output=True)
        self.assertEqual(0, result.returncode, result.stderr)
        try:
            with self.assertRaisesRegex(LIFECYCLE.LifecycleError, "symlink|junction"):
                LIFECYCLE.cmd_verify(Namespace(project_root=str(self.project), plan=str(self.artifacts / "mapped-plan.json"), state=str(self.artifacts / "mapped-state.json")))
        finally:
            self.mapped.rmdir()

    @unittest.skipUnless(os.name == "nt", "Windows junction regression")
    def test_artifact_junction_cannot_escape_mapped_repository_guard(self):
        plan = self.plan()
        alias = self.mapped / "artifact-link"
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(alias), str(self.artifacts)], capture_output=True)
        self.assertEqual(0, result.returncode, result.stderr)
        try:
            with self.assertRaisesRegex(LIFECYCLE.LifecycleError, "artifact must be outside"):
                LIFECYCLE.ensure_external(alias / "unsafe-plan.json", self.config, self.project, plan["workspace_map"])
            self.assertFalse((self.artifacts / "unsafe-plan.json").exists())
            checkpoint = self.checkpoint(plan, "task-claimed")
            checkpoint["evidence_ref"] = str(alias / Path(checkpoint["evidence_ref"]).name)
            with self.assertRaisesRegex(LIFECYCLE.LifecycleError, "artifact must be outside"):
                self.advance(self.artifacts / "mapped-plan.json", self.artifacts / "mapped-state.json", checkpoint)
        finally:
            alias.rmdir()

    def test_artifact_inspection_errors_do_not_authorize_writes(self):
        result = subprocess.CompletedProcess([], 128, stdout="", stderr="fatal: detected dubious ownership")
        with mock.patch.object(LIFECYCLE.subprocess, "run", return_value=result):
            with self.assertRaisesRegex(LIFECYCLE.LifecycleError, "cannot safely inspect"):
                LIFECYCLE.ensure_external(self.artifacts / "unsafe.json", self.config, self.project, self.mapping)
        self.assertFalse((self.artifacts / "unsafe.json").exists())


if __name__ == "__main__":
    unittest.main()
