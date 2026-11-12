"""Run two independent HTTP clients against a real room server and SQLite."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen


SCRIPTS = Path(__file__).resolve().parents[1] / "prototypes/agent_coordination_rooms/coordinate-agent-rooms/scripts"


class ServiceTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.db = Path(folder.name) / "room.sqlite"
        self.cli("room.py", "init", "--project", "pilot")
        for actor in ("alice", "bob"):
            self.cli("room.py", "grant", actor, "--project", "pilot")
        self.cli("room.py", "grant", "cara")
        self.start()

    def cli(self, script, *args):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / script), "--db", str(self.db), *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def token(self, actor):
        return self.cli("room_service.py", "issue-token", actor)["token"]

    def start(self):
        self.process = subprocess.Popen(
            [sys.executable, str(SCRIPTS / "room_service.py"), "--db", str(self.db),
             "serve", "--port", "0"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
        )
        self.addCleanup(self.stop, self.process)
        ready = self.process.stdout.readline()
        self.assertTrue(ready, self.process.stderr.read() if self.process.poll() is not None else "")
        self.url = f"http://127.0.0.1:{json.loads(ready)['port']}"

    def stop(self, process):
        if process.poll() is None:
            process.terminate()
        process.communicate(timeout=5)

    def request(self, path, token=None, body=None, status=200):
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        try:
            response = urlopen(Request(self.url + path, data=data, headers=headers), timeout=5)
        except HTTPError as error:
            response = error
        with response:
            self.assertEqual(response.code, status)
            return json.load(response)

    def test_two_clients_reconnect_and_recover_same_discussion(self):
        alice, bob = self.token("alice"), self.token("bob")
        self.assertEqual(self.request("/v1/history?inbox=1", bob), [])
        question = {"request": "question", "body": "Проверка прошла?", "to": "bob"}
        first = self.request("/v1/messages", alice, question)
        self.assertEqual(self.request("/v1/messages", alice, question), first)
        self.stop(self.process)
        self.start()
        self.assertEqual(self.request("/v1/history?inbox=1&after=0", bob), [first])
        self.assertEqual(self.request("/v1/history?inbox=1", alice), [])
        second = self.request("/v1/messages", bob, {
            "request": "reply", "body": "Да", "to": "alice", "reply_to": first["id"],
        })
        self.assertEqual(self.request(f"/v1/history?inbox=1&after={first['id']}", alice), [second])
        self.assertEqual(second["thread_id"], first["id"])
        self.assertEqual(self.request("/v1/history", bob), [first, second])

    def test_identity_scope_and_revocation_are_enforced(self):
        alice, bob, cara = (self.token(actor) for actor in ("alice", "bob", "cara"))
        self.request("/v1/history", status=401)
        self.request("/v1/messages", alice, {"request": "q", "body": "draft", "actor": "bob"}, status=400)
        draft = {"request": "q", "body": "pilot details", "projects": ["pilot"], "to": "bob"}
        self.request("/v1/messages", alice, draft, status=403)
        self.request("/v1/scope", alice, {"projects": ["pilot"]})
        posted = self.request("/v1/messages", alice, draft)
        self.assertEqual(self.request("/v1/history", cara), [])
        self.request("/v1/messages", cara, {"request": "r", "body": "reply", "reply_to": posted["id"]}, status=403)
        self.assertEqual(self.request("/v1/history?inbox=1", bob), [posted])
        self.cli("room.py", "revoke", "bob")
        self.cli("room.py", "grant", "bob", "--project", "pilot")
        self.request("/v1/history", bob, status=401)
        self.assertEqual(self.request("/v1/history", self.token("bob")), [posted])


if __name__ == "__main__":
    unittest.main()
