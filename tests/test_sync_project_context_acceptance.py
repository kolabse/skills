from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPT_DIRECTORY = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "sync-project-context"
    / "scripts"
)
sys.dont_write_bytecode = True
sys.path.insert(0, str(SCRIPT_DIRECTORY))

import context_sync_acceptance  # noqa: E402


class SyncProjectContextAcceptanceTests(unittest.TestCase):
    def test_two_machine_state_sequence_preserves_invariants(self) -> None:
        result = context_sync_acceptance.run_acceptance(stream_count=8)

        self.assertTrue(result["passed"])
        self.assertEqual(2, result["machines"])
        self.assertEqual(8, result["streams"])
        self.assertEqual(16, result["checkpoints"])
        self.assertIn("idempotent-repeated-restore", result["invariants"])


if __name__ == "__main__":
    unittest.main()
