import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "skills/maintain-work-plan/scripts/work_plan.py"
SPEC = importlib.util.spec_from_file_location("work_plan", SCRIPT)
work_plan = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(work_plan)


class WorkPlanTests(unittest.TestCase):
    def setUp(self):
        self.task = dict(id="TASK-002", title="Экспорт", status="planned", depends_on=[], desired_date="2026-10-01",
                         starts_at="2026-10-01T10:00:00+05:00", duration_minutes=60)
        self.plan = dict(schema_version=1, project_id="stable", project_code="APP", id_prefix="TASK",
                         historical_ids=["TASK-001"], tasks=[self.task])
        self.state = dict(schema_version=1, calendar_id="cal", observation_complete=True,
                          unknown_outcome_task_ids=[], events=[], links=[])

    def desired(self):
        return dict(title="[APP] Экспорт", starts_at=self.task["starts_at"], duration_minutes=60)

    def linked(self):
        self.state["events"] = [dict(event_id="e", project_id="stable", task_id="TASK-002", managed=self.desired())]
        self.state["links"] = [dict(event_id="e", project_id="stable", task_id="TASK-002", last_synced=self.desired())]

    def operation(self):
        return work_plan.calendar_preview(self.plan, self.state)["operations"][0]

    def test_ids_reserve_history_allow_log_first_overlap_and_preserve_padding(self):
        self.plan["historical_ids"] += ["TASK-002", "TASK-0123"]
        before = copy.deepcopy(self.plan)
        self.assertEqual("TASK-0124", work_plan.validate_snapshot(self.plan)["next_id"])
        self.assertEqual(before, self.plan)
        self.plan["tasks"] = []
        self.assertEqual("TASK-0124", work_plan.validate_snapshot(self.plan)["next_id"])

    def test_alias_duplicates_and_unsupported_id_fail(self):
        for ids in (["TASK-2"], ["TASK-001", "TASK-001"], ["OTHER-003"]):
            with self.subTest(ids=ids):
                self.plan["historical_ids"] = ids
                with self.assertRaises(work_plan.PlanError):
                    work_plan.validate_snapshot(self.plan)

    def test_dependency_warnings_and_cycle(self):
        other = dict(self.task, id="TASK-003", desired_date="2026-10-03", depends_on=[])
        other["starts_at"] = "2026-10-03T10:00:00+05:00"
        self.plan["tasks"].append(other)
        self.task.update(desired_date="2026-10-01", depends_on=["TASK-003", "TASK-001"])
        result = work_plan.validate_snapshot(self.plan)
        self.assertEqual(["dependency_order", "dependency_date", "historical_dependency_outcome_unknown"],
                         [warning["code"] for warning in result["warnings"]])
        other["depends_on"] = ["TASK-002"]
        with self.assertRaisesRegex(work_plan.PlanError, "cycle"):
            work_plan.validate_snapshot(self.plan)

    def test_invalid_inputs_raise_controlled_error(self):
        mutations = [lambda p: p.update(schema_version=True),
                     lambda p: p["tasks"][0].update(status="completed"),
                     lambda p: p["tasks"][0].update(status={}),
                     lambda p: p.update(project_code="[APP]"),
                     lambda p: p["tasks"][0].update(desired_date=None),
                     lambda p: p["tasks"][0].update(desired_date="2026-02-30"),
                     lambda p: p["tasks"][0].update(depends_on=["TASK-999"]),
                     lambda p: p["tasks"][0].update(depends_on=["TASK-002"]),
                     lambda p: p["tasks"][0].update(duration_minutes=True),
                     lambda p: p["tasks"][0].update(starts_at="2026-10-01T10:00:00"),
                     lambda p: p["tasks"][0].update(starts_at="2026-10-01T10:00:00+05:99"),
                     lambda p: p["tasks"][0].pop("starts_at")]
        for mutate in mutations:
            candidate = copy.deepcopy(self.plan)
            mutate(candidate)
            with self.subTest(candidate=candidate), self.assertRaises(work_plan.PlanError):
                work_plan.validate_snapshot(candidate)

    def test_partial_and_pending_remain_supported_active_tasks(self):
        for status in ("partial", "acceptance_pending"):
            self.task["status"] = status
            self.assertTrue(work_plan.validate_snapshot(self.plan)["valid"])
            self.assertEqual(1, len(self.plan["tasks"]))

    def test_create_recover_noop_and_update(self):
        self.assertEqual("create", self.operation()["operation"])
        self.linked()
        link = self.state["links"].pop()
        self.assertEqual("recover", self.operation()["operation"])
        self.state["links"].append(link)
        self.assertEqual("noop", self.operation()["operation"])
        self.task["title"] = "New title"
        op = self.operation()
        self.assertEqual("update", op["operation"])
        self.assertEqual("e", op["event_id"])
        self.assertEqual("[APP] Экспорт", op["expected_managed"]["title"])

    def test_remote_changes_missing_mapping_and_duplicate_identity_conflict(self):
        self.linked()
        self.state["events"][0]["managed"]["title"] = "Remote edit"
        self.assertEqual("conflict", self.operation()["operation"])
        self.state["events"] = []
        self.assertEqual("conflict", self.operation()["operation"])
        self.linked()
        self.state["events"].append(dict(self.state["events"][0], event_id="e2"))
        self.assertEqual("duplicate_identity", self.operation()["reason"])

    def test_uncertain_outcome_blocks_create_but_allows_verified_recovery(self):
        self.state["unknown_outcome_task_ids"] = ["TASK-002"]
        self.assertEqual("unknown_outcome", self.operation()["reason"])
        self.linked()
        self.state["links"] = []
        self.assertEqual("recover", self.operation()["operation"])
        self.state["observation_complete"] = False
        self.assertEqual("incomplete_observation", self.operation()["reason"])

    def test_recovery_rejects_event_linked_to_another_identity(self):
        for project, task_id in (("foreign-project", "TASK-002"), ("stable", "TASK-003")):
            with self.subTest(project=project, task_id=task_id):
                self.linked()
                self.state["links"][0].update(project_id=project, task_id=task_id)
                before = copy.deepcopy((self.plan, self.state))
                op = self.operation()
                self.assertEqual("conflict", op["operation"])
                self.assertEqual("event_linked_elsewhere", op["reason"])
                self.assertEqual("e", op["event_id"])
                self.assertEqual(before, (self.plan, self.state))

    def test_namespace_and_offset_equivalence(self):
        self.linked()
        self.state["events"][0]["managed"]["starts_at"] = "2026-10-01T05:00:00+00:00"
        self.assertEqual("noop", self.operation()["operation"])
        self.plan["project_code"] = "RENAMED"
        self.assertEqual("update", self.operation()["operation"])
        self.state["events"][0]["project_id"] = "other"
        self.assertEqual("conflict", self.operation()["operation"])

    def test_removed_schedule_or_task_never_deletes(self):
        self.linked()
        del self.task["starts_at"], self.task["duration_minutes"]
        self.task["desired_date"] = None
        self.assertEqual("unlink_review", self.operation()["operation"])
        self.plan["tasks"] = []
        self.assertEqual("unlink_review", self.operation()["operation"])

    def test_calendar_strict_validation_and_input_preservation(self):
        before = copy.deepcopy((self.plan, self.state))
        result = work_plan.calendar_preview(self.plan, self.state)
        self.assertEqual(before, (self.plan, self.state))
        self.assertNotIn("attendees", json.dumps(result))
        self.state["attendees"] = ["someone@example.test"]
        with self.assertRaises(work_plan.PlanError):
            self.operation()

    def test_cli_read_only_status_validation_and_malformed_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "plan.json"
            source.write_text(json.dumps(self.plan), encoding="utf-8")
            old = source.read_bytes()
            for args in (["status"], ["validate", "--input", str(source)]):
                run = subprocess.run([sys.executable, str(SCRIPT), *args, "--json"], cwd=root, capture_output=True, text=True)
                self.assertEqual(0, run.returncode, run.stderr)
                json.loads(run.stdout)
            self.assertEqual(old, source.read_bytes())
            self.assertEqual([source], list(root.iterdir()))
            source.write_text("{", encoding="utf-8")
            run = subprocess.run([sys.executable, str(SCRIPT), "validate", "--input", str(source), "--json"], capture_output=True, text=True)
            self.assertEqual(2, run.returncode)
            self.assertIn("error", json.loads(run.stdout))
            self.assertNotIn("Traceback", run.stderr)
            source.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
            with self.assertRaisesRegex(work_plan.PlanError, "Duplicate"):
                work_plan.load(source)

    def test_all_day_create_recover_noop_update_and_timed_switch(self):
        del self.task["starts_at"], self.task["duration_minutes"]
        op = self.operation()
        self.assertEqual({"title": "[APP] Экспорт", "date": "2026-10-01"}, op["desired"])
        self.state["events"] = [dict(event_id="e", project_id="stable", task_id="TASK-002", managed=op["desired"].copy())]
        self.assertEqual("recover", self.operation()["operation"])
        self.state["links"] = [dict(event_id="e", project_id="stable", task_id="TASK-002", last_synced=op["desired"].copy())]
        self.assertEqual("noop", self.operation()["operation"])
        self.task["desired_date"] = "2026-10-02"
        self.assertEqual("update", self.operation()["operation"])
        self.task.update(starts_at="2026-10-02T10:00:00+05:00", duration_minutes=60)
        self.assertIn("starts_at", self.operation()["desired"])
        current = self.operation()["desired"]
        self.state["events"][0]["managed"] = current.copy()
        self.state["links"][0]["last_synced"] = current.copy()
        del self.task["starts_at"], self.task["duration_minutes"]
        self.assertEqual("update", self.operation()["operation"])
        self.assertIn("date", self.operation()["desired"])


if __name__ == "__main__":
    unittest.main()
