from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from compose_skills import canonical_digest, load_catalog, resolve, verify_execution  # noqa: E402


class ComposeSkillsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = load_catalog(Path(__file__).resolve().parents[1] / "skill-catalog.json")

    def test_required_order_and_enabled_optional_steps(self) -> None:
        plan = resolve(self.catalog, "protected-push", {"notify-via-telegram"})
        self.assertEqual(
            ["synchronize-git-repositories", "verify-before-push", "notify-via-telegram"],
            [step["skill"] for step in plan["steps"]],
        )
        self.assertEqual([True, True, False], [step["required"] for step in plan["steps"]])

    def test_rejects_undeclared_optional_step(self) -> None:
        with self.assertRaisesRegex(ValueError, "not optional"):
            resolve(self.catalog, "protected-push", {"operate-yandex-cloud"})

    def evidence(self, plan: dict[str, object], statuses: list[str]) -> dict[str, object]:
        value: dict[str, object] = {
            "schema_version": 1,
            "composition": plan["composition"],
            "plan_sha256": plan["plan_sha256"],
            "steps": [
                {
                    "skill": step["skill"],
                    "status": status,
                    "evidence_sha256": "a" * 64 if status == "passed" else None,
                }
                for step, status in zip(plan["steps"], statuses, strict=True)
            ],
        }
        value["evidence_sha256"] = canonical_digest(value)
        return value

    def test_verifies_required_and_non_blocking_optional_results(self) -> None:
        plan = resolve(self.catalog, "protected-push", {"notify-via-telegram"})
        result = verify_execution(plan, self.evidence(plan, ["passed", "passed", "failed"]))
        self.assertTrue(result["passed"])
        self.assertEqual([], result["required_failures"])
        self.assertEqual(["notify-via-telegram"], result["optional_failures"])

    def test_required_failure_blocks_composition(self) -> None:
        plan = resolve(self.catalog, "protected-push", set())
        result = verify_execution(plan, self.evidence(plan, ["passed", "failed"]))
        self.assertFalse(result["passed"])
        self.assertEqual(["verify-before-push"], result["required_failures"])

    def test_rejects_stale_plan_binding(self) -> None:
        plan = resolve(self.catalog, "protected-push", set())
        evidence = self.evidence(plan, ["passed", "passed"])
        evidence["plan_sha256"] = "b" * 64
        unsigned = dict(evidence)
        unsigned.pop("evidence_sha256")
        evidence["evidence_sha256"] = canonical_digest(unsigned)
        with self.assertRaisesRegex(ValueError, "another plan"):
            verify_execution(plan, evidence)


if __name__ == "__main__":
    unittest.main()
