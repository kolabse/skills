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

import room_registry
import room_service


class RoomOnboardingTests(unittest.TestCase):
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

    def run_cli(self, script, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPTS / script), *map(str, args)],
            capture_output=True, text=True, encoding="utf-8", timeout=15,
        )

    def admin(self, *args):
        result = self.run_cli("room_admin.py", "--rooms-dir", self.registry.directory, *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

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
