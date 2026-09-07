"""Explicit, local advisory bookkeeping. Report commands never read this file."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile


MAX_BYTES = 65536
MAX_ENTRIES = 128
NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
STATES = (
    "eligible", "awaiting-collection", "collection-consented", "collection-declined",
    "drafted", "awaiting-submission", "submission-consented", "submission-declined",
    "submitted", "submission-unknown",
)
ADVISORY = (
    "Advisory bookkeeping only: states never replace fresh per-report collection "
    "consent or separate submission consent. No report command reads this ledger."
)


class SessionError(Exception):
    """Only fixed, non-identifying messages may cross this boundary."""


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise SessionError("Invalid session command arguments.")


def validate(value):
    if (not isinstance(value, dict) or set(value) != {"schema_version", "entries"}
            or type(value["schema_version"]) is not int or value["schema_version"] != 1
            or not isinstance(value["entries"], list)
            or not 1 <= len(value["entries"]) <= MAX_ENTRIES):
        raise SessionError("Invalid session ledger.")
    for entry in value["entries"]:
        if (not isinstance(entry, dict) or set(entry) != {"skill", "state"}
                or not isinstance(entry["skill"], str)
                or not 1 <= len(entry["skill"]) <= 128
                or not NAME.fullmatch(entry["skill"])
                or not isinstance(entry["state"], str) or entry["state"] not in STATES):
            raise SessionError("Invalid session ledger.")
    return value


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise SessionError("Invalid session ledger.")
        value[key] = item
    return value


def location(ledger, project_root):
    project = project_root.resolve(strict=True)
    path = ledger.resolve()
    if not project.is_dir() or path.is_relative_to(project):
        raise SessionError("Session ledger must be outside the declared project.")
    return path


def read(path):
    with path.open("rb") as handle:
        raw = handle.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise SessionError("Session ledger exceeds the size limit.")
    return validate(json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object))


def write(path, value, *, create):
    raw = (json.dumps(validate(value), indent=2, ensure_ascii=True) + "\n").encode("utf-8")
    if len(raw) > MAX_BYTES:
        raise SessionError("Session ledger exceeds the size limit.")
    # Unique sibling temporary files prevent partial writes. Linking on create
    # publishes atomically and fails if any destination already exists.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, prefix=".feedback-session-", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        if create:
            os.link(temporary, path)
        else:
            os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def parser():
    result = Parser(description=ADVISORY)
    commands = result.add_subparsers(dest="command", required=True)
    for command in ("create", "show", "set", "append"):
        child = commands.add_parser(command, description=ADVISORY)
        child.add_argument("--ledger", type=Path, required=True)
        child.add_argument("--project-root", type=Path, required=True)
        if command in ("create", "append"):
            child.add_argument("--skill", action="append", required=True)
        if command == "set":
            child.add_argument("--entry", type=int, required=True)
            child.add_argument("--state", choices=STATES, required=True)
    return result


def main(argv: list[str] | None = None) -> int:
    try:
        args = parser().parse_args(argv)
        path = location(args.ledger, args.project_root)
        value = {"schema_version": 1, "entries": []} if args.command == "create" else read(path)
        if args.command in ("create", "append"):
            value["entries"].extend({"skill": name, "state": "eligible"} for name in args.skill)
        elif args.command == "set":
            if not 0 <= args.entry < len(value["entries"]):
                raise SessionError("Invalid session entry index.")
            value["entries"][args.entry]["state"] = args.state
        validate(value)
        if args.command != "show":
            # Recheck resolution before mutation; no implicit project discovery.
            if location(args.ledger, args.project_root) != path:
                raise SessionError("Session location changed.")
            write(path, value, create=args.command == "create")
        print(json.dumps({"advisory": ADVISORY, "ledger": value}, ensure_ascii=True))
        return 0
    except SessionError as exc:
        message = str(exc)
    except (OSError, ValueError, TypeError, RecursionError, RuntimeError):
        message = "Session ledger could not be processed."
    print(json.dumps({"error": message, "advisory": ADVISORY}), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
