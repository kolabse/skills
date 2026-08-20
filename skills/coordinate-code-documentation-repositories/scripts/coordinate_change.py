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


CONFIG_VERSION = 1
CONFIG_RELATIVE = Path(".agents/coordinate-code-documentation-repositories/config.json")
TOPICS = {
    "requirement",
    "decision",
    "behavior",
    "operational-impact",
    "validation",
    "limitations",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
UNSAFE_TEXT_RE = re.compile(
    r"(?i)(?:https?://|\b[A-Z]:[\\/]|(?:^|\s)/(?:[^/\s]+/)+|(?:password|secret|token|api[_-]?key)\s*[:=]\s*\S+|"
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b)"
)


class CoordinationError(RuntimeError):
    pass


def canonical_digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def signed(value: dict[str, Any], field: str) -> dict[str, Any]:
    result = dict(value)
    result[field] = canonical_digest(result)
    return result


def load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CoordinationError(f"{label} is unavailable or invalid JSON: {error}") from error
    if not isinstance(value, dict):
        raise CoordinationError(f"{label} must be a JSON object")
    return value


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, indent=2, sort_keys=True) + "\n"
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def validate_relative_path(value: object, label: str, *, allow_parent: bool) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 300:
        raise CoordinationError(f"{label} must be a non-empty relative path")
    text = value.strip().replace("\\", "/")
    if text.startswith("/") or re.match(r"^[A-Za-z]:/", text) or text.startswith("//"):
        raise CoordinationError(f"{label} must not be absolute")
    parts = PurePosixPath(text).parts
    if not allow_parent and ".." in parts:
        raise CoordinationError(f"{label} must stay inside the documentation repository")
    if any(part in ("", "\x00") for part in parts):
        raise CoordinationError(f"{label} is invalid")
    return text


def safe_text(value: object, label: str, *, maximum: int = 1000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise CoordinationError(f"{label} must be a concise non-empty string")
    text = value.strip()
    if UNSAFE_TEXT_RE.search(text):
        raise CoordinationError(f"{label} contains a URL, email address, absolute path, or possible secret")
    return text


def validate_config(value: dict[str, Any]) -> dict[str, Any]:
    if set(value) != {"version", "repositories", "canonical_documentation", "traceability"}:
        raise CoordinationError("configuration has unknown or missing fields")
    version = value.get("version")
    if not isinstance(version, int) or version != CONFIG_VERSION:
        if isinstance(version, int) and version > CONFIG_VERSION:
            raise CoordinationError("configuration uses an unknown newer version")
        raise CoordinationError("configuration version is unsupported")
    repositories = value.get("repositories")
    if not isinstance(repositories, dict) or set(repositories) != {"implementation", "documentation"}:
        raise CoordinationError("repositories must declare implementation and documentation exactly once")
    normalized_repositories: dict[str, dict[str, str]] = {}
    for role in ("implementation", "documentation"):
        item = repositories[role]
        if not isinstance(item, dict) or set(item) != {"path"}:
            raise CoordinationError(f"repository role {role} must contain only path")
        normalized_repositories[role] = {
            "path": validate_relative_path(item["path"], f"repositories.{role}.path", allow_parent=True)
        }
    if normalized_repositories["implementation"]["path"] == normalized_repositories["documentation"]["path"]:
        raise CoordinationError("implementation and documentation must be separate repositories")
    documentation = value.get("canonical_documentation")
    if not isinstance(documentation, dict) or set(documentation) != {"roots", "required_topics"}:
        raise CoordinationError("canonical_documentation must contain roots and required_topics")
    roots_value = documentation.get("roots")
    if not isinstance(roots_value, list) or not roots_value:
        raise CoordinationError("canonical_documentation.roots must be a non-empty list")
    roots = [validate_relative_path(item, "canonical_documentation.roots", allow_parent=False) for item in roots_value]
    if len(set(roots)) != len(roots):
        raise CoordinationError("canonical documentation roots must be unique")
    topics_value = documentation.get("required_topics")
    if (
        not isinstance(topics_value, list)
        or not topics_value
        or any(not isinstance(item, str) or item not in TOPICS for item in topics_value)
    ):
        raise CoordinationError("required_topics contains an unsupported topic")
    if len(set(topics_value)) != len(topics_value):
        raise CoordinationError("required_topics must be unique")
    traceability = value.get("traceability")
    if not isinstance(traceability, dict) or set(traceability) != {"method"}:
        raise CoordinationError("traceability must contain only method")
    if traceability.get("method") not in {"change-request", "release-evidence", "project-record"}:
        raise CoordinationError("traceability method is unsupported")
    return {
        "version": CONFIG_VERSION,
        "repositories": normalized_repositories,
        "canonical_documentation": {"roots": roots, "required_topics": list(topics_value)},
        "traceability": {"method": traceability["method"]},
    }


def git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args], cwd=root, text=True, encoding="utf-8", errors="replace",
        capture_output=True, check=False,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise CoordinationError(f"Git inspection failed for {root.name}: {detail}")
    return result


def inspect_repository(root: Path, role: str, configured_path: str) -> dict[str, Any]:
    state: dict[str, Any] = {"role": role, "path": configured_path, "blockers": []}
    if not root.is_dir():
        state["blockers"].append("repository path does not exist")
        return state
    top = git(root, "rev-parse", "--show-toplevel", check=False)
    if top.returncode != 0:
        state["blockers"].append("path is not a Git repository")
        return state
    git_root = Path(top.stdout.strip()).resolve()
    if git_root != root.resolve():
        state["blockers"].append("configured path is not the exact Git root")
        return state
    state["head"] = git(root, "rev-parse", "HEAD").stdout.strip()
    branch = git(root, "symbolic-ref", "--quiet", "--short", "HEAD", check=False)
    if branch.returncode != 0:
        state["branch"] = None
        state["blockers"].append("repository is on a detached HEAD")
    else:
        state["branch"] = branch.stdout.strip()
    porcelain = git(root, "status", "--porcelain=v1").stdout
    state["clean"] = not bool(porcelain.strip())
    if not state["clean"]:
        state["blockers"].append("worktree is dirty")
    upstream = git(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}", check=False)
    if upstream.returncode != 0:
        state.update({"upstream": None, "upstream_sha": None, "ahead": None, "behind": None})
        state["blockers"].append("tracked upstream is missing")
        return state
    state["upstream"] = upstream.stdout.strip()
    state["upstream_sha"] = git(root, "rev-parse", "@{upstream}").stdout.strip()
    counts = git(root, "rev-list", "--left-right", "--count", "HEAD...@{upstream}").stdout.split()
    state["ahead"], state["behind"] = (int(counts[0]), int(counts[1]))
    if state["behind"] and state["ahead"]:
        state["blockers"].append("repository has diverged from upstream")
    elif state["behind"]:
        state["blockers"].append("repository is behind upstream")
    elif state["ahead"]:
        state["blockers"].append("repository has unpublished commits")
    return state


def resolve_contract(project_root: Path) -> tuple[dict[str, Any], dict[str, Path], list[dict[str, Any]]]:
    config_path = project_root / CONFIG_RELATIVE
    config = validate_config(load_object(config_path, "configuration"))
    roots = {
        role: (project_root / config["repositories"][role]["path"]).resolve()
        for role in ("implementation", "documentation")
    }
    if roots["implementation"] == roots["documentation"]:
        raise CoordinationError("implementation and documentation must resolve to separate repositories")
    states = [
        inspect_repository(roots[role], role, config["repositories"][role]["path"])
        for role in ("implementation", "documentation")
    ]
    return config, roots, states


def status(project_root: Path) -> dict[str, Any]:
    config_path = project_root / CONFIG_RELATIVE
    result: dict[str, Any] = {
        "schema_version": 1,
        "mode": "status",
        "project_root": str(project_root),
        "config_path": str(config_path),
        "configured": config_path.is_file(),
        "repositories": [],
        "blockers": [],
        "mutates_repositories": False,
    }
    if not config_path.is_file():
        result["blockers"].append("configuration is missing")
        result["ready"] = False
        return signed(result, "report_sha256")
    config, roots, states = resolve_contract(project_root)
    result["config_sha256"] = canonical_digest(config)
    result["repositories"] = states
    for state in states:
        result["blockers"].extend(f"{state['role']}: {item}" for item in state["blockers"])
    documentation_root = roots["documentation"]
    for item in config["canonical_documentation"]["roots"]:
        candidate = (documentation_root / item).resolve()
        if not candidate.is_dir() or not is_within(candidate, documentation_root):
            result["blockers"].append(f"canonical documentation root is missing or invalid: {item}")
    result["ready"] = not result["blockers"]
    return signed(result, "report_sha256")


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def documentation_path(root: Path, value: object, label: str) -> tuple[str, Path]:
    relative = validate_relative_path(value, label, allow_parent=False)
    resolved = (root / relative).resolve()
    if not is_within(resolved, root):
        raise CoordinationError(f"{label} escapes the documentation repository")
    return relative, resolved


def in_canonical_root(path: Path, documentation_root: Path, roots: list[str]) -> bool:
    return any(is_within(path, (documentation_root / item).resolve()) for item in roots)


def validate_change_input(value: dict[str, Any], config: dict[str, Any], documentation_root: Path) -> dict[str, Any]:
    if set(value) != {"outcome", "documentation_sources", "documentation_targets", "topics"}:
        raise CoordinationError("change input has unknown or missing fields")
    outcome = safe_text(value.get("outcome"), "outcome")
    roots = config["canonical_documentation"]["roots"]
    normalized: dict[str, list[str]] = {}
    for field in ("documentation_sources", "documentation_targets"):
        items = value.get(field)
        if not isinstance(items, list) or not items:
            raise CoordinationError(f"{field} must be a non-empty list")
        paths: list[str] = []
        for item in items:
            relative, resolved = documentation_path(documentation_root, item, field)
            if not in_canonical_root(resolved, documentation_root, roots):
                raise CoordinationError(f"{field} path is outside canonical roots: {relative}")
            if field == "documentation_sources" and not resolved.is_file():
                raise CoordinationError(f"documentation source does not exist: {relative}")
            if field == "documentation_targets" and resolved.is_dir():
                raise CoordinationError(f"documentation target must be a file path: {relative}")
            paths.append(relative)
        if len(set(paths)) != len(paths):
            raise CoordinationError(f"{field} must not contain duplicates")
        normalized[field] = paths
    topics = value.get("topics")
    if (
        not isinstance(topics, list)
        or not topics
        or any(not isinstance(item, str) or item not in TOPICS for item in topics)
    ):
        raise CoordinationError("topics contains an unsupported value")
    if len(set(topics)) != len(topics):
        raise CoordinationError("topics must be unique")
    missing = set(config["canonical_documentation"]["required_topics"]) - set(topics)
    if missing:
        raise CoordinationError(f"change input omits required topics: {', '.join(sorted(missing))}")
    return {"outcome": outcome, **normalized, "topics": list(topics)}


def ensure_external_output(path: Path, repository_roots: dict[str, Path]) -> None:
    resolved = path.resolve()
    for role, root in repository_roots.items():
        if is_within(resolved, root):
            raise CoordinationError(f"plan output must stay outside the {role} repository")


def build_plan(project_root: Path, input_path: Path, output: Path | None) -> dict[str, Any]:
    config, roots, states = resolve_contract(project_root)
    blockers = [f"{state['role']}: {item}" for state in states for item in state["blockers"]]
    for item in config["canonical_documentation"]["roots"]:
        candidate = (roots["documentation"] / item).resolve()
        if not candidate.is_dir() or not is_within(candidate, roots["documentation"]):
            blockers.append(f"canonical documentation root is missing or invalid: {item}")
    change = validate_change_input(load_object(input_path, "change input"), config, roots["documentation"])
    plan = {
        "schema_version": 1,
        "mode": "plan",
        "config_sha256": canonical_digest(config),
        "outcome": change["outcome"],
        "documentation_sources": change["documentation_sources"],
        "documentation_targets": change["documentation_targets"],
        "topics": change["topics"],
        "repositories": {
            state["role"]: {
                "path": state["path"],
                "head": state.get("head"),
                "upstream": state.get("upstream"),
                "upstream_sha": state.get("upstream_sha"),
            }
            for state in states
        },
        "blockers": blockers,
        "ready": not blockers,
        "mutates_repositories": False,
    }
    plan = signed(plan, "plan_sha256")
    if output is not None:
        ensure_external_output(output, roots)
        atomic_write(output, plan)
    return plan


def verify_digest(value: dict[str, Any], field: str, label: str) -> None:
    expected = value.get(field)
    if not isinstance(expected, str) or not SHA256_RE.fullmatch(expected):
        raise CoordinationError(f"{label} has no valid {field}")
    actual = canonical_digest({key: item for key, item in value.items() if key != field})
    if actual != expected:
        raise CoordinationError(f"{label} digest does not match its content")


def verify_completion(project_root: Path, plan_path: Path, input_path: Path) -> dict[str, Any]:
    plan = load_object(plan_path, "plan")
    verify_digest(plan, "plan_sha256", "plan")
    if plan.get("mode") != "plan" or plan.get("ready") is not True:
        raise CoordinationError("verification requires a blocker-free plan")
    config, roots, states = resolve_contract(project_root)
    if plan.get("config_sha256") != canonical_digest(config):
        raise CoordinationError("configuration changed after the plan")
    evidence = load_object(input_path, "verification input")
    expected_fields = {
        "plan_sha256", "implementation_commit", "documentation_commit",
        "documentation_evidence", "validation_results", "traceability",
    }
    if set(evidence) != expected_fields:
        raise CoordinationError("verification input has unknown or missing fields")
    if evidence.get("plan_sha256") != plan["plan_sha256"]:
        raise CoordinationError("verification input is bound to another plan")
    blockers = [f"{state['role']}: {item}" for state in states for item in state["blockers"]]
    state_by_role = {state["role"]: state for state in states}
    for role, field in (("implementation", "implementation_commit"), ("documentation", "documentation_commit")):
        commit = evidence.get(field)
        if not isinstance(commit, str) or not COMMIT_RE.fullmatch(commit):
            blockers.append(f"{field} is invalid")
            continue
        current = state_by_role[role]
        planned = plan["repositories"][role]["head"]
        if commit == planned:
            blockers.append(f"{role} repository did not change from the plan")
        if current.get("head") != commit:
            blockers.append(f"{role} final commit does not match local HEAD")
        if current.get("upstream") != plan["repositories"][role]["upstream"]:
            blockers.append(f"{role} tracked upstream changed after the plan")
        if current.get("upstream_sha") != commit:
            blockers.append(f"{role} final commit is not the tracked upstream identity")
        if roots[role].is_dir() and current.get("head") is not None:
            ancestry = git(roots[role], "merge-base", "--is-ancestor", planned, commit, check=False)
            if ancestry.returncode != 0:
                blockers.append(f"{role} final commit does not descend from the planned commit")
            if role == "implementation":
                content_change = git(
                    roots[role], "diff", "--quiet", planned, commit, "--", check=False
                )
                if content_change.returncode == 0:
                    blockers.append("implementation content did not change from the plan")
                elif content_change.returncode != 1:
                    blockers.append("implementation content could not be compared")
    planned_targets = set(plan["documentation_targets"])
    documentation_commit = evidence.get("documentation_commit")
    if (
        isinstance(documentation_commit, str)
        and COMMIT_RE.fullmatch(documentation_commit)
        and roots["documentation"].is_dir()
        and state_by_role["documentation"].get("head") is not None
    ):
        planned_documentation_commit = plan["repositories"]["documentation"]["head"]
        changed = git(
            roots["documentation"],
            "diff", "--name-only", planned_documentation_commit, documentation_commit,
            "--", *sorted(planned_targets),
            check=False,
        )
        if changed.returncode != 0:
            blockers.append("planned documentation targets could not be compared")
        else:
            changed_targets = {item.strip().replace("\\", "/") for item in changed.stdout.splitlines() if item.strip()}
            for target in sorted(planned_targets - changed_targets):
                blockers.append(f"planned documentation target did not change: {target}")
    documentation_evidence = evidence.get("documentation_evidence")
    if not isinstance(documentation_evidence, dict):
        blockers.append("documentation_evidence must be an object")
        documentation_evidence = {}
    elif not set(documentation_evidence).issubset(TOPICS):
        blockers.append("documentation_evidence contains an unsupported topic")
    required_topics = plan["topics"]
    roots_config = config["canonical_documentation"]["roots"]
    for topic in required_topics:
        paths = documentation_evidence.get(topic)
        if not isinstance(paths, list) or not paths:
            blockers.append(f"documentation evidence is missing for topic: {topic}")
            continue
        for item in paths:
            try:
                relative, resolved = documentation_path(roots["documentation"], item, f"documentation_evidence.{topic}")
                if not resolved.is_file() or not in_canonical_root(resolved, roots["documentation"], roots_config):
                    blockers.append(f"documentation evidence path is missing or outside canonical roots: {relative}")
                elif relative not in planned_targets:
                    blockers.append(f"documentation evidence is not a planned target: {relative}")
            except CoordinationError as error:
                blockers.append(str(error))
    validations = evidence.get("validation_results")
    if not isinstance(validations, list) or not validations:
        blockers.append("validation_results must be a non-empty list")
    else:
        for item in validations:
            if (
                not isinstance(item, dict)
                or set(item) != {"name", "status", "evidence_sha256"}
                or item.get("status") != "passed"
                or not SHA256_RE.fullmatch(str(item.get("evidence_sha256", "")))
            ):
                blockers.append("every validation result must be passed and digest-bound")
                break
            try:
                safe_text(item.get("name"), "validation result name", maximum=200)
            except CoordinationError as error:
                blockers.append(str(error))
                break
    traceability = evidence.get("traceability")
    roles: set[str] = set()
    if not isinstance(traceability, list):
        blockers.append("traceability must be a list")
    else:
        for item in traceability:
            if (
                not isinstance(item, dict)
                or set(item) != {"method", "repository", "reference", "evidence_sha256"}
                or item.get("method") != config["traceability"]["method"]
                or item.get("repository") not in {"implementation", "documentation"}
                or not SHA256_RE.fullmatch(str(item.get("evidence_sha256", "")))
            ):
                blockers.append("traceability record is invalid or uses the wrong configured method")
                continue
            try:
                safe_text(item.get("reference"), "traceability reference", maximum=300)
            except CoordinationError as error:
                blockers.append(str(error))
                continue
            roles.add(item["repository"])
    if roles != {"implementation", "documentation"}:
        blockers.append("traceability must cover both repository roles")
    result = {
        "schema_version": 1,
        "mode": "verify",
        "plan_sha256": plan["plan_sha256"],
        "commits": {
            "implementation": evidence.get("implementation_commit") if isinstance(evidence.get("implementation_commit"), str) else None,
            "documentation": evidence.get("documentation_commit") if isinstance(evidence.get("documentation_commit"), str) else None,
        },
        "blockers": sorted(set(blockers)),
        "passed": not blockers,
        "mutates_repositories": False,
    }
    return signed(result, "report_sha256")


def configure(project_root: Path, source: Path | None) -> dict[str, Any]:
    target = project_root / CONFIG_RELATIVE
    if source is None:
        config = validate_config(load_object(target, "configuration"))
        changed = False
    else:
        config = validate_config(load_object(source, "configuration source"))
        existing = target.read_text(encoding="utf-8") if target.is_file() else None
        rendered = json.dumps(config, indent=2, sort_keys=True) + "\n"
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
    root = argparse.ArgumentParser(description="Coordinate code and canonical documentation repositories")
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
    except CoordinationError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
