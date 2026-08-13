from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from compose_skills import load_catalog, resolve  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
