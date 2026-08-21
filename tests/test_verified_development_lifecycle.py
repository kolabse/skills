from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from argparse import Namespace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "skills/execute-verified-development-lifecycle/scripts/development_lifecycle.py"
SPEC = importlib.util.spec_from_file_location("development_lifecycle", SCRIPT)
assert SPEC and SPEC.loader
LIFECYCLE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LIFECYCLE)


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def git(repository: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repository), *args], capture_output=True, text=True, check=True)
    return result.stdout.strip()


class VerifiedDevelopmentLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.project = self.base / "project"
        self.repository = self.project / "app"
        self.repository.mkdir(parents=True)
        self.remote = self.base / "remote.git"
        subprocess.run(["git", "init", "--bare", str(self.remote)], capture_output=True, check=True)
        git(self.repository, "init", "-b", "main")
        git(self.repository, "config", "user.email", "tests@example.invalid")
        git(self.repository, "config", "user.name", "Lifecycle Tests")
        git(self.repository, "remote", "add", "origin", str(self.remote))
        (self.repository / "docs").mkdir()
        (self.repository / "docs/requirements.md").write_text("requirements\n", encoding="utf-8")
        (self.repository / "AGENTS.md").write_text(LIFECYCLE.RULE_BLOCK + "\n", encoding="utf-8")
        git(self.repository, "add", ".")
        git(self.repository, "commit", "-m", "Initial")
        git(self.repository, "push", "-u", "origin", "main")
        self.artifacts = self.base / "artifacts"
        self.artifacts.mkdir()
        self.config = self.make_config()
        self.source = self.base / "config.json"
        write_json(self.source, self.config)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def make_config(self) -> dict:
        gates = [
            {"id": name, "required": True, "failure_rewind": name}
            for name in LIFECYCLE.ORDER
        ]
        gates[3]["failure_rewind"] = "tdd-red"
        return {
            "version": 1,
            "repositories": [{"name": "app", "path": "app", "base_ref": "origin/main", "require_clean": True, "require_upstream_current": True}],
            "rules": [{"id": "project-rules", "path": "AGENTS.md"}],
            "references": [{"id": "requirements", "path": "docs/requirements.md"}],
            "checks": [{"id": "unit-tests", "phase": "green", "required": True}],
            "gates": gates,
            "adapters": [{"id": "project-adapter", "kind": "project", "capabilities": sorted(LIFECYCLE.CAPABILITIES)}],
            "required_capabilities": sorted(LIFECYCLE.CAPABILITIES),
            "notifications": [{"id": "team", "path": "project notification profile"}],
            "documentation": [{"id": "canonical-docs", "path": "docs/behavior.md"}],
            "integration": {"development_repository": "app", "development_ref": "origin/development", "review_required": True},
            "production": {"delegated": True, "route_label": "configured-gitflow"},
            "delivery": {"deployment_required": True, "marker_required": True, "smoke_required": True},
            "cleanup": {"proof_methods": ["merged"]},
        }

    def configure(self) -> dict:
        return LIFECYCLE.cmd_configure(Namespace(project_root=str(self.project), config_source=str(self.source)))

    def install_rules(self) -> dict:
        return LIFECYCLE.cmd_configure_rules(Namespace(project_root=str(self.project), apply=True, yes=True))

    def make_plan(self) -> tuple[Path, Path, dict]:
        commit = git(self.repository, "rev-parse", "HEAD")
        request = {
            "lifecycle_id": "change-53", "outcome": "verified behavior", "feature_ref": "feature/change-53",
            "changed_scope": ["app/service.py"],
            "repositories": [{"name": "app", "start_commit": commit, "upstream_commit": commit, "clean": True, "current": True}],
            "rules_read": ["project-rules"], "references_read": ["requirements"],
            "documentation_targets": ["canonical-docs"], "notifications": ["team"],
        }
        input_path = self.artifacts / "input.json"
        plan_path = self.artifacts / "plan.json"
        state_path = self.artifacts / "state.json"
        write_json(input_path, request)
        plan = LIFECYCLE.cmd_plan(Namespace(project_root=str(self.project), input=str(input_path), output=str(plan_path), state_output=str(state_path)))
        return plan_path, state_path, plan

    def checkpoint(self, plan: dict, name: str, attempt: int = 1, status: str = "passed", rewind_to=None) -> dict:
        subjects = []
        for kind in sorted(LIFECYCLE.SUBJECT_KINDS[name]):
            identity = "a" * 40 if kind in {"commit", "tree"} else ("feature/change-53" if kind == "ref" else f"{kind}-identity")
            subjects.append({"kind": kind, "role": "checkpoint-subject", "repository": "app" if name in LIFECYCLE.SOURCE_CHECKPOINTS else None, "identity": identity})
        assertions = [{"name": assertion, "passed": status == "passed"} for assertion in sorted(LIFECYCLE.ASSERTIONS[name])]
        value = {
            "schema_version": 1, "checkpoint": name, "status": status,
            "plan_sha256": plan["plan_sha256"], "config_sha256": plan["config_sha256"],
            "attempt": attempt, "observed_at": datetime.now(timezone.utc).isoformat(),
            "subjects": subjects,
            "assertions": assertions,
            "coverage": {
                "repositories": [], "rules": [], "references": [], "checks": [],
                "documentation": [], "notifications": [],
            }, "evidence_sha256": "", "evidence_ref": "", "rewind_to": rewind_to,
        }
        if name == "changed-scope-preflight":
            value["coverage"] = {
                "repositories": ["app"], "rules": ["project-rules"], "references": ["requirements"],
                "checks": ["unit-tests"], "documentation": ["canonical-docs"], "notifications": ["team"],
            }
        evidence = {
            "schema_version": 1, "plan_sha256": plan["plan_sha256"], "config_sha256": plan["config_sha256"],
            "checkpoint": name, "observed_at": value["observed_at"], "subjects": subjects, "assertions": assertions,
            "producer": "fixture", "artifact_sha256": "c" * 64,
        }
        evidence_path = self.artifacts / f"evidence-{name}-{attempt}-{len(list(self.artifacts.glob('evidence-*')))}.json"
        write_json(evidence_path, evidence)
        value["evidence_ref"] = str(evidence_path)
        value["evidence_sha256"] = LIFECYCLE.digest(evidence)
        return value

    def advance(self, plan_path: Path, state_path: Path, checkpoint: dict) -> dict:
        path = self.artifacts / f"checkpoint-{len(list(self.artifacts.glob('checkpoint-*')))}.json"
        write_json(path, checkpoint)
        return LIFECYCLE.cmd_advance(Namespace(project_root=str(self.project), plan=str(plan_path), state=str(state_path), checkpoint=str(path)))

    def rebind_evidence(self, checkpoint: dict) -> None:
        path = Path(checkpoint["evidence_ref"])
        evidence = read_json(path)
        evidence["observed_at"] = checkpoint["observed_at"]
        evidence["subjects"] = checkpoint["subjects"]
        evidence["assertions"] = checkpoint["assertions"]
        write_json(path, evidence)
        checkpoint["evidence_sha256"] = LIFECYCLE.digest(evidence)

    def replan(self, suffix: str) -> dict:
        return LIFECYCLE.cmd_plan(Namespace(
            project_root=str(self.project), input=str(self.artifacts / "input.json"),
            output=str(self.artifacts / f"plan-{suffix}.json"), state_output=str(self.artifacts / f"state-{suffix}.json"),
        ))

    def test_configure_is_idempotent_and_status_and_migrate_are_read_only(self) -> None:
        first = self.configure()
        before = LIFECYCLE.project_config(self.project).read_bytes()
        second = self.configure()
        status = LIFECYCLE.cmd_status(Namespace(project_root=str(self.project)))
        migrated = LIFECYCLE.cmd_migrate(Namespace(project_root=str(self.project)))
        self.assertEqual(first["config_sha256"], second["config_sha256"])
        self.assertEqual(before, LIFECYCLE.project_config(self.project).read_bytes())
        self.assertFalse(status["mutates_repository"])
        self.assertFalse(migrated["changed"])

    def test_newer_configuration_is_rejected(self) -> None:
        self.config["version"] = 2
        write_json(self.source, self.config)
        with self.assertRaisesRegex(LIFECYCLE.LifecycleError, "unsupported configuration version"):
            self.configure()

    def test_rules_report_missing_and_malformed_and_apply_is_guarded(self) -> None:
        self.configure()
        (self.repository / "AGENTS.md").unlink()
        missing = LIFECYCLE.cmd_rules_status(Namespace(project_root=str(self.project)))
        self.assertFalse(missing["passed"])
        self.assertEqual("missing", missing["repositories"][0]["status"])
        with self.assertRaisesRegex(LIFECYCLE.LifecycleError, "requires both --apply and --yes"):
            LIFECYCLE.cmd_configure_rules(Namespace(project_root=str(self.project), apply=True, yes=False))
        (self.repository / "AGENTS.md").write_text(LIFECYCLE.START_MARKER + "\n", encoding="utf-8")
        malformed = LIFECYCLE.cmd_rules_status(Namespace(project_root=str(self.project)))
        self.assertEqual("malformed-markers", malformed["repositories"][0]["status"])
        with self.assertRaisesRegex(LIFECYCLE.LifecycleError, "malformed or duplicate"):
            self.install_rules()
        (self.repository / "AGENTS.md").unlink()
        applied = self.install_rules()
        self.assertTrue(applied["passed"])
        self.assertTrue(LIFECYCLE.cmd_rules_status(Namespace(project_root=str(self.project)))["passed"])

    def test_plan_requires_exact_coverage_and_external_outputs(self) -> None:
        self.configure()
        plan_path, state_path, plan = self.make_plan()
        self.assertTrue(plan["ready"])
        self.assertTrue(plan_path.is_file() and state_path.is_file())
        request = read_json(self.artifacts / "input.json")
        request["rules_read"] = []
        write_json(self.artifacts / "input.json", request)
        blocked = LIFECYCLE.cmd_plan(Namespace(project_root=str(self.project), input=str(self.artifacts / "input.json"), output=str(self.artifacts / "blocked.json"), state_output=str(self.artifacts / "blocked-state.json")))
        self.assertFalse(blocked["ready"])
        with self.assertRaisesRegex(LIFECYCLE.LifecycleError, "outside configured repositories"):
            LIFECYCLE.cmd_plan(Namespace(project_root=str(self.project), input=str(self.artifacts / "input.json"), output=str(self.repository / "plan.json"), state_output=str(self.artifacts / "unsafe-state.json")))

    def test_ordered_checkpoints_failure_rewind_and_invalidation(self) -> None:
        self.configure()
        plan_path, state_path, plan = self.make_plan()
        with self.assertRaisesRegex(LIFECYCLE.LifecycleError, "expected checkpoint task-claimed"):
            self.advance(plan_path, state_path, self.checkpoint(plan, "tdd-red"))
        self.advance(plan_path, state_path, self.checkpoint(plan, "task-claimed"))
        self.advance(plan_path, state_path, self.checkpoint(plan, "feature-prepared"))
        self.advance(plan_path, state_path, self.checkpoint(plan, "tdd-red"))
        failed = self.checkpoint(plan, "tdd-green", status="failed", rewind_to="tdd-red")
        self.advance(plan_path, state_path, failed)
        state = LIFECYCLE.read_json(state_path)
        self.assertEqual(["task-claimed", "feature-prepared"], list(state["completed"]))
        self.assertTrue(state["failed"])
        self.advance(plan_path, state_path, self.checkpoint(plan, "tdd-red", attempt=2))
        self.advance(plan_path, state_path, self.checkpoint(plan, "tdd-green", attempt=2))
        self.assertFalse(LIFECYCLE.read_json(state_path)["failed"])

    def test_verify_requires_and_accepts_complete_ordered_state(self) -> None:
        self.configure()
        plan_path, state_path, plan = self.make_plan()
        partial = LIFECYCLE.cmd_verify(Namespace(project_root=str(self.project), plan=str(plan_path), state=str(state_path)))
        self.assertFalse(partial["passed"])
        for name in LIFECYCLE.ORDER:
            self.advance(plan_path, state_path, self.checkpoint(plan, name))
        result = LIFECYCLE.cmd_verify(Namespace(project_root=str(self.project), plan=str(plan_path), state=str(state_path)))
        self.assertTrue(result["passed"])
        self.assertTrue(result["production_delegated"])
        self.assertFalse(result["mutates_repository"])

    def test_dependencies_plan_is_read_only_and_apply_requires_confirmation(self) -> None:
        planned = LIFECYCLE.cmd_dependencies(Namespace(include_integrations=False, apply=False, yes=False))
        self.assertFalse(planned["mutates_environment"])
        self.assertEqual(4, len(planned["required"]))
        with self.assertRaisesRegex(LIFECYCLE.LifecycleError, "requires both --apply and --yes"):
            LIFECYCLE.cmd_dependencies(Namespace(include_integrations=False, apply=True, yes=False))

    def test_plan_independently_rejects_lied_git_state_and_in_progress_operation(self) -> None:
        self.configure()
        self.make_plan()
        (self.repository / "untracked.txt").write_text("dirty\n", encoding="utf-8")
        dirty = self.replan("dirty")
        self.assertFalse(dirty["ready"])
        self.assertTrue(any("not clean" in item for item in dirty["blockers"]))
        (self.repository / "untracked.txt").unlink()

        request = read_json(self.artifacts / "input.json")
        request["repositories"][0]["start_commit"] = "0" * 40
        write_json(self.artifacts / "input.json", request)
        lied_sha = self.replan("lied-sha")
        self.assertTrue(any("identities do not match" in item for item in lied_sha["blockers"]))

        request["repositories"][0]["start_commit"] = git(self.repository, "rev-parse", "HEAD")
        write_json(self.artifacts / "input.json", request)
        git_dir = Path(git(self.repository, "rev-parse", "--git-dir"))
        if not git_dir.is_absolute():
            git_dir = self.repository / git_dir
        (git_dir / "MERGE_HEAD").write_text("a" * 40 + "\n", encoding="ascii")
        in_progress = self.replan("in-progress")
        self.assertTrue(any("operation in progress" in item for item in in_progress["blockers"]))

    def test_plan_rejects_live_base_or_upstream_mismatch(self) -> None:
        self.configure()
        self.make_plan()
        original = git(self.repository, "rev-parse", "HEAD")
        git(self.repository, "commit", "--allow-empty", "-m", "Local advance")
        request = read_json(self.artifacts / "input.json")
        request["repositories"][0]["start_commit"] = git(self.repository, "rev-parse", "HEAD")
        request["repositories"][0]["upstream_commit"] = original
        write_json(self.artifacts / "input.json", request)
        blocked = self.replan("base-upstream")
        self.assertFalse(blocked["ready"])
        self.assertTrue(any("HEAD/base/upstream" in item for item in blocked["blockers"]))

    def test_plan_rejects_missing_and_symlinked_declared_files(self) -> None:
        self.configure()
        (self.repository / "docs/requirements.md").unlink()
        (self.repository / "AGENTS.md").unlink()
        plan = self.make_plan()[2]
        self.assertTrue(any("managed lifecycle rule" in item for item in plan["blockers"]))
        self.assertTrue(any("declared rules file" in item for item in plan["blockers"]))
        git(self.repository, "restore", "AGENTS.md")
        missing_reference = self.replan("missing-reference")
        self.assertTrue(any("declared references file" in item for item in missing_reference["blockers"]))
        git(self.repository, "restore", "docs/requirements.md")
        original_probe = LIFECYCLE.path_has_symlink
        with mock.patch.object(
            LIFECYCLE,
            "path_has_symlink",
            side_effect=lambda path, boundary: path.name == "requirements.md" or original_probe(path, boundary),
        ):
            linked = self.replan("symlink-reference")
        self.assertTrue(any("symlinked" in item for item in linked["blockers"]))

    def test_retained_evidence_digest_and_content_must_match(self) -> None:
        self.configure()
        plan_path, state_path, plan = self.make_plan()
        checkpoint = self.checkpoint(plan, "task-claimed")
        evidence = read_json(Path(checkpoint["evidence_ref"]))
        evidence["producer"] = "tampered"
        write_json(Path(checkpoint["evidence_ref"]), evidence)
        with self.assertRaisesRegex(LIFECYCLE.LifecycleError, "canonical digest"):
            self.advance(plan_path, state_path, checkpoint)

        checkpoint = self.checkpoint(plan, "task-claimed", attempt=1)
        evidence = read_json(Path(checkpoint["evidence_ref"]))
        evidence["observed_at"] = datetime.now(timezone.utc).isoformat()
        write_json(Path(checkpoint["evidence_ref"]), evidence)
        checkpoint["evidence_sha256"] = LIFECYCLE.digest(evidence)
        with self.assertRaisesRegex(LIFECYCLE.LifecycleError, "timestamp, subjects, or assertions"):
            self.advance(plan_path, state_path, checkpoint)

    def test_retained_evidence_allows_canonicalized_parent_alias(self) -> None:
        self.configure()
        plan_path, state_path, plan = self.make_plan()
        alias = self.base / "artifacts-alias"
        try:
            alias.symlink_to(self.artifacts, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"directory symlinks are unavailable: {exc}")
        checkpoint = self.checkpoint(plan, "task-claimed")
        checkpoint["evidence_ref"] = str(alias / Path(checkpoint["evidence_ref"]).name)

        result = self.advance(plan_path, state_path, checkpoint)

        self.assertEqual(result["current_checkpoint"], "task-claimed")

    def test_verify_rejects_self_rehashed_state_with_malformed_completed_entries(self) -> None:
        self.configure()
        plan_path, state_path, _ = self.make_plan()
        state = LIFECYCLE.read_json(state_path)
        state["completed"] = {name: {} for name in LIFECYCLE.ORDER}
        state["current_checkpoint"] = "cleanup-proved"
        state["complete"] = True
        state["state_sha256"] = LIFECYCLE.digest(state, "state_sha256")
        write_json(state_path, state)

        with self.assertRaises(LIFECYCLE.LifecycleError):
            LIFECYCLE.cmd_verify(Namespace(
                project_root=str(self.project), plan=str(plan_path), state=str(state_path),
            ))

    def test_verify_revalidates_retained_evidence_after_completion(self) -> None:
        self.configure()
        plan_path, state_path, plan = self.make_plan()
        for name in LIFECYCLE.ORDER:
            self.advance(plan_path, state_path, self.checkpoint(plan, name))

        state = LIFECYCLE.read_json(state_path)
        evidence_path = Path(state["completed"]["task-claimed"]["evidence_ref"])
        original = evidence_path.read_bytes()
        evidence = LIFECYCLE.read_json(evidence_path)
        evidence["producer"] = "tampered-after-advance"
        write_json(evidence_path, evidence)
        with self.assertRaises(LIFECYCLE.LifecycleError):
            LIFECYCLE.cmd_verify(Namespace(
                project_root=str(self.project), plan=str(plan_path), state=str(state_path),
            ))

        evidence_path.write_bytes(original)
        evidence_path.unlink()
        with self.assertRaises(LIFECYCLE.LifecycleError):
            LIFECYCLE.cmd_verify(Namespace(
                project_root=str(self.project), plan=str(plan_path), state=str(state_path),
            ))

    def test_deployment_must_match_development_integration_identity(self) -> None:
        self.configure()
        plan_path, state_path, plan = self.make_plan()
        deployment_index = LIFECYCLE.ORDER.index("deployment-observed")
        for name in LIFECYCLE.ORDER[:deployment_index]:
            self.advance(plan_path, state_path, self.checkpoint(plan, name))

        checkpoint = self.checkpoint(plan, "deployment-observed")
        development = next(
            subject for subject in checkpoint["subjects"]
            if subject["kind"] == "development-integration"
        )
        development["identity"] = "different-development-integration"
        self.rebind_evidence(checkpoint)
        with self.assertRaisesRegex(
            LIFECYCLE.LifecycleError, "deployment.*development integration",
        ):
            self.advance(plan_path, state_path, checkpoint)

    def test_source_checkpoint_requires_per_repository_subject(self) -> None:
        self.configure()
        plan_path, state_path, plan = self.make_plan()
        self.advance(plan_path, state_path, self.checkpoint(plan, "task-claimed"))
        checkpoint = self.checkpoint(plan, "feature-prepared")
        for subject in checkpoint["subjects"]:
            subject["repository"] = None
        self.rebind_evidence(checkpoint)
        with self.assertRaisesRegex(LIFECYCLE.LifecycleError, "lacks subject identity"):
            self.advance(plan_path, state_path, checkpoint)

    def test_failed_checkpoint_needs_failure_and_config_rejects_forward_rewind(self) -> None:
        self.configure()
        plan_path, state_path, plan = self.make_plan()
        checkpoint = self.checkpoint(plan, "task-claimed", status="failed", rewind_to="task-claimed")
        for assertion in checkpoint["assertions"]:
            assertion["passed"] = True
        self.rebind_evidence(checkpoint)
        with self.assertRaisesRegex(LIFECYCLE.LifecycleError, "at least one failed assertion"):
            self.advance(plan_path, state_path, checkpoint)

        bad = self.make_config()
        bad["gates"][0]["failure_rewind"] = "tdd-green"
        with self.assertRaisesRegex(LIFECYCLE.LifecycleError, "same or earlier"):
            LIFECYCLE.validate_config(bad)

    def test_checkpoint_timestamp_rejects_naive_and_future_values(self) -> None:
        self.configure()
        plan_path, state_path, plan = self.make_plan()
        naive = self.checkpoint(plan, "task-claimed")
        naive["observed_at"] = "2030-01-01T00:00:00"
        self.rebind_evidence(naive)
        with self.assertRaisesRegex(LIFECYCLE.LifecycleError, "include a timezone"):
            self.advance(plan_path, state_path, naive)
        future = self.checkpoint(plan, "task-claimed")
        future["observed_at"] = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        self.rebind_evidence(future)
        with self.assertRaisesRegex(LIFECYCLE.LifecycleError, "too far in the future"):
            self.advance(plan_path, state_path, future)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
