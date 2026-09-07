from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import re
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from test_report_skill_feedback import feedback


class FeedbackFeaturesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.skill_root = self.root / "selected"
        self.skill_root.mkdir()
        self.skill_bytes = b"---\nname: review-code-changes\ndescription: Review changes.\n---\nBody\n"
        (self.skill_root / "SKILL.md").write_bytes(self.skill_bytes)
        (self.skill_root / "collection-metadata.json").write_text(json.dumps({
            "schema_version": 2, "skill": "review-code-changes", "version": "2.3.4"
        }), encoding="utf-8")
        self.answers = {
            "agent": {"name": "codex"},
            "environment": {"os": "windows", "project_kind": "application", "repository_count": 1},
            "invocation": {"expected": "explicit", "observed": "explicit"},
            "outcome": "partial", "signals": ["manual-correction"],
        }
        self.answers_path = self.root / "answers.json"
        self.answers_path.write_text(json.dumps(self.answers), encoding="utf-8")
        self.output = self.root / "input.json"

    def build_args(self, consent=True, **overrides):
        args = dict(answers=self.answers_path, skill_root=self.skill_root,
                    installation_scope="project", collection_consent=consent,
                    output=self.output, language=None)
        args.update(overrides)
        return argparse.Namespace(**args)

    def test_builder_uses_selected_artifact_not_reporter_version(self):
        result = feedback.build_input(self.build_args())
        value = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(value["skill"]["version"], "2.3.4")
        self.assertEqual(value["skill"]["artifact"]["skill_sha256"], hashlib.sha256(self.skill_bytes).hexdigest())
        self.assertEqual(result["observed_skill"]["version"], "2.3.4")
        self.assertEqual(result["reporter"]["name"], "report-skill-feedback")
        self.assertNotIn(str(self.skill_root), self.output.read_text(encoding="utf-8"))

    def test_prepare_is_pure_and_contains_no_answers(self):
        with mock.patch.object(Path, "read_bytes", side_effect=AssertionError("read")), \
             mock.patch.object(Path, "resolve", side_effect=AssertionError("resolve")), \
             mock.patch.object(feedback, "write_atomic", side_effect=AssertionError("write")), \
             mock.patch.object(feedback.shutil, "which", side_effect=AssertionError("discovery")), \
             mock.patch.object(feedback, "reporter_provenance", side_effect=AssertionError("metadata")):
            for language in ("en", "ru"):
                result = feedback.prepare(argparse.Namespace(skill="review-code-changes", language=language))
                self.assertNotIn("outcome", result)
                self.assertNotIn("answers", result)
                self.assertEqual(result["language"], language)
                self.assertTrue(all("default" not in item for item in result["questions"]))

    def test_all_consent_guards_precede_io(self):
        with mock.patch.object(Path, "read_bytes", side_effect=AssertionError("read")), \
             mock.patch.object(Path, "resolve", side_effect=AssertionError("resolve")), \
             mock.patch.object(feedback, "reporter_provenance", side_effect=AssertionError("metadata")):
            operations = [(feedback.build_input, self.build_args(False)),
                          (feedback.draft, argparse.Namespace(collection_consent=False)),
                          (feedback.submit, argparse.Namespace(submission_consent=False))]
            for operation, args in operations:
                with self.assertRaises(feedback.FeedbackError) as caught:
                    operation(args)
                self.assertEqual(caught.exception.submission_state, "not-attempted")

    def test_two_explicit_installations_preserve_byte_hash_and_local_roots(self):
        first = feedback.build_input(self.build_args())
        initial = json.loads(self.output.read_text(encoding="utf-8"))
        second_root = self.root / "another"
        second_root.mkdir()
        (second_root / "SKILL.md").write_bytes(self.skill_bytes)
        (second_root / "collection-metadata.json").write_text(json.dumps({
            "skill": "review-code-changes", "version": "8.9.0"
        }), encoding="utf-8")
        second = feedback.build_input(self.build_args(skill_root=second_root))
        final = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(first["observed_skill"]["version"], "2.3.4")
        self.assertEqual(second["observed_skill"]["version"], "8.9.0")
        self.assertEqual(initial["skill"]["artifact"], final["skill"]["artifact"])
        final["skill"]["version"] = "2.3.4"
        self.assertEqual(feedback.report_id(initial), feedback.report_id(final))
        self.assertNotIn(str(second_root), feedback.render(final))
        self.assertNotIn(str(second_root), json.dumps(final))
        self.assertIn("SKILL.md SHA-256", feedback.render(final))

    def test_invalid_or_missing_metadata_never_guesses(self):
        metadata = self.skill_root / "collection-metadata.json"
        for value in ({"skill": "other", "version": "1.0.0"},
                      {"skill": "review-code-changes"},
                      {"skill": "review-code-changes", "version": True},
                      {"skill": "review-code-changes", "version": "secret-version"}, []):
            with self.subTest(value=value):
                metadata.write_text(json.dumps(value), encoding="utf-8")
                with self.assertRaises(feedback.FeedbackError):
                    feedback.build_input(self.build_args())
        metadata.write_bytes(b"not json")
        with self.assertRaises(feedback.FeedbackError):
            feedback.build_input(self.build_args())
        metadata.unlink()
        with self.assertRaises(feedback.FeedbackError) as caught:
            feedback.build_input(self.build_args())
        self.assertNotIn(str(metadata), str(caught.exception))
        self.assertFalse(self.output.exists())

    def test_builder_rejects_injected_subject_and_fabricated_defaults(self):
        for field, value in (("skill", {"name": "other", "version": "1.0.0"}),
                             ("schema_version", 1), ("language", "en")):
            answers = {**self.answers, field: value}
            self.answers_path.write_text(json.dumps(answers), encoding="utf-8")
            with self.assertRaises(feedback.FeedbackError):
                feedback.build_input(self.build_args())
        answers = dict(self.answers)
        answers.pop("outcome")
        self.answers_path.write_text(json.dumps(answers), encoding="utf-8")
        with self.assertRaises(feedback.FeedbackError):
            feedback.build_input(self.build_args())

    def payload(self):
        return {"schema_version": 1, "skill": {"name": "review-code-changes", "version": "2.3.4"},
                **copy.deepcopy(self.answers)}

    def test_legacy_english_bytes_and_russian_seals(self):
        value = self.payload()
        identifier = feedback.report_id(value)
        body = (f"# Skill feedback: review-code-changes\n\nReport ID: `{identifier}`\n\n"
                "This report was prepared with explicit collection consent. Its body is de-identified, "
                "but a GitHub submission remains attributable to the submitting account.\n\n"
                "## Context\n\n- Skill version: `2.3.4`\n- Agent: `codex`\n- OS: `windows`\n"
                "- Project kind: `application`\n- Repository count: `1`\n"
                "- Expected invocation: `explicit`\n- Observed invocation: `explicit`\n"
                "- Outcome: `partial`\n\n## Signals\n\n- `manual-correction`\n")
        expected = body + f"<!-- report-skill-feedback:v1 sha256={hashlib.sha256(body.encode()).hexdigest()} -->\n"
        self.assertEqual(feedback.render(value), expected)
        value.update(language="ru", task_summary="Original user text", unclear="Untranslated input")
        russian = feedback.render(feedback.validate(value))
        self.assertIn("## Контекст", russian)
        self.assertIn("## Что было непонятно", russian)
        self.assertIn("Original user text", russian)
        self.assertIn("`manual-correction`", russian)
        self.assertNotEqual(identifier, feedback.report_id(value))
        for content in (expected, russian):
            self.output.write_text(content, encoding="utf-8", newline="\n")
            self.assertEqual(feedback.validate_report(self.output)[0], content)
        ru_id = feedback.report_id(value)
        value["language"] = "en"
        self.assertNotEqual(ru_id, feedback.report_id(value))

    def test_enum_and_boolean_validation_is_structured(self):
        updates = [("schema_version", True), ("schema_version", 1.0), ("outcome", []),
                   ("signals", [{}]), ("signals", [["manual-correction"]]),
                   ("agent", {"name": {}}), ("language", []),
                   ("invocation", {"expected": [], "observed": "explicit"}),
                   ("environment", {"os": [], "project_kind": "application", "repository_count": 1}),
                   ("evidence", [{"kind": [], "status": "passed", "summary": "Observed"}])]
        for key, value in updates:
            with self.subTest(key=key, value=value):
                payload = self.payload()
                payload[key] = value
                with self.assertRaises(feedback.FeedbackError):
                    feedback.validate(payload)

    def test_schema_version_pattern_matches_runtime(self):
        schema_path = Path(feedback.__file__).parents[1] / "schemas/feedback-input.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        pattern = schema["properties"]["skill"]["properties"]["version"]["pattern"]
        for version in ("1.2.3", "1.2.3-beta.1", "1.2.3+local", "1x2x3", "invalid"):
            self.assertEqual(bool(re.fullmatch(pattern, version)), bool(feedback.VERSION.fullmatch(version)))
        self.assertEqual(schema["properties"]["schema_version"]["type"], "integer")

    def submit_args(self):
        self.output.write_text(feedback.render(self.payload()), encoding="utf-8", newline="\n")
        return argparse.Namespace(report=self.output, submission_consent=True)

    def test_submit_unknown_categories_redact_secrets_and_never_retry(self):
        args = self.submit_args()
        secret = "ghp_1234567890123456789 C:\\private\\account person@example.test"
        for diagnostic, category in (("authentication failed", "auth"), ("connection failed", "network"),
                                     ("HTTP 503", "service"), ("validation rejected", "rejected"),
                                     ("unexpected failure", "unknown")):
            with self.subTest(category=category):
                completed = subprocess.CompletedProcess(["gh"], 1, secret, diagnostic + secret)
                with mock.patch.object(feedback.shutil, "which", return_value="gh"), \
                     mock.patch.object(feedback.subprocess, "run", return_value=completed) as run:
                    with self.assertRaises(feedback.FeedbackError) as caught:
                        feedback.submit(args)
                result = caught.exception.as_result()
                self.assertEqual(result["category"], category)
                self.assertEqual(result["submission_state"], "unknown")
                self.assertIsNone(result["submitted"])
                self.assertFalse(result["retry_allowed"])
                self.assertNotIn(secret, json.dumps(result))
                run.assert_called_once()
                self.assertLessEqual(run.call_args.kwargs["timeout"], 60)

    def test_timeout_and_invalid_success_are_unknown_spawn_failure_is_not_attempted(self):
        args = self.submit_args()
        cases = [subprocess.TimeoutExpired("private command", 60, stderr="private secret"),
                 subprocess.CompletedProcess(["gh"], 0, "https://github.com/other/repo/issues/1", "secret"),
                 OSError("C:\\secret\\gh private secret")]
        for index, case in enumerate(cases):
            kwargs = {"side_effect": case} if isinstance(case, Exception) else {"return_value": case}
            with mock.patch.object(feedback.shutil, "which", return_value="gh"), \
                 mock.patch.object(feedback.subprocess, "run", **kwargs) as run:
                with self.assertRaises(feedback.FeedbackError) as caught:
                    feedback.submit(args)
            result = caught.exception.as_result()
            self.assertEqual(result["submission_state"], "not-attempted" if index == 2 else "unknown")
            self.assertIs(result["submitted"], False if index == 2 else None)
            self.assertNotIn("secret", json.dumps(result))
            run.assert_called_once()
        with mock.patch.object(feedback.shutil, "which", return_value=None), \
             mock.patch.object(feedback.subprocess, "run") as run:
            with self.assertRaises(feedback.FeedbackError) as caught:
                feedback.submit(args)
            self.assertEqual(caught.exception.category, "missing-gh")
            self.assertFalse(caught.exception.as_result()["submitted"])
            run.assert_not_called()

    def test_reporter_unknown_metadata_is_controlled(self):
        with mock.patch.object(feedback, "artifact_metadata", side_effect=feedback.FeedbackError("unavailable")):
            reporter = feedback.reporter_provenance()
        self.assertEqual(reporter["name"], "report-skill-feedback")
        self.assertEqual(reporter["version"], "unknown")
        own_skill = Path(feedback.__file__).resolve().parents[1] / "SKILL.md"
        self.assertEqual(reporter["skill_sha256"], hashlib.sha256(own_skill.read_bytes()).hexdigest())
        with mock.patch.object(feedback, "artifact_metadata", side_effect=feedback.FeedbackError("unavailable")), \
             mock.patch.object(Path, "read_bytes", side_effect=OSError("private path")):
            self.assertEqual(feedback.reporter_provenance()["skill_sha256"], "unknown")

    def test_cli_build_language_and_safe_error_json(self):
        output = io.StringIO()
        with redirect_stdout(output):
            code = feedback.main(["build-input", "--answers", str(self.answers_path),
                                  "--skill-root", str(self.skill_root), "--installation-scope", "project",
                                  "--collection-consent", "--output", str(self.output), "--language", "ru", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(self.output.read_text(encoding="utf-8"))["language"], "ru")
        self.assertEqual(json.loads(output.getvalue())["operation"], "build-input")
        output = io.StringIO()
        with redirect_stdout(output):
            code = feedback.main(["draft", "--input", "C:/private/secret.json", "--collection-consent", "--json"])
        self.assertEqual(code, 1)
        result = json.loads(output.getvalue())
        self.assertEqual(result["category"], "local-io")
        self.assertNotIn("private", output.getvalue())

    def test_cli_parser_rejects_private_arguments_without_echoing_them(self):
        private = "C:/private/ghp_1234567890123456789"
        commands = [
            ["prepare", "--skill", "review-code-changes", "--language", private],
            ["prepare", "--skill", "review-code-changes", "--" + private],
            ["build-input", "--answers", "answers.json", "--skill-root", "selected",
             "--installation-scope", private, "--output", "output.json"],
        ]
        for command in commands:
            with self.subTest(command=command):
                stdout, stderr = io.StringIO(), io.StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    code = feedback.main(command)
                self.assertEqual(code, 1)
                result = json.loads(stdout.getvalue())
                self.assertEqual(result["category"], "validation")
                self.assertEqual(result["submission_state"], "not-attempted")
                self.assertFalse(result["submitted"])
                self.assertNotIn(private, stdout.getvalue() + stderr.getvalue())
        with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as caught:
            feedback.main(["--help"])
        self.assertEqual(caught.exception.code, 0)

    def malformed_json_samples(self):
        return [b'{"nested":' + b'[' * 15000 + b'0' + b']' * 15000 + b'}',
                b'{"number":' + b'9' * 20000 + b'}']

    def test_deep_json_and_overlong_integers_have_safe_validation_errors(self):
        for raw in self.malformed_json_samples():
            with self.subTest(size=len(raw)):
                self.answers_path.write_bytes(raw)
                with self.assertRaises(feedback.FeedbackError) as caught:
                    feedback.load_json(self.answers_path)
                result = caught.exception.as_result()
                self.assertEqual(result["category"], "validation")
                self.assertEqual(result["submission_state"], "not-attempted")
                self.assertNotIn(str(self.answers_path), json.dumps(result))

    def test_confirmed_submission_survives_malformed_reporter_metadata(self):
        args = self.submit_args()
        url = "https://github.com/kolabse/skills/issues/123"
        for raw in self.malformed_json_samples():
            with self.subTest(size=len(raw)):
                (self.skill_root / "collection-metadata.json").write_bytes(raw)
                with mock.patch.object(feedback, "__file__", str(self.skill_root / "scripts/report_feedback.py")), \
                     mock.patch.object(feedback.shutil, "which", return_value="gh"), \
                     mock.patch.object(feedback.subprocess, "run", return_value=subprocess.CompletedProcess(["gh"], 0, url, "")) as run:
                    result = feedback.submit(args)
                self.assertTrue(result["submitted"])
                self.assertEqual(result["issue_url"], url)
                self.assertEqual(result["reporter"]["version"], "unknown")
                run.assert_called_once()

    def test_confirmed_submission_survives_reporter_path_errors(self):
        args = self.submit_args()
        url = "https://github.com/kolabse/skills/issues/123"
        for error in (OSError("private path"), ValueError("private path"), RuntimeError("private path")):
            with self.subTest(error=type(error).__name__), \
                 mock.patch.object(Path, "resolve", side_effect=[self.output, error]), \
                 mock.patch.object(feedback.shutil, "which", return_value="gh"), \
                 mock.patch.object(feedback.subprocess, "run", return_value=subprocess.CompletedProcess(["gh"], 0, url, "")):
                result = feedback.submit(args)
            self.assertTrue(result["submitted"])
            self.assertEqual(result["issue_url"], url)
            self.assertEqual(result["reporter"]["root"], "unknown")
            self.assertNotIn("private", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
