from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from pathlib import Path, PurePosixPath
from typing import Any

import context_sync


ENVIRONMENT_MANIFEST_VERSION = 1
MAX_RULE_BYTES = 32 * 1024
MAX_REQUIREMENTS = 100
MAX_PREFERENCES_BYTES = 16 * 1024
SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+-]{0,255}$")
SENSITIVE_KEY = re.compile(
    r"(?:password|passwd|secret|token|credential|cookie|session|private[_-]?key|connection[_-]?string)",
    re.I,
)
NOTIFY_SETTING_ID = "notify-via-telegram"
NOTIFY_DELIVERY_MODES = {"global-and-project", "project-only"}
RULE_FILENAMES = {"AGENTS.md", "CLAUDE.md"}


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def require_exact_fields(
    value: object,
    *,
    required: set[str],
    optional: set[str] | None = None,
    label: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise context_sync.ContextSyncError(f"{label} must be an object")
    optional = optional or set()
    if not required.issubset(value) or set(value) - required - optional:
        raise context_sync.ContextSyncError(
            f"{label} has missing or unexpected fields"
        )
    return value


def safe_string(value: object, label: str, *, maximum: int = 256) -> str:
    if not isinstance(value, str):
        raise context_sync.ContextSyncError(f"{label} must be a string")
    result = value.strip()
    if not result or len(result) > maximum or re.search(r"[\x00-\x1f\x7f]", result):
        raise context_sync.ContextSyncError(
            f"{label} must contain 1-{maximum} printable characters"
        )
    if context_sync.scan_secrets(result, label):
        raise context_sync.ContextSyncError(f"{label} contains a possible secret")
    return result


def safe_identifier(value: object, label: str) -> str:
    result = safe_string(value, label)
    if not SAFE_IDENTIFIER.fullmatch(result):
        raise context_sync.ContextSyncError(f"{label} is not a portable identifier")
    return result


def safe_source_identifier(value: object, label: str) -> str:
    result = safe_identifier(value, label)
    if "://" in result or "/" in result:
        raise context_sync.ContextSyncError(
            f"{label} must be a package or collection identifier, not a URL"
        )
    return result


def normalize_rule_path(value: object, project_root: Path) -> tuple[str, Path]:
    path = safe_string(value, "rule.path", maximum=512).replace("\\", "/")
    pure = PurePosixPath(path)
    if pure.is_absolute() or ".." in pure.parts or pure.name not in RULE_FILENAMES:
        raise context_sync.ContextSyncError(
            "rule.path must be a project-relative AGENTS.md or CLAUDE.md path"
        )
    normalized = pure.as_posix()
    target = (project_root / Path(*pure.parts)).resolve()
    if not context_sync.is_within(target, project_root):
        raise context_sync.ContextSyncError("rule.path resolves outside the project")
    return normalized, target


def normalize_declaration_path(value: object, project_root: Path) -> tuple[str, Path]:
    path = safe_string(value, "declaration_path", maximum=512).replace("\\", "/")
    pure = PurePosixPath(path)
    if pure.is_absolute() or ".." in pure.parts or pure.name in {"", "."}:
        raise context_sync.ContextSyncError(
            "declaration_path must be a project-relative file path"
        )
    normalized = pure.as_posix()
    target = (project_root / Path(*pure.parts)).resolve()
    if not context_sync.is_within(target, project_root):
        raise context_sync.ContextSyncError(
            "declaration_path resolves outside the project"
        )
    return normalized, target


def git_path_state(project_root: Path, relative_path: str) -> dict[str, Any]:
    git_root_value = context_sync.run_git(
        project_root, ["rev-parse", "--show-toplevel"], check=False
    )
    if not git_root_value:
        return {"available": False, "tracked": False, "ignored": False}
    git_root = Path(git_root_value).resolve()
    target = (project_root / Path(*PurePosixPath(relative_path).parts)).resolve()
    try:
        git_relative = target.relative_to(git_root).as_posix()
    except ValueError as error:
        raise context_sync.ContextSyncError(
            "rule.path is outside the active Git repository"
        ) from error
    tracked = context_sync.run_git(
        git_root, ["ls-files", "--error-unmatch", "--", git_relative], check=False
    ) is not None
    ignored = context_sync.run_git(
        git_root, ["check-ignore", "-q", "--", git_relative], check=False
    ) is not None
    state: dict[str, Any] = {
        "available": True,
        "tracked": tracked,
        "ignored": ignored,
    }
    if tracked:
        status = context_sync.run_git(
            git_root, ["status", "--porcelain=v1", "--", git_relative], check=False
        )
        state["modified"] = bool(status)
        state["blob_oid"] = context_sync.run_git(
            git_root, ["rev-parse", f"HEAD:{git_relative}"], check=False
        )
        state["head"] = context_sync.run_git(
            git_root, ["rev-parse", "HEAD"], check=False
        )
    return state


def read_rule(target: Path, label: str) -> str:
    if not target.is_file() or target.is_symlink():
        raise context_sync.ContextSyncError(
            f"{label} must identify an existing regular file, not a symlink"
        )
    if target.stat().st_size > MAX_RULE_BYTES:
        raise context_sync.ContextSyncError(
            f"{label} exceeds the {MAX_RULE_BYTES}-byte rule limit"
        )
    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise context_sync.ContextSyncError(f"{label} must be UTF-8 text") from error
    if not content.strip() or "\0" in content:
        raise context_sync.ContextSyncError(f"{label} is empty or invalid text")
    if context_sync.scan_secrets(content, label):
        raise context_sync.ContextSyncError(f"{label} contains a possible secret")
    return content


def validate_preferences(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise context_sync.ContextSyncError(f"{label} must be an object")
    for key, item in value.items():
        if not isinstance(key, str) or not key or SENSITIVE_KEY.search(key):
            raise context_sync.ContextSyncError(
                f"{label} contains a forbidden or invalid key"
            )
        if not isinstance(item, (str, int, float, bool)) and item is not None:
            raise context_sync.ContextSyncError(
                f"{label}.{key} must be a JSON scalar"
            )
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    if len(encoded) > MAX_PREFERENCES_BYTES:
        raise context_sync.ContextSyncError(f"{label} is too large")
    if context_sync.scan_secrets(value, label):
        raise context_sync.ContextSyncError(f"{label} contains a possible secret")
    return dict(sorted(value.items()))


def validate_known_setting(
    identifier: str, scope: str, schema_version: str, preferences: dict[str, Any]
) -> None:
    if identifier != NOTIFY_SETTING_ID:
        return
    if schema_version != "1":
        raise context_sync.ContextSyncError(
            "notify-via-telegram project settings require schema version 1"
        )
    if scope != "project":
        raise context_sync.ContextSyncError(
            "notify-via-telegram synchronized settings require project scope"
        )
    required = {"delivery_mode", "chat_id"}
    optional = {"message_thread_id"}
    if not required.issubset(preferences) or set(preferences) - required - optional:
        raise context_sync.ContextSyncError(
            "notify-via-telegram project settings have missing or unexpected fields"
        )
    if preferences["delivery_mode"] not in NOTIFY_DELIVERY_MODES:
        raise context_sync.ContextSyncError(
            "notify-via-telegram delivery_mode is invalid"
        )
    if not isinstance(preferences["chat_id"], str) or not re.fullmatch(
        r"-?[0-9]+", preferences["chat_id"]
    ):
        raise context_sync.ContextSyncError(
            "notify-via-telegram chat_id must be numeric"
        )
    thread_id = preferences.get("message_thread_id")
    if thread_id is not None and (
        not isinstance(thread_id, str) or not re.fullmatch(r"[0-9]+", thread_id)
    ):
        raise context_sync.ContextSyncError(
            "notify-via-telegram message_thread_id must be numeric"
        )


def normalize_environment_input(value: object, project_root: Path) -> dict[str, Any]:
    root = require_exact_fields(
        value,
        required=set(),
        optional={"rules", "skills", "plugins", "settings"},
        label="Environment input",
    )
    result: dict[str, list[dict[str, Any]]] = {
        "rules": [],
        "skills": [],
        "plugins": [],
        "settings": [],
        "git_coverage": [],
    }
    for category in ("rules", "skills", "plugins", "settings"):
        items = root.get(category, [])
        if not isinstance(items, list) or len(items) > MAX_REQUIREMENTS:
            raise context_sync.ContextSyncError(
                f"{category} must be an array with at most {MAX_REQUIREMENTS} items"
            )

    seen: set[tuple[str, str]] = set()
    for index, raw in enumerate(root.get("rules", [])):
        item = require_exact_fields(
            raw,
            required={"id", "path", "scope"},
            label=f"rules[{index}]",
        )
        identifier = safe_identifier(item["id"], f"rules[{index}].id")
        scope = safe_identifier(item["scope"], f"rules[{index}].scope")
        if scope not in {"project", "subtree"}:
            raise context_sync.ContextSyncError("rule.scope must be project or subtree")
        relative, target = normalize_rule_path(item["path"], project_root)
        key = ("rules", identifier)
        if key in seen:
            raise context_sync.ContextSyncError(f"Duplicate environment id: {identifier}")
        seen.add(key)
        git = git_path_state(project_root, relative)
        if git.get("tracked"):
            if git.get("modified"):
                raise context_sync.ContextSyncError(
                    f"Tracked rule has unpublished changes and cannot be captured: {relative}"
                )
            result["rules"].append(
                {
                    "id": identifier,
                    "path": relative,
                    "scope": scope,
                    "classification": "satisfied_by_git",
                    "git": {"blob_oid": git.get("blob_oid"), "head": git.get("head")},
                }
            )
        else:
            content = read_rule(target, f"rules[{index}].path")
            result["rules"].append(
                {
                    "id": identifier,
                    "path": relative,
                    "scope": scope,
                    "classification": "local_portable",
                    "ignored": bool(git.get("ignored")),
                    "content": content,
                    "content_sha256": sha256_text(content),
                }
            )

    for category in ("skills", "plugins"):
        for index, raw in enumerate(root.get(category, [])):
            required = {"id", "version", "required"}
            optional = {"declaration_path"}
            if category == "skills":
                optional.update({"source", "digest"})
            item = require_exact_fields(
                raw,
                required=required,
                optional=optional,
                label=f"{category}[{index}]",
            )
            identifier = safe_identifier(item["id"], f"{category}[{index}].id")
            if not isinstance(item["required"], bool):
                raise context_sync.ContextSyncError(
                    f"{category}[{index}].required must be boolean"
                )
            normalized: dict[str, Any] = {
                "id": identifier,
                "version": safe_string(item["version"], f"{category}[{index}].version"),
                "required": item["required"],
            }
            if category == "skills":
                if "source" in item:
                    normalized["source"] = safe_source_identifier(
                        item["source"], f"{category}[{index}].source"
                    )
                if "digest" in item:
                    digest = safe_string(item["digest"], f"{category}[{index}].digest")
                    if not re.fullmatch(r"[0-9a-f]{64}", digest):
                        raise context_sync.ContextSyncError("skill.digest must be SHA-256")
                    normalized["digest"] = digest
            key = (category, identifier)
            if key in seen:
                raise context_sync.ContextSyncError(f"Duplicate environment id: {identifier}")
            seen.add(key)
            if "declaration_path" in item:
                relative, _target = normalize_declaration_path(
                    item["declaration_path"], project_root
                )
                git = git_path_state(project_root, relative)
                if git.get("tracked") and git.get("modified"):
                    raise context_sync.ContextSyncError(
                        f"Tracked {category} declaration has unpublished changes: {relative}"
                    )
                if git.get("tracked"):
                    result["git_coverage"].append(
                        {
                            "category": category,
                            "id": identifier,
                            "path": relative,
                            "blob_oid": git.get("blob_oid"),
                            "head": git.get("head"),
                        }
                    )
                    continue
            result[category].append(normalized)

    for index, raw in enumerate(root.get("settings", [])):
        item = require_exact_fields(
            raw,
            required={"id", "scope", "schema_version", "preferences", "required"},
            optional={"declaration_path"},
            label=f"settings[{index}]",
        )
        identifier = safe_identifier(item["id"], f"settings[{index}].id")
        scope = safe_identifier(item["scope"], f"settings[{index}].scope")
        if scope not in {"project", "user"}:
            raise context_sync.ContextSyncError("setting.scope must be project or user")
        if not isinstance(item["required"], bool):
            raise context_sync.ContextSyncError("setting.required must be boolean")
        preferences = validate_preferences(
            item["preferences"], f"settings[{index}].preferences"
        )
        schema_version = safe_string(
            item["schema_version"], f"settings[{index}].schema_version"
        )
        validate_known_setting(identifier, scope, schema_version, preferences)
        key = ("settings", identifier)
        if key in seen:
            raise context_sync.ContextSyncError(f"Duplicate environment id: {identifier}")
        seen.add(key)
        if "declaration_path" in item:
            relative, _target = normalize_declaration_path(
                item["declaration_path"], project_root
            )
            git = git_path_state(project_root, relative)
            if git.get("tracked") and git.get("modified"):
                raise context_sync.ContextSyncError(
                    f"Tracked settings declaration has unpublished changes: {relative}"
                )
            if git.get("tracked"):
                result["git_coverage"].append(
                    {
                        "category": "settings",
                        "id": identifier,
                        "path": relative,
                        "blob_oid": git.get("blob_oid"),
                        "head": git.get("head"),
                    }
                )
                continue
        result["settings"].append(
            {
                "id": identifier,
                "scope": scope,
                "schema_version": schema_version,
                "preferences": preferences,
                "preferences_sha256": context_sync.canonical_digest(preferences),
                "required": item["required"],
                "materialization": "manual",
            }
        )
    for items in result.values():
        items.sort(key=lambda item: (item.get("category", ""), item["id"]))
    return result


def manifest_digest(manifest: dict[str, Any]) -> str:
    unsigned = dict(manifest)
    unsigned.pop("content_sha256", None)
    return context_sync.canonical_digest(unsigned)


def load_manifest_file(
    path: Path, project_id: str, *, require_filename: bool = True
) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise context_sync.ContextSyncError(
            f"Environment manifest is invalid: {path}: {error}"
        ) from error
    required = {
        "schema_version", "manifest_id", "project_id", "machine_id", "created_at",
        "parent_manifest_ids", "repository", "rules", "skills", "plugins", "settings",
        "git_coverage",
        "content_sha256",
    }
    manifest = require_exact_fields(value, required=required, label="Environment manifest")
    if manifest["schema_version"] != ENVIRONMENT_MANIFEST_VERSION:
        raise context_sync.ContextSyncError("Environment manifest version is unsupported")
    manifest_id = manifest["manifest_id"]
    if not isinstance(manifest_id, str) or not re.fullmatch(r"environment-[0-9a-f]{32}", manifest_id):
        raise context_sync.ContextSyncError("Environment manifest id is invalid")
    if require_filename and path.stem != manifest_id:
        raise context_sync.ContextSyncError("Environment manifest filename does not match its id")
    if manifest["project_id"] != project_id:
        raise context_sync.ContextSyncError("Environment manifest project_id mismatch")
    if not isinstance(manifest["project_id"], str) or not context_sync.PROJECT_ID_PATTERN.fullmatch(
        manifest["project_id"]
    ):
        raise context_sync.ContextSyncError("Environment manifest project_id is invalid")
    if not isinstance(manifest["parent_manifest_ids"], list) or not all(
        isinstance(item, str) and re.fullmatch(r"environment-[0-9a-f]{32}", item)
        for item in manifest["parent_manifest_ids"]
    ):
        raise context_sync.ContextSyncError("Environment manifest parents are invalid")
    if len(manifest["parent_manifest_ids"]) != len(set(manifest["parent_manifest_ids"])):
        raise context_sync.ContextSyncError("Environment manifest parents are duplicated")
    if not isinstance(manifest["machine_id"], str) or not re.fullmatch(
        r"machine-[0-9a-f]{12}", manifest["machine_id"]
    ):
        raise context_sync.ContextSyncError("Environment manifest machine_id is invalid")
    repository = require_exact_fields(
        manifest["repository"],
        required={"fingerprint", "head"},
        label="Environment manifest repository",
    )
    for field, pattern in (
        ("fingerprint", r"[0-9a-f]{64}"),
        ("head", r"[0-9a-f]{40,64}"),
    ):
        item = repository[field]
        if item is not None and (not isinstance(item, str) or not re.fullmatch(pattern, item)):
            raise context_sync.ContextSyncError(
                f"Environment manifest repository.{field} is invalid"
            )
    for field in ("rules", "skills", "plugins", "settings", "git_coverage"):
        if not isinstance(manifest[field], list) or len(manifest[field]) > MAX_REQUIREMENTS:
            raise context_sync.ContextSyncError(f"Environment manifest {field} is invalid")
    seen: set[tuple[str, str]] = set()
    for index, raw_coverage in enumerate(manifest["git_coverage"]):
        coverage = require_exact_fields(
            raw_coverage,
            required={"category", "id", "path", "blob_oid", "head"},
            label=f"Environment manifest git_coverage[{index}]",
        )
        category = coverage["category"]
        if category not in {"skills", "plugins", "settings"}:
            raise context_sync.ContextSyncError("Environment Git coverage category is invalid")
        identifier = safe_identifier(
            coverage["id"], f"Environment manifest git_coverage[{index}].id"
        )
        if (category, identifier) in seen:
            raise context_sync.ContextSyncError("Environment Git coverage ids are duplicated")
        seen.add((category, identifier))
        path = safe_string(
            coverage["path"],
            f"Environment manifest git_coverage[{index}].path",
            maximum=512,
        ).replace("\\", "/")
        pure = PurePosixPath(path)
        if pure.is_absolute() or ".." in pure.parts or pure.as_posix() != path:
            raise context_sync.ContextSyncError("Environment Git coverage path is invalid")
        for field in ("blob_oid", "head"):
            item = coverage[field]
            if item is not None and (
                not isinstance(item, str) or not re.fullmatch(r"[0-9a-f]{40,64}", item)
            ):
                raise context_sync.ContextSyncError("Environment Git coverage digest is invalid")
    for index, raw_rule in enumerate(manifest["rules"]):
        if not isinstance(raw_rule, dict):
            raise context_sync.ContextSyncError("Environment manifest rule is invalid")
        classification = raw_rule.get("classification")
        common = {"id", "path", "scope", "classification"}
        extra = {"git"} if classification == "satisfied_by_git" else {
            "ignored", "content", "content_sha256"
        }
        rule = require_exact_fields(
            raw_rule,
            required=common | extra,
            label=f"Environment manifest rules[{index}]",
        )
        identifier = safe_identifier(rule["id"], f"Environment manifest rules[{index}].id")
        if ("rules", identifier) in seen:
            raise context_sync.ContextSyncError("Environment manifest rule ids are duplicated")
        seen.add(("rules", identifier))
        path = safe_string(rule["path"], f"Environment manifest rules[{index}].path", maximum=512).replace("\\", "/")
        pure = PurePosixPath(path)
        if pure.is_absolute() or ".." in pure.parts or pure.name not in RULE_FILENAMES or pure.as_posix() != path:
            raise context_sync.ContextSyncError("Environment manifest rule path is invalid")
        if rule["scope"] not in {"project", "subtree"}:
            raise context_sync.ContextSyncError("Environment manifest rule scope is invalid")
        if classification == "satisfied_by_git":
            git = require_exact_fields(
                rule["git"],
                required={"blob_oid", "head"},
                label=f"Environment manifest rules[{index}].git",
            )
            for field in ("blob_oid", "head"):
                item = git[field]
                if item is not None and (
                    not isinstance(item, str) or not re.fullmatch(r"[0-9a-f]{40,64}", item)
                ):
                    raise context_sync.ContextSyncError("Environment manifest Git coverage is invalid")
        elif classification == "local_portable":
            if not isinstance(rule["ignored"], bool):
                raise context_sync.ContextSyncError("Environment manifest ignored flag is invalid")
            content = rule.get("content")
            if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_RULE_BYTES:
                raise context_sync.ContextSyncError("Environment rule content is invalid")
            if rule.get("content_sha256") != sha256_text(content):
                raise context_sync.ContextSyncError("Environment rule digest does not match")
        else:
            raise context_sync.ContextSyncError("Environment manifest rule classification is invalid")
    for category in ("skills", "plugins"):
        for index, raw_item in enumerate(manifest[category]):
            optional = {"source", "digest"} if category == "skills" else set()
            item = require_exact_fields(
                raw_item,
                required={"id", "version", "required"},
                optional=optional,
                label=f"Environment manifest {category}[{index}]",
            )
            identifier = safe_identifier(item["id"], f"Environment manifest {category}[{index}].id")
            if (category, identifier) in seen:
                raise context_sync.ContextSyncError(f"Environment manifest {category} ids are duplicated")
            seen.add((category, identifier))
            safe_string(item["version"], f"Environment manifest {category}[{index}].version")
            if not isinstance(item["required"], bool):
                raise context_sync.ContextSyncError(f"Environment manifest {category} required flag is invalid")
            if "source" in item:
                safe_source_identifier(item["source"], f"Environment manifest {category}[{index}].source")
            if "digest" in item and (
                not isinstance(item["digest"], str) or not re.fullmatch(r"[0-9a-f]{64}", item["digest"])
            ):
                raise context_sync.ContextSyncError("Environment manifest skill digest is invalid")
    for index, raw_setting in enumerate(manifest["settings"]):
        setting = require_exact_fields(
            raw_setting,
            required={"id", "scope", "schema_version", "preferences", "preferences_sha256", "required", "materialization"},
            label=f"Environment manifest settings[{index}]",
        )
        identifier = safe_identifier(setting["id"], f"Environment manifest settings[{index}].id")
        if ("settings", identifier) in seen:
            raise context_sync.ContextSyncError("Environment manifest setting ids are duplicated")
        seen.add(("settings", identifier))
        if setting["scope"] not in {"project", "user"} or setting["materialization"] != "manual":
            raise context_sync.ContextSyncError("Environment manifest setting policy is invalid")
        schema_version = safe_string(
            setting["schema_version"],
            f"Environment manifest settings[{index}].schema_version",
        )
        if not isinstance(setting["required"], bool):
            raise context_sync.ContextSyncError("Environment manifest setting required flag is invalid")
        preferences = validate_preferences(
            setting["preferences"], f"Environment manifest settings[{index}].preferences"
        )
        validate_known_setting(identifier, setting["scope"], schema_version, preferences)
        if setting["preferences_sha256"] != context_sync.canonical_digest(preferences):
            raise context_sync.ContextSyncError("Environment setting digest does not match")
    if manifest.get("content_sha256") != manifest_digest(manifest):
        raise context_sync.ContextSyncError("Environment manifest digest does not match")
    if context_sync.scan_secrets(manifest):
        raise context_sync.ContextSyncError("Environment manifest contains a possible secret")
    return manifest


def load_manifests(directory: Path, project_id: str) -> list[dict[str, Any]]:
    result = [
        load_manifest_file(path, project_id)
        for path in sorted((directory / "environment-manifests").glob("*.json"))
    ]
    validate_manifest_graph(result)
    result.sort(key=lambda item: (item["created_at"], item["manifest_id"]))
    return result


def validate_manifest_graph(result: list[dict[str, Any]]) -> None:
    by_id = {item["manifest_id"]: item for item in result}
    if len(by_id) != len(result):
        raise context_sync.ContextSyncError("Environment manifest IDs are duplicated")
    for item in result:
        for parent in item["parent_manifest_ids"]:
            if parent not in by_id:
                raise context_sync.ContextSyncError(
                    f"Environment history is incomplete; missing parent: {parent}"
                )
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(identifier: str) -> None:
        if identifier in visiting:
            raise context_sync.ContextSyncError("Environment history contains a cycle")
        if identifier in visited:
            return
        visiting.add(identifier)
        for parent in by_id[identifier]["parent_manifest_ids"]:
            visit(parent)
        visiting.remove(identifier)
        visited.add(identifier)

    for identifier in by_id:
        visit(identifier)


def manifest_heads(manifests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    parents = {parent for item in manifests for parent in item["parent_manifest_ids"]}
    return [item for item in manifests if item["manifest_id"] not in parents]


def load_optional_state(args: argparse.Namespace, project_root: Path) -> dict[str, Any]:
    path_value = getattr(args, "local_state", None)
    if not path_value:
        return {"skills": [], "plugins": [], "settings": []}
    path = context_sync.resolved(path_value)
    context_sync.validate_external_path(path, project_root, "Local state input", reject_git=False)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise context_sync.ContextSyncError(f"Local state is invalid JSON: {error}") from error
    state = require_exact_fields(
        value,
        required=set(),
        optional={"skills", "plugins", "settings"},
        label="Local state",
    )
    normalized: dict[str, list[dict[str, Any]]] = {"skills": [], "plugins": [], "settings": []}
    allowed = {
        "skills": {"id", "version", "digest"},
        "plugins": {"id", "version", "connected"},
        "settings": {"id", "schema_version", "preferences_sha256"},
    }
    for category in normalized:
        items = state.get(category, [])
        if not isinstance(items, list) or len(items) > MAX_REQUIREMENTS:
            raise context_sync.ContextSyncError(f"Local state {category} is invalid")
        seen: set[str] = set()
        for index, raw in enumerate(items):
            if not isinstance(raw, dict) or "id" not in raw or set(raw) - allowed[category]:
                raise context_sync.ContextSyncError(f"Local state {category}[{index}] is invalid")
            item = dict(raw)
            item["id"] = safe_identifier(item["id"], f"Local state {category}[{index}].id")
            if item["id"] in seen:
                raise context_sync.ContextSyncError(f"Local state {category} ids are duplicated")
            seen.add(item["id"])
            if category == "skills":
                if "version" in item:
                    item["version"] = safe_string(item["version"], f"Local state {category}[{index}].version")
                if "digest" in item and (
                    not isinstance(item["digest"], str) or not re.fullmatch(r"[0-9a-f]{64}", item["digest"])
                ):
                    raise context_sync.ContextSyncError("Local skill digest is invalid")
            elif category == "plugins":
                if "version" in item:
                    item["version"] = safe_string(item["version"], f"Local state {category}[{index}].version")
                if "connected" in item and not isinstance(item["connected"], bool):
                    raise context_sync.ContextSyncError("Local plugin connected flag is invalid")
            else:
                if "schema_version" in item:
                    item["schema_version"] = safe_string(item["schema_version"], f"Local state {category}[{index}].schema_version")
                if "preferences_sha256" in item and (
                    not isinstance(item["preferences_sha256"], str)
                    or not re.fullmatch(r"[0-9a-f]{64}", item["preferences_sha256"])
                ):
                    raise context_sync.ContextSyncError("Local settings digest is invalid")
            normalized[category].append(item)
    if context_sync.scan_secrets(normalized):
        raise context_sync.ContextSyncError("Local state contains a possible secret")
    return normalized


def selected_manifest(args: argparse.Namespace, directory: Path, project_id: str) -> dict[str, Any]:
    manifests = load_manifests(directory, project_id)
    if not manifests:
        raise context_sync.ContextSyncError("No environment manifests are available")
    requested = getattr(args, "manifest_id", None)
    if requested:
        for item in manifests:
            if item["manifest_id"] == requested:
                return item
        raise context_sync.ContextSyncError(f"Environment manifest does not exist: {requested}")
    heads = manifest_heads(manifests)
    if len(heads) != 1:
        raise context_sync.ContextSyncError(
            "Multiple environment manifest heads require explicit review and --manifest-id"
        )
    return heads[0]


def build_plan(project_root: Path, manifest: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    for coverage in manifest["git_coverage"]:
        git = git_path_state(project_root, coverage["path"])
        matches = git.get("tracked") and git.get("blob_oid") == coverage["blob_oid"]
        actions.append(
            {
                "category": coverage["category"],
                "id": coverage["id"],
                "path": coverage["path"],
                "status": "satisfied_by_git" if matches else "approval_required",
                "reason": (
                    "Git declaration matches the captured source"
                    if matches
                    else "Git declaration differs or is missing; inspect the repository before adding a local requirement"
                ),
            }
        )
    for rule in manifest["rules"]:
        relative, target = normalize_rule_path(rule["path"], project_root)
        git = git_path_state(project_root, relative)
        if rule["classification"] == "satisfied_by_git":
            same_blob = git.get("tracked") and git.get("blob_oid") == rule.get("git", {}).get("blob_oid")
            actions.append(
                {
                    "category": "rules", "id": rule["id"], "path": relative,
                    "status": "satisfied_by_git" if same_blob else "approval_required",
                    "reason": "Git blob matches the captured source" if same_blob else "Git is authoritative but its rule differs or is missing",
                }
            )
            continue
        expected = rule["content_sha256"]
        if git.get("tracked"):
            actual = sha256_text(read_rule(target, f"rule {relative}")) if target.is_file() else None
            status = "satisfied_by_git" if actual == expected else "approval_required"
            reason = "Git now provides the same rule" if actual == expected else "Git now owns a different rule; do not overwrite it"
        elif target.exists():
            actual = sha256_text(read_rule(target, f"rule {relative}"))
            status = "satisfied_locally" if actual == expected else "approval_required"
            reason = "Existing local rule matches" if actual == expected else "Existing local rule differs; merge manually"
        else:
            status = "apply_local_rule"
            reason = "Rule is absent from Git and the destination"
        actions.append({"category": "rules", "id": rule["id"], "path": relative, "status": status, "reason": reason})

    state_by_category = {
        category: {item["id"]: item for item in state[category]}
        for category in ("skills", "plugins", "settings")
    }
    for skill in manifest["skills"]:
        local = state_by_category["skills"].get(skill["id"])
        matches = bool(local) and local.get("version") == skill["version"] and (
            not skill.get("digest") or local.get("digest") == skill.get("digest")
        )
        actions.append({
            "category": "skills", "id": skill["id"],
            "status": "satisfied_locally" if matches else "install_required",
            "reason": "Verified installed requirement" if matches else "Install from the declared canonical source and verify provenance",
        })
    for plugin in manifest["plugins"]:
        local = state_by_category["plugins"].get(plugin["id"])
        if not local or local.get("version") != plugin["version"]:
            status, reason = "install_required", "Install the declared plugin version"
        elif plugin["required"] and not local.get("connected", False):
            status, reason = "approval_required", "Reconnect interactively; credentials are never synchronized"
        else:
            status, reason = "satisfied_locally", "Plugin requirement is present"
        actions.append({"category": "plugins", "id": plugin["id"], "status": status, "reason": reason})
    for setting in manifest["settings"]:
        local = state_by_category["settings"].get(setting["id"])
        matches = bool(local) and local.get("schema_version") == setting["schema_version"] and local.get("preferences_sha256") == setting["preferences_sha256"]
        actions.append({
            "category": "settings", "id": setting["id"],
            "status": "satisfied_locally" if matches else "manual_apply_required",
            "reason": "Safe preferences match" if matches else "Apply through the owning component's schema-aware interface",
            **({"preferences": setting["preferences"]} if not matches else {}),
        })
    counts: dict[str, int] = {}
    for action in actions:
        counts[action["status"]] = counts.get(action["status"], 0) + 1
    return {"actions": actions, "counts": dict(sorted(counts.items()))}


def command_inspect(args: argparse.Namespace) -> dict[str, Any]:
    project_root = context_sync.resolved(args.project_path)
    if not project_root.is_dir():
        raise context_sync.ContextSyncError(f"Project directory does not exist: {project_root}")
    value = context_sync.load_capture_input(args, project_root)
    environment = normalize_environment_input(value, project_root)
    counts = {key: len(items) for key, items in environment.items()}
    return {"ok": True, "read_only": True, "counts": counts, "environment": environment}


def command_capture(args: argparse.Namespace) -> dict[str, Any]:
    if not args.acknowledge_environment_policy:
        raise context_sync.ContextSyncError(
            "Pass --acknowledge-environment-policy after reviewing portable rule content and preferences"
        )
    project_root, _config_path, config, entry, current, directory = context_sync.configured_context(args)
    environment = normalize_environment_input(
        context_sync.load_capture_input(args, project_root), project_root
    )
    manifests = load_manifests(directory, entry["project_id"])
    heads = manifest_heads(manifests)
    if len(heads) > 1 and not args.merge_heads:
        raise context_sync.ContextSyncError(
            "Concurrent environment manifest heads require explicit review and --merge-heads"
        )
    manifest_id = f"environment-{uuid.uuid4().hex}"
    manifest = {
        "schema_version": ENVIRONMENT_MANIFEST_VERSION,
        "manifest_id": manifest_id,
        "project_id": entry["project_id"],
        "machine_id": config["machine_id"],
        "created_at": context_sync.utc_now(),
        "parent_manifest_ids": [item["manifest_id"] for item in heads],
        "repository": {
            "fingerprint": current.get("fingerprint"),
            "head": current.get("head"),
        },
        **environment,
    }
    manifest["content_sha256"] = manifest_digest(manifest)
    if context_sync.scan_secrets(manifest):
        raise context_sync.ContextSyncError("Environment manifest rejected by the final secret scan")
    path = directory / "environment-manifests" / f"{manifest_id}.json"
    context_sync.atomic_write_json(path, manifest)
    load_manifest_file(path, entry["project_id"])
    return {
        "captured": True,
        "manifest_id": manifest_id,
        "parent_manifest_ids": manifest["parent_manifest_ids"],
        "path": str(path),
        "counts": {key: len(environment[key]) for key in environment},
    }


def command_plan(args: argparse.Namespace) -> dict[str, Any]:
    project_root, _config_path, _config, entry, current, directory = context_sync.configured_context(args)
    manifest = selected_manifest(args, directory, entry["project_id"])
    expected = manifest["repository"].get("fingerprint")
    if expected and current.get("fingerprint") and expected != current.get("fingerprint"):
        raise context_sync.ContextSyncError("Environment manifest belongs to another repository")
    state = load_optional_state(args, project_root)
    plan = build_plan(project_root, manifest, state)
    return {
        "ok": True,
        "read_only": True,
        "project_id": entry["project_id"],
        "manifest_id": manifest["manifest_id"],
        **plan,
    }


def command_apply(args: argparse.Namespace) -> dict[str, Any]:
    if not args.approve_local_rules:
        raise context_sync.ContextSyncError(
            "Pass --approve-local-rules after reviewing environment-plan"
        )
    project_root, _config_path, _config, entry, current, directory = context_sync.configured_context(args)
    manifest = selected_manifest(args, directory, entry["project_id"])
    expected = manifest["repository"].get("fingerprint")
    if expected and current.get("fingerprint") and expected != current.get("fingerprint"):
        raise context_sync.ContextSyncError("Environment manifest belongs to another repository")
    plan = build_plan(project_root, manifest, load_optional_state(args, project_root))
    portable = {item["id"]: item for item in manifest["rules"] if item["classification"] == "local_portable"}
    applied: list[dict[str, str]] = []
    for action in plan["actions"]:
        if action["category"] != "rules" or action["status"] != "apply_local_rule":
            continue
        rule = portable[action["id"]]
        relative, target = normalize_rule_path(rule["path"], project_root)
        if git_path_state(project_root, relative).get("tracked") or target.exists():
            raise context_sync.ContextSyncError(
                f"Rule destination changed after planning; refusing to overwrite: {relative}"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        resolved_parent = target.parent.resolve()
        if not context_sync.is_within(resolved_parent, project_root):
            raise context_sync.ContextSyncError("Rule parent resolves outside the project")
        try:
            with target.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(rule["content"])
        except FileExistsError as error:
            raise context_sync.ContextSyncError(
                f"Rule destination appeared during apply: {relative}"
            ) from error
        if sha256_text(target.read_text(encoding="utf-8")) != rule["content_sha256"]:
            raise context_sync.ContextSyncError(f"Applied rule verification failed: {relative}")
        applied.append({"id": rule["id"], "path": relative})
    return {
        "applied": True,
        "manifest_id": manifest["manifest_id"],
        "local_rules_created": applied,
        "remaining_actions": [
            action for action in plan["actions"]
            if action["category"] != "rules" or action["status"] != "apply_local_rule"
        ],
    }


def command_status(args: argparse.Namespace) -> dict[str, Any]:
    _root, _config_path, _config, entry, _current, directory = context_sync.configured_context(args)
    manifests = load_manifests(directory, entry["project_id"])
    heads = manifest_heads(manifests)
    return {
        "ok": True,
        "project_id": entry["project_id"],
        "manifest_count": len(manifests),
        "head_manifest_ids": [item["manifest_id"] for item in heads],
        "has_conflict": len(heads) > 1,
        "manifest_files": [str(directory / "environment-manifests" / f"{item['manifest_id']}.json") for item in manifests],
    }


def command_audit(args: argparse.Namespace) -> dict[str, Any]:
    result = command_status(args)
    findings = (
        [
            {
                "kind": "multiple-heads",
                "message": "Environment manifest heads require explicit reconciliation",
            }
        ]
        if result["has_conflict"]
        else []
    )
    result.update(
        {
            "ok": not findings,
            "audited": True,
            "scanned_at": context_sync.utc_now(),
            "findings": findings,
        }
    )
    return result


def command_hydrate(args: argparse.Namespace) -> dict[str, Any]:
    project_root, _config_path, _config, entry, current = context_sync.configured_mapping(args)
    if entry["backend"] != "google-drive":
        raise context_sync.ContextSyncError("environment-hydrate requires a Google Drive mapping")
    snapshot = context_sync.resolved(args.snapshot_root)
    context_sync.validate_external_path(snapshot, project_root, "Drive snapshot")
    context_sync.validate_storage(entry, current.get("fingerprint"), snapshot)
    existing = load_manifests(snapshot, entry["project_id"])
    by_id = {item["manifest_id"]: item for item in existing}
    for value in args.environment_file:
        source = context_sync.resolved(value)
        context_sync.validate_external_path(source, project_root, "Downloaded environment manifest")
        manifest = load_manifest_file(source, entry["project_id"], require_filename=False)
        identifier = manifest["manifest_id"]
        if identifier in by_id and by_id[identifier] != manifest:
            raise context_sync.ContextSyncError(f"Environment manifest conflicts with existing content: {identifier}")
        by_id[identifier] = manifest
    validate_manifest_graph(list(by_id.values()))
    target_dir = snapshot / "environment-manifests"
    for identifier, manifest in by_id.items():
        context_sync.atomic_write_json(target_dir / f"{identifier}.json", manifest)
    load_manifests(snapshot, entry["project_id"])
    return {"hydrated": True, "project_id": entry["project_id"], "manifest_count": len(by_id)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Reconcile portable project environment requirements")
    parser.add_argument("--config-path")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect = subparsers.add_parser("inspect", help="Classify declared environment items without writing")
    inspect.add_argument("--project-path", required=True)
    source = inspect.add_mutually_exclusive_group(required=True)
    source.add_argument("--input")
    source.add_argument("--stdin", action="store_true")
    inspect.add_argument("--json", action="store_true")

    capture = subparsers.add_parser("capture", help="Capture an immutable sanitized environment manifest")
    capture.add_argument("--project-path", required=True)
    capture.add_argument("--snapshot-root")
    source = capture.add_mutually_exclusive_group(required=True)
    source.add_argument("--input")
    source.add_argument("--stdin", action="store_true")
    capture.add_argument("--merge-heads", action="store_true")
    capture.add_argument("--acknowledge-environment-policy", action="store_true")
    capture.add_argument("--json", action="store_true")

    for name, handler_help in (
        ("plan", "Plan reconciliation without modifying the destination"),
        ("apply", "Create only missing untracked local AGENTS.md or CLAUDE.md rules"),
    ):
        command = subparsers.add_parser(name, help=handler_help)
        command.add_argument("--project-path", required=True)
        command.add_argument("--snapshot-root")
        command.add_argument("--manifest-id")
        command.add_argument("--local-state")
        if name == "apply":
            command.add_argument("--approve-local-rules", action="store_true")
        command.add_argument("--json", action="store_true")

    for name in ("status", "audit"):
        command = subparsers.add_parser(name)
        command.add_argument("--project-path", required=True)
        command.add_argument("--snapshot-root")
        command.add_argument("--json", action="store_true")

    hydrate = subparsers.add_parser("hydrate")
    hydrate.add_argument("--project-path", required=True)
    hydrate.add_argument("--snapshot-root", required=True)
    hydrate.add_argument("--environment-file", action="append", required=True)
    hydrate.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    handlers = {
        "inspect": command_inspect,
        "capture": command_capture,
        "plan": command_plan,
        "apply": command_apply,
        "status": command_status,
        "audit": command_audit,
        "hydrate": command_hydrate,
    }
    try:
        result = handlers[args.command](args)
        print(json.dumps(result, ensure_ascii=False, indent=2 if args.json else None, sort_keys=True))
        return 0
    except (context_sync.ContextSyncError, OSError, ValueError) as error:
        if getattr(args, "json", False):
            print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False, sort_keys=True))
        else:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
