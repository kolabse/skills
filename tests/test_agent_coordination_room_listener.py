"""Persist room events for the correct Desktop chat across listener restarts."""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] /
                       "prototypes/agent_coordination_rooms/coordinate-agent-rooms/scripts"))
import room_listener
import room_worker


class ListenerTests(unittest.TestCase):
    def test_worker_restricts_capabilities_before_sending_room_text(self):
        with TemporaryDirectory() as folder:
            executable = Path(folder) / "codex.exe"
            with patch.object(room_worker.subprocess, "Popen") as spawn, patch.object(room_worker, "AppServer") as server:
                spawn.return_value.__enter__.return_value.poll.return_value = 0
                server.return_value.call.return_value = ({"config": {}}, [])
                server.return_value.turn.return_value = ("Answer", {})
                room_worker.codex_answer(executable, "Synthetic question", project_mode=True)
                argv = spawn.call_args.args[0]
                for feature in ("shell_tool", "apps", "plugins", "hooks", "multi_agent_v2"):
                    self.assertIn(("--disable", feature), list(zip(argv, argv[1:])))
                self.assertIn("mcp_servers={}", argv)
                self.assertTrue(server.return_value.new_thread.call_args.kwargs["restricted"])
                self.assertTrue(server.return_value.turn.call_args.kwargs["restricted"])
                server.reset_mock()
                server.return_value.call.return_value = ({"config": {"mcp_servers": {"synthetic": {}}}}, [])
                with self.assertRaisesRegex(room_worker.WorkerError, "enabled MCP server"):
                    room_worker.codex_answer(executable, "Synthetic question", project_mode=True)
                server.return_value.new_thread.assert_not_called()
                server.return_value.turn.assert_not_called()
    def test_resume_before_reply_and_after_publish_without_duplicates(self):
        with TemporaryDirectory() as folder:
            state = Path(folder) / "listener.sqlite"
            binding = dict(origin="https://room.example/rooms/portal", actor="bob", projects=["portal"],
                           thread="chat-a", auto_reply=True)
            question = dict(id=2, actor="alice", recipient="bob", projects=["portal"],
                            reply_to=None, thread_id=2, body="Synthetic question")
            room_listener.capture_desktop_inbox(state, binding, lambda *_: [question])
            answered, receipts = [], {}

            def answer(text):
                answered.append(text)
                if len(answered) == 1:
                    raise InterruptedError("listener stopped before saving its answer")
                return "Synthetic answer"

            def request(*args):
                receipt = dict(id=3, actor="bob", recipient="alice", reply_to=2, thread_id=2)
                if args[1] not in receipts:
                    receipts[args[1]] = receipt
                    raise ConnectionError("response lost after server accepted reply")
                return receipts[args[1]]

            for error in (InterruptedError, ConnectionError):
                with self.assertRaises(error):
                    room_listener.process_desktop_reply(state, binding, request, answer)
            for _ in range(2):
                room_listener.process_desktop_reply(state, binding, request, answer)
            self.assertEqual(answered, ["Synthetic question"] * 2)
            self.assertEqual(list(receipts), ["codex-reply-2"])
            self.assertEqual(len(room_listener.desktop_pending(state, "chat-a")), 1)
    def test_auto_reply_accepts_addressed_and_broadcast_requests_from_any_sender(self):
        with TemporaryDirectory() as folder:
            state = Path(folder) / "listener.sqlite"
            binding = dict(origin="https://room.example/rooms/portal", actor="bob", projects=["portal"],
                           thread="chat-a", auto_reply=True, auto_reply_from=[])
            base = {"actor": "new-colleague", "recipient": "bob", "projects": ["portal"],
                    "reply_to": None, "body": "Can you confirm?"}
            page = [
                dict(base, id=1, thread_id=1),
                dict(base, id=2, thread_id=2, recipient=None, question=True, projects=[]),
                dict(base, id=3, thread_id=3, recipient=None),
                dict(base, id=4, thread_id=2, reply_to=2),
                dict(base, id=5, thread_id=5, recipient="other"),
                dict(base, id=6, thread_id=2, reply_to=4, question=True),
                dict(base, id=7, thread_id=7, question=False),
            ]
            room_listener.capture_desktop_inbox(state, binding, lambda *_: page)
            self.assertEqual([(row["message"]["id"], row["auto_reply"])
                              for row in room_listener.desktop_pending(state, "chat-a")],
                             [(1, True), (2, True), (3, False), (4, False), (6, True), (7, False)])
    def test_routes_each_room_to_its_chat_and_retains_replies_without_triggering_a_turn(self):
        def message(number, sender="alice", recipient="bob", project="portal", parent=None):
            return {"id": number, "actor": sender, "recipient": recipient, "projects": [project],
                    "reply_to": parent, "thread_id": parent or number, "body": "Status?"}

        with TemporaryDirectory() as folder:
            state = Path(folder) / "listener.sqlite"
            portal = dict(origin="https://room.example/rooms/portal", actor="bob", projects={"portal"},
                          thread="chat-a", auto_reply_from={"alice"})
            infra = dict(origin="https://room.example/rooms/infra", actor="bob", projects={"infra"},
                         thread="chat-b", auto_reply_from={"alice"})
            portal_page = [message(1, recipient=None), message(2), message(3, parent=1),
                           message(4, recipient="carol"), message(5, sender="bob", recipient="alice"),
                           message(6, project="infra")]
            infra_page = [message(1, project="infra")]
            seen = []

            def request(page):
                def history(*argv):
                    after = int(argv[-1])
                    seen.append(after)
                    return [item for item in page if item["id"] > after]
                return history

            room_listener.capture_desktop_inbox(state, portal, request(portal_page))
            room_listener.capture_desktop_inbox(state, infra, request(infra_page))
            room_listener.capture_desktop_inbox(state, portal, request(portal_page))
            self.assertEqual(seen, [0, 0, 6])
            self.assertEqual([(row["message"]["id"], row["auto_reply"])
                              for row in room_listener.desktop_pending(state, "chat-a")],
                             [(1, False), (2, True), (3, False)])
            self.assertEqual([(row["message"]["id"], row["auto_reply"])
                              for row in room_listener.desktop_pending(state, "chat-b")], [(1, True)])
            with self.assertRaisesRegex(room_listener.ListenerError, "already bound"):
                room_listener.capture_desktop_inbox(state, {**portal, "thread": "wrong"}, request(portal_page))

    def test_invalid_page_does_not_advance_or_persist_partial_results(self):
        with TemporaryDirectory() as folder:
            state = Path(folder) / "listener.sqlite"
            binding = dict(origin="https://room.example/rooms/portal", actor="bob", projects={"portal"},
                           thread="chat-a", auto_reply_from={"alice"})
            question = {"id": 1, "actor": "alice", "recipient": "bob", "projects": ["portal"],
                        "reply_to": None, "thread_id": 1, "body": "Status?"}
            with self.assertRaisesRegex(room_listener.ListenerError, "invalid room history sequence"):
                room_listener.capture_desktop_inbox(state, binding, lambda *_: [question, question])
            self.assertEqual(room_listener.desktop_pending(state, "chat-a"), [])
            room_listener.capture_desktop_inbox(state, binding, lambda *_: [question])
            self.assertEqual(len(room_listener.desktop_pending(state, "chat-a")), 1)
