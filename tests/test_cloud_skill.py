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
    load_config,
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
            self.assertIn("version: 2", content)

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


if __name__ == "__main__":
    unittest.main()
