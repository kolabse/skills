from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIRECTORY = ROOT / "skills" / "sync-project-context" / "scripts"
sys.path.insert(0, str(SCRIPT_DIRECTORY))

import context_sync  # noqa: E402
import environment_sync  # noqa: E402


def namespace(**values: object) -> argparse.Namespace:
    defaults = {
        "config_path": None,
        "snapshot_root": None,
        "manifest_id": None,
        "local_state": None,
        "merge_heads": False,
        "acknowledge_environment_policy": False,
        "approve_local_rules": False,
        "stdin": False,
    }
    defaults.update(values)
    return argparse.Namespace(**defaults)


def git(path: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(path), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def initialize_repository(path: Path, *, agents: str | None = None) -> None:
    path.mkdir(parents=True)
    git(path, "init", "-q")
    git(path, "config", "user.name", "Environment Tests")
    git(path, "config", "user.email", "environment@example.invalid")
    git(path, "remote", "add", "origin", "https://example.invalid/shared/project.git")
    (path / "README.md").write_text("project\n", encoding="utf-8")
    if agents is not None:
        (path / "AGENTS.md").write_text(agents, encoding="utf-8")
    git(path, "add", ".")
    git(path, "commit", "-qm", "initial")


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


class EnvironmentSyncTests(unittest.TestCase):
    def test_notify_project_setting_is_captured_and_planned_without_token(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            destination = root / "destination"
            initialize_repository(source)
            initialize_repository(destination)
            storage = root / "storage"
            config = root / "config.json"
            self.configure(source, storage, config, "proj-notify-setting")
            self.configure(destination, storage, config, "proj-notify-setting")
            preferences = {
                "delivery_mode": "project-only",
                "chat_id": "-100123",
                "message_thread_id": "42",
            }
            input_path = root / "input.json"
            write_json(
                input_path,
                {
                    "settings": [
                        {
                            "id": "notify-via-telegram",
                            "scope": "project",
                            "schema_version": "1",
                            "preferences": preferences,
                            "required": True,
                        }
                    ]
                },
            )
            captured = environment_sync.command_capture(
                namespace(
                    project_path=str(source),
                    input=str(input_path),
                    config_path=str(config),
                    acknowledge_environment_policy=True,
                )
            )
            manifest = json.loads(Path(captured["path"]).read_text(encoding="utf-8"))
            self.assertEqual(preferences, manifest["settings"][0]["preferences"])
            self.assertNotIn("token", json.dumps(manifest).lower())

            planned = environment_sync.command_plan(
                namespace(project_path=str(destination), config_path=str(config))
            )
            action = planned["actions"][0]
            self.assertEqual("manual_apply_required", action["status"])
            self.assertEqual(preferences, action["preferences"])

            local_state = root / "local-state.json"
            write_json(
                local_state,
                {
                    "settings": [
                        {
                            "id": "notify-via-telegram",
                            "schema_version": "1",
                            "preferences_sha256": context_sync.canonical_digest(
                                preferences
                            ),
                        }
                    ]
                },
            )
            satisfied = environment_sync.command_plan(
                namespace(
                    project_path=str(destination),
                    config_path=str(config),
                    local_state=str(local_state),
                )
            )
            self.assertEqual("satisfied_locally", satisfied["actions"][0]["status"])

    def test_notify_project_setting_rejects_invalid_mode_and_secret_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            initialize_repository(project)
            input_path = root / "input.json"
            base = {
                "id": "notify-via-telegram",
                "scope": "project",
                "schema_version": "1",
                "required": True,
            }
            for preferences in (
                {"delivery_mode": "unknown", "chat_id": "123"},
                {
                    "delivery_mode": "project-only",
                    "chat_id": "123",
                    "bot_token": "123456:fixture-token",
                },
            ):
                with self.subTest(preferences=preferences):
                    write_json(
                        input_path,
                        {"settings": [{**base, "preferences": preferences}]},
                    )
                    with self.assertRaises(context_sync.ContextSyncError):
                        environment_sync.command_inspect(
                            namespace(project_path=str(project), input=str(input_path))
                        )

            write_json(
                input_path,
                {
                    "settings": [
                        {
                            **base,
                            "scope": "user",
                            "preferences": {
                                "delivery_mode": "project-only",
                                "chat_id": "123",
                            },
                        }
                    ]
                },
            )
            with self.assertRaises(context_sync.ContextSyncError):
                environment_sync.command_inspect(
                    namespace(project_path=str(project), input=str(input_path))
                )

    def configure(
        self, project: Path, storage: Path, config: Path, project_id: str
    ) -> None:
        context_sync.command_configure(
            namespace(
                project_path=str(project),
                storage_root=str(storage),
                project_id=project_id,
                backend="local-folder",
                mode="metadata-only",
                acknowledge_storage_policy=True,
                config_path=str(config),
            )
        )

    def test_inspect_uses_git_as_source_of_truth(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            initialize_repository(project, agents="# Tracked rules\n")
            input_path = root / "input.json"
            write_json(
                input_path,
                {"rules": [{"id": "project-rules", "path": "AGENTS.md", "scope": "project"}]},
            )

            result = environment_sync.command_inspect(
                namespace(project_path=str(project), input=str(input_path))
            )

            rule = result["environment"]["rules"][0]
            self.assertEqual("satisfied_by_git", rule["classification"])
            self.assertNotIn("content", rule)
            self.assertTrue(rule["git"]["blob_oid"])

    def test_inspect_captures_only_explicit_untracked_agents_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            initialize_repository(project)
            (project / "AGENTS.md").write_text("# Local rules\n", encoding="utf-8")
            input_path = root / "input.json"
            write_json(
                input_path,
                {"rules": [{"id": "project-rules", "path": "AGENTS.md", "scope": "project"}]},
            )

            result = environment_sync.command_inspect(
                namespace(project_path=str(project), input=str(input_path))
            )

            rule = result["environment"]["rules"][0]
            self.assertEqual("local_portable", rule["classification"])
            self.assertEqual("# Local rules\n", rule["content"])

    def test_inspect_rejects_modified_tracked_rule(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            initialize_repository(project, agents="# Tracked rules\n")
            (project / "AGENTS.md").write_text("# Unpublished rules\n", encoding="utf-8")
            input_path = root / "input.json"
            write_json(
                input_path,
                {"rules": [{"id": "project-rules", "path": "AGENTS.md", "scope": "project"}]},
            )

            with self.assertRaisesRegex(
                context_sync.ContextSyncError, "unpublished changes"
            ):
                environment_sync.command_inspect(
                    namespace(project_path=str(project), input=str(input_path))
                )

    def test_tracked_dependency_declaration_is_covered_by_git(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            initialize_repository(project)
            input_path = root / "input.json"
            write_json(
                input_path,
                {
                    "skills": [
                        {
                            "id": "sync-project-context",
                            "version": "1.0.0",
                            "required": True,
                            "source": "kolabse-skills",
                            "declaration_path": "README.md",
                        }
                    ]
                },
            )

            result = environment_sync.command_inspect(
                namespace(project_path=str(project), input=str(input_path))
            )

            self.assertEqual([], result["environment"]["skills"])
            coverage = result["environment"]["git_coverage"][0]
            self.assertEqual("skills", coverage["category"])
            self.assertEqual("README.md", coverage["path"])
            self.assertTrue(coverage["blob_oid"])

    def test_capture_plan_and_apply_create_only_missing_rule(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            destination = root / "destination"
            initialize_repository(source)
            initialize_repository(destination)
            (source / "AGENTS.md").write_text("# Portable rules\n", encoding="utf-8")
            storage = root / "storage"
            config = root / "config.json"
            project_id = "proj-environment-test"
            self.configure(source, storage, config, project_id)
            self.configure(destination, storage, config, project_id)
            input_path = root / "input.json"
            write_json(
                input_path,
                {
                    "rules": [{"id": "project-rules", "path": "AGENTS.md", "scope": "project"}],
                    "skills": [{"id": "sync-project-context", "version": "1.0.0", "required": True, "source": "kolabse-skills"}],
                    "plugins": [{"id": "google-drive", "version": "0.1.0", "required": True}],
                    "settings": [{"id": "project-preferences", "scope": "project", "schema_version": "1", "preferences": {"mode": "safe"}, "required": True}],
                },
            )
            captured = environment_sync.command_capture(
                namespace(
                    project_path=str(source),
                    input=str(input_path),
                    config_path=str(config),
                    acknowledge_environment_policy=True,
                )
            )

            planned = environment_sync.command_plan(
                namespace(project_path=str(destination), config_path=str(config))
            )
            statuses = {(item["category"], item["id"]): item["status"] for item in planned["actions"]}
            self.assertEqual("apply_local_rule", statuses[("rules", "project-rules")])
            self.assertEqual("install_required", statuses[("skills", "sync-project-context")])
            self.assertEqual("install_required", statuses[("plugins", "google-drive")])
            self.assertEqual("manual_apply_required", statuses[("settings", "project-preferences")])

            applied = environment_sync.command_apply(
                namespace(
                    project_path=str(destination),
                    config_path=str(config),
                    manifest_id=captured["manifest_id"],
                    approve_local_rules=True,
                )
            )
            self.assertEqual("# Portable rules\n", (destination / "AGENTS.md").read_text(encoding="utf-8"))
            self.assertEqual([{"id": "project-rules", "path": "AGENTS.md"}], applied["local_rules_created"])
            self.assertIn("?? AGENTS.md", git(destination, "status", "--short"))

    def test_local_state_can_satisfy_declarative_requirements(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            initialize_repository(project)
            storage = root / "storage"
            config = root / "config.json"
            self.configure(project, storage, config, "proj-local-state")
            preferences = {"mode": "safe"}
            input_path = root / "input.json"
            write_json(
                input_path,
                {
                    "skills": [{"id": "portable-skill", "version": "1", "required": True}],
                    "plugins": [{"id": "portable-plugin", "version": "2", "required": True}],
                    "settings": [{"id": "prefs", "scope": "project", "schema_version": "3", "preferences": preferences, "required": True}],
                },
            )
            environment_sync.command_capture(
                namespace(
                    project_path=str(project), input=str(input_path), config_path=str(config),
                    acknowledge_environment_policy=True,
                )
            )
            local_state = root / "local-state.json"
            write_json(
                local_state,
                {
                    "skills": [{"id": "portable-skill", "version": "1"}],
                    "plugins": [{"id": "portable-plugin", "version": "2", "connected": True}],
                    "settings": [{"id": "prefs", "schema_version": "3", "preferences_sha256": context_sync.canonical_digest(preferences)}],
                },
            )

            planned = environment_sync.command_plan(
                namespace(
                    project_path=str(project), config_path=str(config), local_state=str(local_state)
                )
            )

            self.assertEqual({"satisfied_locally": 3}, planned["counts"])

    def test_plan_never_overwrites_git_owned_rule(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            destination = root / "destination"
            initialize_repository(source)
            initialize_repository(destination, agents="# Destination Git rule\n")
            (source / "AGENTS.md").write_text("# Portable rules\n", encoding="utf-8")
            storage = root / "storage"
            config = root / "config.json"
            project_id = "proj-git-conflict"
            self.configure(source, storage, config, project_id)
            self.configure(destination, storage, config, project_id)
            input_path = root / "input.json"
            write_json(input_path, {"rules": [{"id": "rules", "path": "AGENTS.md", "scope": "project"}]})
            environment_sync.command_capture(
                namespace(
                    project_path=str(source), input=str(input_path), config_path=str(config),
                    acknowledge_environment_policy=True,
                )
            )

            planned = environment_sync.command_plan(
                namespace(project_path=str(destination), config_path=str(config))
            )

            self.assertEqual("approval_required", planned["actions"][0]["status"])
            self.assertIn("Git now owns", planned["actions"][0]["reason"])

    def test_rule_and_preferences_secret_patterns_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            initialize_repository(project)
            (project / "AGENTS.md").write_text("api_key=abcdefgh12345678\n", encoding="utf-8")
            input_path = root / "input.json"
            write_json(input_path, {"rules": [{"id": "rules", "path": "AGENTS.md", "scope": "project"}]})
            with self.assertRaisesRegex(context_sync.ContextSyncError, "possible secret"):
                environment_sync.command_inspect(
                    namespace(project_path=str(project), input=str(input_path))
                )

            (project / "AGENTS.md").unlink()
            write_json(
                input_path,
                {"settings": [{"id": "prefs", "scope": "project", "schema_version": "1", "preferences": {"access_token": "hidden"}, "required": True}]},
            )
            with self.assertRaisesRegex(context_sync.ContextSyncError, "forbidden"):
                environment_sync.command_inspect(
                    namespace(project_path=str(project), input=str(input_path))
                )

    def test_audit_rejects_tampered_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            initialize_repository(project)
            storage = root / "storage"
            config = root / "config.json"
            self.configure(project, storage, config, "proj-audit-environment")
            input_path = root / "input.json"
            write_json(input_path, {"plugins": [{"id": "google-drive", "version": "1", "required": False}]})
            captured = environment_sync.command_capture(
                namespace(
                    project_path=str(project), input=str(input_path), config_path=str(config),
                    acknowledge_environment_policy=True,
                )
            )
            manifest_path = Path(captured["path"])
            value = json.loads(manifest_path.read_text(encoding="utf-8"))
            value["plugins"][0]["version"] = "2"
            write_json(manifest_path, value)

            with self.assertRaisesRegex(context_sync.ContextSyncError, "digest does not match"):
                environment_sync.command_audit(
                    namespace(project_path=str(project), config_path=str(config))
                )

    def test_google_drive_snapshot_hydrates_environment_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            destination = root / "destination"
            initialize_repository(source)
            initialize_repository(destination)
            storage = root / "storage"
            source_config = root / "source-config.json"
            destination_config = root / "destination-config.json"
            project_id = "proj-drive-environment"
            self.configure(source, storage, source_config, project_id)
            input_path = root / "input.json"
            write_json(
                input_path,
                {"plugins": [{"id": "google-drive", "version": "1", "required": True}]},
            )
            captured = environment_sync.command_capture(
                namespace(
                    project_path=str(source), input=str(input_path), config_path=str(source_config),
                    acknowledge_environment_policy=True,
                )
            )
            marker = storage / project_id / "project.json"
            context_sync.command_configure(
                namespace(
                    project_path=str(destination),
                    backend="google-drive",
                    marker_file=str(marker),
                    project_id=project_id,
                    drive_project_folder_id="drive-project",
                    drive_checkpoints_folder_id="drive-checkpoints",
                    drive_marker_file_id="drive-marker",
                    mode="metadata-only",
                    acknowledge_storage_policy=True,
                    config_path=str(destination_config),
                )
            )
            snapshot = root / "snapshot"
            context_sync.command_hydrate_drive(
                namespace(
                    project_path=str(destination), config_path=str(destination_config),
                    output_root=str(snapshot), marker_file=str(marker), checkpoint_file=[],
                )
            )

            hydrated = environment_sync.command_hydrate(
                namespace(
                    project_path=str(destination), config_path=str(destination_config),
                    snapshot_root=str(snapshot), environment_file=[captured["path"]],
                )
            )
            audited = environment_sync.command_audit(
                namespace(
                    project_path=str(destination), config_path=str(destination_config),
                    snapshot_root=str(snapshot),
                )
            )

            self.assertEqual(1, hydrated["manifest_count"])
            self.assertTrue(audited["ok"])


if __name__ == "__main__":
    unittest.main()
