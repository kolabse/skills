"""Complete an approved personal-link onboarding in the originating chat."""
from argparse import Namespace
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from test_agent_coordination_project_rooms import SCRIPTS
import room_listener


class ChatOnboardingTests(unittest.TestCase):
    def test_approved_link_registers_current_chat_and_verifies_fresh_poll(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            codex = root / "codex.exe"
            codex.touch()
            chat = "00000000-0000-4000-8000-000000000001"
            link = "https://room.example/rooms/portal/invite"
            secret = "a" * 43
            args = Namespace(link=link + "#" + secret, project=["portal"], auto_reply_from=["alice"],
                             codex=codex, after=0)
            config = root / "bindings.json"
            state = root / "listener.sqlite"
            joined = {"actor": "bob", "readable": ["portal"], "link": link,
                      "session_file": str(root / "session.json"), "status": "joined", "room": "portal"}
            with (patch.dict(os.environ, {"CODEX_THREAD_ID": chat}),
                  patch.object(room_listener, "connect", return_value=joined),
                  patch.object(room_listener, "worker_request",
                               return_value={"readable": ["portal"], "publishable": ["portal"]}),
                  patch.object(room_listener, "ensure_running", return_value={"polled": True, "after": 0},
                               create=True) as startup):
                result = room_listener.onboard(args, config, state)
                again = room_listener.onboard(args, config, state)
            binding, = json.loads(config.read_text(encoding="utf-8"))
            self.assertEqual(binding["thread"], chat)
            self.assertEqual(binding["auto_reply_from"], ["alice"])
            self.assertEqual(result, again)
            self.assertEqual(result["listener"], {"polled": True, "after": 0})
            self.assertEqual(startup.call_count, 2)
            self.assertNotIn(secret, str(result) + str(binding))
            self.assertFalse(room_listener.disable_binding(config, link, "another-chat"))
            self.assertTrue(room_listener.disable_binding(config, link, chat))
            self.assertEqual(json.loads(config.read_text(encoding="utf-8")), [])

    def test_missing_chat_stops_before_consuming_the_invite(self):
        with TemporaryDirectory() as folder:
            args = Namespace(link="https://room.example/rooms/portal/invite", project=["portal"],
                             auto_reply_from=[], codex=None, after=0)
            with (patch.dict(os.environ, {"CODEX_THREAD_ID": ""}),
                  patch.object(room_listener, "connect") as connect):
                with self.assertRaisesRegex(room_listener.ListenerError, "current Desktop chat"):
                    room_listener.onboard(args, Path(folder) / "bindings.json", Path(folder) / "listener.sqlite")
                connect.assert_not_called()
