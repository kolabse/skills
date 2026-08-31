from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CONFIG_RELATIVE = Path(".agents/verify-before-push/config.json")
DEFAULT_EVIDENCE = Path(".agents/verify-before-push/evidence.json")
TRUSTED_ENVIRONMENT_VARIABLE = "VERIFY_BEFORE_PUSH_TRUSTED_ENVIRONMENT_SHA256"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
POLICY_START = "<!-- verify-before-push:start -->"
POLICY_END = "<!-- verify-before-push:end -->"
CODEX_POLICY_BLOCK = """<!-- verify-before-push:start -->
## Verification before push

Use `$verify-before-push` before pushing protected repositories. Run the
project-declared checks and require current evidence bound to the exact Git
commits and worktrees being pushed. Treat missing, failed, malformed, or
stale evidence as a stop condition for a protected push.
<!-- verify-before-push:end -->"""
CLAUDE_POLICY_BLOCK = CODEX_POLICY_BLOCK.replace("`$verify-before-push`", "`/verify-before-push`")
AGENTS = {
    "codex": {"filename": "AGENTS.md", "block": CODEX_POLICY_BLOCK},
    "claude-code": {"filename": "CLAUDE.md", "block": CLAUDE_POLICY_BLOCK},
}


class VerificationError(RuntimeError):
    pass


class ReuseUnavailable(VerificationError):
    """Full verification is supported, but runtime identity is ambiguous."""


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def run_process(args: list[str], cwd: Path, timeout: int = 30) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            args, cwd=cwd, capture_output=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise VerificationError(f"Could not run {args[0]!r} in {cwd}: {error}") from error


def git(repo: Path, *args: str, check: bool = True) -> bytes:
    result = run_process(["git", "-C", str(repo), *args], repo)
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).decode("utf-8", errors="replace").strip()
        raise VerificationError(f"git {' '.join(args)} failed in {repo}: {detail[:300]}")
    return result.stdout


def git_root(path: Path) -> Path:
    output = git(path, "rev-parse", "--show-toplevel")
    return Path(output.decode("utf-8", errors="replace").strip()).resolve()


def load_json(path: Path, label: str) -> dict[str, Any]:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise VerificationError(f"{label} contains duplicate JSON keys")
            result[key] = value
        return result

    try:
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    except FileNotFoundError as error:
        raise VerificationError(f"{label} is missing: {path}") from error
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise VerificationError(f"{label} is invalid: {path}: {error}") from error
    if not isinstance(data, dict):
        raise VerificationError(f"{label} root must be an object: {path}")
    return data


def resolve_inside(base: Path, value: str, label: str) -> Path:
    if Path(value).is_absolute():
        raise VerificationError(f"{label} must be relative to project root: {value}")
    path = (base / value).resolve()
    if path == base or base in path.parents:
        return path
    # Repositories may intentionally be sibling clones; other files may not escape.
    if label in {"repository", "check cwd"}:
        return path
    raise VerificationError(f"{label} must stay inside project root: {value}")


def load_config(project_root: Path) -> tuple[dict[str, Any], Path]:
    path = project_root / CONFIG_RELATIVE
    config = load_json(path, "Configuration")
    return config, validate_config_document(config, project_root, validate_checks=False)


def validate_config_document(
    config: dict[str, Any], project_root: Path, *, validate_checks: bool = True,
) -> Path:
    if type(config.get("version")) is not int or config["version"] != 1:
        raise VerificationError("Configuration version must be 1")
    if not isinstance(config.get("reuse_verified_results", False), bool):
        raise VerificationError("reuse_verified_results must be a boolean")
    repositories = config.get("repositories")
    checks = config.get("checks")
    if not isinstance(repositories, list) or not repositories:
        raise VerificationError("repositories must be a non-empty list")
    if not isinstance(checks, list) or not checks:
        raise VerificationError("checks must be a non-empty list")
    evidence_value = config.get("evidence_file", DEFAULT_EVIDENCE.as_posix())
    if not isinstance(evidence_value, str) or not evidence_value:
        raise VerificationError("evidence_file must be a non-empty string")
    evidence_path = resolve_inside(project_root, evidence_value, "evidence_file")
    roots = [validate_repository_entry(entry, project_root)[1] for entry in repositories]
    if not validate_checks:
        return evidence_path
    names: set[str] = set()
    for entry in checks:
        name = validate_check(entry, project_root, roots)[0]
        if name in names:
            raise VerificationError(f"Duplicate check name: {name}")
        names.add(name)
    return evidence_path


def policy_state(project_root: Path, agent: str = "codex") -> tuple[Path, str, bool]:
    path = project_root / AGENTS[agent]["filename"]
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    starts, ends = text.count(POLICY_START), text.count(POLICY_END)
    if starts != ends or starts > 1 or (starts == 1 and text.index(POLICY_START) > text.index(POLICY_END)):
        raise VerificationError(f"{AGENTS[agent]['filename']} contains malformed or duplicate managed markers")
    return path, text, starts == 1


def ensure_policy(project_root: Path, agent: str = "codex") -> bool:
    path, text, configured = policy_state(project_root, agent)
    if configured:
        return False
    separator = "" if not text else ("\n" if text.endswith("\n") else "\n\n")
    path.write_text(f"{text}{separator}{AGENTS[agent]['block']}\n", encoding="utf-8", newline="\n")
    return True


def ensure_evidence_ignored(project_root: Path, evidence_path: Path) -> bool:
    relative = evidence_path.relative_to(project_root).as_posix()
    path = project_root / ".gitignore"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    lines = text.splitlines()
    if relative in lines:
        return False
    lines.append(relative)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return True


def configuration_status(project_root: Path, agent: str = "codex") -> dict[str, Any]:
    config, evidence_path = load_config(project_root)
    validate_config_document(config, project_root)
    rules_path, _, policy = policy_state(project_root, agent)
    ignore = project_root / ".gitignore"
    ignored = ignore.is_file() and evidence_path.relative_to(project_root).as_posix() in ignore.read_text(encoding="utf-8").splitlines()
    return {
        "skill": "verify-before-push",
        "scope": "project",
        "agent": agent,
        "rules_file": str(rules_path),
        "configured": policy and ignored,
        "valid": True,
        "version": config["version"],
        "config_file": str(project_root / CONFIG_RELATIVE),
        "policy": policy,
        "evidence_ignored": ignored,
    }


def configure_project(project_root: Path, source: Path | None, agent: str = "codex") -> dict[str, Any]:
    target = project_root / CONFIG_RELATIVE
    config = load_json(source.resolve() if source else target, "Configuration")
    evidence_path = validate_config_document(config, project_root)
    policy_state(project_root, agent)
    previous = target.read_bytes() if target.is_file() else None
    write_atomic(target, config)
    changed = previous != target.read_bytes()
    changed = ensure_policy(project_root, agent) or changed
    changed = ensure_evidence_ignored(project_root, evidence_path) or changed
    state = configuration_status(project_root, agent)
    state["changed"] = changed
    return state


def validate_repository_entry(entry: Any, project_root: Path) -> tuple[str, Path, bool, bool]:
    if not isinstance(entry, dict):
        raise VerificationError("Each repository entry must be an object")
    name, value = entry.get("name"), entry.get("path")
    if not isinstance(name, str) or not name or not isinstance(value, str) or not value:
        raise VerificationError("Each repository requires non-empty name and path")
    path = resolve_inside(project_root, value, "repository")
    root = git_root(path)
    if root != path:
        raise VerificationError(f"Repository path must be its Git root: {path}")
    for flag in ("require_clean", "require_upstream_current"):
        if not isinstance(entry.get(flag, True), bool):
            raise VerificationError(f"Repository {flag} must be a boolean")
    return name, root, entry.get("require_clean", True), entry.get("require_upstream_current", True)


def repository_state(entry: Any, project_root: Path) -> dict[str, Any]:
    name, repo, require_clean, require_upstream = validate_repository_entry(entry, project_root)
    head = git(repo, "rev-parse", "HEAD").decode().strip()
    status = git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    fingerprint = hashlib.sha256()
    fingerprint.update(status)
    fingerprint.update(git(repo, "diff", "--binary", "--no-ext-diff"))
    fingerprint.update(git(repo, "diff", "--cached", "--binary", "--no-ext-diff"))
    untracked = git(repo, "ls-files", "--others", "--exclude-standard", "-z")
    for raw_name in sorted(name for name in untracked.split(b"\0") if name):
        name = raw_name.decode("utf-8", errors="surrogateescape")
        path = repo / name
        fingerprint.update(raw_name)
        if path.is_symlink():
            fingerprint.update(b"symlink\0" + os.readlink(path).encode("utf-8", errors="surrogateescape"))
        elif path.is_file():
            fingerprint.update(b"file\0")
            with path.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    fingerprint.update(chunk)
        else:
            fingerprint.update(b"other\0")
    upstream_result = run_process(
        ["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"], repo
    )
    upstream = upstream_result.stdout.decode().strip() if upstream_result.returncode == 0 else ""
    upstream_sha = ""
    ahead = behind = None
    if upstream:
        upstream_sha = git(repo, "rev-parse", upstream).decode().strip()
        counts = git(repo, "rev-list", "--left-right", "--count", f"HEAD...{upstream}").decode().split()
        ahead, behind = int(counts[0]), int(counts[1])
    state = {
        "name": name,
        "path": str(repo),
        "head": head,
        "worktree_sha256": fingerprint.hexdigest(),
        "clean": not status,
        "upstream": upstream,
        "upstream_sha": upstream_sha,
        "ahead": ahead,
        "behind": behind,
    }
    if require_clean and status:
        raise VerificationError(f"Repository {name!r} is not clean")
    if require_upstream:
        if not upstream:
            raise VerificationError(f"Repository {name!r} has no upstream")
        if behind:
            raise VerificationError(f"Repository {name!r} is behind upstream by {behind} commit(s)")
    return state


def capture_states(config: dict[str, Any], project_root: Path) -> list[dict[str, Any]]:
    states = [repository_state(entry, project_root) for entry in config["repositories"]]
    names = [state["name"] for state in states]
    paths = [state["path"] for state in states]
    if len(names) != len(set(names)) or len(paths) != len(set(paths)):
        raise VerificationError("Repository names and Git roots must be unique")
    return states


def refresh_required_upstreams(config: dict[str, Any], project_root: Path) -> None:
    fetched: set[tuple[Path, str]] = set()
    for entry in config["repositories"]:
        _, repo, _, required = validate_repository_entry(entry, project_root)
        if not required:
            continue
        branch = git(repo, "branch", "--show-current").decode().strip()
        if not branch:
            raise VerificationError(f"Repository {repo} has detached HEAD")
        remote = git(repo, "config", "--get", f"branch.{branch}.remote", check=False).decode().strip()
        if not remote or remote == ".":
            raise VerificationError(f"Repository {repo} has no fetchable upstream remote")
        key = (repo, remote)
        if key not in fetched:
            git(repo, "fetch", "--prune", remote)
            fetched.add(key)
        # A successful fetch alone does not prove that this exact tracking ref
        # still exists remotely or is included in the configured fetch refspec.
        merge = git(repo, "config", "--get-all", f"branch.{branch}.merge").decode().splitlines()
        if len(merge) != 1 or not merge[0].startswith("refs/heads/"):
            raise VerificationError("Upstream must name exactly one remote branch")
        advertised = git(repo, "ls-remote", "--exit-code", remote, merge[0]).decode().splitlines()
        records = [line.split() for line in advertised]
        if len(records) != 1 or len(records[0]) != 2 or records[0][1] != merge[0]:
            raise VerificationError("Remote upstream identity is ambiguous")
        local_sha = git(repo, "rev-parse", "@{upstream}").decode().strip()
        if local_sha != records[0][0]:
            raise VerificationError("Fetched upstream does not match fresh remote state")


def validate_check(
    entry: Any, project_root: Path, allowed_roots: list[Path]
) -> tuple[str, Path, list[str], int, bool, str]:
    if not isinstance(entry, dict):
        raise VerificationError("Each check entry must be an object")
    name = entry.get("name")
    cwd_value = entry.get("cwd", ".")
    command = entry.get("command")
    if not isinstance(name, str) or not name:
        raise VerificationError("Each check requires a non-empty name")
    if not isinstance(cwd_value, str):
        raise VerificationError(f"Check {name!r} cwd must be a string")
    if not isinstance(command, list) or not command or not all(isinstance(arg, str) and arg for arg in command):
        raise VerificationError(f"Check {name!r} command must be a non-empty string array")
    timeout = entry.get("timeout_seconds", 600)
    if not isinstance(timeout, int) or timeout < 1 or timeout > 86400:
        raise VerificationError(f"Check {name!r} timeout_seconds is invalid")
    enabled = entry.get("enabled", True)
    required = entry.get("required", True)
    if not isinstance(enabled, bool) or not isinstance(required, bool):
        raise VerificationError(f"Check {name!r} enabled and required must be booleans")
    reason = entry.get("skip_reason", "")
    if not enabled and (required or not isinstance(reason, str) or not reason.strip()):
        raise VerificationError(f"Disabled check {name!r} must be optional with skip_reason")
    cwd = resolve_inside(project_root, cwd_value, "check cwd")
    if not cwd.is_dir() or not any(cwd == root or root in cwd.parents for root in allowed_roots):
        raise VerificationError(f"Check {name!r} cwd must be inside a configured repository")
    return name, cwd, command, timeout, enabled, reason


def execute_checks(config: dict[str, Any], project_root: Path, *, pin_executables: bool = False) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    names: set[str] = set()
    allowed_roots = [validate_repository_entry(entry, project_root)[1] for entry in config["repositories"]]
    for entry in config["checks"]:
        name, cwd, command, timeout, enabled, reason = validate_check(entry, project_root, allowed_roots)
        if name in names:
            raise VerificationError(f"Duplicate check name: {name}")
        names.add(name)
        if not enabled:
            results.append({"name": name, "status": "skipped", "reason": reason})
            continue
        if pin_executables:
            command = [executable_identity(command[0], cwd)["path"], *command[1:]]
        result = run_process(command, cwd, timeout)
        status = "passed" if result.returncode == 0 else "failed"
        results.append({"name": name, "status": status, "exit_code": result.returncode})
        print(f"{name}: {status}")
        if result.returncode != 0 and bool(entry.get("required", True)):
            detail = (result.stderr or result.stdout).decode("utf-8", errors="replace").strip()
            raise VerificationError(f"Required check {name!r} failed: {detail[-500:]}")
    return results


def write_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as output:
            json.dump(value, output, indent=2, sort_keys=True)
            output.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def file_sha256(path: Path) -> str:
    fingerprint = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            fingerprint.update(chunk)
    return fingerprint.hexdigest()


def executable_identity(command: str, cwd: Path) -> dict[str, str]:
    if Path(command).is_absolute():
        path = Path(command).resolve()
    elif "/" in command or "\\" in command:
        path = (cwd / command).resolve()
    else:
        if any(not Path(entry).is_absolute() for entry in os.get_exec_path()):
            raise ReuseUnavailable("Relative or empty PATH entries cannot establish reusable executable identity")
        resolved = shutil.which(command)
        if resolved is None:
            raise VerificationError(f"Cannot resolve check executable: {command}")
        if not Path(resolved).is_absolute():
            raise ReuseUnavailable("Implicit current-directory PATH lookup cannot establish reusable executable identity")
        path = Path(resolved).resolve()
    if not path.is_file():
        raise VerificationError(f"Check executable is missing: {path}")
    return {"path": str(path), "sha256": file_sha256(path)}


def runtime_fingerprint(config: dict[str, Any], project_root: Path) -> str:
    roots = [validate_repository_entry(entry, project_root)[1] for entry in config["repositories"]]
    commands = []
    for entry in config["checks"]:
        name, cwd, command, _, enabled, _ = validate_check(entry, project_root, roots)
        if enabled:
            commands.append({"name": name, "cwd": str(cwd), "executable": executable_identity(command[0], cwd)})
    # Store only digests, never environment values (which can contain secrets).
    # This is an additional local check, not proof of external-service stability.
    environment = {key: value for key, value in os.environ.items() if key != TRUSTED_ENVIRONMENT_VARIABLE}
    return digest({
        "helper": file_sha256(Path(__file__).resolve()),
        "python": executable_identity(sys.executable, project_root),
        "python_version": sys.version,
        "prefix": sys.prefix,
        "base_prefix": sys.base_prefix,
        "platform": platform.platform(),
        "git": executable_identity("git", project_root),
        "environment_sha256": digest(environment),
        "commands": commands,
    })


def tracking_identity(repo: Path) -> dict[str, str]:
    branch = git(repo, "symbolic-ref", "--quiet", "HEAD").decode().strip()
    short_branch = git(repo, "branch", "--show-current").decode().strip()
    remote = git(repo, "config", "--get", f"branch.{short_branch}.remote").decode().strip()
    if not remote or remote == ".":
        raise VerificationError("Reuse requires a fetchable upstream remote")
    # URL values may contain credentials. Bind their complete identities without
    # storing those values in evidence or displaying them.
    remote_configuration = {
        "fetch_urls": git(repo, "remote", "get-url", "--all", remote).decode().splitlines(),
        "push_urls": git(repo, "remote", "get-url", "--push", "--all", remote).decode().splitlines(),
        "fetch_refspecs": git(repo, "config", "--get-all", f"remote.{remote}.fetch").decode().splitlines(),
        "branch_push_remote": git(repo, "config", "--get", f"branch.{short_branch}.pushRemote", check=False).decode().strip(),
        "push_default": git(repo, "config", "--get", "remote.pushDefault", check=False).decode().strip(),
    }
    return {
        "path": str(repo),
        "git_dir": git(repo, "rev-parse", "--absolute-git-dir").decode().strip(),
        "branch": branch,
        "remote": remote,
        "merge": git(repo, "config", "--get-all", f"branch.{short_branch}.merge").decode().strip(),
        "remote_sha256": digest(remote_configuration),
    }


def reuse_identity(
    config: dict[str, Any], project_root: Path, trusted_environment: str | None,
) -> dict[str, Any] | None:
    if not config.get("reuse_verified_results", False) or trusted_environment is None:
        return None
    if not isinstance(trusted_environment, str) or SHA256.fullmatch(trusted_environment) is None:
        raise VerificationError("Trusted environment fingerprint must be a lowercase SHA-256 digest")
    repositories = [validate_repository_entry(entry, project_root) for entry in config["repositories"]]
    if not all(required for _, _, _, required in repositories):
        return None
    try:
        runtime = runtime_fingerprint(config, project_root)
    except ReuseUnavailable:
        return None
    return {
        "runtime_sha256": runtime,
        "environment_sha256": trusted_environment,
        "tracking": [tracking_identity(repo) for _, repo, _, _ in repositories],
    }


def validate_results(config: dict[str, Any], results: Any, project_root: Path, *, reusable: bool) -> None:
    if not isinstance(results, list) or len(results) != len(config["checks"]):
        raise VerificationError("Evidence must contain exactly the configured check results")
    by_name: dict[str, dict[str, Any]] = {}
    for item in results:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str) or item["name"] in by_name:
            raise VerificationError("Evidence check names must be unique strings")
        by_name[item["name"]] = item
    roots = [validate_repository_entry(entry, project_root)[1] for entry in config["repositories"]]
    for entry in config["checks"]:
        name, _, _, _, enabled, reason = validate_check(entry, project_root, roots)
        item = by_name.get(name)
        if item is None:
            raise VerificationError(f"Evidence is missing check {name!r}")
        if not enabled:
            if item != {"name": name, "status": "skipped", "reason": reason}:
                raise VerificationError(f"Evidence skip does not match configured check {name!r}")
            continue
        if set(item) != {"name", "status", "exit_code"} or type(item["exit_code"]) is not int:
            raise VerificationError(f"Evidence result is malformed for check {name!r}")
        status = "passed" if item["exit_code"] == 0 else "failed"
        if item["status"] != status:
            raise VerificationError(f"Evidence status and exit code disagree for check {name!r}")
        if status != "passed" and (reusable or entry.get("required", True)):
            raise VerificationError(f"Check {name!r} is not recorded as passed")


def delivered_same_head(previous: Any, current: list[dict[str, Any]]) -> bool:
    if not isinstance(previous, list) or len(previous) != len(current):
        return False
    delivery_fields = {"upstream_sha", "ahead", "behind"}
    for old, new in zip(previous, current):
        if not isinstance(old, dict) or set(old) != set(new):
            return False
        if canonical_json(old) == canonical_json(new):
            continue
        if canonical_json({key: value for key, value in old.items() if key not in delivery_fields}) != canonical_json({
            key: value for key, value in new.items() if key not in delivery_fields
        }):
            return False
        if (not old["upstream"] or type(old["ahead"]) is not int or old["ahead"] <= 0
                or type(old["behind"]) is not int or old["behind"] != 0
                or new["upstream_sha"] != new["head"] or new["ahead"] != 0 or new["behind"] != 0
                or not isinstance(old["upstream_sha"], str)
                or re.fullmatch(r"[0-9a-f]{40}(?:[0-9a-f]{24})?", old["upstream_sha"]) is None
                or old["upstream_sha"] == new["head"]):
            return False
        repo = Path(new["path"])
        ancestor = run_process(["git", "-C", str(repo), "merge-base", "--is-ancestor", old["upstream_sha"], new["head"]], repo)
        if ancestor.returncode != 0:
            return False
        count = git(repo, "rev-list", "--count", f"{old['upstream_sha']}..{new['head']}").decode().strip()
        if int(count) != old["ahead"]:
            return False
    return True


def validate_receipt(
    config: dict[str, Any], evidence: dict[str, Any], current: list[dict[str, Any]],
    identity: dict[str, Any] | None, project_root: Path, *, for_reuse: bool = False,
) -> None:
    version = evidence.get("version")
    if type(version) is not int or version not in {1, 2} or evidence.get("config_sha256") != digest(config):
        raise VerificationError("Evidence does not match current configuration")
    if not isinstance(evidence.get("checked_at"), str):
        raise VerificationError("Evidence verification time is missing")
    try:
        checked_at = datetime.fromisoformat(evidence["checked_at"].replace("Z", "+00:00"))
    except ValueError as error:
        raise VerificationError("Evidence verification time is malformed") from error
    if checked_at.tzinfo is None:
        raise VerificationError("Evidence verification time must include timezone")
    if version == 1:
        if set(evidence) != {"version", "config_sha256", "checked_at", "repositories", "checks"}:
            raise VerificationError("Legacy evidence has an invalid structure")
        if for_reuse:
            raise VerificationError("Legacy evidence cannot authorize result reuse")
        if canonical_json(evidence.get("repositories")) != canonical_json(current):
            raise VerificationError("Evidence is stale for current repository state")
    else:
        expected_keys = {"version", "config_sha256", "checked_at", "repositories", "checks", "reuse_identity", "receipt_sha256"}
        if set(evidence) != expected_keys:
            raise VerificationError("Reusable evidence has an invalid structure")
        payload = {key: value for key, value in evidence.items() if key != "receipt_sha256"}
        if evidence.get("receipt_sha256") != digest(payload):
            raise VerificationError("Reusable evidence digest does not match its contents")
        if identity is None or evidence.get("reuse_identity") != identity:
            raise VerificationError("Reusable evidence runtime, environment, or tracking identity changed or is unavailable")
        if not delivered_same_head(evidence.get("repositories"), current):
            raise VerificationError("Evidence is stale: only delivery of the same checked HEAD may differ")
    validate_results(config, evidence.get("checks"), project_root, reusable=version == 2)


def run_verification(project_root: Path, trusted_environment: str | None = None) -> Path:
    config, evidence_path = load_config(project_root)
    reused = False
    try:
        validate_config_document(config, project_root)
        refresh_required_upstreams(config, project_root)
        before = capture_states(config, project_root)
        identity = reuse_identity(config, project_root, trusted_environment)
        if identity is not None and evidence_path.is_file():
            try:
                evidence = load_json(evidence_path, "Evidence")
                validate_receipt(config, evidence, before, identity, project_root, for_reuse=True)
            except VerificationError:
                # An invalid cache is not a pass: fall back to the full checks.
                pass
            else:
                if before != capture_states(config, project_root) or identity != reuse_identity(config, project_root, trusted_environment):
                    raise VerificationError("State changed while validating reusable evidence")
                reused = True
                print(f"Verified results reused without rewriting evidence: {evidence_path}")
                return evidence_path
    finally:
        # Any failure or full rerun invalidates the previous receipt. A genuine
        # reuse is read-only and retains the original verification timestamp.
        if not reused:
            evidence_path.unlink(missing_ok=True)
    checks = execute_checks(config, project_root, pin_executables=identity is not None)
    refresh_required_upstreams(config, project_root)
    after = capture_states(config, project_root)
    if before != after or identity != reuse_identity(config, project_root, trusted_environment):
        raise VerificationError("Git, runtime, or environment state changed while checks were running")
    current_config, _ = load_config(project_root)
    if digest(config) != digest(current_config):
        raise VerificationError("Configuration changed while checks were running")
    # Legacy semantics allow failed optional checks, but they must not become a
    # reusable success. Keep those complete-run results on the strict v1 path.
    reusable = identity is not None and all(item["status"] != "failed" for item in checks)
    evidence = {
        "version": 2 if reusable else 1,
        "config_sha256": digest(config),
        "checked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "repositories": after,
        "checks": checks,
    }
    if reusable:
        evidence["reuse_identity"] = identity
        evidence["receipt_sha256"] = digest(evidence)
    write_atomic(evidence_path, evidence)
    print(f"Evidence written: {evidence_path}")
    return evidence_path


def verify_evidence(project_root: Path, repository: Path | None = None, trusted_environment: str | None = None) -> bool:
    config, evidence_path = load_config(project_root)
    configured_roots = [validate_repository_entry(entry, project_root)[1] for entry in config["repositories"]]
    if repository is not None:
        candidate = git_root(repository.resolve())
        if candidate not in configured_roots:
            print(f"Repository is not gated: {candidate}")
            return False
    validate_config_document(config, project_root)
    refresh_required_upstreams(config, project_root)
    evidence = load_json(evidence_path, "Evidence")
    current = capture_states(config, project_root)
    identity = reuse_identity(config, project_root, trusted_environment) if evidence.get("version") == 2 else None
    validate_receipt(config, evidence, current, identity, project_root)
    print(f"Evidence is current: {evidence_path}")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run and validate Git-state-bound pre-push evidence.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("run", "verify", "gate", "configure", "status", "migrate"):
        child = subparsers.add_parser(command)
        child.add_argument("--project-root", type=Path, default=Path.cwd())
        if command in {"run", "verify", "gate"}:
            child.add_argument("--trusted-environment-fingerprint", default=os.environ.get(TRUSTED_ENVIRONMENT_VARIABLE))
        if command == "gate":
            child.add_argument("--repository", type=Path, required=True)
        if command == "configure":
            child.add_argument("--config-source", type=Path)
        if command in {"configure", "status", "migrate"}:
            child.add_argument("--agent", choices=sorted(AGENTS), default="codex")
            child.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    project_root = args.project_root.resolve()
    try:
        if args.command == "run":
            run_verification(project_root, args.trusted_environment_fingerprint)
        elif args.command == "verify":
            verify_evidence(project_root, trusted_environment=args.trusted_environment_fingerprint)
        elif args.command == "gate":
            verify_evidence(project_root, args.repository, args.trusted_environment_fingerprint)
        elif args.command == "configure":
            state = configure_project(project_root, args.config_source, args.agent)
            print(json.dumps(state, sort_keys=True) if args.json else f"Configured: {state['config_file']}")
        elif args.command == "status":
            state = configuration_status(project_root, args.agent)
            print(json.dumps(state, sort_keys=True) if args.json else f"Configured: {state['configured']}")
            if not state["configured"]:
                return 1
        else:
            state = configure_project(project_root, None, args.agent)
            print(json.dumps(state, sort_keys=True) if args.json else f"Configuration is version {state['version']}")
        return 0
    except VerificationError as error:
        print(f"VERIFICATION_FAILED: {error}", file=sys.stderr)
        return 1
    except Exception as error:  # fail closed for unexpected verifier failures
        print(f"VERIFICATION_FAILED: unexpected {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
