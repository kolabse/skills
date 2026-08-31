from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


CONFIG_VERSION = 1
CONFIG_RELATIVE = Path(".agents/execute-configured-gitflow-releases/config.json")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
GATE_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
REMOTE_RE = re.compile(r"^[A-Za-z0-9._-]+$")
UNSAFE_TEXT_RE = re.compile(
    r"(?i)(?:https?://|\b[A-Z]:[\\/]|(?:^|\s)/(?:[^/\s]+/)+|(?:password|secret|token|api[_-]?key)\s*[:=]\s*\S+|"
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b)"
)


class GitFlowError(RuntimeError):
    pass


def canonical_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def signed(value: dict[str, Any], field: str) -> dict[str, Any]:
    result = dict(value)
    result[field] = canonical_digest(result)
    return result


def load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise GitFlowError(f"{label} is unavailable or invalid JSON: {error}") from error
    if not isinstance(value, dict):
        raise GitFlowError(f"{label} must be a JSON object")
    return value


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(value, indent=2, sort_keys=True) + "\n")
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def valid_branch(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 240:
        raise GitFlowError(f"{label} must be a non-empty branch name")
    text = value.strip()
    result = subprocess.run(
        ["git", "check-ref-format", "--branch", text],
        text=True, encoding="utf-8", errors="replace", capture_output=True, check=False,
    )
    if result.returncode != 0:
        raise GitFlowError(f"{label} is not a valid branch name")
    return text


def safe_text(value: object, label: str, *, maximum: int = 200) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise GitFlowError(f"{label} must be a concise non-empty identifier")
    text = value.strip()
    if UNSAFE_TEXT_RE.search(text):
        raise GitFlowError(f"{label} contains a URL, email address, absolute path, or possible secret")
    return text


def validate_gates(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not GATE_RE.fullmatch(item) for item in value):
        raise GitFlowError(f"{label} must contain portable lowercase gate names")
    if len(set(value)) != len(value):
        raise GitFlowError(f"{label} contains duplicate gates")
    return list(value)


def validate_config(value: dict[str, Any]) -> dict[str, Any]:
    expected = {
        "version", "remote", "branches", "protected_production", "default_route",
        "gates", "deployment", "reintegration",
    }
    if set(value) != expected:
        raise GitFlowError("configuration has unknown or missing fields")
    version = value.get("version")
    if not isinstance(version, int) or version != CONFIG_VERSION:
        if isinstance(version, int) and version > CONFIG_VERSION:
            raise GitFlowError("configuration uses an unknown newer version")
        raise GitFlowError("configuration version is unsupported")
    remote = value.get("remote")
    if not isinstance(remote, str) or not REMOTE_RE.fullmatch(remote):
        raise GitFlowError("remote name is invalid")
    branches = value.get("branches")
    required_branches = {"development", "production", "hotfix_prefix"}
    if (
        not isinstance(branches, dict)
        or not required_branches.issubset(branches)
        or not set(branches).issubset(required_branches | {"release_prefix"})
    ):
        raise GitFlowError("branches must declare development, production, hotfix_prefix, and optionally release_prefix")
    development = valid_branch(branches["development"], "development branch")
    production = valid_branch(branches["production"], "production branch")
    prefix = branches.get("hotfix_prefix")
    if not isinstance(prefix, str) or not prefix.endswith("/") or len(prefix) < 2:
        raise GitFlowError("hotfix_prefix must be a non-empty branch namespace ending in /")
    valid_branch(f"{prefix}candidate", "hotfix prefix")
    if development == production:
        raise GitFlowError("development and production roles must be different")
    if development.startswith(prefix) or production.startswith(prefix):
        raise GitFlowError("persistent branch roles must remain outside the hotfix namespace")
    normalized_branches = {"development": development, "production": production, "hotfix_prefix": prefix}
    if "release_prefix" in branches:
        release_prefix = branches["release_prefix"]
        if (
            not isinstance(release_prefix, str)
            or release_prefix != release_prefix.strip()
            or not release_prefix.endswith("/")
            or len(release_prefix) < 2
        ):
            raise GitFlowError("release_prefix must be a non-empty branch namespace ending in /")
        valid_branch(f"{release_prefix}candidate", "release prefix")
        if release_prefix.startswith(prefix) or prefix.startswith(release_prefix):
            raise GitFlowError("release and hotfix namespaces must not overlap")
        if any(
            branch.startswith(release_prefix) or release_prefix.startswith(f"{branch}/")
            for branch in (development, production)
        ):
            raise GitFlowError("persistent branch roles must remain outside the release namespace")
        normalized_branches["release_prefix"] = release_prefix
    if value.get("protected_production") is not True:
        raise GitFlowError("production must be declared protected")
    default_route = value.get("default_route")
    if default_route not in {None, "standard"}:
        raise GitFlowError("default_route may be standard or null; hotfix is never a default")
    gates = value.get("gates")
    if not isinstance(gates, dict) or set(gates) != {"common", "standard", "hotfix"}:
        raise GitFlowError("gates must declare common, standard, and hotfix lists")
    normalized_gates = {name: validate_gates(gates[name], f"gates.{name}") for name in ("common", "standard", "hotfix")}
    combined = normalized_gates["common"] + normalized_gates["standard"] + normalized_gates["hotfix"]
    if len(set(combined)) != len(combined):
        raise GitFlowError("gate names must be unique across common and route-specific lists")
    deployment = value.get("deployment")
    if not isinstance(deployment, dict) or set(deployment) != {"evidence_required"} or not isinstance(deployment.get("evidence_required"), bool):
        raise GitFlowError("deployment must declare evidence_required")
    reintegration = value.get("reintegration")
    if not isinstance(reintegration, dict) or set(reintegration) != {"required"} or reintegration.get("required") is not True:
        raise GitFlowError("hotfix reintegration must be required")
    return {
        "version": CONFIG_VERSION,
        "remote": remote,
        "branches": normalized_branches,
        "protected_production": True,
        "default_route": default_route,
        "gates": normalized_gates,
        "deployment": {"evidence_required": deployment["evidence_required"]},
        "reintegration": {"required": True},
    }


def git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args], cwd=root, text=True, encoding="utf-8", errors="replace",
        capture_output=True, check=False,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise GitFlowError(f"Git inspection failed: {detail}")
    return result


def require_git_root(project_root: Path) -> None:
    top = git(project_root, "rev-parse", "--show-toplevel", check=False)
    if top.returncode != 0 or Path(top.stdout.strip()).resolve() != project_root.resolve():
        raise GitFlowError("project root must be the exact Git repository root")


def remote_ref(config: dict[str, Any], branch: str) -> str:
    return f"refs/remotes/{config['remote']}/{branch}"


def resolve_ref(project_root: Path, ref: str) -> str | None:
    result = git(project_root, "rev-parse", "--verify", ref, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def inspect_repository(project_root: Path) -> dict[str, Any]:
    require_git_root(project_root)
    result: dict[str, Any] = {
        "head": git(project_root, "rev-parse", "HEAD").stdout.strip(),
        "clean": not bool(git(project_root, "status", "--porcelain=v1").stdout.strip()),
        "blockers": [],
        "warnings": [],
    }
    branch = git(project_root, "symbolic-ref", "--quiet", "--short", "HEAD", check=False)
    result["branch"] = branch.stdout.strip() if branch.returncode == 0 else None
    if result["branch"] is None:
        result["blockers"].append("repository is on a detached HEAD")
    if not result["clean"]:
        result["blockers"].append("worktree is dirty")
    upstream = git(project_root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}", check=False)
    if upstream.returncode != 0:
        result.update({"upstream": None, "upstream_sha": None, "ahead": None, "behind": None})
        result["blockers"].append("tracked upstream is missing")
        return result
    result["upstream"] = upstream.stdout.strip()
    result["upstream_sha"] = git(project_root, "rev-parse", "@{upstream}").stdout.strip()
    counts = git(project_root, "rev-list", "--left-right", "--count", "HEAD...@{upstream}").stdout.split()
    result["ahead"], result["behind"] = int(counts[0]), int(counts[1])
    if result["ahead"] and result["behind"]:
        result["blockers"].append("repository has diverged from upstream")
    elif result["behind"]:
        result["blockers"].append("repository is behind upstream")
    elif result["ahead"]:
        result["warnings"].append("source commit is not yet published to its tracked upstream")
    return result


def load_config(project_root: Path) -> dict[str, Any]:
    return validate_config(load_object(project_root / CONFIG_RELATIVE, "configuration"))


def status(project_root: Path) -> dict[str, Any]:
    config_path = project_root / CONFIG_RELATIVE
    result: dict[str, Any] = {
        "schema_version": 1,
        "mode": "status",
        "project_root": str(project_root),
        "config_path": str(config_path),
        "configured": config_path.is_file(),
        "blockers": [],
        "mutates_repository": False,
    }
    if not config_path.is_file():
        result["blockers"].append("configuration is missing")
        result["ready"] = False
        return signed(result, "report_sha256")
    config = load_config(project_root)
    require_git_root(project_root)
    result["config_sha256"] = canonical_digest(config)
    identities = {}
    for role in ("development", "production"):
        branch = config["branches"][role]
        identity = resolve_ref(project_root, remote_ref(config, branch))
        identities[role] = {"branch": branch, "remote_commit": identity}
        if identity is None:
            result["blockers"].append(f"remote {role} branch is missing")
    result["remote"] = config["remote"]
    result["branches"] = identities
    result["ready"] = not result["blockers"]
    return signed(result, "report_sha256")


def validate_route_input(value: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    allowed = {"release_id", "route", "source_branch", "explicit_hotfix"}
    required = {"release_id", "source_branch", "explicit_hotfix"}
    if not required.issubset(value) or not set(value).issubset(allowed):
        raise GitFlowError("route input has unknown or missing fields")
    release_id = safe_text(value.get("release_id"), "release_id")
    source_branch = valid_branch(value.get("source_branch"), "source_branch")
    explicit_hotfix = value.get("explicit_hotfix")
    if not isinstance(explicit_hotfix, bool):
        raise GitFlowError("explicit_hotfix must be boolean")
    route = value.get("route", config["default_route"])
    if route not in {"standard", "hotfix"}:
        raise GitFlowError("release route is ambiguous and no standard default is declared")
    if route == "hotfix" and not explicit_hotfix:
        raise GitFlowError("hotfix route requires explicit hotfix intent")
    if route == "standard" and explicit_hotfix:
        raise GitFlowError("explicit hotfix intent conflicts with the standard route")
    return {"release_id": release_id, "route": route, "source_branch": source_branch, "explicit_hotfix": explicit_hotfix}


def ensure_external_output(path: Path, project_root: Path) -> None:
    try:
        path.resolve().relative_to(project_root.resolve())
    except ValueError:
        return
    raise GitFlowError("release plan output must stay outside the repository")


def build_plan(project_root: Path, input_path: Path, output: Path | None) -> dict[str, Any]:
    config = load_config(project_root)
    route_input = validate_route_input(load_object(input_path, "route input"), config)
    state = inspect_repository(project_root)
    blockers = list(state["blockers"])
    warnings = list(state["warnings"])
    branches = config["branches"]
    route = route_input["route"]
    source_branch = route_input["source_branch"]
    release_source = (
        source_branch.startswith(branches.get("release_prefix", "release/"))
        and source_branch not in {branches["development"], branches["production"]}
        and not source_branch.startswith(branches["hotfix_prefix"])
    )
    if state.get("branch") != route_input["source_branch"]:
        blockers.append("source_branch does not match the checked-out branch")
    if route == "standard":
        if source_branch != branches["development"] and not release_source:
            blockers.append("standard route must start from the configured development branch or release namespace")
        target_branch = branches["production"]
    else:
        if not route_input["source_branch"].startswith(branches["hotfix_prefix"]):
            blockers.append("hotfix source is outside the configured hotfix namespace")
        target_branch = branches["production"]
    identities: dict[str, str | None] = {}
    for role in ("development", "production"):
        identities[role] = resolve_ref(project_root, remote_ref(config, branches[role]))
        if identities[role] is None:
            blockers.append(f"remote {role} branch is missing")
    configured_source = resolve_ref(project_root, remote_ref(config, route_input["source_branch"]))
    if configured_source is None:
        blockers.append("source branch is missing from the configured remote")
    else:
        counts = git(
            project_root, "rev-list", "--left-right", "--count",
            f"HEAD...{configured_source}",
        ).stdout.split()
        source_ahead, source_behind = int(counts[0]), int(counts[1])
        if source_ahead and source_behind:
            blockers.append("source branch has diverged from the configured remote")
        elif source_behind:
            blockers.append("source branch is behind the configured remote")
        elif source_ahead:
            warnings.append("source commit is not yet published to the configured remote")
    if route == "hotfix" and identities["production"] is not None:
        ancestry = git(project_root, "merge-base", "--is-ancestor", identities["production"], "HEAD", check=False)
        if ancestry.returncode != 0:
            blockers.append("hotfix source does not descend from the remote production identity")
    if route == "standard" and release_source and identities["development"] is not None:
        ancestry = git(
            project_root, "merge-base", "--is-ancestor",
            identities["development"], state["head"], check=False,
        )
        if ancestry.returncode != 0:
            blockers.append("release source does not descend from the remote development identity")
    gates = config["gates"]["common"] + config["gates"][route]
    plan = {
        "schema_version": 1,
        "mode": "plan",
        "release_id": route_input["release_id"],
        "route": route,
        "config_sha256": canonical_digest(config),
        "remote": config["remote"],
        "source_branch": route_input["source_branch"],
        "target_branch": target_branch,
        "source_commit": state["head"],
        "remote_identities": identities,
        "gates": gates,
        "deployment_evidence_required": config["deployment"]["evidence_required"],
        "reintegration_required": route == "hotfix" and config["reintegration"]["required"],
        "warnings": warnings,
        "blockers": sorted(set(blockers)),
        "ready": not blockers,
        "mutates_repository": False,
    }
    plan = signed(plan, "plan_sha256")
    if output is not None:
        ensure_external_output(output, project_root)
        atomic_write(output, plan)
    return plan


def verify_digest(value: dict[str, Any], field: str, label: str) -> None:
    expected = value.get(field)
    if not isinstance(expected, str) or not SHA256_RE.fullmatch(expected):
        raise GitFlowError(f"{label} has no valid {field}")
    actual = canonical_digest({key: item for key, item in value.items() if key != field})
    if actual != expected:
        raise GitFlowError(f"{label} digest does not match its content")


def valid_digest(value: object) -> bool:
    return isinstance(value, str) and bool(SHA256_RE.fullmatch(value))


def verify_completion(project_root: Path, plan_path: Path, input_path: Path) -> dict[str, Any]:
    plan = load_object(plan_path, "release plan")
    verify_digest(plan, "plan_sha256", "release plan")
    if plan.get("mode") != "plan" or plan.get("ready") is not True:
        raise GitFlowError("verification requires a blocker-free release plan")
    config = load_config(project_root)
    if plan.get("config_sha256") != canonical_digest(config):
        raise GitFlowError("release configuration changed after the plan")
    evidence = load_object(input_path, "verification input")
    expected_fields = {
        "plan_sha256", "source_commit", "gate_evidence", "review",
        "production_commit", "deployment", "reintegration",
    }
    if set(evidence) != expected_fields:
        raise GitFlowError("verification input has unknown or missing fields")
    if evidence.get("plan_sha256") != plan["plan_sha256"]:
        raise GitFlowError("verification input is bound to another plan")
    blockers: list[str] = []
    source_commit = evidence.get("source_commit")
    if source_commit != plan["source_commit"] or not COMMIT_RE.fullmatch(str(source_commit or "")):
        blockers.append("source commit does not match the planned source identity")
    gates = evidence.get("gate_evidence")
    if not isinstance(gates, dict) or set(gates) != set(plan["gates"]):
        blockers.append("gate evidence must cover all and only planned gates")
    else:
        for name in plan["gates"]:
            item = gates[name]
            if (
                not isinstance(item, dict)
                or set(item) != {"status", "commit", "evidence_sha256"}
                or item.get("status") != "passed"
                or item.get("commit") != plan["source_commit"]
                or not valid_digest(item.get("evidence_sha256"))
            ):
                blockers.append(f"gate evidence is invalid or stale: {name}")
    review = evidence.get("review")
    if (
        not isinstance(review, dict)
        or set(review) != {
            "status", "source_branch", "target_branch", "source_commit", "evidence_sha256"
        }
        or review.get("status") != "passed"
        or review.get("source_branch") != plan["source_branch"]
        or review.get("target_branch") != plan["target_branch"]
        or review.get("source_commit") != plan["source_commit"]
        or not valid_digest(review.get("evidence_sha256"))
    ):
        blockers.append("review evidence does not match the planned route")
    current_source = resolve_ref(project_root, remote_ref(config, plan["source_branch"]))
    if current_source != plan["source_commit"]:
        blockers.append("remote source branch changed after the release plan")
    production_commit = evidence.get("production_commit")
    if not isinstance(production_commit, str) or not COMMIT_RE.fullmatch(production_commit):
        blockers.append("production_commit is invalid")
    current_production = resolve_ref(project_root, remote_ref(config, config["branches"]["production"]))
    if current_production != production_commit:
        blockers.append("production_commit does not match the current remote production identity")
    source_reached_production = False
    planned_production_preserved = False
    production_advanced = False
    if isinstance(production_commit, str) and COMMIT_RE.fullmatch(production_commit):
        production_ancestry = git(
            project_root, "merge-base", "--is-ancestor",
            plan["source_commit"], production_commit,
            check=False,
        )
        source_reached_production = production_ancestry.returncode == 0
        if not source_reached_production:
            blockers.append("remote production does not contain the planned source commit")
        planned_production = plan["remote_identities"].get("production")
        if isinstance(planned_production, str):
            production_advanced = production_commit != planned_production
            if not production_advanced:
                blockers.append("remote production did not advance from the planned identity")
            preserved_production = git(
                project_root, "merge-base", "--is-ancestor",
                planned_production, production_commit,
                check=False,
            )
            planned_production_preserved = preserved_production.returncode == 0
            if not planned_production_preserved:
                blockers.append("remote production discarded the planned production history")
    deployment = evidence.get("deployment")
    if not isinstance(deployment, dict) or set(deployment) != {"status", "production_commit", "evidence_sha256"}:
        blockers.append("deployment evidence is invalid")
    elif config["deployment"]["evidence_required"]:
        if deployment.get("status") != "passed" or deployment.get("production_commit") != production_commit or not valid_digest(deployment.get("evidence_sha256")):
            blockers.append("required deployment evidence is missing, stale, or failing")
    elif deployment.get("status") not in {"passed", "not-required"}:
        blockers.append("deployment status is unsupported")
    elif deployment.get("production_commit") != production_commit:
        blockers.append("deployment evidence is bound to another production commit")
    elif deployment.get("status") == "passed" and not valid_digest(deployment.get("evidence_sha256")):
        blockers.append("deployment evidence digest is invalid")
    elif deployment.get("status") == "not-required" and deployment.get("evidence_sha256") is not None:
        blockers.append("not-required deployment evidence digest must be null")
    reintegration = evidence.get("reintegration")
    if not isinstance(reintegration, dict) or set(reintegration) != {"status", "target_branch", "commit", "evidence_sha256"}:
        blockers.append("reintegration evidence is invalid")
        reintegration_status = None
        reintegration = {}
    else:
        reintegration_status = reintegration.get("status")
    if plan["route"] == "hotfix":
        current_development = resolve_ref(project_root, remote_ref(config, config["branches"]["development"]))
        if reintegration_status == "blocked":
            blockers.append("hotfix production publication is verified but reintegration is blocked")
        elif (
            reintegration_status != "passed"
            or reintegration.get("target_branch") != config["branches"]["development"]
            or reintegration.get("commit") != current_development
            or not valid_digest(reintegration.get("evidence_sha256"))
        ):
            blockers.append("hotfix reintegration does not match the current remote development identity")
        elif isinstance(current_development, str):
            reintegration_ancestry = git(
                project_root, "merge-base", "--is-ancestor",
                plan["source_commit"], current_development,
                check=False,
            )
            if reintegration_ancestry.returncode != 0:
                blockers.append("remote development does not contain the planned hotfix commit")
            planned_development = plan["remote_identities"].get("development")
            if isinstance(planned_development, str):
                if current_development == planned_development:
                    blockers.append("remote development did not advance during hotfix reintegration")
                preserved_development = git(
                    project_root, "merge-base", "--is-ancestor",
                    planned_development, current_development,
                    check=False,
                )
                if preserved_development.returncode != 0:
                    blockers.append("remote development discarded the planned development history")
    elif (
        reintegration_status != "not-required"
        or reintegration.get("target_branch") != config["branches"]["development"]
        or reintegration.get("commit") is not None
        or reintegration.get("evidence_sha256") is not None
    ):
        blockers.append("standard route must declare a clean not-required reintegration record")
    result = {
        "schema_version": 1,
        "mode": "verify",
        "release_id": plan["release_id"],
        "route": plan["route"],
        "source_commit": plan["source_commit"],
        "production_commit": production_commit if isinstance(production_commit, str) else None,
        "production_published": bool(
            isinstance(production_commit, str)
            and COMMIT_RE.fullmatch(production_commit)
            and isinstance(current_production, str)
            and current_production == production_commit
            and source_reached_production
            and planned_production_preserved
            and production_advanced
        ),
        "reintegration_status": reintegration_status if reintegration_status in {"passed", "blocked", "not-required"} else None,
        "blockers": sorted(set(blockers)),
        "passed": not blockers,
        "mutates_repository": False,
    }
    return signed(result, "report_sha256")


def configure(project_root: Path, source: Path | None) -> dict[str, Any]:
    target = project_root / CONFIG_RELATIVE
    if source is None:
        config = validate_config(load_object(target, "configuration"))
        changed = False
    else:
        config = validate_config(load_object(source, "configuration source"))
        rendered = json.dumps(config, indent=2, sort_keys=True) + "\n"
        existing = target.read_text(encoding="utf-8") if target.is_file() else None
        changed = existing != rendered
        if changed:
            atomic_write(target, config)
    return signed({
        "schema_version": 1,
        "mode": "configure",
        "config_path": str(target),
        "config_sha256": canonical_digest(config),
        "changed": changed,
    }, "report_sha256")


def migrate(project_root: Path) -> dict[str, Any]:
    target = project_root / CONFIG_RELATIVE
    config = validate_config(load_object(target, "configuration"))
    return signed({
        "schema_version": 1,
        "mode": "migrate",
        "config_path": str(target),
        "version": config["version"],
        "changed": False,
    }, "report_sha256")


def emit(result: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        state = result.get("passed", result.get("ready", True))
        print(f"{result['mode']}: {'passed' if state else 'blocked'}")
        for blocker in result.get("blockers", []):
            print(f"- {blocker}")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Plan and verify configured GitFlow releases")
    sub = root.add_subparsers(dest="command", required=True)
    for name in ("configure", "status", "migrate", "plan", "verify"):
        command = sub.add_parser(name)
        command.add_argument("--project-root", type=Path, required=True)
        command.add_argument("--json", action="store_true")
        if name == "configure":
            command.add_argument("--config-source", type=Path)
        elif name == "plan":
            command.add_argument("--input", type=Path, required=True)
            command.add_argument("--output", type=Path)
        elif name == "verify":
            command.add_argument("--plan", type=Path, required=True)
            command.add_argument("--input", type=Path, required=True)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    project_root = args.project_root.resolve()
    try:
        if args.command == "configure":
            result = configure(project_root, args.config_source)
        elif args.command == "status":
            result = status(project_root)
        elif args.command == "migrate":
            result = migrate(project_root)
        elif args.command == "plan":
            result = build_plan(project_root, args.input, args.output)
        else:
            result = verify_completion(project_root, args.plan, args.input)
        emit(result, args.json)
        if result.get("ready") is False or result.get("passed") is False:
            return 1
        return 0
    except GitFlowError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
