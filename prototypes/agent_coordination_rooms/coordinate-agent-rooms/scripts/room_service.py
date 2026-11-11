#!/usr/bin/env python3
"""Private-network room API for the #175 pilot."""
import argparse
from contextlib import closing, contextmanager
import hashlib
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
from pathlib import Path
import secrets
import sqlite3
import ssl
import sys
import time
from urllib.parse import parse_qs, urlsplit

import room


MAX_JSON = 16 * 1024
MAX_ID = 2**63 - 1
CREATE_TOKENS = """CREATE TABLE IF NOT EXISTS room_tokens (
    digest TEXT PRIMARY KEY,
    actor TEXT UNIQUE NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    expires_at INTEGER NOT NULL
)"""


class RequestError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


@contextmanager
def transaction(path, write):
    with closing(room.database(path, False)) as db, db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        yield db


def token_digest(token):
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def issue_token(db_path, actor, minutes):
    token = secrets.token_urlsafe(32)
    with transaction(db_path, True) as db:
        room.member(db, actor)
        db.execute(CREATE_TOKENS)
        db.execute(
            """INSERT INTO room_tokens (digest, actor, expires_at) VALUES (?, ?, ?)
            ON CONFLICT(actor) DO UPDATE SET digest = excluded.digest, expires_at = excluded.expires_at""",
            (token_digest(token), actor, int(time.time()) + minutes * 60),
        )
    return {"token": token}


def authenticated_actor(db, headers):
    values = headers.get_all("Authorization", [])
    if len(values) == 1:
        kind, _, token = values[0].partition(" ")
        if kind.lower() == "bearer" and token.isascii() and len(token) == 43:
            row = db.execute(
                """SELECT m.id FROM room_tokens t JOIN members m ON m.id = t.actor
                WHERE t.digest = ? AND t.expires_at > ?""",
                (token_digest(token), int(time.time())),
            ).fetchone()
            if row:
                return row["id"]
    raise RequestError(HTTPStatus.UNAUTHORIZED, "valid room token required")


def identifier(value):
    if not isinstance(value, str):
        raise ValueError("expected a participant, request or project ID")
    try:
        return room.identifier(value)
    except argparse.ArgumentTypeError as error:
        raise ValueError(str(error)) from error


def project_ids(value):
    if not isinstance(value, list) or len(value) > 64:
        raise ValueError("projects must be a list of at most 64 IDs")
    return [identifier(item) for item in value]


def post_arguments(data):
    if not {"request", "body"} <= data.keys() <= {"request", "body", "projects", "to", "reply_to"}:
        raise ValueError("invalid message fields")
    body = data["body"]
    if not isinstance(body, str) or not body.strip() or len(body) > 4000:
        raise ValueError("body must contain 1 to 4000 characters")
    body.encode("utf-8")  # Reject unpaired surrogate escapes before SQLite.
    reply_to = data.get("reply_to")
    if reply_to is not None and (type(reply_to) is not int or not 1 <= reply_to <= MAX_ID):
        raise ValueError("reply_to must be a valid message ID")
    recipient = data.get("to")
    return {
        "request": identifier(data["request"]), "body": body,
        "project": project_ids(data.get("projects", [])),
        "to": identifier(recipient) if recipient is not None else None, "reply_to": reply_to,
    }


def history_arguments(query):
    params = parse_qs(query, keep_blank_values=True, strict_parsing=True, max_num_fields=3)
    if params.keys() - {"after", "limit", "inbox"} or any(len(values) != 1 for values in params.values()):
        raise ValueError("invalid history query")
    after = int(params.get("after", ["0"])[0])
    limit = int(params.get("limit", ["100"])[0])
    inbox = params.get("inbox", ["0"])[0]
    if not 0 <= after <= MAX_ID or not 1 <= limit <= 1000 or inbox not in {"0", "1"}:
        raise ValueError("invalid cursor, limit or inbox flag")
    return {"after": after, "limit": limit, "inbox": inbox == "1"}


class RoomHandler(BaseHTTPRequestHandler):
    def setup(self):
        self.request.settimeout(10)
        super().setup()

    def log_message(self, format, *args):
        # Room messages and Authorization headers are never written to the HTTP log.
        return

    def send_json(self, status, result):
        body = json.dumps(result, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        if self.headers.get_content_type() != "application/json":
            raise RequestError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "application/json required")
        lengths = self.headers.get_all("Content-Length", [])
        if self.headers.get("Transfer-Encoding") is not None or len(lengths) != 1:
            raise ValueError("exactly one Content-Length is required")
        size = int(lengths[0])
        if size <= 0:
            raise ValueError("empty JSON body")
        if size > MAX_JSON:
            raise RequestError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "JSON body is too large")
        data = json.loads(self.rfile.read(size).decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("expected a JSON object")
        return data

    def dispatch(self):
        try:
            result = self.route()
            self.send_json(HTTPStatus.OK, result)
        except RequestError as error:
            self.send_json(error.status, {"error": str(error)})
        except ValueError as error:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        except room.RoomError as error:
            self.send_json(HTTPStatus.FORBIDDEN, {"error": str(error)})
        except sqlite3.Error:
            self.send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "room database unavailable"})
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass

    do_GET = do_POST = dispatch

    def route(self):
        url = urlsplit(self.path)
        route = self.command, url.path
        if route == ("GET", "/health") and not url.query:
            return {"status": "ok"}
        handler = {
            ("GET", "/v1/history"): room.history,
            ("GET", "/v1/access"): room.access,
            ("POST", "/v1/messages"): room.post,
            ("POST", "/v1/scope"): room.scope,
        }.get(route)
        if handler is None:
            raise RequestError(HTTPStatus.NOT_FOUND, "route not found")
        if handler is not room.history and url.query:
            raise ValueError("unexpected query parameters")
        arguments = {}
        if handler is room.history:
            arguments = history_arguments(url.query)
        if handler is room.post:
            arguments = post_arguments(self.read_json())
        if handler is room.scope:
            payload = self.read_json()
            if payload.keys() != {"projects"}:
                raise ValueError("scope requires projects")
            arguments = {"project": project_ids(payload["projects"])}
        with transaction(self.server.db_path, self.command == "POST") as db:
            actor = authenticated_actor(db, self.headers)
            return handler(db, argparse.Namespace(actor=actor, **arguments))


class RoomServer(ThreadingHTTPServer):
    def __init__(self, address, db_path, tls):
        self.db_path = db_path
        self.tls = tls
        super().__init__(address, RoomHandler)

    def get_request(self):
        sock, address = super().get_request()
        if self.tls is not None:
            try:
                sock = self.tls.wrap_socket(sock, server_side=True, do_handshake_on_connect=False)
            except OSError:
                sock.close()
                raise
        return sock, address


def serve(args):
    address = ipaddress.IPv4Address(args.bind)
    if bool(args.cert) != bool(args.key) or (not address.is_loopback and not args.cert):
        raise ValueError("a TLS certificate and key are required for a network bind")
    tls = None
    if args.cert:
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.minimum_version = ssl.TLSVersion.TLSv1_2
        tls.load_cert_chain(args.cert, args.key)
    with transaction(args.db, True) as db:
        db.execute("SELECT 1 FROM members LIMIT 1")
        db.execute(CREATE_TOKENS)
    with RoomServer((str(address), args.port), args.db, tls) as server:
        print(json.dumps({"port": server.server_port, "tls": tls is not None}), flush=True)
        server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    server = commands.add_parser("serve")
    server.add_argument("--bind", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8766)
    server.add_argument("--cert", type=Path)
    server.add_argument("--key", type=Path)
    token = commands.add_parser("issue-token")
    token.add_argument("actor", type=room.identifier)
    token.add_argument("--minutes", type=int, default=60)
    args = parser.parse_args()
    try:
        if args.command == "serve":
            serve(args)
        else:
            if not 1 <= args.minutes <= 1440:
                raise ValueError("token lifetime must be between 1 and 1440 minutes")
            print(json.dumps(issue_token(args.db, args.actor, args.minutes)))
    except KeyboardInterrupt:
        return 0
    except (ValueError, OSError, sqlite3.Error, room.RoomError) as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
