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


SCHEMA_VERSION = 2
TAG_PATTERN = re.compile(
    r"^v([0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?)$"
)
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
MAX_OUTPUT_CHARS = 2000
REQUIRED_FILES = (
    "skill-catalog.json",
    ".claude-plugin/plugin.json",
    ".codex-plugin/plugin.json",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "scripts/validate_skills.py",
    "scripts/security_checks.py",
    "scripts/build_release.py",
    ".github/workflows/release.yml",
)
CHECKS = (
    ("structural-validation", ("scripts/validate_skills.py",), 180),
    ("security", ("scripts/security_checks.py",), 180),
    ("unit-tests", ("-m", "unittest", "discover", "-s", "tests", "-v"), 900),
)
REQUIRED_GATES = {
    "local_release_check",
    "locked_holdout",
    "consumer_smoke",
    "supported_platform_ci",
    "review",
}
SUPPORTED_PLATFORMS = ("linux", "macos", "windows")
SUPPORTED_AGENTS = ("claude-code", "codex")
POST_PUBLICATION_STEPS = [
    "audit the published release, assets, checksums, and attestations",
    "fetch and prune remote refs after merge and publication",
    "run cleanup-plan for every temporary feature or release branch",
    "switch to the configured primary branch and make it current with its upstream",
    "delete only branches that cleanup-plan proves represented upstream",
    "finish with a clean worktree on the current primary branch",
]
REDACTIONS = (
    re.compile(r"(?i)(authorization\s*:\s*)(\S+)"),
    re.compile(r"(?i)((?:password|secret|token|api[_-]?key)\s*[=:]\s*)(\S+)"),
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
)


class ReleaseError(RuntimeError):
    pass


def canonical_digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_object(path: Path, label: str | None = None) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ReleaseError(f"{label or path} is missing: {path}") from error
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReleaseError(f"{label or path} is not valid UTF-8 JSON: {error}") from error
    if not isinstance(value, dict):
        raise ReleaseError(f"{label or path} must contain a JSON object")
    return value


def safe_project_file(root: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ReleaseError(f"{label} must be a repository-relative POSIX path")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ReleaseError(f"{label} escapes the repository")
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise ReleaseError(f"{label} escapes the repository") from error
    if not path.is_file():
        raise ReleaseError(f"{label} is missing: {value}")
    return path


def run_git(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *arguments],
            cwd=root,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ReleaseError(f"Git inspection failed: {error}") from error


def git_text(root: Path, *arguments: str) -> str | None:
    result = run_git(root, *arguments)
    return result.stdout.strip() if result.returncode == 0 else None


def repository_operation(root: Path) -> str | None:
    markers = {
        "MERGE_HEAD": "merge",
        "CHERRY_PICK_HEAD": "cherry-pick",
        "REVERT_HEAD": "revert",
        "rebase-merge": "rebase",
        "rebase-apply": "rebase",
    }
    for marker, name in markers.items():
        value = git_text(root, "rev-parse", "--git-path", marker)
        if value and (Path(value) if Path(value).is_absolute() else root / value).exists():
            return name
    return None


def repository_state(root: Path) -> dict[str, Any]:
    if git_text(root, "rev-parse", "--is-inside-work-tree") != "true":
        return {"is_git_repository": False}
    branch = git_text(root, "branch", "--show-current") or None
    head = git_text(root, "rev-parse", "HEAD")
    upstream = git_text(root, "rev-parse", "--abbrev-ref", "@{upstream}")
    ahead = behind = None
    if upstream:
        counts = git_text(root, "rev-list", "--left-right", "--count", f"HEAD...{upstream}")
        if counts:
            ahead, behind = (int(item) for item in counts.split())
    return {
        "is_git_repository": True,
        "branch": branch,
        "head": head,
        "upstream": upstream,
        "ahead": ahead,
        "behind": behind,
        "dirty": bool(git_text(root, "status", "--porcelain=v1", "--untracked-files=all")),
        "operation": repository_operation(root),
    }


def inspect(root: Path, tag: str | None = None) -> dict[str, Any]:
    root = root.resolve()
    blockers: list[str] = []
    warnings: list[str] = []
    missing = [name for name in REQUIRED_FILES if not (root / name).is_file()]
    blockers.extend(f"required file is missing: {name}" for name in missing)
    version = None
    versions: dict[str, Any] = {}
    if tag is not None:
        match = TAG_PATTERN.fullmatch(tag)
        if not match:
            blockers.append(f"invalid release tag: {tag}")
        else:
            version = match.group(1)
    try:
        catalog = load_object(root / "skill-catalog.json", "skill catalog")
        versions["catalog"] = catalog.get("collection_version")
        holdout = catalog.get("release_holdout")
        if not isinstance(holdout, dict):
            raise ReleaseError("skill catalog release_holdout must be an object")
        holdout_path = safe_project_file(root, holdout.get("path"), "release_holdout.path")
        if not SHA256_PATTERN.fullmatch(str(holdout.get("sha256", ""))):
            raise ReleaseError("release_holdout.sha256 is missing or invalid")
        if canonical_digest(load_object(holdout_path, "release holdout")) != holdout["sha256"]:
            raise ReleaseError("release holdout digest does not match the catalog")
        entries = catalog.get("skills")
        if not isinstance(entries, list):
            raise ReleaseError("skill catalog skills must be an array")
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
                raise ReleaseError(f"skill catalog entry {index} is malformed")
            skill_root = safe_project_file(
                root,
                f"{entry.get('path')}/collection-metadata.json",
                f"skills[{index}].path",
            )
            versions[f"skill:{entry['name']}"] = load_object(
                skill_root, f"metadata for {entry['name']}"
            ).get("version")
    except ReleaseError as error:
        blockers.append(str(error))
    try:
        versions["plugin"] = load_object(
            root / ".codex-plugin" / "plugin.json", "plugin manifest"
        ).get("version")
    except ReleaseError as error:
        blockers.append(str(error))
    try:
        versions["claude_plugin"] = load_object(
            root / ".claude-plugin" / "plugin.json", "Claude Code plugin manifest"
        ).get("version")
    except ReleaseError as error:
        blockers.append(str(error))
    if version:
        mismatched = {name: value for name, value in versions.items() if value != version}
        if mismatched:
            blockers.append(f"release versions do not all match {version}: {mismatched}")
        try:
            changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
            if not re.search(rf"^## \[{re.escape(version)}\](?:\s|$)", changelog, re.MULTILINE):
                blockers.append(f"CHANGELOG.md has no versioned heading for {version}")
        except (OSError, UnicodeDecodeError) as error:
            blockers.append(f"CHANGELOG.md cannot be read: {error}")
    state = repository_state(root)
    if not state.get("is_git_repository"):
        blockers.append("project root is not a Git repository")
    else:
        if state.get("operation"):
            blockers.append(f"repository has an in-progress {state['operation']}")
        if not state.get("branch"):
            blockers.append("repository is on a detached HEAD")
        if not state.get("upstream"):
            blockers.append("current branch has no upstream")
        if state.get("behind"):
            blockers.append(f"current branch is behind upstream by {state['behind']} commit(s)")
        if state.get("ahead") and state.get("behind"):
            blockers.append("current branch has diverged from upstream")
        elif state.get("ahead"):
            warnings.append(f"current branch is ahead of upstream by {state['ahead']} commit(s)")
        if state.get("dirty"):
            warnings.append("worktree is dirty; release evidence must be rebound after changes")
    if tag and state.get("is_git_repository"):
        tag_type = git_text(root, "cat-file", "-t", f"refs/tags/{tag}")
        if tag_type is not None:
            blockers.append(f"tag {tag} already exists; use audit-release instead of republishing it")
    result = {
        "schema_version": SCHEMA_VERSION,
        "mode": "plan" if tag else "status",
        "project_root": str(root),
        "tag": tag,
        "target_version": version,
        "versions": versions,
        "repository": state,
        "blockers": blockers,
        "warnings": warnings,
        "ready_for_local_checks": not blockers,
        "post_publication_steps": POST_PUBLICATION_STEPS,
        "mutates_repository": False,
    }
    result["report_sha256"] = canonical_digest(result)
    return result


def redact_output(value: str) -> str:
    text = "".join(character if character in "\n\r\t" or ord(character) >= 32 else "?" for character in value)
    for pattern in REDACTIONS:
        text = pattern.sub(lambda match: (match.group(1) if match.lastindex else "") + "[REDACTED]", text)
    if len(text) > MAX_OUTPUT_CHARS:
        text = "[truncated]\n" + text[-MAX_OUTPUT_CHARS:]
    return text.strip()


def run_command(root: Path, name: str, command: list[str], timeout: int) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            cwd=root,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            timeout=timeout,
        )
        combined = f"stdout\0{result.stdout}\0stderr\0{result.stderr}"
        return {
            "name": name,
            "returncode": result.returncode,
            "timed_out": False,
            "output_sha256": hashlib.sha256(combined.encode("utf-8")).hexdigest(),
            "output_tail": redact_output((result.stdout + "\n" + result.stderr).strip()),
            "passed": result.returncode == 0,
        }
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout or b""
        stderr = error.stderr or b""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        output = stdout + "\n" + stderr
        return {
            "name": name,
            "returncode": None,
            "timed_out": True,
            "output_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
            "output_tail": redact_output(output),
            "passed": False,
        }
    except OSError as error:
        output = str(error)
        return {
            "name": name,
            "returncode": None,
            "timed_out": False,
            "output_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
            "output_tail": redact_output(output),
            "passed": False,
        }


def prepare_output(
    root: Path,
    output_root: Path | None,
    blockers: list[str],
    *,
    create: bool = True,
) -> tuple[Path | None, tempfile.TemporaryDirectory[str] | None]:
    if output_root is None:
        if not create:
            return None, None
        temporary = tempfile.TemporaryDirectory(prefix="skill-release-")
        return Path(temporary.name), temporary
    output = output_root.resolve()
    if output == root or output.is_relative_to(root):
        blockers.append("explicit output root must be outside the repository")
        return None, None
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        blockers.append("explicit output root must be absent or an empty directory")
        return None, None
    if create:
        output.mkdir(parents=True, exist_ok=True)
    return output, None


def check(root: Path, tag: str, output_root: Path | None) -> dict[str, Any]:
    root = root.resolve()
    plan = inspect(root, tag)
    blockers = list(plan["blockers"])
    results: list[dict[str, Any]] = []
    if plan["repository"].get("dirty"):
        blockers.append("local release checks require a clean worktree")
    output: Path | None = None
    temporary: tempfile.TemporaryDirectory[str] | None = None
    output, temporary = prepare_output(
        root, output_root, blockers, create=not blockers
    )
    try:
        if not blockers and output is not None:
            for name, arguments, timeout in CHECKS:
                command = [sys.executable, *arguments]
                result = run_command(root, name, command, timeout)
                results.append(result)
                if not result["passed"]:
                    break
            if len(results) == len(CHECKS) and all(item["passed"] for item in results):
                build = run_command(
                    root,
                    "build",
                    [
                        sys.executable,
                        "scripts/build_release.py",
                        "--source",
                        str(root),
                        "--tag",
                        tag,
                        "--output",
                        str(output),
                    ],
                    300,
                )
                results.append(build)
                if build["passed"]:
                    results.append(
                        run_command(
                            root,
                            "checksums",
                            [
                                sys.executable,
                                "scripts/build_release.py",
                                "--verify",
                                str(output / "SHA256SUMS"),
                            ],
                            120,
                        )
                    )
        post_check_state = repository_state(root)
        if not blockers and post_check_state.get("dirty"):
            blockers.append("local release checks mutated the repository worktree")
        passed = not blockers and len(results) == len(CHECKS) + 2 and all(
            item["passed"] for item in results
        )
        response = {
            **plan,
            "mode": "check",
            "blockers": blockers,
            "ready_for_local_checks": not blockers,
            "checks": results,
            "passed": passed,
            "external_gates_remaining": [
                "locked model-backed holdout and baseline comparison",
                "consumer installation smoke test",
                "supported-platform CI",
                "reviewed immutable tag and GitHub attested publication",
            ],
            "post_check_repository": post_check_state,
        }
        response.pop("report_sha256", None)
        response["evidence"] = {
            "tag": tag,
            "commit": plan["repository"].get("head"),
            "checks_sha256": canonical_digest(results),
        }
        response["report_sha256"] = canonical_digest(response)
        return response
    finally:
        if temporary is not None:
            temporary.cleanup()


def verify_digest(value: dict[str, Any], field: str, label: str) -> None:
    expected = value.get(field)
    if not isinstance(expected, str) or not SHA256_PATTERN.fullmatch(expected):
        raise ReleaseError(f"{label} has no valid {field}")
    actual = canonical_digest({key: item for key, item in value.items() if key != field})
    if actual != expected:
        raise ReleaseError(f"{label} digest does not match its content")


def verify_evidence(root: Path, tag: str, evidence_path: Path) -> dict[str, Any]:
    root = root.resolve()
    evidence = load_object(evidence_path.resolve(), "release evidence")
    verify_digest(evidence, "evidence_sha256", "release evidence")
    required = {"schema_version", "tag", "commit", "gates", "evidence_sha256"}
    if set(evidence) != required or evidence["schema_version"] != 1:
        raise ReleaseError("release evidence has an unsupported contract")
    if evidence["tag"] != tag or not TAG_PATTERN.fullmatch(tag):
        raise ReleaseError("release evidence tag does not match the requested tag")
    commit = evidence["commit"]
    head = git_text(root, "rev-parse", "HEAD")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit) or commit != head:
        raise ReleaseError("release evidence is not bound to the current HEAD")
    gates = evidence["gates"]
    if not isinstance(gates, dict) or set(gates) != REQUIRED_GATES:
        raise ReleaseError("release evidence must contain every required gate exactly once")
    for name in sorted(REQUIRED_GATES):
        gate = gates[name]
        if not isinstance(gate, dict) or gate.get("passed") is not True:
            raise ReleaseError(f"release gate did not pass: {name}")
        if gate.get("commit") != commit:
            raise ReleaseError(f"release gate is bound to another commit: {name}")
        verify_digest(gate, "evidence_sha256", f"release gate {name}")
    platforms = gates["supported_platform_ci"].get("platforms")
    if platforms != list(SUPPORTED_PLATFORMS):
        raise ReleaseError("supported-platform CI evidence is incomplete")
    agents = gates["consumer_smoke"].get("agents")
    if agents != list(SUPPORTED_AGENTS):
        raise ReleaseError("consumer-smoke evidence must cover Claude Code and Codex")
    holdout_digest = gates["locked_holdout"].get("assertion_digest")
    if not SHA256_PATTERN.fullmatch(str(holdout_digest or "")):
        raise ReleaseError("locked holdout evidence has no assertion digest")
    result = {
        "schema_version": SCHEMA_VERSION,
        "mode": "verify-evidence",
        "valid": True,
        "tag": tag,
        "commit": commit,
        "gates": sorted(REQUIRED_GATES),
        "evidence_sha256": evidence["evidence_sha256"],
        "mutates_repository": False,
    }
    result["report_sha256"] = canonical_digest(result)
    return result


def parse_checksums(path: Path) -> dict[str, str]:
    checksums: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise ReleaseError(f"SHA256SUMS cannot be read: {error}") from error
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9._+-]+)", line)
        if not match or match.group(2) in checksums:
            raise ReleaseError("SHA256SUMS is malformed or duplicated")
        checksums[match.group(2)] = match.group(1)
    return checksums


def run_json_command(command: list[str], timeout: int, label: str) -> Any:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ReleaseError(f"{label} failed: {error}") from error
    if result.returncode != 0:
        detail = redact_output(result.stderr.decode("utf-8", errors="replace"))
        raise ReleaseError(f"{label} failed: {detail[-500:]}")
    try:
        return json.loads(result.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReleaseError(f"{label} did not return JSON") from error


def audit_release(root: Path, tag: str, repository: str) -> dict[str, Any]:
    root = root.resolve()
    match = TAG_PATTERN.fullmatch(tag)
    if not match or not REPOSITORY_PATTERN.fullmatch(repository):
        raise ReleaseError("audit-release requires a valid tag and owner/repository")
    if git_text(root, "cat-file", "-t", f"refs/tags/{tag}") != "tag":
        raise ReleaseError("release tag must exist locally and be annotated")
    commit = git_text(root, "rev-list", "-n", "1", tag)
    if not commit:
        raise ReleaseError("release tag commit cannot be resolved")
    release = run_json_command(
        [
            "gh",
            "release",
            "view",
            tag,
            "--repo",
            repository,
            "--json",
            "url,tagName,isDraft,isPrerelease,assets",
        ],
        60,
        "GitHub release inspection",
    )
    if (
        not isinstance(release, dict)
        or release.get("tagName") != tag
        or release.get("isDraft") is not False
        or release.get("isPrerelease") is not False
    ):
        raise ReleaseError("GitHub release is missing, draft, prerelease, or bound to another tag")
    version = match.group(1)
    names = {
        f"kolabse-skills-v{version}.zip",
        f"kolabse-skills-v{version}.tar.gz",
        "release-manifest.json",
        "SHA256SUMS",
    }
    assets = release.get("assets")
    if not isinstance(assets, list) or {item.get("name") for item in assets if isinstance(item, dict)} != names:
        raise ReleaseError("GitHub release assets are incomplete or unexpected")
    with tempfile.TemporaryDirectory(prefix="skill-release-audit-") as directory:
        output = Path(directory)
        try:
            download = subprocess.run(
                ["gh", "release", "download", tag, "--repo", repository, "--dir", str(output)],
                capture_output=True,
                check=False,
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ReleaseError(f"GitHub release download failed: {error}") from error
        if download.returncode != 0:
            detail = redact_output(download.stderr.decode("utf-8", errors="replace"))
            raise ReleaseError(f"GitHub release download failed: {detail[-500:]}")
        if {item.name for item in output.iterdir() if item.is_file()} != names:
            raise ReleaseError("downloaded release assets are incomplete or unexpected")
        checksums = parse_checksums(output / "SHA256SUMS")
        if set(checksums) != names - {"SHA256SUMS"}:
            raise ReleaseError("SHA256SUMS does not cover every payload asset exactly once")
        observed = {name: file_digest(output / name) for name in sorted(names)}
        for name, expected in checksums.items():
            if observed[name] != expected:
                raise ReleaseError(f"published checksum mismatch: {name}")
        api_digests = {
            item["name"]: str(item.get("digest", "")).removeprefix("sha256:")
            for item in assets
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        }
        if api_digests != observed:
            raise ReleaseError("GitHub asset digests do not match downloaded bytes")
        manifest = load_object(output / "release-manifest.json", "release manifest")
        if manifest.get("release") != tag or manifest.get("source_commit") != commit:
            raise ReleaseError("release manifest is bound to another tag or commit")
        attestation = run_json_command(
            [
                "gh",
                "attestation",
                "verify",
                str(output / f"kolabse-skills-v{version}.zip"),
                "--repo",
                repository,
                "--format",
                "json",
            ],
            120,
            "release attestation verification",
        )
        rows = attestation if isinstance(attestation, list) else []
        matched = False
        for row in rows:
            verification = row.get("verificationResult", {}) if isinstance(row, dict) else {}
            statement = verification.get("statement", {}) if isinstance(verification, dict) else {}
            subjects = statement.get("subject", []) if isinstance(statement, dict) else []
            subject_digests = {
                item.get("name"): item.get("digest", {}).get("sha256")
                for item in subjects
                if isinstance(item, dict) and isinstance(item.get("digest"), dict)
            }
            signature = verification.get("signature", {}) if isinstance(verification, dict) else {}
            certificate = signature.get("certificate", {}) if isinstance(signature, dict) else {}
            if (
                subject_digests == observed
                and certificate.get("githubWorkflowRepository") == repository
                and certificate.get("sourceRepositoryURI") == f"https://github.com/{repository}"
                and certificate.get("sourceRepositoryDigest") == commit
                and certificate.get("sourceRepositoryRef") == f"refs/tags/{tag}"
                and certificate.get("githubWorkflowName") == "Release artifacts"
            ):
                matched = True
                break
        if not matched:
            raise ReleaseError("no attestation binds every asset to the release tag and commit")
    result = {
        "schema_version": SCHEMA_VERSION,
        "mode": "audit-release",
        "passed": True,
        "repository": repository,
        "tag": tag,
        "commit": commit,
        "release_url": release.get("url"),
        "assets": [
            {"name": name, "sha256": observed[name]} for name in sorted(observed)
        ],
        "attestation_verified": True,
        "mutates_repository": False,
    }
    result["report_sha256"] = canonical_digest(result)
    return result


def cleanup_plan(root: Path, tag: str, primary: str, branches: list[str]) -> dict[str, Any]:
    root = root.resolve()
    if not branches or len(branches) != len(set(branches)):
        raise ReleaseError("cleanup-plan requires unique branch names")
    if git_text(root, "cat-file", "-t", f"refs/tags/{tag}") != "tag":
        raise ReleaseError("cleanup-plan requires an annotated local release tag")
    primary_commit = git_text(root, "rev-parse", primary)
    tag_commit = git_text(root, "rev-list", "-n", "1", tag)
    if not primary_commit or tag_commit != primary_commit:
        raise ReleaseError("release tag must point at the selected primary ref")
    rows: list[dict[str, Any]] = []
    for branch in branches:
        if run_git(root, "check-ref-format", "--branch", branch).returncode != 0:
            raise ReleaseError(f"invalid branch name: {branch}")
        commit = git_text(root, "rev-parse", f"refs/heads/{branch}")
        if not commit:
            rows.append({"branch": branch, "safe_to_delete": False, "reason": "missing-local-branch"})
            continue
        if run_git(root, "merge-base", "--is-ancestor", commit, primary).returncode == 0:
            reason = "merged"
            safe = True
        elif git_text(root, "rev-parse", f"{branch}^{{tree}}") == git_text(root, "rev-parse", f"{primary}^{{tree}}"):
            reason = "identical-tree"
            safe = True
        else:
            cherry = run_git(root, "cherry", primary, branch)
            lines = cherry.stdout.splitlines() if cherry.returncode == 0 else []
            safe = bool(lines) and all(line.startswith("-") for line in lines)
            reason = "patch-equivalent" if safe else "unrepresented-commits"
        rows.append(
            {
                "branch": branch,
                "commit": commit,
                "safe_to_delete": safe,
                "reason": reason,
            }
        )
    result = {
        "schema_version": SCHEMA_VERSION,
        "mode": "cleanup-plan",
        "tag": tag,
        "primary": primary,
        "primary_commit": primary_commit,
        "safe_to_delete": all(item["safe_to_delete"] for item in rows),
        "branches": rows,
        "mutates_repository": False,
    }
    result["report_sha256"] = canonical_digest(result)
    return result


def cleanup_apply(
    root: Path,
    plan_value: object,
    audit_value: object,
    confirmation: str,
    remote: str,
) -> dict[str, Any]:
    root = root.resolve()
    if not isinstance(plan_value, dict) or not isinstance(audit_value, dict):
        raise ReleaseError("cleanup plan and release audit must be JSON objects")
    plan = dict(plan_value)
    audit = dict(audit_value)
    verify_digest(plan, "report_sha256", "cleanup plan")
    verify_digest(audit, "report_sha256", "release audit")
    if (
        plan.get("schema_version") != SCHEMA_VERSION
        or plan.get("mode") != "cleanup-plan"
        or plan.get("safe_to_delete") is not True
        or plan.get("mutates_repository") is not False
    ):
        raise ReleaseError("cleanup plan is not an approved all-safe plan")
    tag = plan.get("tag")
    primary = plan.get("primary")
    primary_commit = plan.get("primary_commit")
    branches = plan.get("branches")
    if confirmation != tag:
        raise ReleaseError("cleanup confirmation must exactly match the release tag")
    if (
        not isinstance(primary, str)
        or run_git(root, "check-ref-format", "--branch", primary).returncode != 0
        or not isinstance(branches, list)
        or not branches
    ):
        raise ReleaseError("cleanup plan must name a local primary branch and branches")
    branch_names = [item.get("branch") for item in branches if isinstance(item, dict)]
    if len(branch_names) != len(branches) or primary in branch_names:
        raise ReleaseError("cleanup plan branches are malformed or include the primary branch")
    if (
        audit.get("schema_version") != SCHEMA_VERSION
        or audit.get("mode") != "audit-release"
        or audit.get("passed") is not True
        or audit.get("attestation_verified") is not True
        or audit.get("mutates_repository") is not False
        or audit.get("tag") != tag
        or audit.get("commit") != primary_commit
    ):
        raise ReleaseError("release audit does not authorize this cleanup plan")
    assets = audit.get("assets")
    if (
        not REPOSITORY_PATTERN.fullmatch(str(audit.get("repository", "")))
        or not isinstance(audit.get("release_url"), str)
        or not audit["release_url"].startswith("https://github.com/")
        or not isinstance(assets, list)
        or len(assets) != 4
        or len({item.get("name") for item in assets if isinstance(item, dict)}) != 4
        or any(
            not isinstance(item, dict)
            or set(item) != {"name", "sha256"}
            or not isinstance(item["name"], str)
            or not SHA256_PATTERN.fullmatch(str(item["sha256"]))
            for item in assets
        )
    ):
        raise ReleaseError("release audit asset or repository evidence is malformed")
    state = repository_state(root)
    if state.get("dirty") or state.get("operation"):
        raise ReleaseError("cleanup requires a clean repository with no operation in progress")
    upstream = git_text(
        root, "for-each-ref", "--format=%(upstream:short)", f"refs/heads/{primary}"
    )
    if upstream != f"{remote}/{primary}":
        raise ReleaseError("primary branch must track the selected remote primary branch")
    fetched = run_git(root, "fetch", "--prune", remote)
    if fetched.returncode != 0:
        raise ReleaseError(f"cleanup fetch failed: {redact_output(fetched.stderr)[-500:]}")
    if git_text(root, "rev-parse", f"{remote}/{primary}") != primary_commit:
        raise ReleaseError("remote primary no longer matches the audited release commit")
    refreshed = cleanup_plan(root, str(tag), primary, [str(name) for name in branch_names])
    if refreshed["report_sha256"] != plan["report_sha256"]:
        raise ReleaseError("cleanup plan is stale; generate and review a new plan")
    for item in branches:
        branch = str(item["branch"])
        remote_commit = git_text(root, "rev-parse", f"refs/remotes/{remote}/{branch}")
        if remote_commit and remote_commit != item.get("commit"):
            raise ReleaseError(f"remote branch changed after planning: {branch}")
    switched = run_git(root, "switch", primary)
    if switched.returncode != 0:
        raise ReleaseError(f"cannot switch to primary branch: {redact_output(switched.stderr)[-500:]}")
    pulled = run_git(root, "pull", "--ff-only")
    if pulled.returncode != 0 or git_text(root, "rev-parse", "HEAD") != primary_commit:
        raise ReleaseError("primary branch cannot be fast-forwarded to the audited release commit")
    deleted_remote: list[str] = []
    deleted_local: list[str] = []
    for item in branches:
        branch = str(item["branch"])
        if git_text(root, "rev-parse", f"refs/remotes/{remote}/{branch}"):
            deletion = run_git(root, "push", remote, "--delete", branch)
            if deletion.returncode != 0:
                raise ReleaseError(f"remote branch deletion failed for {branch}: {redact_output(deletion.stderr)[-500:]}")
            deleted_remote.append(branch)
        deletion = run_git(root, "branch", "-D", branch)
        if deletion.returncode != 0:
            raise ReleaseError(f"local branch deletion failed for {branch}: {redact_output(deletion.stderr)[-500:]}")
        deleted_local.append(branch)
    final_state = repository_state(root)
    if (
        final_state.get("branch") != primary
        or final_state.get("dirty")
        or final_state.get("ahead") != 0
        or final_state.get("behind") != 0
    ):
        raise ReleaseError("cleanup did not finish on a clean current primary branch")
    result = {
        "schema_version": SCHEMA_VERSION,
        "mode": "cleanup-apply",
        "passed": True,
        "tag": tag,
        "primary": primary,
        "commit": primary_commit,
        "deleted_local": deleted_local,
        "deleted_remote": deleted_remote,
        "mutates_repository": True,
    }
    result["report_sha256"] = canonical_digest(result)
    return result


def emit(result: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return
    mode = result["mode"]
    passed = result.get("passed", result.get("valid", not result.get("blockers")))
    print(f"{mode}: {'passed' if passed else 'blocked'}")
    for blocker in result.get("blockers", []):
        print(f"BLOCKER: {blocker}")
    for warning in result.get("warnings", []):
        print(f"WARNING: {warning}")
    for item in result.get("checks", []):
        print(f"{'PASS' if item['passed'] else 'FAIL'}: {item['name']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Plan, verify, audit, and clean up a skill collection release safely."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "plan", "check"):
        child = subparsers.add_parser(name)
        child.add_argument("--project-root", type=Path, required=True)
        child.add_argument("--json", action="store_true")
        if name != "status":
            child.add_argument("--tag", required=True)
        if name == "check":
            child.add_argument("--output-root", type=Path)
    evidence = subparsers.add_parser("verify-evidence")
    evidence.add_argument("--project-root", type=Path, required=True)
    evidence.add_argument("--tag", required=True)
    evidence.add_argument("--evidence", type=Path, required=True)
    evidence.add_argument("--json", action="store_true")
    audit = subparsers.add_parser("audit-release")
    audit.add_argument("--project-root", type=Path, required=True)
    audit.add_argument("--tag", required=True)
    audit.add_argument("--repository", required=True)
    audit.add_argument("--json", action="store_true")
    cleanup = subparsers.add_parser("cleanup-plan")
    cleanup.add_argument("--project-root", type=Path, required=True)
    cleanup.add_argument("--tag", required=True)
    cleanup.add_argument("--primary", default="origin/main")
    cleanup.add_argument("--branch", action="append", required=True)
    cleanup.add_argument("--json", action="store_true")
    apply_cleanup = subparsers.add_parser("cleanup-apply")
    apply_cleanup.add_argument("--project-root", type=Path, required=True)
    apply_cleanup.add_argument("--plan", type=Path, required=True)
    apply_cleanup.add_argument("--audit", type=Path, required=True)
    apply_cleanup.add_argument("--confirm", required=True)
    apply_cleanup.add_argument("--remote", default="origin")
    apply_cleanup.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        root = args.project_root.resolve()
        if args.command == "status":
            result = inspect(root)
        elif args.command == "plan":
            result = inspect(root, args.tag)
        elif args.command == "check":
            result = check(root, args.tag, args.output_root)
        elif args.command == "verify-evidence":
            result = verify_evidence(root, args.tag, args.evidence)
        elif args.command == "audit-release":
            result = audit_release(root, args.tag, args.repository)
        elif args.command == "cleanup-plan":
            result = cleanup_plan(root, args.tag, args.primary, args.branch)
        else:
            result = cleanup_apply(
                root,
                load_object(args.plan.resolve(), "cleanup plan"),
                load_object(args.audit.resolve(), "release audit"),
                args.confirm,
                args.remote,
            )
        emit(result, args.json)
        passed = result.get("passed", result.get("valid", not result.get("blockers")))
        return 0 if passed else 1
    except (ReleaseError, OSError, ValueError) as error:
        if getattr(args, "json", False):
            print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False, sort_keys=True))
        else:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
