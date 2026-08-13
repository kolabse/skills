from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIRECTORY = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "operate-yandex-cloud"
    / "scripts"
)
sys.dont_write_bytecode = True
sys.path.insert(0, str(SCRIPT_DIRECTORY))

from cloud_skill import (  # noqa: E402
    CommandResult,
    ProjectConfig,
    configure_project,
    detect_toolsets,
    inspect_tools,
    load_config,
    local_config_path,
    run_preflight,
    version_at_least,
)


class ConfigTests(unittest.TestCase):
    def test_round_trip_project_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            expected = configure_project(
                project,
                "b1gcloud123",
                "b1gfolder456",
                "project-profile",
            )

            self.assertEqual(expected, load_config(project))
            content = (project / ".agents/operate-yandex-cloud/project.yaml").read_text(
                encoding="utf-8"
            )
            local_content = local_config_path(project).read_text(encoding="utf-8")
            ignore_content = (
                project / ".agents/operate-yandex-cloud/.gitignore"
            ).read_text(encoding="utf-8")
            self.assertIn("version: 3", content)
            self.assertNotIn("yc_profile", content)
            self.assertIn('yc_profile: "project-profile"', local_content)
            self.assertIn("/local.yaml", ignore_content)

    def test_loads_legacy_cloud_only_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            path = project / ".agents/operate-yandex-cloud/project.yaml"
            path.parent.mkdir(parents=True)
            path.write_text('version: 1\ncloud_id: "b1glegacy"\n', encoding="utf-8")

            self.assertEqual(
                ProjectConfig(cloud_id="b1glegacy", version=1),
                load_config(project),
            )

    def test_loads_legacy_profile_until_configuration_migrates_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            path = project / ".agents/operate-yandex-cloud/project.yaml"
            path.parent.mkdir(parents=True)
            path.write_text(
                'version: 2\ncloud_id: "b1glegacy"\n'
                'folder_id: "b1gfolder"\nyc_profile: "legacy-profile"\n',
                encoding="utf-8",
            )

            legacy = load_config(project)
            migrated = configure_project(
                project,
                legacy.cloud_id,
                legacy.folder_id,
                legacy.yc_profile,
            )

            project_content = path.read_text(encoding="utf-8")
            self.assertEqual("legacy-profile", migrated.yc_profile)
            self.assertNotIn("yc_profile", project_content)
            self.assertEqual("legacy-profile", load_config(project).yc_profile)

    def test_local_profile_overrides_legacy_project_profile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            path = project / ".agents/operate-yandex-cloud/project.yaml"
            path.parent.mkdir(parents=True)
            path.write_text(
                'version: 2\ncloud_id: "b1glegacy"\n'
                'yc_profile: "legacy-profile"\n',
                encoding="utf-8",
            )
            local_config_path(project).write_text(
                'version: 1\nyc_profile: "local-profile"\n',
                encoding="utf-8",
            )

            self.assertEqual("local-profile", load_config(project).yc_profile)

    def test_configuration_preserves_existing_local_ignore_rules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            ignore_path = project / ".agents/operate-yandex-cloud/.gitignore"
            ignore_path.parent.mkdir(parents=True)
            ignore_path.write_text("workstation-cache/\n", encoding="utf-8")

            configure_project(project, "b1gcloud123")

            self.assertEqual(
                ["workstation-cache/", "/local.yaml"],
                ignore_path.read_text(encoding="utf-8").splitlines(),
            )

    def test_rejects_invalid_identifier(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                configure_project(Path(directory), "NOT A CLOUD")


class ToolTests(unittest.TestCase):
    def test_detects_repository_toolsets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "terraform").mkdir()
            (project / "terraform/main.tf").write_text("", encoding="utf-8")
            (project / "ansible").mkdir()
            (project / "helm/chart").mkdir(parents=True)
            (project / "helm/chart/Chart.yaml").write_text("", encoding="utf-8")
            (project / ".gitlab-ci.yml").write_text("", encoding="utf-8")
            (project / "inspect.sh").write_text("jq '.items' data.json", encoding="utf-8")

            self.assertEqual(
                {
                    "base",
                    "terraform",
                    "ansible",
                    "helm",
                    "kubernetes",
                    "gitlab",
                    "data",
                },
                detect_toolsets([project]),
            )

    def test_compares_numeric_versions(self) -> None:
        self.assertTrue(version_at_least("1.15.0", "1.5.0"))
        self.assertTrue(version_at_least("3.12", "3.12.0"))
        self.assertFalse(version_at_least("1.4.9", "1.5.0"))

    def test_inspects_fake_cloud_terraform_and_kubectl_clis(self) -> None:
        outputs = {
            "git": "git version 2.45.1",
            "rg": "ripgrep 14.1.0",
            "ssh": "OpenSSH_9.6p1",
            "yc": "Yandex Cloud CLI 0.140.0",
            "terraform": "Terraform v1.8.5",
            "kubectl": '{"clientVersion":{"gitVersion":"v1.30.2"}}',
        }

        def runner(command, *, cwd=None):
            executable = command[0]
            return CommandResult(list(command), 0, outputs[executable])

        with patch("cloud_skill.shutil.which", side_effect=lambda name: f"/fake/{name}"):
            results = inspect_tools(
                {"base", "terraform", "kubernetes"},
                runner=runner,
            )

        statuses = {result.name: result.status for result in results}
        self.assertEqual("installed", statuses["yc"])
        self.assertEqual("installed", statuses["terraform"])
        self.assertEqual("installed", statuses["kubectl"])


class PreflightTests(unittest.TestCase):
    def test_preflight_validates_explicit_project_context(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            configure_project(project, "b1gcloud123", "b1gfolder456", "project")

            def runner(command, *, cwd=None):
                joined = " ".join(command)
                if "iam whoami" in joined:
                    output = json.dumps("subject-id")
                elif "cloud get" in joined:
                    output = json.dumps({"id": "b1gcloud123"})
                elif "folder get" in joined:
                    output = json.dumps(
                        {"id": "b1gfolder456", "cloud_id": "b1gcloud123"}
                    )
                elif command == ["yc", "config", "get", "cloud-id"]:
                    output = "different-cloud"
                elif command == ["yc", "config", "get", "folder-id"]:
                    output = "different-folder"
                elif command == ["yc", "config", "profile", "list"]:
                    output = "default ACTIVE"
                elif command == ["ssh-add", "-l"]:
                    output = "256 SHA256:fingerprint identity"
                else:
                    return CommandResult(list(command), 1, "unexpected command")
                return CommandResult(list(command), 0, output)

            with patch("cloud_skill.shutil.which", return_value="/fake/tool"):
                checks = run_preflight(project, [project], runner=runner)

            statuses = {check.name: check.status for check in checks}
            self.assertEqual("pass", statuses["project-config"])
            self.assertEqual("pass", statuses["yc-identity"])
            self.assertEqual("pass", statuses["cloud-access"])
            self.assertEqual("pass", statuses["folder-access"])
            self.assertEqual("warn", statuses["global-yc-context"])
            self.assertNotIn("fail", statuses.values())

    def test_preflight_checks_fake_kubernetes_and_terraform_contexts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            configure_project(project, "b1gcloud123")
            (project / "k8s").mkdir()
            terraform = project / "terraform/.terraform"
            terraform.mkdir(parents=True)
            (project / "terraform/main.tf").write_text("", encoding="utf-8")
            (terraform / "environment").write_text("staging\n", encoding="utf-8")

            def runner(command, *, cwd=None):
                joined = " ".join(command)
                if "iam whoami" in joined:
                    output = json.dumps("subject-id")
                elif "cloud get" in joined:
                    output = json.dumps({"id": "b1gcloud123"})
                elif command == ["yc", "config", "get", "cloud-id"]:
                    output = "b1gcloud123"
                elif command == ["yc", "config", "get", "folder-id"]:
                    output = ""
                elif command == ["yc", "config", "profile", "list"]:
                    output = "default ACTIVE"
                elif command == ["kubectl", "config", "current-context"]:
                    output = "yc-staging"
                elif command[:3] == ["kubectl", "config", "view"]:
                    output = "application"
                elif command == ["ssh-add", "-l"]:
                    output = "256 SHA256:fingerprint identity"
                else:
                    return CommandResult(list(command), 1, "unexpected command")
                return CommandResult(list(command), 0, output)

            with patch("cloud_skill.shutil.which", return_value="/fake/tool"):
                checks = run_preflight(project, [project], runner=runner)

            statuses = {check.name: check.status for check in checks}
            self.assertEqual("pass", statuses["kubernetes-context"])
            self.assertEqual("pass", statuses["terraform-workspace"])
            self.assertNotIn("fail", statuses.values())


if __name__ == "__main__":
    unittest.main()
