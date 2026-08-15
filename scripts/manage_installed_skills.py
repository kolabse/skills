from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


COLLECTION = "kolabse-skills"
COLLECTION_VERSION = "1.11.0"
SKILLS_CLI_VERSION = "1.5.22"
LOCK_FILE = "skills-lock.json"
METADATA_FILE = "collection-metadata.json"
CANONICAL_REPOSITORY = "https://github.com/kolabse/skills"
CANONICAL_SLUG = "kolabse/skills"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
KNOWN_SKILLS = {
    "maintain-work-log",
    "notify-via-telegram",
    "operate-yandex-cloud",
    "release-skill-collection",
    "sync-project-context",
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


def default_global_root() -> Path:
    return Path.home() / ".agents"


def normalize_github_source(source: str) -> dict[str, str] | None:
    value = source.strip().replace("\\", "/")
    ref = ""
    if value.startswith("git@github.com:"):
        value = value.removeprefix("git@github.com:")
    elif value.startswith("ssh://git@github.com/"):
        value = value.removeprefix("ssh://git@github.com/")
    elif "://" in value:
        parsed = urlparse(value)
        if parsed.hostname not in {"github.com", "www.github.com"}:
            return None
        value = parsed.path.lstrip("/")
    if value.endswith(".git"):
        value = value[:-4]
    if "/tree/" in value:
        value, ref = value.split("/tree/", 1)
    elif "@" in value:
        value, ref = value.rsplit("@", 1)
    if value.casefold() != CANONICAL_SLUG:
        return None
    identity = CANONICAL_REPOSITORY + (f"@{ref}" if ref else "")
    return {"kind": "github", "identity": identity, "canonical_repository": CANONICAL_REPOSITORY}


def validate_local_source(path: Path, skill: str) -> str:
    root = path.resolve()
    manifest = load_object(root / ".codex-plugin/plugin.json", "local source plugin manifest")
    catalog = load_object(root / "skill-catalog.json", "local source catalog")
    repository = manifest.get("repository")
    if manifest.get("name") != COLLECTION or normalize_github_source(str(repository or "")) is None:
        raise ManagerError(f"local source is not the canonical {COLLECTION} collection: {root}")
    entries = catalog.get("skills")
    names = {
        entry.get("name")
        for entry in entries
        if isinstance(entry, dict)
    } if isinstance(entries, list) else set()
    if skill not in names or not (root / "skills" / skill / "SKILL.md").is_file():
        raise ManagerError(f"local source does not contain catalog skill {skill}: {root}")
    return str(root)


def classify_lock_source(
    project: Path,
    name: str,
    entry: dict[str, Any],
    trusted_development_sources: dict[str, Path] | None = None,
) -> dict[str, Any]:
    source = entry.get("source")
    source_type = entry.get("sourceType")
    if not isinstance(source, str) or not source.strip():
        return {"valid": False, "kind": "unknown", "identity": "", "error": "lock source is missing"}
    github = normalize_github_source(source)
    if source_type in {None, "github"} and github is not None:
        return {"valid": True, "error": "", **github}
    if source_type == "local":
        candidate = Path(source).expanduser()
        if not candidate.is_absolute():
            candidate = project.resolve() / candidate
        try:
            identity = validate_local_source(candidate, name)
        except ManagerError as error:
            return {"valid": False, "kind": "local", "identity": str(candidate), "error": str(error)}
        return {
            "valid": True,
            "kind": "local",
            "identity": identity,
            "canonical_repository": CANONICAL_REPOSITORY,
            "error": "",
        }
    trusted = trusted_development_sources or {}
    if source in trusted:
        try:
            identity = validate_local_source(trusted[source], name)
        except ManagerError as error:
            return {"valid": False, "kind": "development", "identity": source, "error": str(error)}
        return {
            "valid": True,
            "kind": "development",
            "identity": f"{source} -> {identity}",
            "canonical_repository": CANONICAL_REPOSITORY,
            "error": "",
        }
    return {
        "valid": False,
        "kind": str(source_type or "unknown"),
        "identity": source,
        "error": f"lock source is not canonical {CANONICAL_SLUG} or a verified local checkout",
    }


def read_project_state(
    project: Path, trusted_development_sources: dict[str, Path] | None = None
) -> dict[str, Any]:
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
        metadata_present = metadata_path.is_file()
        try:
            metadata = load_object(metadata_path, f"{name} metadata")
        except ManagerError as error:
            metadata_error = str(error)
        metadata_schema = metadata.get("schema_version")
        metadata_valid = (
            metadata_schema in {1, 2}
            and metadata.get("collection") == COLLECTION
            and metadata.get("skill") == name
            and normalize_github_source(str(metadata.get("source", ""))) is not None
            and (
                metadata_schema == 1
                or normalize_github_source(
                    str(metadata.get("canonical_repository", ""))
                )
                is not None
            )
        )
        source_state = classify_lock_source(root, name, entry, trusted_development_sources)
        if source_state["valid"] and metadata_valid:
            provenance_status = "verified"
        elif source_state["valid"] and not metadata_present:
            provenance_status = "legacy-unverified"
        else:
            provenance_status = "mismatch"
        skills.append(
            {
                "name": name,
                "installed": skill_root.is_dir(),
                "path": str(skill_root),
                "source": entry.get("source", ""),
                "computed_hash": entry.get("computedHash", ""),
                "collection": metadata.get("collection", ""),
                "version": metadata.get("version", "unknown"),
                "metadata_valid": metadata_valid,
                "metadata_error": metadata_error,
                "provenance_status": provenance_status,
                "source_kind": source_state["kind"],
                "source_identity": source_state["identity"],
                "provenance_error": source_state["error"],
                "legacy_adoption_available": provenance_status == "legacy-unverified",
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


def read_global_state(
    global_root: Path | None = None,
    trusted_development_sources: dict[str, Path] | None = None,
) -> dict[str, Any]:
    root = (global_root or default_global_root()).expanduser().resolve()
    lock_path = root / ".skill-lock.json"
    lock = load_object(lock_path, "global skills lock")
    if lock.get("version") != 3:
        raise ManagerError("unsupported global skills lock version; expected .skill-lock.json v3")
    entries = lock.get("skills")
    if not isinstance(entries, dict):
        raise ManagerError("global .skill-lock.json field 'skills' must be an object")
    installed_root = root / "skills"
    skills: list[dict[str, Any]] = []
    for name in sorted(set(entries) & KNOWN_SKILLS):
        entry = entries[name]
        if not isinstance(entry, dict):
            raise ManagerError(f"global lock entry for {name} must be an object")
        skill_root = installed_root / name
        metadata_path = skill_root / METADATA_FILE
        metadata: dict[str, Any] = {}
        metadata_error = ""
        metadata_present = metadata_path.is_file()
        try:
            metadata = load_object(metadata_path, f"{name} metadata")
        except ManagerError as error:
            metadata_error = str(error)
        metadata_schema = metadata.get("schema_version")
        metadata_valid = (
            metadata_schema in {1, 2}
            and metadata.get("collection") == COLLECTION
            and metadata.get("skill") == name
            and normalize_github_source(str(metadata.get("source", ""))) is not None
            and (
                metadata_schema == 1
                or normalize_github_source(str(metadata.get("canonical_repository", "")))
                is not None
            )
        )
        source_state = classify_lock_source(root, name, entry, trusted_development_sources)
        if source_state["valid"] and metadata_valid:
            provenance_status = "verified"
        elif source_state["valid"] and not metadata_present:
            provenance_status = "legacy-unverified"
        else:
            provenance_status = "mismatch"
        digest = entry.get("skillFolderHash", entry.get("computedHash", ""))
        skills.append(
            {
                "name": name,
                "installed": skill_root.is_dir(),
                "path": str(skill_root),
                "source": entry.get("source", ""),
                "computed_hash": digest,
                "collection": metadata.get("collection", ""),
                "version": metadata.get("version", "unknown"),
                "metadata_valid": metadata_valid,
                "metadata_error": metadata_error,
                "provenance_status": provenance_status,
                "source_kind": source_state["kind"],
                "source_identity": source_state["identity"],
                "provenance_error": source_state["error"],
                "legacy_adoption_available": provenance_status == "legacy-unverified",
            }
        )
    return {
        "schema_version": 1,
        "collection": COLLECTION,
        "scope": "global",
        "global_root": str(root),
        "lock_file": str(lock_path),
        "skills": skills,
    }


def print_state(state: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True))
        return
    print(f"Collection: {state['collection']} ({state['scope']})")
    for skill in state["skills"]:
        marker = "ok" if skill["installed"] and skill["provenance_status"] == "verified" else "problem"
        print(
            f"[{marker}] {skill['name']}: {skill['version']} "
            f"({skill['provenance_status']}; {skill['source_identity'] or skill['source']})"
        )


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


def runtime_status_command(
    project: Path, installed_skill: Path, declared: object
) -> list[str]:
    if not isinstance(declared, list) or not declared or not all(
        isinstance(item, str) and item for item in declared
    ):
        raise ManagerError("runtime status command must be a non-empty string array")
    command: list[str] = []
    for index, token in enumerate(declared):
        value = token.replace("<project-root>", str(project.resolve())).replace(
            "<project-path>", str(project.resolve())
        )
        if "<" in value or ">" in value:
            raise ManagerError(f"runtime status command has an unresolved placeholder: {value}")
        if index == 0 and value in {"python", "python3"}:
            value = python_executable()
        elif index == 1 and not Path(value).is_absolute():
            candidate = (installed_skill / value).resolve()
            try:
                candidate.relative_to(installed_skill.resolve())
            except ValueError as error:
                raise ManagerError("runtime status script escapes the installed skill") from error
            value = str(candidate)
        command.append(value)
    return command


def runtime_artifact_exists(payload: dict[str, Any]) -> bool:
    for key, value in payload.items():
        if not isinstance(value, str) or not value:
            continue
        if key in {"config_file", "config_path", "policy_file", "path"} or key.endswith(
            ("_file", "_path")
        ):
            try:
                if Path(value).expanduser().exists():
                    return True
            except OSError:
                continue
    return False


def deep_runtime_doctor(
    project: Path,
    state: dict[str, Any],
    include_user_config: bool = False,
    timeout: int = 30,
    repository_root: Path | None = None,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    root = (repository_root or REPOSITORY_ROOT).resolve()
    catalog = load_object(root / "skill-catalog.json", "Skill catalog")
    entries = {
        item.get("name"): item
        for item in catalog.get("skills", [])
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    checks: list[dict[str, Any]] = []
    problems: list[str] = []
    warnings: list[str] = []
    for installed in state["skills"]:
        name = installed["name"]
        catalog_entry = entries.get(name)
        if not catalog_entry:
            problems.append(f"{name} is missing from the collection catalog")
            continue
        configuration = catalog_entry.get("configuration")
        if not isinstance(configuration, dict):
            checks.append({"skill": name, "status": "not-applicable"})
            continue
        config_scope = configuration.get("scope")
        if config_scope == "user" and not include_user_config:
            checks.append(
                {"skill": name, "status": "skipped", "reason": "user configuration not requested"}
            )
            continue
        try:
            command = runtime_status_command(
                project, Path(installed["path"]), configuration.get("status")
            )
        except ManagerError as error:
            problems.append(f"{name} runtime status declaration is invalid: {error}")
            checks.append({"skill": name, "status": "invalid-declaration"})
            continue
        try:
            result = subprocess.run(
                command,
                cwd=project.resolve(),
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            problems.append(f"{name} runtime status failed to execute: {error}")
            checks.append({"skill": name, "status": "error"})
            continue
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            payload = None
        if not isinstance(payload, dict):
            problems.append(f"{name} runtime status returned invalid JSON")
            checks.append(
                {"skill": name, "status": "error", "returncode": result.returncode}
            )
            continue
        configured = payload.get("configured")
        valid = payload.get("valid")
        if valid is False:
            runtime_status = "invalid"
            problems.append(f"{name} runtime configuration is invalid")
        elif configured is False:
            if runtime_artifact_exists(payload):
                runtime_status = "partial"
                problems.append(f"{name} runtime configuration is only partially configured")
            else:
                runtime_status = "unconfigured"
                warnings.append(f"{name} is installed but not configured")
        elif result.returncode != 0:
            runtime_status = "error"
            problems.append(
                f"{name} runtime status failed with exit code {result.returncode}"
            )
        else:
            runtime_status = "healthy"
        checks.append(
            {
                "skill": name,
                "status": runtime_status,
                "returncode": result.returncode,
                "result": payload,
            }
        )
    return checks, problems, warnings


def print_portable(value: str) -> None:
    encoding = sys.stdout.encoding or "utf-8"
    sys.stdout.write(value.encode(encoding, errors="replace").decode(encoding))
    if value and not value.endswith("\n"):
        sys.stdout.write("\n")


def resolve_update_selection(
    project: Path,
    skills: list[str],
    scope: str,
    adopt_legacy: bool = False,
    trusted_development_sources: dict[str, Path] | None = None,
    global_root: Path | None = None,
) -> list[str]:
    unknown = set(skills) - KNOWN_SKILLS
    if unknown:
        raise ManagerError(f"Unknown collection skills: {', '.join(sorted(unknown))}")
    if scope == "global":
        if not skills:
            raise ManagerError(
                "global updates require explicit skill names so unrelated global skills are not updated"
            )
        state = read_global_state(global_root, trusted_development_sources)
    else:
        state = read_project_state(project, trusted_development_sources)
    entries = {item["name"]: item for item in state["skills"]}
    if skills:
        missing = set(skills) - set(entries)
        if missing:
            raise ManagerError(
                f"Collection skills are not present in the {scope} lock: {', '.join(sorted(missing))}"
            )
        selected = skills
    else:
        selected = sorted(entries)
        if not selected:
            raise ManagerError("no kolabse skills were found in skills-lock.json")

    mismatched = [name for name in selected if entries[name]["provenance_status"] == "mismatch"]
    if mismatched:
        raise ManagerError(
            "collection provenance mismatch for: " + ", ".join(sorted(mismatched))
        )
    legacy = [name for name in selected if entries[name]["provenance_status"] == "legacy-unverified"]
    if legacy and not adopt_legacy:
        raise ManagerError(
            "legacy installations require explicit --adopt-legacy: " + ", ".join(sorted(legacy))
        )
    return selected


def update_skills(
    project: Path,
    skills: list[str],
    scope: str,
    cli_version: str,
    yes: bool,
    timeout: int,
    adopt_legacy: bool = False,
    trusted_development_sources: dict[str, Path] | None = None,
    global_root: Path | None = None,
    as_json: bool = False,
) -> dict[str, Any]:
    if scope == "global" and global_root is not None:
        requested_root = global_root.expanduser().resolve()
        if requested_root != default_global_root().resolve():
            raise ManagerError(
                "relocated global roots are read-only because the external skills CLI cannot target them"
            )
    selected = resolve_update_selection(
        project,
        skills,
        scope,
        adopt_legacy,
        trusted_development_sources,
        global_root,
    )
    before = (
        read_project_state(project, trusted_development_sources)
        if scope == "project"
        else read_global_state(global_root, trusted_development_sources)
    )
    before_by_name = {item["name"]: item for item in before["skills"]}
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
    if result.stdout.strip() and not as_json:
        print_portable(result.stdout.strip())
    state = doctor(
        project,
        trusted_development_sources,
        scope=scope,
        global_root=global_root,
    )
    if not state["healthy"]:
        detail = "; ".join(state["problems"])
        raise ManagerError(f"post-update diagnosis failed: {detail}")
    after_by_name = {item["name"]: item for item in state["skills"]}
    outcomes: list[dict[str, Any]] = []
    for name in selected:
        old = before_by_name[name]
        new = after_by_name[name]
        changed = old["version"] != new["version"] or old["computed_hash"] != new["computed_hash"]
        outcomes.append(
            {
                "skill": name,
                "status": "updated" if changed else "unchanged",
                "previous_version": old["version"],
                "version": new["version"],
                "provenance_status": new["provenance_status"],
            }
        )
    return {
        "schema_version": 1,
        "operation": "update",
        "collection": COLLECTION,
        "scope": scope,
        "outcomes": outcomes,
        "healthy": True,
    }


def telegram_config_path(environment: dict[str, str] | None = None) -> Path:
    env = os.environ if environment is None else environment
    if env.get("TELEGRAM_NOTIFY_CONFIG"):
        return Path(env["TELEGRAM_NOTIFY_CONFIG"]).expanduser()
    if os.name == "nt" and env.get("LOCALAPPDATA"):
        return Path(env["LOCALAPPDATA"]) / "codex" / "telegram-notify" / "config.json"
    return Path(env.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "codex" / "telegram-notify" / "config.json"


def sync_project_context_config_path(environment: dict[str, str] | None = None) -> Path:
    env = os.environ if environment is None else environment
    if env.get("KOLABSE_SYNC_PROJECT_CONTEXT_CONFIG"):
        return Path(env["KOLABSE_SYNC_PROJECT_CONTEXT_CONFIG"]).expanduser().resolve()
    if os.name == "nt":
        base = Path(env.get("APPDATA", Path.home() / "AppData/Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        base = Path(env.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "kolabse" / "sync-project-context" / "config.json"


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
    context_config = sync_project_context_config_path()
    context_script = installed / "sync-project-context/scripts/context_sync.py"
    if include_user_config and context_config.is_file() and context_script.is_file():
        commands.append(
            (
                "sync-project-context",
                [
                    python,
                    str(context_script),
                    "--config-path",
                    str(context_config),
                    "migrate",
                    "--json",
                ],
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
        results.append(
            {
                "skill": name,
                "status": "migrated" if payload.get("changed") else "unchanged",
                "result": payload,
            }
        )
    return {
        "schema_version": 1,
        "operation": "migrate",
        "collection": COLLECTION,
        "scope": "project",
        "outcomes": results,
        "migrations": results,
    }


def build_update_plan(
    project: Path,
    skills: list[str],
    scope: str,
    adopt_legacy: bool = False,
    global_root: Path | None = None,
) -> dict[str, Any]:
    unknown = set(skills) - KNOWN_SKILLS
    if unknown:
        raise ManagerError(f"Unknown collection skills: {', '.join(sorted(unknown))}")
    state = read_project_state(project) if scope == "project" else read_global_state(global_root)
    entries = {item["name"]: item for item in state["skills"]}
    selected = skills or sorted(entries)
    missing = set(selected) - set(entries)
    if missing:
        raise ManagerError(
            f"Collection skills are not present in the {scope} lock: {', '.join(sorted(missing))}"
        )
    outcomes: list[dict[str, Any]] = []
    for name in selected:
        item = entries[name]
        provenance = item["provenance_status"]
        if provenance == "mismatch":
            action = "blocked"
            reason = item["provenance_error"] or "provenance mismatch"
        elif provenance == "legacy-unverified" and not adopt_legacy:
            action = "blocked"
            reason = "legacy installation requires --adopt-legacy"
        elif provenance == "legacy-unverified":
            action = "adopt-and-update"
            reason = ""
        elif item["version"] == COLLECTION_VERSION:
            action = "unchanged"
            reason = ""
        else:
            action = "update"
            reason = ""
        outcomes.append(
            {
                "skill": name,
                "action": action,
                "reason": reason,
                "current_version": item["version"],
                "target_version": COLLECTION_VERSION,
                "provenance_status": provenance,
                "source_identity": item["source_identity"],
            }
        )
    migrations = (
        [name for name, _ in migration_commands(project, False)] if scope == "project" else []
    )
    return {
        "schema_version": 1,
        "operation": "plan",
        "collection": COLLECTION,
        "scope": scope,
        "target_version": COLLECTION_VERSION,
        "mutates": False,
        "blocked": any(item["action"] == "blocked" for item in outcomes),
        "outcomes": outcomes,
        "migration_candidates": migrations,
    }


def doctor(
    project: Path,
    trusted_development_sources: dict[str, Path] | None = None,
    scope: str = "project",
    global_root: Path | None = None,
    deep: bool = False,
    include_user_config: bool = False,
    runtime_timeout: int = 30,
    repository_root: Path | None = None,
) -> dict[str, Any]:
    state = (
        read_project_state(project, trusted_development_sources)
        if scope == "project"
        else read_global_state(global_root, trusted_development_sources)
    )
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
        if skill["provenance_status"] == "legacy-unverified":
            problems.append(
                f"{skill['name']} is a legacy installation; run update with --adopt-legacy"
            )
        elif skill["provenance_status"] == "mismatch":
            detail = skill["provenance_error"] or "metadata and lock source do not identify the collection"
            problems.append(f"{skill['name']} provenance mismatch: {detail}")
        if not isinstance(skill["source"], str) or not skill["source"]:
            problems.append(f"{skill['name']} has no lock source")
        digest = skill["computed_hash"]
        valid_digest_lengths = {64} if scope == "project" else {40, 64}
        if not isinstance(digest, str) or len(digest) not in valid_digest_lengths:
            problems.append(f"{skill['name']} has an invalid lock hash")
    if len(versions) > 1:
        problems.append(f"installed skills use mixed collection versions: {sorted(versions)}")
    warnings: list[str] = []
    if deep:
        if scope != "project":
            raise ManagerError("--deep is supported only for project scope")
        runtime_checks, runtime_problems, runtime_warnings = deep_runtime_doctor(
            project,
            state,
            include_user_config=include_user_config,
            timeout=runtime_timeout,
            repository_root=repository_root,
        )
        state["runtime_checks"] = runtime_checks
        problems.extend(runtime_problems)
        warnings.extend(runtime_warnings)
    state["healthy"] = not problems
    state["problems"] = problems
    state["warnings"] = warnings
    state["migration_candidates"] = (
        [name for name, _ in migration_commands(project, False)] if scope == "project" else []
    )
    return state


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage installed kolabse skills.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "doctor", "migrate"):
        child = subparsers.add_parser(name)
        child.add_argument("--project-path", type=Path, default=Path.cwd())
        child.add_argument("--json", action="store_true")
        if name in {"status", "doctor"}:
            child.add_argument("--scope", choices=("project", "global"), default="project")
            child.add_argument("--global-root", type=Path)
        if name == "doctor":
            child.add_argument("--deep", action="store_true")
            child.add_argument("--include-user-config", action="store_true")
            child.add_argument("--runtime-timeout", type=int, default=30)
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
    update.add_argument("--global-root", type=Path)
    update.add_argument("--json", action="store_true")
    update.add_argument(
        "--adopt-legacy",
        action="store_true",
        help="explicitly update pre-metadata installs from a verified source",
    )
    plan = subparsers.add_parser("plan")
    plan.add_argument("skills", nargs="*")
    plan.add_argument("--project-path", type=Path, default=Path.cwd())
    plan.add_argument("--scope", choices=("project", "global"), default="project")
    plan.add_argument("--global-root", type=Path)
    plan.add_argument("--adopt-legacy", action="store_true")
    plan.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "status":
            state = (
                read_project_state(args.project_path)
                if args.scope == "project"
                else read_global_state(args.global_root)
            )
            print_state(state, args.json)
            return 0
        if args.command == "doctor":
            state = doctor(
                args.project_path,
                scope=args.scope,
                global_root=args.global_root,
                deep=args.deep,
                include_user_config=args.include_user_config,
                runtime_timeout=args.runtime_timeout,
            )
            print_state(state, args.json)
            if not args.json and state["problems"]:
                for problem in state["problems"]:
                    print(f"PROBLEM: {problem}")
            return 0 if state["healthy"] else 1
        if args.command == "plan":
            result = build_update_plan(
                args.project_path,
                args.skills,
                args.scope,
                args.adopt_legacy,
                args.global_root,
            )
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
            else:
                for outcome in result["outcomes"]:
                    print(
                        f"[{outcome['action']}] {outcome['skill']}: "
                        f"{outcome['current_version']} -> {outcome['target_version']}"
                    )
            return 1 if result["blocked"] else 0
        if args.command == "migrate":
            result = migrate(args.project_path, args.include_user_config, args.timeout)
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        if args.migrate and args.scope != "project":
            raise ManagerError("--migrate is supported only for project-scoped updates")
        result = update_skills(
            args.project_path,
            args.skills,
            args.scope,
            args.cli_version,
            args.yes,
            args.timeout,
            args.adopt_legacy,
            global_root=args.global_root,
            as_json=args.json,
        )
        if args.migrate:
            migration = migrate(args.project_path, args.include_user_config, args.timeout)
            result["migration"] = migration
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except ManagerError as error:
        if getattr(args, "json", False):
            failure = {
                "schema_version": 1,
                "operation": args.command,
                "collection": COLLECTION,
                "scope": getattr(args, "scope", "project"),
                "outcomes": [
                    {
                        "skill": ",".join(getattr(args, "skills", [])) or "collection",
                        "status": "failed",
                        "reason": str(error),
                    }
                ],
            }
            print(json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True), file=sys.stderr)
        else:
            print(f"MANAGER_FAILED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
