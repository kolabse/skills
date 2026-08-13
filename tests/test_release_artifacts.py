from __future__ import annotations

import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path


SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1] / "scripts"
sys.dont_write_bytecode = True
sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from build_release import build_release, verify_checksums  # noqa: E402


class ReleaseArtifactTests(unittest.TestCase):
    def test_release_build_is_deterministic_and_contains_distribution(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as first_directory:
            with tempfile.TemporaryDirectory() as second_directory:
                first = Path(first_directory)
                second = Path(second_directory)
                first_files = build_release(repository, "v1.2.3", first)
                second_files = build_release(repository, "v1.2.3", second)

                self.assertEqual(
                    [path.name for path in first_files],
                    [path.name for path in second_files],
                )
                for first_path, second_path in zip(first_files, second_files):
                    self.assertEqual(first_path.read_bytes(), second_path.read_bytes())

                prefix = "kolabse-skills-v1.2.3/"
                with zipfile.ZipFile(first / "kolabse-skills-v1.2.3.zip") as archive:
                    zip_names = set(archive.namelist())
                with tarfile.open(first / "kolabse-skills-v1.2.3.tar.gz") as archive:
                    tar_names = set(archive.getnames())
                expected = prefix + "skills/operate-yandex-cloud/SKILL.md"
                self.assertIn(expected, zip_names)
                self.assertIn(expected, tar_names)
                self.assertFalse(any("/.git/" in name for name in zip_names))

                manifest = json.loads(
                    (first / "release-manifest.json").read_text(encoding="utf-8")
                )
                self.assertEqual("v1.2.3", manifest["release"])
                self.assertEqual(2, len(manifest["artifacts"]))
                self.assertTrue(manifest["source_commit"])
                verify_checksums(first / "SHA256SUMS")

    def test_verification_rejects_tampered_artifact(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            build_release(repository, "v1.2.3", output)
            archive = output / "kolabse-skills-v1.2.3.zip"
            archive.write_bytes(archive.read_bytes() + b"tampered")

            with self.assertRaisesRegex(ValueError, "Checksum mismatch"):
                verify_checksums(output / "SHA256SUMS")

    def test_clean_git_source_uses_canonical_blob_line_endings(self) -> None:
        with tempfile.TemporaryDirectory() as source_directory:
            with tempfile.TemporaryDirectory() as output_directory:
                source = Path(source_directory)
                output = Path(output_directory)
                files = {
                    "README.md": "# Test\r\n",
                    "LICENSE": "Test license\r\n",
                    "CHANGELOG.md": "# Changes\r\n",
                    "skill-catalog.json": '{"schema_version": 1}\r\n',
                    "skills/demo/SKILL.md": (
                        "---\r\nname: demo\r\ndescription: Demo.\r\n---\r\n"
                    ),
                }
                for name, content in files.items():
                    path = source / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(content, encoding="utf-8", newline="")
                self.run_git(source, "init", "--quiet")
                self.run_git(source, "config", "user.name", "Release Test")
                self.run_git(source, "config", "user.email", "release@example.test")
                self.run_git(source, "config", "core.autocrlf", "true")
                self.run_git(source, "add", ".")
                self.run_git(source, "commit", "--quiet", "-m", "fixture")

                build_release(source, "v1.2.3", output)

                with zipfile.ZipFile(output / "kolabse-skills-v1.2.3.zip") as archive:
                    readme = archive.read("kolabse-skills-v1.2.3/README.md")
                manifest = json.loads(
                    (output / "release-manifest.json").read_text(encoding="utf-8")
                )
                self.assertEqual(b"# Test\n", readme)
                self.assertFalse(manifest["source_commit"].endswith("-dirty"))

    @staticmethod
    def run_git(directory: Path, *arguments: str) -> None:
        subprocess.run(
            ["git", "-C", str(directory), *arguments],
            capture_output=True,
            check=True,
        )


if __name__ == "__main__":
    unittest.main()
