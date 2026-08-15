from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIRECTORY = ROOT / "skills" / "release-skill-collection" / "scripts"
sys.dont_write_bytecode = True
sys.path.insert(0, str(SCRIPT_DIRECTORY))

import release_collection  # noqa: E402


class ReleaseSkillCollectionTests(unittest.TestCase):
    def test_status_is_read_only_and_reports_aligned_collection_versions(self) -> None:
        result = release_collection.inspect(ROOT)

        self.assertEqual("status", result["mode"])
        self.assertFalse(result["mutates_repository"])
        self.assertFalse(result["blockers"])
        self.assertEqual("1.7.0", result["versions"]["catalog"])
        self.assertEqual("1.7.0", result["versions"]["plugin"])
        self.assertEqual(
            "1.7.0", result["versions"]["skill:release-skill-collection"]
        )

    def test_plan_rejects_an_invalid_tag_without_running_checks(self) -> None:
        result = release_collection.inspect(ROOT, "release-latest")

        self.assertEqual("plan", result["mode"])
        self.assertFalse(result["ready_for_local_checks"])
        self.assertIn("invalid release tag: release-latest", result["blockers"])
        self.assertFalse(result["mutates_repository"])

    def test_current_version_is_a_complete_release_candidate(self) -> None:
        result = release_collection.inspect(ROOT, "v1.7.0")

        self.assertFalse(result["blockers"])
        self.assertEqual("1.7.0", result["target_version"])
        self.assertEqual(5, len(result["post_publication_steps"]))
        self.assertTrue(
            any("primary branch" in item for item in result["post_publication_steps"])
        )
        self.assertTrue(
            any("delete merged" in item for item in result["post_publication_steps"])
        )

    def test_check_refuses_dirty_candidate_and_repository_output(self) -> None:
        plan = release_collection.inspect(ROOT, "v1.7.0")
        plan["repository"]["dirty"] = True
        with patch.object(release_collection, "inspect", return_value=plan):
            result = release_collection.check(ROOT, "v1.7.0", ROOT / "dist")

        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"])
        self.assertTrue(any("clean worktree" in item for item in result["blockers"]))
        self.assertIn(
            "explicit output root must be outside the repository", result["blockers"]
        )


if __name__ == "__main__":
    unittest.main()
