from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from install_personal_plugin import install  # noqa: E402


class PersonalPluginInstallerTests(unittest.TestCase):
    def make_source(self, root: Path, version: str) -> Path:
        source = root / "source"
        manifest = source / ".codex-plugin/plugin.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(
            json.dumps({"name": "kolabse-skills", "version": version}), encoding="utf-8"
        )
        skill = source / "skills/demo"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: demo\ndescription: demo\n---\n", encoding="utf-8")
        return source

    def test_install_creates_marketplace_and_cachebusted_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.make_source(root, "1.2.0")
            state = install(source, root / "plugins", root / "marketplace.json")
            self.assertTrue(state["version"].startswith("1.2.0+codex.local-"))
            marketplace = json.loads((root / "marketplace.json").read_text(encoding="utf-8"))
            self.assertEqual("./plugins/kolabse-skills", marketplace["plugins"][0]["source"]["path"])

    def test_update_preserves_other_marketplace_entries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.make_source(root, "1.2.0")
            marketplace = root / "marketplace.json"
            marketplace.write_text(
                json.dumps(
                    {
                        "name": "personal",
                        "interface": {"displayName": "My plugins"},
                        "plugins": [{"name": "other"}],
                    }
                ),
                encoding="utf-8",
            )
            install(source, root / "plugins", marketplace)
            payload = json.loads(marketplace.read_text(encoding="utf-8"))
            self.assertEqual("My plugins", payload["interface"]["displayName"])
            self.assertEqual(["other", "kolabse-skills"], [item["name"] for item in payload["plugins"]])


if __name__ == "__main__":
    unittest.main()
