from __future__ import annotations

import json
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


if __name__ == "__main__":
    unittest.main()
