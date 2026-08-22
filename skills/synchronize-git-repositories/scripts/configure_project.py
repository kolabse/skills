from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


START = "<!-- synchronize-git-repositories:start -->"
END = "<!-- synchronize-git-repositories:end -->"
LEGACY_BLOCK = """<!-- synchronize-git-repositories:start -->
## Repository synchronization

Use `$synchronize-git-repositories` before analysis, edits, validation,
commits, pushes, deployments, or remote operations. Synchronize every
repository involved in the task with its tracked upstream using safe
fast-forward updates, preserve dirty worktrees, and never resolve divergence
with an automatic stash, reset, rebase, merge, clean, or force-push.
<!-- synchronize-git-repositories:end -->"""
CODEX_BLOCK = """<!-- synchronize-git-repositories:start -->
## Repository synchronization

Use `$synchronize-git-repositories` before analysis, edits, validation,
commits, pushes, deployments, or remote operations. Synchronize every
repository involved in the task with its tracked upstream using safe
fast-forward updates, preserve dirty worktrees, and never resolve divergence
with an automatic stash, reset, rebase, merge, clean, or force-push.
For authorized changes intended for publication, publish a feature branch
from the verified current primary-branch SHA before the first code edit and
track that branch's own remote ref rather than the primary branch.
<!-- synchronize-git-repositories:end -->"""
CLAUDE_BLOCK = CODEX_BLOCK.replace("`$synchronize-git-repositories`", "`/synchronize-git-repositories`")
AGENTS = {
    "codex": {"filename": "AGENTS.md", "block": CODEX_BLOCK},
    "claude-code": {"filename": "CLAUDE.md", "block": CLAUDE_BLOCK},
}


class ConfigurationError(RuntimeError):
    pass


def rules_path(project_path: Path, agent: str) -> Path:
    return project_path.resolve() / AGENTS[agent]["filename"]


def inspect(project_path: Path, agent: str = "codex") -> dict[str, object]:
    path = rules_path(project_path, agent)
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    starts, ends = text.count(START), text.count(END)
    malformed = starts != ends or starts > 1 or (starts == 1 and text.index(START) > text.index(END))
    configured = starts == 1 and ends == 1 and not malformed
    return {
        "skill": "synchronize-git-repositories",
        "scope": "project",
        "configured": configured,
        "valid": not malformed,
        "agent": agent,
        "rules_file": str(path),
        "agents_file": str(path),
        "managed_block": configured,
    }


def configure(project_path: Path, agent: str = "codex") -> tuple[dict[str, object], bool]:
    state = inspect(project_path, agent)
    if not state["valid"]:
        raise ConfigurationError(f"{AGENTS[agent]['filename']} contains malformed or duplicate managed markers")
    path = rules_path(project_path, agent)
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    block = AGENTS[agent]["block"]
    changed = False
    if not state["configured"]:
        separator = "" if not text else ("\n" if text.endswith("\n") else "\n\n")
        path.write_text(f"{text}{separator}{block}\n", encoding="utf-8", newline="\n")
        changed = True
    elif agent == "codex" and LEGACY_BLOCK in text:
        path.write_text(
            text.replace(LEGACY_BLOCK, CODEX_BLOCK, 1), encoding="utf-8", newline="\n"
        )
        changed = True
    result = inspect(project_path, agent)
    result["changed"] = changed
    return result, changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Configure repository synchronization policy.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("configure", "status"):
        child = subparsers.add_parser(command)
        child.add_argument("--project-path", required=True, type=Path)
        child.add_argument("--agent", choices=sorted(AGENTS), default="codex")
        child.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        state = configure(args.project_path, args.agent)[0] if args.command == "configure" else inspect(args.project_path, args.agent)
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
