import argparse
import importlib.util
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "maintain-project-digest" / "scripts" / "project_digest.py"
SPEC = importlib.util.spec_from_file_location("project_digest", SCRIPT)
assert SPEC and SPEC.loader
project_digest = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(project_digest)


class ProjectDigestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.docs = self.root / "docs"
        self.docs.mkdir()
        self.input = self.root / "changes.json"

    def tearDown(self):
        self.temp.cleanup()

    def write_changes(self, changes):
        self.input.write_text(
            json.dumps({"schema_version": 1, "changes": changes}, ensure_ascii=False),
            encoding="utf-8",
        )

    def args(self, command, expected=None):
        values = {
            "command": command,
            "project_root": str(self.root),
            "documentation_root": str(self.docs),
            "digest_file": "project-digest.md",
            "input": str(self.input),
            "json": True,
        }
        if expected is not None:
            values["expected_sha256"] = expected
        return argparse.Namespace(**values)

    def test_plan_and_apply_create_categorized_digest(self):
        self.write_changes(
            [
                {"category": "fixed", "summary": "Форма больше не отправляется дважды."},
                {"category": "new", "summary": "Добавлен список категорий товара."},
            ]
        )
        plan = project_digest.make_plan(self.args("plan"))
        self.assertEqual("create", plan["action"])
        self.assertEqual("missing", plan["expected_sha256"])

        result = project_digest.apply_plan(
            self.args("apply", plan["expected_sha256"])
        )
        content = (self.docs / "project-digest.md").read_text(encoding="utf-8")
        self.assertEqual("created", result["action"])
        self.assertIn(f"## [{date.today().isoformat()}]", content)
        self.assertLess(content.index("### Доработки"), content.index("### Исправления"))
        self.assertNotIn("### Улучшения", content)

    def test_same_entry_is_idempotent_across_categories(self):
        summary = "Поиск стал быстрее."
        self.write_changes([{"category": "improved", "summary": summary}])
        first = project_digest.make_plan(self.args("plan"))
        project_digest.apply_plan(self.args("apply", first["expected_sha256"]))

        self.write_changes([{"category": "fixed", "summary": "  ПОИСК стал быстрее  "}])
        second = project_digest.make_plan(self.args("plan"))
        self.assertEqual("unchanged", second["action"])
        self.assertEqual([], second["added"])
        self.assertEqual(1, second["preview"].count("Поиск стал быстрее."))

    def test_stale_plan_does_not_overwrite_another_writer(self):
        self.write_changes([{"category": "new", "summary": "Добавлен экспорт."}])
        stale = project_digest.make_plan(self.args("plan"))

        target = self.docs / "project-digest.md"
        target.write_text("# Дайджест проекта\n", encoding="utf-8")
        with self.assertRaisesRegex(project_digest.DigestError, "changed after planning"):
            project_digest.apply_plan(self.args("apply", stale["expected_sha256"]))
        self.assertEqual("# Дайджест проекта\n", target.read_text(encoding="utf-8"))
        self.assertFalse((self.docs / "project-digest.md.lock").exists())

    def test_existing_lock_fails_without_removing_it(self):
        self.write_changes([{"category": "new", "summary": "Добавлен экспорт."}])
        lock = self.docs / "project-digest.md.lock"
        lock.write_text("other writer\n", encoding="utf-8")
        with self.assertRaisesRegex(project_digest.DigestError, "locked"):
            project_digest.apply_plan(self.args("apply", "missing"))
        self.assertTrue(lock.exists())

    def test_only_today_section_changes(self):
        today = date.today().isoformat()
        old_text = (
            "# Дайджест проекта\r\n\r\n"
            f"## [{today}]\r\n\r\n### Доработки\r\n\r\n- Добавлен поиск.\r\n\r\n"
            "## [2020-01-01]\r\n\r\n### Исправления\r\n\r\n- Исправлена старая ошибка.\r\n"
        )
        old = old_text.encode("utf-8")
        target = self.docs / "project-digest.md"
        target.write_bytes(old)
        old_marker = "## [2020-01-01]".encode("utf-8")
        old_section = old[old.index(old_marker) :]
        self.write_changes([{"category": "docs", "summary": "Добавлена инструкция по поиску."}])
        plan = project_digest.make_plan(self.args("plan"))
        project_digest.apply_plan(self.args("apply", plan["expected_sha256"]))
        updated = target.read_bytes()
        self.assertEqual(old_section, updated[updated.index(old_marker) :])

    def test_rejects_unknown_today_structure(self):
        today = date.today().isoformat()
        (self.docs / "project-digest.md").write_text(
            f"# Дайджест проекта\n\n## [{today}]\n\nПроизвольный текст.\n",
            encoding="utf-8",
        )
        self.write_changes([{"category": "fixed", "summary": "Исправлен вход."}])
        with self.assertRaisesRegex(project_digest.DigestError, "unfamiliar structure"):
            project_digest.make_plan(self.args("plan"))

    def test_rejects_sensitive_value_in_summary(self):
        self.write_changes(
            [{"category": "security", "summary": "Обновлён token=top-secret-value"}]
        )
        with self.assertRaisesRegex(project_digest.DigestError, "sensitive value"):
            project_digest.make_plan(self.args("plan"))

    def test_status_reports_ambiguous_documentation(self):
        (self.root / "documentation").mkdir()
        payload = project_digest.status(
            argparse.Namespace(
                project_root=str(self.root),
                documentation_root=None,
                digest_file="project-digest.md",
            )
        )
        self.assertEqual("ambiguous", payload["resolution"])
        self.assertEqual(2, len(payload["documentation_candidates"]))


if __name__ == "__main__":
    unittest.main()
