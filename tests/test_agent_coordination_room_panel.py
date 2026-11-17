"""The AICQ panel replays one authorized transcript per chat."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from test_agent_coordination_project_rooms import SCRIPTS
import room_listener


class PanelTests(unittest.TestCase):
    def test_snapshot_includes_incoming_and_own_replies_once(self):
        with TemporaryDirectory() as folder:
            db = Path(folder) / "room.sqlite"
            binding = dict(origin="https://room.example/rooms/pilot", actor="bob",
                           thread="chat-a", projects=["portal"], auto_reply=False)
            base = dict(actor="alice", recipient="bob", projects=["portal"], reply_to=None, body="Status?")
            page = [
                dict(base, id=1, thread_id=1),
                dict(base, id=2, thread_id=1, actor="bob", recipient="alice", reply_to=1, body="Done"),
                dict(base, id=3, thread_id=3, recipient="carol"),
                dict(base, id=4, thread_id=4, recipient=None, projects=["private"]),
            ]

            def history(*args):
                return [message for message in page if message["id"] > int(args[-1])]

            for _ in range(2):
                room_listener.capture_desktop_inbox(db, binding, history)
            result = room_listener.desktop_transcript(db, "chat-a")
            self.assertEqual([(row["message"]["id"], row["message"]["body"]) for row in result],
                             [(1, "Status?"), (2, "Done")])
            self.assertEqual(room_listener.desktop_transcript(db, "another-chat"), [])
