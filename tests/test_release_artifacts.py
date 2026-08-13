from __future__ import annotations

import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path


REPOSITORY_DIRECTORY = Path(__file__).resolve().parents[1]
SCRIPTS_DIRECTORY = REPOSITORY_DIRECTORY / "scripts"
PLUGIN_VERSION = json.loads(
    (REPOSITORY_DIRECTORY / ".codex-plugin" / "plugin.json").read_text(
        encoding="utf-8"
    )
)["version"]
SKILL_NAMES = tuple(
    entry["name"]
    for entry in json.loads(
        (REPOSITORY_DIRECTORY / "skill-catalog.json").read_text(encoding="utf-8")
    )["skills"]
)
RELEASE_TAG = f"v{PLUGIN_VERSION}"
ARCHIVE_BASENAME = f"kolabse-skills-{RELEASE_TAG}"
sys.dont_write_bytecode = True
sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from build_release import build_release, verify_checksums  # noqa: E402


class ReleaseArtifactTests(unittest.TestCase):
    def test_release_build_is_deterministic_and_contains_distribution(self) -> None:
        repository = REPOSITORY_DIRECTORY
        with tempfile.TemporaryDirectory() as first_directory:
            with tempfile.TemporaryDirectory() as second_directory:
                first = Path(first_directory)
                second = Path(second_directory)
                first_files = build_release(repository, RELEASE_TAG, first)
                second_files = build_release(repository, RELEASE_TAG, second)

                self.assertEqual(
                    [path.name for path in first_files],
                    [path.name for path in second_files],
                )
                for first_path, second_path in zip(first_files, second_files):
                    self.assertEqual(first_path.read_bytes(), second_path.read_bytes())

                prefix = f"{ARCHIVE_BASENAME}/"
                with zipfile.ZipFile(first / f"{ARCHIVE_BASENAME}.zip") as archive:
                    zip_names = set(archive.namelist())
                with tarfile.open(first / f"{ARCHIVE_BASENAME}.tar.gz") as archive:
                    tar_names = set(archive.getnames())
                for skill in SKILL_NAMES:
                    expected = prefix + f"skills/{skill}/SKILL.md"
                    self.assertIn(expected, zip_names)
                    self.assertIn(expected, tar_names)
                self.assertIn(prefix + ".codex-plugin/plugin.json", zip_names)
                self.assertIn(prefix + ".codex-plugin/plugin.json", tar_names)
                self.assertIn(prefix + "scripts/trigger_evals.py", zip_names)
                self.assertIn(prefix + "scripts/trigger_evals.py", tar_names)
                for skill in SKILL_NAMES:
                    self.assertIn(prefix + f"evals/{skill}.json", zip_names)
                    self.assertIn(prefix + f"evals/{skill}.json", tar_names)
                self.assertIn(prefix + "evals/release-holdout-v1.json", zip_names)
                self.assertIn(prefix + "evals/release-holdout-v1.json", tar_names)
                baseline = "evals/baselines/release-holdout-v1-v0.8.0.json"
                self.assertIn(prefix + baseline, zip_names)
                self.assertIn(prefix + baseline, tar_names)
                self.assertFalse(any("/.git/" in name for name in zip_names))

                manifest = json.loads(
                    (first / "release-manifest.json").read_text(encoding="utf-8")
                )
                self.assertEqual(RELEASE_TAG, manifest["release"])
                self.assertEqual(2, len(manifest["artifacts"]))
                self.assertTrue(manifest["source_commit"])
                verify_checksums(first / "SHA256SUMS")

    def test_verification_rejects_tampered_artifact(self) -> None:
        repository = REPOSITORY_DIRECTORY
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            build_release(repository, RELEASE_TAG, output)
            archive = output / f"{ARCHIVE_BASENAME}.zip"
            archive.write_bytes(archive.read_bytes() + b"tampered")

            with self.assertRaisesRegex(ValueError, "Checksum mismatch"):
                verify_checksums(output / "SHA256SUMS")

    def test_plugin_version_must_match_release_tag(self) -> None:
        repository = REPOSITORY_DIRECTORY
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "does not match release tag"):
                build_release(repository, "v9.9.9", Path(directory))

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
