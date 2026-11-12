"""Invitation redemption, session renewal and revocation for the room pilot."""
import json
from pathlib import Path
import sys
import tempfile
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] /
                       "prototypes/agent_coordination_rooms/coordinate-agent-rooms/scripts"))
import room
import room_service
import room_team


class TeamRoomTests(unittest.TestCase):
    def setUp(self):
        from argparse import Namespace
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.db = Path(directory.name) / "room.sqlite"
        with room.transaction(self.db, True, initialize=True) as db:
            room.init(db, Namespace(project=["pilot"]))
            room.grant(db, Namespace(actor="alice", project=["pilot"]))
            room.install_tokens(db)
            room_team.install(db)
        self.server = room_service.RoomServer(("127.0.0.1", 0), self.db, None, invite_only=True)
        self.worker = Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.addCleanup(self.stop)
        self.origin = f"http://127.0.0.1:{self.server.server_port}"

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(5)

    def invite(self):
        with room.transaction(self.db, True) as db:
            return room_team.issue_invite(db, "alice", 30)

    def request(self, path, payload=None, token=None, status=200):
        headers = {"Content-Type": "application/json"} if payload is not None else {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        data = json.dumps(payload).encode() if payload is not None else None
        try:
            response = urlopen(Request(self.origin + path, data=data, headers=headers), timeout=5)
        except HTTPError as error:
            response = error
        with response:
            self.assertEqual(response.code, status)
            return json.load(response)

    def test_invitation_is_one_time_and_cannot_set_its_own_permissions(self):
        invitation = self.invite()
        self.request("/v1/team/join", {"invite": invitation, "actor": "owner"}, status=400)
        result = self.request("/v1/team/join", {"invite": invitation})
        self.assertEqual(result["actor"], "alice")
        self.assertEqual(self.request("/v1/access", token=result["token"])["readable"], ["pilot"])
        self.request("/v1/team/join", {"invite": invitation}, status=401)
        self.request("/v1/scope", {"projects": ["other"]}, token=result["token"], status=403)

    def test_renewal_and_revocation_affect_room_access(self):
        from argparse import Namespace
        session = self.request("/v1/team/join", {"invite": self.invite()})
        self.request("/v1/access", token=session["credential"], status=401)
        fresh = self.request("/v1/team/renew", {"credential": session["credential"]})
        self.assertNotEqual(fresh["token"], session["token"])
        self.request("/v1/access", token=session["token"], status=401)
        self.request("/v1/access", token=fresh["token"])
        pending = self.invite()
        with room.transaction(self.db, True) as db:
            room.revoke(db, Namespace(actor="alice"))
            room.grant(db, Namespace(actor="alice", project=[]))
        self.request("/v1/access", token=fresh["token"], status=401)
        self.request("/v1/team/renew", {"credential": session["credential"]}, status=401)
        self.request("/v1/team/join", {"invite": pending}, status=401)
        with room.transaction(self.db, True) as db:
            with self.assertRaises(room.RoomError):
                room_team.issue_invite(db, "alice", 30)

    def test_expired_and_superseded_invitations_and_manual_tokens_are_denied(self):
        older = self.invite()
        current = self.invite()
        self.request("/v1/team/join", {"invite": older}, status=401)
        with room.transaction(self.db, True) as db:
            db.execute("UPDATE room_team_invites SET expires_at=0")
        self.request("/v1/team/join", {"invite": current}, status=401)
        token = room_service.issue_token(self.db, "alice", 60)["token"]
        self.request("/v1/access", token=token, status=401)

    def test_cli_joins_and_renews_without_printing_secrets(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from unittest.mock import patch
        import room_join

        token = self.db.parent / "token.json"
        credential = self.db.parent / "credential.json"
        args = ["--url", self.origin, "--credential-file", str(credential), "--token-file", str(token)]
        invitation = self.invite()
        stdout = StringIO()
        with patch.object(room_join, "getpass", return_value=invitation) as prompt, redirect_stdout(stdout):
            self.assertEqual(room_join.main(args), 0)
            initial = json.loads(token.read_text())["token"]
            self.assertEqual(room_join.main(args), 0)
            prompt.assert_called_once()
        updated = json.loads(token.read_text())["token"]
        renewal = json.loads(credential.read_text())["credential"]
        for secret in (initial, updated, invitation, renewal):
            self.assertNotIn(secret, stdout.getvalue())
        self.assertEqual([json.loads(line)["status"] for line in stdout.getvalue().splitlines()],
                         ["joined", "renewed"])
        self.request("/v1/access", token=initial, status=401)
        self.request("/v1/access", token=updated)

    def test_secrets_are_not_stored_as_plaintext(self):
        invite = self.invite()
        session = self.request("/v1/team/join", {"invite": invite})
        with room.transaction(self.db, False) as db:
            dump = "\n".join(db.iterdump())
        for secret in (invite, session["token"], session["credential"]):
            self.assertNotIn(secret, dump)


if __name__ == "__main__":
    unittest.main()
