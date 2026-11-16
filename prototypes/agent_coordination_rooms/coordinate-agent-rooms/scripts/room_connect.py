#!/usr/bin/env python3
"""Join an AICQ room by personal link or renew a locally saved room session."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request

import room
import room_client
from room_invitation import REVISION, SECRET, VERSION, parse_link, split_invitation
from room_join import save_document


def default_state():
    if os.name == "nt":
        return Path(os.environ["LOCALAPPDATA"]) / "Formika" / "AICQ" / "onboarding"
    return Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state") / "aicq"


def request_json(opener, url, *, payload=None, token=None):
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    with opener.open(Request(url, data=data, headers=headers), timeout=15) as response:
        if response.headers.get_content_type() != "application/json":
            raise ValueError("the link did not return an AICQ JSON response")
        result = json.loads(response.read(16 * 1024))
    if not isinstance(result, dict):
        raise ValueError("invalid AICQ response")
    return result


def read_identity(path, link):
    with path.open("rb") as stream:
        document = json.loads(stream.read(16 * 1024))
    if not isinstance(document, dict) or document.get("link") != link:
        raise ValueError("JSON does not match the invitation link")
    if type(document.get("version")) is not int or document["version"] != VERSION:
        raise ValueError("unsupported invitation or session version")
    participant(document)
    return document


def participant(document):
    if not isinstance(document.get("actor"), str) or not isinstance(document.get("projects"), list):
        raise ValueError("invalid participant or project list in JSON")
    try:
        room.identifier(document["actor"])
        if not all(isinstance(project, str) and room.identifier(project) for project in document["projects"]):
            raise ValueError("invalid project list in JSON")
    except argparse.ArgumentTypeError:
        raise ValueError("invalid participant or project ID in JSON") from None
    return document["actor"], sorted(set(document["projects"]))


def secret(document, key):
    value = document.get(key)
    if not isinstance(value, str) or SECRET.fullmatch(value) is None:
        raise ValueError(f"invalid {key} in AICQ JSON")
    return value


def session_path(link, state_dir=None):
    session_id = hashlib.sha256(link.encode("utf-8")).hexdigest()
    return (state_dir or default_state()) / (session_id + ".json")


def connect(args):
    link, invitation = split_invitation(args.link)
    room_url, name = parse_link(link)
    session_file = session_path(link, args.state_dir)
    state_dir = session_file.parent
    if invitation is not None and args.invite_file is not None:
        raise ValueError("use either a personal link or a legacy invitation file")
    if args.invite_file is not None and args.invite_file.resolve() == session_file.resolve():
        raise ValueError("invitation and session files must differ")
    state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Serialize renewals of the same locally saved session. Each renewal
    # invalidates the previous token on the server.
    with room.transaction(session_file.with_suffix(".lock"), True, initialize=True):
        new_invitation = invitation is not None or args.invite_file is not None
        if not new_invitation and not session_file.is_file():
            raise ValueError("no saved session for this room; ask for a personal invitation link")
        _, opener = room_client.connection(room_url, args.ca)
        manifest = request_json(opener, link)
        revision = manifest.pop("client_revision", None)
        if (type(manifest.get("version")) is not int or manifest != {"version": VERSION, "room": name}
                or (revision is not None and (not isinstance(revision, str) or not REVISION.fullmatch(revision)))):
            raise ValueError("unsupported AICQ invitation or room mismatch")
        if invitation is not None:
            result = request_json(opener, room_url + "/v1/team/join", payload={"invite": invitation})
            identity = result
            actor, projects = participant(identity)
        else:
            identity = read_identity(args.invite_file or session_file, link)
            actor, projects = participant(identity)
            if new_invitation:
                payload = {"invite": secret(identity, "invite"), "actor": actor, "projects": projects}
                result = request_json(opener, room_url + "/v1/team/join", payload=payload)
            else:
                payload = {"credential": secret(identity, "credential")}
                result = request_json(opener, room_url + "/v1/team/renew", payload=payload)
        if result.get("actor") != actor:
            raise ValueError("server returned an unexpected participant")
        token = secret(result, "token")
        credential = secret(result if new_invitation else identity, "credential")
        save_document(session_file, {
            "version": VERSION, "link": link, "actor": actor, "projects": projects,
            "token": token, "credential": credential,
        })
        access = request_json(opener, room_url + "/v1/access", token=token)
        if access.get("readable") != projects:
            raise ValueError("current project permissions differ from the invitation; contact the administrator")
        return {"status": "joined" if new_invitation else "renewed", "actor": actor,
                "room": name, "readable": projects, "link": link, "session_file": str(session_file)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    links = parser.add_mutually_exclusive_group(required=True)
    links.add_argument("--link", help="public, fragment-free invitation page")
    links.add_argument("--link-stdin", action="store_true", help="read the personal link from stdin")
    parser.add_argument("--invite-file", type=Path, help="legacy JSON invitation for the public link")
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--ca", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.link_stdin:
            args.link = sys.stdin.readline(4097).rstrip("\r\n")
            if len(args.link) > 4096:
                raise ValueError("invitation link is too long")
        elif "#" in args.link:
            raise ValueError("pass a personal invitation using --link-stdin")
        print(json.dumps(connect(args)))
    except HTTPError as error:
        reason = {
            401: "invitation or session was rejected; check with the administrator",
            404: "invitation route not found",
            429: "try again later",
        }.get(error.code, "room request failed")
        error.close()
        print(f"Room returned HTTP {error.code}: {reason}", file=sys.stderr)
        return 1
    except (ValueError, KeyError, OSError, sqlite3.Error, URLError) as error:
        print(f"Room connection failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
