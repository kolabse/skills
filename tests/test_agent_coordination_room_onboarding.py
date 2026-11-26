"""A colleague can connect and renew from a room link and a private invitation."""
import json
from pathlib import Path
import subprocess
import sys
from threading import Thread
import unittest
from urllib.request import Request, urlopen

from test_agent_coordination_project_rooms import SCRIPTS
from tempfile import TemporaryDirectory

import room_listener
import room_client
import room_registry
import room_service


class RoomOnboardingTests(unittest.TestCase):
    def test_broadcast_ask_is_distinct_from_an_ordinary_room_message(self):
        public_link = self.base + "/rooms/alpha/invite"
        personal = self.admin("invite", "alpha", "alice", "--origin", self.base)["link"]
        join = self.run_cli("room_connect.py", "--link-stdin", "--state-dir", self.folder / "client",
                            stdin=personal + "\n")
        self.assertEqual(join.returncode, 0, join.stderr)
        session = json.loads(join.stdout)["session_file"]

        def client(*args, status=0):
            result = self.run_cli("room_client.py", "--url", public_link.removesuffix("/invite"),
                                  "--token-file", session, *args)
            self.assertEqual(result.returncode, status, result.stderr)
            return json.loads(result.stdout) if result.stdout else None

        client("post", "notice", "Build complete")
        client("ask", "question", "Can anyone check?")
        notice, question = client("history")
        self.assertFalse(notice.get("question", False))
        self.assertIs(question["question"], True)
        self.assertIsNone(question["recipient"])
        client("post", "question", "Can anyone check?", status=1)

    def test_two_listeners_answer_followup_once_in_original_thread(self):
        self.admin("grant", "alpha", "bob", "--project", "portal")
        url = self.base + "/rooms/alpha"
        sessions = {}
        for actor in ("alice", "bob"):
            link = self.admin("invite", "alpha", actor, "--origin", self.base)["link"]
            joined = self.run_cli("room_connect.py", "--link-stdin", "--state-dir", self.folder / actor,
                                  stdin=link + "\n")
            self.assertEqual(joined.returncode, 0, joined.stderr)
            sessions[actor] = json.loads(joined.stdout)["session_file"]

        def request(actor, *command):
            args = room_client.parse(["--url", url, "--token-file", sessions[actor], *command])
            if args.command in ("ask", "ack-inbox"):
                result, status = room_client.managed_inbox(args)
                self.assertEqual(status, 0, result)
                return result
            return room_client.request_room(args)

        generated = []
        def poll(actor):
            state = self.folder / actor / "listener.sqlite"
            binding = dict(origin=url, actor=actor, projects=["portal"], thread=actor, auto_reply=True)
            def send(*command):
                return request(actor, *command)
            def answer(body):
                generated.append((actor, body))
                return "Response to " + body
            room_listener.capture_desktop_inbox(state, binding, send)
            room_listener.process_desktop_reply(state, binding, send, answer)

        question = request("alice", "ask", "first", "Check revision?", "--to", "bob")
        poll("bob")
        first_reply = request("alice", "history")[-1]
        request("alice", "ack-inbox", str(first_reply["id"]))
        followup = request("alice", "ask", "followup", "Which revision?", "--to", "bob",
                           "--reply-to", str(first_reply["id"]))
        for _ in range(3):
            poll("alice")
            poll("bob")
        history = request("alice", "history")
        self.assertEqual([actor for actor, _ in generated], ["bob", "bob"])
        self.assertEqual(generated[0][1], "Check revision?")
        self.assertEqual(json.loads(generated[1][1]), {
            "previous_reply": "Response to Check revision?", "followup": "Which revision?",
        })
        self.assertEqual([m["reply_to"] for m in history],
                         [None, question["id"], first_reply["id"], followup["id"]])
        self.assertEqual({m["thread_id"] for m in history}, {question["id"]})

    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.registry = room_registry.RoomRegistry(self.folder / "rooms")
        self.admin("create", "alpha", "--project", "portal")
        self.admin("create", "beta", "--project", "infra")
        self.admin("grant", "alpha", "alice", "--project", "portal")
        self.admin("grant", "beta", "alice", "--project", "infra")
        self.server = room_service.RoomServer(("127.0.0.1", 0), None, None, True, registry=self.registry)
        self.worker = Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.addCleanup(self.stop)
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(5)

    def run_cli(self, script, *args, stdin=None):
        return subprocess.run(
            [sys.executable, str(SCRIPTS / script), *map(str, args)],
            input=stdin, capture_output=True, text=True, encoding="utf-8", timeout=15,
        )

    def admin(self, *args):
        result = self.run_cli("room_admin.py", "--rooms-dir", self.registry.directory, *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_personal_link_joins_and_renews_without_an_invitation_file(self):
        invitation = self.admin("invite", "alpha", "alice", "--origin", self.base)["link"]
        manifest, secret = invitation.split("#", 1)
        self.assertEqual(manifest, self.base + "/rooms/alpha/invite")
        state = self.folder / "client"

        def connect(link):
            return self.run_cli("room_connect.py", "--link-stdin", "--state-dir", state, stdin=link + "\n")

        wrong_room = connect(invitation.replace("/alpha/", "/beta/"))
        self.assertIn("HTTP 401", wrong_room.stderr)
        joined = connect(invitation)
        self.assertEqual(joined.returncode, 0, joined.stderr)
        receipt = json.loads(joined.stdout)
        self.assertEqual((receipt["status"], receipt["actor"], receipt["readable"]),
                         ("joined", "alice", ["portal"]))
        renewed = connect(manifest)
        self.assertEqual(renewed.returncode, 0, renewed.stderr)
        self.assertEqual(json.loads(renewed.stdout)["status"], "renewed")
        self.assertEqual(json.loads(renewed.stdout)["session_file"], receipt["session_file"])
        replay = connect(invitation)
        self.assertIn("HTTP 401", replay.stderr)
        self.assertNotIn(secret, joined.stdout + renewed.stdout + wrong_room.stderr + replay.stderr)
        self.assertNotIn(secret, Path(receipt["session_file"]).read_text(encoding="utf-8"))

    def test_link_and_bundle_connect_and_renew_two_isolated_sessions(self):
        alpha = self.base + "/rooms/alpha/invite"
        beta = self.base + "/rooms/beta/invite"
        with urlopen(alpha, timeout=5) as page:
            self.assertEqual(page.headers.get_content_type(), "text/html")
            self.assertIn("AICQ", page.read().decode("utf-8"))
        with urlopen(Request(alpha, headers={"Accept": "application/json"}), timeout=5) as manifest:
            self.assertEqual(json.load(manifest), {"version": 1, "room": "alpha"})

        bundles = {
            link: self.admin("invite", name, "alice", "--link", link)
            for link, name in ((alpha, "alpha"), (beta, "beta"))
        }
        invite_file = self.folder / "invitation.json"
        state = self.folder / "client"

        def connect(link, *extra):
            return self.run_cli("room_connect.py", "--link", link, "--state-dir", state, *extra)

        invite_file.write_text(json.dumps(bundles[alpha]), encoding="utf-8")
        mismatch = connect(beta, "--invite-file", invite_file)
        self.assertNotEqual(mismatch.returncode, 0)
        self.assertIn("does not match the invitation link", mismatch.stderr)
        tampered = dict(bundles[alpha], actor="someone-else")
        invite_file.write_text(json.dumps(tampered), encoding="utf-8")
        invalid = connect(alpha, "--invite-file", invite_file)
        self.assertNotEqual(invalid.returncode, 0)
        self.assertIn("HTTP 401", invalid.stderr)

        for link, project in ((alpha, "portal"), (beta, "infra")):
            invite_file.write_text(json.dumps(bundles[link]), encoding="utf-8")
            joined = connect(link, "--invite-file", invite_file)
            self.assertEqual(joined.returncode, 0, joined.stderr)
            receipt = json.loads(joined.stdout)
            self.assertEqual((receipt["status"], receipt["actor"], receipt["readable"]),
                             ("joined", "alice", [project]))
            session_path = Path(receipt["session_file"])
            previous = json.loads(session_path.read_text(encoding="utf-8"))["token"]
            renewed = connect(link)
            self.assertEqual(renewed.returncode, 0, renewed.stderr)
            self.assertEqual(json.loads(renewed.stdout)["status"], "renewed")
            saved = json.loads(session_path.read_text(encoding="utf-8"))
            self.assertNotEqual(saved["token"], previous)
            for secret in (bundles[link]["invite"], saved["credential"], saved["token"]):
                self.assertNotIn(secret, joined.stdout + renewed.stdout)

        self.assertEqual(len(list(state.glob("*.json"))), 2)

    def test_outgoing_id_does_not_hide_unacknowledged_inbox_after_restart(self):
        link = self.base + "/rooms/alpha/invite"
        self.admin("grant", "alpha", "bob", "--project", "portal")

        def join(actor):
            invite_file = self.folder / (actor + ".json")
            invite_file.write_text(json.dumps(self.admin("invite", "alpha", actor, "--link", link)),
                                   encoding="utf-8")
            result = self.run_cli("room_connect.py", "--link", link, "--invite-file", invite_file,
                                  "--state-dir", self.folder / actor)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)["session_file"]

        alice, bob = join("alice"), join("bob")

        def client(token_file, *args, status=0):
            result = self.run_cli("room_client.py", "--url", link.removesuffix("/invite"),
                                  "--token-file", token_file, *args)
            self.assertEqual(result.returncode, status, result.stderr)
            return json.loads(result.stdout)

        client(bob, "post", "seed", "Earlier message")
        question = client(alice, "post", "q", "Question for Bob", "--to", "bob")
        outgoing = client(bob, "post", "legacy", "A later outgoing question", "--to", "alice")
        self.assertEqual((question["id"], outgoing["id"]), (2, 3))
        self.assertEqual(client(bob, "history", "--inbox", "--after", "3"), [])

        # Each CLI call is a fresh process. Reading alone does not acknowledge.
        self.assertEqual(client(bob, "inbox"), [question])
        blocked = client(bob, "ask", "new", "New question", "--to", "alice", status=2)
        self.assertEqual(blocked, {"status": "pending_inbox", "messages": [question]})
        self.assertEqual(client(bob, "inbox"), [question])
        self.assertEqual(client(bob, "ack-inbox", "2"), {"after": 2})
        self.assertEqual(client(bob, "inbox"), [])
        self.assertEqual(client(bob, "ask", "new", "New question", "--to", "alice")["id"], 4)
        self.assertEqual([item["id"] for item in client(alice, "inbox")], [3, 4])
