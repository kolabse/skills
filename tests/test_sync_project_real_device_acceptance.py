from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPT_DIRECTORY = Path(__file__).resolve().parents[1] / "skills" / "sync-project-context" / "scripts"
sys.path.insert(0, str(SCRIPT_DIRECTORY))
import real_device_acceptance  # noqa: E402


def draft(run_id: str = "run-alpha") -> dict[str, object]:
    return {
        "schema_version": 1,
        "kind": "sync-project-context-real-device",
        "run_id": run_id,
        "skill_version": "1.9.0-rc1",
        "backend": "google-drive",
        "machine_ids": ["machine-alpha", "machine-beta"],
        "product_versions": {"codex": "2026.815", "google-drive-connector": "0.1.11"},
        "scenarios": [
            {"name": name, "passed": True, "observations": {"checks": 1}}
            for name in real_device_acceptance.SCENARIOS
        ],
    }


class RealDeviceAcceptanceTests(unittest.TestCase):
    def test_public_schema_is_well_formed(self) -> None:
        import json

        schema = SCRIPT_DIRECTORY.parent / "schemas" / "real-device-acceptance.schema.json"
        document = json.loads(schema.read_text(encoding="utf-8"))
        self.assertEqual("https://json-schema.org/draft/2020-12/schema", document["$schema"])

    def test_seal_validate_and_verify_two_runs(self) -> None:
        first = real_device_acceptance.seal(draft("run-alpha"))
        second = real_device_acceptance.seal(draft("run-beta"))
        self.assertTrue(real_device_acceptance.validate(first)["passed"])
        self.assertTrue(real_device_acceptance.verify_promotion([first, second])["passed"])

    def test_failed_scenario_blocks_promotion(self) -> None:
        first_draft = draft("run-alpha")
        first_draft["scenarios"][0]["passed"] = False
        first = real_device_acceptance.seal(first_draft)
        second = real_device_acceptance.seal(draft("run-beta"))
        self.assertFalse(real_device_acceptance.verify_promotion([first, second])["passed"])

    def test_rejects_duplicate_runs_and_free_text(self) -> None:
        first = real_device_acceptance.seal(draft("run-alpha"))
        with self.assertRaisesRegex(real_device_acceptance.AcceptanceError, "distinct"):
            real_device_acceptance.verify_promotion([first, first])
        unsafe = draft()
        unsafe["notes"] = "C:/private/path"
        with self.assertRaisesRegex(real_device_acceptance.AcceptanceError, "unexpected"):
            real_device_acceptance.seal(unsafe)


if __name__ == "__main__":
    unittest.main()
