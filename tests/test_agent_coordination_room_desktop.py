"""Desktop room dispatch and replay contract."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "prototypes/agent_coordination_rooms/coordinate-agent-rooms/scripts"))
import desktop_room


class DesktopRoomTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "binding.sqlite"
        self.binding = {"url": "https://room.example", "actor": "bob", "peer": "alice",
                        "thread": "00000000-0000-4000-8000-000000000001"}
        desktop_room.bind(self.path, self.binding)
        self.question = {"id": 12, "actor": "alice", "recipient": "bob", "projects": [],
                         "body": "What is 7 plus 5? Reply with the number only.",
                         "thread_id": 12, "reply_to": None}
        self.queue = Mock(return_value="queued-id")
        self.observe = Mock(return_value={"id": "turn-id", "answer": "12"})
        self.publish = Mock(return_value={"id": 13, "actor": "bob", "recipient": "alice",
                                         "thread_id": 12, "reply_to": 12, "body": "12"})

    def run_question(self, **kwargs):
        return desktop_room.deliver(self.path, self.binding, self.question,
                                    self.queue, self.observe, self.publish, **kwargs)

    def test_restart_and_duplicate_keep_one_queue_and_one_reply(self):
        self.assertEqual(self.run_question(queue_only=True)["status"], "queued")
        self.observe.assert_not_called()
        self.assertEqual(self.run_question()["status"], "answered")
        self.assertEqual(self.run_question()["status"], "already_answered")
        self.queue.assert_called_once()
        self.observe.assert_called_once()
        self.publish.assert_called_once_with("desktop-reply-12", "12", "alice", 12)

    def test_uncertain_queue_result_is_observed_and_not_submitted_again(self):
        self.queue.side_effect = TimeoutError("queue outcome unknown")
        with self.assertRaises(TimeoutError):
            self.run_question(queue_only=True)
        self.assertEqual(self.run_question()["status"], "answered")
        self.queue.assert_called_once()

    def test_room_failure_uses_durable_answer_on_retry(self):
        reply = self.publish.return_value
        self.publish.side_effect = [OSError("temporarily offline"), reply]
        with self.assertRaises(OSError):
            self.run_question()
        self.assertEqual(self.run_question()["reply_id"], 13)
        self.queue.assert_called_once()
        self.observe.assert_called_once()
        self.assertEqual(self.publish.call_args_list[0], self.publish.call_args_list[1])

    def test_interrupted_snapshot_does_not_count_as_a_completed_turn(self):
        message = {"type": "userMessage", "content": [{"type": "text", "text": "marker"}]}
        answer = {"type": "agentMessage", "phase": "final_answer", "text": "12"}
        snapshot = {"id": "turn-id", "status": "interrupted", "items": [message, answer]}
        self.assertIsNone(desktop_room.completed_reply([snapshot], "marker", "12"))
        snapshot["status"] = "completed"
        self.assertEqual(desktop_room.completed_reply([snapshot], "marker", "12")["id"], "turn-id")

    def test_wrong_peer_or_project_content_is_not_queued(self):
        for changes in ({"actor": "other"}, {"projects": ["pilot"]}, {"body": "Read a local file"}):
            with self.subTest(changes=changes):
                original = self.question
                self.question = dict(original, **changes)
                with self.assertRaises(desktop_room.AdapterError):
                    self.run_question()
                self.question = original
        self.queue.assert_not_called()


if __name__ == "__main__":
    unittest.main()
