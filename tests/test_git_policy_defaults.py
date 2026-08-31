from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "skills/synchronize-git-repositories/scripts/configure_project.py"
SPEC = importlib.util.spec_from_file_location("git_policy_defaults", SCRIPT)
POLICY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(POLICY)


class GitPolicyDefaultsTests(unittest.TestCase):
    def test_configure_installs_conditional_defaults_for_both_agents(self) -> None:
        for agent, filename in (("codex", "AGENTS.md"), ("claude-code", "CLAUDE.md")):
            with self.subTest(agent=agent), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                state, changed = POLICY.configure(root, agent)
                content = (root / filename).read_text(encoding="utf-8")
                self.assertTrue(changed)
                self.assertTrue(state["defaults_configured"])
                for token in ("feature/", "bugfix/", "release/", "hotfix/", "feat", "fix", "refactor", "docs", "test", "chore", "development", "production"):
                    self.assertIn(token, content)
                self.assertIn("explicit project or user", content)
                self.assertIn("independently", content)
                self.assertIn("trunk", content)
                self.assertIn("configured base", content)
                original = (root / filename).read_bytes()
                self.assertFalse(POLICY.configure(root, agent)[1])
                self.assertEqual(original, (root / filename).read_bytes())

    def test_custom_rules_and_managed_blocks_are_preserved_byte_for_byte(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "AGENTS.md"
            custom = ("# Custom\r\nUse task/ branches and ticket commits.\r\n"
                      "<!-- synchronize-git-repositories:start -->\r\nCustom synchronization.\r\n"
                      "<!-- synchronize-git-repositories:end -->\r\n").encode()
            path.write_bytes(custom)
            POLICY.configure(root)
            self.assertTrue(path.read_bytes().startswith(custom))
            self.assertIn(b"git-workflow-defaults:start", path.read_bytes())
            custom_defaults = b"<!-- git-workflow-defaults:start -->\r\nMy rules.\r\n<!-- git-workflow-defaults:end -->\r\n"
            path.write_bytes(custom + custom_defaults)
            self.assertFalse(POLICY.configure(root)[1])
            self.assertEqual(custom + custom_defaults, path.read_bytes())

    def test_malformed_default_markers_block_before_sync_write(self) -> None:
        for text in ("<!-- git-workflow-defaults:start -->\n", "<!-- git-workflow-defaults:end -->\n<!-- git-workflow-defaults:start -->", "<!-- git-workflow-defaults:start --><!-- git-workflow-defaults:end -->" * 2):
            with self.subTest(text=text), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                path = root / "AGENTS.md"
                path.write_text(text, encoding="utf-8")
                original = path.read_bytes()
                self.assertFalse(POLICY.inspect(root)["valid"])
                with self.assertRaises(POLICY.ConfigurationError):
                    POLICY.configure(root)
                self.assertEqual(original, path.read_bytes())

    def test_known_legacy_blocks_upgrade_for_both_agents(self) -> None:
        for agent, filename, invocation in (("codex", "AGENTS.md", "$"), ("claude-code", "CLAUDE.md", "/")):
            for source in (POLICY.LEGACY_BLOCK, POLICY.PREVIOUS_BLOCK):
                with self.subTest(agent=agent, source=source), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    path = root / filename
                    legacy = source.replace("$synchronize", invocation + "synchronize")
                    path.write_text(legacy, encoding="utf-8")
                    POLICY.configure(root, agent)
                    self.assertIn("configured base", path.read_text(encoding="utf-8"))
                    self.assertEqual(1, path.read_text(encoding="utf-8").count(POLICY.START))

    def test_symlink_guard_is_checked_before_read_or_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "AGENTS.md"
            path.write_bytes(b"untouched\r\n")
            with patch.object(Path, "is_symlink", return_value=True):
                with self.assertRaisesRegex(POLICY.ConfigurationError, "symlink"):
                    POLICY.configure(root)
            self.assertEqual(b"untouched\r\n", path.read_bytes())

    def test_malformed_sync_or_overlapping_blocks_do_not_write(self) -> None:
        for content in (
            POLICY.START,
            POLICY.START + POLICY.DEFAULTS_START + POLICY.END + POLICY.DEFAULTS_END,
        ):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                path = root / "AGENTS.md"
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(POLICY.ConfigurationError):
                    POLICY.configure(root)
                self.assertEqual(content, path.read_text(encoding="utf-8"))

    def test_symlink_rules_file_rejected_without_changing_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "external.md"
            target.write_text("untouched", encoding="utf-8")
            try:
                (root / "AGENTS.md").symlink_to(target)
            except OSError:
                self.skipTest("symlink creation unavailable")
            with self.assertRaises(POLICY.ConfigurationError):
                POLICY.configure(root)
            self.assertEqual("untouched", target.read_text(encoding="utf-8"))

    def test_bootstrap_plan_is_read_only_and_apply_requires_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            argv = [sys.executable, str(SCRIPT), "bootstrap", "--project-path", str(root), "--json"]
            plan = subprocess.run(argv, capture_output=True, text=True)
            self.assertEqual(0, plan.returncode, plan.stderr)
            self.assertFalse(json.loads(plan.stdout)["configured"])
            self.assertEqual([], list(root.iterdir()))
            unconfirmed = subprocess.run([*argv, "--apply"], capture_output=True, text=True)
            self.assertNotEqual(0, unconfirmed.returncode)
            self.assertEqual([], list(root.iterdir()))
            applied = subprocess.run([*argv, "--apply", "--yes"], capture_output=True, text=True)
            self.assertEqual(0, applied.returncode, applied.stderr)
            self.assertTrue(json.loads(applied.stdout)["defaults_configured"])


if __name__ == "__main__":
    unittest.main()
