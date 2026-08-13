from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


START = "<!-- maintain-work-log:start -->"
END = "<!-- maintain-work-log:end -->"
BLOCK = """<!-- maintain-work-log:start -->
## Work log

Use `$maintain-work-log` for every project task. Maintain the dated,
chronological log in `docs/reports/work-log.md`; record material changes,
operations, diagnostics, discussions, decisions, verification, blockers,
and rollback results before completing the task. Never record secrets,
personal data, private reasoning, or raw sensitive logs.
<!-- maintain-work-log:end -->"""
LOG_RELATIVE = Path("docs/reports/work-log.md")


class ConfigurationError(RuntimeError):
    pass


def inspect(project_path: Path) -> dict[str, object]:
    root = project_path.resolve()
    agents = root / "AGENTS.md"
    log = root / LOG_RELATIVE
    text = agents.read_text(encoding="utf-8") if agents.is_file() else ""
    starts, ends = text.count(START), text.count(END)
    malformed = starts != ends or starts > 1 or (starts == 1 and text.index(START) > text.index(END))
    managed = starts == 1 and ends == 1 and not malformed
    return {
        "skill": "maintain-work-log",
        "scope": "project",
        "configured": managed and log.is_file(),
        "valid": not malformed,
        "agents_file": str(agents),
        "managed_block": managed,
        "work_log": str(log),
        "work_log_exists": log.is_file(),
    }


def configure(project_path: Path) -> tuple[dict[str, object], bool]:
    root = project_path.resolve()
    state = inspect(root)
    if not state["valid"]:
        raise ConfigurationError("AGENTS.md contains malformed or duplicate managed markers")
    agents = root / "AGENTS.md"
    text = agents.read_text(encoding="utf-8") if agents.is_file() else ""
    changed = False
    if not state["managed_block"]:
        separator = "" if not text else ("\n" if text.endswith("\n") else "\n\n")
        agents.write_text(f"{text}{separator}{BLOCK}\n", encoding="utf-8", newline="\n")
        changed = True
    log = root / LOG_RELATIVE
    if not log.is_file():
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text("# Журнал работ\n", encoding="utf-8", newline="\n")
        changed = True
    result = inspect(root)
    result["changed"] = changed
    return result, changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Configure the project work-log policy.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("configure", "status"):
        child = subparsers.add_parser(command)
        child.add_argument("--project-path", required=True, type=Path)
        child.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        state = configure(args.project_path)[0] if args.command == "configure" else inspect(args.project_path)
        if args.json:
            print(json.dumps(state, ensure_ascii=False, sort_keys=True))
        else:
            print(f"{'configured' if state['configured'] else 'not configured'}: {state['agents_file']}")
        return 0 if state["configured"] and state["valid"] else 1
    except (ConfigurationError, OSError, UnicodeError) as error:
        print(f"CONFIGURATION_FAILED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
