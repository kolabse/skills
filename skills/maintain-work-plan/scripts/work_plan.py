#!/usr/bin/env python3
"""Read-only validation and calendar previews for normalized work-plan snapshots."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import re
import sys


class PlanError(ValueError):
    """Malformed normalized input."""


def obj(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= value.keys() or value.keys() - set(required) - set(optional):
        raise PlanError("Object has missing or unsupported fields.")
    return value


def string(value):
    if not isinstance(value, str) or not value.strip() or value != value.strip() or any(ord(c) < 32 for c in value):
        raise PlanError("Expected a nonempty single-line string without surrounding whitespace.")
    return value


def array(value):
    if not isinstance(value, list):
        raise PlanError("Expected an array.")
    return value


def version(value):
    if type(value) is not int or value != 1:
        raise PlanError("schema_version must be integer 1.")


def timestamp(value):
    string(value)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}", value):
        raise PlanError("starts_at requires seconds and an explicit numeric UTC offset.")
    try:
        offset = value[-6:]
        if int(offset[1:3]) > 23 or int(offset[4:]) > 59:
            raise ValueError()
        return datetime.fromisoformat(value).astimezone(timezone.utc)
    except (ValueError, OverflowError) as exc:
        raise PlanError("Invalid starts_at timestamp.") from exc


def day(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise PlanError("Date must be YYYY-MM-DD.")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise PlanError("Invalid date.") from exc


def schedule(value):
    timestamp(value["starts_at"])
    if type(value["duration_minutes"]) is not int or value["duration_minutes"] < 1:
        raise PlanError("duration_minutes must be a positive integer.")


def validate_snapshot(payload):
    obj(payload, ("schema_version", "project_id", "project_code", "id_prefix", "historical_ids", "tasks"))
    version(payload["schema_version"])
    for key in ("project_id", "project_code", "id_prefix"):
        string(payload[key])
    if any(c in payload["project_code"] for c in "[]"):
        raise PlanError("project_code cannot contain brackets.")
    prefix = payload["id_prefix"]
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", prefix):
        raise PlanError("id_prefix must be an ASCII identifier beginning with a letter.")
    numbers = {}
    width = 3

    def identifier(value):
        nonlocal width
        string(value)
        match = re.fullmatch(re.escape(prefix) + r"-(\d+)", value, flags=re.ASCII)
        if not match or len(match[1]) > 100 or int(match[1]) < 1:
            raise PlanError("Task ID must use the configured prefix and a positive numeric suffix.")
        number = int(match[1])
        if number in numbers and numbers[number] != value:
            raise PlanError("Numeric aliases for task IDs are ambiguous.")
        numbers[number] = value
        width = max(width, len(match[1]))
        return value

    history = [identifier(item) for item in array(payload["historical_ids"])]
    if len(set(history)) != len(history):
        raise PlanError("Duplicate historical IDs.")
    tasks = array(payload["tasks"])
    by_id = {}
    for task in tasks:
        obj(task, ("id", "title", "status", "depends_on", "desired_date"), ("starts_at", "duration_minutes"))
        identifier(task["id"])
        if task["id"] in by_id:
            raise PlanError("Duplicate active task IDs.")
        by_id[task["id"]] = task
        string(task["title"])
        if task["status"] not in ("planned", "in_progress", "blocked", "partial", "acceptance_pending"):
            raise PlanError("Unsupported active status.")
        deps = array(task["depends_on"])
        for dep in deps:
            identifier(dep)
        if len(set(deps)) != len(deps):
            raise PlanError("Duplicate dependency IDs.")
        desired = task["desired_date"]
        if desired is not None:
            if not isinstance(desired, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", desired):
                raise PlanError("desired_date must be YYYY-MM-DD or null.")
            try:
                date.fromisoformat(desired)
            except ValueError as exc:
                raise PlanError("Invalid desired_date.") from exc
        if ("starts_at" in task) != ("duration_minutes" in task):
            raise PlanError("Scheduling fields must occur together.")
        if "starts_at" in task:
            schedule(task)
            if desired is None or desired != task["starts_at"][:10]:
                raise PlanError("Timed tasks require desired_date matching the local starts_at date.")
    warnings = []
    positions = {task_id: i for i, task_id in enumerate(by_id)}
    for task in tasks:
        for dep in task["depends_on"]:
            if dep == task["id"] or dep not in by_id and dep not in history:
                raise PlanError("Self or unknown dependency.")
            if dep not in by_id:
                warnings.append({"code": "historical_dependency_outcome_unknown", "task_id": task["id"], "dependency_id": dep})
                continue
            for code, condition in (
                ("dependency_order", positions[dep] > positions[task["id"]]),
                ("dependency_date", bool(task["desired_date"] and by_id[dep]["desired_date"] and by_id[dep]["desired_date"] > task["desired_date"])),
            ):
                if condition:
                    warnings.append({"code": code, "task_id": task["id"], "dependency_id": dep})
    # Iterative traversal keeps long valid plans independent of Python's recursion limit.
    remaining = {key: set(task["depends_on"]) & by_id.keys() for key, task in by_id.items()}
    while remaining:
        ready = {key for key, deps in remaining.items() if not deps}
        if not ready:
            raise PlanError("Dependency cycle.")
        remaining = {key: deps - ready for key, deps in remaining.items() if key not in ready}
    return {"valid": True, "next_id": f"{prefix}-{max(numbers, default=0) + 1:0{width}d}", "warnings": warnings}


def managed(value):
    if isinstance(value, dict) and "date" in value:
        obj(value, ("title", "date"))
        string(value["title"])
        day(value["date"])
        return (value["title"], "all_day", value["date"])
    obj(value, ("title", "starts_at", "duration_minutes"))
    string(value["title"])
    schedule(value)
    return (value["title"], timestamp(value["starts_at"]), value["duration_minutes"])


def calendar_preview(snapshot, state):
    validation = validate_snapshot(snapshot)
    obj(state, ("schema_version", "calendar_id", "observation_complete", "unknown_outcome_task_ids", "events", "links"))
    version(state["schema_version"])
    string(state["calendar_id"])
    if type(state["observation_complete"]) is not bool:
        raise PlanError("observation_complete must be boolean.")
    unknown = array(state["unknown_outcome_task_ids"])
    for item in unknown:
        string(item)
    if len(set(unknown)) != len(unknown):
        raise PlanError("Duplicate unknown-outcome task IDs.")
    events = {}
    identities = {}
    for event in array(state["events"]):
        obj(event, ("event_id", "project_id", "task_id", "managed"))
        for key in ("event_id", "project_id", "task_id"):
            string(event[key])
        managed(event["managed"])
        if event["event_id"] in events:
            raise PlanError("Duplicate event IDs.")
        events[event["event_id"]] = event
        identities.setdefault((event["project_id"], event["task_id"]), []).append(event)
    links = {}
    linked_events = {}
    for link in array(state["links"]):
        obj(link, ("project_id", "task_id", "event_id", "last_synced"))
        for key in ("project_id", "task_id", "event_id"):
            string(link[key])
        managed(link["last_synced"])
        identity = (link["project_id"], link["task_id"])
        if identity in links or link["event_id"] in linked_events:
            raise PlanError("Duplicate links.")
        links[identity] = link
        linked_events[link["event_id"]] = identity
    operations = []
    project = snapshot["project_id"]
    active = {task["id"] for task in snapshot["tasks"]}
    for task in snapshot["tasks"]:
        identity = (project, task["id"])
        link = links.get(identity)
        matches = identities.get(identity, [])
        op = {"task_id": task["id"]}
        if "starts_at" not in task and task["desired_date"] is None:
            if link or matches:
                operations.append(dict(op, operation="unlink_review", reason="scheduling_removed"))
            continue
        desired = {"title": f'[{snapshot["project_code"]}] {task["title"]}'}
        if "starts_at" in task:
            desired.update(starts_at=task["starts_at"], duration_minutes=task["duration_minutes"])
        else:
            desired["date"] = task["desired_date"]
        event = events.get(link["event_id"]) if link else matches[0] if len(matches) == 1 else None
        if not state["observation_complete"]:
            op.update(operation="conflict", reason="incomplete_observation")
        elif len(matches) > 1:
            op.update(operation="conflict", reason="duplicate_identity")
        elif link and (event is None or (event["project_id"], event["task_id"]) != identity):
            op.update(operation="conflict", reason="missing_or_mismatched_link")
        elif event and event["event_id"] in linked_events and linked_events[event["event_id"]] != identity:
            op.update(operation="conflict", reason="event_linked_elsewhere", event_id=event["event_id"])
        elif event and managed(event["managed"]) == managed(desired):
            op.update(operation="noop" if link else "recover", event_id=event["event_id"], desired=desired)
        elif task["id"] in unknown:
            op.update(operation="conflict", reason="unknown_outcome")
        elif event and link and managed(event["managed"]) == managed(link["last_synced"]):
            op.update(operation="update", event_id=event["event_id"], desired=desired, expected_managed=event["managed"].copy())
        elif event:
            op.update(operation="conflict", reason="remote_changes_or_unlinked_difference", event_id=event["event_id"])
        else:
            op.update(operation="create", desired=desired)
        operations.append(op)
    orphan_ids = {task_id for p, task_id in links if p == project and task_id not in active}
    orphan_ids.update(task_id for p, task_id in identities if p == project and task_id not in active)
    operations.extend({"task_id": task_id, "operation": "unlink_review", "reason": "task_not_active"} for task_id in sorted(orphan_ids))
    return {"calendar_id": state["calendar_id"], "project_id": project, "operations": operations, "warnings": validation["warnings"]}


def load(path):
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise PlanError("Duplicate JSON object keys.")
            result[key] = value
        return result

    try:
        return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique_keys)
    except (OSError, UnicodeError, ValueError) as exc:
        raise PlanError(f"Cannot read JSON input: {exc}") from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "validate", "calendar-preview"):
        command = commands.add_parser(name)
        command.add_argument("--json", action="store_true")
        if name != "status":
            command.add_argument("--input", required=True)
        if name == "calendar-preview":
            command.add_argument("--calendar-state", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "status":
            result = {"schema_version": 1, "read_only": True, "configured": False, "format": "normalized-json-snapshot"}
        else:
            snapshot = load(args.input)
            result = validate_snapshot(snapshot) if args.command == "validate" else calendar_preview(snapshot, load(args.calendar_state))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (PlanError, RecursionError, OverflowError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
