from __future__ import annotations

import json
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "skills/develop-with-test-first-evidence/scripts/evidence.py"


class TestFirstEvidenceTests(unittest.TestCase):
    def validate(self, document: dict) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(SCRIPT), "validate", "--input", str(path)],
                capture_output=True, text=True, check=False,
            )

    def evidence(self) -> dict:
        evidence = {
            "schema_version": 1,
            "behavior": "reject an invalid lifecycle checkpoint",
            "subject": {"kind": "commit", "identity": "a" * 40},
            "red": {
                "command": ["python", "-m", "unittest", "test_invalid_checkpoint"],
                "exit_code": 1,
                "summary": "assertion failed because invalid checkpoints were accepted",
                "failure_class": "intended_behavior",
                "intended_behavior_failure_reason": "the validation behavior is not implemented",
            },
            "green": {
                "focused": {"command": ["python", "-m", "unittest", "test_invalid_checkpoint"], "exit_code": 0, "summary": "focused behavior passes"},
                "broader": {"command": ["python", "-m", "unittest"], "exit_code": 0, "summary": "broader suite passes"},
            },
        }
        raw = json.dumps(evidence, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        evidence["evidence_digest"] = "sha256:" + hashlib.sha256(raw).hexdigest()
        return evidence

    def test_accepts_observed_red_then_green_evidence(self) -> None:
        result = self.validate(self.evidence())
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(json.loads(result.stdout)["valid"])

    def test_rejects_green_red_and_failing_green(self) -> None:
        evidence = self.evidence()
        evidence["red"]["exit_code"] = 0
        evidence["green"]["focused"]["exit_code"] = 2
        result = self.validate(evidence)
        self.assertNotEqual(0, result.returncode)
        errors = json.loads(result.stdout)["errors"]
        self.assertIn("red.exit_code must be nonzero", errors)
        self.assertIn("green.focused.exit_code must be zero", errors)

    def test_requires_behavior_runs_and_expected_failure_reason(self) -> None:
        evidence = self.evidence()
        del evidence["behavior"]
        result = self.validate(evidence)
        errors = json.loads(result.stdout)["errors"]
        self.assertIn("missing evidence.behavior", errors)

        evidence = self.evidence()
        del evidence["red"]["intended_behavior_failure_reason"]
        result = self.validate(evidence)
        errors = json.loads(result.stdout)["errors"]
        self.assertIn("missing red.intended_behavior_failure_reason", errors)

        evidence = self.evidence()
        del evidence["green"]["focused"]["summary"]
        result = self.validate(evidence)
        errors = json.loads(result.stdout)["errors"]
        self.assertIn("missing green.focused.summary", errors)


if __name__ == "__main__":
    unittest.main()
