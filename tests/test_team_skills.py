from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/synchronize-team-skills/scripts/team_skills.py"
SPEC = importlib.util.spec_from_file_location("team_skills", SCRIPT)
assert SPEC and SPEC.loader
team_skills = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(team_skills)


class TeamSkillsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.docs = self.root / "docs"
        self.docs.mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def configure_args(self, **overrides: object) -> argparse.Namespace:
        values: dict[str, object] = {
            "project_root": str(self.root),
            "documentation_root": str(self.docs),
            "collection_version": "1.18.0",
            "agent": ["codex"],
            "skill": [
                "synchronize-git-repositories",
                "synchronize-team-skills",
                "verify-before-push",
            ],
            "json": True,
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def apply_args(self, expected: str, **overrides: object) -> argparse.Namespace:
        current_plan = team_skills.make_plan(self.root, str(self.docs))
        values: dict[str, object] = {
            "project_root": str(self.root),
            "documentation_root": str(self.docs),
            "expected_manifest_sha256": expected,
            "expected_plan_sha256": current_plan["plan_sha256"],
            "yes": True,
            "json": True,
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def install(self, name: str, version: str = "1.18.0", agent: str = "codex") -> Path:
        layout = self.root / team_skills.AGENT_LAYOUTS[agent]
        skill = layout / name
        skill.mkdir(parents=True, exist_ok=True)
        metadata = {
            "schema_version": 2,
            "collection": "kolabse-skills",
            "version": version,
            "skill": name,
            "source": team_skills.CANONICAL_SOURCE,
            "canonical_repository": team_skills.CANONICAL_SOURCE,
        }
        (skill / "collection-metadata.json").write_text(
            json.dumps(metadata), encoding="utf-8"
        )
        lock_path = self.root / "skills-lock.json"
        lock = (
            json.loads(lock_path.read_text(encoding="utf-8"))
            if lock_path.is_file()
            else {"version": 1, "skills": {}}
        )
        lock["skills"][name] = {
            "source": "kolabse/skills",
            "sourceType": "github",
            "computedHash": team_skills.skill_folder_hash(skill),
        }
        lock_path.write_text(json.dumps(lock), encoding="utf-8")
        return skill

    def test_configure_is_idempotent_and_requires_bootstrap_skill(self) -> None:
        first = team_skills.configure(self.configure_args())
        content = (self.docs / team_skills.DOCUMENT_NAME).read_bytes()
        second = team_skills.configure(self.configure_args())

        self.assertTrue(first["changed"])
        self.assertFalse(second["changed"])
        self.assertEqual(content, (self.docs / team_skills.DOCUMENT_NAME).read_bytes())
        with self.assertRaisesRegex(team_skills.TeamSkillsError, "bootstrap dependencies"):
            team_skills.configure(
                self.configure_args(skill=["verify-before-push"])
            )

    def test_manifest_rejects_unknown_collection_skill(self) -> None:
        with self.assertRaisesRegex(team_skills.TeamSkillsError, "unknown collection"):
            team_skills.configure(
                self.configure_args(
                    skill=[
                        "synchronize-git-repositories",
                        "synchronize-team-skills",
                        "verify-before-puhs",
                    ]
                )
            )

    def test_known_skills_match_collection_catalog(self) -> None:
        catalog = json.loads((ROOT / "skill-catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(
            {item["name"] for item in catalog["skills"]},
            team_skills.KNOWN_SKILLS,
        )

    def test_canonical_github_source_matches_installer_forms(self) -> None:
        for source in (
            "kolabse/skills",
            "https://github.com/kolabse/skills",
            "https://www.github.com/kolabse/skills.git",
            "git@github.com:kolabse/skills",
            "ssh://git@github.com/kolabse/skills",
            "https://github.com/kolabse/skills/tree/v1.18.0",
            "kolabse/skills@v1.18.0",
        ):
            with self.subTest(source=source):
                self.assertTrue(team_skills.canonical_github_source(source))
        self.assertFalse(team_skills.canonical_github_source("example/skills"))
        self.assertFalse(
            team_skills.canonical_github_source(
                "https://example.com/kolabse/skills"
            )
        )

    def test_observation_accepts_normalized_metadata_provenance(self) -> None:
        skill = self.install("verify-before-push")
        metadata_path = skill / "collection-metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["source"] = "ssh://git@github.com/kolabse/skills"
        metadata["canonical_repository"] = (
            "https://www.github.com/kolabse/skills.git"
        )
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
        lock_path = self.root / "skills-lock.json"
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        lock["skills"]["verify-before-push"]["computedHash"] = (
            team_skills.skill_folder_hash(skill)
        )
        lock_path.write_text(json.dumps(lock), encoding="utf-8")

        observed = team_skills.observe_skill(
            self.root,
            skill,
            "verify-before-push",
            "1.18.0",
            lock["skills"]["verify-before-push"],
        )

        self.assertEqual("verified", observed["provenance"])

    def test_managed_document_accepts_crlf_line_endings(self) -> None:
        team_skills.configure(self.configure_args())
        path = self.docs / team_skills.DOCUMENT_NAME
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))

        status = team_skills.inspect(self.root, str(self.docs))

        self.assertTrue(status["configured"])
        self.assertEqual("1.18.0", status["collection_version"])

    def test_managed_document_rejects_end_before_start_without_traceback(self) -> None:
        path = self.docs / team_skills.DOCUMENT_NAME
        path.write_text(
            f"{team_skills.END}\n{team_skills.START}\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(team_skills.TeamSkillsError, "out of order"):
            team_skills.inspect(self.root, str(self.docs))

    def test_relative_documentation_root_is_resolved_from_project_root(self) -> None:
        args = self.configure_args(documentation_root="docs")

        configured = team_skills.configure(args)

        self.assertTrue(
            Path(configured["document"]).samefile(
                self.docs / team_skills.DOCUMENT_NAME
            )
        )

    def test_status_reports_versions_extras_and_project_overrides_without_writes(self) -> None:
        team_skills.configure(self.configure_args())
        self.install("synchronize-git-repositories")
        self.install("synchronize-team-skills")
        self.install("verify-before-push", "1.4.0")
        self.install("notify-via-telegram")
        before = sorted(path.relative_to(self.root) for path in self.root.rglob("*"))

        status = team_skills.inspect(self.root, str(self.docs))

        after = sorted(path.relative_to(self.root) for path in self.root.rglob("*"))
        states = {item["name"]: item for item in status["agents"][0]["skills"]}
        self.assertEqual("current", states["synchronize-team-skills"]["state"])
        self.assertEqual("current", states["synchronize-git-repositories"]["state"])
        self.assertEqual("outdated", states["verify-before-push"]["state"])
        self.assertTrue(states["verify-before-push"]["project_override"])
        self.assertEqual(["notify-via-telegram"], [item["name"] for item in status["agents"][0]["extras"]])
        self.assertFalse(status["ready"])
        self.assertEqual(before, after)

    def test_status_accepts_verified_canonical_local_checkout(self) -> None:
        team_skills.configure(self.configure_args())
        checkout = self.root / "checkout"
        (checkout / ".codex-plugin").mkdir(parents=True)
        (checkout / "skills/verify-before-push").mkdir(parents=True)
        (checkout / ".codex-plugin/plugin.json").write_text(
            json.dumps(
                {
                    "name": "kolabse-skills",
                    "repository": "https://github.com/kolabse/skills",
                }
            ),
            encoding="utf-8",
        )
        (checkout / "skill-catalog.json").write_text(
            json.dumps({"skills": [{"name": "verify-before-push"}]}),
            encoding="utf-8",
        )
        (checkout / "skills/verify-before-push/SKILL.md").write_text(
            "fixture", encoding="utf-8"
        )
        skill = self.install("verify-before-push")
        lock_path = self.root / "skills-lock.json"
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        lock["skills"]["verify-before-push"].update(
            {"source": str(checkout), "sourceType": "local"}
        )
        lock_path.write_text(json.dumps(lock), encoding="utf-8")

        observed = team_skills.observe_skill(
            self.root,
            skill,
            "verify-before-push",
            "1.18.0",
            lock["skills"]["verify-before-push"],
        )

        self.assertEqual("verified", observed["provenance"])

    def test_plan_is_digest_bound_and_targets_only_declared_names(self) -> None:
        configured = team_skills.configure(self.configure_args())
        self.install("synchronize-git-repositories")
        self.install("synchronize-team-skills")
        plan = team_skills.make_plan(self.root, str(self.docs))

        self.assertEqual(configured["manifest_sha256"], plan["manifest_sha256"])
        self.assertEqual([], plan["blockers"])
        self.assertEqual(["verify-before-push"], plan["installers"][0]["selected"])
        argv = plan["installers"][0]["argv"]
        self.assertIn("kolabse/skills@v1.18.0", argv)
        self.assertEqual(3, argv.count("--skill"))
        self.assertNotIn("notify-via-telegram", argv)

    def test_plan_blocks_unverified_collision_and_newer_version(self) -> None:
        team_skills.configure(self.configure_args())
        self.install("synchronize-git-repositories")
        (self.root / ".agents/skills/synchronize-team-skills").mkdir(parents=True)
        self.install("verify-before-push", "2.0.0")

        plan = team_skills.make_plan(self.root, str(self.docs))

        self.assertEqual([], plan["installers"])
        self.assertIn("codex:synchronize-team-skills:unverified", plan["blockers"])
        self.assertIn("codex:verify-before-push:newer-than-required", plan["blockers"])

    def test_prerelease_version_orders_before_same_core_release(self) -> None:
        self.assertEqual("outdated", team_skills.version_state("1.18.0-rc.1", "1.18.0"))
        self.assertEqual(
            "newer-than-required",
            team_skills.version_state("1.18.0", "1.18.0-rc.1"),
        )
        self.assertEqual(
            "outdated",
            team_skills.version_state("1.18.0-rc.2", "1.18.0-rc.10"),
        )
        self.assertEqual(
            "version-mismatch",
            team_skills.version_state("1.18.0+build.1", "1.18.0"),
        )

    def test_malformed_lock_file_fails_closed(self) -> None:
        team_skills.configure(self.configure_args())
        (self.root / "skills-lock.json").write_text("{broken", encoding="utf-8")

        with self.assertRaisesRegex(team_skills.TeamSkillsError, "invalid"):
            team_skills.inspect(self.root, str(self.docs))

    def test_status_rejects_content_drift_with_unchanged_metadata(self) -> None:
        team_skills.configure(self.configure_args())
        for name in (
            "synchronize-git-repositories",
            "synchronize-team-skills",
            "verify-before-push",
        ):
            self.install(name)
        drifted = self.root / ".agents/skills/verify-before-push/SKILL.md"
        drifted.write_text("changed after installation", encoding="utf-8")

        plan = team_skills.make_plan(self.root, str(self.docs))

        self.assertIn("codex:verify-before-push:unverified", plan["blockers"])
        self.assertEqual([], plan["installers"])

    def test_status_ignores_python_runtime_cache_files(self) -> None:
        team_skills.configure(self.configure_args())
        for name in (
            "synchronize-git-repositories",
            "synchronize-team-skills",
            "verify-before-push",
        ):
            self.install(name)
        cache = self.root / ".agents/skills/synchronize-team-skills/scripts/__pycache__"
        cache.mkdir(parents=True)
        (cache / "team_skills.cpython-313.pyc").write_bytes(b"runtime cache")

        status = team_skills.inspect(self.root, str(self.docs))

        states = {item["name"]: item["state"] for item in status["agents"][0]["skills"]}
        self.assertEqual("current", states["synchronize-team-skills"])

    def test_unsafe_layout_does_not_scan_extras(self) -> None:
        team_skills.configure(self.configure_args())
        layout = self.root / ".agents/skills"
        (layout / "notify-via-telegram").mkdir(parents=True)

        with mock.patch.object(Path, "is_symlink", return_value=True), mock.patch.object(
            team_skills, "verified_extra"
        ) as extra:
            status = team_skills.inspect(self.root, str(self.docs))

        extra.assert_not_called()
        self.assertFalse(status["agents"][0]["layout_safe"])
        self.assertEqual([], status["agents"][0]["extras"])

    def test_symlinked_extra_is_reported_and_blocks_plan(self) -> None:
        team_skills.configure(self.configure_args())
        layout = self.root / ".agents/skills"
        extra_path = layout / "notify-via-telegram"
        extra_path.mkdir(parents=True)

        original = Path.is_symlink

        def fake_is_symlink(path: Path) -> bool:
            if path == extra_path:
                return True
            return original(path)

        with mock.patch.object(Path, "is_symlink", fake_is_symlink):
            plan = team_skills.make_plan(self.root, str(self.docs))

        unsafe = plan["status"]["agents"][0]["unsafe_extras"]
        self.assertEqual(["notify-via-telegram"], [item["name"] for item in unsafe])
        self.assertIn(
            "codex:extra:notify-via-telegram:unsafe-symlink",
            plan["blockers"],
        )

    def test_apply_rejects_missing_confirmation_and_stale_manifest(self) -> None:
        configured = team_skills.configure(self.configure_args())
        with self.assertRaisesRegex(team_skills.TeamSkillsError, "requires --yes"):
            team_skills.apply(self.apply_args(configured["manifest_sha256"], yes=False))
        with self.assertRaisesRegex(team_skills.TeamSkillsError, "changed after planning"):
            team_skills.apply(self.apply_args("0" * 64))

    def test_apply_rejects_installation_drift_after_review(self) -> None:
        configured = team_skills.configure(self.configure_args())
        reviewed = team_skills.make_plan(self.root, str(self.docs))
        self.install("synchronize-team-skills")

        with self.assertRaisesRegex(team_skills.TeamSkillsError, "plan changed after review"):
            team_skills.apply(
                self.apply_args(
                    configured["manifest_sha256"],
                    expected_plan_sha256=reviewed["plan_sha256"],
                )
            )

    def test_apply_installs_then_verifies_and_preserves_extras(self) -> None:
        configured = team_skills.configure(self.configure_args())
        self.install("notify-via-telegram")

        def fake_run(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            for name in (
                "synchronize-git-repositories",
                "synchronize-team-skills",
                "verify-before-push",
            ):
                self.install(name)
            return subprocess.CompletedProcess(argv, 0, "", "")

        with mock.patch.object(team_skills.shutil, "which", return_value="npx"), mock.patch.object(
            team_skills.subprocess, "run", side_effect=fake_run
        ) as run:
            result = team_skills.apply(self.apply_args(configured["manifest_sha256"]))

        self.assertTrue(result["ready"])
        self.assertTrue(result["new_task_required"])
        self.assertEqual(1, run.call_count)
        self.assertTrue((self.root / ".agents/skills/notify-via-telegram").is_dir())

    def test_ambiguous_documentation_fails_closed(self) -> None:
        (self.root / "documentation").mkdir()
        with self.assertRaisesRegex(team_skills.TeamSkillsError, "ambiguous"):
            team_skills.inspect(self.root, None)


if __name__ == "__main__":
    unittest.main()
