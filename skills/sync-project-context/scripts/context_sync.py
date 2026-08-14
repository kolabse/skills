from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


CONFIG_VERSION = 1
CHECKPOINT_VERSION = 1
PROJECT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
MAX_SUMMARY = 8000
MAX_ITEM = 2000
MAX_ITEMS = 100
CONTEXT_LIST_FIELDS = (
    "decisions",
    "actions",
    "verifications",
    "open_questions",
    "next_steps",
    "relevant_paths",
)
SECRET_PATTERNS = (
    ("private-key", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----", re.I)),
    (
        "authorization",
        re.compile(
            r"\b(?:authorization\s*:\s*)?(?:bearer|basic)\s+"
            r"[A-Za-z0-9._~+/=-]{12,}",
            re.I,
        ),
    ),
    (
        "jwt",
        re.compile(
            r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\."
            r"[A-Za-z0-9_-]{8,}\b"
        ),
    ),
    (
        "github-token",
        re.compile(
            r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|"
            r"github_pat_[A-Za-z0-9_]{20,})\b"
        ),
    ),
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    (
        "telegram-token",
        re.compile(r"\b[0-9]{6,12}:[A-Za-z0-9_-]{30,}\b"),
    ),
    (
        "credential-assignment",
        re.compile(
            r"\b(?:password|passwd|secret|api[_-]?key|access[_-]?token|"
            r"refresh[_-]?token)\s*[:=]\s*['\"]?[A-Za-z0-9._~+/=-]{8,}",
            re.I,
        ),
    ),
)


class ContextSyncError(RuntimeError):
    pass


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def default_config_path() -> Path:
    override = os.environ.get("KOLABSE_SYNC_PROJECT_CONTEXT_CONFIG")
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "kolabse" / "sync-project-context" / "config.json"


def resolved(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def enclosing_git_root(path: Path) -> Path | None:
    candidate = path if path.is_dir() else path.parent
    for directory in (candidate, *candidate.parents):
        if (directory / ".git").exists():
            return directory
    return None


def atomic_write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(
            handle, "w", encoding="utf-8", newline="\n"
        ) as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def canonical_digest(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def new_config() -> dict[str, Any]:
    return {
        "version": CONFIG_VERSION,
        "machine_id": f"machine-{uuid.uuid4().hex[:12]}",
        "projects": [],
    }


def validate_config(config: object) -> dict[str, Any]:
    if not isinstance(config, dict):
        raise ContextSyncError("Configuration root must be an object")
    if config.get("version") != CONFIG_VERSION:
        raise ContextSyncError("Unsupported configuration version; run migrate")
    machine_id = config.get("machine_id")
    if not isinstance(machine_id, str) or not re.fullmatch(
        r"machine-[0-9a-f]{12}", machine_id
    ):
        raise ContextSyncError("Configuration machine_id is invalid")
    projects = config.get("projects")
    if not isinstance(projects, list):
        raise ContextSyncError("Configuration projects must be an array")
    for index, item in enumerate(projects):
        if not isinstance(item, dict):
            raise ContextSyncError(
                f"Configuration projects[{index}] must be an object"
            )
        required = {"project_id", "local_root", "storage_root", "mode"}
        if set(item) != required:
            raise ContextSyncError(
                f"Configuration projects[{index}] has unexpected fields"
            )
        if not isinstance(item["project_id"], str) or not (
            PROJECT_ID_PATTERN.fullmatch(item["project_id"])
        ):
            raise ContextSyncError(
                f"Configuration projects[{index}].project_id is invalid"
            )
        if item["mode"] not in {"metadata-only", "paths"}:
            raise ContextSyncError(
                f"Configuration projects[{index}].mode is invalid"
            )
        if not all(
            isinstance(item[field], str) and item[field]
            for field in ("local_root", "storage_root")
        ):
            raise ContextSyncError(
                f"Configuration projects[{index}] paths are invalid"
            )
    return config


def load_config(path: Path, *, allow_missing: bool = False) -> dict[str, Any]:
    if not path.is_file():
        if allow_missing:
            return new_config()
        raise ContextSyncError(f"Configuration is missing: {path}")
    try:
        return validate_config(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ContextSyncError(f"Configuration is invalid JSON: {error}") from error


def find_project(
    config: dict[str, Any], project_root: Path
) -> dict[str, Any]:
    identity = os.path.normcase(str(project_root))
    matches = [
        item
        for item in config["projects"]
        if os.path.normcase(str(resolved(item["local_root"]))) == identity
    ]
    if len(matches) != 1:
        if matches:
            raise ContextSyncError(
                "Configuration contains duplicate project mappings"
            )
        raise ContextSyncError("Project is not configured; run configure first")
    return matches[0]


def run_git(
    project_root: Path, arguments: list[str], *, check: bool = True
) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(project_root), *arguments],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        if check:
            raise ContextSyncError("Git is required but was not found")
        return None
    if completed.returncode != 0:
        if check:
            detail = completed.stderr.strip() or "Git command failed"
            raise ContextSyncError(detail)
        return None
    return completed.stdout.rstrip("\r\n")


def canonical_remote(remote: str) -> str:
    value = remote.strip()
    scp_match = re.fullmatch(r"(?:[^@/]+@)?([^:/]+):(.+)", value)
    if scp_match and "://" not in value:
        host, path = scp_match.groups()
        canonical = f"{host.lower()}/{path}"
    else:
        parsed = urlsplit(value if "://" in value else f"ssh://{value}")
        host = (parsed.hostname or "").lower()
        canonical = f"{host}/{parsed.path.lstrip('/')}"
    return canonical.removesuffix(".git").rstrip("/")


def repository_fingerprint(project_root: Path) -> str | None:
    remote = run_git(
        project_root, ["config", "--get", "remote.origin.url"], check=False
    )
    if not remote:
        return None
    canonical = canonical_remote(remote)
    if not canonical:
        return None
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def repository_state(project_root: Path, mode: str) -> dict[str, Any]:
    git_root = run_git(
        project_root, ["rev-parse", "--show-toplevel"], check=False
    )
    if not git_root:
        return {"available": False, "fingerprint": None}
    head = run_git(project_root, ["rev-parse", "HEAD"], check=False)
    upstream = run_git(
        project_root, ["rev-parse", "@{upstream}"], check=False
    )
    branch = run_git(
        project_root,
        ["symbolic-ref", "--quiet", "--short", "HEAD"],
        check=False,
    )
    upstream_name = run_git(
        project_root,
        ["rev-parse", "--abbrev-ref", "@{upstream}"],
        check=False,
    )
    porcelain = (
        run_git(
            project_root,
            ["status", "--porcelain=v1", "--untracked-files=all"],
            check=False,
        )
        or ""
    )
    staged = 0
    unstaged = 0
    untracked = 0
    changed_paths: list[str] = []
    for line in porcelain.splitlines():
        if len(line) < 3:
            continue
        x, y = line[0], line[1]
        if x == "?" and y == "?":
            untracked += 1
        else:
            staged += int(x not in {" ", "?"})
            unstaged += int(y not in {" ", "?"})
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        changed_paths.append(path.strip('"'))
    state: dict[str, Any] = {
        "available": True,
        "fingerprint": repository_fingerprint(project_root),
        "head": head,
        "upstream_head": upstream,
        "dirty": {
            "staged": staged,
            "unstaged": unstaged,
            "untracked": untracked,
        },
    }
    if mode == "paths":
        state.update(
            {
                "branch": branch,
                "upstream": upstream_name,
                "changed_paths": sorted(set(changed_paths)),
            }
        )
    return state


def scan_secrets(
    value: object, location: str = "$"
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            findings.extend(scan_secrets(child, f"{location}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(scan_secrets(child, f"{location}[{index}]"))
    elif isinstance(value, str):
        for name, pattern in SECRET_PATTERNS:
            if pattern.search(value):
                findings.append({"location": location, "kind": name})
    return findings


def validate_context(value: object, mode: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContextSyncError("Capture input must be a JSON object")
    allowed = {"summary", *CONTEXT_LIST_FIELDS}
    unexpected = set(value) - allowed
    if unexpected:
        raise ContextSyncError(
            f"Capture input has unexpected fields: {sorted(unexpected)}"
        )
    summary = value.get("summary")
    if (
        not isinstance(summary, str)
        or not summary.strip()
        or len(summary) > MAX_SUMMARY
    ):
        raise ContextSyncError(
            f"summary must contain 1-{MAX_SUMMARY} characters"
        )
    context: dict[str, Any] = {"summary": summary.strip()}
    for field in CONTEXT_LIST_FIELDS:
        items = value.get(field, [])
        if not isinstance(items, list) or len(items) > MAX_ITEMS:
            raise ContextSyncError(
                f"{field} must be an array with at most {MAX_ITEMS} items"
            )
        if not all(
            isinstance(item, str)
            and item.strip()
            and len(item) <= MAX_ITEM
            for item in items
        ):
            raise ContextSyncError(
                f"{field} items must contain 1-{MAX_ITEM} characters"
            )
        context[field] = [item.strip() for item in items]
    if mode == "metadata-only" and context["relevant_paths"]:
        raise ContextSyncError(
            "metadata-only mode does not permit relevant_paths"
        )
    findings = scan_secrets(context)
    if findings:
        locations = ", ".join(
            sorted({finding["location"] for finding in findings})
        )
        raise ContextSyncError(
            f"Capture rejected: possible secret at {locations}"
        )
    return context


def project_directory(entry: dict[str, Any]) -> Path:
    return resolved(entry["storage_root"]) / entry["project_id"]


def load_project_marker(directory: Path) -> dict[str, Any]:
    path = directory / "project.json"
    try:
        marker = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ContextSyncError(
            f"Storage project marker is missing: {path}"
        ) from error
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ContextSyncError(
            f"Storage project marker is invalid: {error}"
        ) from error
    if not isinstance(marker, dict) or marker.get("schema_version") != 1:
        raise ContextSyncError("Storage project marker version is unsupported")
    return marker


def validate_storage(
    entry: dict[str, Any], current_fingerprint: str | None
) -> Path:
    directory = project_directory(entry)
    marker = load_project_marker(directory)
    if marker.get("project_id") != entry["project_id"]:
        raise ContextSyncError(
            "Storage project_id does not match local configuration"
        )
    expected = marker.get("repository_fingerprint")
    if expected and current_fingerprint and expected != current_fingerprint:
        raise ContextSyncError(
            "Repository fingerprint does not match the configured storage project"
        )
    return directory


def checkpoint_digest(checkpoint: dict[str, Any]) -> str:
    unsigned = dict(checkpoint)
    unsigned.pop("content_sha256", None)
    return canonical_digest(unsigned)


def load_checkpoints(
    directory: Path, project_id: str
) -> list[dict[str, Any]]:
    checkpoints: list[dict[str, Any]] = []
    for path in sorted((directory / "checkpoints").glob("*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ContextSyncError(
                f"Checkpoint is invalid: {path}: {error}"
            ) from error
        if (
            not isinstance(value, dict)
            or value.get("schema_version") != CHECKPOINT_VERSION
        ):
            raise ContextSyncError(
                f"Checkpoint version is unsupported: {path}"
            )
        if value.get("project_id") != project_id:
            raise ContextSyncError(f"Checkpoint project_id mismatch: {path}")
        if path.stem != value.get("checkpoint_id"):
            raise ContextSyncError(
                f"Checkpoint filename does not match its id: {path}"
            )
        parents = value.get("parent_checkpoint_ids")
        if not isinstance(parents, list) or not all(
            isinstance(parent, str)
            and re.fullmatch(r"checkpoint-[0-9a-f]{32}", parent)
            for parent in parents
        ):
            raise ContextSyncError(f"Checkpoint parents are invalid: {path}")
        if len(parents) != len(set(parents)):
            raise ContextSyncError(f"Checkpoint parents are duplicated: {path}")
        if value.get("content_sha256") != checkpoint_digest(value):
            raise ContextSyncError(f"Checkpoint digest does not match: {path}")
        findings = scan_secrets(value)
        if findings:
            raise ContextSyncError(
                f"Checkpoint contains a possible secret: {path}"
            )
        checkpoints.append(value)
    checkpoints.sort(
        key=lambda item: (
            str(item.get("created_at", "")),
            str(item.get("checkpoint_id", "")),
        )
    )
    return checkpoints


def checkpoint_heads(
    checkpoints: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    referenced = {
        parent
        for item in checkpoints
        for parent in item.get("parent_checkpoint_ids", [])
    }
    heads = [
        item
        for item in checkpoints
        if item.get("checkpoint_id") not in referenced
    ]
    heads.sort(
        key=lambda item: (
            str(item.get("created_at", "")),
            str(item.get("checkpoint_id", "")),
        )
    )
    return heads


def load_capture_input(
    args: argparse.Namespace, project_root: Path
) -> object:
    if args.stdin:
        text = sys.stdin.read()
    else:
        input_path = resolved(args.input)
        if is_within(input_path, project_root):
            raise ContextSyncError(
                "Capture input must stay outside the project directory"
            )
        text = input_path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ContextSyncError(
            f"Capture input is invalid JSON: {error}"
        ) from error


def command_configure(args: argparse.Namespace) -> dict[str, Any]:
    if not args.acknowledge_storage_policy:
        raise ContextSyncError(
            "Pass --acknowledge-storage-policy after confirming the storage is approved"
        )
    project_root = resolved(args.project_path)
    storage_root = resolved(args.storage_root)
    if not project_root.is_dir():
        raise ContextSyncError(
            f"Project directory does not exist: {project_root}"
        )
    if project_root == storage_root or is_within(storage_root, project_root):
        raise ContextSyncError(
            "Storage root must stay outside the project directory"
        )
    storage_git_root = enclosing_git_root(storage_root)
    if storage_git_root is not None:
        raise ContextSyncError(
            "Storage root must stay outside every Git worktree: "
            f"{storage_git_root}"
        )
    project_id = args.project_id or f"proj-{uuid.uuid4().hex[:16]}"
    if not PROJECT_ID_PATTERN.fullmatch(project_id):
        raise ContextSyncError(
            "project_id must be 3-64 lowercase letters, digits, or hyphens"
        )
    config_path = (
        resolved(args.config_path) if args.config_path else default_config_path()
    )
    if is_within(config_path, project_root):
        raise ContextSyncError(
            "Configuration path must stay outside the project directory"
        )
    config = load_config(config_path, allow_missing=True)
    fingerprint = repository_fingerprint(project_root)
    directory = storage_root / project_id
    marker_path = directory / "project.json"
    if marker_path.exists():
        marker = load_project_marker(directory)
        if marker.get("project_id") != project_id:
            raise ContextSyncError(
                "Existing storage marker uses another project_id"
            )
        expected = marker.get("repository_fingerprint")
        if expected and fingerprint and expected != fingerprint:
            raise ContextSyncError(
                "Existing storage marker belongs to another repository"
            )
    else:
        marker = {
            "schema_version": 1,
            "project_id": project_id,
            "repository_fingerprint": fingerprint,
            "created_at": utc_now(),
        }
        atomic_write_json(marker_path, marker)
    (directory / "checkpoints").mkdir(parents=True, exist_ok=True)
    new_entry = {
        "project_id": project_id,
        "local_root": str(project_root),
        "storage_root": str(storage_root),
        "mode": args.mode,
    }
    identity = os.path.normcase(str(project_root))
    existing = [
        item
        for item in config["projects"]
        if os.path.normcase(str(resolved(item["local_root"]))) == identity
    ]
    changed = existing != [new_entry]
    config["projects"] = [
        item
        for item in config["projects"]
        if os.path.normcase(str(resolved(item["local_root"]))) != identity
    ]
    config["projects"].append(new_entry)
    config["projects"].sort(
        key=lambda item: os.path.normcase(item["local_root"])
    )
    atomic_write_json(config_path, config)
    return {
        "configured": True,
        "changed": changed,
        "project_id": project_id,
        "mode": args.mode,
        "config_path": str(config_path),
        "storage_project": str(directory),
    }


def configured_context(
    args: argparse.Namespace,
) -> tuple[
    Path,
    Path,
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    project_root = resolved(args.project_path)
    config_path = (
        resolved(args.config_path) if args.config_path else default_config_path()
    )
    if not project_root.is_dir():
        raise ContextSyncError(
            f"Project directory does not exist: {project_root}"
        )
    if is_within(config_path, project_root):
        raise ContextSyncError(
            "Configuration path must stay outside the project directory"
        )
    config = load_config(config_path)
    entry = find_project(config, project_root)
    storage_root = resolved(entry["storage_root"])
    if storage_root == project_root or is_within(storage_root, project_root):
        raise ContextSyncError(
            "Configured storage root is inside the project directory"
        )
    storage_git_root = enclosing_git_root(storage_root)
    if storage_git_root is not None:
        raise ContextSyncError(
            "Configured storage root is inside a Git worktree: "
            f"{storage_git_root}"
        )
    current = repository_state(project_root, entry["mode"])
    validate_storage(entry, current.get("fingerprint"))
    return project_root, config_path, config, entry, current


def command_status(args: argparse.Namespace) -> dict[str, Any]:
    _project_root, config_path, _config, entry, current = configured_context(
        args
    )
    directory = project_directory(entry)
    checkpoints = load_checkpoints(directory, entry["project_id"])
    heads = checkpoint_heads(checkpoints)
    latest = heads[-1] if len(heads) == 1 else None
    recorded = latest.get("repository", {}) if latest else {}
    return {
        "configured": True,
        "project_id": entry["project_id"],
        "mode": entry["mode"],
        "config_path": str(config_path),
        "storage_project": str(directory),
        "checkpoint_count": len(checkpoints),
        "head_checkpoint_ids": [item["checkpoint_id"] for item in heads],
        "latest_checkpoint_id": (
            latest.get("checkpoint_id") if latest else None
        ),
        "latest_created_at": latest.get("created_at") if latest else None,
        "head_matches": bool(latest)
        and recorded.get("head") == current.get("head"),
        "worktree_matches": bool(latest)
        and recorded.get("dirty") == current.get("dirty"),
        "has_conflict": len(heads) > 1,
        "current_repository": current,
    }


def command_capture(args: argparse.Namespace) -> dict[str, Any]:
    project_root, _config_path, config, entry, current = configured_context(args)
    directory = project_directory(entry)
    context = validate_context(
        load_capture_input(args, project_root), entry["mode"]
    )
    checkpoints = load_checkpoints(directory, entry["project_id"])
    heads = checkpoint_heads(checkpoints)
    if len(heads) > 1 and not getattr(args, "merge_heads", False):
        identifiers = ", ".join(item["checkpoint_id"] for item in heads)
        raise ContextSyncError(
            "Concurrent checkpoint heads require explicit review and "
            f"--merge-heads: {identifiers}"
        )
    parents = [item["checkpoint_id"] for item in heads]
    checkpoint_id = f"checkpoint-{uuid.uuid4().hex}"
    checkpoint = {
        "schema_version": CHECKPOINT_VERSION,
        "checkpoint_id": checkpoint_id,
        "project_id": entry["project_id"],
        "machine_id": config["machine_id"],
        "created_at": utc_now(),
        "parent_checkpoint_ids": parents,
        "repository": current,
        "context": context,
    }
    checkpoint["content_sha256"] = checkpoint_digest(checkpoint)
    if scan_secrets(checkpoint):
        raise ContextSyncError(
            "Checkpoint rejected by the final secret scan"
        )
    path = directory / "checkpoints" / f"{checkpoint_id}.json"
    atomic_write_json(path, checkpoint)
    return {
        "captured": True,
        "checkpoint_id": checkpoint_id,
        "parent_checkpoint_ids": parents,
        "created_at": checkpoint["created_at"],
        "path": str(path),
    }


def freshness(
    recorded: dict[str, Any], current: dict[str, Any]
) -> dict[str, bool]:
    return {
        "head_matches": recorded.get("head") == current.get("head"),
        "upstream_matches": recorded.get("upstream_head")
        == current.get("upstream_head"),
        "worktree_matches": recorded.get("dirty") == current.get("dirty"),
    }


def command_restore(args: argparse.Namespace) -> dict[str, Any]:
    _root, _config_path, _config, entry, current = configured_context(args)
    directory = project_directory(entry)
    checkpoints = load_checkpoints(directory, entry["project_id"])
    if not checkpoints:
        raise ContextSyncError("No checkpoints are available")
    by_id = {item["checkpoint_id"]: item for item in checkpoints}
    heads = checkpoint_heads(checkpoints)
    checkpoint_id = getattr(args, "checkpoint_id", None)
    if checkpoint_id:
        latest = by_id.get(checkpoint_id)
        if latest is None:
            raise ContextSyncError(
                f"Checkpoint does not exist: {checkpoint_id}"
            )
    elif len(heads) > 1:
        identifiers = ", ".join(item["checkpoint_id"] for item in heads)
        raise ContextSyncError(
            "Concurrent checkpoint heads require separate review with "
            f"--checkpoint-id: {identifiers}"
        )
    else:
        latest = heads[0]
    return {
        "project_id": entry["project_id"],
        "checkpoint_id": latest["checkpoint_id"],
        "created_at": latest["created_at"],
        "machine_id": latest["machine_id"],
        "parent_checkpoint_ids": latest["parent_checkpoint_ids"],
        "freshness": freshness(latest["repository"], current),
        "head_checkpoint_ids": [item["checkpoint_id"] for item in heads],
        "has_conflict": len(heads) > 1,
        "recorded_repository": latest["repository"],
        "current_repository": current,
        "context": latest["context"],
    }


def command_audit(args: argparse.Namespace) -> dict[str, Any]:
    _root, _config_path, _config, entry, current = configured_context(args)
    directory = validate_storage(entry, current.get("fingerprint"))
    checkpoints = load_checkpoints(directory, entry["project_id"])
    return {
        "ok": True,
        "project_id": entry["project_id"],
        "checkpoint_count": len(checkpoints),
        "scanned_at": utc_now(),
        "findings": [],
    }


def command_migrate(args: argparse.Namespace) -> dict[str, Any]:
    config_path = (
        resolved(args.config_path) if args.config_path else default_config_path()
    )
    config = load_config(config_path)
    atomic_write_json(config_path, config)
    return {
        "migrated": True,
        "changed": False,
        "version": CONFIG_VERSION,
        "config_path": str(config_path),
    }


def markdown_restore(result: dict[str, Any]) -> str:
    lines = [
        "# Project handoff",
        "",
        f"- Checkpoint: `{result['checkpoint_id']}`",
        f"- Created: `{result['created_at']}`",
        f"- Source machine: `{result['machine_id']}`",
    ]
    current = result["freshness"]
    if not all(current.values()):
        lines.append(
            "- Freshness: **stale or changed; reinspect the current project "
            "before acting**"
        )
    else:
        lines.append("- Freshness: current Git state matches the checkpoint")
    if result["has_conflict"]:
        formatted = ", ".join(
            f"`{value}`" for value in result["head_checkpoint_ids"]
        )
        lines.append(f"- Concurrent checkpoint heads: {formatted}")
    context = result["context"]
    lines.extend(["", "## Summary", "", context["summary"]])
    headings = (
        ("decisions", "Decisions"),
        ("actions", "Actions"),
        ("verifications", "Verification"),
        ("open_questions", "Open questions"),
        ("next_steps", "Next steps"),
        ("relevant_paths", "Relevant paths"),
    )
    for field, heading in headings:
        if context.get(field):
            lines.extend(["", f"## {heading}", ""])
            lines.extend(f"- {item}" for item in context[field])
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Save and restore private project handoff checkpoints"
    )
    parser.add_argument(
        "--config-path",
        help="Explicit configuration path (primarily for isolated profiles)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    configure = subparsers.add_parser(
        "configure", help="Configure a local project mapping"
    )
    configure.add_argument("--project-path", required=True)
    configure.add_argument("--storage-root", required=True)
    configure.add_argument("--project-id")
    configure.add_argument(
        "--mode", choices=("metadata-only", "paths"), default="metadata-only"
    )
    configure.add_argument(
        "--acknowledge-storage-policy", action="store_true"
    )
    configure.add_argument("--json", action="store_true")

    for name in ("status", "audit"):
        child = subparsers.add_parser(name)
        child.add_argument("--project-path", required=True)
        child.add_argument("--json", action="store_true")

    restore = subparsers.add_parser("restore")
    restore.add_argument("--project-path", required=True)
    restore.add_argument("--checkpoint-id")
    restore.add_argument("--json", action="store_true")

    capture = subparsers.add_parser("capture")
    capture.add_argument("--project-path", required=True)
    source = capture.add_mutually_exclusive_group(required=True)
    source.add_argument("--input")
    source.add_argument("--stdin", action="store_true")
    capture.add_argument("--merge-heads", action="store_true")
    capture.add_argument("--json", action="store_true")

    migrate = subparsers.add_parser("migrate")
    migrate.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        handler = {
            "configure": command_configure,
            "status": command_status,
            "capture": command_capture,
            "restore": command_restore,
            "audit": command_audit,
            "migrate": command_migrate,
        }[args.command]
        result = handler(args)
        if args.command == "restore" and not args.json:
            print(markdown_restore(result), end="")
        elif getattr(args, "json", False):
            print(
                json.dumps(
                    result, ensure_ascii=False, indent=2, sort_keys=True
                )
            )
        else:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (ContextSyncError, OSError, ValueError) as error:
        if getattr(args, "json", False):
            print(
                json.dumps(
                    {"ok": False, "error": str(error)},
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
        else:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
