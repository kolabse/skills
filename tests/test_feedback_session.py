from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/report-skill-feedback/scripts/feedback_session.py"
REPORT = ROOT / "skills/report-skill-feedback/scripts/report_feedback.py"


class FeedbackSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "private-project"
        self.project.mkdir()
        self.ledger = self.root / "session.json"

    def run_cli(self, command, *args, ledger=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), command, "--ledger", str(ledger or self.ledger),
             "--project-root", str(self.project), *args], capture_output=True, text=True,
        )

    def create(self):
        result = self.run_cli("create", "--skill", "review-code-changes", "--skill", "review-code-changes")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_duplicate_reports_have_independent_advisory_states(self):
        self.create()
        result = self.run_cli("set", "--entry", "0", "--state", "collection-consented")
        self.assertEqual(result.returncode, 0, result.stdout)
        shown = json.loads(self.run_cli("show").stdout)
        self.assertIn("never", shown["advisory"])
        self.assertIn("collection", shown["advisory"])
        self.assertIn("submission", shown["advisory"])
        self.assertEqual([x["state"] for x in shown["ledger"]["entries"]], ["collection-consented", "eligible"])
        self.assertEqual(self.run_cli("append", "--skill", "review-code-changes").returncode, 0)
        self.assertEqual(len(json.loads(self.ledger.read_text())["entries"]), 3)

    def test_create_never_overwrites_existing_file(self):
        self.create()
        before = self.ledger.read_bytes()
        self.assertNotEqual(self.run_cli("create", "--skill", "other-skill").returncode, 0)
        self.assertEqual(self.ledger.read_bytes(), before)

    def test_project_paths_and_resolved_aliases_are_rejected(self):
        destination = self.project / "secret-ledger.json"
        result = self.run_cli("create", "--skill", "review-code-changes", ledger=destination)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(destination.exists())
        self.assertNotIn(str(self.project), result.stdout + result.stderr)
        alias = self.root / "alias"
        try:
            alias.symlink_to(self.project, target_is_directory=True)
        except OSError:
            return  # Windows may not grant symlink creation to the test user.
        self.assertNotEqual(self.run_cli("create", "--skill", "review-code-changes", ledger=alias / "ledger.json").returncode, 0)
        self.assertFalse((self.project / "ledger.json").exists())

    def test_invalid_entry_updates_preserve_valid_ledger(self):
        self.create()
        before = self.ledger.read_bytes()
        for index, state in [("-1", "submitted"), ("2", "submitted"), ("true", "submitted"), ("0", "private-path")]:
            with self.subTest(index=index, state=state):
                result = self.run_cli("set", "--entry", index, "--state", state)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.ledger.read_bytes(), before)
                self.assertNotIn("private-path", result.stdout + result.stderr)

    def test_malformed_or_excessive_ledgers_cannot_be_shown_or_updated(self):
        self.create()
        valid = json.loads(self.ledger.read_text())
        bad_values = [
            {**valid, "private": "secret-project"},
            {**valid, "schema_version": True},
            {**valid, "entries": [{"skill": "review-code-changes", "state": True}]},
            {**valid, "entries": [{"skill": "secret@example.com", "state": "eligible"}]},
            {**valid, "entries": [{"skill": "review-code-changes", "state": "unknown"}]},
            {**valid, "entries": [{"skill": "review-code-changes", "state": "eligible", "text": "private"}]},
            {**valid, "entries": valid["entries"] * 65},
            {**valid, "entries": []},
        ]
        raw_values = [json.dumps(value) for value in bad_values] + [" " * 65537, "{", '{"schema_version":1,"schema_version":1,"entries":[]}']
        for raw in raw_values:
            with self.subTest(raw=raw[:80]):
                self.ledger.write_text(raw, encoding="utf-8")
                before = self.ledger.read_bytes()
                for command, args in [("show", ()), ("set", ("--entry", "0", "--state", "submitted"))]:
                    result = self.run_cli(command, *args)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn("secret", result.stdout + result.stderr)
                    self.assertEqual(self.ledger.read_bytes(), before)

    def test_invalid_names_and_entry_limit_cannot_create_or_append(self):
        for name in ["", "../private", "secret@example.com", "plugin:review", "a" * 129]:
            self.assertNotEqual(self.run_cli("create", "--skill", name).returncode, 0)
            self.assertFalse(self.ledger.exists())
        self.create()
        value = json.loads(self.ledger.read_text())
        value["entries"] = value["entries"] * 64
        self.ledger.write_text(json.dumps(value))
        before = self.ledger.read_bytes()
        self.assertNotEqual(self.run_cli("append", "--skill", "review-code-changes").returncode, 0)
        self.assertEqual(self.ledger.read_bytes(), before)

    def test_ledger_consent_states_do_not_authorize_report_commands(self):
        self.create()
        self.assertEqual(self.run_cli("set", "--entry", "0", "--state", "collection-consented").returncode, 0)
        self.assertEqual(self.run_cli("set", "--entry", "1", "--state", "submission-consented").returncode, 0)
        for command, option, expected in [("draft", "--input", "collection-consent"), ("submit", "--report", "submission-consent")]:
            result = subprocess.run([sys.executable, str(REPORT), command, option, str(self.ledger), "--json"], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(expected, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
