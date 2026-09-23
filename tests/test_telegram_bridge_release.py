from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_release", ROOT / "scripts/build_release.py")
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)
TAG = "telegram-task-bridge-v0.1.0"


class TelegramBridgeReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.source = self.base / "repository"
        self.source.mkdir()
        self.prototype = self.source / release.BRIDGE_SOURCE
        self.prototype.mkdir(parents=True)
        shutil.copyfile(ROOT / "LICENSE", self.source / "LICENSE")
        for name in release.BRIDGE_INPUTS:
            (self.prototype / name).write_bytes((ROOT / release.BRIDGE_SOURCE / name).read_bytes().replace(b"\r\n", b"\n"))
        self.git("init")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Release Test")
        self.git("config", "core.autocrlf", "false")
        (self.source / ".gitattributes").write_text("* text eol=crlf\n")
        self.commit()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.source), *args], check=True, capture_output=True).stdout

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-m", "test: fixture")

    def build(self, folder="release", tag=TAG):
        return release.build_telegram_bridge_release(self.source, tag, self.base / folder)

    def test_deterministic_canonical_bytes_and_metadata(self):
        first = self.build("first")
        self.git("config", "core.autocrlf", "true")
        for path in (self.source / "LICENSE", *self.prototype.iterdir()):
            path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        self.git("add", "--renormalize", ".")
        self.assertFalse(self.git("status", "--porcelain").strip())
        second = self.build("second")
        self.assertEqual([path.name for path in first], [f"{TAG}.zip", "release-manifest.json", "SHA256SUMS"])
        self.assertEqual([path.read_bytes() for path in first], [path.read_bytes() for path in second])
        manifest = json.loads(first[1].read_text())
        self.assertEqual(manifest["release"], TAG)
        self.assertEqual(manifest["source_commit"], self.git("rev-parse", "HEAD").decode().strip())
        self.assertEqual(manifest["artifacts"][0]["sha256"], release.sha256_file(first[0]))
        with zipfile.ZipFile(first[0]) as archive:
            for info in archive.infolist():
                self.assertTrue(info.filename.startswith("telegram-task-bridge/"))
                self.assertEqual(info.date_time, release.ZIP_TIMESTAMP)
                self.assertNotIn(b"\r\n", archive.read(info))
            for name in release.BRIDGE_DOCS:
                self.assertIn(f"telegram-task-bridge/{name}", archive.namelist())
            plugin = json.loads(archive.read("telegram-task-bridge/.codex-plugin/plugin.json"))
            self.assertEqual(plugin["name"], "telegram-task-bridge")
            self.assertEqual(plugin["version"], "0.1.0")
        release.verify_checksums(first[2])
        first[0].write_bytes(first[0].read_bytes() + b"tamper")
        with self.assertRaisesRegex(ValueError, "Checksum mismatch"):
            release.verify_checksums(first[2])

    def test_wrong_tag_name_and_version(self):
        for tag in ("v0.1.0", "telegram-task-bridge-v../x", "telegram-task-bridge-v0.2.0"):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                self.build(tag=tag)
        manifest_path = self.prototype / "plugin-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["name"] = "wrong-plugin"
        manifest_path.write_text(json.dumps(manifest))
        self.commit()
        with self.assertRaisesRegex(ValueError, "manifest name/version"):
            self.build()

    def test_dirty_source_and_staged_source(self):
        (self.prototype / "server.py").write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "source must be clean"):
            self.build()
        self.git("add", ".")
        with self.assertRaisesRegex(ValueError, "source must be clean"):
            self.build()
        self.assertFalse((self.base / "release").exists())

    def test_untracked_credentials_are_rejected_without_exposure(self):
        secret = "123456789:EXAMPLE_PRIVATE_TOKEN"
        (self.prototype / "credentials.json").write_text(secret)
        result = subprocess.run([
            "python", str(ROOT / "scripts/build_release.py"), "--telegram-bridge",
            "--source", str(self.source), "--tag", TAG, "--output", str(self.base / "release"),
        ], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn(secret, result.stdout + result.stderr)
        self.assertNotIn("credentials.json", result.stdout + result.stderr)
        self.assertFalse((self.base / "release").exists())

    def test_ignored_credentials_are_rejected(self):
        (self.source / ".git/info/exclude").write_text("credentials.json\n")
        (self.prototype / "credentials.json").write_text("private")
        with self.assertRaisesRegex(ValueError, "Unexpected untracked"):
            self.build()

    def test_nonempty_or_inside_output_is_preserved(self):
        output = self.base / "release"
        output.mkdir()
        keep = output / "keep.txt"
        keep.write_text("preserve")
        with self.assertRaisesRegex(ValueError, "empty directory"):
            self.build()
        self.assertEqual(keep.read_text(), "preserve")
        with self.assertRaisesRegex(ValueError, "outside"):
            release.build_telegram_bridge_release(self.source, TAG, self.source / "dist")

    def test_committed_symlink_is_rejected(self):
        target = self.prototype / "linked.py"
        try:
            target.symlink_to("server.py")
        except (OSError, NotImplementedError):
            self.skipTest("Symbolic link creation unavailable")
        self.git("config", "core.symlinks", "true")
        self.commit()
        with self.assertRaisesRegex(ValueError, "symbolic links"):
            self.build()

    def test_real_commit_required(self):
        empty = self.base / "empty"
        empty.mkdir()
        self.source = empty
        with self.assertRaisesRegex(ValueError, "committed"):
            self.build()


if __name__ == "__main__":
    unittest.main()
