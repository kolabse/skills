"""Authenticated revision handoff through a real room and two worker processes."""
from argparse import Namespace
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from urllib.error import HTTPError

from test_agent_coordination_project_rooms import SCRIPTS
import room
from room_connect import request_json
from room_client import connection
from room_registry import RoomRegistry
from room_service import RoomServer
import room_team


class RevisionHandoffTests(unittest.TestCase):
    def test_only_assigned_exact_revision_unlocks_once_and_recovers_after_restart(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "portal"
            repo.mkdir()

            def git(*args):
                return subprocess.check_output(["git", "-C", str(repo), *args], timeout=10).decode().strip()

            git("init", "-q")
            (repo / "marker.txt").write_bytes(b"ready")
            git("add", "marker.txt")
            git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture")
            revision = git("rev-parse", "HEAD")
            digest = hashlib.sha256(b"ready").hexdigest()
            registry = RoomRegistry(root / "rooms")
            registry.create("pilot", Namespace(project=["portal"]))
            with room.transaction(registry.lookup("pilot"), True) as db:
                tokens = {}
                for actor in ("portal-agent", "infra-agent", "observer"):
                    room.grant(db, Namespace(actor=actor, project=["portal"]))
                    tokens[actor] = room.mint_token(db, actor, 60, room_team.MODE)

            with RoomServer(("127.0.0.1", 0), None, None, True, registry=registry) as server:
                thread = Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    url = f"http://127.0.0.1:{server.server_port}/rooms/pilot"
                    _, opener = connection(url, None)

                    def request(actor, action, payload):
                        return request_json(opener, url + "/v1/revision-check/" + action,
                                            payload=payload, token=tokens[actor])

                    def cli(*args):
                        return subprocess.run([sys.executable, str(SCRIPTS / "room_revision_worker.py"), *map(str, args)],
                                              capture_output=True, text=True, timeout=15)

                    job = {"id": "check-1", "revision": revision}
                    with self.assertRaises(HTTPError) as unconfigured:
                        request("portal-agent", "submit", job)
                    self.assertEqual(unconfigured.exception.code, 404)

                    result = cli("configure", "--db", registry.lookup("pilot"), "--project", "portal",
                                 "--requester", "portal-agent", "--executor", "infra-agent",
                                 "--file", "marker.txt", "--sha256", digest)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    with self.assertRaises(HTTPError) as unauthorized:
                        request("observer", "submit", job)
                    self.assertEqual(unauthorized.exception.code, 403)
                    self.assertEqual(request("portal-agent", "submit", job)["status"], "pending")
                    self.assertEqual(request("portal-agent", "submit", job)["status"], "pending")
                    with self.assertRaises(HTTPError) as conflicting:
                        request("portal-agent", "submit", {**job, "revision": "f" * 40})
                    self.assertEqual(conflicting.exception.code, 409)
                    evidence = {**job, "sha256": digest}
                    with self.assertRaises(HTTPError) as wrong_actor:
                        request("observer", "complete", evidence)
                    self.assertEqual(wrong_actor.exception.code, 403)
                    with self.assertRaises(HTTPError) as wrong_revision:
                        request("infra-agent", "complete", {**evidence, "revision": "f" * 40})
                    self.assertEqual(wrong_revision.exception.code, 409)
                    with self.assertRaises(HTTPError) as wrong_evidence:
                        request("infra-agent", "complete", {**evidence, "sha256": "0" * 64})
                    self.assertEqual(wrong_evidence.exception.code, 409)
                    self.assertEqual(request("portal-agent", "get", {"id": job["id"]})["status"], "pending")

                    for actor, token in tokens.items():
                        (root / actor).write_text(json.dumps({"token": token}), encoding="utf-8")

                    def tick(actor, *args):
                        result = cli("tick", "--url", url, "--token-file", root / actor, *args)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        return json.loads(result.stdout)

                    with ThreadPoolExecutor(max_workers=2) as pool:
                        outcomes = list(pool.map(lambda _: tick("infra-agent", "--repository", repo,
                                                              "--state", root / "infra.sqlite"), range(2)))
                    self.assertEqual(sum(item["executed"] for item in outcomes), 1)
                    self.assertEqual(tick("infra-agent", "--repository", repo,
                                          "--state", root / "infra.sqlite")["executed"], 0)
                    published = request("portal-agent", "get", {"id": job["id"]})
                    self.assertEqual((published["status"], published["revision"], published["sha256"]),
                                     ("ready", revision, digest))
                    self.assertEqual(request("infra-agent", "complete", evidence), published)
                    self.assertEqual(tick("portal-agent", "--job", job["id"], "--state", root / "portal.sqlite"),
                                     {"continued": True})
                    self.assertEqual(tick("portal-agent", "--job", job["id"], "--state", root / "portal.sqlite"),
                                     {"continued": False})
                    with room.transaction(root / "portal.sqlite", False) as db:
                        self.assertEqual(db.execute("SELECT COUNT(*) FROM continuations").fetchone()[0], 1)
                    with room.transaction(registry.lookup("pilot"), False) as db:
                        self.assertEqual(db.execute("SELECT COUNT(*) FROM revision_checks").fetchone()[0], 1)
                    request("portal-agent", "submit", {"id": "missing", "revision": "e" * 40})
                    self.assertEqual(tick("infra-agent", "--repository", repo,
                                          "--state", root / "infra.sqlite"), {"executed": 1})
                    self.assertEqual(request("portal-agent", "get", {"id": "missing"})["status"], "failed")
                    failed = cli("watch", "--url", url, "--token-file", root / "portal-agent",
                                 "--state", root / "portal.sqlite", "--job", "missing")
                    self.assertEqual(failed.returncode, 1, failed.stderr)
                    self.assertEqual(json.loads(failed.stdout), {"continued": False, "status": "failed"})
                    common = [sys.executable, str(SCRIPTS / "room_revision_worker.py"), "watch", "--url", url]
                    infra = [*common, "--token-file", str(root / "infra-agent"),
                             "--state", str(root / "infra.sqlite"), "--repository", str(repo)]
                    portal = [*common, "--token-file", str(root / "portal-agent"),
                              "--state", str(root / "portal.sqlite"), "--job", "automatic-1",
                              "--revision", revision]
                    with subprocess.Popen(infra, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                          text=True) as executor:
                        try:
                            first = subprocess.run(portal, capture_output=True, text=True, timeout=15)
                            self.assertEqual(first.returncode, 0, first.stderr)
                            self.assertEqual(json.loads(first.stdout), {"continued": True})
                            retry = subprocess.run(portal, capture_output=True, text=True, timeout=8)
                            self.assertEqual(retry.returncode, 0, retry.stderr)
                            self.assertEqual(json.loads(retry.stdout), {"continued": False})
                        finally:
                            if executor.poll() is None:
                                executor.terminate()
                            output, errors = executor.communicate(timeout=5)
                    self.assertEqual([json.loads(line) for line in output.splitlines()],
                                     [{"executed": 1}], errors)
                finally:
                    server.shutdown()
                    thread.join(5)
