from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import bootstrap_update as bootstrap  # noqa: E402


class BootstrapUpdateTests(unittest.TestCase):
    def make_release(self, root: Path, tag: str = "v1.4.0") -> tuple[Path, Path]:
        archive = root / f"kolabse-skills-{tag}.zip"
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr(
                f"kolabse-skills-{tag}/scripts/manage_installed_skills.py",
                "raise SystemExit(0)\n",
            )
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        checksums = root / "SHA256SUMS"
        checksums.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
        return archive, checksums

    def test_offline_verified_archive_runs_from_temporary_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive, checksums = self.make_release(root)
            with patch.object(bootstrap, "verify_attestation") as attest, patch.object(
                bootstrap, "run_manager", return_value=0
            ) as run:
                result = bootstrap.bootstrap(
                    "v1.4.0", "doctor", ["--json"], root, 30, archive, checksums
                )
            self.assertEqual(0, result)
            attest.assert_called_once()
            self.assertEqual("doctor", run.call_args.args[1])
            self.assertFalse(run.call_args.args[0].exists())

    def test_checksum_mismatch_stops_before_attestation_or_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive, checksums = self.make_release(root)
            checksums.write_text(f"{'0' * 64}  {archive.name}\n", encoding="utf-8")
            with patch.object(bootstrap, "verify_attestation") as attest, patch.object(
                bootstrap, "run_manager"
            ) as run:
                with self.assertRaisesRegex(bootstrap.BootstrapError, "checksum mismatch"):
                    bootstrap.bootstrap(
                        "v1.4.0", "doctor", [], root, 30, archive, checksums
                    )
            attest.assert_not_called()
            run.assert_not_called()

    def test_archive_path_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "bad.zip"
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("../escape", "bad")
            with self.assertRaisesRegex(bootstrap.BootstrapError, "unsafe"):
                bootstrap.safe_extract(archive, root / "out")
            self.assertFalse((root / "escape").exists())

    def test_stable_tag_is_loaded_from_github_api(self) -> None:
        with patch.object(
            bootstrap,
            "request_bytes",
            return_value=json.dumps({"tag_name": "v1.4.0"}).encode(),
        ):
            self.assertEqual("v1.4.0", bootstrap.resolve_stable_tag(10))

    def test_unattested_offline_mode_must_be_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive, checksums = self.make_release(root)
            with patch.object(bootstrap, "verify_attestation") as attest, patch.object(
                bootstrap, "run_manager", return_value=0
            ):
                bootstrap.bootstrap(
                    "v1.4.0",
                    "status",
                    [],
                    root,
                    30,
                    archive,
                    checksums,
                    allow_unattested_offline=True,
                )
            attest.assert_not_called()

    def test_run_manager_forwards_claude_code_agent(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(
            bootstrap.shutil, "which", return_value=sys.executable
        ), patch.object(bootstrap.subprocess, "run") as run:
            root = Path(directory)
            run.return_value.returncode = 0
            bootstrap.run_manager(
                root / "manager.py", "plan", ["--json"], root, 30, "claude-code"
            )
            command = run.call_args.args[0]
            self.assertIn("--agent", command)
            self.assertEqual("claude-code", command[command.index("--agent") + 1])

    def test_conflicting_forwarded_agent_is_rejected(self) -> None:
        with self.assertRaisesRegex(bootstrap.BootstrapError, "conflicts"):
            bootstrap.forwarded_agent_arguments(
                ["--agent", "codex"], "claude-code"
            )


if __name__ == "__main__":
    unittest.main()
