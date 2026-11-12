#!/usr/bin/env python3
"""Single-workstation prototype for the agent coordination room in #175."""
import argparse
from contextlib import closing, contextmanager
import hashlib
import json
from pathlib import Path
import re
import secrets
import sqlite3
import sys
import time


SCHEMA = (
    "CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY)",
    """CREATE TABLE IF NOT EXISTS members (
        id TEXT PRIMARY KEY,
        readable TEXT NOT NULL,
        publishable TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY,
        actor TEXT NOT NULL,
        request TEXT NOT NULL,
        body TEXT NOT NULL,
        projects TEXT NOT NULL,
        recipient TEXT,
        reply_to INTEGER REFERENCES messages(id),
        thread_id INTEGER REFERENCES messages(id),
        UNIQUE (actor, request)
    )""",
)


TOKEN_TABLE = """CREATE TABLE IF NOT EXISTS room_tokens (
    digest TEXT PRIMARY KEY,
    actor TEXT UNIQUE NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    expires_at INTEGER NOT NULL,
    auth_mode TEXT
)"""


class RoomError(Exception):
    pass


def database(path, initialize):
    if initialize:
        return sqlite3.connect(path)
    return sqlite3.connect(path.resolve().as_uri() + "?mode=rw", uri=True)


@contextmanager
def transaction(path, write, *, initialize=False):
    with closing(database(path, initialize)) as db, db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        yield db


def install_tokens(db):
    db.execute(TOKEN_TABLE)
    if not any(column["name"] == "auth_mode" for column in db.execute("PRAGMA table_info(room_tokens)")):
        db.execute("ALTER TABLE room_tokens ADD COLUMN auth_mode TEXT")


def membership_event(db, actor, event):
    db.execute("""CREATE TABLE IF NOT EXISTS room_membership_audit (
        id INTEGER PRIMARY KEY, actor TEXT NOT NULL, event TEXT NOT NULL, occurred_at INTEGER NOT NULL
    )""")
    db.execute("INSERT INTO room_membership_audit (actor, event, occurred_at) VALUES (?, ?, ?)",
               (actor, event, int(time.time())))


def token_digest(token):
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def mint_token(db, actor, minutes, auth_mode=None):
    token = secrets.token_urlsafe(32)
    db.execute(
        """INSERT INTO room_tokens (digest, actor, expires_at, auth_mode) VALUES (?, ?, ?, ?)
        ON CONFLICT(actor) DO UPDATE SET digest = excluded.digest,
            expires_at = excluded.expires_at, auth_mode = excluded.auth_mode""",
        (token_digest(token), actor, int(time.time()) + minutes * 60, auth_mode),
    )
    return token


def init(db, args):
    for statement in SCHEMA:
        db.execute(statement)
    db.executemany("INSERT OR IGNORE INTO projects VALUES (?)",
                   ((project,) for project in args.project))
    return {"initialized": True}


def member(db, actor):
    row = db.execute("SELECT * FROM members WHERE id = ?", (actor,)).fetchone()
    if row is None:
        raise RoomError("not a room member")
    selection = row["publishable"]
    return set(json.loads(row["readable"])), None if selection is None else set(json.loads(selection))


def grant(db, args):
    projects = set(args.project)
    allowed = {row["id"] for row in db.execute("SELECT id FROM projects")}
    if not projects <= allowed:
        raise RoomError("project is not configured for this room")
    try:
        _, existing_scope = member(db, args.actor)
    except RoomError:
        existing_scope = None
    selection = None if existing_scope is None else json.dumps(sorted(projects & existing_scope))
    db.execute(
        """INSERT INTO members VALUES (?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET readable = excluded.readable,
        publishable = excluded.publishable""",
        (args.actor, json.dumps(sorted(projects)), selection),
    )
    return {"member": args.actor}


def revoke(db, args):
    if db.execute("DELETE FROM members WHERE id = ?", (args.actor,)).rowcount:
        membership_event(db, args.actor, "revoked")
        if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='room_team_retired'").fetchone():
            db.execute("INSERT OR IGNORE INTO room_team_retired VALUES (?)", (args.actor,))
    return {"revoked": args.actor}


def access(db, args):
    readable, publishable = member(db, args.actor)
    return {
        "readable": sorted(readable),
        "publishable": sorted(publishable or ()),
        "scope_selected": publishable is not None,
    }


def scope(db, args):
    readable, _ = member(db, args.actor)
    projects = set(args.project)
    if not projects <= readable:
        raise RoomError("publication scope exceeds project access")
    db.execute("UPDATE members SET publishable = ? WHERE id = ?",
               (json.dumps(sorted(projects)), args.actor))
    return access(db, args)


def message(row):
    return {
        "id": row["id"],
        "actor": row["actor"],
        "body": row["body"],
        "projects": json.loads(row["projects"]),
        "recipient": row["recipient"],
        "reply_to": row["reply_to"],
        "thread_id": row["thread_id"] or row["id"],
    }


def post(db, args):
    readable, publishable = member(db, args.actor)
    if not args.body.strip():
        raise RoomError("message body is empty")
    projects = set(args.project)
    thread_id = None
    if args.reply_to is not None:
        parent = db.execute("SELECT * FROM messages WHERE id = ?", (args.reply_to,)).fetchone()
        if parent is None or not set(json.loads(parent["projects"])) <= readable:
            raise RoomError("message unavailable")
        projects.update(json.loads(parent["projects"]))
        thread_id = parent["thread_id"] or parent["id"]
    if not projects <= (publishable or set()):
        raise RoomError("message projects exceed publication scope")
    if args.to is not None:
        recipient = db.execute("SELECT readable FROM members WHERE id = ?", (args.to,)).fetchone()
        if recipient is None or not projects <= set(json.loads(recipient["readable"])):
            raise RoomError("recipient cannot read this message")

    fields = (args.body, json.dumps(sorted(projects)), args.to, args.reply_to, thread_id)
    previous = db.execute("SELECT * FROM messages WHERE actor = ? AND request = ?",
                          (args.actor, args.request)).fetchone()
    if previous is not None:
        if tuple(previous[key] for key in ("body", "projects", "recipient", "reply_to", "thread_id")) != fields:
            raise RoomError("request ID already used for a different message")
        return message(previous)

    inserted = db.execute(
        """INSERT INTO messages (actor, request, body, projects, recipient, reply_to, thread_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (args.actor, args.request, *fields),
    )
    return message(db.execute("SELECT * FROM messages WHERE id = ?", (inserted.lastrowid,)).fetchone())


def history(db, args):
    readable, _ = member(db, args.actor)
    if args.after < 0 or not 1 <= args.limit <= 1000:
        raise RoomError("history requires a nonnegative cursor and a limit from 1 to 1000")
    rows = db.execute(
        """SELECT * FROM messages AS m
        WHERE m.id > :after AND (:all_messages OR m.recipient = :actor)
        AND NOT EXISTS (
            SELECT value FROM json_each(m.projects)
            EXCEPT SELECT value FROM json_each(:readable)
        )
        ORDER BY m.id LIMIT :limit""",
        {"after": args.after, "all_messages": not args.inbox, "actor": args.actor,
         "readable": json.dumps(sorted(readable)), "limit": args.limit},
    )
    return [message(row) for row in rows]


def identifier(value):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value):
        raise argparse.ArgumentTypeError("use a stable ID of 1 to 128 ASCII letters, digits, dots, underscores or hyphens")
    return value


def parse(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    for handler in (init, grant, revoke, access, scope, post, history):
        command = commands.add_parser(handler.__name__)
        command.set_defaults(handler=handler)
        if handler is not init:
            command.add_argument("actor", type=identifier)
        if handler in (init, grant, scope, post):
            command.add_argument("--project", action="append", default=[], type=identifier)
        if handler is post:
            command.add_argument("request", type=identifier)
            command.add_argument("body")
            command.add_argument("--to", type=identifier)
            command.add_argument("--reply-to", type=int)
        if handler is history:
            command.add_argument("--after", type=int, default=0)
            command.add_argument("--limit", type=int, default=100)
            command.add_argument("--inbox", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse(argv)
    try:
        write = args.command not in {"access", "history"}
        with transaction(args.db, write, initialize=args.command == "init") as db:
            result = args.handler(db, args)
        print(json.dumps(result))
    except (RoomError, sqlite3.Error) as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
