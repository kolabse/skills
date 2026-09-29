"""Branch choices are private, explicit and subordinate to actual instructions."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "skills/synchronize-git-repositories/scripts/branch_policy.py"


class BranchPolicyTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("branch_policy", HELPER)
        self.policy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.policy)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.config = self.root / "private"
        self.context = {
            "schema_version": 1, "agent": "codex", "task_kind": "bugfix", "slug": "repair",
            "application_rule": self.rule("Codex developer default", "codex/{slug}", True),
        }

    def rule(self, source, template, allowed=False, priority=10):
        return {"source": source, "priority": priority, "evidence": "Explicit test instruction",
                "allows_user_choice": allowed,
                "templates": dict.fromkeys(("feature", "bugfix", "release", "hotfix"), template)}

    def write(self, name, data):
        path = self.root / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def resolve(self):
        return self.policy.resolve(self.write("context.json", self.context), self.config)

    def configure(self, fallback="collection", agent="codex", honor_project_policy=True, **extra):
        choice = self.write("choice.json", dict(schema_version=1, honor_project_policy=honor_project_policy,
                                               fallback=fallback, **extra))
        plan = self.policy.configure(agent, choice, self.config)
        return self.policy.configure(agent, choice, self.config,
                                     expected_digest=plan["plan_digest"], confirm=True)

    def test_no_answer_and_status_write_nothing(self):
        self.assertEqual(self.policy.status("codex", self.config)["state"], "unconfigured")
        choice = self.write("choice.json", {"schema_version": 1, "honor_project_policy": True,
                                            "fallback": "collection"})
        self.assertEqual(self.policy.configure("codex", choice, self.config)["state"], "confirmation-required")
        self.assertFalse(self.config.exists())

    def test_application_default_beats_collection_without_choice(self):
        decision = self.resolve()
        self.assertEqual(decision["branch"], "codex/repair")
        self.assertIn("bugfix/repair", " ".join(decision["explanation"]))

    def test_absent_application_default_uses_confirmed_collection(self):
        self.context["application_rule"] = None
        self.configure()
        decision = self.resolve()
        self.assertEqual(decision["branch"], "bugfix/repair")
        self.assertIsNone(decision["priority"])
        self.assertIn("no application", " ".join(decision["explanation"]).lower())

    def test_absent_application_default_uses_project_or_explicit_or_binding(self):
        self.context["application_rule"] = None
        self.context["explicit_user_rule"] = self.rule("explicit user", "chosen/{slug}", priority=20)
        self.assertEqual(self.resolve()["branch"], "chosen/repair")
        self.context.pop("explicit_user_rule")
        self.context["binding_rule"] = self.rule("mandatory", "required/{slug}", priority=1)
        self.assertEqual(self.resolve()["branch"], "required/repair")
        self.context.pop("binding_rule")
        self.assertFalse(self.config.exists())
        self.context["project_rule"] = self.rule("project instruction", "project/{slug}", priority=30)
        self.assertEqual(self.resolve()["branch"], "project/repair")
        self.configure(honor_project_policy=False)
        self.assertEqual(self.resolve()["branch"], "bugfix/repair")
        self.context["explicit_user_rule"] = self.rule("explicit user", "chosen/{slug}", priority=20)
        self.assertEqual(self.resolve()["branch"], "chosen/repair")
        self.context.pop("explicit_user_rule")
        self.context["binding_rule"] = self.rule("mandatory", "required/{slug}", priority=1)
        self.assertEqual(self.resolve()["branch"], "required/repair")

    def test_absent_application_and_no_other_policy_blocks_without_writes(self):
        self.context["application_rule"] = None
        with self.assertRaisesRegex(self.policy.PolicyError, "No applicable naming rule"):
            self.resolve()
        self.assertFalse(self.config.exists())
        self.configure("application")
        with self.assertRaisesRegex(self.policy.PolicyError, "No applicable naming rule"):
            self.resolve()

    def test_confirmed_collection_only_where_application_permits(self):
        self.configure()
        self.assertEqual(self.resolve()["branch"], "bugfix/repair")
        self.context["application_rule"]["allows_user_choice"] = False
        self.assertEqual(self.resolve()["branch"], "codex/repair")
        self.context["explicit_user_rule"] = self.rule("user", "custom/{slug}", priority=20)
        with self.assertRaises(self.policy.PolicyError):
            self.resolve()

    def test_project_override_and_mandatory_rule(self):
        self.configure()
        self.context["project_rule"] = self.rule("project", "team/{slug}", priority=30)
        self.assertEqual(self.resolve()["branch"], "team/repair")
        self.configure(honor_project_policy=False)
        self.assertEqual(self.resolve()["branch"], "bugfix/repair")
        self.context["binding_rule"] = self.rule("mandatory", "required/{slug}", priority=1)
        self.assertEqual(self.resolve()["branch"], "required/repair")

    def test_explicit_choice_allowed(self):
        self.context["explicit_user_rule"] = self.rule("user request", "chosen/{slug}", priority=20)
        self.assertEqual(self.resolve()["branch"], "chosen/repair")

    def test_agent_isolation_and_revert(self):
        self.configure()
        self.assertEqual(self.policy.status("claude-code", self.config)["state"], "unconfigured")
        self.configure("application")
        self.assertEqual(self.resolve()["branch"], "codex/repair")

    def test_provider_change_retains_snapshot_missing_blocks(self):
        provider = {"schema_version": 1, "identity": "team/custom", "revision": "1",
                    "templates": self.rule("x", "old/{slug}")["templates"]}
        path = self.write("provider.json", provider)
        self.configure("external-skill", provider={"identity": "team/custom", "template_source": str(path)})
        provider.update(revision="2", templates=self.rule("x", "new/{slug}")["templates"])
        self.write("provider.json", provider)
        self.assertEqual(self.policy.status("codex", self.config)["state"], "confirmation-pending")
        self.assertEqual(self.resolve()["branch"], "old/repair")
        path.unlink()
        with self.assertRaises(self.policy.PolicyError):
            self.resolve()

    def test_check_rejects_name_context_and_policy_changes(self):
        decision = self.write("decision.json", self.resolve())
        context = self.root / "context.json"
        self.assertEqual(self.policy.check(context, decision, "codex/repair", self.config)["state"], "verified")
        with self.assertRaises(self.policy.PolicyError):
            self.policy.check(context, decision, "bugfix/repair", self.config)
        self.context["slug"] = "other"
        self.write("context.json", self.context)
        with self.assertRaises(self.policy.PolicyError):
            self.policy.check(context, decision, "codex/repair", self.config)
        self.context["slug"] = "repair"
        self.write("context.json", self.context)
        self.configure()
        with self.assertRaises(self.policy.PolicyError):
            self.policy.check(context, decision, "codex/repair", self.config)

    def test_invalid_refs_hotfix_and_duplicate_json(self):
        for slug in ("../bad", "bad.lock", "a b", "a@{b"):
            self.context["slug"] = slug
            with self.assertRaises(self.policy.PolicyError):
                self.resolve()
        self.context.update(slug="urgent", task_kind="hotfix")
        with self.assertRaises(self.policy.PolicyError):
            self.resolve()
        self.context["urgent_production_fix"] = True
        self.assertEqual(self.resolve()["branch"], "codex/urgent")
        path = self.root / "duplicate.json"
        path.write_text('{"schema_version":1,"schema_version":1}')
        with self.assertRaises(self.policy.PolicyError):
            self.policy.resolve(path, self.config)

    def test_copied_skill_provenance_is_actual_artifact(self):
        copied = self.root / "standalone"
        shutil.copytree(HELPER.parents[1], copied)
        spec = importlib.util.spec_from_file_location("copied_policy", copied / "scripts/branch_policy.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.context["collection_metadata"] = {"version": "reported-only", "source": "plugin manifest"}
        decision = module.resolve(self.write("context.json", self.context), self.config)
        self.assertEqual(Path(decision["provenance"]["skill_path"]), copied / "SKILL.md")
        self.assertIn("skill_sha256", decision["provenance"])
        self.assertEqual(decision["collection_metadata"]["version"], "reported-only")

    def test_collection_update_needs_new_confirmation(self):
        self.configure()
        old = self.write("decision.json", self.resolve())
        self.policy.COLLECTION["revision"] = "2"
        self.policy.COLLECTION["templates"]["bugfix"] = "fix/{slug}"
        current = self.policy.status("codex", self.config)
        self.assertEqual(current["state"], "confirmation-pending")
        self.assertEqual(current["provider_snapshot"]["revision"], "1")
        self.assertEqual(self.resolve()["branch"], "bugfix/repair")
        with self.assertRaises(self.policy.PolicyError):
            self.policy.check(self.root / "context.json", old, "bugfix/repair", self.config)
        self.configure()
        self.assertEqual(self.resolve()["branch"], "fix/repair")

    def test_confirmation_digest_blocks_changed_selection_and_no_confirm_never_writes(self):
        choice = self.write("choice.json", {"schema_version": 1, "honor_project_policy": True,
                                            "fallback": "collection"})
        plan = self.policy.configure("codex", choice, self.config)
        self.write("choice.json", {"schema_version": 1, "honor_project_policy": False,
                                  "fallback": "collection"})
        with self.assertRaises(self.policy.PolicyError):
            self.policy.configure("codex", choice, self.config, plan["plan_digest"], confirm=True)
        with self.assertRaises(self.policy.PolicyError):
            self.policy.configure("codex", choice, self.config, confirm=True)
        self.assertFalse(self.config.exists())

    def test_project_priority_and_ambiguity(self):
        self.configure(honor_project_policy=False)
        self.context["project_rule"] = self.rule("higher instruction", "mandatory/{slug}", priority=2)
        self.assertEqual(self.resolve()["branch"], "mandatory/repair")
        self.context["explicit_user_rule"] = self.rule("user", "other/{slug}", priority=20)
        with self.assertRaises(self.policy.PolicyError):
            self.resolve()
        del self.context["explicit_user_rule"]
        self.context["project_rule"]["priority"] = 10
        with self.assertRaises(self.policy.PolicyError):
            self.resolve()

    def test_application_delegates_to_existing_project_and_mandatory_constraint(self):
        self.context["project_rule"] = self.rule("explicit repository instruction", "feature/{slug}", priority=20)
        self.assertEqual(self.resolve()["branch"], "feature/repair")
        self.assertFalse(self.config.exists())
        self.configure(honor_project_policy=False)
        self.assertEqual(self.resolve()["branch"], "bugfix/repair")
        self.context["binding_rule"] = self.context.pop("project_rule")
        self.assertEqual(self.resolve()["branch"], "feature/repair")
        self.context["application_rule"]["allows_user_choice"] = False
        with self.assertRaises(self.policy.PolicyError):
            self.resolve()

    def test_higher_priority_explicit_instruction_beats_lower_application_rule(self):
        self.context["application_rule"]["allows_user_choice"] = False
        self.context["explicit_user_rule"] = self.rule("higher actual instruction", "chosen/{slug}", priority=2)
        self.assertEqual(self.resolve()["branch"], "chosen/repair")

    def test_malformed_unsupported_and_oversized_policy_are_blocked(self):
        for choice in (
            {"schema_version": True, "honor_project_policy": True, "fallback": "collection"},
            {"schema_version": 1, "honor_project_policy": "yes", "fallback": "collection"},
            {"schema_version": 1, "honor_project_policy": True, "fallback": "other"},
            {"schema_version": 1, "honor_project_policy": True, "fallback": "external-skill"},
            {"schema_version": 1, "honor_project_policy": True, "fallback": "collection", "provider": {}},
        ):
            with self.assertRaises(self.policy.PolicyError):
                self.policy.configure("codex", self.write("invalid.json", choice), self.config)
        giant = self.root / "large.json"
        giant.write_text(" " * (self.policy.LIMIT + 1))
        with self.assertRaises(self.policy.PolicyError):
            self.policy.configure("codex", giant, self.config)
        self.assertFalse(self.config.exists())

    def test_cli_yes_is_not_consent_and_saved_decision_checks(self):
        choice = self.write("choice.json", {"schema_version": 1, "honor_project_policy": True,
                                            "fallback": "collection"})
        command = [sys.executable, str(HELPER)]
        result = subprocess.run(command + ["configure", "--agent", "codex", "--choice-file", str(choice),
                               "--config-root", str(self.config), "--yes"], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.config.exists())
        context = self.write("context.json", self.context)
        output = self.root / "decision.json"
        result = subprocess.run(command + ["resolve", "--context", str(context), "--output", str(output),
                               "--config-root", str(self.config)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run(command + ["check", "--context", str(context), "--decision", str(output),
                               "--branch", "codex/repair", "--config-root", str(self.config)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_artifact_edit_invalidates_saved_decision(self):
        copied = self.root / "copied"
        shutil.copytree(HELPER.parents[1], copied)
        spec = importlib.util.spec_from_file_location("artifact_policy", copied / "scripts/branch_policy.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        context = self.write("context.json", self.context)
        decision = self.write("decision.json", module.resolve(context, self.config))
        with (copied / "SKILL.md").open("a", encoding="utf-8") as stream:
            stream.write("\nChanged policy instructions\n")
        with self.assertRaises(module.PolicyError):
            module.check(context, decision, "codex/repair", self.config)

    def test_default_user_configuration_is_application_scoped(self):
        base = self.root / "user-config"
        with patch.dict(os.environ, {"APPDATA": str(base), "XDG_CONFIG_HOME": str(base)}):
            codex = self.policy.status("codex")
            claude = self.policy.status("claude-code")
        self.assertEqual(Path(codex["config_path"]), base / "kolabse/branch-policy/codex.json")
        self.assertEqual(Path(claude["config_path"]), base / "kolabse/branch-policy/claude-code.json")
        self.assertFalse(base.exists())

    def test_cli_unicode_json_survives_ascii_terminal(self):
        self.context["application_rule"]["source"] = "命名规则"
        self.context["slug"] = "修复"
        context = self.write("context.json", self.context)
        result = subprocess.run([sys.executable, str(HELPER), "resolve", "--context", str(context),
                                 "--config-root", str(self.config)], capture_output=True,
                                env=dict(os.environ, PYTHONIOENCODING="ascii"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["branch"], "codex/修复")
        self.context["slug"] = "修复..错误"
        self.write("context.json", self.context)
        result = subprocess.run([sys.executable, str(HELPER), "resolve", "--context", str(context),
                                 "--config-root", str(self.config)], capture_output=True,
                                env=dict(os.environ, PYTHONIOENCODING="ascii"))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stderr)["state"], "blocked")

    def test_cli_decision_cannot_overwrite_selected_provider(self):
        provider = self.write("source.json", {"schema_version": 1, "identity": "team/source", "revision": "1",
                                              "templates": self.rule("x", "team/{slug}")["templates"]})
        self.configure("external-skill", provider={"identity": "team/source", "template_source": str(provider)})
        original = provider.read_bytes()
        context = self.write("context.json", self.context)
        output = str(provider).upper() if os.name == "nt" else str(provider)
        result = subprocess.run([sys.executable, str(HELPER), "resolve", "--context", str(context),
                                 "--config-root", str(self.config), "--output", output],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("provider", json.loads(result.stderr)["error"])
        self.assertEqual(provider.read_bytes(), original)

    def test_provider_identity_and_symlink_are_not_silently_accepted(self):
        provider = self.write("source.json", {"schema_version": 1, "identity": "real", "revision": "1",
                                              "templates": self.rule("x", "safe/{slug}")["templates"]})
        with self.assertRaises(self.policy.PolicyError):
            self.configure("user-global", provider={"identity": "different", "template_source": str(provider)})
        link = self.root / "source-link.json"
        try:
            link.symlink_to(provider)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unavailable to this user")
        with self.assertRaises(self.policy.PolicyError):
            self.configure("user-global", provider={"identity": "real", "template_source": str(link)})
        self.assertFalse(self.config.exists())


if __name__ == "__main__":
    unittest.main()
