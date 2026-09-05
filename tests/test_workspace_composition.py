from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest

import test_lifecycle_workspace as lifecycle_fixture


VERIFIER = Path(__file__).resolve().parents[1] / "skills/verify-before-push/scripts/verify_before_push.py"


class WorkspaceCompositionTests(unittest.TestCase):
    def test_one_map_selects_same_clean_worktree_for_verifier_and_lifecycle(self):
        fixture = lifecycle_fixture.LifecycleWorkspaceTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        config_path = fixture.project / ".agents/verify-before-push/config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps({
            "version": 1,
            "repositories": [{"name": "app", "path": "app", "require_clean": True,
                              "require_upstream_current": True}],
            "checks": [{"name": "selected-worktree", "cwd": "app", "command": [
                sys.executable, "-c", "from pathlib import Path; assert Path.cwd().name == 'checkout'"
            ]}],
        }), encoding="utf-8")
        before_config = config_path.read_bytes()
        (fixture.repository / "unrelated.txt").write_text("preserve canonical work", encoding="utf-8")
        common = ["--project-root", str(fixture.project), "--workspace-map", str(fixture.map_path)]
        for command, extra in (("run", []), ("gate", ["--repository", str(fixture.mapped)])):
            result = subprocess.run([sys.executable, str(VERIFIER), command, *common, *extra],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(0, result.returncode, result.stderr)
        plan = fixture.plan()
        self.assertTrue(plan["ready"], plan["blockers"])
        receipts = list((fixture.workspace / ".verify-before-push-evidence").glob("*.json"))
        self.assertEqual(1, len(receipts))
        evidence = json.loads(receipts[0].read_text(encoding="utf-8"))
        selected = evidence["repositories"][0]
        self.assertEqual(fixture.mapped.resolve(), Path(selected["path"]))
        self.assertEqual(plan["repositories"][0]["head"], selected["head"])
        self.assertEqual("checkout", plan["workspace_map"]["repositories"]["app"])
        self.assertEqual(before_config, config_path.read_bytes())
        self.assertEqual("preserve canonical work", (fixture.repository / "unrelated.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
