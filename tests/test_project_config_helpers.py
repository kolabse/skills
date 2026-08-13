from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = shutil.which("python") or sys.executable


class ProjectConfigurationHelperTests(unittest.TestCase):
    def run_helper(self, skill: str, command: str, project: Path) -> subprocess.CompletedProcess[str]:
        script = ROOT / "skills" / skill / "scripts" / "configure_project.py"
        return subprocess.run(
            [PYTHON, str(script), command, "--project-path", str(project), "--json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def test_sync_configuration_is_idempotent_and_preserves_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            agents = project / "AGENTS.md"
            agents.write_text("# Existing\n\nKeep this.\n", encoding="utf-8")
            first = self.run_helper("synchronize-git-repositories", "configure", project)
            self.assertEqual(0, first.returncode, first.stderr)
            first_text = agents.read_text(encoding="utf-8")
            second = self.run_helper("synchronize-git-repositories", "configure", project)
            self.assertEqual(0, second.returncode, second.stderr)
            self.assertEqual(first_text, agents.read_text(encoding="utf-8"))
            self.assertIn("Keep this.", first_text)
            self.assertEqual(1, first_text.count("synchronize-git-repositories:start"))
            self.assertFalse(json.loads(second.stdout)["changed"])

    def test_work_log_configuration_creates_required_files_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            first = self.run_helper("maintain-work-log", "configure", project)
            self.assertEqual(0, first.returncode, first.stderr)
            agents = (project / "AGENTS.md").read_bytes()
            work_log = (project / "docs/reports/work-log.md").read_bytes()
            second = self.run_helper("maintain-work-log", "configure", project)
            self.assertEqual(0, second.returncode, second.stderr)
            self.assertEqual(agents, (project / "AGENTS.md").read_bytes())
            self.assertEqual(work_log, (project / "docs/reports/work-log.md").read_bytes())
            self.assertFalse(json.loads(second.stdout)["changed"])

    def test_status_is_read_only_and_reports_unconfigured(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            result = self.run_helper("synchronize-git-repositories", "status", project)
            self.assertEqual(1, result.returncode)
            self.assertFalse(json.loads(result.stdout)["configured"])
            self.assertEqual([], list(project.iterdir()))

    def test_malformed_markers_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            agents = project / "AGENTS.md"
            original = "<!-- maintain-work-log:start -->\n"
            agents.write_text(original, encoding="utf-8")
            result = self.run_helper("maintain-work-log", "configure", project)
            self.assertEqual(1, result.returncode)
            self.assertEqual(original, agents.read_text(encoding="utf-8"))
            self.assertFalse((project / "docs").exists())


if __name__ == "__main__":
    unittest.main()
