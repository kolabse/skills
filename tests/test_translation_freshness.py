from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import validate_localizations as validator
import translation_freshness as freshness


def digest(text):
    return hashlib.sha256(text.replace("\r\n", "\n").encode()).hexdigest()


class TranslationFreshnessTests(unittest.TestCase):
    def test_validator_accepts_relative_project_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            self.fixture(root)
            previous = Path.cwd()
            try:
                os.chdir(root)
                self.assertEqual(1, validator.validate(Path(".")))
            finally:
                os.chdir(previous)

    def test_validator_accepts_symlinked_project_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            project = root / "project"
            project.mkdir()
            self.fixture(project)
            alias = root / "alias"
            try:
                alias.symlink_to(project, target_is_directory=True)
            except OSError:
                if os.name != "nt":
                    raise
                self.skipTest("Windows directory symlink privilege unavailable")
            self.assertEqual(1, validator.validate(alias))

    def test_duplicate_headings_do_not_collide_with_explicit_suffix(self):
        parts = freshness.sections("# Foo\nA\n# Foo\nB\n# Foo-1\nC\n")
        self.assertEqual(3, len({part["id"] for part in parts}))

    def test_duplicate_json_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            path = root / freshness.STATE_PATH
            text = path.read_text(encoding="utf-8").replace('"schema_version": 1', '"schema_version": 2, "schema_version": 1')
            path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(freshness.FreshnessError, "duplicate"):
                freshness.status(root)

    def fixture(self, root):
        (root / "docs/i18n/tr").mkdir(parents=True)
        source = "# Project\n\nEnglish | Türkçe\n\n## Safety\n\nAsk before publishing.\n"
        target = "# Proje\n\nEnglish | Türkçe\n\n## Güvenlik\n\nYayımlamadan önce sorun.\n"
        (root / "README.md").write_text(source, encoding="utf-8")
        (root / "docs/i18n/tr/README.md").write_text(target, encoding="utf-8")
        manifest = {"schema_version": 1, "canonical_locale": "en", "locales": {
            "tr": {"name": "Türkçe", "documents": [{"canonical": "README.md", "translation": "docs/i18n/tr/README.md"}]}}}
        (root / "docs/i18n/locales.json").write_text(json.dumps(manifest), encoding="utf-8")
        state = {"schema_version": 1, "snapshots": {"README.md": {digest(source): {
            "sections": [{"id": "project", "heading": "Project", "sha256": digest("# Project\n\nEnglish | Türkçe\n\n")},
                         {"id": "safety", "heading": "Safety", "sha256": digest("## Safety\n\nAsk before publishing.\n")}]}}},
            "translations": [{"locale": "tr", "canonical": "README.md", "translation": "docs/i18n/tr/README.md",
                              "source_sha256": digest(source), "translation_sha256": digest(target), "review": "baseline"}]}
        (root / "docs/i18n/translation-status.json").write_text(json.dumps(state), encoding="utf-8")
        return source, target

    def test_changed_english_prose_requires_translation_attention(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, _ = self.fixture(root)
            (root / "README.md").write_text(source.replace("Ask before publishing.", "Never publish without approval."), encoding="utf-8")
            with self.assertRaisesRegex(validator.LocalizationError, "translation freshness"):
                validator.validate(root)

    def test_changed_translation_requires_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, target = self.fixture(root)
            (root / "docs/i18n/tr/README.md").write_text(target + "\nChanged advice.\n", encoding="utf-8")
            with self.assertRaisesRegex(validator.LocalizationError, "translation freshness"):
                validator.validate(root)

    def test_status_identifies_changed_sections_and_is_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, _ = self.fixture(root)
            path = root / freshness.STATE_PATH
            before = path.read_bytes()
            (root / "README.md").write_text(source.replace("Ask before publishing.", "Ask twice before publishing."), encoding="utf-8")
            result = freshness.status(root)
            row = result["documents"][0]
            self.assertEqual(["source-changed"], row["reasons"])
            self.assertEqual([{"id": "safety", "heading": "Safety", "change": "modified"}], row["changed_sections"])
            self.assertFalse(result["semantic_quality_verified"])
            self.assertEqual(before, path.read_bytes())

    def test_record_requires_exact_reviewed_inputs_and_does_not_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = self.fixture(root)
            changed = source.replace("Ask before publishing.", "Check before publishing.")
            (root / "README.md").write_text(changed, encoding="utf-8")
            before = (root / freshness.STATE_PATH).read_bytes()
            with self.assertRaisesRegex(freshness.FreshnessError, "changed"):
                freshness.record(root, "tr", "README.md", digest(source), digest(target))
            proposed = freshness.record(root, "tr", "README.md", digest(changed), digest(target))
            self.assertEqual("reviewed", proposed["translations"][0]["review"])
            self.assertEqual(2, len(proposed["snapshots"]["README.md"]))
            self.assertEqual(before, (root / freshness.STATE_PATH).read_bytes())
            (root / freshness.STATE_PATH).write_text(json.dumps(proposed), encoding="utf-8")
            self.assertTrue(freshness.status(root)["aligned"])

    def test_missing_record_is_unknown_and_snapshot_cannot_bless_existing_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            with self.assertRaisesRegex(freshness.FreshnessError, "already exists"):
                freshness.snapshot(root)
            path = root / freshness.STATE_PATH
            path.unlink()
            self.assertEqual(["untracked"], freshness.status(root)["documents"][0]["reasons"])
            proposal = freshness.snapshot(root)
            self.assertFalse(path.exists())
            self.assertEqual("baseline", proposal["translations"][0]["review"])

    def test_line_endings_do_not_invalidate_alignment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = self.fixture(root)
            (root / "README.md").write_bytes(source.replace("\n", "\r\n").encode())
            (root / "docs/i18n/tr/README.md").write_bytes(target.replace("\n", "\r\n").encode())
            self.assertTrue(freshness.status(root)["aligned"])
            self.assertEqual("baseline", freshness.status(root)["documents"][0]["review"])

    def test_duplicate_and_contradictory_records_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            path = root / freshness.STATE_PATH
            original = json.loads(path.read_text(encoding="utf-8"))
            corrupt = json.loads(json.dumps(original))
            corrupt["translations"].append(corrupt["translations"][0])
            path.write_text(json.dumps(corrupt), encoding="utf-8")
            with self.assertRaisesRegex(freshness.FreshnessError, "duplicate"):
                freshness.status(root)
            corrupt = json.loads(json.dumps(original))
            revision = next(iter(corrupt["snapshots"]["README.md"].values()))
            revision["sections"][0]["sha256"] = "0" * 64
            path.write_text(json.dumps(corrupt), encoding="utf-8")
            with self.assertRaisesRegex(freshness.FreshnessError, "contradict"):
                freshness.status(root)

    def test_added_and_removed_sections_are_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, _ = self.fixture(root)
            (root / "README.md").write_text(source.replace("## Safety", "## Publication"), encoding="utf-8")
            changes = freshness.status(root)["documents"][0]["changed_sections"]
            self.assertEqual({("publication", "added"), ("safety", "removed")}, {(item["id"], item["change"]) for item in changes})


if __name__ == "__main__":
    unittest.main()
