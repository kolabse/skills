#!/usr/bin/env python3
"""Command-line client for a private agent coordination room."""
import argparse
import ipaddress
import json
from pathlib import Path
import ssl
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPSHandler, HTTPRedirectHandler, ProxyHandler, Request, build_opener


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
    post = commands.add_parser("post")
    post.add_argument("request")
    post.add_argument("body")
    post.add_argument("--to")
    post.add_argument("--reply-to", type=int)
    post.add_argument("--project", action="append", default=[])
    return parser.parse_args(argv)


def connection(origin, ca):
    url = urlsplit(origin)
    if not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in {"", "/"}:
        raise ValueError("use the room service origin as --url")
    if url.scheme != "https":
        if url.scheme != "http" or not ipaddress.ip_address(url.hostname).is_loopback:
            raise ValueError("the room client requires HTTPS outside loopback")
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


def main():
    args = parse()
    try:
        print(json.dumps(request_room(args)))
    except HTTPError as error:
        print(http_error_message(error), file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, URLError) as error:
        print(f"Room request failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
