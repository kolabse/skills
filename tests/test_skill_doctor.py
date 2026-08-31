from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import manage_installed_skills as manager  # noqa: E402


class SkillDoctorTests(unittest.TestCase):
    def make_skill(self, root: Path, name: str = "verify-before-push", version: str = "1.19.1") -> Path:
        path = root / name
        path.mkdir(parents=True, exist_ok=True)
        (path / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: A fixture skill.\n---\nBody.\n", encoding="utf-8"
        )
        (path / "collection-metadata.json").write_text(json.dumps({
            "schema_version": 2, "collection": "kolabse-skills", "skill": name,
            "version": version, "source": "https://github.com/kolabse/skills",
            "canonical_repository": "https://github.com/kolabse/skills",
        }), encoding="utf-8")
        return path

    def make_project(self, root: Path) -> Path:
        project = root / "project"
        self.make_skill(project / ".agents/skills")
        (project / "skills-lock.json").write_text(json.dumps({
            "version": 1, "skills": {"verify-before-push": {
                "source": "kolabse/skills", "sourceType": "github", "computedHash": "0" * 64,
            }},
        }), encoding="utf-8")
        return project

    def call(self, *args: str) -> tuple[int, dict, str]:
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                code = manager.main(list(args))
            except SystemExit as error:
                code = int(error.code)
        return code, json.loads(out.getvalue()) if out.getvalue() else {}, err.getvalue()

    def test_opt_in_doctor_reports_duplicate_versions_without_inventing_activation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = self.make_project(root)
            user_root = root / "explicit-user-skills"
            self.make_skill(user_root, version="1.18.0")
            code, result, error = self.call(
                "doctor", "--project-path", str(project), "--inspect-sources",
                "--skill-root", str(user_root), "--json",
            )
            self.assertEqual(0, code, error)
            diagnosis = result["source_diagnostics"]
            self.assertEqual(2, len(diagnosis["copies"]))
            self.assertEqual({"1.19.1", "1.18.0"}, {item["version"] for item in diagnosis["copies"]})
            self.assertIn("version-conflict", diagnosis["conflicts"][0]["kinds"])
            self.assertEqual("unknown", diagnosis["conflicts"][0]["effective_copy"])
            self.assertEqual("not-provided", diagnosis["observations"]["status"])
            observation = diagnosis["observations"]["skills"][0]
            self.assertEqual("unknown", observation["availability"])
            self.assertEqual("unknown", observation["invocation"])

    def test_default_doctor_has_no_inventory_and_ignores_external_roots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = self.make_project(Path(directory))
            before = manager.doctor(project)
            code, result, error = self.call("doctor", "--project-path", str(project), "--json")
            self.assertEqual(0, code, error)
            self.assertEqual(before, result)
            self.assertNotIn("source_diagnostics", result)

    def test_roots_require_explicit_inspection_switch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = self.make_project(Path(directory))
            for flag in ("--skill-root", "--plugin-root", "--observations"):
                with self.subTest(flag=flag):
                    code, result, error = self.call(
                        "doctor", "--project-path", str(project), flag, directory, "--json"
                    )
                    self.assertEqual(1, code)
                    self.assertIn("--inspect-sources", error)
                    self.assertEqual({}, result)

    def test_inventory_includes_unlocked_selected_project_skills_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = self.make_project(root)
            self.make_skill(project / ".agents/skills", name="custom-local-skill")
            self.make_skill(project / ".claude/skills", name="other-agent-skill")
            self.make_skill(root / "home/.codex/skills", name="unrequested-user-skill")
            with patch.object(Path, "home", side_effect=AssertionError("unexpected home discovery")):
                code, result, error = self.call(
                    "doctor", "--project-path", str(project), "--inspect-sources", "--json"
                )
            self.assertEqual(0, code, error)
            self.assertEqual({"custom-local-skill", "verify-before-push"},
                             {copy["skill"] for copy in result["source_diagnostics"]["copies"]})

    def test_explicit_plugin_uses_only_immediate_skills_not_manifest_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = self.make_project(root)
            plugin = root / "plugin-version"
            self.make_skill(plugin / "skills", name="plugin-skill")
            self.make_skill(plugin / "unrelated/skills", name="hidden-skill")
            (plugin / ".codex-plugin").mkdir()
            (plugin / ".codex-plugin/plugin.json").write_text(
                '{"name":"fixture","skills":"../unrelated-secret-path"}', encoding="utf-8"
            )
            code, result, error = self.call(
                "doctor", "--project-path", str(project), "--inspect-sources",
                "--plugin-root", str(plugin), "--json",
            )
            self.assertEqual(0, code, error)
            copies = result["source_diagnostics"]["copies"]
            self.assertEqual({"plugin-skill", "verify-before-push"}, {copy["skill"] for copy in copies})
            self.assertEqual(str(plugin), next(copy for copy in copies if copy["skill"] == "plugin-skill")["source_path"])

    def test_lockless_plugin_inventory_does_not_claim_healthy_install(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            plugin = root / "plugin"
            self.make_skill(plugin / "skills")
            code, result, error = self.call(
                "doctor", "--project-path", str(project), "--inspect-sources",
                "--plugin-root", str(plugin), "--json",
            )
            self.assertEqual(1, code, error)
            self.assertFalse(result["healthy"])
            self.assertEqual(1, len(result["source_diagnostics"]["copies"]))
            self.assertEqual("unknown", result["source_diagnostics"]["observations"]["skills"][0]["availability"])

    def observation_file(self, root: Path, **overrides: object) -> Path:
        value = {
            "schema_version": 1, "agent": "codex", "context_id": "task-123",
            "observed_at": "2026-08-31T12:00:00Z", "skills": [{
                "skill": "verify-before-push", "availability": "available", "invocation": "not-invoked",
            }],
        }
        value.update(overrides)
        path = root / "observations.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def test_user_observations_are_not_inferred_or_independently_verified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = self.make_project(root)
            observation = self.observation_file(root, skills=[
                {"skill": "verify-before-push", "availability": "available", "invocation": "not-invoked"},
                {"skill": "not-on-disk", "availability": "unknown", "invocation": "invoked"},
            ])
            code, result, error = self.call(
                "doctor", "--project-path", str(project), "--inspect-sources",
                "--observations", str(observation), "--json",
            )
            self.assertEqual(0, code, error)
            reported = result["source_diagnostics"]["observations"]
            self.assertEqual("user-reported", reported["status"])
            self.assertEqual("task-123", reported["context_id"])
            observed = {item["skill"]: item for item in reported["skills"]}
            self.assertEqual("not-invoked", observed["verify-before-push"]["invocation"])
            self.assertEqual("unknown", observed["not-on-disk"]["availability"])
            self.assertEqual("invoked", observed["not-on-disk"]["invocation"])
            self.assertIn("observations-not-independently-verified", result["source_diagnostics"]["limitations"])

    def test_observations_reject_wrong_agent_free_text_and_duplicate_rows_without_echo(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = self.make_project(root)
            cases = [
                {"agent": "claude-code"}, {"prompt": "private-token-that-must-not-leak"},
                {"context_id": "token=private-token-that-must-not-leak"},
                {"skills": [{"skill": "verify-before-push", "availability": "available", "invocation": "unknown"}] * 2},
                {"skills": [{"skill": "verify-before-push", "availability": True, "invocation": "unknown"}]},
                {"observed_at": "not-a-time"},
            ]
            for values in cases:
                with self.subTest(values=values):
                    observation = self.observation_file(root, **values)
                    code, result, error = self.call(
                        "doctor", "--project-path", str(project), "--inspect-sources",
                        "--observations", str(observation), "--json",
                    )
                    self.assertEqual(1, code)
                    self.assertEqual({}, result)
                    self.assertNotIn("private-token-that-must-not-leak", error)

    def test_same_version_content_and_source_conflicts_do_not_choose_winner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = self.make_project(root)
            user_root = root / "user-skills"
            copy = self.make_skill(user_root)
            (copy / "SKILL.md").write_text("Different payload", encoding="utf-8")
            metadata = json.loads((copy / "collection-metadata.json").read_text(encoding="utf-8"))
            metadata["source"] = "https://github.com/other/skills?token=do-not-print-this"
            (copy / "collection-metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
            code, result, error = self.call(
                "doctor", "--project-path", str(project), "--inspect-sources",
                "--skill-root", str(user_root), "--json",
            )
            self.assertEqual(0, code, error)
            diagnosis = result["source_diagnostics"]
            self.assertIn("source-conflict", diagnosis["conflicts"][0]["kinds"])
            self.assertIn("content-conflict", diagnosis["conflicts"][0]["kinds"])
            self.assertNotIn("do-not-print-this", json.dumps(diagnosis))
            self.assertEqual("unknown", diagnosis["conflicts"][0]["effective_copy"])

    def test_no_execution_or_writes_and_deep_never_includes_extra_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = self.make_project(root)
            extra = root / "user-skills"
            self.make_skill(extra, name="dangerous-extra")
            before = {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            with patch.object(manager.subprocess, "run", side_effect=AssertionError("unexpected execution")):
                code, _, error = self.call(
                    "doctor", "--project-path", str(project), "--inspect-sources",
                    "--skill-root", str(extra), "--json",
                )
            self.assertEqual(0, code, error)
            with patch.object(manager, "deep_runtime_doctor", return_value=([], [], [])) as deep:
                code, _, error = self.call(
                    "doctor", "--project-path", str(project), "--inspect-sources",
                    "--skill-root", str(extra), "--deep", "--json",
                )
                names = {item["name"] for item in deep.call_args.args[1]["skills"]}
                self.assertEqual({"verify-before-push"}, names)
                self.assertFalse(deep.call_args.kwargs["include_user_config"])
            self.assertEqual(0, code, error)
            self.assertEqual(before, {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()})

    def test_duplicate_root_arguments_deduplicate_copies_and_stay_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = self.make_project(root)
            extra = root / "user-skills"
            self.make_skill(extra)
            args = ("doctor", "--project-path", str(project), "--inspect-sources",
                    "--skill-root", str(extra), "--skill-root", str(extra), "--json")
            code, result, error = self.call(*args)
            self.assertEqual(0, code, error)
            self.assertEqual(2, len(result["source_diagnostics"]["copies"]))
            self.assertEqual(result, self.call(*args)[1])

    def test_missing_and_invalid_sources_are_reported_not_executed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = self.make_project(root)
            extra = root / "user-skills"
            copy = self.make_skill(extra)
            (copy / "collection-metadata.json").write_text("{bad-secret-json", encoding="utf-8")
            (copy / "SKILL.md").unlink()
            code, result, error = self.call(
                "doctor", "--project-path", str(project), "--inspect-sources",
                "--skill-root", str(extra), "--skill-root", str(root / "missing"), "--json",
            )
            self.assertEqual(0, code, error)
            diagnosis = result["source_diagnostics"]
            self.assertIn("missing", {item["status"] for item in diagnosis["sources"]})
            observed = next(item for item in diagnosis["copies"] if item["source_kind"] == "user-root")
            self.assertFalse(observed["installed"])
            self.assertEqual("invalid", observed["metadata_status"])
            self.assertNotIn("bad-secret-json", json.dumps(result))

    def test_symlinked_root_is_unsafe_and_never_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = self.make_project(root)
            outside = root / "outside"
            self.make_skill(outside, name="must-not-read")
            link = root / "linked"
            try:
                link.symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("directory symlinks require local OS privileges")
            code, result, error = self.call(
                "doctor", "--project-path", str(project), "--inspect-sources",
                "--skill-root", str(link), "--json",
            )
            self.assertEqual(0, code, error)
            self.assertEqual({"verify-before-push"}, {c["skill"] for c in result["source_diagnostics"]["copies"]})
            self.assertIn("unsafe", {s["status"] for s in result["source_diagnostics"]["sources"]})

    def test_duplicate_json_keys_are_rejected_without_echoing_contents(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = self.make_project(root)
            path = self.observation_file(root)
            raw = path.read_text(encoding="utf-8").replace('"agent": "codex"', '"agent": "claude-code", "agent": "codex"')
            path.write_text(raw, encoding="utf-8")
            code, result, _ = self.call(
                "doctor", "--project-path", str(project), "--inspect-sources",
                "--observations", str(path), "--json",
            )
            self.assertEqual(1, code)
            self.assertEqual({}, result)

    def test_high_confidence_credential_patterns_in_observation_identifiers_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = self.make_project(root)
            token = "ghp_" + "a" * 36
            path = self.observation_file(root, context_id=token)
            code, result, error = self.call(
                "doctor", "--project-path", str(project), "--inspect-sources",
                "--observations", str(path), "--json",
            )
            self.assertEqual(1, code)
            self.assertEqual({}, result)
            self.assertNotIn(token, error)

    def test_source_limits_and_oversized_files_fail_closed(self) -> None:
        import skill_doctor

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = self.make_project(root)
            extra = root / "extra"
            copy = self.make_skill(extra)
            (copy / "SKILL.md").write_bytes(b"x" * (skill_doctor.MAX_SKILL_BYTES + 1))
            (copy / "collection-metadata.json").write_bytes(b"x" * (skill_doctor.MAX_JSON_BYTES + 1))
            code, result, error = self.call(
                "doctor", "--project-path", str(project), "--inspect-sources",
                "--skill-root", str(extra), "--json",
            )
            self.assertEqual(0, code, error)
            observed = next(c for c in result["source_diagnostics"]["copies"] if c["source_kind"] == "user-root")
            self.assertFalse(observed["installed"])
            self.assertIn("skill-file-size-limit", observed["issues"])
            self.assertIn("metadata-file-size-limit", observed["issues"])
            with patch.object(skill_doctor, "MAX_ENTRIES", 0):
                diagnosis = skill_doctor.inspect_sources(project, "codex")
                self.assertEqual("source-entry-limit", diagnosis["sources"][0]["reason_code"])
                self.assertEqual([], diagnosis["copies"])
            with self.assertRaisesRegex(skill_doctor.InspectionError, "source-root-limit"):
                skill_doctor.inspect_sources(project, "codex", [extra] * skill_doctor.MAX_ROOTS)

    def test_windows_reparse_points_are_rejected_without_privileged_fixture(self) -> None:
        import skill_doctor

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = self.make_project(root)
            extra = root / "junction"
            self.make_skill(extra, name="not-inspected")
            original = Path.lstat

            def lstat(path: Path):
                info = original(path)
                return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400) if path == extra else info

            with patch.object(Path, "lstat", lstat):
                diagnosis = skill_doctor.inspect_sources(project, "codex", [extra])
            self.assertEqual({"verify-before-push"}, {c["skill"] for c in diagnosis["copies"]})
            self.assertEqual("unsafe", diagnosis["sources"][1]["status"])

    def test_local_lock_sources_are_not_followed_and_sensitive_source_urls_are_sanitized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = self.make_project(root)
            lock_path = project / "skills-lock.json"
            value = json.loads(lock_path.read_text(encoding="utf-8"))
            entry = value["skills"]["verify-before-push"]
            entry.update(source=str(root / "do-not-inspect"), sourceType="local")
            lock_path.write_text(json.dumps(value), encoding="utf-8")
            with patch.object(manager, "validate_local_source", side_effect=AssertionError("unrequested local source read")):
                code, result, error = self.call(
                    "doctor", "--project-path", str(project), "--inspect-sources", "--json"
                )
            self.assertEqual(1, code, error)
            self.assertEqual("mismatch", result["skills"][0]["provenance_status"])
            self.assertNotIn("do-not-inspect", json.dumps(result))
            entry.update(source="https://user:secret@github.com/kolabse/skills?token=private", sourceType="github")
            lock_path.write_text(json.dumps(value), encoding="utf-8")
            code, result, error = self.call(
                "doctor", "--project-path", str(project), "--inspect-sources", "--json"
            )
            self.assertEqual(0, code, error)
            self.assertNotIn("secret", json.dumps(result))
            self.assertNotIn("private", json.dumps(result))

    def test_observation_paths_only_reference_already_inspected_copies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = self.make_project(root)
            copy_path = str(project / ".agents/skills/verify-before-push")
            for selected, expected in ((copy_path, 0), (str(root / "outside"), 1)):
                with self.subTest(selected=selected):
                    path = self.observation_file(root, skills=[{
                        "skill": "verify-before-push", "availability": "available", "invocation": "unknown",
                        "copy_path": selected,
                    }])
                    code, result, error = self.call(
                        "doctor", "--project-path", str(project), "--inspect-sources",
                        "--observations", str(path), "--json",
                    )
                    self.assertEqual(expected, code, error)
                    if expected == 0:
                        self.assertEqual(copy_path, result["source_diagnostics"]["observations"]["skills"][0]["copy_path"])

    def assert_schema(self, value: object, schema: dict, document: dict | None = None) -> None:
        # Dependency-free validation of every keyword used by these two schemas.
        document = document or schema
        if "$ref" in schema:
            node = document
            for part in schema["$ref"].removeprefix("#/").split("/"):
                node = node[part]
            self.assert_schema(value, node, document)
            return
        types = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}
        if "type" in schema:
            names = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
            self.assertTrue(any(type(value) is types[name] for name in names))
        if "const" in schema:
            self.assertEqual(schema["const"], value)
        if "enum" in schema:
            self.assertIn(value, schema["enum"])
        if isinstance(value, dict):
            self.assertTrue(set(schema.get("required", [])) <= set(value))
            if schema.get("additionalProperties") is False:
                self.assertTrue(set(value) <= set(schema.get("properties", {})))
            for key, item in value.items():
                if key in schema.get("properties", {}):
                    self.assert_schema(item, schema["properties"][key], document)
        elif isinstance(value, list):
            self.assertLessEqual(len(value), schema.get("maxItems", len(value)))
            self.assertGreaterEqual(len(value), schema.get("minItems", 0))
            if schema.get("uniqueItems"):
                self.assertEqual(len(value), len({json.dumps(item, sort_keys=True) for item in value}))
            for item in value:
                self.assert_schema(item, schema.get("items", {}), document)
        elif isinstance(value, str):
            self.assertLessEqual(len(value), schema.get("maxLength", len(value)))
            if "pattern" in schema:
                self.assertRegex(value, schema["pattern"])
            if schema.get("format") == "date-time":
                from datetime import datetime
                datetime.fromisoformat(value.replace("Z", "+00:00"))

    def test_public_schemas_match_actual_observations_and_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = self.make_project(root)
            extra = root / "extra"
            self.make_skill(extra, version="1.0.0")
            path = self.observation_file(root)
            input_schema = json.loads((ROOT / "schemas/skill-doctor-observations.schema.json").read_text(encoding="utf-8"))
            result_schema = json.loads((ROOT / "schemas/skill-doctor-result.schema.json").read_text(encoding="utf-8"))
            self.assert_schema(json.loads(path.read_text(encoding="utf-8")), input_schema)
            code, result, error = self.call(
                "doctor", "--project-path", str(project), "--inspect-sources",
                "--skill-root", str(extra), "--observations", str(path), "--json",
            )
            self.assertEqual(0, code, error)
            self.assert_schema(result["source_diagnostics"], result_schema)

    def deep_fixture(self, root: Path) -> tuple[Path, Path]:
        project = self.make_project(root)
        script = project / ".agents/skills/verify-before-push/scripts/status.py"
        script.parent.mkdir()
        script.write_text("print('status fixture')\n", encoding="utf-8")
        (root / "skill-catalog.json").write_text(json.dumps({"skills": [{
            "name": "verify-before-push", "configuration": {
                "scope": "project", "status": ["python", "scripts/status.py"],
            },
        }]}), encoding="utf-8")
        return project, script

    def test_opt_in_deep_never_executes_unverified_project_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project, _ = self.deep_fixture(root)
            lock = project / "skills-lock.json"
            value = json.loads(lock.read_text(encoding="utf-8"))
            value["skills"]["verify-before-push"]["source"] = "other/skills"
            lock.write_text(json.dumps(value), encoding="utf-8")
            with patch.object(manager.subprocess, "run", return_value=subprocess.CompletedProcess(
                [], 0, stdout='{"configured":true,"valid":true}', stderr=""
            )) as execute:
                state = manager.doctor(project, inspect_sources=True, deep=True, repository_root=root)
            self.assertEqual(0, execute.call_count, "unverified installed copy must never be executed")
            self.assertFalse(state["healthy"])
            self.assertEqual("blocked-unverified", state["runtime_checks"][0]["status"])

    def test_opt_in_deep_rejects_reparse_script_ancestor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project, script = self.deep_fixture(root)
            original = Path.lstat

            def lstat(path: Path):
                info = original(path)
                return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400) if path == script.parent else info

            with patch.object(Path, "lstat", lstat), patch.object(
                manager.subprocess, "run", return_value=subprocess.CompletedProcess(
                    [], 0, stdout='{"configured":true,"valid":true}', stderr=""
                )
            ) as execute:
                state = manager.doctor(project, inspect_sources=True, deep=True, repository_root=root)
            self.assertEqual(0, execute.call_count, "a reparse-linked script ancestor must block execution")
            self.assertFalse(state["healthy"])
            self.assertEqual("invalid-declaration", state["runtime_checks"][0]["status"])

    def test_opt_in_deep_accepts_only_verified_safe_exact_python_script(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project, script = self.deep_fixture(root)
            with patch.object(manager.subprocess, "run", return_value=subprocess.CompletedProcess(
                [], 0, stdout='{"configured":true,"valid":true}', stderr=""
            )) as execute:
                state = manager.doctor(project, inspect_sources=True, deep=True, repository_root=root)
            self.assertTrue(state["healthy"])
            self.assertEqual([manager.python_executable(), str(script)], execute.call_args.args[0])
            declarations = (["python", str(script)], ["python", "scripts/../scripts/status.py"],
                            ["python", "-c", "print('unsafe')"], ["sh", "scripts/status.py"])
            for command in declarations:
                with self.subTest(command=command):
                    catalog = {"skills": [{"name": "verify-before-push", "configuration": {
                        "scope": "project", "status": command,
                    }}]}
                    (root / "skill-catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
                    with patch.object(manager.subprocess, "run") as execute:
                        state = manager.doctor(project, inspect_sources=True, deep=True, repository_root=root)
                    execute.assert_not_called()
                    self.assertFalse(state["healthy"])
                    self.assertEqual("invalid-declaration", state["runtime_checks"][0]["status"])

    def test_opt_in_deep_blocks_missing_metadata_and_reparse_script_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project, script = self.deep_fixture(root)
            metadata = script.parent.parent / "collection-metadata.json"
            metadata.unlink()
            with patch.object(manager.subprocess, "run") as execute:
                state = manager.doctor(project, inspect_sources=True, deep=True, repository_root=root)
            execute.assert_not_called()
            self.assertEqual("blocked-unverified", state["runtime_checks"][0]["status"])
            self.make_skill(project / ".agents/skills")
            original = Path.lstat

            def lstat(path: Path):
                info = original(path)
                return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400) if path == script else info

            with patch.object(Path, "lstat", lstat), patch.object(manager.subprocess, "run") as execute:
                state = manager.doctor(project, inspect_sources=True, deep=True, repository_root=root)
            execute.assert_not_called()
            self.assertEqual("invalid-declaration", state["runtime_checks"][0]["status"])


if __name__ == "__main__":
    unittest.main()
