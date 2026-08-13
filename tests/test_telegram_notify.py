from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
