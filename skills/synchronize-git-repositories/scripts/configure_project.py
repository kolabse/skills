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
PREVIOUS_BLOCK = """<!-- synchronize-git-repositories:start -->
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
CODEX_BLOCK = PREVIOUS_BLOCK.replace(
    "publish a feature branch\nfrom the verified current primary-branch SHA",
    "publish a task branch\nfrom the verified current configured base SHA",
).replace("rather than the primary branch", "rather than the base branch")
CLAUDE_BLOCK = CODEX_BLOCK.replace("`$synchronize-git-repositories`", "`/synchronize-git-repositories`")
DEFAULTS_START = "<!-- git-workflow-defaults:start -->"
DEFAULTS_END = "<!-- git-workflow-defaults:end -->"
DEFAULTS_BLOCK = """<!-- git-workflow-defaults:start -->
## Default Git workflow conventions

These are fallback conventions only. Existing explicit project or user
instructions, branch mappings, release configuration, and commit rules take
precedence independently for each dimension; never overwrite or reinterpret
them during installation or update.

When branch naming is unspecified, use `feature/<description>` for new work,
`bugfix/<description>` for ordinary defects, `release/<version>` for release
preparation, and `hotfix/<description>` only for an explicitly requested urgent
production fix. A defect alone does not authorize a hotfix or release.

Use the project's configured development role as the base for feature/ and
bugfix/ work and release/ preparation; use its configured production role for
explicit hotfix/ work. Resolve these roles from project rules, never from an
assumed branch name. Do not create develop/main branches, introduce GitFlow
into a trunk-based project, or invent missing development/production mappings.
If the required base or integration target is unknown, ask before branching
or integrating. Naming defaults do not authorize publication or integration.

When commit message conventions are unspecified, use `type: summary` or
`type(scope): summary`, with types `feat`, `fix`, `refactor`, `docs`, `test`,
and `chore`, chosen for the actual change. Preserve explicit project formats,
allowed types, scopes, ticket requirements, and release/versioning rules.
<!-- git-workflow-defaults:end -->"""
AGENTS = {
    "codex": {"filename": "AGENTS.md", "block": CODEX_BLOCK},
    "claude-code": {"filename": "CLAUDE.md", "block": CLAUDE_BLOCK},
}


class ConfigurationError(RuntimeError):
    pass


def rules_path(project_path: Path, agent: str) -> Path:
    return project_path.resolve() / AGENTS[agent]["filename"]


def read_rules(path: Path) -> str:
    if path.is_symlink():
        raise ConfigurationError(f"rules file must not be a symlink: {path}")
    if not path.exists():
        return ""
    if not path.is_file():
        raise ConfigurationError(f"rules path must be a regular file: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        return handle.read()


def marker_state(text: str, start: str, end: str) -> tuple[bool, bool]:
    starts, ends = text.count(start), text.count(end)
    malformed = starts != ends or starts > 1 or (starts == 1 and text.index(start) > text.index(end))
    return starts == 1 and ends == 1 and not malformed, malformed


def inspect(project_path: Path, agent: str = "codex") -> dict[str, object]:
    path = rules_path(project_path, agent)
    text = read_rules(path)
    configured, malformed = marker_state(text, START, END)
    defaults_configured, defaults_malformed = marker_state(text, DEFAULTS_START, DEFAULTS_END)
    overlap = configured and defaults_configured and not (
        text.index(END) + len(END) <= text.index(DEFAULTS_START)
        or text.index(DEFAULTS_END) + len(DEFAULTS_END) <= text.index(START)
    )
    return {
        "skill": "synchronize-git-repositories",
        "scope": "project",
        "configured": configured,
        "valid": not (malformed or defaults_malformed or overlap),
        "agent": agent,
        "rules_file": str(path),
        "agents_file": str(path),
        "managed_block": configured,
        "defaults_configured": defaults_configured,
        "defaults_malformed": defaults_malformed or overlap,
    }


def configure(project_path: Path, agent: str = "codex") -> tuple[dict[str, object], bool]:
    state = inspect(project_path, agent)
    if not state["valid"]:
        raise ConfigurationError(f"{AGENTS[agent]['filename']} contains malformed or duplicate managed markers")
    path = rules_path(project_path, agent)
    text = read_rules(path)
    original = text
    block = AGENTS[agent]["block"]
    if not state["configured"]:
        separator = "" if not text else ("\n" if text.endswith("\n") else "\n\n")
        text = f"{text}{separator}{block}\n"
    else:
        start, end = text.index(START), text.index(END) + len(END)
        current = text[start:end].replace("\r\n", "\n")
        known = [LEGACY_BLOCK, PREVIOUS_BLOCK]
        if agent == "claude-code":
            known = [item.replace("`$synchronize-git-repositories`", "`/synchronize-git-repositories`") for item in known]
        if current in known:
            text = text[:start] + block + text[end:]
    if not state["defaults_configured"]:
        separator = "" if not text else ("\n" if text.endswith("\n") else "\n\n")
        text = f"{text}{separator}{DEFAULTS_BLOCK}\n"
    changed = text != original
    if changed:
        path.write_text(text, encoding="utf-8", newline="")
    result = inspect(project_path, agent)
    result["changed"] = changed
    return result, changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Configure repository synchronization policy.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("configure", "status", "bootstrap"):
        child = subparsers.add_parser(command)
        child.add_argument("--project-path", required=True, type=Path)
        child.add_argument("--agent", choices=sorted(AGENTS), default="codex")
        child.add_argument("--json", action="store_true")
        if command == "bootstrap":
            child.add_argument("--apply", action="store_true")
            child.add_argument("--yes", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "bootstrap":
            state = inspect(args.project_path, args.agent)
            if not state["valid"]:
                raise ConfigurationError("rules contain malformed or duplicate managed markers")
            if args.apply and not args.yes:
                raise ConfigurationError("bootstrap requires both --apply and --yes")
            state = configure(args.project_path, args.agent)[0] if args.apply else state
            state["mode"] = "bootstrap"
            state["mutates_repository"] = bool(state.get("changed", False))
        else:
            state = configure(args.project_path, args.agent)[0] if args.command == "configure" else inspect(args.project_path, args.agent)
        if args.json:
            print(json.dumps(state, ensure_ascii=False, sort_keys=True))
        else:
            print(f"{'configured' if state['configured'] else 'not configured'}: {state['agents_file']}")
        return 0 if state["valid"] and (state["configured"] or args.command == "bootstrap") else 1
    except (ConfigurationError, OSError, UnicodeError) as error:
        print(f"CONFIGURATION_FAILED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
