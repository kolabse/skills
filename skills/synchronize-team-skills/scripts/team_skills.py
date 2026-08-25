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


SKILL_NAME = "synchronize-team-skills"
REQUIRED_SKILLS = {SKILL_NAME, "synchronize-git-repositories"}
SOURCE = "kolabse/skills"
CANONICAL_SOURCE = "https://github.com/kolabse/skills"
CLI_VERSION = "1.5.22"
DOCUMENT_NAME = "team-agent-skills.md"
START = "<!-- synchronize-team-skills:manifest:start -->"
END = "<!-- synchronize-team-skills:manifest:end -->"
AGENT_LAYOUTS = {"codex": ".agents/skills", "claude-code": ".claude/skills"}
NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
VERSION_PATTERN = re.compile(
    r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?$"
)
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_FIELDS = {
    "schema_version",
    "source",
    "collection_version",
    "scope",
    "agents",
    "skills",
    "extras_policy",
}


class TeamSkillsError(RuntimeError):
    def __init__(self, message: str, *, mutates_environment: bool = False):
        super().__init__(message)
        self.mutates_environment = mutates_environment


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def plan_binding(value: object, field: str = "") -> object:
    if isinstance(value, dict):
        return {key: plan_binding(item, key) for key, item in value.items()}
    if isinstance(value, list):
        return [plan_binding(item, field) for item in value]
    if isinstance(value, str) and field in {"document", "layout", "path"}:
        return os.path.normcase(value)
    return value


def load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise TeamSkillsError(f"{label} is missing: {path}") from error
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise TeamSkillsError(f"{label} is invalid JSON: {path}: {error}") from error
    if not isinstance(value, dict):
        raise TeamSkillsError(f"{label} must be a JSON object: {path}")
    return value


def default_collection_version() -> str:
    metadata = load_object(Path(__file__).resolve().parents[1] / "collection-metadata.json", "collection metadata")
    version = metadata.get("version")
    if not isinstance(version, str) or not VERSION_PATTERN.fullmatch(version):
        raise TeamSkillsError("installed collection metadata has no valid version")
    return version


def validate_manifest(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != REQUIRED_FIELDS:
        raise TeamSkillsError("team manifest fields do not match schema version 1")
    if value.get("schema_version") != 1:
        raise TeamSkillsError("team manifest schema_version must be 1")
    if value.get("source") != SOURCE:
        raise TeamSkillsError(f"team manifest source must be {SOURCE}")
    version = value.get("collection_version")
    if not isinstance(version, str) or not VERSION_PATTERN.fullmatch(version):
        raise TeamSkillsError("team manifest collection_version is invalid")
    if value.get("scope") != "project" or value.get("extras_policy") != "preserve":
        raise TeamSkillsError("team manifest must use project scope and preserve extras")
    agents = value.get("agents")
    if (
        not isinstance(agents, list)
        or not agents
        or not all(agent in AGENT_LAYOUTS for agent in agents)
        or len(agents) != len(set(agents))
    ):
        raise TeamSkillsError("team manifest agents are invalid or duplicated")
    skills = value.get("skills")
    if (
        not isinstance(skills, list)
        or not skills
        or not all(isinstance(name, str) and NAME_PATTERN.fullmatch(name) for name in skills)
        or len(skills) != len(set(skills))
    ):
        raise TeamSkillsError("team manifest skills are invalid or duplicated")
    missing_dependencies = sorted(REQUIRED_SKILLS - set(skills))
    if missing_dependencies:
        raise TeamSkillsError(
            f"team manifest must include bootstrap dependencies {missing_dependencies}"
        )
    normalized = dict(value)
    normalized["agents"] = sorted(agents)
    normalized["skills"] = sorted(skills)
    return normalized


def document_block(manifest: dict[str, Any]) -> str:
    payload = json.dumps(manifest, indent=2, ensure_ascii=False)
    return f"{START}\n```json\n{payload}\n```\n{END}"


def parse_document(text: str) -> dict[str, Any]:
    start_count = text.count(START)
    end_count = text.count(END)
    if start_count != 1 or end_count != 1:
        raise TeamSkillsError("team document must contain exactly one complete managed manifest block")
    start = text.index(START)
    end = text.index(END)
    if end < start:
        raise TeamSkillsError("team document managed markers are out of order")
    end += len(END)
    managed = text[start:end]
    match = re.fullmatch(
        re.escape(START)
        + r"\r?\n```json\r?\n(?P<payload>.*?)\r?\n```\r?\n"
        + re.escape(END),
        managed,
        flags=re.DOTALL,
    )
    if not match:
        raise TeamSkillsError("team document managed block has an unfamiliar structure")
    try:
        value = json.loads(match.group("payload"))
    except json.JSONDecodeError as error:
        raise TeamSkillsError(f"team document manifest is invalid JSON: {error}") from error
    return validate_manifest(value)


def resolve_documentation_root(project_root: Path, explicit: str | None) -> Path:
    if explicit:
        requested = Path(explicit)
        root = (
            requested.resolve()
            if requested.is_absolute()
            else (project_root / requested).resolve()
        )
        if not root.is_dir():
            raise TeamSkillsError(f"documentation root does not exist: {root}")
        return root
    candidates = [project_root / name for name in ("docs", "documentation", "doc")]
    existing = [path.resolve() for path in candidates if path.is_dir()]
    containing = [path for path in existing if (path / DOCUMENT_NAME).is_file()]
    if len(containing) == 1:
        return containing[0]
    if len(containing) > 1 or len(existing) > 1:
        raise TeamSkillsError("project documentation location is ambiguous")
    if len(existing) == 1:
        return existing[0]
    raise TeamSkillsError("project documentation location is not configured")


def document_path(project_root: Path, documentation_root: str | None) -> Path:
    return resolve_documentation_root(project_root, documentation_root) / DOCUMENT_NAME


def read_manifest(project_root: Path, documentation_root: str | None) -> tuple[Path, dict[str, Any]]:
    path = document_path(project_root, documentation_root)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise TeamSkillsError(f"team skill document is missing: {path}") from error
    except UnicodeDecodeError as error:
        raise TeamSkillsError(f"team skill document is not UTF-8: {path}") from error
    return path, parse_document(text)


def version_state(observed: str, required: str) -> str:
    if observed == required:
        return "current"
    observed_match = VERSION_PATTERN.fullmatch(observed)
    required_match = VERSION_PATTERN.fullmatch(required)
    if not observed_match or not required_match:
        return "version-mismatch"
    observed_precedence = observed.split("+", 1)[0]
    required_precedence = required.split("+", 1)[0]
    if observed_precedence == required_precedence:
        return "version-mismatch"
    observed_parts = observed_precedence.split("-", 1)
    required_parts = required_precedence.split("-", 1)
    observed_core = tuple(int(item) for item in observed_parts[0].split("."))
    required_core = tuple(int(item) for item in required_parts[0].split("."))
    if observed_core < required_core:
        return "outdated"
    if observed_core > required_core:
        return "newer-than-required"
    observed_pre = observed_parts[1].split(".") if len(observed_parts) == 2 else None
    required_pre = required_parts[1].split(".") if len(required_parts) == 2 else None
    if observed_pre is None:
        return "newer-than-required"
    if required_pre is None:
        return "outdated"
    for observed_item, required_item in zip(observed_pre, required_pre):
        if observed_item == required_item:
            continue
        observed_numeric = observed_item.isdigit()
        required_numeric = required_item.isdigit()
        if observed_numeric and required_numeric:
            return "outdated" if int(observed_item) < int(required_item) else "newer-than-required"
        if observed_numeric != required_numeric:
            return "outdated" if observed_numeric else "newer-than-required"
        return "outdated" if observed_item < required_item else "newer-than-required"
    return "outdated" if len(observed_pre) < len(required_pre) else "newer-than-required"


def read_lock_entries(project_root: Path) -> dict[str, dict[str, Any]]:
    try:
        value = json.loads((project_root / "skills-lock.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as error:
        raise TeamSkillsError(f"skills-lock.json is unreadable or invalid: {error}") from error
    entries = value.get("skills") if isinstance(value, dict) else None
    if not isinstance(entries, dict):
        raise TeamSkillsError("skills-lock.json field 'skills' must be an object")
    return {name: entry for name, entry in entries.items() if isinstance(entry, dict)}


def canonical_lock_entry(entry: dict[str, Any] | None) -> bool:
    if not isinstance(entry, dict) or entry.get("sourceType") not in {None, "github"}:
        return False
    source = entry.get("source")
    if not isinstance(source, str):
        return False
    normalized = source.strip().lower().replace("\\", "/")
    normalized = re.sub(r"@v?[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9a-z.-]+)?$", "", normalized)
    normalized = re.sub(r"/tree/v?[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9a-z.-]+)?$", "", normalized)
    normalized = normalized.removesuffix(".git").rstrip("/")
    return normalized in {
        SOURCE,
        CANONICAL_SOURCE,
        "git@github.com:kolabse/skills",
    }


def skill_folder_hash(path: Path) -> str | None:
    files: list[tuple[str, bytes]] = []
    try:
        for current, directories, names in os.walk(path, followlinks=False):
            current_path = Path(current)
            if any((current_path / name).is_symlink() for name in directories):
                return None
            directories[:] = [
                name for name in directories if name not in {".git", "node_modules"}
            ]
            for name in names:
                candidate = current_path / name
                if candidate.is_symlink() or not candidate.is_file():
                    return None
                relative = candidate.relative_to(path).as_posix()
                files.append((relative, candidate.read_bytes()))
    except OSError:
        return None
    result = hashlib.sha256()
    for relative, content in sorted(files):
        result.update(relative.encode("utf-8"))
        result.update(content)
    return result.hexdigest()


def observe_skill(
    path: Path,
    name: str,
    required_version: str,
    lock_entry: dict[str, Any] | None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "name": name,
        "path": str(path),
        "installed": path.is_dir(),
        "version": "missing",
        "provenance": "missing",
        "state": "missing",
        "shadowing_risk": path.is_dir(),
    }
    if not path.is_dir():
        return result
    if path.is_symlink():
        result.update(version="unknown", provenance="unsafe-symlink", state="unverified")
        return result
    metadata_path = path / "collection-metadata.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
        result.update(version="unknown", provenance="unverified", state="unverified")
        return result
    valid_identity = (
        isinstance(metadata, dict)
        and metadata.get("collection") == "kolabse-skills"
        and metadata.get("skill") == name
        and metadata.get("source") == CANONICAL_SOURCE
        and metadata.get("canonical_repository") == CANONICAL_SOURCE
    )
    version = metadata.get("version") if isinstance(metadata, dict) else None
    expected_hash = lock_entry.get("computedHash") if isinstance(lock_entry, dict) else None
    actual_hash = skill_folder_hash(path)
    content_verified = (
        canonical_lock_entry(lock_entry)
        and isinstance(expected_hash, str)
        and HASH_PATTERN.fullmatch(expected_hash) is not None
        and actual_hash == expected_hash
    )
    if not valid_identity or not isinstance(version, str) or not content_verified:
        result.update(version=str(version or "unknown"), provenance="unverified", state="unverified")
        return result
    result.update(version=version, provenance="verified", state=version_state(version, required_version))
    return result


def verified_extra(
    path: Path,
    desired: set[str],
    lock_entry: dict[str, Any] | None,
) -> dict[str, str] | None:
    if not path.is_dir() or path.name in desired:
        return None
    try:
        metadata = json.loads((path / "collection-metadata.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(metadata, dict) or metadata.get("collection") != "kolabse-skills":
        return None
    version = metadata.get("version")
    if not isinstance(version, str):
        return None
    observed = observe_skill(path, path.name, version, lock_entry)
    if observed["state"] != "current":
        return None
    return {"name": path.name, "version": version, "action": "preserve"}


def inspect(project_root: Path, documentation_root: str | None) -> dict[str, Any]:
    path, manifest = read_manifest(project_root, documentation_root)
    desired = set(manifest["skills"])
    lock_entries = read_lock_entries(project_root)
    agents: list[dict[str, Any]] = []
    ready = True
    for agent in manifest["agents"]:
        layout = project_root / AGENT_LAYOUTS[agent]
        layout_safe = not layout.is_symlink() and layout.resolve().is_relative_to(project_root)
        if layout_safe:
            skills = [
                observe_skill(
                    layout / name,
                    name,
                    manifest["collection_version"],
                    lock_entries.get(name),
                )
                for name in manifest["skills"]
            ]
        else:
            skills = [
                {
                    "name": name,
                    "path": str(layout / name),
                    "installed": (layout / name).is_dir(),
                    "version": "unknown",
                    "provenance": "unsafe-layout",
                    "state": "unverified",
                    "shadowing_risk": (layout / name).is_dir(),
                }
                for name in manifest["skills"]
            ]
        extras = []
        if layout_safe and layout.is_dir():
            extras = [
                item
                for child in sorted(layout.iterdir())
                if (item := verified_extra(child, desired, lock_entries.get(child.name)))
            ]
        agent_ready = all(item["state"] == "current" for item in skills)
        ready = ready and agent_ready
        agents.append(
            {
                "agent": agent,
                "layout": str(layout),
                "layout_safe": layout_safe,
                "ready": agent_ready,
                "skills": skills,
                "extras": extras,
            }
        )
    return {
        "schema_version": 1,
        "mode": "status",
        "configured": True,
        "document": str(path),
        "manifest_sha256": digest(manifest),
        "source": manifest["source"],
        "collection_version": manifest["collection_version"],
        "extras_policy": manifest["extras_policy"],
        "agents": agents,
        "ready": ready,
        "mutates_environment": False,
    }


def configure(args: argparse.Namespace) -> dict[str, Any]:
    project_root = Path(args.project_root).resolve()
    root = resolve_documentation_root(project_root, args.documentation_root)
    path = root / DOCUMENT_NAME
    manifest = validate_manifest(
        {
            "schema_version": 1,
            "source": SOURCE,
            "collection_version": args.collection_version or default_collection_version(),
            "scope": "project",
            "agents": args.agent or ["codex"],
            "skills": args.skill or sorted(REQUIRED_SKILLS),
            "extras_policy": "preserve",
        }
    )
    block = document_block(manifest)
    if path.exists():
        original = path.read_text(encoding="utf-8")
        if START in original or END in original:
            parse_document(original)
            start = original.index(START)
            end = original.index(END, start) + len(END)
            updated = original[:start] + block + original[end:]
        else:
            updated = original.rstrip() + "\n\n" + block + "\n"
    else:
        original = ""
        updated = (
            "# Team agent skills\n\n"
            "This reviewed document declares the project-scoped agent skills shared by the team.\n"
            "Local locks and user configuration remain machine-specific.\n\n"
            f"{block}\n"
        )
    changed = updated != original
    if changed:
        path.write_text(updated, encoding="utf-8", newline="\n")
    return {
        "schema_version": 1,
        "mode": "configure",
        "changed": changed,
        "document": str(path),
        "manifest_sha256": digest(manifest),
        "mutates_repository": changed,
    }


def make_plan(project_root: Path, documentation_root: str | None) -> dict[str, Any]:
    status = inspect(project_root, documentation_root)
    blockers: list[str] = []
    installers: list[dict[str, Any]] = []
    for agent in status["agents"]:
        states = {item["name"]: item["state"] for item in agent["skills"]}
        for name, state in states.items():
            if state in {"unverified", "newer-than-required", "version-mismatch"}:
                blockers.append(f"{agent['agent']}:{name}:{state}")
        selected = [name for name, state in states.items() if state in {"missing", "outdated"}]
        if selected and not any(item.startswith(f"{agent['agent']}:") for item in blockers):
            argv = ["npx", "--yes", f"skills@{CLI_VERSION}", "add", f"{SOURCE}@v{status['collection_version']}"]
            for name in sorted(states):
                argv.extend(["--skill", name])
            argv.extend(["--agent", agent["agent"], "--copy", "-y"])
            installers.append({"agent": agent["agent"], "selected": selected, "argv": argv})
    result = {
        "schema_version": 1,
        "mode": "plan",
        "document": status["document"],
        "manifest_sha256": status["manifest_sha256"],
        "collection_version": status["collection_version"],
        "installers": installers,
        "blockers": blockers,
        "ready": not blockers,
        "changes_required": bool(installers),
        "status": status,
        "mutates_environment": False,
    }
    result["plan_sha256"] = digest(plan_binding(result))
    return result


def apply(args: argparse.Namespace) -> dict[str, Any]:
    if not args.yes:
        raise TeamSkillsError("apply requires --yes after explicit approval")
    project_root = Path(args.project_root).resolve()
    plan = make_plan(project_root, args.documentation_root)
    if args.expected_manifest_sha256 != plan["manifest_sha256"]:
        raise TeamSkillsError("team manifest changed after planning")
    if args.expected_plan_sha256 != plan["plan_sha256"]:
        raise TeamSkillsError("team skill plan changed after review")
    if plan["blockers"]:
        raise TeamSkillsError(f"team skill alignment is blocked: {plan['blockers']}")
    if plan["installers"] and shutil.which("npx") is None:
        raise TeamSkillsError("npx is required to align team skills")
    completed_agents: list[str] = []
    mutated = False
    for installer in plan["installers"]:
        completed = subprocess.run(
            installer["argv"],
            cwd=project_root,
            shell=False,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        mutated = True
        if completed.returncode:
            raise TeamSkillsError(
                f"skill installer failed for {installer['agent']} with exit code {completed.returncode}",
                mutates_environment=True,
            )
        completed_agents.append(installer["agent"])
    after = inspect(project_root, args.documentation_root)
    if not after["ready"]:
        raise TeamSkillsError(
            "installer completed but project skills do not match the team manifest",
            mutates_environment=mutated,
        )
    return {
        "schema_version": 1,
        "mode": "apply",
        "changed": mutated,
        "completed_agents": completed_agents,
        "manifest_sha256": after["manifest_sha256"],
        "ready": True,
        "new_task_required": mutated,
        "mutates_environment": mutated,
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    sub = result.add_subparsers(dest="command", required=True)

    def common(name: str) -> argparse.ArgumentParser:
        command = sub.add_parser(name)
        command.add_argument("--project-root", required=True)
        command.add_argument("--documentation-root")
        command.add_argument("--json", action="store_true")
        return command

    configure_parser = common("configure")
    configure_parser.add_argument("--collection-version")
    configure_parser.add_argument("--agent", action="append", choices=sorted(AGENT_LAYOUTS))
    configure_parser.add_argument("--skill", action="append")
    common("status")
    common("plan")
    apply_parser = common("apply")
    apply_parser.add_argument("--expected-manifest-sha256", required=True)
    apply_parser.add_argument("--expected-plan-sha256", required=True)
    apply_parser.add_argument("--yes", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "configure":
            result = configure(args)
        elif args.command == "status":
            result = inspect(Path(args.project_root).resolve(), args.documentation_root)
        elif args.command == "plan":
            result = make_plan(Path(args.project_root).resolve(), args.documentation_root)
        else:
            result = apply(args)
        print(json.dumps(result, indent=2 if args.json else None, ensure_ascii=False))
        if args.command == "status":
            return 0 if result["ready"] else 1
        if args.command == "plan":
            return 0 if result["ready"] else 1
        return 0
    except TeamSkillsError as error:
        print(
            json.dumps(
                {
                    "schema_version": 1,
                    "error": str(error),
                    "mutates_environment": error.mutates_environment,
                },
                ensure_ascii=False,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
