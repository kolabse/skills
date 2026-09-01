"""Migrate verified kolabse project copies to global agent installations."""

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


COLLECTION = "kolabse-skills"
SOURCE = "kolabse/skills"
CANONICAL_REPOSITORY = "https://github.com/kolabse/skills"
CLI_VERSION = "1.5.22"
AGENT_LAYOUTS = {"codex": ".agents/skills", "claude-code": ".claude/skills"}
LOCK_FILE = "skills-lock.json"
GLOBAL_LOCK = ".agents/.skill-lock.json"
METADATA_FILE = "collection-metadata.json"
SHA = re.compile(r"^[0-9a-f]{64}$")


class CentralizeError(RuntimeError):
    def __init__(self, message: str, *, mutated: bool = False):
        super().__init__(message)
        self.mutated = mutated


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def load_object(path: Path, label: str, missing: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        if missing is not None:
            return missing
        raise CentralizeError(f"{label} is missing: {path}")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CentralizeError(f"{label} is invalid: {path}: {error}") from error
    if not isinstance(value, dict):
        raise CentralizeError(f"{label} must contain a JSON object: {path}")
    return value


def known_skills(repository_root: Path) -> set[str]:
    catalog = load_object(repository_root / "skill-catalog.json", "skill catalog")
    entries = catalog.get("skills")
    if not isinstance(entries, list):
        raise CentralizeError("skill catalog has no skills array")
    return {
        item["name"] for item in entries
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }


def collection_version(repository_root: Path) -> str:
    catalog = load_object(repository_root / "skill-catalog.json", "skill catalog")
    version = catalog.get("collection_version")
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", version):
        raise CentralizeError("skill catalog collection_version is invalid")
    return version


def folder_hash(path: Path) -> str | None:
    result = hashlib.sha256()
    files: list[tuple[str, bytes]] = []
    try:
        for current, directories, names in os.walk(path, followlinks=False):
            current_path = Path(current)
            if any((current_path / name).is_symlink() for name in directories):
                return None
            directories[:] = [name for name in directories if name not in {"__pycache__", ".git", "node_modules"}]
            for name in names:
                candidate = current_path / name
                if candidate.is_symlink() or not candidate.is_file():
                    return None
                if candidate.suffix in {".pyc", ".pyo"}:
                    continue
                files.append((candidate.relative_to(path).as_posix(), candidate.read_bytes()))
    except OSError:
        return None
    for relative, content in sorted(files):
        result.update(relative.encode("utf-8"))
        result.update(content)
    return result.hexdigest()


def canonical_source(value: object) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.strip().replace("\\", "/").removesuffix(".git")
    for prefix in ("https://github.com/", "https://www.github.com/", "ssh://git@github.com/", "git@github.com:"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
            break
    if "/tree/" in normalized:
        normalized = normalized.split("/tree/", 1)[0]
    elif "@" in normalized:
        normalized = normalized.rsplit("@", 1)[0]
    return normalized.casefold() == SOURCE


def project_entries(project: Path) -> dict[str, dict[str, Any]]:
    value = load_object(project / LOCK_FILE, "project skills lock", {"skills": {}})
    entries = value.get("skills")
    if not isinstance(entries, dict):
        raise CentralizeError("project skills lock has no skills object")
    return {name: entry for name, entry in entries.items() if isinstance(entry, dict)}


def observe_copy(project: Path, agent: str, name: str, entry: dict[str, Any] | None) -> dict[str, Any]:
    lexical_path = project / AGENT_LAYOUTS[agent] / name
    expected_parent = (project / AGENT_LAYOUTS[agent]).resolve()
    if lexical_path.is_symlink():
        return {"agent": agent, "name": name, "path": str(lexical_path), "status": "unsafe", "hash": ""}
    path = lexical_path.resolve()
    if not path.is_relative_to(expected_parent):
        return {"agent": agent, "name": name, "path": str(path), "status": "unsafe", "hash": ""}
    actual_hash = folder_hash(path)
    metadata = load_object(path / METADATA_FILE, f"{name} metadata", {})
    expected_hash = entry.get("computedHash") if isinstance(entry, dict) else None
    verified = (
        actual_hash is not None
        and metadata.get("collection") == COLLECTION
        and metadata.get("skill") == name
        and canonical_source(metadata.get("source"))
        and canonical_source(metadata.get("canonical_repository"))
        and isinstance(metadata.get("version"), str)
        and (
            entry is None
            or (
                canonical_source(entry.get("source"))
                and isinstance(expected_hash, str)
                and expected_hash == actual_hash
            )
        )
    )
    return {
        "agent": agent, "name": name, "path": str(path),
        "status": "verified" if verified else "unverified",
        "version": str(metadata.get("version", "unknown")),
        "hash": actual_hash or "",
    }


def make_plan(project: Path, repository_root: Path) -> dict[str, Any]:
    project = project.resolve()
    known = known_skills(repository_root)
    entries = project_entries(project)
    copies: list[dict[str, Any]] = []
    for agent, relative in AGENT_LAYOUTS.items():
        layout = project / relative
        if not layout.is_dir() or layout.is_symlink():
            continue
        for child in sorted(layout.iterdir()):
            if child.is_dir() and child.name in known:
                copies.append(observe_copy(project, agent, child.name, entries.get(child.name)))
    blockers = [f"{item['agent']}:{item['name']}:{item['status']}" for item in copies if item["status"] != "verified"]
    installers = []
    version = collection_version(repository_root)
    for agent in AGENT_LAYOUTS:
        names = sorted({item["name"] for item in copies if item["agent"] == agent and item["status"] == "verified"})
        if names:
            argv = ["npx", "--yes", f"skills@{CLI_VERSION}", "add", f"{SOURCE}@v{version}"]
            for name in names:
                argv.extend(["--skill", name])
            argv.extend(["--agent", agent, "--copy", "--global", "-y"])
            installers.append({"agent": agent, "skills": names, "argv": argv})
    lock_path = project / LOCK_FILE
    result = {
        "schema_version": 1,
        "operation": "centralize-plan",
        "project": str(project),
        "target_scope": "global",
        "target_version": version,
        "legacy_project_copies": copies,
        "installers": installers,
        "blockers": blockers,
        "changes_required": bool(copies),
        "mutates": False,
        "project_lock_sha256": hashlib.sha256(lock_path.read_bytes()).hexdigest() if lock_path.is_file() else "",
        "user_notice_required": bool(copies),
        "notice": (
            "Kolabse skills are now installed globally. Verified project copies can be migrated; "
            "project configuration remains in the project."
            if copies else "No project-scoped kolabse skill copies were found."
        ),
    }
    result["plan_sha256"] = digest(result)
    return result


def global_install_root(agent: str) -> Path:
    return Path.home().resolve() / AGENT_LAYOUTS[agent]


def verify_global(agent: str, names: list[str], version: str) -> None:
    lock = load_object(Path.home().resolve() / GLOBAL_LOCK, "global skills lock")
    if lock.get("version") != 3 or not isinstance(lock.get("skills"), dict):
        raise CentralizeError("global installer did not create a supported .skill-lock.json")
    for name in names:
        path = global_install_root(agent) / name
        metadata = load_object(path / METADATA_FILE, f"global {name} metadata")
        entry = lock["skills"].get(name)
        expected = entry.get("skillFolderHash") if isinstance(entry, dict) else None
        actual = folder_hash(path)
        if not (
            metadata.get("collection") == COLLECTION
            and metadata.get("skill") == name
            and metadata.get("version") == version
            and canonical_source(metadata.get("source"))
            and canonical_source(metadata.get("canonical_repository"))
            and canonical_source(entry.get("source") if isinstance(entry, dict) else None)
            and isinstance(expected, str) and SHA.fullmatch(expected) and expected == actual
        ):
            raise CentralizeError(f"global verification failed for {agent}:{name}", mutated=True)


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def backup_root(plan_sha256: str) -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    return base / "kolabse" / "skill-installation-backups" / plan_sha256


def apply_plan(project: Path, repository_root: Path, expected_plan: str, yes: bool) -> dict[str, Any]:
    if not yes:
        raise CentralizeError("centralization requires --yes after reviewing the plan")
    plan = make_plan(project, repository_root)
    if expected_plan != plan["plan_sha256"]:
        raise CentralizeError("centralization plan changed after review")
    if plan["blockers"]:
        raise CentralizeError(f"centralization is blocked: {plan['blockers']}")
    if not plan["changes_required"]:
        return {"schema_version": 1, "operation": "centralize", "changed": False, "notice": plan["notice"], "new_task_required": False}
    npx = shutil.which("npx")
    if npx is None:
        raise CentralizeError("npx is required to install global skills")
    backup = backup_root(plan["plan_sha256"])
    if backup.exists():
        raise CentralizeError(f"centralization backup already exists: {backup}")
    mutated = False
    for installer in plan["installers"]:
        argv = [npx, *installer["argv"][1:]]
        completed = subprocess.run(argv, cwd=project.resolve(), shell=False, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace")
        mutated = True
        if completed.returncode:
            raise CentralizeError(f"global installer failed for {installer['agent']} with exit code {completed.returncode}", mutated=True)
        verify_global(installer["agent"], installer["skills"], plan["target_version"])
    backup.mkdir(parents=True)
    lock_path = project.resolve() / LOCK_FILE
    if lock_path.is_file():
        shutil.copy2(lock_path, backup / LOCK_FILE)
    for item in plan["legacy_project_copies"]:
        source = Path(item["path"])
        if folder_hash(source) != item["hash"]:
            raise CentralizeError(f"project copy changed after planning: {item['agent']}:{item['name']}", mutated=True)
        target = backup / item["agent"] / item["name"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target)
    for item in plan["legacy_project_copies"]:
        shutil.rmtree(Path(item["path"]))
    if lock_path.is_file():
        lock = load_object(lock_path, "project skills lock")
        entries = lock.get("skills")
        if not isinstance(entries, dict):
            raise CentralizeError("project skills lock changed after planning", mutated=True)
        for name in {item["name"] for item in plan["legacy_project_copies"]}:
            entries.pop(name, None)
        write_json_atomic(lock_path, lock)
    return {
        "schema_version": 1, "operation": "centralize", "changed": True,
        "migrated": [{"agent": item["agent"], "skill": item["name"]} for item in plan["legacy_project_copies"]],
        "backup": str(backup.resolve()), "project_configuration_preserved": True,
        "notice": "Kolabse skills now use global installations; project-specific configuration was preserved.",
        "new_task_required": True,
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    sub = result.add_subparsers(dest="command", required=True)
    for name in ("plan", "apply"):
        command = sub.add_parser(name)
        command.add_argument("--project-path", type=Path, default=Path.cwd())
        command.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[1])
        command.add_argument("--json", action="store_true")
        if name == "apply":
            command.add_argument("--expected-plan-sha256", required=True)
            command.add_argument("--yes", action="store_true")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        result = (
            make_plan(args.project_path, args.repository_root)
            if args.command == "plan"
            else apply_plan(args.project_path, args.repository_root, args.expected_plan_sha256, args.yes)
        )
        print(json.dumps(result, ensure_ascii=False, indent=2 if args.json else None))
        return 1 if args.command == "plan" and result["blockers"] else 0
    except CentralizeError as error:
        print(json.dumps({"schema_version": 1, "operation": args.command, "error": str(error), "mutated": error.mutated}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
