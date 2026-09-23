import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from prototypes.telegram_task_bridge.store import Store
from prototypes.telegram_task_bridge.telegram import Telegram, TelegramError, bind_database, bind_bot_database, receiver_lock


class TelegramTests(unittest.TestCase):
    def test_sender_chat_and_reply_filter_and_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            store = Store(path)
            task = store.register("test")
            q = store.create_question(**task, text="question")
            store.mark_sent(q["question_id"], 456)
            adapter = Telegram.__new__(Telegram)
            adapter.chat_id = 123
            update = {"update_id": 1, "message": {"chat": {"id": 123, "type": "private"},
                "from": {"id": 123}, "reply_to_message": {"message_id": 456}, "text": "answer"}}
            variants = [({"from": {"id": 999}},), ({"chat": {"id": 999, "type": "private"}},),
                        ({"forward_origin": {"type": "user"}},), ({"reply_to_message": {}},)]
            for index, (changes,) in enumerate(variants, 1):
                bad = copy.deepcopy(update)
                bad["update_id"] = index
                bad["message"].update(changes)
                self.assertEqual(adapter.receive(store, bad)["status"], "ignored")
            self.assertEqual(store.poll(**task), [])
            update["update_id"] = 5
            self.assertEqual(adapter.receive(store, update)["status"], "answered")
            store.close()
            store = Store(path)
            self.assertEqual(adapter.receive(store, update)["status"], "duplicate")
            self.assertEqual(store.offset(), 6)
            self.assertEqual(store.poll(**task)[0]["answer"], "answer")
            store.close()

    def test_webhook_refused_without_deletion(self):
        adapter = Telegram.__new__(Telegram)
        with patch.object(adapter, "call", return_value={"url": "https://example.org/hook"}) as call:
            with self.assertRaises(TelegramError):
                adapter.preflight()
            call.assert_called_once_with("getWebhookInfo")

    def test_database_and_receiver_are_exclusive(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            bind_database(path, "one")
            bind_database(path, "one")
            with self.assertRaises(TelegramError):
                bind_database(path, "two")
            with patch("prototypes.telegram_task_bridge.telegram.state_dir", return_value=Path(tmp)):
                bind_bot_database(123, path)
                bind_bot_database(123, path)
                with self.assertRaises(TelegramError):
                    bind_bot_database(123, Path(tmp) / "other.db")
                with receiver_lock("test"):
                    with self.assertRaises(TelegramError):
                        with receiver_lock("test"):
                            pass


if __name__ == "__main__":
    unittest.main()
