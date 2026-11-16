#!/usr/bin/env python3
"""Administer project rooms locally on the room server."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

import room
from room_client import validate_url
from room_invitation import VERSION, parse_link
from room_registry import RoomRegistry
import room_team


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rooms-dir", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("room")
    create.add_argument("--project", type=room.identifier, action="append", required=True)
    commands.add_parser("list")
    grant = commands.add_parser("grant")
    revoke = commands.add_parser("revoke")
    invite = commands.add_parser("invite")
    for command in (grant, revoke, invite):
        command.add_argument("room")
        command.add_argument("actor", type=room.identifier)
    grant.add_argument("--project", type=room.identifier, action="append", default=[])
    invite.add_argument("--minutes", type=int, default=30)
    formats = invite.add_mutually_exclusive_group()
    formats.add_argument("--origin", help="issue a personal link for this HTTPS service origin")
    formats.add_argument("--link", help="produce a legacy JSON bundle for this exact invitation page")
    args = parser.parse_args(argv)
    registry = RoomRegistry(args.rooms_dir)
    try:
        if args.command == "create":
            result = registry.create(args.room, args)
        elif args.command == "list":
            result = registry.names()
        else:
            with room.transaction(registry.lookup(args.room), True) as db:
                if args.command == "invite":
                    result = {}
                    if args.link is not None:
                        _, name = parse_link(args.link)
                        if name != args.room:
                            raise ValueError("invitation link must identify the selected room")
                        readable, _ = room.member(db, args.actor)
                        result = {"version": VERSION, "link": args.link, "actor": args.actor,
                                  "projects": sorted(readable)}
                    if args.origin is not None:
                        origin = validate_url(args.origin)
                        if origin.path not in {"", "/"}:
                            raise ValueError("--origin must be the service origin")
                        manifest = f"{args.origin.rstrip('/')}/rooms/{args.room}/invite"
                        parse_link(manifest)
                        token = room_team.issue_invite(db, args.actor, args.minutes)
                        result = {"link": f"{manifest}#{token}"}
                    else:
                        result["invite"] = room_team.issue_invite(db, args.actor, args.minutes)
                else:
                    action = room.grant if args.command == "grant" else room.revoke
                    result = action(db, args)
        print(json.dumps(result))
    except (OSError, ValueError, sqlite3.Error, room.RoomError) as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
