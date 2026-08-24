from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1] / "scripts"
sys.dont_write_bytecode = True
sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from smoke_marketplaces import smoke  # noqa: E402


class MarketplaceSmokeTests(unittest.TestCase):
    def test_repository_marketplaces_expose_the_collection(self) -> None:
        repository = Path(__file__).resolve().parents[1]

        result = smoke(repository)

        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual("kolabse", result["marketplace"])
        self.assertEqual("kolabse-skills", result["plugin"])
        self.assertEqual(
            result["versions"]["codex"],
            result["versions"]["claude-code"],
        )
        self.assertGreater(result["skill_count"], 0)


if __name__ == "__main__":
    unittest.main()
