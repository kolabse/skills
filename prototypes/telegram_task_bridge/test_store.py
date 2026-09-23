import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from prototypes.telegram_task_bridge.store import Store


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "state.db"
        self.store = Store(self.path)
        self.a = self.store.register("task A")
        self.b = self.store.register("task B")

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def question(self, credentials=None, message_id=10):
        result = self.store.create_question(**(credentials or self.a), text="Which option?")
        self.store.mark_sent(result["question_id"], message_id)
        return result["question_id"]

    def test_restart_duplicate_offset_and_ack(self):
        question_id = self.question()
        self.assertEqual(self.store.receive(5, 10, "Option A")["status"], "answered")
        self.store.advance_offset(5)
        self.store.close()
        self.store = Store(self.path)
        self.assertEqual(self.store.receive(5, 10, "changed"), {"status": "duplicate"})
        self.assertEqual(self.store.receive(6, 10, "changed")["status"], "already_answered")
        self.assertEqual(self.store.poll(**self.a)[0]["answer"], "Option A")
        self.store.advance_offset(2)
        self.assertEqual(self.store.offset(), 6)
        self.store.ack(**self.a, question_id=question_id)
        self.store.ack(**self.a, question_id=question_id)
        self.assertEqual(self.store.poll(**self.a), [])

    def test_two_tasks_and_credentials(self):
        qa = self.question()
        qb = self.question(self.b, 20)
        self.store.receive(1, 20, "B answer")
        self.assertEqual(self.store.poll(**self.a), [])
        self.assertEqual(self.store.poll(**self.b)[0]["question_id"], qb)
        for method in (self.store.authenticate, self.store.poll):
            with self.assertRaises(PermissionError):
                method(self.a["task_id"], self.b["secret"])
        with self.assertRaises(ValueError):
            self.store.ack(**self.a, question_id=qb)
        with self.assertRaises(ValueError):
            self.store.get_question(**self.b, question_id=qa)
        self.assertEqual(self.store.poll(**self.b)[0]["answer"], "B answer")
        with closing(sqlite3.connect(self.path)) as db:
            self.assertNotIn(self.a["secret"], str(db.execute("SELECT * FROM tasks").fetchall()))

    def test_expiry_unknown_and_invalid_text(self):
        with patch("prototypes.telegram_task_bridge.store.time.time", return_value=100):
            q = self.store.create_question(**self.a, text="Expiring", ttl_seconds=1)
            self.store.mark_sent(q["question_id"], 30)
        with patch("prototypes.telegram_task_bridge.store.time.time", return_value=101):
            self.assertEqual(self.store.receive(1, 30, "late")["status"], "expired")
            self.assertEqual(self.store.get_question(**self.a, question_id=q["question_id"])["status"], "expired")
        self.assertEqual(self.store.receive(2, 999, "unknown")["status"], "unknown")
        self.question()
        self.assertEqual(self.store.receive(3, 10, " " )["status"], "invalid_text")
        self.assertEqual(self.store.receive(4, 10, "x" * 3501)["status"], "invalid_text")
        self.assertEqual(self.store.receive(5, 10, "valid")["status"], "answered")

    def test_pending_unknown_send_and_validation(self):
        q = self.store.create_question(**self.a, text="Question")
        with self.assertRaises(ValueError):
            self.store.ack(**self.a, question_id=q["question_id"])
        self.store.mark_failed(q["question_id"])
        self.assertEqual(self.store.get_question(**self.a, question_id=q["question_id"])["status"], "unknown")
        with self.assertRaises(ValueError):
            self.store.mark_sent(q["question_id"], 50)
        for ttl in (0, -1, 86401, True, float("nan")):
            with self.assertRaises(ValueError):
                self.store.create_question(**self.a, text="question", ttl_seconds=ttl)
        with self.assertRaises(ValueError):
            self.store.create_question(**self.a, text="x" * 3501)

    def test_unique_sent_anchor_and_atomic_replay_across_connections(self):
        first = self.question()
        second = self.store.create_question(**self.b, text="Next instruction")
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.mark_sent(second["question_id"], 10)
        self.assertEqual(self.store.get_question(**self.b, question_id=second["question_id"])["status"], "pending")
        other = Store(self.path)
        try:
            self.store.receive(42, 10, "durable answer")
            self.assertEqual(other.receive(42, 10, "different"), {"status": "duplicate"})
            self.assertEqual(other.poll(**self.a)[0]["answer"], "durable answer")
            with self.assertRaises(ValueError):
                other.mark_sent(first, 20)
            other.advance_offset(42)
            self.assertEqual(self.store.offset(), 43)
        finally:
            other.close()

    def test_answer_received_before_expiry_remains_deliverable(self):
        with patch("prototypes.telegram_task_bridge.store.time.time", return_value=100):
            q = self.store.create_question(**self.a, text="Question", ttl_seconds=1)
            self.store.mark_sent(q["question_id"], 10)
            self.store.receive(1, 10, "in time")
        with patch("prototypes.telegram_task_bridge.store.time.time", return_value=200):
            self.assertEqual(self.store.poll(**self.a)[0]["answer"], "in time")


if __name__ == "__main__":
    unittest.main()
