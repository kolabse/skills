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


CONFIG_VERSION = 2
CHECKPOINT_VERSION = 2
THREAD_REGISTRY_VERSION = 1
SUPPORTED_CHECKPOINT_VERSIONS = {1, CHECKPOINT_VERSION}
SUPPORTED_BACKENDS = {"google-drive", "local-folder"}
DEFAULT_STREAM_ID = "project"
STREAM_ID_PATTERN = re.compile(r"^stream-[0-9a-f]{16,64}$")
PROJECT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
MAX_SUMMARY = 8000
MAX_CHAT_TITLE = 256
MAX_ITEM = 2000
MAX_ITEMS = 100
MAX_THREAD_ID = 512
MAX_SOURCE_MARKER = 512
MAX_DRIVE_MARKER_BYTES = 16 * 1024
MAX_DRIVE_INVENTORY_AGE_SECONDS = 5 * 60
DRIVE_FOLDER_MIME = "application/vnd.google-apps.folder"
DRIVE_JSON_MIME = "application/json"
DRIVE_OBJECT_FIELDS = {
    "id",
    "title",
    "mime_type",
    "parent_ids",
    "file_or_folder",
    "drive_id",
    "shared",
    "source_visibility_status",
    "can_list_children",
    "can_download",
}
CONTEXT_LIST_FIELDS = (
    "rationale",
    "discussions",
    "decisions",
    "actions",
    "verifications",
    "blockers",
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
        path.resolve().relative_to(parent.resolve())
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
        common = {"project_id", "local_root", "backend", "mode"}
        backend = item.get("backend")
        backend_fields = {
            "local-folder": {"storage_root"},
            "google-drive": {
                "drive_project_folder_id",
                "drive_checkpoints_folder_id",
                "drive_marker_file_id",
            },
        }.get(backend)
        if backend_fields is None or set(item) != common | backend_fields:
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
        string_fields = {"local_root"} | backend_fields
        if not all(
            isinstance(item[field], str) and item[field]
            for field in string_fields
        ):
            raise ContextSyncError(
                f"Configuration projects[{index}] storage fields are invalid"
            )
    return config


def read_config_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ContextSyncError(f"Configuration is missing: {path}") from error
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ContextSyncError(f"Configuration is invalid JSON: {error}") from error
    if not isinstance(value, dict):
        raise ContextSyncError("Configuration root must be an object")
    return value


def migrate_config(config: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    version = config.get("version")
    if version == CONFIG_VERSION:
        return validate_config(config), False
    if version != 1:
        raise ContextSyncError("Unsupported configuration version")
    projects = config.get("projects")
    if not isinstance(projects, list):
        raise ContextSyncError("Configuration projects must be an array")
    migrated = dict(config)
    migrated["version"] = CONFIG_VERSION
    migrated["projects"] = [
        {**item, "backend": "local-folder"}
        if isinstance(item, dict) and "backend" not in item
        else item
        for item in projects
    ]
    return validate_config(migrated), True


def load_config(path: Path, *, allow_missing: bool = False) -> dict[str, Any]:
    if not path.is_file():
        if allow_missing:
            return new_config()
        raise ContextSyncError(f"Configuration is missing: {path}")
    return validate_config(read_config_object(path))


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


def plan_backend_selection(
    *,
    configured_backend: str | None,
    requested_backend: str | None,
    google_drive_connected: bool,
) -> dict[str, Any]:
    for label, backend in (
        ("configured_backend", configured_backend),
        ("requested_backend", requested_backend),
    ):
        if backend is not None and backend not in SUPPORTED_BACKENDS:
            raise ContextSyncError(f"{label} is unsupported: {backend}")
    if not isinstance(google_drive_connected, bool):
        raise ContextSyncError("google_drive_connected must be boolean")
    google_drive_blocked = {
        "status": "blocked",
        "backend": None,
        "blocker": "google-drive-unavailable",
        "explicit_alternatives": ["local-folder"],
        "next_steps": [
            "connect-google-drive",
            "request-local-folder-explicitly",
        ],
        "requires_storage_approval": True,
    }

    if configured_backend is not None:
        if requested_backend not in {None, configured_backend}:
            return {
                "status": "reconfiguration-required",
                "backend": None,
                "configured_backend": configured_backend,
                "requested_backend": requested_backend,
                "requires_storage_approval": True,
            }
        if configured_backend == "google-drive" and not google_drive_connected:
            return {
                "status": "blocked",
                "backend": "google-drive",
                "selection_source": "configured",
                "blocker": "google-drive-unavailable",
                "next_steps": ["connect-google-drive"],
                "requires_storage_approval": False,
            }
        return {
            "status": "ready",
            "backend": configured_backend,
            "selection_source": "configured",
            "requires_storage_approval": False,
        }

    if requested_backend == "local-folder":
        return {
            "status": "ready",
            "backend": "local-folder",
            "selection_source": "explicit",
            "requires_storage_approval": True,
        }
    if requested_backend == "google-drive" and not google_drive_connected:
        return google_drive_blocked
    if requested_backend == "google-drive" or google_drive_connected:
        return {
            "status": "ready",
            "backend": "google-drive",
            "selection_source": "explicit" if requested_backend else "default",
            "requires_storage_approval": True,
        }
    return google_drive_blocked


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
    allowed = {"summary", "chat_title", *CONTEXT_LIST_FIELDS}
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
    if "chat_title" in value:
        context["chat_title"] = normalize_chat_title(value["chat_title"])
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


def normalize_chat_title(value: object) -> str:
    if not isinstance(value, str):
        raise ContextSyncError("chat_title must be a string")
    title = value.strip()
    if not title or len(title) > MAX_CHAT_TITLE:
        raise ContextSyncError(
            f"chat_title must contain 1-{MAX_CHAT_TITLE} characters"
        )
    if re.search(r"[\x00-\x1f\x7f]", title):
        raise ContextSyncError("chat_title must be a single printable line")
    findings = scan_secrets(title, "$.chat_title")
    if findings:
        raise ContextSyncError(
            "Capture rejected: possible secret at $.chat_title"
        )
    return title


def thread_registry_path(config_path: Path) -> Path:
    return config_path.with_name(f"{config_path.stem}.thread-registry.json")


def new_thread_registry(machine_id: str) -> dict[str, Any]:
    return {
        "schema_version": THREAD_REGISTRY_VERSION,
        "machine_id": machine_id,
        "projects": {},
    }


def validate_thread_registry(
    value: object, machine_id: str
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "machine_id",
        "projects",
    }:
        raise ContextSyncError("Thread registry root is invalid")
    if value.get("schema_version") != THREAD_REGISTRY_VERSION:
        raise ContextSyncError("Thread registry version is unsupported")
    if value.get("machine_id") != machine_id:
        raise ContextSyncError("Thread registry belongs to another machine")
    projects = value.get("projects")
    if not isinstance(projects, dict):
        raise ContextSyncError("Thread registry projects must be an object")
    for project_id, project in projects.items():
        if not isinstance(project_id, str) or not PROJECT_ID_PATTERN.fullmatch(
            project_id
        ):
            raise ContextSyncError("Thread registry project_id is invalid")
        if not isinstance(project, dict) or set(project) != {"threads"}:
            raise ContextSyncError("Thread registry project is invalid")
        threads = project.get("threads")
        if not isinstance(threads, dict):
            raise ContextSyncError("Thread registry threads must be an object")
        for key, binding in threads.items():
            if not isinstance(key, str) or not re.fullmatch(r"[0-9a-f]{64}", key):
                raise ContextSyncError("Thread registry key is invalid")
            if not isinstance(binding, dict) or set(binding) != {
                "stream_id",
                "source_revision",
                "source_head_turn_id",
                "last_checkpoint_id",
                "updated_at",
            }:
                raise ContextSyncError("Thread registry binding is invalid")
            validate_stream_id(binding.get("stream_id"))
            for field in ("source_revision", "source_head_turn_id"):
                marker = binding.get(field)
                if marker is not None and (
                    not isinstance(marker, str)
                    or not marker
                    or len(marker) > MAX_SOURCE_MARKER
                ):
                    raise ContextSyncError(
                        f"Thread registry {field} is invalid"
                    )
            checkpoint_id = binding.get("last_checkpoint_id")
            if checkpoint_id is not None and (
                not isinstance(checkpoint_id, str)
                or not re.fullmatch(r"checkpoint-[0-9a-f]{32}", checkpoint_id)
            ):
                raise ContextSyncError(
                    "Thread registry last_checkpoint_id is invalid"
                )
            if not isinstance(binding.get("updated_at"), str):
                raise ContextSyncError("Thread registry updated_at is invalid")
    return value


def load_thread_registry(
    path: Path, machine_id: str
) -> dict[str, Any]:
    if not path.is_file():
        return new_thread_registry(machine_id)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ContextSyncError(
            f"Thread registry is invalid JSON: {error}"
        ) from error
    return validate_thread_registry(value, machine_id)


def normalize_source_marker(value: object, label: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ContextSyncError(f"{label} must be a string or number")
    marker = str(value).strip()
    if not marker or len(marker) > MAX_SOURCE_MARKER:
        raise ContextSyncError(
            f"{label} must contain 1-{MAX_SOURCE_MARKER} characters"
        )
    return marker


def normalize_optional_source_marker(value: object, label: str) -> str | None:
    if value is None:
        return None
    return normalize_source_marker(value, label)


def thread_registry_key(project_id: str, thread_id: object) -> str:
    if (
        not isinstance(thread_id, str)
        or not thread_id.strip()
        or len(thread_id) > MAX_THREAD_ID
    ):
        raise ContextSyncError(
            f"thread_id must contain 1-{MAX_THREAD_ID} characters"
        )
    encoded = f"{project_id}\0{thread_id.strip()}".encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def default_thread_stream_id(project_id: str, thread_id: object) -> str:
    return f"stream-{thread_registry_key(project_id, thread_id)[:32]}"


def registry_threads(
    registry: dict[str, Any], project_id: str
) -> dict[str, Any]:
    project = registry["projects"].setdefault(project_id, {"threads": {}})
    return project["threads"]


def project_directory(entry: dict[str, Any]) -> Path:
    if entry.get("backend") != "local-folder":
        raise ContextSyncError(
            "Google Drive storage requires a hydrated local snapshot"
        )
    return resolved(entry["storage_root"]) / entry["project_id"]


def load_project_marker_file(path: Path) -> dict[str, Any]:
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
    if scan_secrets(marker):
        raise ContextSyncError("Storage project marker contains a possible secret")
    return marker


def load_discovery_project_marker(path: Path, expected_sha256: str) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ContextSyncError("Drive marker digest is invalid")
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise ContextSyncError(f"Drive marker cannot be read: {path}") from error
    if len(payload) > MAX_DRIVE_MARKER_BYTES:
        raise ContextSyncError("Drive marker is too large")
    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise ContextSyncError("Drive marker digest does not match downloaded bytes")
    try:
        marker = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ContextSyncError(f"Drive marker is invalid: {error}") from error
    if not isinstance(marker, dict) or marker.get("schema_version") != 1:
        raise ContextSyncError("Drive marker version is unsupported")
    if scan_secrets(marker):
        raise ContextSyncError("Drive marker contains a possible secret")
    if set(marker) != {
        "schema_version",
        "project_id",
        "repository_fingerprint",
        "created_at",
    }:
        raise ContextSyncError("Drive marker has unexpected or missing fields")
    project_id = marker.get("project_id")
    fingerprint = marker.get("repository_fingerprint")
    created_at = marker.get("created_at")
    if not isinstance(project_id, str) or not PROJECT_ID_PATTERN.fullmatch(project_id):
        raise ContextSyncError("Drive marker project_id is invalid")
    if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        raise ContextSyncError("Drive marker repository fingerprint is invalid")
    if not isinstance(created_at, str) or not created_at.endswith("Z"):
        raise ContextSyncError("Drive marker timestamp is invalid")
    try:
        datetime.fromisoformat(created_at[:-1] + "+00:00")
    except ValueError as error:
        raise ContextSyncError("Drive marker timestamp is invalid") from error
    return marker


def validate_drive_object(
    value: object,
    *,
    expected_parent: str | None,
    expected_kind: str,
    expected_title: str | None = None,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != DRIVE_OBJECT_FIELDS:
        raise ContextSyncError("Drive inventory object shape is invalid")
    identifier = value.get("id")
    title = value.get("title")
    parent_ids = value.get("parent_ids")
    if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", identifier):
        raise ContextSyncError("Drive inventory object id is invalid")
    if not isinstance(title, str) or not title.strip():
        raise ContextSyncError("Drive inventory object title is invalid")
    if expected_title is not None and title != expected_title:
        raise ContextSyncError("Drive inventory object title is unexpected")
    if (
        not isinstance(parent_ids, list)
        or not parent_ids
        or not all(isinstance(item, str) and item for item in parent_ids)
        or len(parent_ids) != len(set(parent_ids))
    ):
        raise ContextSyncError("Drive inventory parent ids are invalid")
    if expected_parent is not None and parent_ids != [expected_parent]:
        raise ContextSyncError("Drive inventory object has an unexpected parent")
    if value.get("drive_id") is not None:
        raise ContextSyncError("Drive inventory object is stored in a shared drive")
    if value.get("shared") is not False:
        raise ContextSyncError("Drive inventory object is shared")
    if value.get("source_visibility_status") != "not_shared":
        raise ContextSyncError("Drive inventory object visibility is not verified private")
    if expected_kind == "folder":
        if (
            value.get("file_or_folder") != "folder"
            or value.get("mime_type") != DRIVE_FOLDER_MIME
            or value.get("can_list_children") is not True
            or value.get("can_download") is not None
        ):
            raise ContextSyncError("Drive inventory folder metadata is invalid")
    elif (
        value.get("file_or_folder") != "file"
        or value.get("mime_type") != DRIVE_JSON_MIME
        or value.get("can_download") is not True
        or value.get("can_list_children") is not None
    ):
        raise ContextSyncError("Drive inventory file metadata is invalid")
    return value


def validate_drive_listing(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, dict) or set(value) != {
        "complete",
        "page_count",
        "terminal_page_token",
        "children",
    }:
        raise ContextSyncError("Drive inventory listing shape is invalid")
    if value.get("complete") is not True or value.get("terminal_page_token") is not None:
        raise ContextSyncError("Drive inventory listing is incomplete")
    page_count = value.get("page_count")
    children = value.get("children")
    if not isinstance(page_count, int) or isinstance(page_count, bool) or page_count < 1:
        raise ContextSyncError("Drive inventory page count is invalid")
    if not isinstance(children, list):
        raise ContextSyncError("Drive inventory children must be an array")
    return children


def validate_drive_observation(
    observation_id: object, observed_at: object
) -> tuple[str, datetime]:
    if not isinstance(observation_id, str) or not re.fullmatch(
        r"observation-[0-9a-f]{32}", observation_id
    ):
        raise ContextSyncError("Drive inventory observation id is invalid")
    if not isinstance(observed_at, str) or not observed_at.endswith("Z"):
        raise ContextSyncError("Drive inventory observation timestamp is invalid")
    try:
        observed = datetime.fromisoformat(observed_at[:-1] + "+00:00")
    except ValueError as error:
        raise ContextSyncError("Drive inventory observation timestamp is invalid") from error
    now = datetime.now(timezone.utc)
    age = (now - observed).total_seconds()
    if age < -30 or age > MAX_DRIVE_INVENTORY_AGE_SECONDS:
        raise ContextSyncError("Drive inventory observation is stale or in the future")
    return observation_id, observed


def validate_drive_mapping_inventory(
    inventory: object, project_root: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str, datetime]:
    if not isinstance(inventory, dict) or set(inventory) != {
        "schema_version",
        "observation_id",
        "observed_at",
        "parent_search",
        "namespaces",
    }:
        raise ContextSyncError("Drive mapping inventory root is invalid")
    if inventory.get("schema_version") != 1 or scan_secrets(inventory):
        raise ContextSyncError("Drive mapping inventory is invalid")
    observation_id, observed_at = validate_drive_observation(
        inventory.get("observation_id"), inventory.get("observed_at")
    )
    discovered_parents = validate_drive_listing(inventory.get("parent_search"))
    parents: list[dict[str, Any]] = []
    parent_by_id: dict[str, dict[str, Any]] = {}
    for value in discovered_parents:
        parent = validate_drive_object(
            value,
            expected_parent=None,
            expected_kind="folder",
            expected_title="Codex Project Context",
        )
        if parent["id"] in parent_by_id:
            raise ContextSyncError("Drive parent search contains a duplicate id")
        parent_by_id[parent["id"]] = parent
        parents.append(parent)
    namespaces = inventory.get("namespaces")
    if not isinstance(namespaces, list):
        raise ContextSyncError("Drive inventory namespaces must be an array")
    observed_ids: set[str] = set(parent_by_id)
    candidates: list[dict[str, Any]] = []
    inspected_parent_ids: set[str] = set()
    for namespace in namespaces:
        if not isinstance(namespace, dict) or set(namespace) != {
            "parent",
            "listing",
            "projects",
        }:
            raise ContextSyncError("Drive namespace inventory shape is invalid")
        parent = validate_drive_object(
            namespace.get("parent"),
            expected_parent=None,
            expected_kind="folder",
            expected_title="Codex Project Context",
        )
        if parent["id"] not in parent_by_id or parent_by_id[parent["id"]] != parent:
            raise ContextSyncError("Drive namespace is missing from parent search")
        if parent["id"] in inspected_parent_ids:
            raise ContextSyncError("Drive namespace inventory is duplicated")
        inspected_parent_ids.add(parent["id"])
        root_children = validate_drive_listing(namespace.get("listing"))
        projects = namespace.get("projects")
        if not isinstance(projects, list):
            raise ContextSyncError("Drive mapping inventory projects must be an array")
        root_names: set[str] = set()
        root_by_id: dict[str, dict[str, Any]] = {}
        for child in root_children:
            item = validate_drive_object(
                child, expected_parent=parent["id"], expected_kind="folder"
            )
            if item["id"] in observed_ids or item["title"] in root_names:
                raise ContextSyncError("Drive inventory has duplicate ids or names")
            observed_ids.add(item["id"])
            root_names.add(item["title"])
            root_by_id[item["id"]] = item

        project_folder_ids: set[str] = set()
        for project in projects:
            if not isinstance(project, dict) or set(project) != {
                "folder",
                "listing",
                "marker",
                "checkpoints_listing",
            }:
                raise ContextSyncError("Drive project inventory shape is invalid")
            folder = validate_drive_object(
                project.get("folder"),
                expected_parent=parent["id"],
                expected_kind="folder",
            )
            if folder["id"] not in root_by_id or root_by_id[folder["id"]] != folder:
                raise ContextSyncError("Drive project folder is missing from the parent listing")
            if folder["id"] in project_folder_ids:
                raise ContextSyncError("Drive project folder inventory is duplicated")
            project_folder_ids.add(folder["id"])

            children = validate_drive_listing(project.get("listing"))
            if len(children) != 2:
                raise ContextSyncError("Drive project folder has unexpected children")
            by_title: dict[str, dict[str, Any]] = {}
            for child in children:
                title = child.get("title") if isinstance(child, dict) else None
                kind = "folder" if title == "checkpoints" else "file"
                item = validate_drive_object(
                    child, expected_parent=folder["id"], expected_kind=kind
                )
                if item["id"] in observed_ids or item["title"] in by_title:
                    raise ContextSyncError("Drive inventory has duplicate ids or names")
                observed_ids.add(item["id"])
                by_title[item["title"]] = item
            if set(by_title) != {"project.json", "checkpoints"}:
                raise ContextSyncError("Drive project folder shape is invalid")

            marker_evidence = project.get("marker")
            if not isinstance(marker_evidence, dict) or set(marker_evidence) != {
                "file_id",
                "path",
                "sha256",
            }:
                raise ContextSyncError("Drive marker evidence shape is invalid")
            if marker_evidence.get("file_id") != by_title["project.json"]["id"]:
                raise ContextSyncError("Drive marker evidence uses another file id")
            marker_path = resolved(str(marker_evidence.get("path", "")))
            validate_external_path(marker_path, project_root, "Drive marker evidence")
            marker_sha256 = str(marker_evidence.get("sha256", ""))
            marker = load_discovery_project_marker(marker_path, marker_sha256)
            if marker["project_id"] != folder["title"]:
                raise ContextSyncError("Drive marker project_id does not match its folder")

            checkpoint_children = validate_drive_listing(project.get("checkpoints_listing"))
            checkpoint_names: set[str] = set()
            for child in checkpoint_children:
                item = validate_drive_object(
                    child,
                    expected_parent=by_title["checkpoints"]["id"],
                    expected_kind="file",
                )
                if item["id"] in observed_ids or item["title"] in checkpoint_names:
                    raise ContextSyncError("Drive checkpoint inventory is duplicated")
                if not re.fullmatch(
                    r"(?:checkpoint|environment)-[0-9a-f]{32}\.json", item["title"]
                ):
                    raise ContextSyncError("Drive checkpoints folder has an unexpected child")
                observed_ids.add(item["id"])
                checkpoint_names.add(item["title"])

            candidates.append(
                {
                    "project_id": marker["project_id"],
                    "repository_fingerprint": marker["repository_fingerprint"],
                    "drive_parent_folder_id": parent["id"],
                    "drive_project_folder_id": folder["id"],
                    "drive_checkpoints_folder_id": by_title["checkpoints"]["id"],
                    "drive_marker_file_id": by_title["project.json"]["id"],
                    "marker_file": str(marker_path),
                    "marker_sha256": marker_sha256,
                }
            )
        if project_folder_ids != set(root_by_id):
            raise ContextSyncError("Drive parent listing has an uninspected project folder")
    if inspected_parent_ids != set(parent_by_id):
        raise ContextSyncError("Drive parent search has an uninspected namespace")
    return parents, candidates, observation_id, observed_at


def seal_drive_mapping_plan(plan: dict[str, Any]) -> dict[str, Any]:
    sealed = dict(plan)
    sealed["plan_sha256"] = canonical_digest(plan)
    return sealed


def command_drive_mapping_plan(args: argparse.Namespace) -> dict[str, Any]:
    project_root = resolved(args.project_path)
    if not project_root.is_dir():
        raise ContextSyncError(f"Project directory does not exist: {project_root}")
    inventory_path = resolved(args.inventory)
    output_path = resolved(args.output)
    validate_external_path(inventory_path, project_root, "Drive mapping inventory")
    validate_external_path(output_path, project_root, "Drive mapping plan output")
    try:
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ContextSyncError(f"Drive mapping inventory is invalid: {error}") from error
    inventory_sha256 = canonical_digest(inventory)
    fingerprint = repository_fingerprint(project_root)
    base: dict[str, Any] = {
        "schema_version": 1,
        "project_path": str(project_root),
        "repository_fingerprint": fingerprint,
        "inventory_sha256": inventory_sha256,
        "observation_id": None,
        "observed_at": None,
        "parent_ids": [],
        "match_count": 0,
        "matches": [],
        "mapping": None,
        "blockers": [],
    }
    if fingerprint is None:
        plan = seal_drive_mapping_plan(
            {**base, "status": "blocked", "action": None, "blockers": ["repository-identity-unavailable"]}
        )
    else:
        try:
            parents, candidates, observation_id, observed_at = validate_drive_mapping_inventory(
                inventory, project_root
            )
        except ContextSyncError:
            plan = seal_drive_mapping_plan(
                {**base, "status": "blocked", "action": None, "blockers": ["untrusted-drive-structure"]}
            )
        else:
            matches = [item for item in candidates if item["repository_fingerprint"] == fingerprint]
            common = {
                **base,
                "observation_id": observation_id,
                "observed_at": observed_at.isoformat().replace("+00:00", "Z"),
                "parent_ids": [parent["id"] for parent in parents],
                "match_count": len(matches),
                "matches": [item["project_id"] for item in matches],
            }
            if len(matches) > 1:
                plan = seal_drive_mapping_plan(
                    {**common, "status": "blocked", "action": None, "blockers": ["duplicate-mapping"]}
                )
            elif matches:
                mapping = {key: value for key, value in matches[0].items() if key != "repository_fingerprint"}
                plan = seal_drive_mapping_plan(
                    {**common, "status": "ready", "action": "reuse", "mapping": mapping}
                )
            elif not parents:
                plan = seal_drive_mapping_plan(
                    {
                        **common,
                        "status": "ready",
                        "action": "create-parent",
                        "mapping": {"parent_title": "Codex Project Context"},
                    }
                )
            elif len(parents) > 1:
                plan = seal_drive_mapping_plan(
                    {**common, "status": "blocked", "action": None, "blockers": ["ambiguous-parent"]}
                )
            else:
                parent = parents[0]
                project_id = "proj-" + hashlib.sha256(
                    f"{parent['id']}\0{fingerprint}".encode("utf-8")
                ).hexdigest()[:16]
                plan = seal_drive_mapping_plan(
                    {
                        **common,
                        "status": "ready",
                        "action": "create",
                        "mapping": {
                            "project_id": project_id,
                            "drive_parent_folder_id": parent["id"],
                        },
                    }
                )
    atomic_write_json(output_path, plan)
    return plan


def load_drive_mapping_plan(
    path_value: str, project_root: Path, expected_action: str
) -> dict[str, Any]:
    path = resolved(path_value)
    validate_external_path(path, project_root, "Drive mapping plan")
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ContextSyncError(f"Drive mapping plan is invalid: {error}") from error
    if not isinstance(plan, dict) or set(plan) != {
        "schema_version",
        "project_path",
        "repository_fingerprint",
        "inventory_sha256",
        "observation_id",
        "observed_at",
        "parent_ids",
        "match_count",
        "matches",
        "mapping",
        "blockers",
        "status",
        "action",
        "plan_sha256",
    } or plan.get("plan_sha256") != canonical_digest(
        {key: value for key, value in plan.items() if key != "plan_sha256"}
    ):
        raise ContextSyncError("Drive mapping plan digest does not match")
    if plan.get("schema_version") != 1:
        raise ContextSyncError("Drive mapping plan version is unsupported")
    validate_drive_observation(
        plan.get("observation_id"), plan.get("observed_at")
    )
    if plan.get("status") != "ready" or plan.get("action") != expected_action:
        raise ContextSyncError(f"Drive mapping plan does not authorize {expected_action}")
    if plan.get("project_path") != str(project_root):
        raise ContextSyncError("Drive mapping plan belongs to another project path")
    if plan.get("repository_fingerprint") != repository_fingerprint(project_root):
        raise ContextSyncError("Drive mapping plan belongs to another repository")
    mapping = plan.get("mapping")
    if not isinstance(mapping, dict):
        raise ContextSyncError("Drive mapping plan has no mapping")
    expected_mapping_fields = (
        {"project_id", "drive_parent_folder_id"}
        if expected_action == "create"
        else {
            "project_id",
            "drive_parent_folder_id",
            "drive_project_folder_id",
            "drive_checkpoints_folder_id",
            "drive_marker_file_id",
            "marker_file",
            "marker_sha256",
        }
    )
    if set(mapping) != expected_mapping_fields:
        raise ContextSyncError("Drive mapping plan mapping shape is invalid")
    return plan


def load_project_marker(directory: Path) -> dict[str, Any]:
    return load_project_marker_file(directory / "project.json")


def validate_storage(
    entry: dict[str, Any], current_fingerprint: str | None, directory: Path | None = None
) -> Path:
    directory = directory or project_directory(entry)
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


def checkpoint_stream_id(checkpoint: dict[str, Any]) -> str:
    return str(checkpoint.get("stream_id", DEFAULT_STREAM_ID))


def checkpoint_snapshot_kind(checkpoint: dict[str, Any]) -> str:
    # Version 1 checkpoints always described a complete project handoff.
    return str(checkpoint.get("snapshot_kind", "baseline"))


def validate_stream_id(value: object) -> str:
    if value == DEFAULT_STREAM_ID:
        return DEFAULT_STREAM_ID
    if not isinstance(value, str) or not STREAM_ID_PATTERN.fullmatch(value):
        raise ContextSyncError(
            "stream_id must be 'project' or stream- followed by 16-64 lowercase hex characters"
        )
    return value


def load_checkpoint_file(
    path: Path, project_id: str, *, require_filename: bool = True
) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ContextSyncError(f"Checkpoint is invalid: {path}: {error}") from error
    if (
        not isinstance(value, dict)
        or value.get("schema_version") not in SUPPORTED_CHECKPOINT_VERSIONS
    ):
        raise ContextSyncError(f"Checkpoint version is unsupported: {path}")
    allowed = {
        "schema_version",
        "checkpoint_id",
        "project_id",
        "machine_id",
        "created_at",
        "parent_checkpoint_ids",
        "repository",
        "context",
        "content_sha256",
    }
    if value["schema_version"] == CHECKPOINT_VERSION:
        allowed.update({"stream_id", "snapshot_kind"})
    unexpected = set(value) - allowed
    if unexpected:
        raise ContextSyncError(
            f"Checkpoint has unexpected fields: {sorted(unexpected)}: {path}"
        )
    if value.get("project_id") != project_id:
        raise ContextSyncError(f"Checkpoint project_id mismatch: {path}")
    checkpoint_id = value.get("checkpoint_id")
    if not isinstance(checkpoint_id, str) or not re.fullmatch(
        r"checkpoint-[0-9a-f]{32}", checkpoint_id
    ):
        raise ContextSyncError(f"Checkpoint id is invalid: {path}")
    if require_filename and path.stem != checkpoint_id:
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
    if value["schema_version"] == CHECKPOINT_VERSION:
        try:
            validate_stream_id(value.get("stream_id"))
        except ContextSyncError as error:
            raise ContextSyncError(f"Checkpoint stream is invalid: {path}") from error
        if value.get("snapshot_kind") not in {"baseline", "delta"}:
            raise ContextSyncError(f"Checkpoint snapshot kind is invalid: {path}")
    try:
        validate_context(value.get("context"), "paths")
    except ContextSyncError as error:
        raise ContextSyncError(f"Checkpoint context is invalid: {path}: {error}") from error
    if value.get("content_sha256") != checkpoint_digest(value):
        raise ContextSyncError(f"Checkpoint digest does not match: {path}")
    if scan_secrets(value):
        raise ContextSyncError(f"Checkpoint contains a possible secret: {path}")
    return value


def load_checkpoints(
    directory: Path, project_id: str
) -> list[dict[str, Any]]:
    checkpoints = [
        load_checkpoint_file(path, project_id)
        for path in sorted((directory / "checkpoints").glob("*.json"))
    ]
    checkpoints.sort(
        key=lambda item: (
            str(item.get("created_at", "")),
            str(item.get("checkpoint_id", "")),
        )
    )
    validate_checkpoint_graph(checkpoints)
    return checkpoints


def validate_checkpoint_graph(checkpoints: list[dict[str, Any]]) -> None:
    by_id = {item["checkpoint_id"]: item for item in checkpoints}
    if len(by_id) != len(checkpoints):
        raise ContextSyncError("Checkpoint IDs are duplicated")
    missing = sorted(
        {
            parent
            for item in checkpoints
            for parent in item["parent_checkpoint_ids"]
            if parent not in by_id
        }
    )
    if missing:
        raise ContextSyncError(
            "Checkpoint history is incomplete; missing parents: "
            + ", ".join(missing)
        )
    for item in checkpoints:
        stream_id = checkpoint_stream_id(item)
        for parent_id in item["parent_checkpoint_ids"]:
            if checkpoint_stream_id(by_id[parent_id]) != stream_id:
                raise ContextSyncError(
                    "Checkpoint history crosses stream boundaries: "
                    f"{item['checkpoint_id']}"
                )
        if (
            item.get("schema_version") == CHECKPOINT_VERSION
            and not item["parent_checkpoint_ids"]
            and checkpoint_snapshot_kind(item) != "baseline"
        ):
            raise ContextSyncError(
                f"Checkpoint stream root must be a baseline: {item['checkpoint_id']}"
            )
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(checkpoint_id: str) -> None:
        if checkpoint_id in visiting:
            raise ContextSyncError("Checkpoint history contains a cycle")
        if checkpoint_id in visited:
            return
        visiting.add(checkpoint_id)
        for parent in by_id[checkpoint_id]["parent_checkpoint_ids"]:
            visit(parent)
        visiting.remove(checkpoint_id)
        visited.add(checkpoint_id)

    for checkpoint_id in by_id:
        visit(checkpoint_id)


def checkpoint_heads(
    checkpoints: list[dict[str, Any]],
    stream_id: str | None = None,
) -> list[dict[str, Any]]:
    selected = [
        item
        for item in checkpoints
        if stream_id is None or checkpoint_stream_id(item) == stream_id
    ]
    referenced = {
        parent
        for item in selected
        for parent in item.get("parent_checkpoint_ids", [])
    }
    heads = [
        item
        for item in selected
        if item.get("checkpoint_id") not in referenced
    ]
    heads.sort(
        key=lambda item: (
            str(item.get("created_at", "")),
            str(item.get("checkpoint_id", "")),
        )
    )
    return heads


def checkpoint_stream_ids(checkpoints: list[dict[str, Any]]) -> list[str]:
    return sorted({checkpoint_stream_id(item) for item in checkpoints})


def checkpoint_history(
    checkpoints: list[dict[str, Any]], latest: dict[str, Any]
) -> list[dict[str, Any]]:
    by_id = {item["checkpoint_id"]: item for item in checkpoints}
    visited: set[str] = set()
    history: list[dict[str, Any]] = []

    def append_after_parents(item: dict[str, Any]) -> None:
        checkpoint_id = item["checkpoint_id"]
        if checkpoint_id in visited:
            return
        for parent_id in sorted(item["parent_checkpoint_ids"]):
            append_after_parents(by_id[parent_id])
        visited.add(checkpoint_id)
        history.append(item)

    append_after_parents(latest)
    # A new full baseline supersedes earlier history on a linear stream. Keep
    # the complete ancestry for merge histories, where one baseline may not
    # dominate every parent branch.
    if all(len(item["parent_checkpoint_ids"]) <= 1 for item in history):
        baseline_indexes = [
            index
            for index, item in enumerate(history)
            if checkpoint_snapshot_kind(item) == "baseline"
        ]
        if baseline_indexes:
            history = history[baseline_indexes[-1] :]
    return history


def effective_chat_title(
    checkpoints: list[dict[str, Any]], latest: dict[str, Any]
) -> str | None:
    for item in reversed(checkpoint_history(checkpoints, latest)):
        title = item.get("context", {}).get("chat_title")
        if isinstance(title, str) and title:
            return title
    return None


def stream_single_head(
    checkpoints: list[dict[str, Any]], stream_id: str
) -> dict[str, Any] | None:
    selected = [
        item for item in checkpoints if checkpoint_stream_id(item) == stream_id
    ]
    heads = checkpoint_heads(selected, stream_id)
    return heads[0] if len(heads) == 1 else None


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


def validate_external_path(
    path: Path, project_root: Path, label: str, *, reject_git: bool = True
) -> None:
    if path == project_root or is_within(path, project_root):
        raise ContextSyncError(f"{label} must stay outside the project directory")
    git_root = enclosing_git_root(path)
    if reject_git and git_root is not None:
        raise ContextSyncError(
            f"{label} must stay outside every Git worktree: {git_root}"
        )


def project_marker(project_root: Path, project_id: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "project_id": project_id,
        "repository_fingerprint": repository_fingerprint(project_root),
        "created_at": utc_now(),
    }


def command_prepare_drive_marker(args: argparse.Namespace) -> dict[str, Any]:
    if not args.acknowledge_storage_policy:
        raise ContextSyncError(
            "Pass --acknowledge-storage-policy after confirming the Drive account is approved"
        )
    project_root = resolved(args.project_path)
    if not project_root.is_dir():
        raise ContextSyncError(f"Project directory does not exist: {project_root}")
    output = resolved(args.output)
    validate_external_path(output, project_root, "Marker output")
    mapping_plan_value = getattr(args, "mapping_plan", None)
    planned_project_id: str | None = None
    if mapping_plan_value:
        mapping_plan = load_drive_mapping_plan(
            mapping_plan_value, project_root, "create"
        )
        planned_project_id = mapping_plan["mapping"].get("project_id")
    project_id = args.project_id or planned_project_id
    if project_id is None:
        raise ContextSyncError(
            "prepare-drive-marker requires a verified zero-match --mapping-plan"
        )
    if planned_project_id and args.project_id and args.project_id != planned_project_id:
        raise ContextSyncError("Explicit project_id conflicts with the Drive mapping plan")
    if not PROJECT_ID_PATTERN.fullmatch(project_id):
        raise ContextSyncError(
            "project_id must be 3-64 lowercase letters, digits, or hyphens"
        )
    marker = project_marker(project_root, project_id)
    atomic_write_json(output, marker)
    return {
        "prepared": True,
        "backend": "google-drive",
        "project_id": project_id,
        "marker_path": str(output),
        "repository_fingerprint": marker["repository_fingerprint"],
    }


def command_backend_plan(args: argparse.Namespace) -> dict[str, Any]:
    project_root = resolved(args.project_path)
    if not project_root.is_dir():
        raise ContextSyncError(
            f"Project directory does not exist: {project_root}"
        )
    config_path = (
        resolved(args.config_path) if args.config_path else default_config_path()
    )
    if is_within(config_path, project_root):
        raise ContextSyncError(
            "Configuration path must stay outside the project directory"
        )
    config = load_config(config_path, allow_missing=True)
    identity = os.path.normcase(str(project_root))
    matches = [
        item
        for item in config["projects"]
        if os.path.normcase(str(resolved(item["local_root"]))) == identity
    ]
    if len(matches) > 1:
        raise ContextSyncError(
            "Configuration contains duplicate project mappings"
        )
    configured_backend = matches[0]["backend"] if matches else None
    plan = plan_backend_selection(
        configured_backend=configured_backend,
        requested_backend=getattr(args, "requested_backend", None),
        google_drive_connected=getattr(args, "google_drive_connected", False),
    )
    result = {
        "project_path": str(project_root),
        "configured": configured_backend is not None,
        **plan,
    }
    if configured_backend is None and plan.get("backend") == "google-drive":
        result["requires_mapping_discovery"] = True
        result["next_steps"] = ["enumerate-drive-mappings", "run-drive-mapping-plan"]
    return result


def command_configure(args: argparse.Namespace) -> dict[str, Any]:
    if not args.acknowledge_storage_policy:
        raise ContextSyncError(
            "Pass --acknowledge-storage-policy after confirming the storage is approved"
        )
    project_root = resolved(args.project_path)
    if not project_root.is_dir():
        raise ContextSyncError(
            f"Project directory does not exist: {project_root}"
        )
    backend = getattr(args, "backend", "local-folder")
    marker_file = getattr(args, "marker_file", None)
    mapping_plan_value = getattr(args, "mapping_plan", None)
    mapping_plan: dict[str, Any] | None = None
    if backend == "google-drive" and mapping_plan_value:
        mapping_plan = load_drive_mapping_plan(
            mapping_plan_value, project_root, "reuse"
        )
        planned = mapping_plan["mapping"]
        for label, explicit in (
            ("project_id", getattr(args, "project_id", None)),
            ("marker_file", marker_file),
            ("drive_project_folder_id", getattr(args, "drive_project_folder_id", None)),
            ("drive_checkpoints_folder_id", getattr(args, "drive_checkpoints_folder_id", None)),
            ("drive_marker_file_id", getattr(args, "drive_marker_file_id", None)),
        ):
            if explicit is not None and str(explicit) != str(planned.get(label)):
                raise ContextSyncError(f"Explicit {label} conflicts with the Drive mapping plan")
        readback_value = getattr(args, "readback_inventory", None)
        if not readback_value:
            raise ContextSyncError(
                "Drive mapping reuse requires a fresh --readback-inventory"
            )
        readback_path = resolved(readback_value)
        validate_external_path(readback_path, project_root, "Drive readback inventory")
        try:
            readback = json.loads(readback_path.read_text(encoding="utf-8"))
            (
                _,
                fresh_candidates,
                fresh_observation_id,
                fresh_observed_at,
            ) = validate_drive_mapping_inventory(readback, project_root)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ContextSyncError) as error:
            raise ContextSyncError(
                f"Drive mapping readback no longer matches the plan: {error}"
            ) from error
        fingerprint = repository_fingerprint(project_root)
        planned_observation_id = mapping_plan.get("observation_id")
        planned_observed_at_value = mapping_plan.get("observed_at")
        try:
            planned_observed_at = datetime.fromisoformat(
                str(planned_observed_at_value)[:-1] + "+00:00"
            )
        except ValueError as error:
            raise ContextSyncError("Drive mapping plan observation is invalid") from error
        if (
            fresh_observation_id == planned_observation_id
            or fresh_observed_at <= planned_observed_at
        ):
            raise ContextSyncError(
                "Drive mapping reuse requires a newer Drive observation"
            )
        fresh_matches = [
            item
            for item in fresh_candidates
            if item["repository_fingerprint"] == fingerprint
        ]
        if len(fresh_matches) != 1:
            raise ContextSyncError(
                "Drive mapping readback no longer matches the plan"
            )
        fresh = fresh_matches[0]
        bound_fields = {
            "project_id",
            "drive_parent_folder_id",
            "drive_project_folder_id",
            "drive_checkpoints_folder_id",
            "drive_marker_file_id",
            "marker_sha256",
        }
        if any(fresh.get(field) != planned.get(field) for field in bound_fields):
            raise ContextSyncError(
                "Drive mapping readback no longer matches the plan"
            )
        marker_file = fresh["marker_file"]
    marker: dict[str, Any] | None = None
    if backend == "google-drive":
        if not marker_file:
            raise ContextSyncError("Google Drive configuration requires --marker-file")
        marker_path = resolved(marker_file)
        validate_external_path(marker_path, project_root, "Marker file")
        if mapping_plan:
            marker = load_discovery_project_marker(
                marker_path, mapping_plan["mapping"]["marker_sha256"]
            )
        else:
            marker = load_project_marker_file(marker_path)
    planned_project_id = mapping_plan["mapping"]["project_id"] if mapping_plan else None
    project_id = args.project_id or planned_project_id or (
        str(marker.get("project_id")) if marker else f"proj-{uuid.uuid4().hex[:16]}"
    )
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
    if backend == "local-folder":
        storage_value = getattr(args, "storage_root", None)
        if not storage_value:
            raise ContextSyncError("Local-folder configuration requires --storage-root")
        storage_root = resolved(storage_value)
        validate_external_path(storage_root, project_root, "Storage root")
        directory = storage_root / project_id
        marker_path = directory / "project.json"
        if marker_path.exists():
            marker = load_project_marker(directory)
        else:
            marker = project_marker(project_root, project_id)
            atomic_write_json(marker_path, marker)
        (directory / "checkpoints").mkdir(parents=True, exist_ok=True)
        new_entry = {
            "project_id": project_id,
            "local_root": str(project_root),
            "backend": backend,
            "storage_root": str(storage_root),
            "mode": args.mode,
        }
        storage_project = str(directory)
    else:
        planned_mapping = mapping_plan["mapping"] if mapping_plan else {}
        drive_fields = {
            "drive_project_folder_id": getattr(args, "drive_project_folder_id", None) or planned_mapping.get("drive_project_folder_id"),
            "drive_checkpoints_folder_id": getattr(args, "drive_checkpoints_folder_id", None) or planned_mapping.get("drive_checkpoints_folder_id"),
            "drive_marker_file_id": getattr(args, "drive_marker_file_id", None) or planned_mapping.get("drive_marker_file_id"),
        }
        if not all(isinstance(value, str) and value.strip() for value in drive_fields.values()):
            raise ContextSyncError("Google Drive configuration requires all Drive file and folder IDs")
        new_entry = {
            "project_id": project_id,
            "local_root": str(project_root),
            "backend": backend,
            **drive_fields,
            "mode": args.mode,
        }
        storage_project = f"google-drive:{drive_fields['drive_project_folder_id']}"
    if marker is None or marker.get("project_id") != project_id:
        raise ContextSyncError("Storage marker uses another project_id")
    expected = marker.get("repository_fingerprint")
    if expected and fingerprint and expected != fingerprint:
        raise ContextSyncError("Storage marker belongs to another repository")
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
        "backend": backend,
        "project_id": project_id,
        "mode": args.mode,
        "config_path": str(config_path),
        "storage_project": storage_project,
    }


def configured_mapping(
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
    current = repository_state(project_root, entry["mode"])
    return project_root, config_path, config, entry, current


def active_storage_directory(
    args: argparse.Namespace,
    project_root: Path,
    entry: dict[str, Any],
    current: dict[str, Any],
) -> Path:
    if entry["backend"] == "local-folder":
        storage_root = resolved(entry["storage_root"])
        validate_external_path(storage_root, project_root, "Configured storage root")
        directory = project_directory(entry)
    else:
        snapshot_value = getattr(args, "snapshot_root", None)
        if not snapshot_value:
            raise ContextSyncError(
                "Google Drive operations require --snapshot-root after connector hydration"
            )
        directory = resolved(snapshot_value)
        validate_external_path(directory, project_root, "Drive snapshot")
    validate_storage(entry, current.get("fingerprint"), directory)
    return directory


def configured_context(
    args: argparse.Namespace,
) -> tuple[
    Path,
    Path,
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    Path,
]:
    project_root, config_path, config, entry, current = configured_mapping(args)
    directory = active_storage_directory(args, project_root, entry, current)
    return project_root, config_path, config, entry, current, directory


def command_transport(args: argparse.Namespace) -> dict[str, Any]:
    _root, config_path, _config, entry, current = configured_mapping(args)
    result = {
        "configured": True,
        "backend": entry["backend"],
        "project_id": entry["project_id"],
        "mode": entry["mode"],
        "config_path": str(config_path),
        "current_repository": current,
    }
    if entry["backend"] == "local-folder":
        result["storage_project"] = str(project_directory(entry))
    else:
        result.update(
            {
                "drive_project_folder_id": entry["drive_project_folder_id"],
                "drive_checkpoints_folder_id": entry["drive_checkpoints_folder_id"],
                "drive_marker_file_id": entry["drive_marker_file_id"],
                "requires_connector_hydration": True,
            }
        )
    return result


def command_hydrate_drive(args: argparse.Namespace) -> dict[str, Any]:
    project_root, _config_path, _config, entry, current = configured_mapping(args)
    if entry["backend"] != "google-drive":
        raise ContextSyncError("hydrate-drive requires a Google Drive mapping")
    output_root = resolved(args.output_root)
    validate_external_path(output_root, project_root, "Drive snapshot")
    if output_root.exists() and any(output_root.iterdir()):
        raise ContextSyncError("Drive snapshot output must be absent or empty")
    marker_path = resolved(args.marker_file)
    validate_external_path(marker_path, project_root, "Downloaded marker")
    marker = load_project_marker_file(marker_path)
    if marker.get("project_id") != entry["project_id"]:
        raise ContextSyncError("Downloaded marker project_id mismatch")
    expected = marker.get("repository_fingerprint")
    fingerprint = current.get("fingerprint")
    if expected and fingerprint and expected != fingerprint:
        raise ContextSyncError("Downloaded marker belongs to another repository")
    values: dict[str, dict[str, Any]] = {}
    for value in getattr(args, "checkpoint_file", []) or []:
        source = resolved(value)
        validate_external_path(source, project_root, "Downloaded checkpoint")
        checkpoint = load_checkpoint_file(
            source, entry["project_id"], require_filename=False
        )
        checkpoint_id = checkpoint["checkpoint_id"]
        if checkpoint_id in values:
            raise ContextSyncError(f"Downloaded checkpoint is duplicated: {checkpoint_id}")
        values[checkpoint_id] = checkpoint
    validate_checkpoint_graph(list(values.values()))
    atomic_write_json(output_root / "project.json", marker)
    (output_root / "checkpoints").mkdir(parents=True, exist_ok=True)
    for checkpoint_id, checkpoint in values.items():
        atomic_write_json(
            output_root / "checkpoints" / f"{checkpoint_id}.json", checkpoint
        )
    load_checkpoints(output_root, entry["project_id"])
    return {
        "hydrated": True,
        "backend": "google-drive",
        "project_id": entry["project_id"],
        "snapshot_root": str(output_root),
        "checkpoint_count": len(values),
    }


def command_status(args: argparse.Namespace) -> dict[str, Any]:
    _project_root, config_path, _config, entry, current, directory = configured_context(
        args
    )
    checkpoints = load_checkpoints(directory, entry["project_id"])
    requested_stream = getattr(args, "stream_id", None)
    if requested_stream is not None:
        requested_stream = validate_stream_id(requested_stream)
    stream_ids = checkpoint_stream_ids(checkpoints)
    if requested_stream is not None:
        stream_ids = [
            stream_id for stream_id in stream_ids if stream_id == requested_stream
        ]
    streams = []
    all_heads: list[dict[str, Any]] = []
    for stream_id in stream_ids:
        stream_checkpoints = [
            item for item in checkpoints if checkpoint_stream_id(item) == stream_id
        ]
        heads = checkpoint_heads(stream_checkpoints, stream_id)
        all_heads.extend(heads)
        latest = heads[-1] if len(heads) == 1 else None
        recorded = latest.get("repository", {}) if latest else {}
        streams.append(
            {
                "stream_id": stream_id,
                "checkpoint_count": len(stream_checkpoints),
                "head_checkpoint_ids": [item["checkpoint_id"] for item in heads],
                "latest_checkpoint_id": latest.get("checkpoint_id") if latest else None,
                "latest_created_at": latest.get("created_at") if latest else None,
                "head_matches": bool(latest)
                and recorded.get("head") == current.get("head"),
                "worktree_matches": bool(latest)
                and recorded.get("dirty") == current.get("dirty"),
                "has_conflict": len(heads) > 1,
            }
        )
    single = streams[0] if len(streams) == 1 else None
    latest = None
    if single and single["latest_checkpoint_id"]:
        latest = next(
            item
            for item in checkpoints
            if item["checkpoint_id"] == single["latest_checkpoint_id"]
        )
    recorded = latest.get("repository", {}) if latest else {}
    return {
        "configured": True,
        "backend": entry["backend"],
        "project_id": entry["project_id"],
        "mode": entry["mode"],
        "config_path": str(config_path),
        "storage_project": (
            str(directory)
            if entry["backend"] == "local-folder"
            else f"google-drive:{entry['drive_project_folder_id']}"
        ),
        "checkpoint_count": len(checkpoints),
        "stream_count": len(streams),
        "streams": streams,
        "head_checkpoint_ids": [item["checkpoint_id"] for item in all_heads],
        "latest_checkpoint_id": (
            latest.get("checkpoint_id") if latest else None
        ),
        "latest_created_at": latest.get("created_at") if latest else None,
        "head_matches": bool(latest)
        and recorded.get("head") == current.get("head"),
        "worktree_matches": bool(latest)
        and recorded.get("dirty") == current.get("dirty"),
        "has_conflict": any(item["has_conflict"] for item in streams),
        "current_repository": current,
    }


def capture_context(
    *,
    config: dict[str, Any],
    entry: dict[str, Any],
    current: dict[str, Any],
    directory: Path,
    context: dict[str, Any],
    stream_id: str,
    requested_kind: str = "auto",
    merge_heads: bool = False,
) -> dict[str, Any]:
    checkpoints = load_checkpoints(directory, entry["project_id"])
    stream_id = validate_stream_id(stream_id)
    stream_checkpoints = [
        item for item in checkpoints if checkpoint_stream_id(item) == stream_id
    ]
    heads = checkpoint_heads(stream_checkpoints, stream_id)
    if len(heads) > 1 and not merge_heads:
        identifiers = ", ".join(item["checkpoint_id"] for item in heads)
        raise ContextSyncError(
            "Concurrent checkpoint heads require explicit review and "
            f"--merge-heads: {identifiers}"
        )
    parents = [item["checkpoint_id"] for item in heads]
    snapshot_kind = (
        "baseline" if not stream_checkpoints else "delta"
    ) if requested_kind == "auto" else requested_kind
    if snapshot_kind not in {"baseline", "delta"}:
        raise ContextSyncError("snapshot_kind must be auto, baseline, or delta")
    if snapshot_kind == "delta" and not parents:
        raise ContextSyncError("A delta checkpoint requires an existing stream baseline")
    checkpoint_id = f"checkpoint-{uuid.uuid4().hex}"
    checkpoint = {
        "schema_version": CHECKPOINT_VERSION,
        "checkpoint_id": checkpoint_id,
        "project_id": entry["project_id"],
        "stream_id": stream_id,
        "snapshot_kind": snapshot_kind,
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
        "backend": entry["backend"],
        "checkpoint_id": checkpoint_id,
        "stream_id": stream_id,
        "snapshot_kind": snapshot_kind,
        "parent_checkpoint_ids": parents,
        "created_at": checkpoint["created_at"],
        "path": str(path),
    }


def command_capture(args: argparse.Namespace) -> dict[str, Any]:
    project_root, _config_path, config, entry, current, directory = configured_context(args)
    context = validate_context(
        load_capture_input(args, project_root), entry["mode"]
    )
    return capture_context(
        config=config,
        entry=entry,
        current=current,
        directory=directory,
        context=context,
        stream_id=getattr(args, "stream_id", None) or DEFAULT_STREAM_ID,
        requested_kind=getattr(args, "snapshot_kind", "auto") or "auto",
        merge_heads=getattr(args, "merge_heads", False),
    )


def load_batch_records(
    args: argparse.Namespace,
    project_root: Path,
    *,
    include_context: bool,
    allow_empty: bool = False,
) -> list[dict[str, Any]]:
    value = load_capture_input(args, project_root)
    if not isinstance(value, dict) or set(value) != {"threads"}:
        raise ContextSyncError("Batch input must contain only a threads array")
    records = value.get("threads")
    if not isinstance(records, list) or (not records and not allow_empty):
        expectation = "an array" if allow_empty else "a non-empty array"
        raise ContextSyncError(f"Batch threads must be {expectation}")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    required = {"thread_id", "source_revision"}
    optional = {"source_head_turn_id", "stream_id", "title"}
    if include_context:
        required.add("context")
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ContextSyncError(f"Batch threads[{index}] must be an object")
        if not required.issubset(record) or set(record) - required - optional:
            raise ContextSyncError(
                f"Batch threads[{index}] has missing or unexpected fields"
            )
        thread_id = record.get("thread_id")
        key = thread_registry_key("project-key-validation", thread_id)
        if key in seen:
            raise ContextSyncError("Batch input contains a duplicate thread_id")
        seen.add(key)
        item: dict[str, Any] = {
            "thread_id": str(thread_id).strip(),
            "source_revision": normalize_source_marker(
                record.get("source_revision"), "source_revision"
            ),
            "source_head_turn_id": normalize_optional_source_marker(
                record.get("source_head_turn_id"), "source_head_turn_id"
            ),
        }
        title = record.get("title")
        if title is not None:
            item["title"] = normalize_chat_title(title)
        supplied_stream = record.get("stream_id")
        if supplied_stream is not None:
            item["stream_id"] = validate_stream_id(supplied_stream)
        if include_context:
            item["context"] = record.get("context")
        normalized.append(item)
    return normalized


def command_batch_plan(args: argparse.Namespace) -> dict[str, Any]:
    project_root, config_path, config, entry, _current, directory = configured_context(args)
    records = load_batch_records(args, project_root, include_context=False)
    registry_path = thread_registry_path(config_path)
    registry = load_thread_registry(registry_path, config["machine_id"])
    bindings = registry_threads(registry, entry["project_id"])
    checkpoints = load_checkpoints(directory, entry["project_id"])
    existing_streams = set(checkpoint_stream_ids(checkpoints))
    plan: list[dict[str, Any]] = []
    counts = {"baseline": 0, "delta": 0, "unchanged": 0}
    planned_streams: dict[str, int] = {}
    for index, record in enumerate(records):
        key = thread_registry_key(entry["project_id"], record["thread_id"])
        binding = bindings.get(key)
        supplied_stream = record.get("stream_id")
        if binding and supplied_stream and supplied_stream != binding["stream_id"]:
            raise ContextSyncError(
                f"Batch threads[{index}] stream_id conflicts with the local registry"
            )
        stream_id = supplied_stream or (
            binding["stream_id"]
            if binding
            else default_thread_stream_id(entry["project_id"], record["thread_id"])
        )
        if stream_id in planned_streams:
            raise ContextSyncError(
                "Multiple local threads resolve to the same stream: "
                f"indexes {planned_streams[stream_id]} and {index}"
            )
        planned_streams[stream_id] = index
        latest = stream_single_head(checkpoints, stream_id)
        stored_title = (
            effective_chat_title(checkpoints, latest) if latest else None
        )
        title_changed = (
            record.get("title") is not None
            and record["title"] != stored_title
        )
        revision_changed = not (
            binding and binding["source_revision"] == record["source_revision"]
        )
        if binding and not revision_changed and not title_changed:
            action = "unchanged"
            read_scope = "none"
        elif binding or stream_id in existing_streams:
            action = "delta"
            if not revision_changed and title_changed:
                read_scope = "none"
            else:
                read_scope = (
                    "after_previous_head"
                    if binding and binding["source_head_turn_id"]
                    else "full_review"
                )
        else:
            action = "baseline"
            read_scope = "full_history"
        counts[action] += 1
        plan.append(
            {
                "index": index,
                "action": action,
                "read_scope": read_scope,
                "stream_id": stream_id,
                "title_changed": title_changed,
                "previous_source_revision": (
                    binding["source_revision"] if binding else None
                ),
                "previous_source_head_turn_id": (
                    binding["source_head_turn_id"] if binding else None
                ),
            }
        )
    return {
        "planned": True,
        "project_id": entry["project_id"],
        "registry_path": str(registry_path),
        "thread_count": len(plan),
        "counts": counts,
        "threads": plan,
    }


def command_batch_capture(args: argparse.Namespace) -> dict[str, Any]:
    project_root, config_path, config, entry, current, directory = configured_context(args)
    records = load_batch_records(args, project_root, include_context=True)
    registry_path = thread_registry_path(config_path)
    registry = load_thread_registry(registry_path, config["machine_id"])
    bindings = registry_threads(registry, entry["project_id"])
    checkpoints = load_checkpoints(directory, entry["project_id"])
    prepared: list[
        tuple[
            int,
            dict[str, Any],
            str,
            dict[str, Any] | None,
            dict[str, Any],
        ]
    ] = []
    prepared_streams: dict[str, int] = {}
    for index, record in enumerate(records):
        key = thread_registry_key(entry["project_id"], record["thread_id"])
        binding = bindings.get(key)
        supplied_stream = record.get("stream_id")
        if binding and supplied_stream and supplied_stream != binding["stream_id"]:
            raise ContextSyncError(
                f"Batch threads[{index}] stream_id conflicts with the local registry"
            )
        stream_id = supplied_stream or (
            binding["stream_id"]
            if binding
            else default_thread_stream_id(entry["project_id"], record["thread_id"])
        )
        if stream_id in prepared_streams:
            raise ContextSyncError(
                "Multiple local threads resolve to the same stream: "
                f"indexes {prepared_streams[stream_id]} and {index}"
            )
        prepared_streams[stream_id] = index
        raw_context = record["context"]
        if not isinstance(raw_context, dict):
            raise ContextSyncError(
                f"Batch threads[{index}] context must be an object"
            )
        raw_context = dict(raw_context)
        if record.get("title") is not None:
            supplied_context_title = raw_context.get("chat_title")
            if (
                supplied_context_title is not None
                and supplied_context_title != record["title"]
            ):
                raise ContextSyncError(
                    f"Batch threads[{index}] title conflicts with context chat_title"
                )
            raw_context["chat_title"] = record["title"]
        context = validate_context(raw_context, entry["mode"])
        prepared.append((index, record, key, binding, context))
    results: list[dict[str, Any]] = []
    skipped = 0
    for index, record, key, binding, context in prepared:
        supplied_stream = record.get("stream_id")
        stream_id = supplied_stream or (
            binding["stream_id"]
            if binding
            else default_thread_stream_id(entry["project_id"], record["thread_id"])
        )
        latest = stream_single_head(checkpoints, stream_id)
        stored_title = (
            effective_chat_title(checkpoints, latest) if latest else None
        )
        title_changed = (
            record.get("title") is not None
            and record["title"] != stored_title
        )
        if (
            binding
            and binding["source_revision"] == record["source_revision"]
            and not title_changed
        ):
            skipped += 1
            results.append(
                {
                    "index": index,
                    "stream_id": stream_id,
                    "skipped": True,
                    "reason": "unchanged",
                }
            )
            continue
        captured = capture_context(
            config=config,
            entry=entry,
            current=current,
            directory=directory,
            context=context,
            stream_id=stream_id,
        )
        bindings[key] = {
            "stream_id": stream_id,
            "source_revision": record["source_revision"],
            "source_head_turn_id": record["source_head_turn_id"],
            "last_checkpoint_id": captured["checkpoint_id"],
            "updated_at": utc_now(),
        }
        atomic_write_json(registry_path, registry)
        results.append({"index": index, "skipped": False, **captured})
    return {
        "captured": True,
        "project_id": entry["project_id"],
        "registry_path": str(registry_path),
        "thread_count": len(records),
        "checkpoint_count": len(records) - skipped,
        "skipped_count": skipped,
        "threads": results,
    }


def command_bind_thread(args: argparse.Namespace) -> dict[str, Any]:
    _project_root, config_path, config, entry, _current, directory = configured_context(args)
    stream_id = validate_stream_id(args.stream_id)
    checkpoints = load_checkpoints(directory, entry["project_id"])
    if stream_id not in checkpoint_stream_ids(checkpoints):
        raise ContextSyncError(f"Checkpoint stream does not exist: {stream_id}")
    stream_checkpoints = [
        item for item in checkpoints if checkpoint_stream_id(item) == stream_id
    ]
    heads = checkpoint_heads(stream_checkpoints, stream_id)
    requested_checkpoint = getattr(args, "checkpoint_id", None)
    if requested_checkpoint is not None:
        selected = next(
            (
                item
                for item in stream_checkpoints
                if item["checkpoint_id"] == requested_checkpoint
            ),
            None,
        )
        if selected is None:
            raise ContextSyncError(
                "Materialized checkpoint does not belong to the selected stream"
            )
        materialized_checkpoint_id = selected["checkpoint_id"]
    elif len(heads) == 1:
        materialized_checkpoint_id = heads[0]["checkpoint_id"]
    else:
        raise ContextSyncError(
            "A conflicted stream requires an explicit --checkpoint-id binding"
        )
    key = thread_registry_key(entry["project_id"], args.thread_id)
    registry_path = thread_registry_path(config_path)
    registry = load_thread_registry(registry_path, config["machine_id"])
    bindings = registry_threads(registry, entry["project_id"])
    existing = bindings.get(key)
    if existing and existing["stream_id"] != stream_id:
        raise ContextSyncError("Thread is already bound to another stream")
    duplicate = next(
        (
            binding
            for other_key, binding in bindings.items()
            if other_key != key and binding["stream_id"] == stream_id
        ),
        None,
    )
    if duplicate is not None:
        raise ContextSyncError(
            "Another local thread is already bound to this stream"
        )
    bindings[key] = {
        "stream_id": stream_id,
        "source_revision": normalize_optional_source_marker(
            args.source_revision, "source_revision"
        ),
        "source_head_turn_id": normalize_optional_source_marker(
            args.source_head_turn_id, "source_head_turn_id"
        ),
        "last_checkpoint_id": materialized_checkpoint_id,
        "updated_at": utc_now(),
    }
    atomic_write_json(registry_path, registry)
    return {
        "bound": True,
        "project_id": entry["project_id"],
        "stream_id": stream_id,
        "checkpoint_id": materialized_checkpoint_id,
        "registry_path": str(registry_path),
    }


def load_materialization_threads(
    args: argparse.Namespace, project_root: Path
) -> list[dict[str, str]]:
    value = load_capture_input(args, project_root)
    if not isinstance(value, dict) or set(value) != {"threads"}:
        raise ContextSyncError(
            "Materialization input must contain only a threads array"
        )
    records = value.get("threads")
    if not isinstance(records, list):
        raise ContextSyncError("Materialization threads must be an array")
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict) or set(record) != {"thread_id"}:
            raise ContextSyncError(
                f"Materialization threads[{index}] must contain only thread_id"
            )
        thread_id = record.get("thread_id")
        key = thread_registry_key("project-key-validation", thread_id)
        if key in seen:
            raise ContextSyncError(
                "Materialization input contains a duplicate thread_id"
            )
        seen.add(key)
        normalized.append({"thread_id": str(thread_id).strip()})
    return normalized


def command_materialize_plan(args: argparse.Namespace) -> dict[str, Any]:
    (
        project_root,
        config_path,
        config,
        entry,
        _current,
        directory,
    ) = configured_context(args)
    records = load_materialization_threads(args, project_root)
    registry_path = thread_registry_path(config_path)
    registry = load_thread_registry(registry_path, config["machine_id"])
    bindings = registry_threads(registry, entry["project_id"])
    all_bindings_by_stream: dict[str, list[dict[str, Any]]] = {}
    for binding in bindings.values():
        all_bindings_by_stream.setdefault(binding["stream_id"], []).append(
            binding
        )
    visible_by_stream: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    visible_keys: set[str] = set()
    for index, record in enumerate(records):
        key = thread_registry_key(entry["project_id"], record["thread_id"])
        visible_keys.add(key)
        binding = bindings.get(key)
        if binding:
            visible_by_stream.setdefault(binding["stream_id"], []).append(
                (index, binding)
            )
    hidden_streams = {
        binding["stream_id"]
        for key, binding in bindings.items()
        if key not in visible_keys
    }
    checkpoints = load_checkpoints(directory, entry["project_id"])
    if not checkpoints:
        raise ContextSyncError("No checkpoints are available")
    plan: list[dict[str, Any]] = []
    counts = {
        "create": 0,
        "update": 0,
        "unchanged": 0,
        "unavailable": 0,
        "blocked": 0,
    }
    project_context_checkpoint_id = None
    for stream_id in checkpoint_stream_ids(checkpoints):
        stream_checkpoints = [
            item
            for item in checkpoints
            if checkpoint_stream_id(item) == stream_id
        ]
        heads = checkpoint_heads(stream_checkpoints, stream_id)
        if stream_id == DEFAULT_STREAM_ID:
            if len(heads) == 1:
                project_context_checkpoint_id = heads[0]["checkpoint_id"]
            continue
        targets = visible_by_stream.get(stream_id, [])
        target_index = targets[0][0] if len(targets) == 1 else None
        latest_checkpoint_id = (
            heads[0]["checkpoint_id"] if len(heads) == 1 else None
        )
        chat_title = (
            effective_chat_title(checkpoints, heads[0])
            if len(heads) == 1
            else None
        )
        all_targets = all_bindings_by_stream.get(stream_id, [])
        if len(heads) != 1:
            action = "blocked"
            reason = "concurrent_checkpoint_heads"
        elif len(all_targets) > 1:
            action = "blocked"
            reason = "multiple_local_tasks_bound"
        elif len(targets) == 1:
            last_checkpoint_id = targets[0][1]["last_checkpoint_id"]
            if last_checkpoint_id == latest_checkpoint_id:
                action = "unchanged"
                reason = "already_materialized"
            else:
                action = "update"
                reason = "new_checkpoint_available"
        elif stream_id in hidden_streams:
            action = "unavailable"
            reason = "bound_task_not_in_desktop_listing"
        else:
            action = "create"
            reason = "no_local_task_binding"
        counts[action] += 1
        plan.append(
            {
                "stream_id": stream_id,
                "action": action,
                "reason": reason,
                "target_index": target_index,
                "latest_checkpoint_id": latest_checkpoint_id,
                "chat_title": chat_title,
                "title_available": chat_title is not None,
                "head_checkpoint_ids": [
                    item["checkpoint_id"] for item in heads
                ],
            }
        )
    return {
        "planned": True,
        "project_id": entry["project_id"],
        "registry_path": str(registry_path),
        "discoverable_thread_count": len(records),
        "stream_count": len(plan),
        "counts": counts,
        "project_context_checkpoint_id": project_context_checkpoint_id,
        "streams": plan,
    }


def command_sync_plan(args: argparse.Namespace) -> dict[str, Any]:
    (
        project_root,
        config_path,
        config,
        entry,
        _current,
        directory,
    ) = configured_context(args)
    records = load_batch_records(
        args, project_root, include_context=False, allow_empty=True
    )
    registry_path = thread_registry_path(config_path)
    registry = load_thread_registry(registry_path, config["machine_id"])
    bindings = registry_threads(registry, entry["project_id"])
    checkpoints = load_checkpoints(directory, entry["project_id"])
    by_id = {item["checkpoint_id"]: item for item in checkpoints}
    all_bindings_by_stream: dict[str, list[dict[str, Any]]] = {}
    for binding in bindings.values():
        all_bindings_by_stream.setdefault(binding["stream_id"], []).append(
            binding
        )

    local_by_stream: dict[str, list[tuple[int, dict[str, Any], dict[str, Any] | None]]] = {}
    visible_keys: set[str] = set()
    for index, record in enumerate(records):
        key = thread_registry_key(entry["project_id"], record["thread_id"])
        visible_keys.add(key)
        binding = bindings.get(key)
        supplied_stream = record.get("stream_id")
        if binding and supplied_stream and supplied_stream != binding["stream_id"]:
            raise ContextSyncError(
                f"Batch threads[{index}] stream_id conflicts with the local registry"
            )
        stream_id = supplied_stream or (
            binding["stream_id"]
            if binding
            else default_thread_stream_id(entry["project_id"], record["thread_id"])
        )
        local_by_stream.setdefault(stream_id, []).append((index, record, binding))

    plan: list[dict[str, Any]] = []
    counts = {
        "save": 0,
        "create": 0,
        "update": 0,
        "unchanged": 0,
        "unavailable": 0,
        "blocked": 0,
    }
    covered_streams: set[str] = set()
    for stream_id, local_targets in sorted(local_by_stream.items()):
        covered_streams.add(stream_id)
        index, record, binding = local_targets[0]
        stream_checkpoints = [
            item
            for item in checkpoints
            if checkpoint_stream_id(item) == stream_id
        ]
        heads = checkpoint_heads(stream_checkpoints, stream_id)
        latest = heads[0] if len(heads) == 1 else None
        latest_id = latest["checkpoint_id"] if latest else None
        remote_title = (
            effective_chat_title(checkpoints, latest) if latest else None
        )
        read_scope = "none"
        preserve_local_title = False
        follow_up_save_title = False
        if len(local_targets) > 1:
            action = "blocked"
            reason = "multiple_local_tasks_resolve_to_stream"
        elif len(all_bindings_by_stream.get(stream_id, [])) > 1:
            action = "blocked"
            reason = "multiple_local_tasks_bound"
        elif len(heads) > 1:
            action = "blocked"
            reason = "concurrent_checkpoint_heads"
        elif binding is None:
            if stream_checkpoints:
                action = "blocked"
                reason = "unbound_local_task_matches_remote_stream"
            else:
                action = "save"
                reason = "new_local_task"
                read_scope = "full_history"
        elif latest is None:
            action = "blocked"
            reason = "bound_stream_missing_from_snapshot"
        else:
            last_checkpoint_id = binding["last_checkpoint_id"]
            known = by_id.get(last_checkpoint_id) if last_checkpoint_id else None
            if last_checkpoint_id and known is None:
                action = "blocked"
                reason = "binding_checkpoint_missing_from_snapshot"
            elif known and checkpoint_stream_id(known) != stream_id:
                action = "blocked"
                reason = "binding_checkpoint_stream_mismatch"
            else:
                known_title = (
                    effective_chat_title(checkpoints, known) if known else None
                )
                revision_changed = (
                    binding["source_revision"] != record["source_revision"]
                )
                title_changed = (
                    record.get("title") is not None
                    and record["title"] != known_title
                )
                local_changed = revision_changed or title_changed
                remote_changed = last_checkpoint_id != latest_id
                remote_title_changed = remote_title != known_title
                if remote_changed and revision_changed:
                    action = "blocked"
                    reason = "concurrent_local_remote_content_changes"
                elif remote_changed and title_changed and remote_title_changed:
                    action = "blocked"
                    reason = "concurrent_local_remote_title_changes"
                elif remote_changed:
                    action = "update"
                    reason = "remote_changes_available"
                    preserve_local_title = title_changed
                    follow_up_save_title = title_changed
                elif local_changed:
                    action = "save"
                    reason = "local_changes_available"
                    if revision_changed:
                        read_scope = (
                            "after_previous_head"
                            if binding["source_head_turn_id"]
                            else "full_review"
                        )
                else:
                    action = "unchanged"
                    reason = "already_synchronized"
        counts[action] += 1
        plan.append(
            {
                "stream_id": stream_id,
                "action": action,
                "reason": reason,
                "target_index": index,
                "read_scope": read_scope,
                "latest_checkpoint_id": latest_id,
                "chat_title": (
                    record.get("title")
                    if action == "save" or preserve_local_title
                    else remote_title
                ),
                "title_available": bool(
                    record.get("title")
                    if action == "save" or preserve_local_title
                    else remote_title
                ),
                "preserve_local_title": preserve_local_title,
                "follow_up_save_title": follow_up_save_title,
            }
        )

    hidden_streams = {
        binding["stream_id"]
        for key, binding in bindings.items()
        if key not in visible_keys
    }
    for stream_id in checkpoint_stream_ids(checkpoints):
        if stream_id == DEFAULT_STREAM_ID or stream_id in covered_streams:
            continue
        stream_checkpoints = [
            item
            for item in checkpoints
            if checkpoint_stream_id(item) == stream_id
        ]
        heads = checkpoint_heads(stream_checkpoints, stream_id)
        latest = heads[0] if len(heads) == 1 else None
        if len(heads) != 1:
            action = "blocked"
            reason = "concurrent_checkpoint_heads"
        elif len(all_bindings_by_stream.get(stream_id, [])) > 1:
            action = "blocked"
            reason = "multiple_local_tasks_bound"
        elif stream_id in hidden_streams:
            action = "unavailable"
            reason = "bound_task_not_in_desktop_listing"
        else:
            action = "create"
            reason = "remote_stream_missing_locally"
        counts[action] += 1
        chat_title = (
            effective_chat_title(checkpoints, latest) if latest else None
        )
        plan.append(
            {
                "stream_id": stream_id,
                "action": action,
                "reason": reason,
                "target_index": None,
                "read_scope": "none",
                "latest_checkpoint_id": (
                    latest["checkpoint_id"] if latest else None
                ),
                "chat_title": chat_title,
                "title_available": chat_title is not None,
                "preserve_local_title": False,
                "follow_up_save_title": False,
            }
        )

    project_head = stream_single_head(checkpoints, DEFAULT_STREAM_ID)
    return {
        "planned": True,
        "mode": "bidirectional",
        "project_id": entry["project_id"],
        "registry_path": str(registry_path),
        "discoverable_thread_count": len(records),
        "stream_count": len(plan),
        "counts": counts,
        "project_context_checkpoint_id": (
            project_head["checkpoint_id"] if project_head else None
        ),
        "streams": plan,
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


def restore_stream(
    checkpoints: list[dict[str, Any]],
    stream_id: str,
    current: dict[str, Any],
    checkpoint_id: str | None = None,
) -> dict[str, Any]:
    by_id = {item["checkpoint_id"]: item for item in checkpoints}
    stream_checkpoints = [
        item for item in checkpoints if checkpoint_stream_id(item) == stream_id
    ]
    if not stream_checkpoints:
        raise ContextSyncError(f"Checkpoint stream does not exist: {stream_id}")
    heads = checkpoint_heads(stream_checkpoints, stream_id)
    if checkpoint_id:
        latest = by_id.get(checkpoint_id)
        if latest is None:
            raise ContextSyncError(
                f"Checkpoint does not exist: {checkpoint_id}"
            )
        if checkpoint_stream_id(latest) != stream_id:
            raise ContextSyncError(
                f"Checkpoint does not belong to stream {stream_id}: {checkpoint_id}"
            )
    elif len(heads) > 1:
        identifiers = ", ".join(item["checkpoint_id"] for item in heads)
        raise ContextSyncError(
            "Concurrent checkpoint heads require separate review with "
            f"--checkpoint-id: {identifiers}"
        )
    else:
        latest = heads[0]
    history = checkpoint_history(checkpoints, latest)
    chat_title = effective_chat_title(checkpoints, latest)
    return {
        "stream_id": stream_id,
        "checkpoint_id": latest["checkpoint_id"],
        "snapshot_kind": checkpoint_snapshot_kind(latest),
        "created_at": latest["created_at"],
        "machine_id": latest["machine_id"],
        "parent_checkpoint_ids": latest["parent_checkpoint_ids"],
        "freshness": freshness(latest["repository"], current),
        "head_checkpoint_ids": [item["checkpoint_id"] for item in heads],
        "has_conflict": len(heads) > 1,
        "recorded_repository": latest["repository"],
        "current_repository": current,
        "context": latest["context"],
        "chat_title": chat_title,
        "title_available": chat_title is not None,
        "history_count": len(history),
        "history": [
            {
                "checkpoint_id": item["checkpoint_id"],
                "created_at": item["created_at"],
                "machine_id": item["machine_id"],
                "snapshot_kind": checkpoint_snapshot_kind(item),
                "repository": item["repository"],
                "context": item["context"],
            }
            for item in history
        ],
    }


def command_restore(args: argparse.Namespace) -> dict[str, Any]:
    _root, _config_path, _config, entry, current, directory = configured_context(args)
    checkpoints = load_checkpoints(directory, entry["project_id"])
    if not checkpoints:
        raise ContextSyncError("No checkpoints are available")
    checkpoint_id = getattr(args, "checkpoint_id", None)
    requested_stream = getattr(args, "stream_id", None)
    if checkpoint_id and requested_stream is None:
        by_id = {item["checkpoint_id"]: item for item in checkpoints}
        selected = by_id.get(checkpoint_id)
        if selected is None:
            raise ContextSyncError(f"Checkpoint does not exist: {checkpoint_id}")
        requested_stream = checkpoint_stream_id(selected)
    if getattr(args, "all_streams", False):
        results = [
            restore_stream(checkpoints, stream_id, current)
            for stream_id in checkpoint_stream_ids(checkpoints)
        ]
        return {
            "project_id": entry["project_id"],
            "all_streams": True,
            "stream_count": len(results),
            "streams": results,
            "current_repository": current,
        }
    stream_ids = checkpoint_stream_ids(checkpoints)
    if requested_stream is None:
        if len(stream_ids) != 1:
            raise ContextSyncError(
                "Multiple checkpoint streams are available; use --stream-id or --all-streams"
            )
        requested_stream = stream_ids[0]
    requested_stream = validate_stream_id(requested_stream)
    result = restore_stream(checkpoints, requested_stream, current, checkpoint_id)
    result["project_id"] = entry["project_id"]
    return result


def command_audit(args: argparse.Namespace) -> dict[str, Any]:
    _root, _config_path, _config, entry, current, directory = configured_context(args)
    validate_storage(entry, current.get("fingerprint"), directory)
    checkpoints = load_checkpoints(directory, entry["project_id"])
    return {
        "ok": True,
        "project_id": entry["project_id"],
        "checkpoint_count": len(checkpoints),
        "stream_count": len(checkpoint_stream_ids(checkpoints)),
        "scanned_at": utc_now(),
        "findings": [],
    }


def command_migrate(args: argparse.Namespace) -> dict[str, Any]:
    config_path = (
        resolved(args.config_path) if args.config_path else default_config_path()
    )
    config, changed = migrate_config(read_config_object(config_path))
    atomic_write_json(config_path, config)
    return {
        "migrated": True,
        "changed": changed,
        "version": CONFIG_VERSION,
        "config_path": str(config_path),
    }


def markdown_restore(result: dict[str, Any]) -> str:
    if result.get("all_streams"):
        lines = [
            "# Project handoff streams",
            "",
            f"- Streams: `{result['stream_count']}`",
        ]
        for stream in result["streams"]:
            title = stream.get("chat_title") or "title unavailable"
            lines.extend(
                [
                    "",
                    f"## `{stream['stream_id']}`",
                    "",
                    f"- Checkpoint: `{stream['checkpoint_id']}`",
                    f"- Chat title: {title}",
                    f"- Updates in restored history: `{stream['history_count']}`",
                    "",
                    stream["context"]["summary"],
                ]
            )
        return "\n".join(lines) + "\n"
    lines = [
        "# Project handoff",
        "",
        f"- Stream: `{result['stream_id']}`",
        f"- Checkpoint: `{result['checkpoint_id']}`",
        f"- Chat title: {result.get('chat_title') or 'title unavailable'}",
        f"- Snapshot kind: `{result['snapshot_kind']}`",
        f"- Updates in restored history: `{result['history_count']}`",
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
        ("rationale", "Rationale and considered options"),
        ("discussions", "Discussion outcomes"),
        ("decisions", "Decisions"),
        ("actions", "Actions"),
        ("verifications", "Verification"),
        ("blockers", "Blockers"),
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

    backend_plan = subparsers.add_parser(
        "backend-plan",
        help="Select a storage backend without changing configuration",
    )
    backend_plan.add_argument("--project-path", required=True)
    backend_plan.add_argument(
        "--requested-backend", choices=tuple(sorted(SUPPORTED_BACKENDS))
    )
    backend_plan.add_argument("--google-drive-connected", action="store_true")
    backend_plan.add_argument("--json", action="store_true")

    configure = subparsers.add_parser(
        "configure", help="Configure a local-folder or Google Drive mapping"
    )
    configure.add_argument("--project-path", required=True)
    configure.add_argument(
        "--backend",
        choices=("local-folder", "google-drive"),
        required=True,
    )
    configure.add_argument("--storage-root")
    configure.add_argument("--drive-project-folder-id")
    configure.add_argument("--drive-checkpoints-folder-id")
    configure.add_argument("--drive-marker-file-id")
    configure.add_argument("--marker-file")
    configure.add_argument("--mapping-plan")
    configure.add_argument("--readback-inventory")
    configure.add_argument("--project-id")
    configure.add_argument(
        "--mode", choices=("metadata-only", "paths"), default="metadata-only"
    )
    configure.add_argument(
        "--acknowledge-storage-policy", action="store_true"
    )
    configure.add_argument("--json", action="store_true")

    marker = subparsers.add_parser("prepare-drive-marker")
    marker.add_argument("--project-path", required=True)
    marker.add_argument("--output", required=True)
    marker.add_argument("--project-id")
    marker.add_argument("--mapping-plan")
    marker.add_argument("--acknowledge-storage-policy", action="store_true")
    marker.add_argument("--json", action="store_true")

    mapping_plan = subparsers.add_parser(
        "drive-mapping-plan",
        help="Plan reuse or creation from a complete Drive metadata inventory",
    )
    mapping_plan.add_argument("--project-path", required=True)
    mapping_plan.add_argument("--inventory", required=True)
    mapping_plan.add_argument("--output", required=True)
    mapping_plan.add_argument("--json", action="store_true")

    transport = subparsers.add_parser("transport")
    transport.add_argument("--project-path", required=True)
    transport.add_argument("--json", action="store_true")

    hydrate = subparsers.add_parser("hydrate-drive")
    hydrate.add_argument("--project-path", required=True)
    hydrate.add_argument("--marker-file", required=True)
    hydrate.add_argument("--checkpoint-file", action="append", default=[])
    hydrate.add_argument("--output-root", required=True)
    hydrate.add_argument("--json", action="store_true")

    status = subparsers.add_parser("status")
    status.add_argument("--project-path", required=True)
    status.add_argument("--snapshot-root")
    status.add_argument("--stream-id")
    status.add_argument("--json", action="store_true")

    audit = subparsers.add_parser("audit")
    audit.add_argument("--project-path", required=True)
    audit.add_argument("--snapshot-root")
    audit.add_argument("--json", action="store_true")

    restore = subparsers.add_parser("restore")
    restore.add_argument("--project-path", required=True)
    restore.add_argument("--snapshot-root")
    restore_selection = restore.add_mutually_exclusive_group()
    restore_selection.add_argument("--checkpoint-id")
    restore_selection.add_argument("--stream-id")
    restore_selection.add_argument("--all-streams", action="store_true")
    restore.add_argument("--json", action="store_true")

    capture = subparsers.add_parser("capture")
    capture.add_argument("--project-path", required=True)
    capture.add_argument("--snapshot-root")
    source = capture.add_mutually_exclusive_group(required=True)
    source.add_argument("--input")
    source.add_argument("--stdin", action="store_true")
    capture.add_argument("--merge-heads", action="store_true")
    capture.add_argument("--stream-id", default=DEFAULT_STREAM_ID)
    capture.add_argument(
        "--snapshot-kind",
        choices=("auto", "baseline", "delta"),
        default="auto",
    )
    capture.add_argument("--json", action="store_true")

    batch_plan = subparsers.add_parser(
        "batch-plan", help="Plan baseline and delta work for discovered project chats"
    )
    batch_plan.add_argument("--project-path", required=True)
    batch_plan.add_argument("--snapshot-root")
    batch_plan_source = batch_plan.add_mutually_exclusive_group(required=True)
    batch_plan_source.add_argument("--input")
    batch_plan_source.add_argument("--stdin", action="store_true")
    batch_plan.add_argument("--json", action="store_true")

    batch_capture = subparsers.add_parser(
        "batch-capture", help="Capture sanitized project chat summaries in one batch"
    )
    batch_capture.add_argument("--project-path", required=True)
    batch_capture.add_argument("--snapshot-root")
    batch_capture_source = batch_capture.add_mutually_exclusive_group(required=True)
    batch_capture_source.add_argument("--input")
    batch_capture_source.add_argument("--stdin", action="store_true")
    batch_capture.add_argument("--json", action="store_true")

    bind_thread = subparsers.add_parser(
        "bind-thread", help="Bind a local Codex chat to a restored stream"
    )
    bind_thread.add_argument("--project-path", required=True)
    bind_thread.add_argument("--snapshot-root")
    bind_thread.add_argument("--thread-id", required=True)
    bind_thread.add_argument("--stream-id", required=True)
    bind_thread.add_argument("--checkpoint-id")
    bind_thread.add_argument("--source-revision")
    bind_thread.add_argument("--source-head-turn-id")
    bind_thread.add_argument("--json", action="store_true")

    materialize_plan = subparsers.add_parser(
        "materialize-plan",
        help="Plan creation or update of restored streams as desktop tasks",
    )
    materialize_plan.add_argument("--project-path", required=True)
    materialize_plan.add_argument("--snapshot-root")
    materialize_source = materialize_plan.add_mutually_exclusive_group(
        required=True
    )
    materialize_source.add_argument("--input")
    materialize_source.add_argument("--stdin", action="store_true")
    materialize_plan.add_argument("--json", action="store_true")

    sync_plan = subparsers.add_parser(
        "sync-plan",
        help="Plan bidirectional save and restore work for project chats",
    )
    sync_plan.add_argument("--project-path", required=True)
    sync_plan.add_argument("--snapshot-root")
    sync_plan_source = sync_plan.add_mutually_exclusive_group(required=True)
    sync_plan_source.add_argument("--input")
    sync_plan_source.add_argument("--stdin", action="store_true")
    sync_plan.add_argument("--json", action="store_true")

    migrate = subparsers.add_parser("migrate")
    migrate.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        handler = {
            "backend-plan": command_backend_plan,
            "drive-mapping-plan": command_drive_mapping_plan,
            "configure": command_configure,
            "prepare-drive-marker": command_prepare_drive_marker,
            "transport": command_transport,
            "hydrate-drive": command_hydrate_drive,
            "status": command_status,
            "capture": command_capture,
            "batch-plan": command_batch_plan,
            "batch-capture": command_batch_capture,
            "bind-thread": command_bind_thread,
            "materialize-plan": command_materialize_plan,
            "sync-plan": command_sync_plan,
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
