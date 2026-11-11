#!/usr/bin/env python3
"""Join a private room with a one-time invitation or renew a team session."""
import argparse
from getpass import getpass
import json
from pathlib import Path
import sys
import tempfile
from urllib.error import HTTPError
from urllib.request import Request

import room_client


def save(path, key, secret):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, encoding="utf-8", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump({key: secret}, stream)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--ca", type=Path)
    parser.add_argument("--credential-file", type=Path, required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    invites = parser.add_mutually_exclusive_group()
    invites.add_argument("--invite-file", type=Path)
    invites.add_argument("--new-invite", action="store_true")
    args = parser.parse_args(argv)
    try:
        paths = [args.credential_file, args.token_file]
        if args.invite_file:
            paths.append(args.invite_file)
        if len({path.resolve() for path in paths}) != len(paths):
            raise ValueError("credential, token and invitation paths must differ")
        origin, opener = room_client.connection(args.url, args.ca)
        join = args.invite_file or args.new_invite or not args.credential_file.is_file()
        if join:
            code = (json.loads(args.invite_file.read_text(encoding="utf-8"))["invite"]
                    if args.invite_file else getpass("One-time room invitation: ").strip())
            route, payload = "/v1/team/join", {"invite": code}
        else:
            credential = json.loads(args.credential_file.read_text(encoding="utf-8"))["credential"]
            route, payload = "/v1/team/renew", {"credential": credential}
        request = Request(origin + route, data=json.dumps(payload).encode("utf-8"),
                          headers={"Content-Type": "application/json"})
        with opener.open(request, timeout=15) as response:
            result = json.load(response)
        if join:
            save(args.credential_file, "credential", result["credential"])
        save(args.token_file, "token", result["token"])
        print(json.dumps({"status": "joined" if join else "renewed", "actor": result["actor"]}))
    except HTTPError as error:
        print(room_client.http_error_message(error), file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError) as error:
        print(f"Room sign-in failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
