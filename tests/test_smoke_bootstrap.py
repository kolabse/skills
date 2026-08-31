from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import smoke_bootstrap  # noqa: E402


class SmokeBootstrapTests(unittest.TestCase):
    def test_default_tag_uses_selected_source_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            (source / "skill-catalog.json").write_text(
                json.dumps({"collection_version": "9.8.7"}), encoding="utf-8"
            )
            with patch.object(smoke_bootstrap, "run_smoke") as run:
                self.assertEqual(0, smoke_bootstrap.main(["--source", str(source)]))
            run.assert_called_once_with(source.resolve(), "v9.8.7", 120, "codex")

    def test_explicit_tag_preserves_override(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            with patch.object(smoke_bootstrap, "run_smoke") as run:
                self.assertEqual(0, smoke_bootstrap.main([
                    "--source", str(source), "--tag", "v2.3.4",
                    "--agent", "claude-code",
                ]))
            run.assert_called_once_with(source.resolve(), "v2.3.4", 120, "claude-code")

    def test_missing_default_version_fails_before_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            (source / "skill-catalog.json").write_text("{}", encoding="utf-8")
            with patch.object(smoke_bootstrap, "run_smoke") as run:
                self.assertEqual(1, smoke_bootstrap.main(["--source", str(source)]))
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
