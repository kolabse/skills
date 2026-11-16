#!/usr/bin/env python3
"""Command-line client for a private agent coordination room."""
import argparse
import hashlib
import ipaddress
import json
from pathlib import Path
import sqlite3
import ssl
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPSHandler, HTTPRedirectHandler, ProxyHandler, Request, build_opener

from room_registry import ROOM_URL_PATH


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def parse(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--ca", type=Path)
    parser.add_argument("--token-file", required=True, type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("access")
    scope = commands.add_parser("scope")
    scope.add_argument("--project", action="append", default=[])
    history = commands.add_parser("history")
    history.add_argument("--inbox", action="store_true")
    history.add_argument("--after", type=int, default=0)
    commands.add_parser("inbox")
    ack = commands.add_parser("ack-inbox")
    ack.add_argument("id", type=int)
    post = commands.add_parser("post")
    ask = commands.add_parser("ask")
    for command in (post, ask):
        command.add_argument("request")
        command.add_argument("body")
        command.add_argument("--to", required=command is ask)
        command.add_argument("--project", action="append", default=[])
    post.add_argument("--reply-to", type=int)
    ask.set_defaults(reply_to=None)
    return parser.parse_args(argv)


def validate_url(origin):
    url = urlsplit(origin)
    if (not url.hostname or url.username is not None or url.password is not None
            or "?" in origin or "#" in origin
            or (url.path not in {"", "/"} and not ROOM_URL_PATH.fullmatch(url.path))):
        raise ValueError("use the service origin or /rooms/<room-id> as --url")
    if url.scheme != "https":
        if url.scheme != "http" or not ipaddress.ip_address(url.hostname).is_loopback:
            raise ValueError("the room client requires HTTPS outside loopback")
    return url


def connection(origin, ca):
    validate_url(origin)
    context = ssl.create_default_context(cafile=str(ca) if ca else None)
    opener = build_opener(ProxyHandler({}), NoRedirect(), HTTPSHandler(context=context))
    return origin.rstrip("/"), opener


def request_room(args):
    origin, opener = connection(args.url, args.ca)
    token = json.loads(args.token_file.read_text(encoding="utf-8"))["token"]
    path, payload = "/v1/access", None
    if args.command == "scope":
        path, payload = "/v1/scope", {"projects": args.project}
    if args.command == "history":
        path = "/v1/history?" + urlencode({"inbox": int(args.inbox), "after": args.after})
    if args.command == "post":
        path, payload = "/v1/messages", {
            "request": args.request, "body": args.body, "to": args.to,
            "reply_to": args.reply_to, "projects": args.project,
        }
    headers = {"Authorization": f"Bearer {token}"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    with opener.open(Request(origin + path, data=data, headers=headers), timeout=10) as response:
        return json.load(response)


def http_error_message(error):
    with error:
        try:
            detail = json.load(error).get("error")
        except (ValueError, AttributeError):
            detail = None
    return f"Room returned HTTP {error.code}" + (f": {detail}" if detail else "")


def managed_inbox(args):
    # Import here because the onboarding CLI also uses the HTTP client.
    import room
    from room_join import save_document

    identity = json.loads(args.token_file.read_text(encoding="utf-8"))
    origin = args.url.rstrip("/")
    actor = identity.get("actor")
    if not actor or identity.get("link") != origin + "/invite":
        raise ValueError("use the saved onboarding session for this room")
    key = hashlib.sha256(json.dumps([origin, actor]).encode("utf-8")).hexdigest()
    checkpoint = args.token_file.parent / f"inbox-{key}.json"

    with room.transaction(checkpoint.with_suffix(".lock"), True, initialize=True):
        after = json.loads(checkpoint.read_text(encoding="utf-8"))["after"] if checkpoint.exists() else 0
        history = argparse.Namespace(**{**vars(args), "command": "history", "inbox": True, "after": after})
        messages = request_room(history)
        if args.command == "inbox":
            return messages, 0
        if args.command == "ask":
            if messages:
                return {"status": "pending_inbox", "messages": messages}, 2
            return request_room(argparse.Namespace(**{**vars(args), "command": "post"})), 0
        if args.id != after:
            if not any(item["id"] == args.id for item in messages):
                raise ValueError("acknowledge only through an ID in the current inbox page")
            save_document(checkpoint, {"after": args.id})
        return {"after": args.id}, 0


def main():
    args = parse()
    try:
        if args.command in {"inbox", "ack-inbox", "ask"}:
            result, status = managed_inbox(args)
            print(json.dumps(result))
            return status
        print(json.dumps(request_room(args)))
    except HTTPError as error:
        print(http_error_message(error), file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, URLError, sqlite3.Error) as error:
        print(f"Room request failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
