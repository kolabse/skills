import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("bridge_release_ci", Path(__file__).resolve().parents[1] / "scripts/check_bridge_release_ci.py")
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)


class BridgeReleaseCITests(unittest.TestCase):
    def runs(self):
        return [{"id": i, "name": name, "head_sha": "commit", "event": "push",
                 "head_branch": "main", "status": "completed", "conclusion": "success"}
                for i, name in enumerate(ci.REQUIRED, 1)]

    def test_exact_main_commit_and_latest_success_required(self):
        runs = self.runs()
        self.assertEqual(len(ci.validate_runs(runs, "commit")), 3)
        for field, value in (("head_sha", "other"), ("event", "pull_request"),
                             ("head_branch", "feature"), ("conclusion", "failure"),
                             ("status", "in_progress")):
            changed = [dict(r) for r in runs]
            changed[0][field] = value
            with self.assertRaises(ValueError, msg=field):
                ci.validate_runs(changed, "commit")
        runs.append(dict(runs[0], id=99, status="in_progress", conclusion=None))
        with self.assertRaises(ValueError):
            ci.validate_runs(runs, "commit")

    def test_required_job_coverage_cannot_be_skipped(self):
        workflow = "Telegram bridge prototype"
        jobs = [{"name": name, "conclusion": "success"} for name in ci.REQUIRED[workflow]]
        ci.validate_jobs(jobs, workflow)
        with self.assertRaises(ValueError):
            ci.validate_jobs(jobs[:1], workflow)
        jobs[0]["conclusion"] = "skipped"
        with self.assertRaises(ValueError):
            ci.validate_jobs(jobs, workflow)
