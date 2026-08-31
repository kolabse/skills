"""Bounded, non-executing skill-source inspection; no agent discovery inference."""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


LAYOUTS = {"codex": ".agents/skills", "claude-code": ".claude/skills"}
MAX_ROOTS = 32
MAX_ENTRIES = 512
MAX_JSON_BYTES = 65536
MAX_SKILL_BYTES = 1048576
NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.+-]+)?\Z")
CONTEXT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z")
SECRET = re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-(?:proj-)?[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16}|[0-9]{6,12}:[A-Za-z0-9_-]{30,})")
CANONICAL = "https://github.com/kolabse/skills"


class InspectionError(RuntimeError):
    pass


def absolute(path: Path) -> Path:
    # Do not resolve links before checking the caller's selected boundary.
    return Path(os.path.abspath(path))


def safe_path(path: Path, boundary: Path) -> bool:
    path, boundary = absolute(path), absolute(boundary)
    try:
        parts = path.relative_to(boundary).parts
    except ValueError:
        return False
    current = boundary
    for part in (None, *parts):
        if part is not None:
            current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            return False
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            return False
    return True


def read_bytes(path: Path, boundary: Path, limit: int) -> bytes:
    if not safe_path(path, boundary):
        raise InspectionError("unsafe-path")
    try:
        if not stat.S_ISREG(path.stat().st_mode):
            raise InspectionError("not-a-regular-file")
        with path.open("rb") as stream:
            data = stream.read(limit + 1)
    except FileNotFoundError as error:
        raise InspectionError("missing-file") from error
    except OSError as error:
        raise InspectionError("unreadable-file") from error
    if len(data) > limit:
        raise InspectionError("file-size-limit")
    return data


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise InspectionError("duplicate-json-key")
        value[key] = item
    return value


def load_json(path: Path, boundary: Path) -> dict[str, Any]:
    try:
        value = json.loads(read_bytes(path, boundary, MAX_JSON_BYTES).decode("utf-8"), object_pairs_hook=unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise InspectionError("invalid-json") from error
    if not isinstance(value, dict):
        raise InspectionError("invalid-json-object")
    return value


def source_identity(value: object) -> str | None:
    """Only echo normalized public GitHub repository identity, never auth/query/ref."""
    if not isinstance(value, str) or len(value) > 2048:
        return None
    candidate = value.strip().replace("\\", "/")
    if candidate.startswith("git@github.com:"):
        candidate = candidate.removeprefix("git@github.com:")
    elif "://" in candidate:
        try:
            parsed = urlparse(candidate)
            if parsed.hostname not in {"github.com", "www.github.com"}:
                return None
            candidate = parsed.path.lstrip("/")
        except ValueError:
            return None
    candidate = candidate.split("/tree/", 1)[0].split("@", 1)[0]
    candidate = candidate.removesuffix(".git")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", candidate):
        return None
    return "https://github.com/" + candidate.lower()


def safe_version(value: object) -> str | None:
    return value if isinstance(value, str) and len(value) <= 80 and VERSION.fullmatch(value) and not SECRET.search(value) else None


def valid_name(value: object) -> bool:
    return isinstance(value, str) and len(value) <= 63 and NAME.fullmatch(value) is not None


def inspect_copy(path: Path, source: dict[str, Any], boundary: Path) -> dict[str, Any]:
    copy: dict[str, Any] = {
        "skill": path.name, "path": str(path), "source_path": source["path"],
        "source_kind": source["kind"], "installed": False, "version": None,
        "metadata_status": "missing", "source_identity": None,
        "skill_sha256": None, "issues": [],
    }
    if not safe_path(path, boundary):
        copy["issues"].append("unsafe-path")
        return copy
    try:
        body = read_bytes(path / "SKILL.md", boundary, MAX_SKILL_BYTES)
        copy["installed"] = True
        copy["skill_sha256"] = hashlib.sha256(body).hexdigest()
    except InspectionError as error:
        copy["issues"].append("skill-" + str(error))
    try:
        metadata = load_json(path / "collection-metadata.json", boundary)
    except InspectionError as error:
        copy["metadata_status"] = "missing" if str(error) == "missing-file" else "invalid"
        copy["issues"].append("metadata-" + str(error))
        return copy
    identity = source_identity(metadata.get("source"))
    canonical = source_identity(metadata.get("canonical_repository"))
    copy["source_identity"] = identity
    copy["version"] = safe_version(metadata.get("version"))
    consistent = (
        type(metadata.get("schema_version")) is int
        and metadata["schema_version"] in {1, 2}
        and metadata.get("collection") == "kolabse-skills"
        and metadata.get("skill") == path.name
        and copy["version"] is not None
        and identity == CANONICAL
        and (metadata["schema_version"] == 1 or canonical == CANONICAL)
    )
    copy["metadata_status"] = "consistent" if consistent else "invalid"
    if not consistent:
        copy["issues"].append("metadata-identity-mismatch")
    return copy


def read_observations(path: Path | None, agent: str, copies: list[dict[str, Any]]) -> dict[str, Any]:
    rows = {
        copy["skill"]: {"skill": copy["skill"], "availability": "unknown",
                        "invocation": "unknown", "copy_path": None}
        for copy in copies
    }
    result: dict[str, Any] = {
        "status": "not-provided", "context_id": None, "observed_at": None, "skills": [],
    }
    if path is not None:
        path = absolute(path)
        value = load_json(path, path.parent)
        if SECRET.search(json.dumps(value, ensure_ascii=False)):
            raise InspectionError("observations-sensitive-content")
        required = {"schema_version", "agent", "context_id", "observed_at", "skills"}
        if set(value) != required or type(value.get("schema_version")) is not int or value["schema_version"] != 1:
            raise InspectionError("observations-invalid-contract")
        if value["agent"] != agent:
            raise InspectionError("observations-agent-mismatch")
        context = value["context_id"]
        if not isinstance(context, str) or not CONTEXT.fullmatch(context):
            raise InspectionError("observations-invalid-context-id")
        timestamp = value["observed_at"]
        try:
            if not isinstance(timestamp, str) or len(timestamp) > 40:
                raise ValueError()
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})", timestamp):
                raise ValueError()
            datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError as error:
            raise InspectionError("observations-invalid-timestamp") from error
        observations = value["skills"]
        if not isinstance(observations, list) or len(observations) > MAX_ENTRIES:
            raise InspectionError("observations-invalid-skills")
        seen: set[str] = set()
        known_paths = {(copy["skill"], copy["path"]) for copy in copies}
        for row in observations:
            if not isinstance(row, dict) or not {"skill", "availability", "invocation"} <= set(row) or set(row) - {"skill", "availability", "invocation", "copy_path"}:
                raise InspectionError("observations-invalid-row")
            name = row["skill"]
            if not valid_name(name) or name in seen:
                raise InspectionError("observations-invalid-or-duplicate-skill")
            if row["availability"] not in ("available", "unavailable", "unknown") or row["invocation"] not in ("invoked", "not-invoked", "unknown"):
                raise InspectionError("observations-invalid-state")
            selected = row.get("copy_path")
            if selected is not None:
                if not isinstance(selected, str) or not Path(selected).is_absolute() or (name, str(absolute(Path(selected)))) not in known_paths:
                    raise InspectionError("observations-uninspected-copy-path")
                selected = str(absolute(Path(selected)))
            seen.add(name)
            rows[name] = {"skill": name, "availability": row["availability"],
                          "invocation": row["invocation"], "copy_path": selected}
        result.update(status="user-reported", context_id=context, observed_at=timestamp)
    result["skills"] = [rows[name] for name in sorted(rows)]
    return result


def inspect_sources(
    project: Path, agent: str, skill_roots: list[Path] | None = None,
    plugin_roots: list[Path] | None = None, observations: Path | None = None,
) -> dict[str, Any]:
    if agent not in LAYOUTS:
        raise InspectionError("unsupported-agent")
    project = absolute(project)
    roots = [("project", project / LAYOUTS[agent], project)]
    roots += [("user-root", absolute(path), absolute(path)) for path in skill_roots or []]
    roots += [("plugin", absolute(path), absolute(path)) for path in plugin_roots or []]
    if len(roots) > MAX_ROOTS:
        raise InspectionError("source-root-limit")
    sources: list[dict[str, Any]] = []
    copies: list[dict[str, Any]] = []
    seen_roots: set[str] = set()
    seen_paths: set[str] = set()
    for kind, root, boundary in roots:
        layout = root / "skills" if kind == "plugin" else root
        key = os.path.normcase(str(layout))
        if key in seen_roots:
            continue
        seen_roots.add(key)
        source = {"kind": kind, "path": str(root), "status": "inspected", "reason_code": None}
        sources.append(source)
        if not safe_path(layout, boundary):
            source.update(status="unsafe", reason_code="unsafe-path")
            continue
        if not layout.exists():
            source.update(status="missing", reason_code="missing-directory")
            continue
        if not layout.is_dir():
            source.update(status="invalid", reason_code="not-a-directory")
            continue
        try:
            entries = []
            with os.scandir(layout) as iterator:
                for entry in iterator:
                    entries.append(entry.name)
                    if len(entries) > MAX_ENTRIES:
                        break
            if len(entries) > MAX_ENTRIES:
                source.update(status="invalid", reason_code="source-entry-limit")
                continue
            for name in sorted(entries):
                if not valid_name(name):
                    continue
                path = layout / name
                if not safe_path(path, boundary):
                    source.update(status="unsafe", reason_code="unsafe-child-path")
                    continue
                if not path.is_dir():
                    continue
                if len(copies) >= MAX_ENTRIES:
                    raise InspectionError("copy-count-limit")
                copy_key = os.path.normcase(str(path))
                if copy_key not in seen_paths:
                    seen_paths.add(copy_key)
                    copies.append(inspect_copy(path, source, boundary))
        except OSError:
            source.update(status="invalid", reason_code="unreadable-directory")
    copies.sort(key=lambda item: (item["skill"], item["path"]))
    conflicts = []
    for name in sorted({copy["skill"] for copy in copies}):
        group = [copy for copy in copies if copy["skill"] == name]
        if len(group) < 2:
            continue
        kinds = ["duplicate-copies"]
        for field, label in (("version", "version-conflict"), ("skill_sha256", "content-conflict"), ("source_identity", "source-conflict")):
            if len({copy[field] for copy in group if copy[field] is not None}) > 1:
                kinds.append(label)
        conflicts.append({"skill": name, "kinds": kinds, "paths": [copy["path"] for copy in group],
                          "versions": [copy["version"] for copy in group], "effective_copy": "unknown"})
    return {
        "schema_version": 1, "agent": agent, "mutates": False,
        "scope": "bounded-explicit-sources", "sources": sources, "copies": copies,
        "conflicts": conflicts, "observations": read_observations(observations, agent, copies),
        "limitations": ["filesystem-does-not-prove-agent-availability-or-invocation",
                        "source-priority-not-inferred", "metadata-is-not-content-provenance",
                        "skill-hash-covers-skill-md-only", "local-lock-sources-not-followed",
                        "observations-not-independently-verified", "observation-freshness-not-verified"],
    }


def bounded_project_state(project: Path, agent: str, diagnosis: dict[str, Any], known_skills: set[str]) -> dict[str, Any]:
    """Legacy-shaped install state without following paths supplied by lock contents."""
    project = absolute(project)
    lock_path = project / "skills-lock.json"
    state: dict[str, Any] = {
        "schema_version": 1, "collection": "kolabse-skills", "agent": agent,
        "layout": LAYOUTS[agent], "scope": "project", "project": str(project),
        "lock_file": str(lock_path), "skills": [],
    }
    try:
        lock = load_json(lock_path, project)
        entries = lock.get("skills")
        if not isinstance(entries, dict):
            raise InspectionError("invalid-skills-lock")
        if len(entries) > MAX_ENTRIES:
            raise InspectionError("skills-lock-entry-limit")
    except InspectionError as error:
        state["inspection_problem"] = "bounded skills lock inspection failed: " + str(error)
        return state
    copies = {item["skill"]: item for item in diagnosis["copies"] if item["source_kind"] == "project"}
    for name in sorted(set(entries) & known_skills):
        entry = entries[name]
        if not isinstance(entry, dict):
            state["inspection_problem"] = "bounded skills lock contains an invalid entry"
            continue
        copy = copies.get(name, {})
        identity = source_identity(entry.get("source"))
        source_valid = identity == CANONICAL and entry.get("sourceType") in (None, "github")
        metadata_valid = copy.get("metadata_status") == "consistent"
        provenance = "verified" if source_valid and metadata_valid else "legacy-unverified" if source_valid and copy.get("metadata_status") == "missing" else "mismatch"
        digest = entry.get("computedHash")
        state["skills"].append({
            "name": name, "installed": copy.get("installed", False),
            "path": str(project / LAYOUTS[agent] / name), "source": identity or "unverified-source",
            "computed_hash": digest if isinstance(digest, str) and re.fullmatch(r"[0-9a-fA-F]{64}", digest) else "",
            "collection": "kolabse-skills" if metadata_valid else "", "version": copy.get("version") or "unknown",
            "metadata_valid": metadata_valid, "metadata_error": "" if metadata_valid else "missing-or-invalid-metadata",
            "provenance_status": provenance, "source_kind": "github" if source_valid else "unknown",
            "source_identity": identity or "", "provenance_error": "" if source_valid else "source-not-verified-within-explicit-boundary",
            "legacy_adoption_available": provenance == "legacy-unverified",
        })
    return state
