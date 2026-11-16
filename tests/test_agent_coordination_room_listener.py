"""Persist room events for the correct Desktop chat across listener restarts."""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] /
                       "prototypes/agent_coordination_rooms/coordinate-agent-rooms/scripts"))
import room_listener


class ListenerTests(unittest.TestCase):
    def test_visible_notification_does_not_publish_or_enqueue_twice(self):
        with TemporaryDirectory() as folder:
            state = Path(folder) / "listener.sqlite"
            binding = dict(origin="https://room.example/rooms/portal", actor="bob", projects={"portal"},
                           thread="chat-a", auto_reply_from=set())
            message = {"id": 1, "actor": "alice", "recipient": "bob", "projects": ["portal"],
                       "reply_to": 4, "thread_id": 4, "body": "Status is green."}
            room_listener.capture_desktop_inbox(state, binding, lambda *_: [message])
            queued = []
            for _ in range(2):
                room_listener.deliver_desktop_message(
                    state, binding, lambda *_: self.fail("notification published to room"),
                    lambda thread, prompt: queued.append((thread, prompt)),
                    lambda *_: {"id": "turn-a", "answer": "Received."},
                )
            self.assertEqual(len(queued), 1)
            self.assertEqual(queued[0][0], "chat-a")
            self.assertIn("Status is green.", queued[0][1])

    def test_closed_chat_defers_delivery_until_the_chat_is_active(self):
        with TemporaryDirectory() as folder:
            state = Path(folder) / "listener.sqlite"
            binding = dict(origin="https://room.example/rooms/portal", actor="bob", projects={"portal"},
                           thread="chat-a", auto_reply_from=set())
            message = {"id": 1, "actor": "alice", "recipient": "bob", "projects": ["portal"],
                       "reply_to": None, "thread_id": 1, "body": "Status is green."}
            room_listener.capture_desktop_inbox(state, binding, lambda *_: [message])
            queued = []

            def queue(thread, prompt):
                queued.append((thread, prompt))
                if len(queued) == 1:
                    raise room_listener.DesktopSessionUnavailable("chat is closed")

            def deliver():
                room_listener.deliver_desktop_message(
                    state, binding, lambda *_: self.fail("notification published to room"),
                    queue, lambda *_: {"id": "turn-a", "answer": "Received."},
                )

            with self.assertRaises(room_listener.DesktopSessionUnavailable):
                deliver()
            deliver()
            deliver()
            self.assertEqual(len(queued), 2)
            self.assertEqual(queued[0], queued[1])

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

    def test_desktop_turn_and_room_reply_are_recovered_without_requeueing(self):
        with TemporaryDirectory() as folder:
            state = Path(folder) / "listener.sqlite"
            binding = dict(origin="https://room.example/rooms/portal", actor="bob", projects={"portal"},
                           thread="chat-a", auto_reply_from={"alice"})
            question = {"id": 2, "actor": "alice", "recipient": "bob", "projects": ["portal"],
                        "reply_to": None, "thread_id": 2, "body": "Status?"}
            messages = [question]
            room_listener.capture_desktop_inbox(state, binding, lambda *_: messages)
            queued, observed, posts = [], [], []

            def queue(thread, prompt):
                queued.append((thread, prompt))
                raise TimeoutError("acknowledgement lost")

            def observe(thread, prompt):
                observed.append((thread, prompt))
                return {"id": "turn-a", "answer": "The check is pending."}

            def request(*args):
                posts.append(args)
                if len(posts) == 1:
                    raise ConnectionError("reply acknowledgement lost")
                return {"id": 3, "actor": "bob", "recipient": "alice", "reply_to": 2, "thread_id": 2}

            with self.assertRaises(TimeoutError):
                room_listener.deliver_desktop_message(state, binding, request, queue, observe)
            with self.assertRaises(ConnectionError):
                room_listener.deliver_desktop_message(state, binding, request, queue, observe)
            room_listener.deliver_desktop_message(state, binding, request, queue, observe)
            room_listener.deliver_desktop_message(state, binding, request, queue, observe)
            self.assertEqual(len(queued), 1)
            self.assertEqual(queued[0][0], "chat-a")
            self.assertIn("Status?", queued[0][1])
            self.assertEqual(observed, queued)
            self.assertEqual(posts, [("post", "codex-reply-2", "The check is pending.",
                                      "--to", "alice", "--reply-to", "2")] * 2)
            self.assertEqual([entry["message"]["id"] for entry in room_listener.desktop_pending(state, "chat-a")],
                             [2])
