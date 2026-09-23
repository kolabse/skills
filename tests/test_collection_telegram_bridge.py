"""The normal collection delivery must carry a complete, current bridge bundle."""
import importlib.util
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import bundle_telegram_bridge as bundle
from build_release import release_files
from install_personal_plugin import install


class CollectionBridgeTests(unittest.TestCase):
    def test_bundle_matches_canonical_runtime(self):
        self.assertEqual([], bundle.synchronize(check=True))

    def test_missing_stale_and_unexpected_inputs_are_detected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            shutil.copytree(ROOT / bundle.SOURCE, root / bundle.SOURCE,
                            ignore=shutil.ignore_patterns("__pycache__"))
            self.assertEqual(set(bundle.INPUTS), set(bundle.synchronize(root, check=True)))
            bundle.synchronize(root)
            self.assertEqual([], bundle.synchronize(root, check=True))
            path = root / bundle.TARGET / "runtime/server.py"
            path.write_text("stale", encoding="utf-8")
            self.assertEqual(["runtime/server.py"], bundle.synchronize(root, check=True))
            bundle.synchronize(root)
            unexpected = root / bundle.TARGET / "private.json"
            unexpected.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Unexpected files"):
                bundle.synchronize(root, check=True)

    def test_collection_archive_contains_every_bridge_file(self):
        files = {path.relative_to(ROOT).as_posix() for path in release_files(ROOT)}
        for name in bundle.INPUTS:
            self.assertIn((bundle.TARGET / name).as_posix(), files)
        self.assertIn("skills/notify-via-telegram/references/task-bridge.md", files)

    def test_personal_plugin_update_copies_bundle_without_installing_receiver(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source"
            shutil.copytree(ROOT / ".codex-plugin", source / ".codex-plugin")
            skill = Path("skills/notify-via-telegram")
            shutil.copytree(ROOT / skill, source / skill,
                            ignore=shutil.ignore_patterns("__pycache__"))
            state = install(source, root / "plugins", root / "marketplace.json")
            target = Path(state["plugin_path"])
            # A normal update restores all nested files from the installed source.
            server = target / bundle.TARGET / "runtime/server.py"
            server.write_text("previous runtime", encoding="utf-8")
            install(source, root / "plugins", root / "marketplace.json")
            for name in bundle.INPUTS:
                self.assertEqual((source / bundle.TARGET / name).read_bytes(),
                                 (target / bundle.TARGET / name).read_bytes())
            self.assertFalse((target / ".mcp.json").exists())
            self.assertFalse((target / "hooks/hooks.json").exists())
            self.assertEqual([target / skill / "SKILL.md"],
                             list((target / skill).rglob("SKILL.md")))
            # The copied installer resolves its entire runtime without a checkout.
            spec = importlib.util.spec_from_file_location(
                "copied_bridge_installer", target / bundle.TARGET / "installer.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            for name in module.FILES:
                self.assertTrue((target / bundle.TARGET / "runtime" / name).is_file())


if __name__ == "__main__":
    unittest.main()
