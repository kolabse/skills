"""Room worker contracts without a model call."""
from argparse import Namespace
import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "prototypes/agent_coordination_rooms/coordinate-agent-rooms/scripts"))
import room_worker


class WorkerTests(unittest.TestCase):
    def test_selects_question_and_retries_the_same_persisted_reply(self):
        calls = []
        answers = []
        question = {"id": 9, "actor": "alice", "recipient": "bob", "body": "How did it go?",
                    "thread_id": 9, "reply_to": None, "projects": []}
        skipped = [
            dict(question, id=6, actor="someone-else"),
            dict(question, id=7, reply_to=3),
            dict(question, id=8, recipient="cara"),
        ]
        def room(*args):
            calls.append(args)
            if args[0] == "history":
                return skipped + [question]
            if len(calls) == 2:
                raise room_worker.WorkerError("temporary delivery failure")
            return {"id": 10, "actor": "bob", "recipient": "alice", "thread_id": 9, "reply_to": 9}

        def answer(text):
            answers.append(text)
            return "It passed.", {"fragments": 3}

        with tempfile.TemporaryDirectory() as state:
            settings = dict(after=5, actor="bob", peer="alice", wait=1,
                            origin="https://room.example", state=Path(state))
            with self.assertRaisesRegex(room_worker.WorkerError, "temporary delivery failure"):
                room_worker.run_one(room, answer, **settings)
            result = room_worker.run_one(room, answer, **settings)
        self.assertEqual(answers, ["How did it go?"])
        self.assertEqual(calls[1], calls[3])
        self.assertEqual(calls[3], ("post", "codex-reply-9", "It passed.", "--to", "alice", "--reply-to", "9"))
        self.assertEqual(result["reply_id"], 10)
        self.assertEqual(result["question_id"], 9)

    def test_room_request_does_not_spawn_another_python(self):
        args = Namespace(url="https://room.example", ca=None, token_file=Path("token.json"))
        with patch.object(room_worker.subprocess, "run", side_effect=PermissionError("child denied")):
            with patch("urllib.request.OpenerDirector.open") as opened, patch.object(Path, "read_text", return_value='{"token":"fixture"}'):
                opened.return_value.__enter__.return_value.read.return_value = b"[]"
                self.assertEqual(room_worker.room_client(args, "history", "--inbox", "--after", "2"), [])
                request = opened.call_args.args[0]
                self.assertEqual(request.full_url, "https://room.example/v1/history?inbox=1&after=2")

    def test_ignores_replies_instead_of_starting_a_loop(self):
        reply = {"id": 3, "actor": "alice", "recipient": "bob", "body": "Reply",
                 "thread_id": 1, "reply_to": 1, "projects": []}
        with tempfile.TemporaryDirectory() as state:
            with self.assertRaisesRegex(room_worker.WorkerError, "no eligible question"):
                room_worker.run_one(lambda *_: [reply], lambda _: self.fail("model called"),
                                    after=2, actor="bob", peer="alice", wait=0,
                                    origin="https://room.example", state=Path(state))


if __name__ == "__main__":
    unittest.main()
