from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "notify-via-telegram"
    / "scripts"
    / "telegram_notify.py"
)
SPEC = importlib.util.spec_from_file_location("telegram_notify", SCRIPT)
assert SPEC and SPEC.loader
telegram_notify = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(telegram_notify)


class TelegramNotifyTests(unittest.TestCase):
    def test_project_profile_is_outside_project_and_contains_no_token(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            global_config = root / "user-config" / "config.json"
            profile_path = telegram_notify.project_config_path(global_config, project)
            telegram_notify.save_config(
                profile_path,
                {
                    "version": 1,
                    "delivery_mode": "project-only",
                    "chat_id": "-1001",
                },
            )
            profile = telegram_notify.load_project_config(profile_path)
            self.assertEqual("project-only", profile["delivery_mode"])
            self.assertEqual("-1001", profile["chat_id"])
            self.assertNotIn("bot_token", profile)
            self.assertNotEqual(project, profile_path.parent)
            self.assertNotIn(project, profile_path.parents)

    def test_project_export_matches_environment_setting_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            global_config = root / "user-config" / "config.json"
            profile_path = telegram_notify.project_config_path(global_config, project)
            telegram_notify.save_config(
                profile_path,
                {
                    "version": 1,
                    "delivery_mode": "global-and-project",
                    "chat_id": "-1002",
                    "message_thread_id": "7",
                },
            )
            output = io.StringIO()
            with redirect_stdout(output):
                telegram_notify.command_project_export(
                    type("Args", (), {"project_path": str(project), "local_state": False})(),
                    global_config,
                )
            exported = json.loads(output.getvalue())
            setting = exported["settings"][0]
            self.assertEqual("notify-via-telegram", setting["id"])
            self.assertEqual("global-and-project", setting["preferences"]["delivery_mode"])
            self.assertEqual("-1002", setting["preferences"]["chat_id"])
            self.assertNotIn("token", json.dumps(exported).lower())

    def test_project_config_schema_declares_both_delivery_modes(self) -> None:
        schema_path = SCRIPT.parent.parent / "schemas" / "project-config.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertEqual(
            ["global-and-project", "project-only"],
            schema["properties"]["delivery_mode"]["enum"],
        )

    def test_bot_token_normalization_accepts_telegram_shape(self) -> None:
        self.assertEqual(
            "123456789:abc_DEF-",
            telegram_notify.normalize_bot_token(" 123456789:abc_DEF- \n"),
        )

    def test_bot_token_normalization_rejects_invalid_values(self) -> None:
        for value in ("", " ", "123", "bot:token", "123:abc def", "123:abcà"):
            with self.subTest(value=value), self.assertRaises(
                telegram_notify.TelegramError
            ):
                telegram_notify.normalize_bot_token(value)

    def test_invalid_bot_token_is_rejected_before_network_access(self) -> None:
        with patch.object(telegram_notify.urllib.request, "urlopen") as urlopen:
            with self.assertRaises(telegram_notify.TelegramError):
                telegram_notify.api_call("123:abcà", "getMe")
        urlopen.assert_not_called()

    def test_config_schema_uses_the_same_bot_token_contract(self) -> None:
        schema_path = SCRIPT.parent.parent / "schemas" / "config.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertEqual(
            "^[0-9]+:[A-Za-z0-9_-]+$",
            schema["properties"]["bot_token"]["pattern"],
        )

    def test_interactive_token_entry_retries_after_local_rejection(self) -> None:
        stderr = io.StringIO()
        with patch.object(
            telegram_notify.getpass,
            "getpass",
            side_effect=[" ", "123456:valid_token"],
        ) as prompt, redirect_stderr(stderr):
            token = telegram_notify.prompt_bot_token()
        self.assertEqual("123456:valid_token", token)
        self.assertEqual(2, prompt.call_count)
        self.assertIn("ERROR: Telegram bot token is empty", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_invalid_environment_token_exits_without_traceback_or_secret(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            stderr = io.StringIO()
            token = "123:abcà"
            with patch.dict(
                os.environ,
                {telegram_notify.TOKEN_ENV: token},
                clear=False,
            ), redirect_stderr(stderr):
                result = telegram_notify.main(
                    [
                        "--config",
                        str(path),
                        "configure",
                        "--chat-id",
                        "123",
                        "--skip-test",
                    ]
                )
            output = stderr.getvalue()
            self.assertEqual(1, result)
            self.assertIn("ERROR: Telegram bot token has an invalid format", output)
            self.assertNotIn("Traceback", output)
            self.assertNotIn(token, output)

    def test_chunk_text_preserves_content_and_limit(self) -> None:
        text = "alpha beta gamma delta"
        chunks = telegram_notify.chunk_text(text, limit=10)
        self.assertTrue(all(0 < len(chunk) <= 10 for chunk in chunks))
        self.assertEqual(" ".join(chunks), text)

    def test_extract_chat_candidates_deduplicates_latest_chat(self) -> None:
        updates = [
            {
                "message": {
                    "chat": {"id": -1001, "type": "supergroup", "title": "Ops"},
                    "message_thread_id": 7,
                }
            },
            {
                "edited_message": {
                    "chat": {"id": -1001, "type": "supergroup", "title": "Ops"},
                    "message_thread_id": 7,
                }
            },
        ]
        candidates = telegram_notify.extract_chat_candidates(updates)
        self.assertEqual(
            candidates,
            [
                {
                    "chat_id": "-1001",
                    "thread_id": "7",
                    "type": "supergroup",
                    "label": "Ops",
                }
            ],
        )

    def test_save_and_load_config_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "config.json"
            telegram_notify.save_config(
                path, {"bot_token": "secret", "chat_id": "123"}
            )
            self.assertEqual(
                telegram_notify.load_config(path),
                {"bot_token": "secret", "chat_id": "123"},
            )

    def test_environment_credentials_override_file(self) -> None:
        resolved = telegram_notify.resolve_credentials(
            {"bot_token": "file-token", "chat_id": "1"},
            {
                "TELEGRAM_BOT_TOKEN": "env-token",
                "TELEGRAM_CHAT_ID": "2",
                "TELEGRAM_MESSAGE_THREAD_ID": "3",
            },
        )
        self.assertEqual(resolved, ("env-token", "2", "3"))

    def test_migrate_legacy_config_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(
                '{"bot_token":"123456:secret","chat_id":"123"}\n',
                encoding="utf-8",
            )
            telegram_notify.command_migrate(path, True)
            first = path.read_bytes()
            self.assertEqual(1, json.loads(first)["version"])
            telegram_notify.command_migrate(path, True)
            self.assertEqual(first, path.read_bytes())

    @unittest.skipUnless(
        os.name == "nt" and shutil.which("powershell"),
        "Windows PowerShell is required",
    )
    def test_windows_token_entry_self_test(self) -> None:
        script = SCRIPT.with_name("configure_windows.ps1")
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
                "-SelfTest",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
