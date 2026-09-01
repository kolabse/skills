from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


REPOSITORY = "kolabse/skills"
MAX_INPUT_BYTES = 32_768
MAX_REPORT_BYTES = 24_000
NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")
FORBIDDEN = (
    ("URL", re.compile(r"(?i)\b(?:https?|ssh|git)://|\bwww\.")),
    ("email address", re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")),
    ("Windows path", re.compile(r"(?i)(?:^|\s)[A-Z]:[\\/]")),
    ("home path", re.compile(r"(?i)(?:^|\s)(?:/home/|/Users/|~[/\\])")),
    ("secret-like value", re.compile(r"(?i)\b(?:gh[pousr]_|sk-|xox[baprs]-|AKIA)[A-Za-z0-9_-]{8,}")),
    ("code fence", re.compile(r"```")),
)
OUTCOMES = {"success", "partial", "blocked", "error"}
AGENTS = {"codex", "claude-code"}
OS_VALUES = {"linux", "macos", "windows", "other"}
PROJECT_KINDS = {
    "application", "library", "documentation", "infrastructure",
    "skill-collection", "mixed", "other",
}
EXPECTED = {"automatic", "explicit", "none", "unsure"}
OBSERVED = {"automatic", "explicit", "not-invoked", "wrong-skill"}
SIGNALS = {
    "false-negative-trigger", "false-positive-trigger", "wrong-workflow",
    "manual-install", "manual-update", "manual-configuration", "manual-correction",
    "retry-required", "required-stage-skipped", "stopped-safely",
    "unwanted-change", "unclear-instruction", "no-problem-observed",
}
EVIDENCE_KINDS = {"trigger", "workflow", "verification", "safety", "user-observation"}
EVIDENCE_STATUS = {"passed", "failed", "partial", "not-observed"}


class FeedbackError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise FeedbackError(f"cannot read feedback input: {error}") from error
    if len(raw) > MAX_INPUT_BYTES:
        raise FeedbackError("feedback input exceeds the size limit")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise FeedbackError(f"feedback input is invalid JSON: {error}") from error
    if not isinstance(value, dict):
        raise FeedbackError("feedback input must be a JSON object")
    return value


def exact_object(value: object, required: set[str], optional: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not required.issubset(value) or set(value) - required - optional:
        raise FeedbackError(f"{label} fields do not match the version 1 contract")
    return value


def bounded_text(value: object, label: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise FeedbackError(f"{label} must be non-empty text no longer than {limit} characters")
    normalized = " ".join(value.split())
    for kind, pattern in FORBIDDEN:
        if pattern.search(normalized):
            raise FeedbackError(f"{label} contains a forbidden {kind}")
    return normalized


def validate(value: dict[str, Any]) -> dict[str, Any]:
    required = {"schema_version", "skill", "agent", "environment", "invocation", "outcome", "signals"}
    optional = {"task_summary", "evidence", "unclear", "improvement"}
    exact_object(value, required, optional, "feedback")
    if value["schema_version"] != 1:
        raise FeedbackError("feedback schema_version must be 1")
    skill = exact_object(value["skill"], {"name", "version"}, set(), "skill")
    if not isinstance(skill["name"], str) or not NAME.fullmatch(skill["name"]):
        raise FeedbackError("skill name is invalid")
    if not isinstance(skill["version"], str) or not VERSION.fullmatch(skill["version"]):
        raise FeedbackError("skill version is invalid")
    agent = exact_object(value["agent"], {"name"}, {"version"}, "agent")
    if agent["name"] not in AGENTS:
        raise FeedbackError("agent name is invalid")
    if "version" in agent:
        agent["version"] = bounded_text(agent["version"], "agent.version", 80)
    environment = exact_object(
        value["environment"], {"os", "project_kind", "repository_count"}, set(), "environment"
    )
    if environment["os"] not in OS_VALUES or environment["project_kind"] not in PROJECT_KINDS:
        raise FeedbackError("environment classification is invalid")
    count = environment["repository_count"]
    if isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= 50:
        raise FeedbackError("repository_count must be an integer from 0 to 50")
    invocation = exact_object(value["invocation"], {"expected", "observed"}, set(), "invocation")
    if invocation["expected"] not in EXPECTED or invocation["observed"] not in OBSERVED:
        raise FeedbackError("invocation classification is invalid")
    if value["outcome"] not in OUTCOMES:
        raise FeedbackError("outcome is invalid")
    signals = value["signals"]
    if not isinstance(signals, list) or len(signals) != len(set(signals)) or set(signals) - SIGNALS:
        raise FeedbackError("signals must be a unique list of supported values")
    for key in ("task_summary", "unclear", "improvement"):
        if key in value:
            value[key] = bounded_text(value[key], key, 500)
    evidence = value.get("evidence", [])
    if not isinstance(evidence, list) or len(evidence) > 12:
        raise FeedbackError("evidence must contain at most 12 entries")
    for index, item in enumerate(evidence):
        item = exact_object(item, {"kind", "status", "summary"}, set(), f"evidence[{index}]")
        if item["kind"] not in EVIDENCE_KINDS or item["status"] not in EVIDENCE_STATUS:
            raise FeedbackError(f"evidence[{index}] classification is invalid")
        item["summary"] = bounded_text(item["summary"], f"evidence[{index}].summary", 300)
    return value


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def report_id(value: dict[str, Any]) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()[:16]


def render(value: dict[str, Any]) -> str:
    identifier = report_id(value)
    lines = [
        f"# Skill feedback: {value['skill']['name']}", "",
        f"Report ID: `{identifier}`", "",
        "This report was prepared with explicit collection consent. Its body is de-identified, "
        "but a GitHub submission remains attributable to the submitting account.", "",
        "## Context", "",
        f"- Skill version: `{value['skill']['version']}`",
        f"- Agent: `{value['agent']['name']}`" + (f" (`{value['agent']['version']}`)" if value['agent'].get('version') else ""),
        f"- OS: `{value['environment']['os']}`",
        f"- Project kind: `{value['environment']['project_kind']}`",
        f"- Repository count: `{value['environment']['repository_count']}`",
        f"- Expected invocation: `{value['invocation']['expected']}`",
        f"- Observed invocation: `{value['invocation']['observed']}`",
        f"- Outcome: `{value['outcome']}`", "",
    ]
    if value.get("task_summary"):
        lines.extend(["## Task summary", "", value["task_summary"], ""])
    lines.extend(["## Signals", ""])
    lines.extend([f"- `{signal}`" for signal in value["signals"]] or ["- None reported"])
    lines.append("")
    if value.get("evidence"):
        lines.extend(["## Observable evidence", ""])
        lines.extend(
            f"- `{item['kind']}` / `{item['status']}`: {item['summary']}"
            for item in value["evidence"]
        )
        lines.append("")
    if value.get("unclear"):
        lines.extend(["## What was unclear", "", value["unclear"], ""])
    if value.get("improvement"):
        lines.extend(["## Suggested improvement", "", value["improvement"], ""])
    body = "\n".join(lines)
    seal = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return body + f"<!-- report-skill-feedback:v1 sha256={seal} -->\n"


def default_output(value: dict[str, Any]) -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    return base / "kolabse" / "skill-feedback" / f"{value['skill']['name']}-{report_id(value)}.md"


def write_atomic(path: Path, content: str) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    temporary.replace(path)


def validate_report(path: Path) -> tuple[str, str, str]:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise FeedbackError(f"cannot read report: {error}") from error
    if len(raw) > MAX_REPORT_BYTES:
        raise FeedbackError("report exceeds the size limit")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise FeedbackError("report is not UTF-8") from error
    match = re.search(r"^# Skill feedback: (?P<skill>[a-z0-9]+(?:-[a-z0-9]+)*)\r?$", text, re.MULTILINE)
    seal = re.search(r"<!-- report-skill-feedback:v1 sha256=(?P<sha>[0-9a-f]{64}) -->\r?\n?$", text)
    report = re.search(r"^Report ID: `(?P<id>[0-9a-f]{16})`\r?$", text, re.MULTILINE)
    if not match or not seal or not report:
        raise FeedbackError("report is not a sealed version 1 feedback draft")
    expected_seal = hashlib.sha256(text[:seal.start()].encode("utf-8")).hexdigest()
    if seal.group("sha") != expected_seal:
        raise FeedbackError("report changed after its reviewed preview")
    for kind, pattern in FORBIDDEN:
        if pattern.search(text):
            raise FeedbackError(f"report contains a forbidden {kind}")
    title = f"Skill feedback: {match.group('skill')} ({report.group('id')})"
    return text, title, report.group("id")


def draft(args: argparse.Namespace) -> dict[str, Any]:
    if not args.collection_consent:
        raise FeedbackError("draft requires --collection-consent for this report")
    value = validate(load_json(args.input))
    output = args.output or default_output(value)
    content = render(value)
    write_atomic(output, content)
    return {
        "schema_version": 1, "operation": "draft", "report_id": report_id(value),
        "report": str(output.expanduser().resolve()), "submitted": False,
        "preview": content,
    }


def submit(args: argparse.Namespace) -> dict[str, Any]:
    if not args.submission_consent:
        raise FeedbackError("submit requires --submission-consent for the reviewed report")
    report = args.report.expanduser().resolve()
    _text, title, identifier = validate_report(report)
    gh = shutil.which("gh")
    if gh is None:
        raise FeedbackError("GitHub CLI is unavailable; keep the reviewed report for manual submission")
    completed = subprocess.run(
        [gh, "issue", "create", "--repo", REPOSITORY, "--title", title, "--body-file", str(report)],
        shell=False, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if completed.returncode:
        raise FeedbackError(f"GitHub submission failed with exit code {completed.returncode}")
    url = completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else ""
    if not re.fullmatch(r"https://github\.com/kolabse/skills/issues/[1-9][0-9]*", url):
        raise FeedbackError("GitHub CLI did not return the expected kolabse/skills issue URL")
    return {"schema_version": 1, "operation": "submit", "report_id": identifier, "submitted": True, "issue_url": url}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Prepare and submit de-identified skill feedback.")
    sub = result.add_subparsers(dest="command", required=True)
    status_parser = sub.add_parser("status")
    status_parser.add_argument("--json", action="store_true")
    draft_parser = sub.add_parser("draft")
    draft_parser.add_argument("--input", type=Path, required=True)
    draft_parser.add_argument("--output", type=Path)
    draft_parser.add_argument("--collection-consent", action="store_true")
    draft_parser.add_argument("--json", action="store_true")
    submit_parser = sub.add_parser("submit")
    submit_parser.add_argument("--report", type=Path, required=True)
    submit_parser.add_argument("--submission-consent", action="store_true")
    submit_parser.add_argument("--json", action="store_true")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "status":
            result = {
                "schema_version": 1,
                "skill": "report-skill-feedback",
                "configured": True,
                "collection_consent_required": True,
                "submission_consent_required": True,
                "submission_repository": REPOSITORY,
            }
        else:
            result = draft(args) if args.command == "draft" else submit(args)
        print(json.dumps(result, ensure_ascii=False, indent=2 if args.json else None))
        return 0
    except FeedbackError as error:
        print(json.dumps({"schema_version": 1, "error": str(error), "submitted": False}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
