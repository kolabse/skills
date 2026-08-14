from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIRECTORY = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "sync-project-context"
    / "scripts"
)
sys.dont_write_bytecode = True
sys.path.insert(0, str(SCRIPT_DIRECTORY))

import context_sync  # noqa: E402


def git(path: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(path), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def create_repository(path: Path, remote: str) -> None:
    path.mkdir(parents=True)
    git(path, "init", "--initial-branch=main")
    git(path, "config", "user.name", "Context Test")
    git(path, "config", "user.email", "context@example.invalid")
    (path / "tracked.txt").write_text("initial\n", encoding="utf-8")
    git(path, "add", "tracked.txt")
    git(path, "commit", "-m", "initial")
    git(path, "remote", "add", "origin", remote)


def namespace(**values: object) -> argparse.Namespace:
    defaults: dict[str, object] = {
        "config_path": None,
        "json": True,
        "merge_heads": False,
        "checkpoint_id": None,
    }
    defaults.update(values)
    return argparse.Namespace(**defaults)


class SyncProjectContextTests(unittest.TestCase):
    def test_configure_capture_restore_without_project_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            storage = root / "drive"
            config = root / "profile" / "config.json"
            payload = root / "payload.json"
            create_repository(project, "https://example.invalid/team/demo.git")
            before = sorted(
                str(path.relative_to(project))
                for path in project.rglob("*")
                if ".git" not in path.parts
            )

            configured = context_sync.command_configure(
                namespace(
                    project_path=str(project),
                    storage_root=str(storage),
                    project_id="proj-shared-context",
                    mode="metadata-only",
                    acknowledge_storage_policy=True,
                    config_path=str(config),
                )
            )
            payload.write_text(
                json.dumps(
                    {
                        "summary": "Implemented a bounded cache change.",
                        "decisions": ["Keep invalidation synchronous."],
                        "actions": ["Updated tests."],
                        "verifications": ["Unit tests passed."],
                        "open_questions": ["Confirm the TTL."],
                        "next_steps": ["Run integration tests."],
                        "relevant_paths": [],
                    }
                ),
                encoding="utf-8",
            )
            captured = context_sync.command_capture(
                namespace(
                    project_path=str(project),
                    input=str(payload),
                    stdin=False,
                    config_path=str(config),
                )
            )
            restored = context_sync.command_restore(
                namespace(project_path=str(project), config_path=str(config))
            )
            status = context_sync.command_status(
                namespace(project_path=str(project), config_path=str(config))
            )
            audited = context_sync.command_audit(
                namespace(project_path=str(project), config_path=str(config))
            )

            after = sorted(
                str(path.relative_to(project))
                for path in project.rglob("*")
                if ".git" not in path.parts
            )
            self.assertEqual(before, after)
            self.assertTrue(configured["configured"])
            self.assertEqual(captured["checkpoint_id"], restored["checkpoint_id"])
            self.assertTrue(all(restored["freshness"].values()))
            self.assertNotIn("branch", restored["recorded_repository"])
            self.assertNotIn("changed_paths", restored["recorded_repository"])
            self.assertEqual(1, status["checkpoint_count"])
            self.assertTrue(audited["ok"])

    def test_configure_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            create_repository(project, "git@example.invalid:team/demo.git")
            arguments = namespace(
                project_path=str(project),
                storage_root=str(root / "drive"),
                project_id="proj-idempotent",
                mode="metadata-only",
                acknowledge_storage_policy=True,
                config_path=str(root / "config.json"),
            )

            first = context_sync.command_configure(arguments)
            config_before = Path(arguments.config_path).read_bytes()
            marker_before = (
                root / "drive" / "proj-idempotent" / "project.json"
            ).read_bytes()
            second = context_sync.command_configure(arguments)

            self.assertTrue(first["changed"])
            self.assertFalse(second["changed"])
            self.assertEqual(config_before, Path(arguments.config_path).read_bytes())
            self.assertEqual(
                marker_before,
                (root / "drive" / "proj-idempotent" / "project.json").read_bytes(),
            )

    def test_metadata_only_rejects_paths_and_secrets(self) -> None:
        safe = {
            "summary": "Continue the verified change.",
            "relevant_paths": ["src/private-name.py"],
        }
        with self.assertRaisesRegex(
            context_sync.ContextSyncError, "does not permit relevant_paths"
        ):
            context_sync.validate_context(safe, "metadata-only")

        unsafe = {
            "summary": "Use Authorization: Bearer abcdefghijklmnopqrstuvwxyz",
        }
        with self.assertRaisesRegex(
            context_sync.ContextSyncError, "possible secret"
        ):
            context_sync.validate_context(unsafe, "metadata-only")

    def test_storage_inside_project_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            create_repository(project, "https://example.invalid/team/demo.git")
            with self.assertRaisesRegex(
                context_sync.ContextSyncError, "outside the project"
            ):
                context_sync.command_configure(
                    namespace(
                        project_path=str(project),
                        storage_root=str(project / ".private-context"),
                        project_id="proj-forbidden",
                        mode="metadata-only",
                        acknowledge_storage_policy=True,
                        config_path=str(root / "config.json"),
                    )
                )

    def test_storage_inside_another_git_worktree_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            storage_repository = root / "shared-repository"
            create_repository(project, "https://example.invalid/team/demo.git")
            create_repository(
                storage_repository,
                "https://example.invalid/team/shared.git",
            )
            with self.assertRaisesRegex(
                context_sync.ContextSyncError, "every Git worktree"
            ):
                context_sync.command_configure(
                    namespace(
                        project_path=str(project),
                        storage_root=str(storage_repository / "context"),
                        project_id="proj-forbidden-git-storage",
                        mode="metadata-only",
                        acknowledge_storage_policy=True,
                        config_path=str(root / "config.json"),
                    )
                )

    def test_second_computer_accepts_same_remote_and_rejects_another(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first"
            second = root / "second"
            wrong = root / "wrong"
            remote = "https://example.invalid/team/demo.git"
            create_repository(first, remote)
            create_repository(second, remote)
            create_repository(wrong, "https://example.invalid/team/other.git")
            storage = root / "drive"
            first_config = root / "first-config.json"
            second_config = root / "second-config.json"

            context_sync.command_configure(
                namespace(
                    project_path=str(first),
                    storage_root=str(storage),
                    project_id="proj-two-computers",
                    mode="metadata-only",
                    acknowledge_storage_policy=True,
                    config_path=str(first_config),
                )
            )
            accepted = context_sync.command_configure(
                namespace(
                    project_path=str(second),
                    storage_root=str(storage),
                    project_id="proj-two-computers",
                    mode="metadata-only",
                    acknowledge_storage_policy=True,
                    config_path=str(second_config),
                )
            )

            self.assertTrue(accepted["configured"])
            with self.assertRaisesRegex(
                context_sync.ContextSyncError, "another repository"
            ):
                context_sync.command_configure(
                    namespace(
                        project_path=str(wrong),
                        storage_root=str(storage),
                        project_id="proj-two-computers",
                        mode="metadata-only",
                        acknowledge_storage_policy=True,
                        config_path=str(root / "wrong-config.json"),
                    )
                )

    def test_paths_mode_records_names_but_not_contents(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            create_repository(project, "https://example.invalid/team/demo.git")
            (project / "tracked.txt").write_text("sensitive body\n", encoding="utf-8")
            state = context_sync.repository_state(project, "paths")

            self.assertEqual(["tracked.txt"], state["changed_paths"])
            self.assertEqual("main", state["branch"])
            self.assertNotIn("sensitive body", json.dumps(state))

    def test_concurrent_heads_require_review_and_can_be_merged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            storage = root / "drive"
            config = root / "config.json"
            payload = root / "payload.json"
            create_repository(project, "https://example.invalid/team/demo.git")
            context_sync.command_configure(
                namespace(
                    project_path=str(project),
                    storage_root=str(storage),
                    project_id="proj-concurrent",
                    mode="metadata-only",
                    acknowledge_storage_policy=True,
                    config_path=str(config),
                )
            )
            payload.write_text(
                json.dumps({"summary": "Reconciled both offline checkpoints."}),
                encoding="utf-8",
            )
            checkpoint_directory = storage / "proj-concurrent" / "checkpoints"
            for suffix, created_at in (
                ("a", "2026-08-14T10:00:00Z"),
                ("b", "2026-08-14T10:01:00Z"),
            ):
                checkpoint_id = "checkpoint-" + suffix * 32
                checkpoint = {
                    "schema_version": 1,
                    "checkpoint_id": checkpoint_id,
                    "project_id": "proj-concurrent",
                    "machine_id": "machine-000000000000",
                    "created_at": created_at,
                    "parent_checkpoint_ids": [],
                    "repository": context_sync.repository_state(
                        project, "metadata-only"
                    ),
                    "context": {
                        "summary": f"Offline branch {suffix}.",
                        "decisions": [],
                        "actions": [],
                        "verifications": [],
                        "open_questions": [],
                        "next_steps": [],
                        "relevant_paths": [],
                    },
                }
                checkpoint["content_sha256"] = context_sync.checkpoint_digest(
                    checkpoint
                )
                (checkpoint_directory / f"{checkpoint_id}.json").write_text(
                    json.dumps(checkpoint), encoding="utf-8"
                )

            status = context_sync.command_status(
                namespace(project_path=str(project), config_path=str(config))
            )
            self.assertTrue(status["has_conflict"])
            self.assertEqual(2, len(status["head_checkpoint_ids"]))
            with self.assertRaisesRegex(
                context_sync.ContextSyncError, "separate review"
            ):
                context_sync.command_restore(
                    namespace(project_path=str(project), config_path=str(config))
                )
            reviewed = context_sync.command_restore(
                namespace(
                    project_path=str(project),
                    config_path=str(config),
                    checkpoint_id="checkpoint-" + "a" * 32,
                )
            )
            self.assertTrue(reviewed["has_conflict"])

            merged = context_sync.command_capture(
                namespace(
                    project_path=str(project),
                    config_path=str(config),
                    input=str(payload),
                    stdin=False,
                    merge_heads=True,
                )
            )
            self.assertEqual(2, len(merged["parent_checkpoint_ids"]))
            final_status = context_sync.command_status(
                namespace(project_path=str(project), config_path=str(config))
            )
            self.assertFalse(final_status["has_conflict"])

    def test_config_and_capture_input_must_stay_outside_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            storage = root / "drive"
            config = root / "config.json"
            create_repository(project, "https://example.invalid/team/demo.git")
            with self.assertRaisesRegex(
                context_sync.ContextSyncError, "Configuration path"
            ):
                context_sync.command_configure(
                    namespace(
                        project_path=str(project),
                        storage_root=str(storage),
                        project_id="proj-local-config",
                        mode="metadata-only",
                        acknowledge_storage_policy=True,
                        config_path=str(project / "context-config.json"),
                    )
                )
            context_sync.command_configure(
                namespace(
                    project_path=str(project),
                    storage_root=str(storage),
                    project_id="proj-local-config",
                    mode="metadata-only",
                    acknowledge_storage_policy=True,
                    config_path=str(config),
                )
            )
            input_path = project / "handoff.json"
            input_path.write_text(
                json.dumps({"summary": "Must not be accepted here."}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                context_sync.ContextSyncError, "Capture input"
            ):
                context_sync.command_capture(
                    namespace(
                        project_path=str(project),
                        config_path=str(config),
                        input=str(input_path),
                        stdin=False,
                    )
                )

    def test_tampered_checkpoint_fails_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            storage = root / "drive"
            config = root / "config.json"
            create_repository(project, "https://example.invalid/team/demo.git")
            context_sync.command_configure(
                namespace(
                    project_path=str(project),
                    storage_root=str(storage),
                    project_id="proj-audit",
                    mode="metadata-only",
                    acknowledge_storage_policy=True,
                    config_path=str(config),
                )
            )
            checkpoint_id = "checkpoint-" + "a" * 32
            checkpoint = {
                "schema_version": 1,
                "checkpoint_id": checkpoint_id,
                "project_id": "proj-audit",
                "machine_id": "machine-000000000000",
                "created_at": "2026-08-14T00:00:00Z",
                "parent_checkpoint_ids": [],
                "repository": {},
                "context": {
                    "summary": "password=supersecretvalue",
                },
            }
            checkpoint["content_sha256"] = context_sync.checkpoint_digest(checkpoint)
            checkpoint_path = (
                storage
                / "proj-audit"
                / "checkpoints"
                / f"{checkpoint_id}.json"
            )
            checkpoint_path.write_text(json.dumps(checkpoint), encoding="utf-8")

            with self.assertRaisesRegex(
                context_sync.ContextSyncError, "possible secret"
            ):
                context_sync.command_audit(
                    namespace(project_path=str(project), config_path=str(config))
                )


if __name__ == "__main__":
    unittest.main()
