"""A room-scoped handoff for checking a file at an exact Git revision."""
import re
from pathlib import PurePosixPath

import room

HEX40 = re.compile(r"[0-9a-f]{40}")
HEX64 = re.compile(r"[0-9a-f]{64}")
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
FILE = re.compile(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*")
ACTIONS = {"submit", "get", "pending", "complete"}


class HandoffError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def require(value, pattern, field):
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError(f"invalid {field}")
    return value


def configure(db, args):
    project = require(args.project, IDENTIFIER, "project")
    requester = require(args.requester, IDENTIFIER, "requester")
    executor = require(args.executor, IDENTIFIER, "executor")
    path = require(args.file, FILE, "file")
    digest = require(args.sha256, HEX64, "sha256")
    if requester == executor or any(part in {".", ".."} for part in path.split("/")):
        raise ValueError("use two distinct actors and a repository-relative file")
    if len(PurePosixPath(path).parts) > 32 or len(path) > 512:
        raise ValueError("file path is too long")
    for actor in (requester, executor):
        ensure_project(db, actor, project)
    db.execute("""CREATE TABLE IF NOT EXISTS revision_check_policy (
        singleton INTEGER PRIMARY KEY CHECK(singleton=1), project TEXT NOT NULL,
        requester TEXT NOT NULL, executor TEXT NOT NULL, file TEXT NOT NULL, sha256 TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS revision_checks (
        id TEXT PRIMARY KEY, revision TEXT NOT NULL, sha256 TEXT,
        failed INTEGER NOT NULL DEFAULT 0 CHECK(failed IN (0, 1) AND (failed=0 OR sha256 IS NULL))
    )""")
    policy = (project, requester, executor, path, digest)
    db.execute("INSERT OR IGNORE INTO revision_check_policy VALUES (1, ?, ?, ?, ?, ?)", policy)
    current = db.execute("SELECT project, requester, executor, file, sha256 FROM revision_check_policy").fetchone()
    if tuple(current) != policy:
        raise ValueError("this room already has a different revision check policy")


def ensure_project(db, actor, project):
    readable, _ = room.member(db, actor)
    if project not in readable:
        raise room.RoomError("project access is required")


def result(row):
    status = "failed" if row["failed"] else "ready" if row["sha256"] is not None else "pending"
    return {"id": row["id"], "revision": row["revision"], "sha256": row["sha256"], "status": status}


def handle(db, actor, action, data):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='revision_check_policy' AND type='table'").fetchone():
        raise HandoffError(404, "revision checking is not configured in this room")
    policy = db.execute("SELECT * FROM revision_check_policy WHERE singleton=1").fetchone()
    role = "requester" if action in {"submit", "get"} else "executor"
    if actor != policy[role]:
        raise HandoffError(403, "actor is not assigned to this operation")
    ensure_project(db, actor, policy["project"])
    if action == "pending":
        if data:
            raise ValueError("pending expects an empty object")
        jobs = db.execute("SELECT * FROM revision_checks WHERE sha256 IS NULL AND failed=0 ORDER BY rowid LIMIT 32")
        return {"jobs": [{**result(job), "file": policy["file"], "expected_sha256": policy["sha256"]}
                         for job in jobs]}

    fields = {"id"} if action == "get" else {"id", "revision"}
    if action == "complete":
        fields.add("sha256")
    if data.keys() != fields:
        raise ValueError("invalid revision check fields")
    key = require(data["id"], IDENTIFIER, "job ID")
    revision = require(data["revision"], HEX40, "revision") if "revision" in data else None
    if action == "submit":
        ensure_project(db, policy["executor"], policy["project"])
        db.execute("INSERT OR IGNORE INTO revision_checks (id, revision) VALUES (?, ?)", (key, revision))
    row = db.execute("SELECT * FROM revision_checks WHERE id=?", (key,)).fetchone()
    if row is None:
        raise HandoffError(404, "revision check does not exist")
    if revision is not None and row["revision"] != revision:
        raise HandoffError(409, "revision does not match the registered check")
    if action == "complete":
        digest = data["sha256"]
        if digest is not None and require(digest, HEX64, "sha256") != policy["sha256"]:
            raise HandoffError(409, "check evidence does not match policy")
        if (row["failed"] or row["sha256"] is not None) and digest != row["sha256"]:
            raise HandoffError(409, "check already has a different result")
        db.execute("UPDATE revision_checks SET sha256=?, failed=? WHERE id=? AND sha256 IS NULL AND failed=0",
                   (digest, int(digest is None), key))
        row = db.execute("SELECT * FROM revision_checks WHERE id=?", (key,)).fetchone()
    return result(row)
