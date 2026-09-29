from __future__ import annotations

import importlib.util
import json
import os
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
    def test_existing_confirmed_choice_survives_bootstrap_update(self) -> None:
        for agent in ("codex", "claude-code"):
            with self.subTest(agent=agent), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                private = root / "private"
                choice = root / "choice.json"
                choice.write_text(json.dumps({"schema_version": 1,
                    "honor_project_policy": True, "fallback": "collection"}), encoding="utf-8")
                command = [sys.executable, str(SCRIPT.with_name("branch_policy.py")),
                    "configure", "--agent", agent, "--choice-file", str(choice),
                    "--config-root", str(private)]
                preview = subprocess.run(command, check=True, capture_output=True, text=True)
                digest = json.loads(preview.stdout)["plan_digest"]
                subprocess.run([*command, "--confirm", "--expected-digest", digest],
                    check=True, capture_output=True, text=True)
                config = private / (agent + ".json")
                original = config.read_bytes()
                for _ in range(2):
                    state, _ = POLICY.configure(root, agent, private)
                    self.assertEqual("configured", state["naming_policy"]["state"])
                    self.assertFalse(state["defaults_configured"])
                    self.assertEqual(original, config.read_bytes())

    def setUp(self) -> None:
        self.private = tempfile.TemporaryDirectory()
        self.addCleanup(self.private.cleanup)
        environment = patch.dict(os.environ, {
            "CODEX_HOME": str(Path(self.private.name).resolve() / "codex"),
            "CLAUDE_CONFIG_DIR": str(Path(self.private.name).resolve() / "claude"),
        })
        environment.start()
        self.addCleanup(environment.stop)

    def test_configure_installs_sync_without_consent_to_naming_defaults(self) -> None:
        for agent, filename in (("codex", "AGENTS.md"), ("claude-code", "CLAUDE.md")):
            with self.subTest(agent=agent), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                state, changed = POLICY.configure(root, agent)
                content = (root / filename).read_text(encoding="utf-8")
                self.assertTrue(changed)
                self.assertFalse(state["defaults_configured"])
                self.assertNotIn(POLICY.DEFAULTS_START, content)
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
            self.assertEqual(custom, path.read_bytes())
            custom_defaults = b"<!-- git-workflow-defaults:start -->\r\nMy rules.\r\n<!-- git-workflow-defaults:end -->\r\n"
            path.write_bytes(custom + custom_defaults)
            self.assertFalse(POLICY.configure(root)[1])
            self.assertEqual(custom + custom_defaults, path.read_bytes())

    def test_existing_known_defaults_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = (POLICY.CODEX_BLOCK + "\n\n" + POLICY.DEFAULTS_BLOCK + "\n").encode()
            (root / "AGENTS.md").write_bytes(original)
            state, changed = POLICY.configure(root)
            self.assertFalse(changed)
            self.assertTrue(state["defaults_configured"])
            self.assertEqual(original, (root / "AGENTS.md").read_bytes())

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
            argv = [sys.executable, str(SCRIPT), "bootstrap", "--project-path", str(root), "--policy-config-root", str(Path(self.private.name).resolve() / "policy"), "--json"]
            plan = subprocess.run(argv, capture_output=True, text=True)
            self.assertEqual(0, plan.returncode, plan.stderr)
            self.assertFalse(json.loads(plan.stdout)["configured"])
            self.assertEqual([], list(root.iterdir()))
            unconfirmed = subprocess.run([*argv, "--apply"], capture_output=True, text=True)
            self.assertNotEqual(0, unconfirmed.returncode)
            self.assertEqual([], list(root.iterdir()))
            applied = subprocess.run([*argv, "--apply", "--yes"], capture_output=True, text=True)
            self.assertEqual(0, applied.returncode, applied.stderr)
            self.assertFalse(json.loads(applied.stdout)["defaults_configured"])
            self.assertEqual("unconfigured", json.loads(applied.stdout)["naming_policy"]["state"])
            self.assertFalse((Path(self.private.name).resolve() / "policy").exists())


if __name__ == "__main__":
    unittest.main()
