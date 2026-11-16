"""Periodic processing of project-labelled questions and cursor recovery."""
import json
from pathlib import Path
import subprocess
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

    def test_status_reports_live_process_last_success_and_resume_cursor(self):
        with TemporaryDirectory() as folder:
            state = Path(folder)

            def status():
                result = subprocess.run(
                    [sys.executable, room_worker.__file__, "status", "--state", folder],
                    capture_output=True, text=True, encoding="utf-8", timeout=5,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                return json.loads(result.stdout)

            self.assertEqual(status(), {"running": False, "last_successful_poll": None, "after": None})
            with room_worker.watch_lease(state):
                self.assertEqual(status(), {"running": True, "last_successful_poll": None, "after": None})
                with self.assertRaisesRegex(room_worker.WorkerError, "already running"):
                    with room_worker.watch_lease(state):
                        self.fail("second watcher acquired the same state")
                options = dict(after=7, actor="bob", peer="alice", origin="https://room.example",
                               state=state, projects={"portal"})
                room_worker.poll_inbox(lambda *_: [], lambda _: self.fail("model called"), **options)
                live = status()
                self.assertTrue(live["running"])
                self.assertEqual(live["after"], 7)
                self.assertRegex(live["last_successful_poll"], r"^\d{4}-\d{2}-\d{2}T.*\+00:00$")
                def fail(*_):
                    raise ConnectionError("offline")
                with self.assertRaises(ConnectionError):
                    room_worker.poll_inbox(fail, lambda _: self.fail("model called"), **options)
                self.assertEqual(status(), live)
            self.assertEqual(status(), {**live, "running": False})
