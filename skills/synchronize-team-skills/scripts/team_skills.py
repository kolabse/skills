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
from urllib.parse import urlparse


SKILL_NAME = "synchronize-team-skills"
REQUIRED_SKILLS = {SKILL_NAME, "synchronize-git-repositories"}
SOURCE = "kolabse/skills"
CANONICAL_SOURCE = "https://github.com/kolabse/skills"
CLI_VERSION = "1.5.22"
DOCUMENT_NAME = "team-agent-skills.md"
START = "<!-- synchronize-team-skills:manifest:start -->"
END = "<!-- synchronize-team-skills:manifest:end -->"
AGENT_LAYOUTS = {"codex": ".agents/skills", "claude-code": ".claude/skills"}
KNOWN_SKILLS = {
    "coordinate-code-documentation-repositories",
    "develop-with-test-first-evidence",
    "diagnose-software-defects",
    "discover-skill-candidates",
    "execute-configured-gitflow-releases",
    "execute-verified-development-lifecycle",
    "maintain-project-digest",
    "maintain-work-log",
    "notify-via-telegram",
    "operate-yandex-cloud",
    "orchestrate-agent-work",
    "report-skill-feedback",
    "release-skill-collection",
    "resolve-git-conflicts",
    "review-code-changes",
    "sync-project-context",
    "synchronize-git-repositories",
    "synchronize-team-skills",
    "verify-before-push",
}
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
    if value.get("scope") != "global" or value.get("extras_policy") != "preserve":
        raise TeamSkillsError("team manifest must use global scope and preserve extras")
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
    unknown_skills = sorted(set(skills) - KNOWN_SKILLS)
    if unknown_skills:
        raise TeamSkillsError(f"team manifest contains unknown collection skills {unknown_skills}")
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


def user_home() -> Path:
    return Path.home().resolve()


def global_layout(agent: str) -> Path:
    return user_home() / AGENT_LAYOUTS[agent]


def global_lock_path() -> Path:
    return user_home() / ".agents/.skill-lock.json"


def read_lock_entries(_project_root: Path) -> dict[str, dict[str, Any]]:
    try:
        value = json.loads(global_lock_path().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as error:
        raise TeamSkillsError(f"global .skill-lock.json is unreadable or invalid: {error}") from error
    if not isinstance(value, dict) or value.get("version") != 3:
        raise TeamSkillsError("global .skill-lock.json must use version 3")
    entries = value.get("skills") if isinstance(value, dict) else None
    if not isinstance(entries, dict):
        raise TeamSkillsError("global .skill-lock.json field 'skills' must be an object")
    return {name: entry for name, entry in entries.items() if isinstance(entry, dict)}


def canonical_github_source(source: str) -> bool:
    value = source.strip().replace("\\", "/")
    if value.startswith("git@github.com:"):
        value = value.removeprefix("git@github.com:")
    elif value.startswith("ssh://git@github.com/"):
        value = value.removeprefix("ssh://git@github.com/")
    elif "://" in value:
        parsed = urlparse(value)
        if parsed.hostname not in {"github.com", "www.github.com"}:
            return False
        value = parsed.path.lstrip("/")
    if value.endswith(".git"):
        value = value[:-4]
    if "/tree/" in value:
        value, _ref = value.split("/tree/", 1)
    elif "@" in value:
        value, _ref = value.rsplit("@", 1)
    return value.casefold() == SOURCE


def verified_lock_source(
    project_root: Path,
    name: str,
    entry: dict[str, Any] | None,
) -> bool:
    if not isinstance(entry, dict):
        return False
    source = entry.get("source")
    source_type = entry.get("sourceType")
    if not isinstance(source, str) or not source.strip():
        return False
    if source_type in {None, "github"}:
        return canonical_github_source(source)
    if source_type != "local":
        return False
    checkout = Path(source).expanduser()
    if not checkout.is_absolute():
        checkout = project_root / checkout
    try:
        checkout = checkout.resolve()
        plugin = load_object(
            checkout / ".codex-plugin/plugin.json", "local source plugin manifest"
        )
        catalog = load_object(checkout / "skill-catalog.json", "local source catalog")
    except (OSError, TeamSkillsError):
        return False
    entries = catalog.get("skills")
    names = {
        item.get("name")
        for item in entries
        if isinstance(item, dict)
    } if isinstance(entries, list) else set()
    return (
        plugin.get("name") == "kolabse-skills"
        and isinstance(plugin.get("repository"), str)
        and canonical_github_source(plugin["repository"])
        and name in names
        and (checkout / "skills" / name / "SKILL.md").is_file()
    )


def skill_folder_hash(path: Path) -> str | None:
    files: list[tuple[str, bytes]] = []
    try:
        for current, directories, names in os.walk(path, followlinks=False):
            current_path = Path(current)
            if any((current_path / name).is_symlink() for name in directories):
                return None
            directories[:] = [
                name
                for name in directories
                if name not in {".git", "node_modules", "__pycache__"}
            ]
            for name in names:
                candidate = current_path / name
                if candidate.suffix in {".pyc", ".pyo"}:
                    continue
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
    project_root: Path,
    path: Path,
    name: str,
    required_version: str,
    lock_entry: dict[str, Any] | None,
) -> dict[str, Any]:
    lock_verified = verified_lock_source(project_root, name, lock_entry)
    source_kind = (
        "local"
        if lock_verified and lock_entry.get("sourceType") == "local"
        else "github" if lock_verified else "missing"
    )
    result: dict[str, Any] = {
        "name": name,
        "path": str(path),
        "installed": path.is_dir(),
        "version": "missing",
        "provenance": "missing",
        "source_kind": source_kind,
        "state": "missing",
        "project_override": False,
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
        and isinstance(metadata.get("source"), str)
        and canonical_github_source(metadata["source"])
        and isinstance(metadata.get("canonical_repository"), str)
        and canonical_github_source(metadata["canonical_repository"])
    )
    version = metadata.get("version") if isinstance(metadata, dict) else None
    expected_hash = (
        lock_entry.get("skillFolderHash", lock_entry.get("computedHash"))
        if isinstance(lock_entry, dict) else None
    )
    actual_hash = skill_folder_hash(path)
    source_content_verified = True
    if source_kind == "local":
        source = Path(lock_entry["source"]).expanduser()
        if not source.is_absolute():
            source = project_root / source
        source_hash = skill_folder_hash(source.resolve() / "skills" / name)
        source_content_verified = source_hash is not None and actual_hash == source_hash
    content_verified = (
        lock_verified
        and isinstance(expected_hash, str)
        and HASH_PATTERN.fullmatch(expected_hash) is not None
        and actual_hash == expected_hash
        and source_content_verified
    )
    if not valid_identity or not isinstance(version, str) or not content_verified:
        result.update(version=str(version or "unknown"), provenance="unverified", state="unverified")
        return result
    result.update(
        version=version,
        provenance="verified",
        source_kind=source_kind,
        state=version_state(version, required_version),
    )
    return result


def verified_extra(
    project_root: Path,
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
    observed = observe_skill(project_root, path, path.name, version, lock_entry)
    if observed["state"] != "current":
        return None
    return {"name": path.name, "version": version, "action": "preserve"}


def inspect(project_root: Path, documentation_root: str | None) -> dict[str, Any]:
    project_root = project_root.resolve()
    path, manifest = read_manifest(project_root, documentation_root)
    desired = set(manifest["skills"])
    lock_entries = read_lock_entries(project_root)
    agents: list[dict[str, Any]] = []
    ready = True
    for agent in manifest["agents"]:
        layout = global_layout(agent)
        layout_safe = not layout.is_symlink() and layout.resolve().is_relative_to(user_home())
        if layout_safe:
            skills = [
                observe_skill(
                    project_root,
                    layout / name,
                    name,
                    manifest["collection_version"],
                    lock_entries.get(name),
                )
                for name in manifest["skills"]
            ]
            for item in skills:
                item["project_override"] = (
                    project_root / AGENT_LAYOUTS[agent] / item["name"]
                ).is_dir()
        else:
            skills = [
                {
                    "name": name,
                    "path": str(layout / name),
                    "installed": (layout / name).is_dir(),
                    "version": "unknown",
                    "provenance": "unsafe-layout",
                    "source_kind": "unknown",
                    "state": "unverified",
                    "project_override": (
                        project_root / AGENT_LAYOUTS[agent] / name
                    ).is_dir(),
                }
                for name in manifest["skills"]
            ]
        extras = []
        unsafe_extras = []
        if layout_safe and layout.is_dir():
            unsafe_extras = [
                {
                    "name": child.name,
                    "path": str(child),
                    "version": "unknown",
                    "provenance": "unsafe-symlink",
                    "state": "unverified",
                    "action": "preserve",
                }
                for child in sorted(layout.iterdir())
                if child.name not in desired and child.is_symlink()
            ]
            extras = [
                item
                for child in sorted(layout.iterdir())
                if not child.is_symlink()
                and (item := verified_extra(project_root, child, desired, lock_entries.get(child.name)))
            ]
        agent_ready = (
            all(
                item["state"] == "current" and not item["project_override"]
                for item in skills
            )
            and not unsafe_extras
        )
        ready = ready and agent_ready
        agents.append(
            {
                "agent": agent,
                "layout": str(layout),
                "layout_safe": layout_safe,
                "ready": agent_ready,
                "skills": skills,
                "extras": extras,
                "unsafe_extras": unsafe_extras,
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
            "scope": "global",
            "agents": args.agent or sorted(AGENT_LAYOUTS),
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
            "This reviewed document declares the globally installed agent skills shared by the team.\n"
            "Project configuration and user secrets remain outside installed skill folders.\n\n"
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
        observed = {item["name"]: item for item in agent["skills"]}
        states = {name: item["state"] for name, item in observed.items()}
        for name, item in observed.items():
            if item["project_override"]:
                blockers.append(
                    f"{agent['agent']}:{name}:project-copy-must-be-centralized"
                )
        for name, state in states.items():
            if state in {"unverified", "newer-than-required", "version-mismatch"}:
                blockers.append(f"{agent['agent']}:{name}:{state}")
            elif state in {"missing", "outdated"} and observed[name]["source_kind"] == "local":
                blockers.append(f"{agent['agent']}:{name}:{state}-local-source")
        for extra in agent["unsafe_extras"]:
            blockers.append(
                f"{agent['agent']}:extra:{extra['name']}:{extra['provenance']}"
            )
        selected = [
            name
            for name, state in states.items()
            if state in {"missing", "outdated"}
            and observed[name]["source_kind"] != "local"
        ]
        if selected and not any(item.startswith(f"{agent['agent']}:") for item in blockers):
            argv = ["npx", "--yes", f"skills@{CLI_VERSION}", "add", f"{SOURCE}@v{status['collection_version']}"]
            for name in sorted(selected):
                argv.extend(["--skill", name])
            argv.extend(["--agent", agent["agent"], "--copy", "--global", "-y"])
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
