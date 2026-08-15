from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any


MAX_RULE_FILES = 100
MAX_RULE_BYTES = 64 * 1024
MAX_BLOCK_CHARS = 8000
MAX_CANDIDATES = 100
MAX_ITEMS = 20
MAX_ITEM_CHARS = 1000
DEFAULT_EXCLUDED_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "vendor",
    "dist",
    "build",
    "__pycache__",
}
NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SKILL_REFERENCE_PATTERN = re.compile(r"(?<![A-Za-z0-9_-])\$([a-z0-9]+(?:-[a-z0-9]+)*)")
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----", re.I),
    re.compile(r"\b(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]{12,}", re.I),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    re.compile(
        r"\b(?:password|passwd|secret|api[_-]?key|access[_-]?token|refresh[_-]?token)"
        r"\s*[:=]\s*['\"]?[A-Za-z0-9._~+/=-]{8,}",
        re.I,
    ),
)
DISQUALIFIERS = {
    "existing-skill",
    "policy-only",
    "single-command",
    "project-specific",
    "sensitive",
    "volatile",
    "not-testable",
}
RESOURCE_TYPES = {"script", "reference", "asset", "none"}
CONTRIBUTION_ATTESTATIONS = {
    "right_to_share",
    "apache_2_0",
    "no_secrets",
    "no_confidential_information",
}
CONTRIBUTION_CANDIDATE_FIELDS = (
    "name",
    "title",
    "summary",
    "triggers",
    "workflow_steps",
    "completion_criteria",
    "safety_boundaries",
    "resources",
    "scope",
    "stability",
    "automation",
    "existing_skill_notes",
    "classification",
    "score",
    "score_breakdown",
    "existing_overlap",
    "review_flags",
)
SHARE_UNSAFE_PATTERNS = (
    re.compile(r"\b(?:https?|file)://", re.I),
    re.compile(r"(?<![A-Za-z0-9])(?:[A-Za-z]:[\\/]|\\\\)[^\s]+"),
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
)


class DiscoveryError(RuntimeError):
    pass


def resolved(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_digest(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def run_git(root: Path, arguments: list[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        return None
    return result.stdout.rstrip("\r\n") if result.returncode == 0 else None


def contains_secret(value: object) -> bool:
    if isinstance(value, dict):
        return any(contains_secret(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_secret(item) for item in value)
    if isinstance(value, str):
        return any(pattern.search(value) for pattern in SECRET_PATTERNS)
    return False


def contains_share_unsafe(value: object) -> bool:
    if isinstance(value, dict):
        return any(contains_share_unsafe(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_share_unsafe(item) for item in value)
    if isinstance(value, str):
        return any(pattern.search(value) for pattern in SHARE_UNSAFE_PATTERNS)
    return False


def discover_rule_paths(root: Path, excluded: set[str]) -> list[Path]:
    paths: list[Path] = []
    for directory, names, files in os.walk(root, followlinks=False):
        names[:] = sorted(
            name
            for name in names
            if name not in excluded and not (Path(directory) / name).is_symlink()
        )
        if "AGENTS.md" in files:
            paths.append((Path(directory) / "AGENTS.md").resolve())
            if len(paths) > MAX_RULE_FILES:
                raise DiscoveryError(
                    f"Project contains more than {MAX_RULE_FILES} AGENTS.md files"
                )
    return sorted(paths, key=lambda path: path.relative_to(root).as_posix())


def git_provenance(root: Path, path: Path) -> dict[str, Any]:
    git_root_value = run_git(root, ["rev-parse", "--show-toplevel"])
    if not git_root_value:
        return {"available": False, "tracked": False, "ignored": False}
    git_root = Path(git_root_value).resolve()
    try:
        relative = path.relative_to(git_root).as_posix()
    except ValueError:
        return {"available": True, "tracked": False, "ignored": False}
    tracked = run_git(
        git_root, ["ls-files", "--error-unmatch", "--", relative]
    ) is not None
    ignored = run_git(git_root, ["check-ignore", "-q", "--", relative]) is not None
    result: dict[str, Any] = {
        "available": True,
        "tracked": tracked,
        "ignored": ignored,
    }
    if tracked:
        result.update(
            {
                "modified": bool(
                    run_git(
                        git_root,
                        ["status", "--porcelain=v1", "--", relative],
                    )
                ),
                "blob_oid": run_git(git_root, ["rev-parse", f"HEAD:{relative}"]),
                "head": run_git(git_root, ["rev-parse", "HEAD"]),
            }
        )
    return result


def split_blocks(relative: str, content: str) -> list[dict[str, Any]]:
    lines = content.splitlines()
    ranges: list[tuple[int, int]] = []
    index = 0
    while index < len(lines):
        if not lines[index].strip():
            index += 1
            continue
        managed = re.fullmatch(
            r"\s*<!--\s*([a-z0-9-]+):start\s*-->\s*", lines[index], re.I
        )
        if managed:
            end_pattern = re.compile(
                rf"\s*<!--\s*{re.escape(managed.group(1))}:end\s*-->\s*",
                re.I,
            )
            end = index
            while end < len(lines) and not end_pattern.fullmatch(lines[end]):
                end += 1
            if end == len(lines):
                raise DiscoveryError(
                    f"Managed rule block is not closed: {relative}:{index + 1}"
                )
            ranges.append((index + 1, end + 1))
            index = end + 1
            continue
        if lines[index].lstrip().startswith("#"):
            end = index + 1
            while end < len(lines):
                if lines[end].lstrip().startswith("#") or re.fullmatch(
                    r"\s*<!--\s*[a-z0-9-]+:start\s*-->\s*", lines[end], re.I
                ):
                    break
                end += 1
            while end > index + 1 and not lines[end - 1].strip():
                end -= 1
            ranges.append((index + 1, end))
            index = end
            continue
        end = index + 1
        while end < len(lines) and lines[end].strip():
            end += 1
        ranges.append((index + 1, end))
        index = end
    blocks: list[dict[str, Any]] = []
    for start_line, end_line in ranges:
        text = "\n".join(lines[start_line - 1 : end_line]).strip()
        if not text:
            continue
        if len(text) > MAX_BLOCK_CHARS:
            raise DiscoveryError(
                f"Rule block exceeds {MAX_BLOCK_CHARS} characters: "
                f"{relative}:{start_line}"
            )
        seed = f"{relative}\0{start_line}\0{end_line}\0{text}"
        blocks.append(
            {
                "block_id": f"block-{digest_text(seed)[:16]}",
                "start_line": start_line,
                "end_line": end_line,
                "sha256": digest_text(text),
                "text": text,
                "skill_references": sorted(set(SKILL_REFERENCE_PATTERN.findall(text))),
            }
        )
    return blocks


def inventory(project_root: Path, excluded: set[str]) -> dict[str, Any]:
    if not project_root.is_dir():
        raise DiscoveryError(f"Project directory does not exist: {project_root}")
    files: list[dict[str, Any]] = []
    block_count = 0
    for path in discover_rule_paths(project_root, excluded):
        if path.is_symlink() or not path.is_file() or not is_within(path, project_root):
            raise DiscoveryError(f"Rule path is not a regular project file: {path}")
        if path.stat().st_size > MAX_RULE_BYTES:
            raise DiscoveryError(
                f"Rule file exceeds {MAX_RULE_BYTES} bytes: {path.relative_to(project_root)}"
            )
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise DiscoveryError(f"Rule file must be UTF-8: {path}") from error
        relative = path.relative_to(project_root).as_posix()
        if contains_secret(content):
            raise DiscoveryError(f"Possible secret detected in rule file: {relative}")
        blocks = split_blocks(relative, content)
        block_count += len(blocks)
        files.append(
            {
                "path": relative,
                "scope": "project" if relative == "AGENTS.md" else f"subtree:{path.parent.relative_to(project_root).as_posix()}",
                "sha256": digest_text(content),
                "git": git_provenance(project_root, path),
                "blocks": blocks,
            }
        )
    result = {
        "schema_version": 1,
        "read_only": True,
        "project_root": str(project_root),
        "rule_file_count": len(files),
        "block_count": block_count,
        "excluded_directories": sorted(excluded),
        "files": files,
    }
    result["inventory_sha256"] = canonical_digest(result)
    return result


def safe_string(value: object, label: str, maximum: int = MAX_ITEM_CHARS) -> str:
    if not isinstance(value, str):
        raise DiscoveryError(f"{label} must be a string")
    result = value.strip()
    if not result or len(result) > maximum or re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", result):
        raise DiscoveryError(f"{label} must contain 1-{maximum} safe characters")
    if contains_secret(result):
        raise DiscoveryError(f"{label} contains a possible secret")
    return result


def string_list(value: object, label: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or len(value) > MAX_ITEMS or (not value and not allow_empty):
        expectation = "0" if allow_empty else "1"
        raise DiscoveryError(f"{label} must contain {expectation}-{MAX_ITEMS} items")
    return [safe_string(item, f"{label}[{index}]") for index, item in enumerate(value)]


def load_json_input(args: argparse.Namespace, label: str = "Candidate input") -> object:
    text = sys.stdin.read() if args.stdin else resolved(args.input).read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise DiscoveryError(f"{label} is invalid JSON: {error}") from error


def load_json_file(path: str, label: str) -> object:
    try:
        return json.loads(resolved(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise DiscoveryError(f"{label} is invalid JSON: {error}") from error


def verify_embedded_digest(value: object, field: str, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not isinstance(value.get(field), str):
        raise DiscoveryError(f"{label} has no {field}")
    without_digest = {key: item for key, item in value.items() if key != field}
    if value[field] != canonical_digest(without_digest):
        raise DiscoveryError(f"{label} digest does not match its content")
    return value


def normalize_candidate_input(value: object, valid_blocks: set[str]) -> list[dict[str, Any]]:
    if not isinstance(value, dict) or set(value) != {"candidates"}:
        raise DiscoveryError("Candidate input must contain only a candidates array")
    candidates = value["candidates"]
    if not isinstance(candidates, list) or not candidates or len(candidates) > MAX_CANDIDATES:
        raise DiscoveryError(f"candidates must contain 1-{MAX_CANDIDATES} items")
    required = {
        "name", "title", "summary", "source_block_ids", "triggers",
        "workflow_steps", "completion_criteria", "safety_boundaries",
        "resources", "scope", "stability", "automation", "disqualifiers",
        "existing_skill_notes",
    }
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(candidates):
        if not isinstance(raw, dict) or set(raw) != required:
            raise DiscoveryError(f"candidates[{index}] has missing or unexpected fields")
        name = safe_string(raw["name"], f"candidates[{index}].name", 63)
        if not NAME_PATTERN.fullmatch(name) or name in seen:
            raise DiscoveryError(f"candidates[{index}].name is invalid or duplicated")
        seen.add(name)
        block_ids = string_list(raw["source_block_ids"], f"candidates[{index}].source_block_ids")
        missing = sorted(set(block_ids) - valid_blocks)
        if missing:
            raise DiscoveryError(
                f"candidates[{index}] references unknown current blocks: {missing}"
            )
        resources = string_list(raw["resources"], f"candidates[{index}].resources", allow_empty=True)
        if set(resources) - RESOURCE_TYPES or ("none" in resources and len(resources) > 1):
            raise DiscoveryError(f"candidates[{index}].resources is invalid")
        disqualifiers = string_list(
            raw["disqualifiers"], f"candidates[{index}].disqualifiers", allow_empty=True
        )
        if set(disqualifiers) - DISQUALIFIERS:
            raise DiscoveryError(f"candidates[{index}].disqualifiers is invalid")
        scope = safe_string(raw["scope"], f"candidates[{index}].scope")
        stability = safe_string(raw["stability"], f"candidates[{index}].stability")
        automation = safe_string(raw["automation"], f"candidates[{index}].automation")
        if scope not in {"cross-project", "project-family", "single-project"}:
            raise DiscoveryError(f"candidates[{index}].scope is invalid")
        if stability not in {"stable", "evolving", "volatile"}:
            raise DiscoveryError(f"candidates[{index}].stability is invalid")
        if automation not in {"deterministic", "mixed", "judgment"}:
            raise DiscoveryError(f"candidates[{index}].automation is invalid")
        normalized.append(
            {
                "name": name,
                "title": safe_string(raw["title"], f"candidates[{index}].title", 128),
                "summary": safe_string(raw["summary"], f"candidates[{index}].summary", 1000),
                "source_block_ids": sorted(set(block_ids)),
                "triggers": string_list(raw["triggers"], f"candidates[{index}].triggers"),
                "workflow_steps": string_list(raw["workflow_steps"], f"candidates[{index}].workflow_steps"),
                "completion_criteria": string_list(raw["completion_criteria"], f"candidates[{index}].completion_criteria"),
                "safety_boundaries": string_list(raw["safety_boundaries"], f"candidates[{index}].safety_boundaries"),
                "resources": sorted(set(resources)),
                "scope": scope,
                "stability": stability,
                "automation": automation,
                "disqualifiers": sorted(set(disqualifiers)),
                "existing_skill_notes": string_list(raw["existing_skill_notes"], f"candidates[{index}].existing_skill_notes", allow_empty=True),
            }
        )
    if contains_secret(normalized):
        raise DiscoveryError("Candidate input contains a possible secret")
    return normalized


def load_catalogs(project_root: Path, values: list[str]) -> list[dict[str, Any]]:
    paths = [resolved(value) for value in values]
    default = project_root / "skill-catalog.json"
    if not paths and default.is_file():
        paths = [default]
    skills: dict[str, dict[str, Any]] = {}
    for path in paths:
        try:
            catalog = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise DiscoveryError(f"Skill catalog is invalid: {path}: {error}") from error
        entries = catalog.get("skills") if isinstance(catalog, dict) else None
        if not isinstance(entries, list):
            raise DiscoveryError(f"Skill catalog has no skills array: {path}")
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
                raise DiscoveryError(f"Skill catalog entry is invalid: {path}")
            name = safe_string(entry["name"], f"Skill catalog name in {path}", 63)
            if not NAME_PATTERN.fullmatch(name):
                raise DiscoveryError(f"Skill catalog name is invalid: {path}")
            provides = entry.get("provides", [])
            if not isinstance(provides, list) or not all(isinstance(item, str) for item in provides):
                raise DiscoveryError(f"Skill catalog provides are invalid: {path}")
            normalized_provides = [
                safe_string(item, f"Skill catalog capability in {path}", 128)
                for item in provides
            ]
            skills[name] = {"name": name, "provides": sorted(normalized_provides)}
    return [skills[name] for name in sorted(skills)]


def tokens(value: str) -> set[str]:
    ignored = {"skill", "project", "workflow", "manage", "use", "and", "the"}
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.lower().replace("_", "-"))
        if len(token) > 2 and token not in ignored
    }


def similarity(left: set[str], right: set[str]) -> float:
    return len(left & right) / len(left | right) if left and right else 0.0


def existing_overlap(candidate: dict[str, Any], skills: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidate_tokens = tokens(candidate["name"] + " " + candidate["summary"])
    best: tuple[float, str] | None = None
    for skill in skills:
        score = 1.0 if skill["name"] == candidate["name"] else similarity(
            candidate_tokens,
            tokens(skill["name"] + " " + " ".join(skill["provides"])),
        )
        if best is None or score > best[0]:
            best = (score, skill["name"])
    if best is None or best[0] < 0.2:
        return None
    penalty = 5 if best[0] >= 0.6 else 3 if best[0] >= 0.35 else 1
    return {"skill": best[1], "similarity": round(best[0], 3), "penalty": penalty}


def score_candidate(candidate: dict[str, Any], overlap: dict[str, Any] | None) -> dict[str, Any]:
    workflow_count = len(candidate["workflow_steps"])
    breakdown = {
        "evidence": min(3, len(candidate["source_block_ids"])),
        "portability": {"cross-project": 3, "project-family": 2, "single-project": 0}[candidate["scope"]],
        "workflow_depth": 3 if workflow_count >= 5 else 2 if workflow_count >= 3 else 1 if workflow_count >= 2 else 0,
        "trigger_clarity": 2 if len(candidate["triggers"]) >= 2 else 1,
        "stability": {"stable": 2, "evolving": 1, "volatile": 0}[candidate["stability"]],
        "automation": {"deterministic": 2, "mixed": 1, "judgment": 0}[candidate["automation"]],
        "testability": 2 if len(candidate["completion_criteria"]) >= 2 else 1,
        "safety": 2 if len(candidate["safety_boundaries"]) >= 2 else 1,
        "resources": int(any(item in {"script", "reference"} for item in candidate["resources"])),
        "overlap_penalty": -(overlap["penalty"] if overlap else 0),
    }
    score = sum(breakdown.values())
    hard_reasons = list(candidate["disqualifiers"])
    review_flags: list[str] = []
    if overlap and overlap["similarity"] == 1.0:
        hard_reasons.append("identical-existing-skill")
    elif overlap and overlap["similarity"] >= 0.6:
        review_flags.append("high-existing-skill-overlap")
    if len(candidate["source_block_ids"]) < 2:
        review_flags.append("single-source-block")
    if hard_reasons or score <= 8:
        classification = "reject"
    elif score <= 12 or review_flags:
        classification = "investigate"
    else:
        classification = "recommended"
    return {
        **candidate,
        "score": score,
        "classification": classification,
        "score_breakdown": breakdown,
        "existing_overlap": overlap,
        "rejection_reasons": sorted(set(hard_reasons)),
        "review_flags": sorted(set(review_flags)),
    }


def score_candidates(
    candidates: list[dict[str, Any]],
    rules: dict[str, Any],
    skills: list[dict[str, Any]],
) -> dict[str, Any]:
    block_index = {
        block["block_id"]: {
            "path": file["path"],
            "start_line": block["start_line"],
            "end_line": block["end_line"],
            "sha256": block["sha256"],
        }
        for file in rules["files"]
        for block in file["blocks"]
    }
    scored = [
        score_candidate(candidate, existing_overlap(candidate, skills))
        for candidate in candidates
    ]
    for index, candidate in enumerate(scored):
        current = tokens(candidate["name"] + " " + candidate["summary"])
        for earlier in scored[:index]:
            if similarity(current, tokens(earlier["name"] + " " + earlier["summary"])) >= 0.7:
                candidate["classification"] = "reject"
                candidate["rejection_reasons"] = sorted(
                    set(candidate["rejection_reasons"] + [f"duplicate-candidate:{earlier['name']}"])
                )
                break
        candidate["source_evidence"] = [block_index[item] for item in candidate["source_block_ids"]]
    order = {"recommended": 0, "investigate": 1, "reject": 2}
    scored.sort(key=lambda item: (order[item["classification"]], -item["score"], item["name"]))
    counts = {name: sum(item["classification"] == name for item in scored) for name in order}
    report = {
        "schema_version": 1,
        "read_only": True,
        "inventory_sha256": rules["inventory_sha256"],
        "catalog_skill_count": len(skills),
        "counts": counts,
        "candidates": scored,
    }
    report["report_sha256"] = canonical_digest(report)
    return report


def normalize_contribution_details(
    value: object, source_block_ids: list[str]
) -> dict[str, Any]:
    required = {
        "evidence_summaries",
        "examples",
        "proposed_tests",
        "known_limitations",
        "attestations",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise DiscoveryError("Contribution details have missing or unexpected fields")
    evidence = value["evidence_summaries"]
    if not isinstance(evidence, list) or len(evidence) != len(source_block_ids):
        raise DiscoveryError("evidence_summaries must cover every source block exactly once")
    normalized_evidence: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, item in enumerate(evidence):
        if not isinstance(item, dict) or set(item) != {"block_id", "summary"}:
            raise DiscoveryError(
                f"evidence_summaries[{index}] must contain only block_id and summary"
            )
        block_id = safe_string(item["block_id"], f"evidence_summaries[{index}].block_id", 64)
        if block_id not in source_block_ids or block_id in seen:
            raise DiscoveryError(
                f"evidence_summaries[{index}].block_id is unknown or duplicated"
            )
        seen.add(block_id)
        normalized_evidence.append(
            {
                "block_id": block_id,
                "summary": safe_string(
                    item["summary"], f"evidence_summaries[{index}].summary", 1000
                ),
            }
        )
    if seen != set(source_block_ids):
        raise DiscoveryError("evidence_summaries do not cover every source block")
    examples = value["examples"]
    if not isinstance(examples, list) or not examples or len(examples) > MAX_ITEMS:
        raise DiscoveryError(f"examples must contain 1-{MAX_ITEMS} items")
    normalized_examples: list[dict[str, Any]] = []
    for index, item in enumerate(examples):
        if not isinstance(item, dict) or set(item) != {"prompt", "expected_outcomes"}:
            raise DiscoveryError(
                f"examples[{index}] must contain only prompt and expected_outcomes"
            )
        normalized_examples.append(
            {
                "prompt": safe_string(item["prompt"], f"examples[{index}].prompt"),
                "expected_outcomes": string_list(
                    item["expected_outcomes"], f"examples[{index}].expected_outcomes"
                ),
            }
        )
    attestations = value["attestations"]
    if (
        not isinstance(attestations, dict)
        or set(attestations) != CONTRIBUTION_ATTESTATIONS
        or any(attestations[name] is not True for name in CONTRIBUTION_ATTESTATIONS)
    ):
        raise DiscoveryError("Every contribution attestation must be explicitly true")
    normalized = {
        "evidence_summaries": sorted(
            normalized_evidence, key=lambda item: item["block_id"]
        ),
        "examples": normalized_examples,
        "proposed_tests": string_list(value["proposed_tests"], "proposed_tests"),
        "known_limitations": string_list(
            value["known_limitations"], "known_limitations", allow_empty=True
        ),
        "attestations": {name: True for name in sorted(CONTRIBUTION_ATTESTATIONS)},
    }
    if contains_secret(normalized) or contains_share_unsafe(normalized):
        raise DiscoveryError(
            "Contribution details contain a possible secret, URL, email, or absolute path"
        )
    return normalized


def export_contribution(
    report_value: object, details_value: object, candidate_name: str
) -> dict[str, Any]:
    report = verify_embedded_digest(report_value, "report_sha256", "Candidate report")
    if report.get("schema_version") != 1 or report.get("read_only") is not True:
        raise DiscoveryError("Candidate report has an unsupported contract")
    candidates = report.get("candidates")
    if not isinstance(candidates, list):
        raise DiscoveryError("Candidate report has no candidates array")
    selected = [item for item in candidates if isinstance(item, dict) and item.get("name") == candidate_name]
    if len(selected) != 1:
        raise DiscoveryError("Candidate name must identify exactly one report candidate")
    candidate = selected[0]
    if candidate.get("classification") == "reject":
        raise DiscoveryError("Rejected candidates cannot be exported for contribution")
    source_ids = candidate.get("source_block_ids")
    source_evidence = candidate.get("source_evidence")
    if (
        not isinstance(source_ids, list)
        or not source_ids
        or not isinstance(source_evidence, list)
        or len(source_ids) != len(source_evidence)
    ):
        raise DiscoveryError("Candidate source evidence is incomplete")
    details = normalize_contribution_details(details_value, source_ids)
    evidence_by_id = {
        item["block_id"]: item["summary"] for item in details["evidence_summaries"]
    }
    portable_evidence: list[dict[str, str]] = []
    for block_id, source in zip(source_ids, source_evidence):
        if not isinstance(source, dict) or not isinstance(source.get("sha256"), str):
            raise DiscoveryError("Candidate source evidence is malformed")
        portable_evidence.append(
            {
                "block_id": block_id,
                "source_sha256": source["sha256"],
                "summary": evidence_by_id[block_id],
            }
        )
    if any(field not in candidate for field in CONTRIBUTION_CANDIDATE_FIELDS):
        raise DiscoveryError("Candidate report is missing contribution fields")
    package = {
        "schema_version": 1,
        "kind": "skill-candidate-contribution",
        "license": "Apache-2.0",
        "source_report": {
            "inventory_sha256": report.get("inventory_sha256"),
            "report_sha256": report["report_sha256"],
        },
        "candidate": {
            field: candidate[field] for field in CONTRIBUTION_CANDIDATE_FIELDS
        },
        "source_evidence": portable_evidence,
        "examples": details["examples"],
        "proposed_tests": details["proposed_tests"],
        "known_limitations": details["known_limitations"],
        "attestations": details["attestations"],
    }
    if contains_secret(package) or contains_share_unsafe(package):
        raise DiscoveryError(
            "Contribution package contains a possible secret, URL, email, or absolute path"
        )
    package["package_sha256"] = canonical_digest(package)
    return package


def validate_contribution(value: object) -> dict[str, Any]:
    package = verify_embedded_digest(value, "package_sha256", "Contribution package")
    required = {
        "schema_version",
        "kind",
        "license",
        "source_report",
        "candidate",
        "source_evidence",
        "examples",
        "proposed_tests",
        "known_limitations",
        "attestations",
        "package_sha256",
    }
    if set(package) != required:
        raise DiscoveryError("Contribution package has missing or unexpected fields")
    if (
        package["schema_version"] != 1
        or package["kind"] != "skill-candidate-contribution"
        or package["license"] != "Apache-2.0"
    ):
        raise DiscoveryError("Contribution package has an unsupported contract")
    candidate = package["candidate"]
    evidence = package["source_evidence"]
    attestations = package["attestations"]
    if (
        not isinstance(candidate, dict)
        or set(candidate) != set(CONTRIBUTION_CANDIDATE_FIELDS)
        or candidate.get("classification") not in {"recommended", "investigate"}
    ):
        raise DiscoveryError("Contribution candidate is missing or not eligible")
    name = safe_string(candidate.get("name"), "candidate.name", 63)
    if not NAME_PATTERN.fullmatch(name):
        raise DiscoveryError("Contribution candidate name is invalid")
    safe_string(candidate.get("title"), "candidate.title", 128)
    safe_string(candidate.get("summary"), "candidate.summary")
    for field in (
        "triggers",
        "workflow_steps",
        "completion_criteria",
        "safety_boundaries",
    ):
        string_list(candidate.get(field), f"candidate.{field}")
    string_list(
        candidate.get("existing_skill_notes"),
        "candidate.existing_skill_notes",
        allow_empty=True,
    )
    string_list(candidate.get("review_flags"), "candidate.review_flags", allow_empty=True)
    resources = string_list(
        candidate.get("resources"), "candidate.resources", allow_empty=True
    )
    if set(resources) - RESOURCE_TYPES or ("none" in resources and len(resources) > 1):
        raise DiscoveryError("Contribution candidate resources are invalid")
    if candidate.get("scope") not in {"cross-project", "project-family", "single-project"}:
        raise DiscoveryError("Contribution candidate scope is invalid")
    if candidate.get("stability") not in {"stable", "evolving", "volatile"}:
        raise DiscoveryError("Contribution candidate stability is invalid")
    if candidate.get("automation") not in {"deterministic", "mixed", "judgment"}:
        raise DiscoveryError("Contribution candidate automation is invalid")
    if not isinstance(candidate.get("score"), int) or isinstance(candidate.get("score"), bool):
        raise DiscoveryError("Contribution candidate score is invalid")
    breakdown = candidate.get("score_breakdown")
    if not isinstance(breakdown, dict) or not all(
        isinstance(item, int) and not isinstance(item, bool) for item in breakdown.values()
    ):
        raise DiscoveryError("Contribution candidate score breakdown is invalid")
    overlap = candidate.get("existing_overlap")
    if overlap is not None and not isinstance(overlap, dict):
        raise DiscoveryError("Contribution candidate overlap is invalid")
    source_report = package["source_report"]
    if not isinstance(source_report, dict) or set(source_report) != {
        "inventory_sha256",
        "report_sha256",
    }:
        raise DiscoveryError("Contribution source report is malformed")
    for field in ("inventory_sha256", "report_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", str(source_report[field])):
            raise DiscoveryError(f"Contribution source report {field} is invalid")
    if not isinstance(evidence, list) or not evidence:
        raise DiscoveryError("Contribution package has no source evidence")
    block_ids: set[str] = set()
    for index, item in enumerate(evidence):
        if not isinstance(item, dict) or set(item) != {
            "block_id",
            "source_sha256",
            "summary",
        }:
            raise DiscoveryError(f"source_evidence[{index}] is malformed")
        block_id = safe_string(item["block_id"], f"source_evidence[{index}].block_id", 64)
        if block_id in block_ids or not re.fullmatch(r"block-[0-9a-f]{16}", block_id):
            raise DiscoveryError(f"source_evidence[{index}].block_id is invalid or duplicated")
        block_ids.add(block_id)
        if not re.fullmatch(r"[0-9a-f]{64}", str(item["source_sha256"])):
            raise DiscoveryError(f"source_evidence[{index}].source_sha256 is invalid")
        safe_string(item["summary"], f"source_evidence[{index}].summary")
    examples = package["examples"]
    if not isinstance(examples, list) or not examples or len(examples) > MAX_ITEMS:
        raise DiscoveryError("Contribution examples are invalid")
    for index, item in enumerate(examples):
        if not isinstance(item, dict) or set(item) != {"prompt", "expected_outcomes"}:
            raise DiscoveryError(f"examples[{index}] is malformed")
        safe_string(item["prompt"], f"examples[{index}].prompt")
        string_list(item["expected_outcomes"], f"examples[{index}].expected_outcomes")
    string_list(package["proposed_tests"], "proposed_tests")
    string_list(package["known_limitations"], "known_limitations", allow_empty=True)
    if (
        not isinstance(attestations, dict)
        or set(attestations) != CONTRIBUTION_ATTESTATIONS
        or any(attestations[name] is not True for name in CONTRIBUTION_ATTESTATIONS)
    ):
        raise DiscoveryError("Contribution attestations are incomplete")
    if contains_secret(package) or contains_share_unsafe(package):
        raise DiscoveryError(
            "Contribution package contains a possible secret, URL, email, or absolute path"
        )
    return {
        "schema_version": 1,
        "valid": True,
        "candidate_name": candidate.get("name"),
        "classification": candidate.get("classification"),
        "evidence_count": len(evidence),
        "package_sha256": package["package_sha256"],
    }


def command_inventory(args: argparse.Namespace) -> dict[str, Any]:
    excluded = DEFAULT_EXCLUDED_DIRECTORIES | set(args.exclude_directory)
    return inventory(resolved(args.project_path), excluded)


def command_score(args: argparse.Namespace) -> dict[str, Any]:
    root = resolved(args.project_path)
    rules = inventory(root, DEFAULT_EXCLUDED_DIRECTORIES | set(args.exclude_directory))
    valid_blocks = {
        block["block_id"] for file in rules["files"] for block in file["blocks"]
    }
    candidates = normalize_candidate_input(load_json_input(args), valid_blocks)
    return score_candidates(candidates, rules, load_catalogs(root, args.catalog))


def command_export_contribution(args: argparse.Namespace) -> dict[str, Any]:
    report = load_json_file(args.report, "Candidate report")
    details = load_json_input(args, "Contribution details")
    return export_contribution(report, details, args.candidate)


def command_validate_contribution(args: argparse.Namespace) -> dict[str, Any]:
    return validate_contribution(load_json_input(args, "Contribution package"))


def write_explicit_output(args: argparse.Namespace, result: dict[str, Any]) -> None:
    if not getattr(args, "output", None):
        return
    output = resolved(args.output)
    project_value = getattr(args, "project_path", None)
    if project_value and is_within(output, resolved(project_value)):
        raise DiscoveryError("Output must stay outside the analyzed project")
    if not output.parent.is_dir():
        raise DiscoveryError(f"Output parent directory does not exist: {output.parent}")
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        dir=output.parent,
        prefix=f".{output.name}.",
        suffix=".tmp",
        delete=False,
    )
    temporary = Path(handle.name)
    try:
        with handle:
            json.dump(result, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Discover evidence-backed reusable skill candidates from local project rules"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    inventory_parser = subparsers.add_parser("inventory")
    inventory_parser.add_argument("--project-path", required=True)
    inventory_parser.add_argument("--exclude-directory", action="append", default=[])
    inventory_parser.add_argument("--json", action="store_true")
    score_parser = subparsers.add_parser("score")
    score_parser.add_argument("--project-path", required=True)
    source = score_parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input")
    source.add_argument("--stdin", action="store_true")
    score_parser.add_argument("--catalog", action="append", default=[])
    score_parser.add_argument("--exclude-directory", action="append", default=[])
    score_parser.add_argument("--output")
    score_parser.add_argument("--json", action="store_true")
    export_parser = subparsers.add_parser("export-contribution")
    export_parser.add_argument("--report", required=True)
    export_parser.add_argument("--candidate", required=True)
    export_source = export_parser.add_mutually_exclusive_group(required=True)
    export_source.add_argument("--input")
    export_source.add_argument("--stdin", action="store_true")
    export_parser.add_argument("--output")
    export_parser.add_argument("--json", action="store_true")
    validate_parser = subparsers.add_parser("validate-contribution")
    validate_source = validate_parser.add_mutually_exclusive_group(required=True)
    validate_source.add_argument("--input")
    validate_source.add_argument("--stdin", action="store_true")
    validate_parser.add_argument("--output")
    validate_parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        commands = {
            "inventory": command_inventory,
            "score": command_score,
            "export-contribution": command_export_contribution,
            "validate-contribution": command_validate_contribution,
        }
        result = commands[args.command](args)
        write_explicit_output(args, result)
        print(json.dumps(result, ensure_ascii=False, indent=2 if args.json else None, sort_keys=True))
        return 0
    except (DiscoveryError, OSError, ValueError) as error:
        payload = {"ok": False, "error": str(error)}
        if getattr(args, "json", False):
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        else:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
