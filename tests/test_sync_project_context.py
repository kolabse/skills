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
        "stream_id": None,
        "all_streams": False,
        "snapshot_kind": "auto",
    }
    defaults.update(values)
    return argparse.Namespace(**defaults)


class SyncProjectContextTests(unittest.TestCase):
    def test_batch_capture_tracks_threads_and_only_appends_changed_chat(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            storage = root / "storage"
            config = root / "config.json"
            discovery = root / "discovery.json"
            batch = root / "batch.json"
            create_repository(project, "https://example.invalid/team/demo.git")
            context_sync.command_configure(
                namespace(
                    project_path=str(project),
                    storage_root=str(storage),
                    project_id="proj-batch-chats",
                    mode="metadata-only",
                    acknowledge_storage_policy=True,
                    config_path=str(config),
                )
            )
            thread_a = "019aaa-first-thread"
            thread_b = "019bbb-second-thread"
            discovery.write_text(
                json.dumps(
                    {
                        "threads": [
                            {"thread_id": thread_a, "source_revision": 100},
                            {"thread_id": thread_b, "source_revision": 200},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            initial_plan = context_sync.command_batch_plan(
                namespace(
                    project_path=str(project),
                    config_path=str(config),
                    input=str(discovery),
                    stdin=False,
                )
            )
            self.assertEqual(
                ["baseline", "baseline"],
                [item["action"] for item in initial_plan["threads"]],
            )
            batch.write_text(
                json.dumps(
                    {
                        "threads": [
                            {
                                "thread_id": thread_a,
                                "source_revision": 100,
                                "source_head_turn_id": "turn-a1",
                                "context": {"summary": "Completed feature A."},
                            },
                            {
                                "thread_id": thread_b,
                                "source_revision": 200,
                                "source_head_turn_id": "turn-b1",
                                "context": {"summary": "Designed feature B."},
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            first = context_sync.command_batch_capture(
                namespace(
                    project_path=str(project),
                    config_path=str(config),
                    input=str(batch),
                    stdin=False,
                )
            )
            self.assertEqual(2, first["checkpoint_count"])
            registry_text = Path(first["registry_path"]).read_text(encoding="utf-8")
            self.assertNotIn(thread_a, registry_text)
            self.assertNotIn(thread_b, registry_text)

            unchanged_plan = context_sync.command_batch_plan(
                namespace(
                    project_path=str(project),
                    config_path=str(config),
                    input=str(discovery),
                    stdin=False,
                )
            )
            self.assertEqual(
                ["unchanged", "unchanged"],
                [item["action"] for item in unchanged_plan["threads"]],
            )

            discovery.write_text(
                json.dumps(
                    {
                        "threads": [
                            {"thread_id": thread_a, "source_revision": 101},
                            {"thread_id": thread_b, "source_revision": 200},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            changed_plan = context_sync.command_batch_plan(
                namespace(
                    project_path=str(project),
                    config_path=str(config),
                    input=str(discovery),
                    stdin=False,
                )
            )
            self.assertEqual("delta", changed_plan["threads"][0]["action"])
            self.assertEqual(
                "after_previous_head", changed_plan["threads"][0]["read_scope"]
            )
            self.assertEqual("unchanged", changed_plan["threads"][1]["action"])
            batch.write_text(
                json.dumps(
                    {
                        "threads": [
                            {
                                "thread_id": thread_a,
                                "source_revision": 101,
                                "source_head_turn_id": "turn-a2",
                                "context": {
                                    "summary": "Verified the feature A follow-up.",
                                    "verifications": ["Targeted tests passed."],
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            second = context_sync.command_batch_capture(
                namespace(
                    project_path=str(project),
                    config_path=str(config),
                    input=str(batch),
                    stdin=False,
                )
            )
            self.assertEqual(1, second["checkpoint_count"])
            status = context_sync.command_status(
                namespace(project_path=str(project), config_path=str(config))
            )
            self.assertEqual(2, status["stream_count"])
            self.assertEqual(
                [1, 2], sorted(item["checkpoint_count"] for item in status["streams"])
            )

    def test_bind_thread_reuses_restored_stream_on_another_machine(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first_project = root / "first"
            second_project = root / "second"
            storage = root / "storage"
            first_config = root / "first-config.json"
            second_config = root / "second-config.json"
            payload = root / "payload.json"
            discovery = root / "discovery.json"
            remote = "https://example.invalid/team/demo.git"
            create_repository(first_project, remote)
            create_repository(second_project, remote)
            for project, config in (
                (first_project, first_config),
                (second_project, second_config),
            ):
                context_sync.command_configure(
                    namespace(
                        project_path=str(project),
                        storage_root=str(storage),
                        project_id="proj-bind-thread",
                        mode="metadata-only",
                        acknowledge_storage_policy=True,
                        config_path=str(config),
                    )
                )
            stream_id = "stream-" + "d" * 32
            payload.write_text(
                json.dumps({"summary": "Created the transferable baseline."}),
                encoding="utf-8",
            )
            context_sync.command_capture(
                namespace(
                    project_path=str(first_project),
                    config_path=str(first_config),
                    input=str(payload),
                    stdin=False,
                    stream_id=stream_id,
                )
            )
            context_sync.command_bind_thread(
                namespace(
                    project_path=str(second_project),
                    config_path=str(second_config),
                    thread_id="receiver-thread-id",
                    stream_id=stream_id,
                    source_revision="500",
                    source_head_turn_id="receiver-turn-1",
                )
            )
            discovery.write_text(
                json.dumps(
                    {
                        "threads": [
                            {
                                "thread_id": "receiver-thread-id",
                                "source_revision": "500",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            plan = context_sync.command_batch_plan(
                namespace(
                    project_path=str(second_project),
                    config_path=str(second_config),
                    input=str(discovery),
                    stdin=False,
                )
            )
            self.assertEqual("unchanged", plan["threads"][0]["action"])
            self.assertEqual(stream_id, plan["threads"][0]["stream_id"])

    def test_materialize_plan_creates_then_updates_one_task_per_stream(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            storage = root / "storage"
            config = root / "config.json"
            payload = root / "payload.json"
            discovery = root / "discovery.json"
            create_repository(project, "https://example.invalid/team/demo.git")
            context_sync.command_configure(
                namespace(
                    project_path=str(project),
                    storage_root=str(storage),
                    project_id="proj-materialize",
                    mode="metadata-only",
                    acknowledge_storage_policy=True,
                    config_path=str(config),
                )
            )
            stream_id = "stream-" + "f" * 32
            payload.write_text(
                json.dumps({"summary": "Prepared the restored feature."}),
                encoding="utf-8",
            )
            baseline = context_sync.command_capture(
                namespace(
                    project_path=str(project),
                    config_path=str(config),
                    input=str(payload),
                    stdin=False,
                    stream_id=stream_id,
                )
            )
            project_context = context_sync.command_capture(
                namespace(
                    project_path=str(project),
                    config_path=str(config),
                    input=str(payload),
                    stdin=False,
                    stream_id="project",
                )
            )
            discovery.write_text('{"threads": []}', encoding="utf-8")
            initial = context_sync.command_materialize_plan(
                namespace(
                    project_path=str(project),
                    config_path=str(config),
                    input=str(discovery),
                    stdin=False,
                )
            )
            self.assertEqual("create", initial["streams"][0]["action"])
            self.assertEqual(1, initial["stream_count"])
            self.assertEqual(
                project_context["checkpoint_id"],
                initial["project_context_checkpoint_id"],
            )

            context_sync.command_bind_thread(
                namespace(
                    project_path=str(project),
                    config_path=str(config),
                    thread_id="restored-task-id",
                    stream_id=stream_id,
                    checkpoint_id=baseline["checkpoint_id"],
                    source_revision=None,
                    source_head_turn_id=None,
                )
            )
            discovery.write_text(
                json.dumps({"threads": [{"thread_id": "restored-task-id"}]}),
                encoding="utf-8",
            )
            unchanged = context_sync.command_materialize_plan(
                namespace(
                    project_path=str(project),
                    config_path=str(config),
                    input=str(discovery),
                    stdin=False,
                )
            )
            self.assertEqual("unchanged", unchanged["streams"][0]["action"])
            self.assertEqual(0, unchanged["streams"][0]["target_index"])

            payload.write_text(
                json.dumps({"summary": "Added a short follow-up decision."}),
                encoding="utf-8",
            )
            delta = context_sync.command_capture(
                namespace(
                    project_path=str(project),
                    config_path=str(config),
                    input=str(payload),
                    stdin=False,
                    stream_id=stream_id,
                )
            )
            update = context_sync.command_materialize_plan(
                namespace(
                    project_path=str(project),
                    config_path=str(config),
                    input=str(discovery),
                    stdin=False,
                )
            )
            self.assertEqual("update", update["streams"][0]["action"])
            self.assertEqual(
                delta["checkpoint_id"],
                update["streams"][0]["latest_checkpoint_id"],
            )

    def test_materialize_plan_does_not_duplicate_an_undiscoverable_bound_task(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            storage = root / "storage"
            config = root / "config.json"
            payload = root / "payload.json"
            discovery = root / "discovery.json"
            create_repository(project, "https://example.invalid/team/demo.git")
            context_sync.command_configure(
                namespace(
                    project_path=str(project),
                    storage_root=str(storage),
                    project_id="proj-hidden-binding",
                    mode="metadata-only",
                    acknowledge_storage_policy=True,
                    config_path=str(config),
                )
            )
            stream_id = "stream-" + "c" * 32
            payload.write_text(
                json.dumps({"summary": "Prepared a baseline."}),
                encoding="utf-8",
            )
            context_sync.command_capture(
                namespace(
                    project_path=str(project),
                    config_path=str(config),
                    input=str(payload),
                    stdin=False,
                    stream_id=stream_id,
                )
            )
            context_sync.command_bind_thread(
                namespace(
                    project_path=str(project),
                    config_path=str(config),
                    thread_id="older-restored-task",
                    stream_id=stream_id,
                    source_revision=None,
                    source_head_turn_id=None,
                )
            )
            discovery.write_text('{"threads": []}', encoding="utf-8")
            plan = context_sync.command_materialize_plan(
                namespace(
                    project_path=str(project),
                    config_path=str(config),
                    input=str(discovery),
                    stdin=False,
                )
            )
            self.assertEqual("unavailable", plan["streams"][0]["action"])
            self.assertEqual(0, plan["counts"]["create"])

    def test_batch_rejects_two_local_threads_bound_to_one_stream(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            storage = root / "storage"
            config = root / "config.json"
            discovery = root / "discovery.json"
            create_repository(project, "https://example.invalid/team/demo.git")
            context_sync.command_configure(
                namespace(
                    project_path=str(project),
                    storage_root=str(storage),
                    project_id="proj-duplicate-stream",
                    mode="metadata-only",
                    acknowledge_storage_policy=True,
                    config_path=str(config),
                )
            )
            stream_id = "stream-" + "e" * 32
            discovery.write_text(
                json.dumps(
                    {
                        "threads": [
                            {
                                "thread_id": "thread-a",
                                "source_revision": 1,
                                "stream_id": stream_id,
                            },
                            {
                                "thread_id": "thread-b",
                                "source_revision": 2,
                                "stream_id": stream_id,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                context_sync.ContextSyncError,
                "Multiple local threads resolve to the same stream",
            ):
                context_sync.command_batch_plan(
                    namespace(
                        project_path=str(project),
                        config_path=str(config),
                        input=str(discovery),
                        stdin=False,
                    )
                )

    def test_chat_streams_restore_baseline_and_incremental_updates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            storage = root / "storage"
            config = root / "config.json"
            payload = root / "payload.json"
            create_repository(project, "https://example.invalid/team/demo.git")
            context_sync.command_configure(
                namespace(
                    project_path=str(project),
                    storage_root=str(storage),
                    project_id="proj-chat-streams",
                    mode="metadata-only",
                    acknowledge_storage_policy=True,
                    config_path=str(config),
                )
            )

            def capture(stream_id: str, value: dict[str, object]) -> dict[str, object]:
                payload.write_text(json.dumps(value), encoding="utf-8")
                return context_sync.command_capture(
                    namespace(
                        project_path=str(project),
                        config_path=str(config),
                        input=str(payload),
                        stdin=False,
                        stream_id=stream_id,
                    )
                )

            stream_a = "stream-" + "a" * 16
            stream_b = "stream-" + "b" * 16
            baseline = capture(
                stream_a,
                {
                    "summary": "Designed the cache invalidation feature in detail.",
                    "rationale": ["Preferred bounded invalidation over global eviction."],
                    "decisions": ["Keep invalidation synchronous."],
                },
            )
            delta = capture(
                stream_a,
                {
                    "summary": "Implemented the agreed cache adapter changes.",
                    "discussions": ["Reviewed the latency tradeoff."],
                    "actions": ["Added targeted unit coverage."],
                },
            )
            capture(
                stream_b,
                {"summary": "Started an independent authentication feature."},
            )

            status = context_sync.command_status(
                namespace(project_path=str(project), config_path=str(config))
            )
            restored = context_sync.command_restore(
                namespace(
                    project_path=str(project),
                    config_path=str(config),
                    stream_id=stream_a,
                )
            )
            restored_all = context_sync.command_restore(
                namespace(
                    project_path=str(project),
                    config_path=str(config),
                    all_streams=True,
                )
            )

            self.assertEqual("baseline", baseline["snapshot_kind"])
            self.assertEqual("delta", delta["snapshot_kind"])
            self.assertEqual([baseline["checkpoint_id"]], delta["parent_checkpoint_ids"])
            self.assertEqual(2, status["stream_count"])
            self.assertFalse(status["has_conflict"])
            self.assertEqual(2, restored["history_count"])
            self.assertEqual(
                ["baseline", "delta"],
                [item["snapshot_kind"] for item in restored["history"]],
            )
            self.assertEqual(2, restored_all["stream_count"])
            with self.assertRaisesRegex(
                context_sync.ContextSyncError, "Multiple checkpoint streams"
            ):
                context_sync.command_restore(
                    namespace(project_path=str(project), config_path=str(config))
                )

    def test_second_computer_appends_to_restored_chat_stream(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first_project = root / "work-project"
            second_project = root / "home-project"
            storage = root / "storage"
            first_config = root / "work-config.json"
            second_config = root / "home-config.json"
            payload = root / "payload.json"
            remote = "https://example.invalid/team/demo.git"
            create_repository(first_project, remote)
            create_repository(second_project, remote)
            stream_id = "stream-" + "c" * 16

            for project, config in (
                (first_project, first_config),
                (second_project, second_config),
            ):
                context_sync.command_configure(
                    namespace(
                        project_path=str(project),
                        storage_root=str(storage),
                        project_id="proj-two-computers",
                        mode="metadata-only",
                        acknowledge_storage_policy=True,
                        config_path=str(config),
                    )
                )

            payload.write_text(
                json.dumps(
                    {
                        "summary": "Completed the initial design and implementation plan.",
                        "rationale": ["Chose an append-only state model."],
                        "decisions": ["Use immutable checkpoints."],
                    }
                ),
                encoding="utf-8",
            )
            first = context_sync.command_capture(
                namespace(
                    project_path=str(first_project),
                    config_path=str(first_config),
                    input=str(payload),
                    stdin=False,
                    stream_id=stream_id,
                )
            )
            payload.write_text(
                json.dumps(
                    {
                        "summary": "Implemented the first slice on the second computer.",
                        "actions": ["Added the stream-aware restore path."],
                        "decisions": ["Keep later saves concise."],
                    }
                ),
                encoding="utf-8",
            )
            second = context_sync.command_capture(
                namespace(
                    project_path=str(second_project),
                    config_path=str(second_config),
                    input=str(payload),
                    stdin=False,
                    stream_id=stream_id,
                )
            )
            restored = context_sync.command_restore(
                namespace(
                    project_path=str(first_project),
                    config_path=str(first_config),
                    stream_id=stream_id,
                )
            )

            self.assertEqual([first["checkpoint_id"]], second["parent_checkpoint_ids"])
            self.assertEqual(2, restored["history_count"])
            self.assertEqual(
                2, len({item["machine_id"] for item in restored["history"]})
            )
            self.assertEqual(
                "Implemented the first slice on the second computer.",
                restored["context"]["summary"],
            )

    def test_checkpoint_graph_rejects_cross_stream_parents(self) -> None:
        parent_id = "checkpoint-" + "a" * 32
        child_id = "checkpoint-" + "b" * 32
        with self.assertRaisesRegex(
            context_sync.ContextSyncError, "crosses stream boundaries"
        ):
            context_sync.validate_checkpoint_graph(
                [
                    {
                        "schema_version": 2,
                        "checkpoint_id": parent_id,
                        "stream_id": "stream-" + "a" * 16,
                        "snapshot_kind": "baseline",
                        "parent_checkpoint_ids": [],
                    },
                    {
                        "schema_version": 2,
                        "checkpoint_id": child_id,
                        "stream_id": "stream-" + "b" * 16,
                        "snapshot_kind": "delta",
                        "parent_checkpoint_ids": [parent_id],
                    },
                ]
            )

    def test_checkpoint_loader_rejects_embedded_transcript_field(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ("checkpoint-" + "d" * 32 + ".json")
            checkpoint = {
                "schema_version": 2,
                "checkpoint_id": "checkpoint-" + "d" * 32,
                "project_id": "proj-private-context",
                "stream_id": "stream-" + "d" * 16,
                "snapshot_kind": "baseline",
                "machine_id": "machine-000000000000",
                "created_at": "2026-08-14T00:00:00Z",
                "parent_checkpoint_ids": [],
                "repository": {},
                "context": {"summary": "Safe continuation summary."},
                "transcript": ["raw chat content must not be accepted"],
            }
            checkpoint["content_sha256"] = context_sync.checkpoint_digest(checkpoint)
            path.write_text(json.dumps(checkpoint), encoding="utf-8")

            with self.assertRaisesRegex(
                context_sync.ContextSyncError, "unexpected fields"
            ):
                context_sync.load_checkpoint_file(path, "proj-private-context")

    def test_google_drive_snapshot_capture_and_restore(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            config = root / "profile/config.json"
            marker = root / "connector/project.json"
            snapshot = root / "snapshot"
            payload = root / "payload.json"
            create_repository(project, "https://example.invalid/team/demo.git")
            before = git(project, "status", "--porcelain=v1")

            prepared = context_sync.command_prepare_drive_marker(
                namespace(
                    project_path=str(project),
                    output=str(marker),
                    project_id="proj-google-drive",
                    acknowledge_storage_policy=True,
                )
            )
            configured = context_sync.command_configure(
                namespace(
                    project_path=str(project),
                    backend="google-drive",
                    storage_root=None,
                    project_id=prepared["project_id"],
                    marker_file=str(marker),
                    drive_project_folder_id="drive-project-folder",
                    drive_checkpoints_folder_id="drive-checkpoints-folder",
                    drive_marker_file_id="drive-marker-file",
                    mode="metadata-only",
                    acknowledge_storage_policy=True,
                    config_path=str(config),
                )
            )
            transport = context_sync.command_transport(
                namespace(project_path=str(project), config_path=str(config))
            )
            hydrated = context_sync.command_hydrate_drive(
                namespace(
                    project_path=str(project),
                    config_path=str(config),
                    marker_file=str(marker),
                    checkpoint_file=[],
                    output_root=str(snapshot),
                )
            )
            payload.write_text(
                json.dumps(
                    {
                        "summary": "Prepared the connector-backed handoff.",
                        "verifications": ["Drive snapshot tests passed."],
                    }
                ),
                encoding="utf-8",
            )
            captured = context_sync.command_capture(
                namespace(
                    project_path=str(project),
                    config_path=str(config),
                    snapshot_root=str(snapshot),
                    input=str(payload),
                    stdin=False,
                )
            )
            restored = context_sync.command_restore(
                namespace(
                    project_path=str(project),
                    config_path=str(config),
                    snapshot_root=str(snapshot),
                )
            )

            self.assertEqual("google-drive", configured["backend"])
            self.assertEqual("drive-project-folder", transport["drive_project_folder_id"])
            self.assertTrue(transport["requires_connector_hydration"])
            self.assertEqual(0, hydrated["checkpoint_count"])
            self.assertEqual("google-drive", captured["backend"])
            self.assertEqual(captured["checkpoint_id"], restored["checkpoint_id"])
            self.assertEqual(before, git(project, "status", "--porcelain=v1"))

    def test_google_drive_hydration_rejects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            config = root / "config.json"
            marker = root / "project.json"
            create_repository(project, "https://example.invalid/team/demo.git")
            context_sync.command_prepare_drive_marker(
                namespace(
                    project_path=str(project),
                    output=str(marker),
                    project_id="proj-drive-audit",
                    acknowledge_storage_policy=True,
                )
            )
            context_sync.command_configure(
                namespace(
                    project_path=str(project),
                    backend="google-drive",
                    storage_root=None,
                    project_id="proj-drive-audit",
                    marker_file=str(marker),
                    drive_project_folder_id="folder-project",
                    drive_checkpoints_folder_id="folder-checkpoints",
                    drive_marker_file_id="file-marker",
                    mode="metadata-only",
                    acknowledge_storage_policy=True,
                    config_path=str(config),
                )
            )
            downloaded = root / "provider-download.bin"
            checkpoint = {
                "schema_version": 1,
                "checkpoint_id": "checkpoint-" + "a" * 32,
                "project_id": "proj-drive-audit",
                "machine_id": "machine-000000000000",
                "created_at": "2026-08-14T00:00:00Z",
                "parent_checkpoint_ids": [],
                "repository": {},
                "context": {"summary": "Valid before tampering."},
            }
            checkpoint["content_sha256"] = "0" * 64
            downloaded.write_text(json.dumps(checkpoint), encoding="utf-8")

            with self.assertRaisesRegex(
                context_sync.ContextSyncError, "digest does not match"
            ):
                context_sync.command_hydrate_drive(
                    namespace(
                        project_path=str(project),
                        config_path=str(config),
                        marker_file=str(marker),
                        checkpoint_file=[str(downloaded)],
                        output_root=str(root / "snapshot"),
                    )
                )

    def test_google_drive_hydration_rejects_incomplete_history(self) -> None:
        checkpoint_id = "checkpoint-" + "a" * 32
        missing_id = "checkpoint-" + "b" * 32
        with self.assertRaisesRegex(
            context_sync.ContextSyncError, "missing parents"
        ):
            context_sync.validate_checkpoint_graph(
                [
                    {
                        "checkpoint_id": checkpoint_id,
                        "parent_checkpoint_ids": [missing_id],
                    }
                ]
            )

    def test_migrates_local_configuration_to_backend_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config.json"
            config.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "machine_id": "machine-000000000000",
                        "projects": [
                            {
                                "project_id": "proj-legacy-local",
                                "local_root": str(root / "project"),
                                "storage_root": str(root / "storage"),
                                "mode": "metadata-only",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            first = context_sync.command_migrate(namespace(config_path=str(config)))
            migrated = json.loads(config.read_text(encoding="utf-8"))
            second = context_sync.command_migrate(namespace(config_path=str(config)))

            self.assertTrue(first["changed"])
            self.assertEqual(2, migrated["version"])
            self.assertEqual("local-folder", migrated["projects"][0]["backend"])
            self.assertFalse(second["changed"])

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
