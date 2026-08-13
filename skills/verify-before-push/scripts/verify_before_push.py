from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CONFIG_RELATIVE = Path(".agents/verify-before-push/config.json")
DEFAULT_EVIDENCE = Path(".agents/verify-before-push/evidence.json")
POLICY_START = "<!-- verify-before-push:start -->"
POLICY_END = "<!-- verify-before-push:end -->"
POLICY_BLOCK = """<!-- verify-before-push:start -->
## Verification before push

Use `$verify-before-push` before pushing protected repositories. Run the
project-declared checks and require current evidence bound to the exact Git
commits and worktrees being pushed. Treat missing, failed, malformed, or
stale evidence as a stop condition for a protected push.
<!-- verify-before-push:end -->"""


class VerificationError(RuntimeError):
    pass


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
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
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
    if config.get("version") != 1:
        raise VerificationError("Configuration version must be 1")
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
    return config, evidence_path


def validate_config_document(config: dict[str, Any], project_root: Path) -> Path:
    if config.get("version") != 1:
        raise VerificationError("Configuration version must be 1")
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
    names: set[str] = set()
    for entry in checks:
        name = validate_check(entry, project_root, roots)[0]
        if name in names:
            raise VerificationError(f"Duplicate check name: {name}")
        names.add(name)
    return evidence_path


def policy_state(project_root: Path) -> tuple[Path, str, bool]:
    path = project_root / "AGENTS.md"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    starts, ends = text.count(POLICY_START), text.count(POLICY_END)
    if starts != ends or starts > 1 or (starts == 1 and text.index(POLICY_START) > text.index(POLICY_END)):
        raise VerificationError("AGENTS.md contains malformed or duplicate managed markers")
    return path, text, starts == 1


def ensure_policy(project_root: Path) -> bool:
    path, text, configured = policy_state(project_root)
    if configured:
        return False
    separator = "" if not text else ("\n" if text.endswith("\n") else "\n\n")
    path.write_text(f"{text}{separator}{POLICY_BLOCK}\n", encoding="utf-8", newline="\n")
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


def configuration_status(project_root: Path) -> dict[str, Any]:
    config, evidence_path = load_config(project_root)
    validate_config_document(config, project_root)
    _, _, policy = policy_state(project_root)
    ignore = project_root / ".gitignore"
    ignored = ignore.is_file() and evidence_path.relative_to(project_root).as_posix() in ignore.read_text(encoding="utf-8").splitlines()
    return {
        "skill": "verify-before-push",
        "scope": "project",
        "configured": policy and ignored,
        "valid": True,
        "version": config["version"],
        "config_file": str(project_root / CONFIG_RELATIVE),
        "policy": policy,
        "evidence_ignored": ignored,
    }


def configure_project(project_root: Path, source: Path | None) -> dict[str, Any]:
    target = project_root / CONFIG_RELATIVE
    config = load_json(source.resolve() if source else target, "Configuration")
    evidence_path = validate_config_document(config, project_root)
    policy_state(project_root)
    previous = target.read_bytes() if target.is_file() else None
    write_atomic(target, config)
    changed = previous != target.read_bytes()
    changed = ensure_policy(project_root) or changed
    changed = ensure_evidence_ignored(project_root, evidence_path) or changed
    state = configuration_status(project_root)
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
    return name, root, bool(entry.get("require_clean", True)), bool(entry.get("require_upstream_current", True))


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


def execute_checks(config: dict[str, Any], project_root: Path) -> list[dict[str, Any]]:
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


def run_verification(project_root: Path) -> Path:
    config, evidence_path = load_config(project_root)
    # A failed or interrupted rerun must not leave older evidence looking valid.
    try:
        evidence_path.unlink()
    except FileNotFoundError:
        pass
    refresh_required_upstreams(config, project_root)
    before = capture_states(config, project_root)
    checks = execute_checks(config, project_root)
    after = capture_states(config, project_root)
    if before != after:
        raise VerificationError("Git state changed while checks were running")
    evidence = {
        "version": 1,
        "config_sha256": digest(config),
        "checked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "repositories": after,
        "checks": checks,
    }
    write_atomic(evidence_path, evidence)
    print(f"Evidence written: {evidence_path}")
    return evidence_path


def verify_evidence(project_root: Path, repository: Path | None = None) -> bool:
    config, evidence_path = load_config(project_root)
    configured_roots = [validate_repository_entry(entry, project_root)[1] for entry in config["repositories"]]
    if repository is not None:
        candidate = git_root(repository.resolve())
        if candidate not in configured_roots:
            print(f"Repository is not gated: {candidate}")
            return False
    refresh_required_upstreams(config, project_root)
    evidence = load_json(evidence_path, "Evidence")
    if evidence.get("version") != 1 or evidence.get("config_sha256") != digest(config):
        raise VerificationError("Evidence does not match current configuration")
    current = capture_states(config, project_root)
    if evidence.get("repositories") != current:
        raise VerificationError("Evidence is stale for current repository state")
    results = evidence.get("checks")
    if not isinstance(results, list):
        raise VerificationError("Evidence check results are missing")
    by_name = {item.get("name"): item for item in results if isinstance(item, dict)}
    allowed_roots = [validate_repository_entry(entry, project_root)[1] for entry in config["repositories"]]
    for entry in config["checks"]:
        name, _, _, _, enabled, _ = validate_check(entry, project_root, allowed_roots)
        if enabled and bool(entry.get("required", True)) and by_name.get(name, {}).get("status") != "passed":
            raise VerificationError(f"Required check {name!r} is not recorded as passed")
    print(f"Evidence is current: {evidence_path}")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run and validate Git-state-bound pre-push evidence.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("run", "verify", "gate", "configure", "status", "migrate"):
        child = subparsers.add_parser(command)
        child.add_argument("--project-root", type=Path, default=Path.cwd())
        if command == "gate":
            child.add_argument("--repository", type=Path, required=True)
        if command == "configure":
            child.add_argument("--config-source", type=Path)
        if command in {"configure", "status", "migrate"}:
            child.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    project_root = args.project_root.resolve()
    try:
        if args.command == "run":
            run_verification(project_root)
        elif args.command == "verify":
            verify_evidence(project_root)
        elif args.command == "gate":
            verify_evidence(project_root, args.repository)
        elif args.command == "configure":
            state = configure_project(project_root, args.config_source)
            print(json.dumps(state, sort_keys=True) if args.json else f"Configured: {state['config_file']}")
        elif args.command == "status":
            state = configuration_status(project_root)
            print(json.dumps(state, sort_keys=True) if args.json else f"Configured: {state['configured']}")
            if not state["configured"]:
                return 1
        else:
            state = configure_project(project_root, None)
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
