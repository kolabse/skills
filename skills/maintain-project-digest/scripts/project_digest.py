#!/usr/bin/env python3
"""Plan and safely apply same-day project digest updates."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from collections import OrderedDict
from datetime import date
from pathlib import Path
from typing import Any


TITLE = "# Дайджест проекта"
DEFAULT_FILENAME = "project-digest.md"
MISSING_SHA256 = "missing"
DOCUMENTATION_NAMES = ("docs", "documentation", "doc")
CATEGORIES = OrderedDict(
    (
        ("new", "Доработки"),
        ("improved", "Улучшения"),
        ("fixed", "Исправления"),
        ("security", "Безопасность"),
        ("docs", "Документация"),
        ("changed", "Важные изменения"),
    )
)
DATE_HEADING = re.compile(r"^## \[(\d{4}-\d{2}-\d{2})\]$", re.MULTILINE)
CATEGORY_HEADING = re.compile(r"^### (.+)$")
SENSITIVE_VALUE = re.compile(
    r"(?i)(?:api[_ -]?key|access[_ -]?token|auth[_ -]?token|token|password|secret)\s*[:=]\s*\S+"
)


class DigestError(Exception):
    """A safe, user-actionable digest failure."""


def _json_print(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _normalize_summary(value: str) -> str:
    return " ".join(value.split()).casefold().rstrip(".!?")


def _validate_summary(value: Any) -> str:
    if not isinstance(value, str):
        raise DigestError("Each change summary must be a string.")
    summary = " ".join(value.strip().split())
    if not summary:
        raise DigestError("Change summaries cannot be empty.")
    if len(summary) > 240:
        raise DigestError("Change summaries cannot exceed 240 characters.")
    if "\n" in value or "\r" in value:
        raise DigestError("Each change summary must stay on one line.")
    if summary.startswith(("-", "*", "#", ">")):
        raise DigestError("Pass plain summary text without Markdown prefixes.")
    if "-----BEGIN " in summary or SENSITIVE_VALUE.search(summary):
        raise DigestError("Change summary appears to contain a sensitive value.")
    return summary


def load_changes(path: Path) -> list[tuple[str, str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DigestError(f"Cannot read changes input: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise DigestError("Changes input must be an object with schema_version 1.")
    if set(payload) != {"schema_version", "changes"}:
        raise DigestError("Changes input contains unsupported fields.")
    raw_changes = payload.get("changes")
    if not isinstance(raw_changes, list) or not 1 <= len(raw_changes) <= 100:
        raise DigestError("Changes input must contain between 1 and 100 entries.")

    changes: list[tuple[str, str]] = []
    for item in raw_changes:
        if not isinstance(item, dict) or set(item) != {"category", "summary"}:
            raise DigestError("Each change must contain only category and summary.")
        category = item.get("category")
        if category not in CATEGORIES:
            raise DigestError(f"Unsupported digest category: {category!r}.")
        changes.append((category, _validate_summary(item.get("summary"))))
    return changes


def discover_documentation(project_root: Path) -> list[Path]:
    return [
        candidate.resolve()
        for name in DOCUMENTATION_NAMES
        if (candidate := project_root / name).is_dir()
    ]


def resolve_target(
    project_root: Path,
    documentation_root: Path | None,
    digest_file: str,
) -> tuple[Path, list[Path]]:
    project_root = project_root.resolve()
    if not project_root.is_dir():
        raise DigestError(f"Project root does not exist: {project_root}")
    if Path(digest_file).name != digest_file or digest_file in {".", ".."}:
        raise DigestError("Digest filename must be a plain filename.")

    candidates = discover_documentation(project_root)
    if documentation_root is None:
        if len(candidates) != 1:
            reason = "not-found" if not candidates else "ambiguous"
            raise DigestError(
                f"Documentation location is {reason}; ask the user for the exact directory or repository."
            )
        documentation_root = candidates[0]
    else:
        if not documentation_root.is_absolute():
            documentation_root = project_root / documentation_root
        documentation_root = documentation_root.resolve()

    if not documentation_root.is_dir():
        raise DigestError(f"Documentation root does not exist: {documentation_root}")
    return documentation_root / digest_file, candidates


def read_digest(path: Path) -> tuple[bytes, str]:
    if not path.exists():
        return b"", MISSING_SHA256
    if not path.is_file():
        raise DigestError(f"Digest target is not a file: {path}")
    data = path.read_bytes()
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DigestError("Existing digest must be UTF-8.") from exc
    return data, _sha256(data)


def _parse_today(section: str) -> OrderedDict[str, list[str]]:
    lines = section.strip("\n").splitlines()
    entries: OrderedDict[str, list[str]] = OrderedDict((key, []) for key in CATEGORIES)
    labels_to_keys = {label: key for key, label in CATEGORIES.items()}
    current: str | None = None
    seen_categories: set[str] = set()

    for line in lines:
        if not line.strip():
            continue
        heading = CATEGORY_HEADING.match(line)
        if heading:
            label = heading.group(1)
            if label not in labels_to_keys:
                raise DigestError(f"Today's section has an unsupported category: {label}")
            current = labels_to_keys[label]
            if current in seen_categories:
                raise DigestError(f"Today's section repeats category: {label}")
            seen_categories.add(current)
            continue
        if not line.startswith("- ") or current is None:
            raise DigestError("Today's section contains an unfamiliar structure; review it manually.")
        entries[current].append(_validate_summary(line[2:]))
    return entries


def _render_section(day: str, entries: OrderedDict[str, list[str]]) -> str:
    parts = [f"## [{day}]"]
    for key, label in CATEGORIES.items():
        values = entries[key]
        if not values:
            continue
        parts.extend(("", f"### {label}", ""))
        parts.extend(f"- {value}" for value in values)
    return "\n".join(parts) + "\n"


def build_content(
    existing: bytes,
    day: str,
    changes: list[tuple[str, str]],
) -> tuple[bytes, list[str], list[str]]:
    if existing:
        raw_text = existing.decode("utf-8")
        if "\r" in raw_text.replace("\r\n", ""):
            raise DigestError("Existing digest contains unsupported line endings.")
        newline = "\r\n" if "\r\n" in raw_text else "\n"
        if newline == "\r\n" and "\n" in raw_text.replace("\r\n", ""):
            raise DigestError("Existing digest mixes LF and CRLF line endings.")
        text = raw_text.replace("\r\n", "\n")
        if not text.startswith(TITLE + "\n"):
            raise DigestError(f"Existing digest must start with {TITLE!r}.")
    else:
        newline = "\n"
        text = TITLE + "\n"

    matches = list(DATE_HEADING.finditer(text))
    prefix_end = matches[0].start() if matches else len(text)
    if text[len(TITLE) + 1 : prefix_end].strip():
        raise DigestError("Existing digest has unfamiliar content before its dated sections.")
    dates = [match.group(1) for match in matches]
    if len(dates) != len(set(dates)):
        raise DigestError("Existing digest contains duplicate date sections.")
    if dates != sorted(dates, reverse=True):
        raise DigestError("Existing digest date sections must be newest first.")
    if any(value > day for value in dates):
        raise DigestError("Existing digest contains a future date; resolve the project date before editing.")

    today_match = next((match for match in matches if match.group(1) == day), None)
    if today_match:
        start = today_match.start()
        next_match = next((match for match in matches if match.start() > start), None)
        end = next_match.start() if next_match else len(text)
        current_section = text[today_match.end() : end]
        entries = _parse_today(current_section)
    else:
        start = len(TITLE) + 1
        end = start
        entries = OrderedDict((key, []) for key in CATEGORIES)

    known = {_normalize_summary(item) for values in entries.values() for item in values}
    added: list[str] = []
    existing_items: list[str] = []
    for category, summary in changes:
        normalized = _normalize_summary(summary)
        if normalized in known:
            existing_items.append(summary)
            continue
        entries[category].append(summary)
        known.add(normalized)
        added.append(summary)

    rendered = _render_section(day, entries)
    if today_match:
        before = text[:start]
        after = text[end:]
        output = before + rendered
        if after:
            output += "\n" + after.lstrip("\n")
    else:
        before = text[:start].rstrip("\n")
        after = text[start:].lstrip("\n")
        output = before + "\n\n" + rendered
        if after:
            output += "\n" + after
    output = output.rstrip("\n") + "\n"
    if newline == "\r\n":
        output = output.replace("\n", "\r\n")
    return output.encode("utf-8"), added, existing_items


def make_plan(args: argparse.Namespace) -> dict[str, Any]:
    target, candidates = resolve_target(
        Path(args.project_root),
        Path(args.documentation_root) if args.documentation_root else None,
        args.digest_file,
    )
    existing, expected = read_digest(target)
    changes = load_changes(Path(args.input))
    day = date.today().isoformat()
    output, added, already_present = build_content(existing, day, changes)
    return {
        "schema_version": 1,
        "action": "create" if expected == MISSING_SHA256 else ("update" if output != existing else "unchanged"),
        "date": day,
        "target": str(target),
        "documentation_candidates": [str(item) for item in candidates],
        "expected_sha256": expected,
        "result_sha256": _sha256(output),
        "added": added,
        "already_present": already_present,
        "preview": output.decode("utf-8"),
    }


def apply_plan(args: argparse.Namespace) -> dict[str, Any]:
    target, _ = resolve_target(
        Path(args.project_root),
        Path(args.documentation_root) if args.documentation_root else None,
        args.digest_file,
    )
    lock_path = target.with_name(target.name + ".lock")
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise DigestError(f"Digest is locked by another writer: {lock_path}") from exc

    temp_path: Path | None = None
    try:
        with os.fdopen(lock_fd, "w", encoding="utf-8") as lock_file:
            lock_file.write("maintain-project-digest\n")
        existing, current_sha = read_digest(target)
        if current_sha != args.expected_sha256:
            raise DigestError(
                "Digest changed after planning; re-read and create a new plan before applying."
            )
        changes = load_changes(Path(args.input))
        day = date.today().isoformat()
        output, added, already_present = build_content(existing, day, changes)
        if output != existing:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=target.parent, prefix=f".{target.name}.", delete=False
            ) as temp_file:
                temp_file.write(output)
                temp_file.flush()
                os.fsync(temp_file.fileno())
                temp_path = Path(temp_file.name)
            os.replace(temp_path, target)
            temp_path = None
        action = "unchanged"
        if output != existing:
            action = "created" if current_sha == MISSING_SHA256 else "updated"
        return {
            "schema_version": 1,
            "action": action,
            "date": day,
            "target": str(target),
            "sha256": _sha256(output),
            "added": added,
            "already_present": already_present,
        }
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        lock_path.unlink(missing_ok=True)


def status(args: argparse.Namespace) -> dict[str, Any]:
    project_root = Path(args.project_root).resolve()
    if not project_root.is_dir():
        raise DigestError(f"Project root does not exist: {project_root}")
    candidates = discover_documentation(project_root)
    target: Path | None = None
    resolution = "not-found"
    if args.documentation_root:
        target, _ = resolve_target(
            project_root, Path(args.documentation_root), args.digest_file
        )
        resolution = "explicit"
    elif len(candidates) == 1:
        target = candidates[0] / args.digest_file
        resolution = "discovered"
    elif len(candidates) > 1:
        resolution = "ambiguous"

    payload: dict[str, Any] = {
        "schema_version": 1,
        "project_root": str(project_root),
        "resolution": resolution,
        "documentation_candidates": [str(item) for item in candidates],
        "target": str(target) if target else None,
        "exists": bool(target and target.is_file()),
    }
    if target and target.is_file():
        data, digest = read_digest(target)
        payload.update({"sha256": digest, "bytes": len(data)})
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "plan", "apply"):
        command = subparsers.add_parser(name)
        command.add_argument("--project-root", required=True)
        command.add_argument("--documentation-root")
        command.add_argument("--digest-file", default=DEFAULT_FILENAME)
        command.add_argument("--json", action="store_true")
        if name in {"plan", "apply"}:
            command.add_argument("--input", required=True)
        if name == "apply":
            command.add_argument("--expected-sha256", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "status":
            payload = status(args)
        elif args.command == "plan":
            payload = make_plan(args)
        else:
            payload = apply_plan(args)
        if args.json:
            _json_print(payload)
        else:
            print(f"{payload.get('action', payload.get('resolution'))}: {payload.get('target')}")
        return 0
    except DigestError as exc:
        if getattr(args, "json", False):
            _json_print({"schema_version": 1, "error": str(exc)})
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
