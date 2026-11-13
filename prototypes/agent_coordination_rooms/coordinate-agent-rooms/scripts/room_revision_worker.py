#!/usr/bin/env python3
"""Poll an authenticated AICQ revision handoff and persist its next step."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from time import sleep
from urllib.error import HTTPError, URLError

import room
from room_client import connection
from room_connect import request_json
import room_revision


def verify(repository, job):
    revision = room_revision.require(job["revision"], room_revision.HEX40, "revision")
    path = room_revision.require(job["file"], room_revision.FILE, "file")
    command = ["git", "--no-replace-objects", "--no-lazy-fetch", "-C", str(repository), "cat-file"]
    kind = subprocess.check_output([*command, "-t", revision], stderr=subprocess.DEVNULL, timeout=10)
    if kind.strip() != b"commit":
        raise ValueError("revision is not a commit")
    object_name = revision + ":" + path
    size = int(subprocess.check_output([*command, "-s", object_name], stderr=subprocess.DEVNULL, timeout=10))
    if size > 1024 * 1024:
        raise ValueError("check file exceeds one MiB")
    contents = subprocess.check_output([*command, "blob", object_name], stderr=subprocess.DEVNULL, timeout=10)
    digest = hashlib.sha256(contents).hexdigest()
    if digest != job["expected_sha256"]:
        raise ValueError("file checksum did not match")
    return digest


def execute(state, url, repository, request):
    executed = 0
    jobs = request("pending", {})["jobs"]
    for job in jobs:
        with room.transaction(state, True, initialize=True) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS evidence (
                room TEXT NOT NULL, id TEXT NOT NULL, revision TEXT NOT NULL,
                file TEXT NOT NULL, digest TEXT, PRIMARY KEY(room, id)
            )""")
            identity = (url, job["id"])
            row = db.execute("SELECT revision, file, digest FROM evidence WHERE room=? AND id=?", identity).fetchone()
            if row is None:
                try:
                    digest = verify(repository, job)
                except (ValueError, subprocess.CalledProcessError):
                    digest = None
                db.execute("INSERT INTO evidence VALUES (?, ?, ?, ?, ?)",
                           (*identity, job["revision"], job["file"], digest))
                executed += 1
            else:
                digest = row["digest"]
                if ((row["revision"], row["file"]) != (job["revision"], job["file"])
                        or (digest is not None and digest != job["expected_sha256"])):
                    raise ValueError("cached evidence does not match this check")
        request("complete", {"id": job["id"], "revision": job["revision"], "sha256": digest})
    return {"executed": executed}


def advance(state, url, key, request, revision=None):
    if revision is not None:
        request("submit", {"id": key, "revision": revision})
    result = request("get", {"id": key})
    if result["status"] == "failed":
        return {"continued": False, "status": "failed"}
    if result["status"] != "ready":
        return None
    room_revision.require(result["sha256"], room_revision.HEX64, "evidence checksum")
    room_revision.require(result["revision"], room_revision.HEX40, "result revision")
    if result["id"] != key or (revision is not None and result["revision"] != revision):
        raise ValueError("result does not match this check")
    with room.transaction(state, True, initialize=True) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS continuations (
            room TEXT NOT NULL, id TEXT NOT NULL, revision TEXT NOT NULL,
            digest TEXT NOT NULL, PRIMARY KEY(room, id)
        )""")
        inserted = db.execute("INSERT OR IGNORE INTO continuations VALUES (?, ?, ?, ?)",
                              (url, key, result["revision"], result["sha256"])).rowcount
        row = db.execute("SELECT revision, digest FROM continuations WHERE room=? AND id=?", (url, key)).fetchone()
        if tuple(row) != (result["revision"], result["sha256"]):
            raise ValueError("result conflicts with the previously unlocked step")
    return {"continued": bool(inserted)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    setup = commands.add_parser("configure")
    setup.add_argument("--db", type=Path, required=True)
    for field in ("project", "requester", "executor", "file", "sha256"):
        setup.add_argument("--" + field, required=True)
    for command in (commands.add_parser("tick"), commands.add_parser("watch")):
        command.add_argument("--url", required=True)
        command.add_argument("--token-file", type=Path, required=True)
        command.add_argument("--state", type=Path, required=True)
        command.add_argument("--ca", type=Path)
        role = command.add_mutually_exclusive_group(required=True)
        role.add_argument("--repository", type=Path)
        role.add_argument("--job")
        command.add_argument("--revision")
    args = parser.parse_args(argv)
    try:
        if args.command == "configure":
            with room.transaction(args.db, True) as db:
                room_revision.configure(db, args)
            return 0
        if args.revision and not args.job:
            parser.error("--revision requires --job")
        if args.repository is not None and not args.repository.is_dir():
            raise ValueError("executor repository directory does not exist")
        url, opener = connection(args.url, args.ca)
        args.state.parent.mkdir(mode=0o700, parents=True, exist_ok=True)

        def request(action, payload):
            token = json.loads(args.token_file.read_text(encoding="utf-8"))["token"]
            return request_json(opener, url + "/v1/revision-check/" + action, payload=payload, token=token)

        while True:
            try:
                if args.repository:
                    result = execute(args.state, url, args.repository, request)
                else:
                    result = advance(args.state, url, args.job, request, args.revision)
                    if result is not None:
                        print(json.dumps(result), flush=True)
                        return int(result.get("status") == "failed")
                if args.command == "tick":
                    print(json.dumps(result if result is not None else {"continued": False}), flush=True)
                    return 0
                if args.repository and result["executed"]:
                    print(json.dumps(result), flush=True)
            except HTTPError as error:
                with error:
                    if args.command == "tick" or error.code not in {429, 500, 502, 503, 504}:
                        raise
            except (URLError, TimeoutError, ConnectionError):
                if args.command == "tick":
                    raise
            sleep(2)
    except KeyboardInterrupt:
        return 0
    except (ValueError, OSError, KeyError, sqlite3.Error, subprocess.SubprocessError, room.RoomError) as error:
        print(f"Revision handoff failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
