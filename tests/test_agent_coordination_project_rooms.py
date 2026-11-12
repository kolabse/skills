"""Exercise two project rooms and a pre-existing pilot database on one listener."""
from argparse import Namespace
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.request import Request

SCRIPTS = Path(__file__).resolve().parents[1] / "prototypes/agent_coordination_rooms/coordinate-agent-rooms/scripts"
sys.path.insert(0, str(SCRIPTS))
import room_client
import room_join


class ProjectRoomTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.state = Path(directory.name)
        self.legacy = self.state / "pilot.sqlite"
        self.registry = self.state / "rooms"
        self.ca = None

    def cli(self, script, *args, status=0):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / script), *map(str, args)],
            capture_output=True, text=True, encoding="utf-8", timeout=15,
        )
        self.assertEqual(result.returncode, status, result.stderr)
        return json.loads(result.stdout) if status == 0 else None

    def admin(self, *args, **kwargs):
        return self.cli("room_admin.py", "--rooms-dir", self.registry, *args, **kwargs)

    def start(self, *options, with_registry=True):
        registry = ["--rooms-dir", str(self.registry)] if with_registry else []
        process = subprocess.Popen(
            [sys.executable, str(SCRIPTS / "room_service.py"),
             "--db", str(self.legacy), *registry,
             "serve", "--port", "0", "--invite-only", *map(str, options)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
        )
        self.addCleanup(self.stop, process)
        ready = process.stdout.readline()
        if not ready:
            self.fail(process.communicate(timeout=5)[1])
        settings = json.loads(ready)
        scheme = "https" if settings["tls"] else "http"
        self.origin = f"{scheme}://127.0.0.1:{settings['port']}"
        return process

    def stop(self, process):
        if process.poll() is None:
            process.terminate()
        process.communicate(timeout=5)

    def request(self, path, body=None, token=None, status=200):
        origin, opener = room_client.connection(self.origin, self.ca)
        headers = {"Content-Type": "application/json"} if body is not None else {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        data = json.dumps(body).encode() if body is not None else None
        try:
            response = opener.open(Request(origin + path, data=data, headers=headers), timeout=5)
        except HTTPError as error:
            response = error
        with response:
            self.assertEqual(response.code, status)
            return json.load(response)

    def test_isolation_and_legacy_compatibility(self):
        self.exercise()

    @unittest.skipUnless(shutil.which("openssl"), "OpenSSL required for a temporary test certificate")
    def test_isolation_over_https(self):
        self.ca = self.state / "cert.pem"
        key = self.state / "key.pem"
        config = self.state / "openssl.cnf"
        config.write_text(
            "[req]\nprompt=no\ndistinguished_name=dn\nx509_extensions=extensions\n"
            "[dn]\nCN=127.0.0.1\n[extensions]\nsubjectAltName=IP:127.0.0.1\n",
            encoding="ascii",
        )
        subprocess.run(
            ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
             "-config", str(config),
             "-out", str(self.ca), "-keyout", str(key)],
            check=True, capture_output=True, timeout=20,
        )
        self.exercise("--cert", self.ca, "--key", key)

    def exercise(self, *options):
        self.cli("room.py", "--db", self.legacy, "init", "--project", "pilot")
        self.cli("room.py", "--db", self.legacy, "grant", "alice", "--project", "pilot")
        pilot_invite = self.cli("room_service.py", "--db", self.legacy, "issue-invite", "alice")
        legacy_process = self.start(*options, with_registry=False)
        pilot = self.request("/v1/team/join", pilot_invite)
        legacy_message = self.request("/v1/messages", {"request": "pilot", "body": "FM-238"},
                                      token=pilot["token"])
        self.stop(legacy_process)
        process = self.start(*options)
        self.assertEqual(self.request("/health"), {"status": "ok"})
        self.assertEqual(self.request("/v1/history", token=pilot["token"]), [legacy_message])

        # Rooms added by a separate CLI process become available without a restart.
        for name in ("alpha", "beta"):
            self.admin("create", name, "--project", name)
            for actor in ("alice", "bob"):
                self.admin("grant", name, actor, "--project", name)
        self.assertEqual(self.admin("list"), ["alpha", "beta"])
        self.admin("create", "alpha", "--project", "other", status=2)
        self.admin("create", "../pilot", "--project", "pilot", status=2)
        self.admin("grant", "alpha", "alice", "--project", "beta", status=2)

        a, b = "/rooms/alpha", "/rooms/beta"
        alpha_invite = self.admin("invite", "alpha", "alice")
        self.request(b + "/v1/team/join", alpha_invite, status=401)
        alpha = self.request(a + "/v1/team/join", alpha_invite)
        self.request(a + "/v1/team/join", alpha_invite, status=401)
        self.request(b + "/v1/team/renew", {"credential": alpha["credential"]}, status=401)
        for path in (b, ""):
            self.request(path + "/v1/history", token=alpha["token"], status=401)
        self.request(a + "/v1/history", token=pilot["token"], status=401)
        self.request("/rooms/unknown/v1/history", token=alpha["token"], status=404)
        self.request("/rooms/%61lpha/v1/history", token=alpha["token"], status=404)

        token_file, credential_file, invite_file = (
            self.state / name for name in ("beta-token.json", "beta-credential.json", "beta-invite.json")
        )
        invite_file.write_text(json.dumps(self.admin("invite", "beta", "alice")), encoding="utf-8")
        join_args = ["--url", self.origin + b + "/", "--credential-file", str(credential_file),
                     "--token-file", str(token_file)]
        if self.ca:
            join_args.extend(["--ca", str(self.ca)])
        with redirect_stdout(StringIO()):
            self.assertEqual(room_join.main([*join_args, "--invite-file", str(invite_file)]), 0)

        def beta_client(command, **args):
            return room_client.request_room(Namespace(
                url=self.origin + b, ca=self.ca, token_file=token_file, command=command, **args,
            ))

        question = {"request": "same-id", "body": "Alpha only", "to": "bob"}
        first = self.request(a + "/v1/messages", question, token=alpha["token"])
        self.assertEqual(beta_client("history", inbox=False, after=0), [])
        beta_token = json.loads(token_file.read_text())["token"]
        beta_bob = self.request(b + "/v1/team/join", self.admin("invite", "beta", "bob"))
        self.request(b + "/v1/messages", {"request": "reply", "body": "Wrong room",
                     "reply_to": first["id"]}, token=beta_bob["token"], status=403)
        second = beta_client("post", request="same-id", body="Beta only", to="bob",
                             reply_to=None, project=[])
        self.assertEqual(first["id"], second["id"])
        reply = self.request(b + "/v1/messages", {"request": "reply", "body": "Beta answer",
                             "reply_to": second["id"], "to": "alice"}, token=beta_bob["token"])
        self.assertEqual(reply["thread_id"], second["id"])
        self.assertEqual(self.request(a + "/v1/history", token=alpha["token"]), [first])
        self.assertEqual(beta_client("history", inbox=True, after=0), [reply])

        self.admin("revoke", "alpha", "alice")
        self.request(a + "/v1/history", token=alpha["token"], status=401)
        self.request(a + "/v1/team/renew", {"credential": alpha["credential"]}, status=401)
        self.stop(process)
        self.start(*options)
        join_args[1] = self.origin + b + "/"
        with redirect_stdout(StringIO()):
            self.assertEqual(room_join.main(join_args), 0)
        self.request(b + "/v1/history", token=beta_token, status=401)
        self.assertEqual(beta_client("history", inbox=False, after=0), [second, reply])
        self.assertEqual(self.request("/v1/history", token=pilot["token"]), [legacy_message])


if __name__ == "__main__":
    unittest.main()
