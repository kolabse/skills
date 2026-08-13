from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.dont_write_bytecode = True
sys.path.insert(0, str(SCRIPTS))

from trigger_evals import (  # noqa: E402
    EvalError,
    markdown_report,
    prepare_suite,
    run_selector,
    score_suite,
)


class TriggerEvalTests(unittest.TestCase):
    def make_repository(self, root: Path) -> None:
        (root / "skills/demo").mkdir(parents=True)
        (root / "evals").mkdir()
        (root / "skills/demo/SKILL.md").write_text(
            '---\nname: demo\ndescription: "Handle demo requests."\n---\n\n# Demo\n',
            encoding="utf-8",
        )
        (root / "skill-catalog.json").write_text(
            json.dumps(
                {
                    "skills": [
                        {"name": "demo", "trigger_evals": "evals/demo.json"}
                    ]
                }
            ),
            encoding="utf-8",
        )
        (root / "evals/demo.json").write_text(
            json.dumps(
                {
                    "skill": "demo",
                    "positive": [{"prompt": "Do the demo", "reason": "yes"}],
                    "negative": [{"prompt": "Explain demos", "reason": "no"}],
                }
            ),
            encoding="utf-8",
        )

    def predictions(self, suite: dict, selected: dict[str, list[str]]) -> dict:
        return {
            "schema_version": 1,
            "suite_digest": suite["suite_digest"],
            "selector": {"provider": "fixture", "model": "deterministic"},
            "predictions": [
                {
                    "id": case["id"],
                    "selected_skills": selected.get(case["prompt"], []),
                    "reason": "fixture decision",
                }
                for case in suite["cases"]
            ],
        }

    def test_prepare_is_blind_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repository(root)
            first, assertions = prepare_suite(root)
            second, _ = prepare_suite(root)
            self.assertEqual(first, second)
            self.assertEqual(2, len(assertions))
            serialized = json.dumps(first)
            self.assertNotIn("expected", serialized)
            self.assertNotIn("target_skill", serialized)
            self.assertNotIn("reason\": \"yes", serialized)

    def test_scores_true_and_false_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repository(root)
            suite, assertions = prepare_suite(root)
            perfect = score_suite(
                suite,
                assertions,
                self.predictions(suite, {"Do the demo": ["demo"]}),
            )
            self.assertEqual(1.0, perfect["summary"]["accuracy"])
            failed = score_suite(
                suite,
                assertions,
                self.predictions(suite, {"Explain demos": ["demo"]}),
            )
            self.assertEqual(0.0, failed["summary"]["accuracy"])
            self.assertEqual(2, len(failed["failures"]))
            self.assertIn("Trigger evaluation report", markdown_report(failed))

    def test_runs_external_selector_over_standard_io(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repository(root)
            suite, assertions = prepare_suite(root)
            python = shutil.which("python") or shutil.which("python3")
            self.assertIsNotNone(python)
            program = (
                "import json,sys; s=json.load(sys.stdin); "
                "json.dump({'schema_version':1,'suite_digest':s['suite_digest'],"
                "'selector':{'provider':'fixture'},'predictions':[{'id':c['id'],"
                "'selected_skills':[],'reason':'fixture'} for c in s['cases']]},sys.stdout)"
            )
            predictions = run_selector([python, "-c", program], suite, timeout=10)
            report = score_suite(suite, assertions, predictions)
            self.assertEqual(2, report["summary"]["assertions"])

    def test_rejects_stale_or_incomplete_predictions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repository(root)
            suite, assertions = prepare_suite(root)
            stale = self.predictions(suite, {})
            stale["suite_digest"] = "0" * 64
            with self.assertRaisesRegex(EvalError, "do not match"):
                score_suite(suite, assertions, stale)
            incomplete = self.predictions(suite, {})
            incomplete["predictions"].pop()
            with self.assertRaisesRegex(EvalError, "incomplete"):
                score_suite(suite, assertions, incomplete)

    def test_rejects_duplicate_prompts_across_skills(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_repository(root)
            (root / "skills/other").mkdir()
            (root / "skills/other/SKILL.md").write_text(
                '---\nname: other\ndescription: "Other workflow."\n---\n',
                encoding="utf-8",
            )
            (root / "evals/other.json").write_text(
                json.dumps(
                    {
                        "skill": "other",
                        "positive": [{"prompt": "Do the demo", "reason": "x"}],
                        "negative": [],
                    }
                ),
                encoding="utf-8",
            )
            catalog = json.loads((root / "skill-catalog.json").read_text())
            catalog["skills"].append(
                {"name": "other", "trigger_evals": "evals/other.json"}
            )
            (root / "skill-catalog.json").write_text(json.dumps(catalog))
            with self.assertRaisesRegex(EvalError, "duplicated across"):
                prepare_suite(root)


if __name__ == "__main__":
    unittest.main()
