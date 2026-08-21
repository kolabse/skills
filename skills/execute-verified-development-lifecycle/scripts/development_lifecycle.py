#!/usr/bin/env python3
"""Validate digest-bound development lifecycle plans and checkpoints.

This helper never performs lifecycle provider actions. Only configure/migrate,
explicitly confirmed rule installation, explicit state-file advancement, and
explicitly confirmed dependency install can write. Subprocesses use argv with
shell=False.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from typing import Any

sys.dont_write_bytecode = True


SKILL_ROOT = Path(__file__).resolve().parents[1]
CONFIG_REL = Path(".agents/execute-verified-development-lifecycle/config.json")
DEPENDENCIES = SKILL_ROOT / "references" / "dependencies.json"
ORDER = [
    "task-claimed", "feature-prepared", "tdd-red", "tdd-green", "changed-scope-preflight",
    "review-complete", "push-verified", "feature-published", "feature-pipeline",
    "documentation-ready", "development-integrated", "documentation-published",
    "production-delegated", "deployment-observed", "marker-observed",
    "smoke-passed", "documentation-complete", "cleanup-proved",
]
CAPABILITIES = {
    "task.claim", "scope.preflight", "scm.review", "scm.pipeline",
    "scm.integrate-development", "development.publish",
    "delivery.observe-deployment", "delivery.observe-marker", "delivery.observe-smoke",
}
START_MARKER = "<!-- execute-verified-development-lifecycle:start -->"
END_MARKER = "<!-- execute-verified-development-lifecycle:end -->"
RULE_BLOCK = f"""{START_MARKER}
## Verified development lifecycle

Use `$execute-verified-development-lifecycle` for changes governed by the
project-declared verified development lifecycle.
{END_MARKER}"""
SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")
REF_RE = re.compile(r"^(?![./])(?!.*(?:\.\.|//|@\{|\\))[A-Za-z0-9][A-Za-z0-9._/-]{0,254}(?<![./])$")
SECRET_RE = re.compile(r"(?i)(?:token|secret|password|passwd|api[_-]?key|private[_-]?key)\s*[:=]")
URL_RE = re.compile(r"(?i)\b(?:https?|ssh)://|\bgit@[^\s:]+:")

ASSERTIONS = {
    "task-claimed": {"task-identity-observed", "single-owner-confirmed"},
    "feature-prepared": {"feature-ref-created", "base-identity-matches", "no-edits-before-feature"},
    "tdd-red": {"relevant-test-failed", "failure-matches-missing-behavior"},
    "tdd-green": {"relevant-test-passed", "required-local-checks-passed"},
    "changed-scope-preflight": {"changed-scope-covered", "repository-rules-covered", "references-covered"},
    "review-complete": {"review-approved", "reviewed-commit-matches"},
    "push-verified": {"exact-state-verification-passed", "verified-commit-matches"},
    "feature-published": {"remote-feature-commit-matches"},
    "feature-pipeline": {"feature-pipeline-passed", "pipeline-commit-matches"},
    "documentation-ready": {"documentation-ready", "notification-dispositions-recorded"},
    "development-integrated": {"development-integration-observed", "integrated-commit-represented"},
    "documentation-published": {"documentation-published", "documentation-traceability-recorded"},
    "production-delegated": {"production-handoff-accepted", "development-identity-matches"},
    "deployment-observed": {"deployment-identity-observed", "development-identity-deployed"},
    "marker-observed": {"marker-identity-observed", "marker-matches-deployment"},
    "smoke-passed": {"smoke-checks-passed", "smoke-target-matches-deployment"},
    "documentation-complete": {"documentation-complete", "notification-outcomes-documented"},
    "cleanup-proved": {"cleanup-targets-enumerated", "upstream-representation-proved"},
}

SUBJECT_KINDS = {
    "task-claimed": {"task"}, "feature-prepared": {"ref", "commit"},
    "tdd-red": {"commit", "tree", "check-run"}, "tdd-green": {"commit", "tree", "check-run"},
    "changed-scope-preflight": {"commit", "tree"}, "review-complete": {"review-change", "commit"},
    "push-verified": {"commit", "tree"}, "feature-published": {"ref", "commit"},
    "feature-pipeline": {"pipeline", "commit"}, "documentation-ready": {"documentation", "notification"},
    "development-integrated": {"development-integration", "commit"}, "documentation-published": {"documentation"},
    "production-delegated": {"production-handoff", "development-integration"}, "deployment-observed": {"deployment", "development-integration"},
    "marker-observed": {"marker", "deployment"}, "smoke-passed": {"smoke-run", "deployment"},
    "documentation-complete": {"documentation", "notification"}, "cleanup-proved": {"cleanup-resource", "durable-target"},
}
SOURCE_CHECKPOINTS = {
    "feature-prepared", "tdd-red", "tdd-green", "changed-scope-preflight",
    "review-complete", "push-verified", "feature-published", "feature-pipeline",
}
FUTURE_SKEW_SECONDS = 300


class LifecycleError(Exception):
    def __init__(self, message: str, *, mutates_environment: bool = False):
        super().__init__(message)
        self.mutates_environment = mutates_environment


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(value: Any, field: str | None = None) -> str:
    if field and isinstance(value, dict):
        value = {k: v for k, v in value.items() if k != field}
    return hashlib.sha256(canonical(value)).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LifecycleError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise LifecycleError(f"expected JSON object: {path}")
    return data


def atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def unique_ids(items: list[dict[str, Any]], label: str) -> list[str]:
    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
        raise LifecycleError(f"{label} must be an array of objects")
    ids = [str(item.get("id", item.get("name", ""))) for item in items]
    if not ids or any(not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", item) for item in ids) or len(ids) != len(set(ids)):
        raise LifecycleError(f"{label} must contain unique non-empty ids")
    return ids


def exact_keys(value: dict[str, Any], required: set[str], label: str) -> None:
    if not isinstance(value, dict):
        raise LifecycleError(f"{label} must be an object")
    missing, extra = sorted(required - value.keys()), sorted(value.keys() - required)
    if missing or extra:
        raise LifecycleError(f"{label} fields invalid; missing={missing}, extra={extra}")


def safe_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 300:
        raise LifecycleError(f"{label} must be a non-empty relative path")
    candidate = Path(value)
    if candidate.is_absolute() or candidate.drive or ".." in candidate.parts:
        raise LifecycleError(f"{label} must not be absolute or escape its root")
    return value


def reject_sensitive(value: Any, label: str = "configuration") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if re.search(r"(?i)(token|secret|password|passwd|api[_-]?key|private[_-]?key)", str(key)):
                raise LifecycleError(f"{label} contains a secret-like field")
            reject_sensitive(item, label)
    elif isinstance(value, list):
        for item in value:
            reject_sensitive(item, label)
    elif isinstance(value, str) and (URL_RE.search(value) or SECRET_RE.search(value)):
        raise LifecycleError(f"{label} contains a URL or secret-like value")


def validate_config(config: dict[str, Any]) -> None:
    required = {"version", "repositories", "rules", "references", "checks", "gates", "adapters", "required_capabilities", "notifications", "documentation", "integration", "production", "delivery", "cleanup"}
    exact_keys(config, required, "configuration")
    reject_sensitive(config)
    if config["version"] != 1:
        raise LifecycleError(f"unsupported configuration version: {config['version']!r}")
    if not all(isinstance(config[key], list) for key in ("repositories", "rules", "references", "checks", "gates", "adapters", "required_capabilities", "notifications", "documentation")):
        raise LifecycleError("configured collections must be arrays")
    repos = unique_ids(config["repositories"], "repositories")
    for item in config["repositories"]:
        exact_keys(item, {"name", "path", "base_ref", "require_clean", "require_upstream_current"}, f"repository {item.get('name')}")
        safe_path(item["path"], "repository.path")
        if not REF_RE.fullmatch(str(item["base_ref"])):
            raise LifecycleError("repository.base_ref is invalid")
        if item["require_clean"] is not True or item["require_upstream_current"] is not True:
            raise LifecycleError("version-1 repositories require clean and upstream-current state")
    unique_ids(config["rules"], "rules")
    unique_ids(config["references"], "references")
    unique_ids(config["checks"], "checks")
    unique_ids(config["notifications"], "notifications") if config["notifications"] else []
    unique_ids(config["documentation"], "documentation")
    for key in ("rules", "references", "notifications", "documentation"):
        for item in config[key]:
            exact_keys(item, {"id", "path"}, f"{key} declaration")
            safe_path(item["path"], f"{key}.path")
    for item in config["checks"]:
        exact_keys(item, {"id", "phase", "required"}, "check")
        if item["phase"] not in {"red", "green", "preflight", "feature-pipeline", "smoke"} or not isinstance(item["required"], bool):
            raise LifecycleError("check phase/required is invalid")
    gate_ids = unique_ids(config["gates"], "gates")
    if set(gate_ids) != set(ORDER) or len(gate_ids) != len(ORDER):
        raise LifecycleError("gates must declare each version-1 lifecycle checkpoint exactly once")
    for item in config["gates"]:
        exact_keys(item, {"id", "required", "failure_rewind"}, "gate")
        if not isinstance(item["required"], bool) or item["failure_rewind"] not in ORDER:
            raise LifecycleError("gate required/failure_rewind is invalid")
        if ORDER.index(item["failure_rewind"]) > ORDER.index(item["id"]):
            raise LifecycleError(f"gate {item['id']} failure_rewind must be the same or earlier checkpoint")
    adapter_ids = unique_ids(config["adapters"], "adapters")
    del adapter_ids
    provided: set[str] = set()
    for item in config["adapters"]:
        exact_keys(item, {"id", "kind", "capabilities"}, "adapter")
        caps = item["capabilities"]
        if not isinstance(caps, list) or not caps or len(caps) != len(set(caps)) or not set(caps) <= CAPABILITIES:
            raise LifecycleError(f"adapter {item['id']} has invalid capabilities")
        provided.update(caps)
    required_caps = config["required_capabilities"]
    if len(required_caps) != len(set(required_caps)) or not set(required_caps) <= CAPABILITIES:
        raise LifecycleError("required_capabilities contains invalid values")
    missing_caps = sorted(set(required_caps) - provided)
    if missing_caps:
        raise LifecycleError(f"required capabilities have no configured adapter: {', '.join(missing_caps)}")
    exact_keys(config["integration"], {"development_repository", "development_ref", "review_required"}, "integration")
    if config["integration"].get("development_repository") not in repos:
        raise LifecycleError("integration.development_repository is not configured")
    if not REF_RE.fullmatch(str(config["integration"]["development_ref"])) or config["integration"]["review_required"] is not True:
        raise LifecycleError("integration development_ref/review_required is invalid")
    exact_keys(config["production"], {"delegated", "route_label"}, "production")
    if config["production"].get("delegated") is not True:
        raise LifecycleError("production must be delegated")
    exact_keys(config["delivery"], {"deployment_required", "marker_required", "smoke_required"}, "delivery")
    if not all(isinstance(config["delivery"][key], bool) for key in config["delivery"]):
        raise LifecycleError("delivery requirements must be boolean")
    exact_keys(config["cleanup"], {"proof_methods"}, "cleanup")
    methods = config["cleanup"].get("proof_methods", [])
    if not methods or len(methods) != len(set(methods)) or not set(methods) <= {"merged", "identical-tree", "patch-equivalent", "provider-representation"}:
        raise LifecycleError("cleanup.proof_methods must not be empty")


def project_config(root: Path) -> Path:
    return root.resolve() / CONFIG_REL


def load_config(root: Path) -> tuple[dict[str, Any], str]:
    config = read_json(project_config(root))
    validate_config(config)
    return config, digest(config)


def inspect_rule_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "status": "missing", "installed": False}
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise LifecycleError(f"cannot read repository rules {path}: {exc}") from exc
    starts, ends = content.count(START_MARKER), content.count(END_MARKER)
    if starts != ends or starts > 1:
        return {"path": str(path), "status": "malformed-markers", "installed": False}
    if starts == 0:
        return {"path": str(path), "status": "missing-reference", "installed": False}
    start, end_start = content.index(START_MARKER), content.index(END_MARKER)
    if end_start < start:
        return {"path": str(path), "status": "malformed-markers", "installed": False}
    end = end_start + len(END_MARKER)
    installed = content[start:end].replace("\r\n", "\n") == RULE_BLOCK
    return {"path": str(path), "status": "installed" if installed else "stale-managed-block", "installed": installed}


def rule_statuses(root: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for repo in config["repositories"]:
        repo_root = (root.resolve() / repo["path"]).resolve()
        if root.resolve() not in (repo_root, *repo_root.parents):
            raise LifecycleError(f"repository path escapes project root: {repo['path']}")
        item = inspect_rule_file(repo_root / "AGENTS.md")
        item["repository"] = repo["name"]
        results.append(item)
    return results


def path_has_symlink(path: Path, boundary: Path) -> bool:
    current = path.absolute()
    boundary = boundary.absolute()
    while True:
        if current.exists() and current.is_symlink():
            return True
        if current == boundary:
            return False
        if boundary not in current.parents:
            return True
        current = current.parent


def run_git(repo: Path, argv: list[str]) -> str:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(["git", "-C", str(repo), *argv], shell=False, check=False, capture_output=True, text=True, env=env)
    if completed.returncode:
        detail = (completed.stderr or completed.stdout).strip().splitlines()
        raise LifecycleError(f"git {' '.join(argv)} failed for {repo}: {detail[-1] if detail else completed.returncode}")
    return completed.stdout.strip()


def inspect_git_repository(root: Path, configured: dict[str, Any], supplied: dict[str, Any]) -> dict[str, Any]:
    lexical = root.absolute() / configured["path"]
    repo = lexical.resolve()
    if root.resolve() not in (repo, *repo.parents) or path_has_symlink(lexical, root.absolute()):
        raise LifecycleError(f"repository {configured['name']} escapes through an absolute or symlinked path")
    if not repo.is_dir():
        raise LifecycleError(f"repository {configured['name']} root does not exist")
    top = Path(run_git(repo, ["rev-parse", "--show-toplevel"])).resolve()
    if top != repo:
        raise LifecycleError(f"repository {configured['name']} path is not the exact Git root")
    git_dir_text = run_git(repo, ["rev-parse", "--git-dir"])
    git_dir = (repo / git_dir_text).resolve() if not Path(git_dir_text).is_absolute() else Path(git_dir_text).resolve()
    in_progress = [name for name in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply", "BISECT_LOG") if (git_dir / name).exists()]
    if in_progress:
        raise LifecycleError(f"repository {configured['name']} has an operation in progress: {', '.join(in_progress)}")
    branch = run_git(repo, ["symbolic-ref", "--quiet", "--short", "HEAD"])
    status = run_git(repo, ["status", "--porcelain=v1", "--untracked-files=all"])
    if status:
        raise LifecycleError(f"repository {configured['name']} is not clean")
    head = run_git(repo, ["rev-parse", "HEAD^{commit}"])
    base = run_git(repo, ["rev-parse", f"{configured['base_ref']}^{{commit}}"])
    upstream = run_git(repo, ["rev-parse", "@{upstream}^{commit}"])
    supplied_start, supplied_upstream = str(supplied.get("start_commit", "")), str(supplied.get("upstream_commit", ""))
    if len({head, base, upstream, supplied_start, supplied_upstream}) != 1:
        raise LifecycleError(f"repository {configured['name']} HEAD/base/upstream/supplied identities do not match")
    return {"name": configured["name"], "root": str(repo), "branch": branch, "head": head, "base": base, "upstream": upstream, "clean": True, "current": True}


def inspect_declared_files(root: Path, config: dict[str, Any]) -> list[dict[str, str]]:
    boundaries = [root.resolve(), *[(root.resolve() / item["path"]).resolve() for item in config["repositories"]]]
    observed: list[dict[str, str]] = []
    for category in ("rules", "references"):
        for declaration in config[category]:
            matches: list[Path] = []
            for boundary in boundaries:
                lexical = boundary / declaration["path"]
                resolved = lexical.resolve()
                if boundary not in (resolved, *resolved.parents):
                    continue
                if lexical.exists() and not path_has_symlink(lexical, boundary) and resolved.is_file() and not resolved.is_symlink():
                    matches.append(resolved)
            if not matches:
                raise LifecycleError(f"declared {category} file {declaration['id']} is missing, non-regular, symlinked, or outside its boundary")
            observed.append({"category": category, "id": declaration["id"], "status": "regular-file"})
    return observed


def cmd_rules_status(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.project_root)
    config, config_hash = load_config(root)
    repositories = rule_statuses(root, config)
    return {"mode": "rules-status", "config_sha256": config_hash, "repositories": repositories, "passed": all(x["installed"] for x in repositories), "mutates_repository": False}


def cmd_configure_rules(args: argparse.Namespace) -> dict[str, Any]:
    if not args.apply or not args.yes:
        raise LifecycleError("rule configuration requires both --apply and --yes")
    root = Path(args.project_root)
    config, config_hash = load_config(root)
    before = rule_statuses(root, config)
    malformed = [x["repository"] for x in before if x["status"] == "malformed-markers"]
    if malformed:
        raise LifecycleError(f"malformed or duplicate managed markers: {', '.join(malformed)}")
    changed: list[str] = []
    for item in before:
        if item["installed"]:
            continue
        path = Path(item["path"])
        content = path.read_text(encoding="utf-8") if path.exists() else ""
        if START_MARKER in content:
            start, end = content.index(START_MARKER), content.index(END_MARKER) + len(END_MARKER)
            content = content[:start] + RULE_BLOCK + content[end:]
        else:
            content = content.rstrip() + ("\n\n" if content.strip() else "") + RULE_BLOCK + "\n"
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
            os.replace(name, path)
        finally:
            if os.path.exists(name):
                os.unlink(name)
        changed.append(item["repository"])
    after = rule_statuses(root, config)
    if not all(x["installed"] for x in after):
        raise LifecycleError("managed rule reference did not validate after configuration")
    return {"mode": "configure-rules", "config_sha256": config_hash, "changed_repositories": changed, "repositories": after, "passed": True, "mutates_repository": bool(changed)}


def ensure_external(path: Path, config: dict[str, Any], root: Path) -> None:
    resolved = path.resolve()
    roots = [(root.resolve() / repo["path"]).resolve() for repo in config["repositories"]]
    if any(resolved == item or item in resolved.parents for item in roots):
        raise LifecycleError(f"artifact must be outside configured repositories: {resolved}")


def verify_retained_evidence(root: Path, config: dict[str, Any], checkpoint: dict[str, Any]) -> None:
    evidence_path = Path(checkpoint["evidence_ref"])
    if not evidence_path.is_absolute():
        evidence_path = root.resolve() / evidence_path
    lexical = evidence_path.absolute()
    if not lexical.exists() or not lexical.is_file() or lexical.is_symlink():
        raise LifecycleError("evidence_ref must identify a regular non-symlink JSON file outside configured repositories")
    resolved = lexical.resolve()
    ensure_external(resolved, config, root)
    evidence = read_json(resolved)
    exact_keys(evidence, {"schema_version", "plan_sha256", "config_sha256", "checkpoint", "observed_at", "subjects", "assertions", "producer", "artifact_sha256"}, "retained evidence")
    reject_sensitive(evidence, "retained evidence")
    if evidence["schema_version"] != 1 or evidence["plan_sha256"] != checkpoint["plan_sha256"] or evidence["config_sha256"] != checkpoint["config_sha256"] or evidence["checkpoint"] != checkpoint["checkpoint"]:
        raise LifecycleError("retained evidence plan/config/checkpoint binding does not match envelope")
    if evidence["observed_at"] != checkpoint["observed_at"] or canonical(evidence["subjects"]) != canonical(checkpoint["subjects"]) or canonical(evidence["assertions"]) != canonical(checkpoint["assertions"]):
        raise LifecycleError("retained evidence timestamp, subjects, or assertions do not match envelope")
    if not isinstance(evidence["producer"], str) or not evidence["producer"] or not SHA_RE.fullmatch(str(evidence["artifact_sha256"])) or len(evidence["artifact_sha256"]) != 64:
        raise LifecycleError("retained evidence producer/artifact digest is malformed")
    if digest(evidence) != checkpoint["evidence_sha256"]:
        raise LifecycleError("retained evidence canonical digest does not match evidence_sha256")


def check_hash(document: dict[str, Any], field: str) -> None:
    if document.get(field) != digest(document, field):
        raise LifecycleError(f"{field} does not match document content")


def gate_map(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in config["gates"]}


def enabled_order(config: dict[str, Any]) -> list[str]:
    gates = gate_map(config)
    delivery = config["delivery"]
    disabled_by_delivery = {
        "deployment-observed": not delivery["deployment_required"],
        "marker-observed": not delivery["marker_required"],
        "smoke-passed": not delivery["smoke_required"],
    }
    return [name for name in ORDER if gates[name]["required"] or not disabled_by_delivery.get(name, False)]


def output(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")


def cmd_configure(args: argparse.Namespace) -> dict[str, Any]:
    root, source = Path(args.project_root), Path(args.config_source)
    config = read_json(source)
    validate_config(config)
    destination = project_config(root)
    if destination.exists() and read_json(destination) != config:
        raise LifecycleError("configuration exists with different content; use migrate for supported changes")
    atomic_write(destination, config)
    return {"mode": "configure", "configured": True, "config_path": str(destination), "config_sha256": digest(config), "mutates_repository": True}


def cmd_status(args: argparse.Namespace) -> dict[str, Any]:
    config, config_hash = load_config(Path(args.project_root))
    return {"mode": "status", "configured": True, "version": config["version"], "config_path": str(project_config(Path(args.project_root))), "config_sha256": config_hash, "repositories": [x["name"] for x in config["repositories"]], "gates": enabled_order(config), "adapters": [x["id"] for x in config["adapters"]], "required_capabilities": config["required_capabilities"], "mutates_repository": False}


def cmd_migrate(args: argparse.Namespace) -> dict[str, Any]:
    config, config_hash = load_config(Path(args.project_root))
    return {"mode": "migrate", "version": config["version"], "changed": False, "config_sha256": config_hash, "mutates_repository": False}


def declared(config: dict[str, Any], key: str) -> list[str]:
    return [str(x.get("id", x.get("name"))) for x in config[key]]


def require_exact(label: str, actual: list[str], expected: list[str], blockers: list[str]) -> None:
    if set(actual) != set(expected) or len(actual) != len(set(actual)):
        blockers.append(f"{label} coverage must equal configured declarations")


def cmd_plan(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.project_root)
    config, config_hash = load_config(root)
    data = read_json(Path(args.input))
    exact_keys(data, {"lifecycle_id", "outcome", "feature_ref", "changed_scope", "repositories", "rules_read", "references_read", "documentation_targets", "notifications"}, "plan input")
    reject_sensitive(data, "plan input")
    blockers: list[str] = []
    if not isinstance(data["lifecycle_id"], str) or not data["lifecycle_id"].strip() or not isinstance(data["outcome"], str) or not data["outcome"].strip():
        blockers.append("lifecycle_id and outcome must be non-empty")
    if not isinstance(data["feature_ref"], str) or not REF_RE.fullmatch(data["feature_ref"]):
        blockers.append("feature_ref is invalid")
    require_exact("repository", [x.get("name", "") for x in data.get("repositories", [])], declared(config, "repositories"), blockers)
    require_exact("rule", data.get("rules_read", []), declared(config, "rules"), blockers)
    require_exact("reference", data.get("references_read", []), declared(config, "references"), blockers)
    require_exact("documentation", data.get("documentation_targets", []), declared(config, "documentation"), blockers)
    require_exact("notification", data.get("notifications", []), declared(config, "notifications"), blockers)
    supplied_by_name = {item.get("name"): item for item in data.get("repositories", []) if isinstance(item, dict)}
    repository_observations: list[dict[str, Any]] = []
    for configured_repo in config["repositories"]:
        repo = supplied_by_name.get(configured_repo["name"], {})
        try:
            exact_keys(repo, {"name", "start_commit", "upstream_commit", "clean", "current"}, "plan repository")
        except LifecycleError as exc:
            blockers.append(str(exc)); continue
        if not SHA_RE.fullmatch(str(repo.get("start_commit", ""))) or not SHA_RE.fullmatch(str(repo.get("upstream_commit", ""))):
            blockers.append(f"repository {repo.get('name', '?')} has invalid commit identity")
            continue
        try:
            observed = inspect_git_repository(root.resolve(), configured_repo, repo)
            repository_observations.append({k: v for k, v in observed.items() if k != "root"})
        except LifecycleError as exc:
            blockers.append(str(exc))
    if not isinstance(data.get("changed_scope"), list) or not data.get("changed_scope"):
        blockers.append("changed_scope must not be empty")
    else:
        for path in data["changed_scope"]:
            try:
                safe_path(path, "changed_scope path")
            except LifecycleError as exc:
                blockers.append(str(exc))
    installations = rule_statuses(root, config)
    for item in installations:
        if not item["installed"]:
            blockers.append(f"repository {item['repository']} lacks the managed lifecycle rule reference ({item['status']})")
    try:
        declared_files = inspect_declared_files(root, config)
    except LifecycleError as exc:
        declared_files = []
        blockers.append(str(exc))
    plan = {
        "schema_version": 1, "mode": "plan", "lifecycle_id": data.get("lifecycle_id", ""), "outcome": data.get("outcome", ""),
        "config_sha256": config_hash, "feature_ref": data.get("feature_ref", ""), "changed_scope": data.get("changed_scope", []),
        "repositories": repository_observations, "rules": declared(config, "rules"), "rule_installations": [{"repository": x["repository"], "status": x["status"], "installed": x["installed"]} for x in installations], "references": declared(config, "references"), "declared_files": declared_files,
        "checks": config["checks"], "gates": config["gates"], "adapters": config["adapters"], "required_capabilities": config["required_capabilities"], "documentation_targets": declared(config, "documentation"),
        "notifications": declared(config, "notifications"), "integration": config["integration"], "production": config["production"],
        "delivery": config["delivery"], "cleanup": config["cleanup"],
        "reminders": ["Prepare feature ref before the first edit", "Complete declared documentation readiness and completion gates", "Record every declared notification disposition", "Production execution is delegated; record only observed handoff and delivery evidence"],
        "blockers": blockers, "ready": not blockers, "mutates_repository": False,
    }
    plan["plan_sha256"] = digest(plan)
    out_path, state_path = Path(args.output), Path(args.state_output)
    ensure_external(out_path, config, root); ensure_external(state_path, config, root)
    atomic_write(out_path, plan)
    state = {"schema_version": 1, "mode": "state", "lifecycle_id": plan["lifecycle_id"], "plan_sha256": plan["plan_sha256"], "config_sha256": config_hash, "current_checkpoint": None, "attempts": {}, "completed": {}, "history": [], "failed": False, "complete": False, "mutates_repository": False}
    state["state_sha256"] = digest(state)
    atomic_write(state_path, state)
    return plan


def validate_state_invariants(config: dict[str, Any], plan: dict[str, Any], state: dict[str, Any]) -> None:
    exact_keys(state, {"schema_version", "mode", "lifecycle_id", "plan_sha256", "config_sha256", "current_checkpoint", "attempts", "completed", "history", "failed", "complete", "mutates_repository", "state_sha256"}, "state")
    if state["schema_version"] != 1 or state["mode"] != "state" or state["mutates_repository"] is not False:
        raise LifecycleError("state metadata is malformed")
    if state["lifecycle_id"] != plan.get("lifecycle_id") or state["plan_sha256"] != plan.get("plan_sha256") or state["config_sha256"] != plan.get("config_sha256"):
        raise LifecycleError("state identity binding does not match plan")
    if not isinstance(state["attempts"], dict) or not isinstance(state["completed"], dict) or not isinstance(state["history"], list) or not isinstance(state["failed"], bool) or not isinstance(state["complete"], bool):
        raise LifecycleError("state collections or flags are malformed")
    active = enabled_order(config)
    completed_names = active[:len(state["completed"])]
    if set(state["completed"]) != set(completed_names):
        raise LifecycleError("completed checkpoints are not an ordered lifecycle prefix")
    counts: dict[str, int] = {}
    expected_attempts: dict[str, int] = {}
    for entry in state["history"]:
        if not isinstance(entry, dict) or entry.get("checkpoint") not in ORDER or entry.get("status") not in {"passed", "failed", "not-required"}:
            raise LifecycleError("state history contains a malformed checkpoint entry")
        name = entry["checkpoint"]
        counts[name] = counts.get(name, 0) + 1
        if entry.get("attempt") != counts[name]:
            raise LifecycleError(f"state history attempt sequence is invalid for {name}")
        expected_attempts[name] = counts[name]
    if state["attempts"] != expected_attempts:
        raise LifecycleError("state attempts do not match history")
    for name, entry in state["completed"].items():
        if not isinstance(entry, dict) or entry.get("checkpoint") != name or entry.get("status") not in {"passed", "not-required"} or not any(canonical(entry) == canonical(item) for item in state["history"]):
            raise LifecycleError(f"completed checkpoint {name} is forged or absent from history")
    expected_current = completed_names[-1] if completed_names else None
    if state["current_checkpoint"] != expected_current:
        raise LifecycleError("current_checkpoint does not match completed prefix")
    expected_failed = bool(state["history"] and state["history"][-1].get("status") == "failed")
    if state["failed"] != expected_failed:
        raise LifecycleError("failed flag does not match final history entry")
    expected_complete = len(completed_names) == len(active) and not expected_failed
    if state["complete"] != expected_complete:
        raise LifecycleError("complete flag does not match lifecycle state")


def load_bound(root: Path, plan_path: Path, state_path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    config, config_hash = load_config(root)
    plan, state = read_json(plan_path), read_json(state_path)
    check_hash(plan, "plan_sha256"); check_hash(state, "state_sha256")
    if plan.get("config_sha256") != config_hash or state.get("config_sha256") != config_hash:
        raise LifecycleError("configuration changed after planning")
    if state.get("plan_sha256") != plan.get("plan_sha256"):
        raise LifecycleError("state is bound to another plan")
    if not plan.get("ready"):
        raise LifecycleError("plan contains blockers")
    validate_state_invariants(config, plan, state)
    return config, plan, state


def checkpoint_coverage(config: dict[str, Any], checkpoint: dict[str, Any]) -> None:
    coverage = checkpoint.get("coverage", {})
    exact_keys(coverage, {"repositories", "rules", "references", "checks", "documentation", "notifications"}, "checkpoint coverage")
    for key, values in coverage.items():
        if not isinstance(values, list) or len(values) != len(set(values)) or any(not isinstance(x, str) for x in values):
            raise LifecycleError(f"checkpoint coverage {key} must contain unique string ids")
    if checkpoint["checkpoint"] != "changed-scope-preflight":
        return
    expected = {"repositories": declared(config, "repositories"), "rules": declared(config, "rules"), "references": declared(config, "references"), "checks": declared(config, "checks"), "documentation": declared(config, "documentation"), "notifications": declared(config, "notifications")}
    for key, values in expected.items():
        if set(coverage.get(key, [])) != set(values):
            raise LifecycleError(f"changed-scope-preflight missing exact {key} coverage")


def cmd_advance(args: argparse.Namespace) -> dict[str, Any]:
    root, state_path = Path(args.project_root), Path(args.state)
    config, plan, state = load_bound(root, Path(args.plan), state_path)
    checkpoint = read_json(Path(args.checkpoint))
    exact_keys(checkpoint, {"schema_version", "plan_sha256", "config_sha256", "checkpoint", "attempt", "status", "observed_at", "subjects", "assertions", "coverage", "evidence_sha256", "evidence_ref", "rewind_to"}, "checkpoint")
    reject_sensitive(checkpoint, "checkpoint")
    if checkpoint.get("schema_version") != 1:
        raise LifecycleError("unsupported checkpoint schema_version")
    try:
        observed = datetime.fromisoformat(str(checkpoint.get("observed_at", "")).replace("Z", "+00:00"))
    except ValueError as exc:
        raise LifecycleError("checkpoint observed_at must be an ISO-8601 timestamp") from exc
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise LifecycleError("checkpoint observed_at must include a timezone")
    if (observed.astimezone(timezone.utc) - datetime.now(timezone.utc)).total_seconds() > FUTURE_SKEW_SECONDS:
        raise LifecycleError("checkpoint observed_at is too far in the future")
    name, status = checkpoint.get("checkpoint"), checkpoint.get("status")
    if name not in ORDER:
        raise LifecycleError(f"unknown checkpoint: {name!r}")
    if checkpoint.get("plan_sha256") != plan["plan_sha256"] or checkpoint.get("config_sha256") != plan["config_sha256"]:
        raise LifecycleError("checkpoint digest binding does not match plan/configuration")
    expected_attempt = state["attempts"].get(name, 0) + 1
    if checkpoint.get("attempt") != expected_attempt:
        raise LifecycleError(f"checkpoint attempt must be {expected_attempt}")
    if not SHA_RE.fullmatch(str(checkpoint.get("evidence_sha256", ""))) or len(checkpoint["evidence_sha256"]) != 64:
        raise LifecycleError("checkpoint evidence_sha256 must be 64 lowercase hexadecimal characters")
    if not checkpoint.get("subjects") or not checkpoint.get("assertions") or not checkpoint.get("evidence_ref"):
        raise LifecycleError("checkpoint requires subjects, assertions, and an evidence reference")
    if not isinstance(checkpoint["evidence_ref"], str) or len(checkpoint["evidence_ref"]) > 200:
        raise LifecycleError("checkpoint evidence_ref is invalid")
    assertion_names: set[str] = set()
    for item in checkpoint["assertions"]:
        exact_keys(item, {"name", "passed"}, "checkpoint assertion")
        if not isinstance(item["name"], str) or not isinstance(item["passed"], bool):
            raise LifecycleError("checkpoint assertion is malformed")
        assertion_names.add(item["name"])
    expected_assertions = {"not-required-by-config"} if status == "not-required" else ASSERTIONS[name]
    missing_assertions = sorted(expected_assertions - assertion_names)
    if missing_assertions or assertion_names != expected_assertions:
        raise LifecycleError(f"checkpoint {name} assertions must exactly equal: {', '.join(sorted(expected_assertions))}")
    seen_kinds: set[str] = set()
    for subject in checkpoint["subjects"]:
        exact_keys(subject, {"kind", "role", "repository", "identity"}, "checkpoint subject")
        kind, identity = subject["kind"], subject["identity"]
        if kind not in SUBJECT_KINDS[name]:
            raise LifecycleError(f"subject kind {kind!r} is not valid for checkpoint {name}")
        repository = subject["repository"]
        if repository is not None and repository not in declared(config, "repositories"):
            raise LifecycleError(f"checkpoint subject repository {repository!r} is not configured")
        if not isinstance(subject["role"], str) or not subject["role"] or not isinstance(identity, str) or not identity:
            raise LifecycleError("checkpoint subject role/identity is invalid")
        if kind in {"commit", "tree"} and not SHA_RE.fullmatch(identity):
            raise LifecycleError(f"subject {kind} identity is not a commit-like SHA")
        if kind == "ref" and not REF_RE.fullmatch(identity):
            raise LifecycleError("subject ref identity is invalid")
        seen_kinds.add(kind)
    missing_kinds = sorted(SUBJECT_KINDS[name] - seen_kinds)
    if missing_kinds:
        raise LifecycleError(f"checkpoint {name} missing bound subject kinds: {', '.join(missing_kinds)}")
    if name in SOURCE_CHECKPOINTS:
        covered_repositories = {x["repository"] for x in checkpoint["subjects"] if x["repository"] is not None}
        missing_repositories = sorted(set(declared(config, "repositories")) - covered_repositories)
        if missing_repositories:
            raise LifecycleError(f"checkpoint {name} lacks subject identity for repositories: {', '.join(missing_repositories)}")
    def identities(document: dict[str, Any], kind: str) -> set[str]:
        return {x["identity"] for x in document.get("subjects", []) if x.get("kind") == kind}
    green = state["completed"].get("tdd-green")
    if green and name in {"review-complete", "push-verified", "feature-published", "feature-pipeline"}:
        if identities(checkpoint, "commit") != identities(green, "commit"):
            raise LifecycleError(f"checkpoint {name} commit does not match tdd-green commit")
    development = state["completed"].get("development-integrated")
    if development and name in {"production-delegated", "deployment-observed"}:
        if identities(checkpoint, "development-integration") != identities(development, "development-integration"):
            raise LifecycleError(f"checkpoint {name} does not match development integration identity")
    production = state["completed"].get("production-delegated")
    if production and name == "deployment-observed":
        if identities(checkpoint, "development-integration") != identities(production, "development-integration"):
            raise LifecycleError("deployment does not match production handoff development identity")
    deployment = state["completed"].get("deployment-observed")
    if deployment and name in {"marker-observed", "smoke-passed"}:
        if identities(checkpoint, "deployment") != identities(deployment, "deployment"):
            raise LifecycleError(f"checkpoint {name} does not match observed deployment identity")
    failed_assertions = [item for item in checkpoint["assertions"] if not item["passed"]]
    required = gate_map(config)[name]["required"]
    if status == "passed" and failed_assertions:
        raise LifecycleError("passed checkpoint requires every assertion to pass")
    if status == "failed" and not failed_assertions:
        raise LifecycleError("failed checkpoint requires at least one failed assertion")
    if status == "not-required" and (required or any(not item["passed"] for item in checkpoint["assertions"])):
        raise LifecycleError("not-required is valid only for an optional gate with a passed not-required-by-config assertion")
    verify_retained_evidence(root, config, checkpoint)
    active = enabled_order(config)
    remaining = [item for item in active if item not in state["completed"]]
    if not remaining or name != remaining[0]:
        raise LifecycleError(f"expected checkpoint {remaining[0] if remaining else 'none'}, received {name}")
    if status in {"passed", "not-required"}:
        if status == "not-required" and required:
            raise LifecycleError("required checkpoint cannot be not-required")
        if checkpoint.get("rewind_to") is not None:
            raise LifecycleError("successful checkpoint cannot request rewind")
        checkpoint_coverage(config, checkpoint)
        state["completed"][name] = checkpoint
        state["current_checkpoint"] = name
        state["failed"] = False
    elif status == "failed":
        checkpoint_coverage(config, checkpoint)
        rewind = checkpoint.get("rewind_to")
        configured = gate_map(config)[name]["failure_rewind"]
        if rewind != configured:
            raise LifecycleError(f"failure rewind must be configured target {configured}")
        start = ORDER.index(rewind)
        state["completed"] = {k: v for k, v in state["completed"].items() if ORDER.index(k) < start}
        state["current_checkpoint"] = ORDER[start - 1] if start else None
        state["failed"] = True
    else:
        raise LifecycleError("checkpoint status must be passed, failed, or not-required")
    state["attempts"][name] = expected_attempt
    state["history"].append(checkpoint)
    state["complete"] = all(item in state["completed"] for item in active) and not state["failed"]
    state["state_sha256"] = digest(state, "state_sha256")
    ensure_external(state_path, config, root)
    atomic_write(state_path, state)
    return {"mode": "advance", "checkpoint": name, "status": status, "current_checkpoint": state["current_checkpoint"], "complete": state["complete"], "state_sha256": state["state_sha256"], "mutates_repository": False}


def replay_and_validate_state(root: Path, config: dict[str, Any], plan: dict[str, Any], state: dict[str, Any]) -> None:
    initial = {"schema_version": 1, "mode": "state", "lifecycle_id": plan["lifecycle_id"], "plan_sha256": plan["plan_sha256"], "config_sha256": plan["config_sha256"], "current_checkpoint": None, "attempts": {}, "completed": {}, "history": [], "failed": False, "complete": False, "mutates_repository": False}
    initial["state_sha256"] = digest(initial)
    with tempfile.TemporaryDirectory(prefix="verified-lifecycle-replay-") as directory:
        temporary = Path(directory)
        plan_path, state_path, checkpoint_path = temporary / "plan.json", temporary / "state.json", temporary / "checkpoint.json"
        atomic_write(plan_path, plan)
        atomic_write(state_path, initial)
        for checkpoint in state["history"]:
            atomic_write(checkpoint_path, checkpoint)
            cmd_advance(SimpleNamespace(project_root=str(root), plan=str(plan_path), state=str(state_path), checkpoint=str(checkpoint_path)))
        replayed = read_json(state_path)
    if canonical(replayed) != canonical(state):
        raise LifecycleError("state does not equal deterministic replay of its checkpoint history")


def cmd_verify(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.project_root)
    config, plan, state = load_bound(root, Path(args.plan), Path(args.state))
    replay_and_validate_state(root, config, plan, state)
    active = enabled_order(config)
    missing = [item for item in active if item not in state["completed"]]
    blockers = (["lifecycle is in a failed rewind loop"] if state["failed"] else []) + [f"missing checkpoint: {x}" for x in missing]
    result = {"schema_version": 1, "mode": "verify", "lifecycle_id": plan["lifecycle_id"], "plan_sha256": plan["plan_sha256"], "current_checkpoint": state["current_checkpoint"], "completed_checkpoints": [x for x in active if x in state["completed"]], "missing_checkpoints": missing, "production_delegated": "production-delegated" in state["completed"], "blockers": blockers, "passed": not blockers, "mutates_repository": False}
    result["report_sha256"] = digest(result)
    return result


def cmd_dependencies(args: argparse.Namespace) -> dict[str, Any]:
    manifest = read_json(DEPENDENCIES)
    selected = manifest["required"] + (manifest["integrations"] if args.include_integrations else [])
    argv = ["npx", "--yes", f"skills@{manifest['cli_version']}", "add", manifest["source"]]
    for name in selected:
        argv.extend(["--skill", name])
    argv.extend(["--agent", "codex", "--copy", "-y"])
    result = {"mode": "dependencies", "required": manifest["required"], "integrations": manifest["integrations"], "selected": selected, "install_argv": argv, "reminders": ["Configure documentation targets before planning", "Configure notification audiences and record every disposition", "Optional integrations do not weaken required lifecycle gates"], "apply_requested": bool(args.apply), "mutates_environment": False}
    if args.apply:
        if not args.yes:
            raise LifecycleError("dependency installation requires both --apply and --yes")
        if shutil.which("npx") is None:
            raise LifecycleError("npx is required to install dependencies")
        completed = subprocess.run(argv, shell=False, check=False)
        if completed.returncode:
            raise LifecycleError(f"dependency installer exited with {completed.returncode}", mutates_environment=True)
        result["mutates_environment"] = True
        result["installed"] = selected
    return result


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    def common(name: str) -> argparse.ArgumentParser:
        item = sub.add_parser(name)
        item.add_argument("--project-root", required=True)
        item.add_argument("--json", action="store_true")
        return item
    c = common("configure"); c.add_argument("--config-source", required=True); c.set_defaults(func=cmd_configure)
    common("status").set_defaults(func=cmd_status)
    common("migrate").set_defaults(func=cmd_migrate)
    common("rules-status").set_defaults(func=cmd_rules_status)
    cr = common("configure-rules"); cr.add_argument("--apply", action="store_true"); cr.add_argument("--yes", action="store_true"); cr.set_defaults(func=cmd_configure_rules)
    pl = common("plan"); pl.add_argument("--input", required=True); pl.add_argument("--output", required=True); pl.add_argument("--state-output", required=True); pl.set_defaults(func=cmd_plan)
    ad = common("advance"); ad.add_argument("--plan", required=True); ad.add_argument("--state", required=True); ad.add_argument("--checkpoint", required=True); ad.set_defaults(func=cmd_advance)
    ve = common("verify"); ve.add_argument("--plan", required=True); ve.add_argument("--state", required=True); ve.set_defaults(func=cmd_verify)
    dep = sub.add_parser("dependencies"); dep.add_argument("--include-integrations", action="store_true"); dep.add_argument("--apply", action="store_true"); dep.add_argument("--yes", action="store_true"); dep.add_argument("--json", action="store_true"); dep.set_defaults(func=cmd_dependencies)
    return p


def main() -> int:
    args = parser().parse_args()
    try:
        payload = args.func(args)
        output(payload, args.json)
        return 0
    except LifecycleError as exc:
        payload = {"passed": False, "error": str(exc), "mutates_repository": False, "mutates_environment": exc.mutates_environment}
        output(payload, getattr(args, "json", False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
