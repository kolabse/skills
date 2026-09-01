from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/report-skill-feedback/scripts/report_feedback.py"
SPEC = importlib.util.spec_from_file_location("report_feedback", SCRIPT)
assert SPEC and SPEC.loader
feedback = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(feedback)


class ReportSkillFeedbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.input = self.root / "input.json"
        self.output = self.root / "report.md"
        self.payload = {
            "schema_version": 1,
            "skill": {"name": "review-code-changes", "version": "1.20.0"},
            "agent": {"name": "codex", "version": "desktop"},
            "environment": {"os": "windows", "project_kind": "application", "repository_count": 2},
            "invocation": {"expected": "automatic", "observed": "not-invoked"},
            "outcome": "partial",
            "signals": ["false-negative-trigger", "manual-correction"],
            "task_summary": "A review was requested, but the skill was selected only after an explicit reminder.",
            "evidence": [{"kind": "trigger", "status": "failed", "summary": "The expected skill was absent from the first response."}],
            "improvement": "Clarify the automatic trigger for direct review requests."
        }
        self.input.write_text(json.dumps(self.payload), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def draft_args(self, consent: bool = True):
        return type("Args", (), {"input": self.input, "output": self.output, "collection_consent": consent})()

    def test_draft_requires_consent_and_is_deterministic(self) -> None:
        with self.assertRaisesRegex(feedback.FeedbackError, "collection-consent"):
            feedback.draft(self.draft_args(False))
        first = feedback.draft(self.draft_args())
        content = self.output.read_bytes()
        second = feedback.draft(self.draft_args())
        self.assertEqual(first["report_id"], second["report_id"])
        self.assertEqual(content, self.output.read_bytes())
        self.assertFalse(first["submitted"])

    def test_draft_rejects_identifying_or_code_content(self) -> None:
        for unsafe in (
            "See https://internal.example.test/report",
            "Contact person@example.test",
            "Read C:\\secret\\project\\file.txt",
            "```python print('secret') ```",
        ):
            with self.subTest(unsafe=unsafe):
                value = dict(self.payload)
                value["task_summary"] = unsafe
                self.input.write_text(json.dumps(value), encoding="utf-8")
                with self.assertRaises(feedback.FeedbackError):
                    feedback.draft(self.draft_args())

    def test_submit_requires_separate_consent_and_exact_destination(self) -> None:
        feedback.draft(self.draft_args())
        declined = type("Args", (), {"report": self.output, "submission_consent": False})()
        with self.assertRaisesRegex(feedback.FeedbackError, "submission-consent"):
            feedback.submit(declined)
        approved = type("Args", (), {"report": self.output, "submission_consent": True})()
        completed = subprocess.CompletedProcess(
            ["gh"], 0, "https://github.com/kolabse/skills/issues/123\n", ""
        )
        with mock.patch.object(feedback.shutil, "which", return_value="gh"), mock.patch.object(
            feedback.subprocess, "run", return_value=completed
        ) as run:
            result = feedback.submit(approved)
        self.assertEqual("https://github.com/kolabse/skills/issues/123", result["issue_url"])
        argv = run.call_args.args[0]
        self.assertEqual(["gh", "issue", "create", "--repo", "kolabse/skills"], argv[:5])

    def test_modified_report_is_rejected(self) -> None:
        feedback.draft(self.draft_args())
        changed = self.output.read_text(encoding="utf-8").replace(
            "Clarify the automatic trigger", "Change the automatic trigger"
        )
        self.output.write_text(changed, encoding="utf-8")
        approved = type("Args", (), {"report": self.output, "submission_consent": True})()
        with self.assertRaisesRegex(feedback.FeedbackError, "changed after"):
            feedback.submit(approved)


if __name__ == "__main__":
    unittest.main()
