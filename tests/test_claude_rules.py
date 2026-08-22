from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(relative: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sync_rules = load(
    "skills/synchronize-git-repositories/scripts/configure_project.py",
    "sync_rules_claude_test",
)
work_log_rules = load(
    "skills/maintain-work-log/scripts/configure_project.py",
    "work_log_rules_claude_test",
)
verify_rules = load(
    "skills/verify-before-push/scripts/verify_before_push.py",
    "verify_rules_claude_test",
)
discover = load(
    "skills/discover-skill-candidates/scripts/discover_candidates.py",
    "discover_rules_claude_test",
)
lifecycle = load(
    "skills/execute-verified-development-lifecycle/scripts/development_lifecycle.py",
    "lifecycle_rules_claude_test",
)
context_sync = load(
    "skills/sync-project-context/scripts/context_sync.py",
    "context_sync",
)
sys.modules["context_sync"] = context_sync
environment_sync = load(
    "skills/sync-project-context/scripts/environment_sync.py",
    "environment_sync_claude_test",
)


class ClaudeRuleCompatibilityTests(unittest.TestCase):
    def test_codex_remains_default_and_claude_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sync_rules.configure(root)
            self.assertIn("`$synchronize-git-repositories`", (root / "AGENTS.md").read_text())
            self.assertFalse((root / "CLAUDE.md").exists())

            sync_rules.configure(root, "claude-code")
            self.assertIn("`/synchronize-git-repositories`", (root / "CLAUDE.md").read_text())
            self.assertNotIn("`$synchronize-git-repositories`", (root / "CLAUDE.md").read_text())

    def test_work_log_configures_selected_rule_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state, changed = work_log_rules.configure(root, "claude-code")
            self.assertTrue(changed)
            self.assertEqual("claude-code", state["agent"])
            self.assertIn("`/maintain-work-log`", (root / "CLAUDE.md").read_text())
            self.assertFalse((root / "AGENTS.md").exists())
            self.assertTrue((root / "docs/reports/work-log.md").is_file())

    def test_verify_policy_uses_claude_file_without_touching_agents(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertTrue(verify_rules.ensure_policy(root, "claude-code"))
            self.assertIn("`/verify-before-push`", (root / "CLAUDE.md").read_text())
            self.assertFalse((root / "AGENTS.md").exists())

    def test_discovery_selects_one_rule_family(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text("# Codex\n", encoding="utf-8")
            (root / "CLAUDE.md").write_text(
                "# Claude\n\nUse `/review-code-changes`. Read /src/api first.\n",
                encoding="utf-8",
            )
            codex = discover.discover_rule_paths(root, set())
            claude = discover.discover_rule_paths(root, set(), "claude-code")
            self.assertEqual(["AGENTS.md"], [path.name for path in codex])
            self.assertEqual(["CLAUDE.md"], [path.name for path in claude])
            report = discover.inventory(root, set(), agent="claude-code")
            references = {
                reference
                for file in report["files"]
                for block in file["blocks"]
                for reference in block["skill_references"]
            }
            self.assertEqual({"review-code-changes"}, references)

    def test_lifecycle_rule_and_dependency_agent_are_bound(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "CLAUDE.md"
            path.write_text(lifecycle.AGENTS["claude-code"]["block"] + "\n", encoding="utf-8")
            state = lifecycle.inspect_rule_file(path, lifecycle.AGENTS["claude-code"]["block"])
            self.assertTrue(state["installed"])

        args = lifecycle.parser().parse_args(["dependencies", "--agent", "claude-code"])
        result = lifecycle.cmd_dependencies(args)
        index = result["install_argv"].index("--agent")
        self.assertEqual("claude-code", result["install_argv"][index + 1])

    def test_context_sync_accepts_only_named_agent_rule_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            relative, target = environment_sync.normalize_rule_path("CLAUDE.md", root)
            self.assertEqual("CLAUDE.md", relative)
            self.assertEqual((root / "CLAUDE.md").resolve(), target.resolve())
            with self.assertRaises(context_sync.ContextSyncError):
                environment_sync.normalize_rule_path("PROJECT.md", root)


if __name__ == "__main__":
    unittest.main()
