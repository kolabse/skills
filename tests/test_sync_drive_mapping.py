from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock


SCRIPT_DIRECTORY = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "sync-project-context"
    / "scripts"
)
sys.dont_write_bytecode = True
sys.path.insert(0, str(SCRIPT_DIRECTORY))

import context_sync  # noqa: E402


FOLDER_MIME = "application/vnd.google-apps.folder"
JSON_MIME = "application/json"


def git(path: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(path), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def create_repository(path: Path) -> None:
    path.mkdir(parents=True)
    git(path, "init", "--initial-branch=main")
    git(path, "config", "user.name", "Drive Mapping Test")
    git(path, "config", "user.email", "drive-mapping@example.invalid")
    (path / "tracked.txt").write_text("initial\n", encoding="utf-8")
    git(path, "add", "tracked.txt")
    git(path, "commit", "-m", "initial")
    git(path, "remote", "add", "origin", "https://example.invalid/team/demo.git")


def namespace(**values: object) -> argparse.Namespace:
    defaults: dict[str, object] = {
        "config_path": None,
        "json": True,
        "project_id": None,
        "mapping_plan": None,
        "readback_inventory": None,
        "marker_file": None,
        "storage_root": None,
        "drive_project_folder_id": None,
        "drive_checkpoints_folder_id": None,
        "drive_marker_file_id": None,
        "mode": "metadata-only",
    }
    defaults.update(values)
    return argparse.Namespace(**defaults)


def drive_object(
    object_id: str,
    title: str,
    *,
    parent_id: str,
    folder: bool,
    visibility: str = "not_shared",
) -> dict[str, object]:
    return {
        "id": object_id,
        "title": title,
        "mime_type": FOLDER_MIME if folder else JSON_MIME,
        "parent_ids": [parent_id],
        "file_or_folder": "folder" if folder else "file",
        "drive_id": None,
        "shared": False,
        "source_visibility_status": visibility,
        "can_list_children": True if folder else None,
        "can_download": None if folder else True,
    }


def complete_listing(children: list[dict[str, object]]) -> dict[str, object]:
    return {
        "complete": True,
        "page_count": 1,
        "terminal_page_token": None,
        "children": children,
    }


def project_inventory(
    root: Path,
    project: Path,
    project_id: str,
    suffix: str,
    parent_id: str = "drive-context-parent",
) -> tuple[dict[str, object], Path]:
    project_folder_id = f"drive-project-{suffix}"
    marker_id = f"drive-marker-{suffix}"
    checkpoints_id = f"drive-checkpoints-{suffix}"
    marker_path = root / f"project-{suffix}.json"
    marker = context_sync.project_marker(project, project_id)
    marker["created_at"] = "2026-08-27T12:00:00Z"
    marker_path.write_text(json.dumps(marker), encoding="utf-8")
    marker_sha = hashlib.sha256(marker_path.read_bytes()).hexdigest()
    marker_metadata = drive_object(
        marker_id, "project.json", parent_id=project_folder_id, folder=False
    )
    checkpoints_metadata = drive_object(
        checkpoints_id,
        "checkpoints",
        parent_id=project_folder_id,
        folder=True,
    )
    entry = {
        "folder": drive_object(
            project_folder_id,
            project_id,
            parent_id=parent_id,
            folder=True,
        ),
        "listing": complete_listing([marker_metadata, checkpoints_metadata]),
        "marker": {
            "file_id": marker_id,
            "path": str(marker_path),
            "sha256": marker_sha,
        },
        "checkpoints_listing": complete_listing([]),
    }
    return entry, marker_path


def drive_parent(parent_id: str = "drive-context-parent") -> dict[str, object]:
    return drive_object(
        parent_id,
        "Codex Project Context",
        parent_id="root",
        folder=True,
    )


def inventory_document(
    projects: list[dict[str, object]],
    *,
    observation_digit: str = "1",
    observed_at: str | None = None,
) -> dict[str, object]:
    parent = drive_parent()
    namespace = {
        "parent": parent,
        "listing": complete_listing([item["folder"] for item in projects]),
        "projects": projects,
    }
    return multi_parent_inventory(
        [namespace],
        observation_digit=observation_digit,
        observed_at=observed_at,
    )


def multi_parent_inventory(
    namespaces: list[dict[str, object]],
    *,
    observation_digit: str = "1",
    observed_at: str | None = None,
) -> dict[str, object]:
    if observed_at is None:
        observed_at = (
            datetime.now(timezone.utc) - timedelta(seconds=30)
        ).isoformat(timespec="seconds").replace("+00:00", "Z")
    return {
        "schema_version": 1,
        "observation_id": "observation-" + observation_digit * 32,
        "observed_at": observed_at,
        "parent_search": complete_listing([item["parent"] for item in namespaces]),
        "namespaces": namespaces,
    }


class SyncDriveMappingTests(unittest.TestCase):
    def write_inventory(
        self, root: Path, value: dict[str, object], name: str = "drive-inventory.json"
    ) -> Path:
        path = root / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def plan(
        self, root: Path, project: Path, inventory: dict[str, object]
    ) -> tuple[dict[str, object], Path]:
        inventory_path = self.write_inventory(root, inventory)
        output = root / "mapping-plan.json"
        result = context_sync.command_drive_mapping_plan(
            namespace(
                project_path=str(project),
                inventory=str(inventory_path),
                output=str(output),
            )
        )
        return result, output

    def test_unique_fingerprint_match_reuses_verified_drive_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "clone-b"
            create_repository(project)
            existing, marker_path = project_inventory(
                root, project, "proj-existing-drive", "existing"
            )

            plan, output = self.plan(root, project, inventory_document([existing]))

            self.assertEqual("ready", plan["status"])
            self.assertEqual("reuse", plan["action"])
            self.assertEqual(
                {
                    "project_id": "proj-existing-drive",
                    "drive_parent_folder_id": "drive-context-parent",
                    "drive_project_folder_id": "drive-project-existing",
                    "drive_checkpoints_folder_id": "drive-checkpoints-existing",
                    "drive_marker_file_id": "drive-marker-existing",
                    "marker_file": str(marker_path.resolve()),
                    "marker_sha256": hashlib.sha256(marker_path.read_bytes()).hexdigest(),
                },
                plan["mapping"],
            )
            self.assertEqual(plan, json.loads(output.read_text(encoding="utf-8")))

    def test_zero_match_seals_one_deterministic_creation_plan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "clone-b"
            create_repository(project)
            inventory = inventory_document([])

            first, first_path = self.plan(root, project, inventory)
            second_path = root / "mapping-plan-second.json"
            second = context_sync.command_drive_mapping_plan(
                namespace(
                    project_path=str(project),
                    inventory=str(root / "drive-inventory.json"),
                    output=str(second_path),
                )
            )

            self.assertEqual("create", first["action"])
            self.assertEqual(first["mapping"]["project_id"], second["mapping"]["project_id"])
            self.assertEqual(first["plan_sha256"], second["plan_sha256"])

            marker_path = root / "prepared-project.json"
            prepared = context_sync.command_prepare_drive_marker(
                namespace(
                    project_path=str(project),
                    output=str(marker_path),
                    mapping_plan=str(first_path),
                    acknowledge_storage_policy=True,
                )
            )
            self.assertEqual(first["mapping"]["project_id"], prepared["project_id"])

    def test_empty_drive_plans_parent_creation_before_project_creation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "clone-b"
            create_repository(project)

            plan, _ = self.plan(root, project, multi_parent_inventory([]))

            self.assertEqual("ready", plan["status"])
            self.assertEqual("create-parent", plan["action"])
            self.assertEqual(
                {"parent_title": "Codex Project Context"}, plan["mapping"]
            )

    def test_duplicate_matches_and_untrusted_visibility_block_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "clone-b"
            create_repository(project)
            first, _ = project_inventory(root, project, "proj-duplicate-a", "a")
            second, _ = project_inventory(root, project, "proj-duplicate-b", "b")

            duplicate, duplicate_path = self.plan(
                root, project, inventory_document([first, second])
            )
            self.assertEqual("blocked", duplicate["status"])
            self.assertIn("duplicate-mapping", duplicate["blockers"])

            untrusted = inventory_document([first])
            untrusted["namespaces"][0]["parent"]["source_visibility_status"] = "access_not_verified"
            blocked, blocked_path = self.plan(root, project, untrusted)
            self.assertEqual("blocked", blocked["status"])
            self.assertIn("untrusted-drive-structure", blocked["blockers"])
            self.assertTrue(duplicate_path.is_file())
            self.assertTrue(blocked_path.is_file())

    def test_incomplete_listing_and_unexpected_checkpoint_child_block(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "clone-b"
            create_repository(project)
            existing, _ = project_inventory(
                root, project, "proj-incomplete", "incomplete"
            )
            incomplete = inventory_document([existing])
            incomplete["namespaces"][0]["listing"]["complete"] = False
            incomplete["namespaces"][0]["listing"]["terminal_page_token"] = "next-page"

            plan, _ = self.plan(root, project, incomplete)
            self.assertEqual("blocked", plan["status"])
            self.assertEqual(["untrusted-drive-structure"], plan["blockers"])

            unexpected = inventory_document([existing])
            existing["checkpoints_listing"] = complete_listing(
                [
                    drive_object(
                        "drive-unexpected-file",
                        "notes.txt",
                        parent_id="drive-checkpoints-incomplete",
                        folder=False,
                    )
                ]
            )
            blocked, _ = self.plan(root, project, unexpected)
            self.assertEqual("blocked", blocked["status"])

    def test_discovery_rejects_noncanonical_marker_and_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "clone-b"
            create_repository(project)
            existing, marker_path = project_inventory(
                root, project, "proj-strict-marker", "strict"
            )
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
            marker["unexpected"] = "field"
            marker_path.write_text(json.dumps(marker), encoding="utf-8")
            existing["marker"]["sha256"] = hashlib.sha256(
                marker_path.read_bytes()
            ).hexdigest()

            extra_field, _ = self.plan(root, project, inventory_document([existing]))
            self.assertEqual("blocked", extra_field["status"])

            marker.pop("unexpected")
            marker_path.write_text(json.dumps(marker), encoding="utf-8")
            existing["marker"]["sha256"] = "0" * 64
            wrong_digest, _ = self.plan(root, project, inventory_document([existing]))
            self.assertEqual("blocked", wrong_digest["status"])

    def test_discovery_parses_the_same_marker_bytes_that_were_hashed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "clone-b"
            create_repository(project)
            _, marker_path = project_inventory(
                root, project, "proj-one-read", "one-read"
            )
            digest = hashlib.sha256(marker_path.read_bytes()).hexdigest()

            with mock.patch.object(
                Path,
                "read_text",
                side_effect=AssertionError("marker must not be read twice"),
            ):
                marker = context_sync.load_discovery_project_marker(
                    marker_path, digest
                )

            self.assertEqual("proj-one-read", marker["project_id"])

    def test_marker_creation_requires_untampered_zero_match_plan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "clone-b"
            create_repository(project)
            marker_path = root / "prepared.json"

            with self.assertRaisesRegex(
                context_sync.ContextSyncError, "zero-match --mapping-plan"
            ):
                context_sync.command_prepare_drive_marker(
                    namespace(
                        project_path=str(project),
                        output=str(marker_path),
                        acknowledge_storage_policy=True,
                    )
            )
            self.assertFalse(marker_path.exists())

            plan, plan_path = self.plan(root, project, inventory_document([]))
            tampered = dict(plan)
            tampered["mapping"] = dict(plan["mapping"])
            tampered["mapping"]["project_id"] = "proj-tampered"
            plan_path.write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaisesRegex(
                context_sync.ContextSyncError, "digest does not match"
            ):
                context_sync.command_prepare_drive_marker(
                    namespace(
                        project_path=str(project),
                        output=str(marker_path),
                        mapping_plan=str(plan_path),
                        acknowledge_storage_policy=True,
                    )
                )
            self.assertFalse(marker_path.exists())

    def test_all_same_named_root_folders_are_inspected_before_deciding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "clone-b"
            create_repository(project)
            existing, _ = project_inventory(
                root,
                project,
                "proj-in-second-parent",
                "second-parent",
                parent_id="drive-context-parent-b",
            )
            first_parent = {
                "parent": drive_parent("drive-context-parent-a"),
                "listing": complete_listing([]),
                "projects": [],
            }
            second_parent = {
                "parent": drive_parent("drive-context-parent-b"),
                "listing": complete_listing([existing["folder"]]),
                "projects": [existing],
            }

            reuse, _ = self.plan(
                root, project, multi_parent_inventory([first_parent, second_parent])
            )
            self.assertEqual("reuse", reuse["action"])
            self.assertEqual(
                "drive-context-parent-b",
                reuse["mapping"]["drive_parent_folder_id"],
            )

            ambiguous, _ = self.plan(
                root, project, multi_parent_inventory([first_parent, {
                    "parent": drive_parent("drive-context-parent-b"),
                    "listing": complete_listing([]),
                    "projects": [],
                }])
            )
            self.assertEqual("blocked", ambiguous["status"])
            self.assertIn("ambiguous-parent", ambiguous["blockers"])

    def test_reuse_configuration_requires_matching_fresh_readback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "clone-b"
            config = root / "config.json"
            create_repository(project)
            existing, marker_path = project_inventory(
                root, project, "proj-readback", "readback"
            )
            inventory = inventory_document([existing])
            _, plan_path = self.plan(root, project, inventory)

            with self.assertRaisesRegex(
                context_sync.ContextSyncError, "fresh --readback-inventory"
            ):
                context_sync.command_configure(
                    namespace(
                        project_path=str(project),
                        backend="google-drive",
                        mapping_plan=str(plan_path),
                        acknowledge_storage_policy=True,
                        config_path=str(config),
                    )
                )

            with self.assertRaisesRegex(
                context_sync.ContextSyncError, "newer Drive observation"
            ):
                context_sync.command_configure(
                    namespace(
                        project_path=str(project),
                        backend="google-drive",
                        mapping_plan=str(plan_path),
                        readback_inventory=str(root / "drive-inventory.json"),
                        acknowledge_storage_policy=True,
                        config_path=str(config),
                    )
                )

            marker = json.loads(marker_path.read_text(encoding="utf-8"))
            marker["repository_fingerprint"] = "0" * 64
            marker_path.write_text(json.dumps(marker), encoding="utf-8")
            existing["marker"]["sha256"] = hashlib.sha256(
                marker_path.read_bytes()
            ).hexdigest()
            inventory["observation_id"] = "observation-" + "2" * 32
            inventory["observed_at"] = context_sync.utc_now()
            changed_inventory = self.write_inventory(
                root, inventory, "changed-readback.json"
            )
            with self.assertRaisesRegex(
                context_sync.ContextSyncError, "no longer matches"
            ):
                context_sync.command_configure(
                    namespace(
                        project_path=str(project),
                        backend="google-drive",
                        mapping_plan=str(plan_path),
                        readback_inventory=str(changed_inventory),
                        acknowledge_storage_policy=True,
                        config_path=str(config),
                    )
                )

    def test_reused_mapping_restores_existing_v2_stream_and_title(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "clone-b"
            config = root / "machine-b-config.json"
            snapshot = root / "snapshot"
            create_repository(project)
            existing, marker_path = project_inventory(
                root, project, "proj-round-trip", "round-trip"
            )
            checkpoint_id = "checkpoint-" + "a" * 32
            stream_id = "stream-" + "b" * 32
            checkpoint_path = root / f"{checkpoint_id}.json"
            checkpoint = {
                "schema_version": 2,
                "checkpoint_id": checkpoint_id,
                "project_id": "proj-round-trip",
                "stream_id": stream_id,
                "snapshot_kind": "baseline",
                "machine_id": "machine-000000000000",
                "created_at": "2026-08-27T12:01:00Z",
                "parent_checkpoint_ids": [],
                "repository": context_sync.repository_state(project, "metadata-only"),
                "context": {
                    "summary": "Saved on computer A.",
                    "chat_title": "Exact saved chat title",
                    "decisions": [],
                    "actions": [],
                    "verifications": [],
                    "blockers": [],
                    "open_questions": [],
                    "next_steps": [],
                    "relevant_paths": [],
                },
            }
            checkpoint["content_sha256"] = context_sync.checkpoint_digest(checkpoint)
            checkpoint_path.write_text(json.dumps(checkpoint), encoding="utf-8")
            existing["checkpoints_listing"] = complete_listing(
                [
                    drive_object(
                        "drive-checkpoint-a",
                        checkpoint_path.name,
                        parent_id="drive-checkpoints-round-trip",
                        folder=False,
                    )
                ]
            )

            plan, plan_path = self.plan(root, project, inventory_document([existing]))
            fresh_inventory = inventory_document(
                [existing],
                observation_digit="2",
                observed_at=context_sync.utc_now(),
            )
            fresh_inventory_path = self.write_inventory(
                root, fresh_inventory, "fresh-readback.json"
            )
            configured = context_sync.command_configure(
                namespace(
                    project_path=str(project),
                    backend="google-drive",
                    mapping_plan=str(plan_path),
                    readback_inventory=str(fresh_inventory_path),
                    acknowledge_storage_policy=True,
                    config_path=str(config),
                )
            )
            context_sync.command_hydrate_drive(
                namespace(
                    project_path=str(project),
                    config_path=str(config),
                    marker_file=str(marker_path),
                    checkpoint_file=[str(checkpoint_path)],
                    output_root=str(snapshot),
                )
            )
            restored = context_sync.command_restore(
                namespace(
                    project_path=str(project),
                    config_path=str(config),
                    snapshot_root=str(snapshot),
                    stream_id=stream_id,
                    checkpoint_id=None,
                    all_streams=False,
                )
            )

            self.assertEqual("proj-round-trip", configured["project_id"])
            self.assertEqual("Exact saved chat title", restored["chat_title"])
            self.assertEqual(stream_id, restored["stream_id"])


if __name__ == "__main__":
    unittest.main()
