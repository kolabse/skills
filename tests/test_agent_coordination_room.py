"""Exercise the room through separate CLI invocations."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


CLI = Path(__file__).resolve().parents[1] / "prototypes/agent_coordination_rooms/coordinate-agent-rooms/scripts/room.py"


class RoomTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.db = Path(directory.name) / "room.sqlite"
        self.run_room("init", "--project", "pilot", "--project", "digest")
        self.run_room("grant", "alice", "--project", "pilot", "--project", "digest")
        self.run_room("grant", "bob", "--project", "pilot")
        self.run_room("grant", "cara", "--project", "pilot", "--project", "digest")

    def run_room(self, *args, error=None):
        result = subprocess.run(
            [sys.executable, str(CLI), "--db", str(self.db), *args],
            capture_output=True, text=True, encoding="utf-8",
        )
        if error:
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn(error, result.stderr)
            return None
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def post(self, actor, request, *args, text="Question?", error=None):
        return self.run_room("post", actor, request, text, *args, error=error)

    def test_address_controls_inbox_and_offline_members_can_reply(self):
        public = self.post("alice", "first")
        directed = self.post("alice", "second", "--to", "bob")
        self.assertEqual(self.run_room("history", "bob", "--after", str(public["id"])), [directed])
        self.assertEqual(self.run_room("history", "bob", "--inbox"), [directed])
        self.assertEqual(self.run_room("history", "cara", "--inbox"), [])
        self.assertEqual(self.run_room("history", "cara"), [public, directed])
        reply = self.post("cara", "reply", "--reply-to", str(directed["id"]), text="I checked it.")
        self.assertEqual(reply["thread_id"], directed["id"])
        self.assertEqual(reply["reply_to"], directed["id"])

    def test_scope_and_current_permissions_apply_to_history_and_replies(self):
        self.post("alice", "restricted", "--project", "pilot", error="publication scope")
        self.run_room("scope", "alice", "--project", "pilot", "--project", "digest")
        secret = self.post("alice", "restricted", "--project", "pilot", "--project", "digest")
        self.assertEqual(self.run_room("history", "bob"), [])
        self.assertEqual(self.run_room("history", "cara"), [secret])
        self.post("bob", "reply", "--reply-to", str(secret["id"]), error="message unavailable")
        self.post("cara", "reply", "--reply-to", str(secret["id"]), error="publication scope")
        self.run_room("scope", "cara", "--project", "pilot", "--project", "digest")
        reply = self.post("cara", "reply", "--reply-to", str(secret["id"]))
        self.assertEqual(reply["projects"], ["digest", "pilot"])
        self.post("alice", "target", "--project", "digest", "--to", "bob", error="recipient")
        self.run_room("grant", "cara", "--project", "pilot")
        self.assertEqual(self.run_room("history", "cara"), [])
        self.run_room("revoke", "cara")
        self.run_room("history", "cara", error="not a room member")

    def test_empty_selection_is_distinct_from_no_selection(self):
        self.assertFalse(self.run_room("access", "alice")["scope_selected"])
        self.assertTrue(self.run_room("scope", "alice")["scope_selected"])
        self.assertEqual(self.run_room("access", "alice")["publishable"], [])
        self.post("alice", "general")
        self.post("alice", "private", "--project", "pilot", error="publication scope")
        self.run_room("revoke", "alice")
        self.run_room("grant", "alice", "--project", "pilot")
        self.assertFalse(self.run_room("access", "alice")["scope_selected"])

    def test_idempotency_and_cursor_pagination(self):
        first = self.post("alice", "key")
        self.assertEqual(self.post("alice", "key"), first)
        self.post("alice", "key", text="different", error="already used")
        second = self.post("alice", "next")
        self.assertEqual(self.run_room("history", "bob", "--limit", "1"), [first])
        self.assertEqual(self.run_room("history", "bob", "--after", str(first["id"])), [second])


if __name__ == "__main__":
    unittest.main()
