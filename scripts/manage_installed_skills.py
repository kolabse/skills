from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


COLLECTION = "kolabse-skills"
SKILLS_CLI_VERSION = "1.5.22"
LOCK_FILE = "skills-lock.json"
METADATA_FILE = "collection-metadata.json"
KNOWN_SKILLS = {
    "maintain-work-log",
    "notify-via-telegram",
    "operate-yandex-cloud",
    "synchronize-git-repositories",
    "verify-before-push",
}


class ManagerError(RuntimeError):
    pass


def load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ManagerError(f"{label} is missing: {path}") from error
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as error:
        raise ManagerError(f"{label} is invalid: {path}: {error}") from error
    if not isinstance(value, dict):
        raise ManagerError(f"{label} must contain a JSON object: {path}")
    return value


def project_install_root(project: Path) -> Path:
    return project.resolve() / ".agents" / "skills"


def read_project_state(project: Path) -> dict[str, Any]:
    root = project.resolve()
    lock = load_object(root / LOCK_FILE, "skills lock")
    entries = lock.get("skills")
    if not isinstance(entries, dict):
        raise ManagerError("skills-lock.json field 'skills' must be an object")
    installed_root = project_install_root(root)
    skills: list[dict[str, Any]] = []
    for name in sorted(set(entries) & KNOWN_SKILLS):
        entry = entries[name]
        if not isinstance(entry, dict):
            raise ManagerError(f"lock entry for {name} must be an object")
        skill_root = installed_root / name
        metadata_path = skill_root / METADATA_FILE
        metadata: dict[str, Any] = {}
        metadata_error = ""
        try:
            metadata = load_object(metadata_path, f"{name} metadata")
        except ManagerError as error:
            metadata_error = str(error)
        skills.append(
            {
                "name": name,
                "installed": skill_root.is_dir(),
                "path": str(skill_root),
                "source": entry.get("source", ""),
                "computed_hash": entry.get("computedHash", ""),
                "collection": metadata.get("collection", ""),
                "version": metadata.get("version", "unknown"),
                "metadata_valid": (
                    metadata.get("schema_version") == 1
                    and metadata.get("collection") == COLLECTION
                    and metadata.get("skill") == name
                ),
                "metadata_error": metadata_error,
            }
        )
    return {
        "schema_version": 1,
        "collection": COLLECTION,
        "scope": "project",
        "project": str(root),
        "lock_file": str(root / LOCK_FILE),
        "skills": skills,
    }


def print_state(state: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True))
        return
    print(f"Collection: {state['collection']} ({state['scope']})")
    for skill in state["skills"]:
        marker = "ok" if skill["installed"] and skill["metadata_valid"] else "problem"
        print(f"[{marker}] {skill['name']}: {skill['version']} ({skill['source']})")


def run_checked(command: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ManagerError(f"Could not run {command[0]!r}: {error}") from error
    if result.returncode != 0:
        detail = (result.stdout + "\n" + result.stderr).strip()
        raise ManagerError(
            f"Command failed ({result.returncode}): {' '.join(command)}: {detail[-1000:]}"
        )
    return result


def print_portable(value: str) -> None:
    encoding = sys.stdout.encoding or "utf-8"
    sys.stdout.write(value.encode(encoding, errors="replace").decode(encoding))
    if value and not value.endswith("\n"):
        sys.stdout.write("\n")


def resolve_update_selection(project: Path, skills: list[str], scope: str) -> list[str]:
    unknown = set(skills) - KNOWN_SKILLS
    if unknown:
        raise ManagerError(f"Unknown collection skills: {', '.join(sorted(unknown))}")
    if scope == "global":
        if not skills:
            raise ManagerError(
                "global updates require explicit skill names so unrelated global skills are not updated"
            )
        return skills

    lock = load_object(project.resolve() / LOCK_FILE, "skills lock")
    entries = lock.get("skills")
    if not isinstance(entries, dict):
        raise ManagerError("skills-lock.json field 'skills' must be an object")
    if skills:
        missing = set(skills) - set(entries)
        if missing:
            raise ManagerError(
                f"Collection skills are not present in the project lock: {', '.join(sorted(missing))}"
            )
        return skills

    selected = sorted(set(entries) & KNOWN_SKILLS)
    if not selected:
        raise ManagerError("no kolabse skills were found in skills-lock.json")
    return selected


def update_skills(
    project: Path,
    skills: list[str],
    scope: str,
    cli_version: str,
    yes: bool,
    timeout: int,
) -> None:
    selected = resolve_update_selection(project, skills, scope)
    npx = shutil.which("npx")
    if not npx:
        raise ManagerError("npx is required to update skills")
    command = [npx, "--yes", f"skills@{cli_version}", "update", *selected]
    command.append("-p" if scope == "project" else "-g")
    if yes:
        command.append("-y")
    result = run_checked(command, project.resolve(), timeout)
    combined_output = f"{result.stdout}\n{result.stderr}".casefold()
    if "no installed skills found matching" in combined_output:
        requested = ", ".join(selected)
        raise ManagerError(
            f"skills CLI did not update {requested}; the lock source may not support in-place "
            "updates (local development installs must be re-added from their source)"
        )
    if result.stdout.strip():
        print_portable(result.stdout.strip())
    if scope == "project":
        state = doctor(project)
        if not state["healthy"]:
            detail = "; ".join(state["problems"])
            raise ManagerError(f"post-update diagnosis failed: {detail}")


def telegram_config_path(environment: dict[str, str] | None = None) -> Path:
    env = os.environ if environment is None else environment
    if env.get("TELEGRAM_NOTIFY_CONFIG"):
        return Path(env["TELEGRAM_NOTIFY_CONFIG"]).expanduser()
    if os.name == "nt" and env.get("LOCALAPPDATA"):
        return Path(env["LOCALAPPDATA"]) / "codex" / "telegram-notify" / "config.json"
    return Path(env.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "codex" / "telegram-notify" / "config.json"


def python_executable() -> str:
    return shutil.which("python") or sys.executable


def migration_commands(project: Path, include_user_config: bool) -> list[tuple[str, list[str]]]:
    root = project.resolve()
    installed = project_install_root(root)
    python = python_executable()
    commands: list[tuple[str, list[str]]] = []
    verify_config = root / ".agents/verify-before-push/config.json"
    verify_script = installed / "verify-before-push/scripts/verify_before_push.py"
    if verify_config.is_file() and verify_script.is_file():
        commands.append(
            (
                "verify-before-push",
                [python, str(verify_script), "migrate", "--project-root", str(root), "--json"],
            )
        )
    cloud_config = root / ".agents/operate-yandex-cloud/project.yaml"
    cloud_script = installed / "operate-yandex-cloud/scripts/migrate_config.py"
    if cloud_config.is_file() and cloud_script.is_file():
        commands.append(
            (
                "operate-yandex-cloud",
                [python, str(cloud_script), "--project-path", str(root), "--json"],
            )
        )
    telegram_config = telegram_config_path()
    telegram_script = installed / "notify-via-telegram/scripts/telegram_notify.py"
    if include_user_config and telegram_config.is_file() and telegram_script.is_file():
        commands.append(
            (
                "notify-via-telegram",
                [python, str(telegram_script), "--config", str(telegram_config), "migrate", "--json"],
            )
        )
    return commands


def migrate(project: Path, include_user_config: bool, timeout: int) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for name, command in migration_commands(project, include_user_config):
        result = run_checked(command, project.resolve(), timeout)
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise ManagerError(f"{name} migration returned invalid JSON") from error
        results.append({"skill": name, "result": payload})
    return {"schema_version": 1, "collection": COLLECTION, "migrations": results}


def doctor(project: Path) -> dict[str, Any]:
    state = read_project_state(project)
    problems: list[str] = []
    if not state["skills"]:
        problems.append("no kolabse skills were found in skills-lock.json")
    versions = {
        skill["version"]
        for skill in state["skills"]
        if skill["installed"] and skill["metadata_valid"]
    }
    for skill in state["skills"]:
        if not skill["installed"]:
            problems.append(f"{skill['name']} is locked but not installed")
        elif not skill["metadata_valid"]:
            problems.append(f"{skill['name']} has missing or invalid collection metadata")
        if not isinstance(skill["source"], str) or not skill["source"]:
            problems.append(f"{skill['name']} has no lock source")
        digest = skill["computed_hash"]
        if not isinstance(digest, str) or len(digest) != 64:
            problems.append(f"{skill['name']} has an invalid lock hash")
    if len(versions) > 1:
        problems.append(f"installed skills use mixed collection versions: {sorted(versions)}")
    state["healthy"] = not problems
    state["problems"] = problems
    state["migration_candidates"] = [name for name, _ in migration_commands(project, False)]
    return state


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage installed kolabse skills.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "doctor", "migrate"):
        child = subparsers.add_parser(name)
        child.add_argument("--project-path", type=Path, default=Path.cwd())
        child.add_argument("--json", action="store_true")
        if name == "migrate":
            child.add_argument("--include-user-config", action="store_true")
            child.add_argument("--timeout", type=int, default=120)
    update = subparsers.add_parser("update")
    update.add_argument("skills", nargs="*")
    update.add_argument("--project-path", type=Path, default=Path.cwd())
    update.add_argument("--scope", choices=("project", "global"), default="project")
    update.add_argument("--cli-version", default=SKILLS_CLI_VERSION)
    update.add_argument("--yes", action="store_true")
    update.add_argument("--timeout", type=int, default=180)
    update.add_argument("--migrate", action="store_true")
    update.add_argument("--include-user-config", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "status":
            state = read_project_state(args.project_path)
            print_state(state, args.json)
            return 0
        if args.command == "doctor":
            state = doctor(args.project_path)
            print_state(state, args.json)
            if not args.json and state["problems"]:
                for problem in state["problems"]:
                    print(f"PROBLEM: {problem}")
            return 0 if state["healthy"] else 1
        if args.command == "migrate":
            result = migrate(args.project_path, args.include_user_config, args.timeout)
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        if args.migrate and args.scope != "project":
            raise ManagerError("--migrate is supported only for project-scoped updates")
        update_skills(
            args.project_path,
            args.skills,
            args.scope,
            args.cli_version,
            args.yes,
            args.timeout,
        )
        if args.migrate:
            result = migrate(args.project_path, args.include_user_config, args.timeout)
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except ManagerError as error:
        print(f"MANAGER_FAILED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
