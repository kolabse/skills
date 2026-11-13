"""Periodic processing of project-labelled questions and cursor recovery."""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "prototypes/agent_coordination_rooms/coordinate-agent-rooms/scripts"))
import room_worker


class WatchTests(unittest.TestCase):
    def test_polls_again_and_reuses_the_reply_after_a_delivery_failure(self):
        question = {"id": 3, "actor": "alice", "recipient": "bob", "body": "Status?",
                    "thread_id": 3, "reply_to": None, "projects": ["portal"]}
        reply = dict(question, id=4, reply_to=1, thread_id=1)
        unapproved = dict(question, id=2, thread_id=2, projects=["infra"])
        calls = []
        posts = []
        answers = []

        def request(*args):
            if args[0] == "history":
                cursor = int(args[-1])
                calls.append(cursor)
                if len(calls) == 1:
                    return []
                return [item for item in (unapproved, question, reply) if item["id"] > cursor]
            posts.append(args)
            if len(posts) == 1:
                raise OSError("connection lost after sending")
            return {"id": 5, "actor": "bob", "recipient": "alice", "reply_to": 3, "thread_id": 3}

        def answer(body):
            answers.append(body)
            return "Please send the check result.", {"fragments": 1}

        with TemporaryDirectory() as folder:
            state = Path(folder)
            options = dict(after=0, actor="bob", peer="alice", origin="https://room.example/rooms/portal",
                           state=state, projects={"portal"})
            self.assertEqual(room_worker.poll_inbox(request, answer, **options), 0)
            with self.assertRaises(OSError):
                room_worker.poll_inbox(request, answer, **options)
            self.assertEqual(room_worker.poll_inbox(request, answer, **options), 1)
            self.assertEqual(room_worker.poll_inbox(request, answer, **options), 0)
            with self.assertRaisesRegex(room_worker.WorkerError, "different"):
                room_worker.poll_inbox(request, answer, **{**options, "projects": {"infra"}})
        self.assertEqual(calls, [0, 0, 2, 4])
        self.assertEqual(answers, ["Status?"])
        self.assertEqual(posts, [("post", "codex-reply-3", "Please send the check result.",
                                  "--to", "alice", "--reply-to", "3")] * 2)
