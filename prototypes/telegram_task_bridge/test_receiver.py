import io
import http.client
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch
import urllib.error

from receiver import Health, read_with_retry, run_receiver
from store import Store
from telegram import Telegram, TelegramError


class ReceiverTests(unittest.TestCase):
    def test_scheduler_entry_exits_paused_before_reading_missing_config(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'receiver-paused').touch()
            database = root / 'absent.db'
            result = subprocess.run([sys.executable, str(Path(__file__).with_name('server.py')),
                                     'receive', '--db', str(database), '--config', str(root / 'missing.json')],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(database.exists())
            self.assertEqual(json.loads((root / 'absent.db.receiver-health.json').read_text())['state'], 'paused')

    def test_paused_receiver_never_contacts_telegram(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'receiver-paused').touch()
            adapter = Mock()
            with patch('telegram.state_dir', return_value=root):
                run_receiver(adapter, Mock(), root / 'test.db', root / 'health.json')
            adapter.preflight.assert_not_called()
            adapter.call.assert_not_called()
            self.assertEqual(json.loads((root / 'health.json').read_text())['state'], 'paused')

    def test_transient_backoff_and_telegram_retry_after(self):
        action = Mock(side_effect=[TelegramError("transport", retryable=True),
                                   TelegramError("rate limit", retryable=True, retry_after=65), "ok"])
        health, sleep = Mock(), Mock()
        self.assertEqual(read_with_retry(action, health, sleep), "ok")
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [2, 30, 30, 5])
        self.assertEqual(action.call_count, 3)

    def test_permanent_failure_never_retried(self):
        action = Mock(side_effect=TelegramError("Telegram getUpdates: HTTP 409"))
        sleep = Mock()
        with self.assertRaises(TelegramError):
            read_with_retry(action, Mock(), sleep)
        sleep.assert_not_called()
        self.assertEqual(action.call_count, 1)

    def test_http_classification_without_token_in_errors(self):
        adapter = Telegram.__new__(Telegram)
        adapter.token = "123:secret"
        for code, retryable in [(401, False), (409, False), (429, True), (503, True)]:
            error = urllib.error.HTTPError("https://secret", code, "private", {},
                                         io.BytesIO(b'{"parameters":{"retry_after":45}}'))
            with patch("telegram.urllib.request.urlopen", side_effect=error):
                with self.assertRaises(TelegramError) as caught:
                    adapter.call("getUpdates")
            self.assertEqual(caught.exception.retryable, retryable)
            self.assertNotIn("secret", str(caught.exception))
            if code == 429:
                self.assertEqual(caught.exception.retry_after, 45)

    def test_truncated_response_is_retryable(self):
        adapter = Telegram.__new__(Telegram)
        adapter.token = "123:secret"
        with patch("telegram.urllib.request.urlopen", side_effect=http.client.IncompleteRead(b"private", 5)):
            with self.assertRaises(TelegramError) as caught:
                adapter.call("getUpdates")
        self.assertTrue(caught.exception.retryable)
        self.assertNotIn("private", str(caught.exception))

    def test_receiver_recovers_and_reports_shutdown(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            store = Store(root / "test.db")
            health = root / "health.json"
            adapter = Mock(chat_id=123)
            adapter.preflight.return_value = 456
            adapter.call.side_effect = [TelegramError("transport", retryable=True), [], KeyboardInterrupt()]
            try:
                with patch("telegram.state_dir", return_value=root), patch("receiver.time.sleep"):
                    run_receiver(adapter, store, root / "test.db", health, sleep=Mock())
                data = json.loads(health.read_text())
                self.assertEqual(data["state"], "stopped")
                self.assertIsNotNone(data["last_poll_at"])
                self.assertEqual(data["consecutive_failures"], 0)
            finally:
                store.close()

    def test_conflict_is_recorded_and_not_retried(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            store = Store(root / "test.db")
            adapter = Mock(chat_id=123)
            adapter.preflight.return_value = 456
            adapter.call.side_effect = TelegramError("Telegram getUpdates: HTTP 409")
            try:
                with patch("telegram.state_dir", return_value=root):
                    with self.assertRaises(TelegramError):
                        run_receiver(adapter, store, root / "test.db", root / "health.json", sleep=Mock())
                self.assertEqual(adapter.call.call_count, 1)
                self.assertEqual(json.loads((root / "health.json").read_text())["state"], "failed")
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
