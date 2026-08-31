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
    "scripts/smoke_marketplaces.py",
    "scripts/build_release.py",
    ".github/workflows/release.yml",
)
CHECKS = (
    ("structural-validation", ("scripts/validate_skills.py",), 180),
    ("marketplace-smoke", ("scripts/smoke_marketplaces.py",), 180),
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


def unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ReleaseError("JSON object contains a duplicate key")
        result[key] = value
    return result


def load_object(path: Path, label: str | None = None) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_json_object)
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
    active_checks = CHECKS
    if (root / "collection-checks.json").exists():
        active_checks = (("collection-full", ("scripts/check_collection.py", "run", "--profile", "full"), 1800),)
        if not (root / "scripts/check_collection.py").is_file():
            blockers.append("declared shared check program requires scripts/check_collection.py")
    if plan["repository"].get("dirty"):
        blockers.append("local release checks require a clean worktree")
    output: Path | None = None
    temporary: tempfile.TemporaryDirectory[str] | None = None
    output, temporary = prepare_output(
        root, output_root, blockers, create=not blockers
    )
    try:
        if not blockers and output is not None:
            for name, arguments, timeout in active_checks:
                command = [sys.executable, *arguments]
                result = run_command(root, name, command, timeout)
                results.append(result)
                if not result["passed"]:
                    break
            if len(results) == len(active_checks) and all(item["passed"] for item in results):
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
        passed = not blockers and len(results) == len(active_checks) + 2 and all(
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
    return verify_commit_evidence(root, tag, evidence_path, git_text(root, "rev-parse", "HEAD"))


def verify_commit_evidence(
    root: Path, tag: str, evidence_path: Path, expected_commit: str | None,
) -> dict[str, Any]:
    """Validate unchanged gate requirements against an explicitly resolved commit."""
    evidence = load_object(evidence_path.resolve(), "release evidence")
    verify_digest(evidence, "evidence_sha256", "release evidence")
    required = {"schema_version", "tag", "commit", "gates", "evidence_sha256"}
    if set(evidence) != required or evidence["schema_version"] != 1:
        raise ReleaseError("release evidence has an unsupported contract")
    if evidence["tag"] != tag or not TAG_PATTERN.fullmatch(tag):
        raise ReleaseError("release evidence tag does not match the requested tag")
    commit = evidence["commit"]
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit) or commit != expected_commit:
        raise ReleaseError("release evidence is not bound to the required commit (current HEAD for verify-evidence)")
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


def remote_repository(root: Path, remote: str) -> str | None:
    value = git_text(root, "remote", "get-url", remote) or ""
    match = re.fullmatch(r"(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?/?", value)
    return match.group(1) if match else None


def remote_observation(root: Path, remote: str, refs: list[str]) -> dict[str, Any]:
    if not remote or remote.startswith("-") or remote not in (git_text(root, "remote") or "").splitlines():
        raise ReleaseError("selected remote does not exist")
    fetch_url = git_text(root, "remote", "get-url", "--all", remote)
    push_url = git_text(root, "remote", "get-url", "--push", "--all", remote)
    if not fetch_url or "\n" in fetch_url or fetch_url != push_url:
        raise ReleaseError("remote must have one identical fetch and push destination")
    result = run_git(root, "ls-remote", remote, *refs)
    if result.returncode:
        raise ReleaseError("remote freshness inspection failed")
    observed: dict[str, str] = {}
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) != 2 or not re.fullmatch(r"[0-9a-f]{40,64}", fields[0]) or fields[1] not in refs or fields[1] in observed:
            raise ReleaseError("remote ref observation is malformed or ambiguous")
        observed[fields[1]] = fields[0]
    return {"remote": remote, "url_sha256": hashlib.sha256(fetch_url.encode()).hexdigest(),
            "refs": {ref: observed.get(ref) for ref in sorted(refs)}}


def github_route_observation(repository: str, primary: str, pull_request: int) -> dict[str, Any]:
    from urllib.parse import quote

    prefix = f"repos/{repository}"
    branch = quote(primary, safe="")
    repo = run_json_command(["gh", "api", prefix], 60, "GitHub repository settings")
    branch_state = run_json_command(["gh", "api", f"{prefix}/branches/{branch}"], 60, "GitHub branch state")
    if not isinstance(branch_state, dict) or not isinstance(branch_state.get("protected"), bool):
        raise ReleaseError("GitHub branch protection visibility is incomplete")
    # A protected branch with an unreadable classic protection endpoint is unknown,
    # not unprotected. Never infer absence from an empty effective-rules response.
    protection = run_json_command(["gh", "api", f"{prefix}/branches/{branch}/protection"], 60,
                                  "GitHub classic branch protection") if branch_state["protected"] else {}
    pages = run_json_command(["gh", "api", "--paginate", "--slurp", f"{prefix}/rules/branches/{branch}"],
                             60, "GitHub effective branch rules")
    if not isinstance(pages, list) or not all(isinstance(page, list) for page in pages):
        raise ReleaseError("GitHub effective rules pagination is incomplete")
    pr = run_json_command(["gh", "api", f"{prefix}/pulls/{pull_request}"], 60, "GitHub pull request")
    if not isinstance(repo, dict) or not isinstance(pr, dict) or not isinstance(protection, dict):
        raise ReleaseError("GitHub route payload is malformed")
    if branch_state["protected"] and (not isinstance(protection.get("required_linear_history"), dict)
                                      or type(protection["required_linear_history"].get("enabled")) is not bool):
        raise ReleaseError("classic linear-history visibility is incomplete")
    head, base = pr.get("head"), pr.get("base")
    if not isinstance(head, dict) or not isinstance(base, dict) or not isinstance(base.get("repo"), dict):
        raise ReleaseError("GitHub pull request identity is incomplete")
    # Keep only routing facts, not unrelated private repository or PR body text.
    return {"repository": {key: repo.get(key) for key in ("full_name", "allow_merge_commit", "allow_squash_merge", "allow_rebase_merge")},
            "protection": protection,
            "rules": [rule for page in pages for rule in page],
            "pull_request": {"number": pr.get("number"), "state": pr.get("state"), "merged": pr.get("merged"),
                             "head": {"sha": head.get("sha")},
                             "base": {"sha": base.get("sha"), "ref": base.get("ref"),
                                      "repo": {"full_name": base["repo"].get("full_name")}}}}


def route_plan(root: Path, tag: str, policy_path: Path, pull_request: int) -> dict[str, Any]:
    root = root.resolve()
    policy = load_object(policy_path, "release route policy")
    if (set(policy) != {"schema_version", "repository", "remote", "primary", "merge_method"}
        or type(policy["schema_version"]) is not int or policy["schema_version"] != 1):
        raise ReleaseError("release route policy has an unsupported contract")
    repository, remote, primary, method = (policy[key] for key in ("repository", "remote", "primary", "merge_method"))
    if not isinstance(repository, str) or not REPOSITORY_PATTERN.fullmatch(repository):
        raise ReleaseError("route policy requires a GitHub owner/repository")
    if method not in ("merge", "squash", "rebase"):
        raise ReleaseError("route policy must explicitly select merge, squash, or rebase")
    if not isinstance(primary, str) or run_git(root, "check-ref-format", "--branch", primary).returncode:
        raise ReleaseError("route policy requires an explicit primary branch")
    if not isinstance(remote, str) or not TAG_PATTERN.fullmatch(tag) or type(pull_request) is not int or pull_request < 1:
        raise ReleaseError("invalid remote, release tag, or pull request number")
    state = repository_state(root)
    blockers: list[str] = []
    remote_repo = remote_repository(root, remote)
    if not remote_repo or remote_repo.casefold() != repository.casefold():
        blockers.append("selected remote does not identify the policy GitHub repository")
    if not state.get("head") or not state.get("branch") or state.get("dirty") or state.get("operation"):
        blockers.append("route planning requires a clean attached candidate with no operation in progress")
    local_primary = git_text(root, "rev-parse", "--verify", f"refs/heads/{primary}^{{commit}}")
    refs = [f"refs/heads/{primary}", f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}"]
    observed = remote_observation(root, remote, refs)
    if not local_primary or observed["refs"][refs[0]] != local_primary:
        blockers.append("local primary does not match freshly observed remote primary")
    if observed["refs"][refs[1]] or git_text(root, "rev-parse", "--verify", f"refs/tags/{tag}"):
        blockers.append("release tag already exists; audit it without moving or republishing it")
    facts = github_route_observation(repository, primary, pull_request)
    repo, protection, rules, pr = (facts.get(key) for key in ("repository", "protection", "rules", "pull_request"))
    if not isinstance(repo, dict) or repo.get("full_name") != repository or not isinstance(protection, dict) or not isinstance(rules, list) or not isinstance(pr, dict):
        raise ReleaseError("GitHub route observation is malformed or belongs to another repository")
    allowed = set()
    for candidate, flag in (("merge", "allow_merge_commit"), ("squash", "allow_squash_merge"), ("rebase", "allow_rebase_merge")):
        if type(repo.get(flag)) is not bool:
            raise ReleaseError("GitHub merge-method availability is incomplete")
        if repo[flag]:
            allowed.add(candidate)
    linear_rule = protection.get("required_linear_history", {})
    if not isinstance(linear_rule, dict):
        raise ReleaseError("classic linear-history protection is malformed")
    linear = linear_rule.get("enabled", False)
    if type(linear) is not bool:
        raise ReleaseError("classic linear-history protection is malformed")
    for rule in rules:
        if not isinstance(rule, dict) or not isinstance(rule.get("type"), str):
            raise ReleaseError("effective branch rule is malformed")
        kind = rule["type"]
        if kind == "required_linear_history":
            linear = True
        if kind == "merge_queue":
            blockers.append("merge queue requires a separately supported integration workflow; no bypass")
        if "parameters" in rule and not isinstance(rule["parameters"], dict):
            raise ReleaseError("effective branch rule parameters are malformed")
        if kind == "pull_request" and "allowed_merge_methods" in rule.get("parameters", {}):
            methods = rule["parameters"]["allowed_merge_methods"]
            if not isinstance(methods, list) or not methods or not all(item in ("merge", "squash", "rebase") for item in methods):
                raise ReleaseError("pull-request merge-method constraint is malformed")
            allowed.intersection_update(methods)
    if linear:
        allowed.discard("merge")
        if method == "merge":
            blockers.append("selected merge method conflicts with required linear history")
    if method not in allowed:
        blockers.append("explicit project merge method is not permitted by observed GitHub rules")
    head = pr.get("head", {})
    base = pr.get("base", {})
    if (pr.get("number") != pull_request or pr.get("state") != "open" or pr.get("merged") is not False
        or not isinstance(head, dict) or not isinstance(base, dict) or head.get("sha") != state.get("head")
        or base.get("sha") != local_primary or base.get("ref") != primary
        or not isinstance(base.get("repo"), dict) or base["repo"].get("full_name") != repository):
        blockers.append("pull request head/base/state does not match the observed candidate and primary")
    # Re-observe refs after provider calls; snapshots are not publication authority.
    if remote_observation(root, remote, refs) != observed or repository_state(root) != state:
        blockers.append("repository or remote refs changed during route planning")
    if load_object(policy_path, "release route policy") != policy:
        blockers.append("project route policy changed during planning")
    result = {"schema_version": SCHEMA_VERSION, "mode": "route-plan", "project_root": str(root),
              "tag": tag, "policy": policy, "policy_sha256": canonical_digest(policy),
              "candidate_commit": state.get("head"),
              "candidate_tree": git_text(root, "rev-parse", "HEAD^{tree}"),
              "primary_commit": local_primary, "primary_tree": git_text(root, "rev-parse", f"{local_primary}^{{tree}}") if local_primary else None,
              "remote_observation": observed, "github_observation": facts,
              "github_observation_sha256": canonical_digest(facts), "selected_method": method,
              "permitted_methods": sorted(allowed), "tag_target": "actual-integrated-primary",
              "new_commit_requires_new_evidence": True,
              "steps": ["revalidate policy, PR, effective rules and remote identities before authorized integration",
                        "integrate only with the explicit permitted method and required GitHub gates",
                        "observe the merged PR and actual integrated primary commit; never predict its SHA",
                        "run and bind every required gate to that exact commit, including review",
                        "only after explicit authorization create the annotated tag at verified integrated primary",
                        "publish immutably, audit, then separately plan and authorize cleanup"],
              "blockers": blockers, "ready": not blockers, "mutates_repository": False}
    result["report_sha256"] = canonical_digest(result)
    return result


def cleanup_plan(root: Path, tag: str, primary: str, branches: list[str], *,
                 remote: str = "origin", release_evidence: Path | None = None) -> dict[str, Any]:
    root = root.resolve()
    if not branches or len(branches) != len(set(branches)):
        raise ReleaseError("cleanup-plan requires unique branch names")
    if git_text(root, "cat-file", "-t", f"refs/tags/{tag}") != "tag":
        raise ReleaseError("cleanup-plan requires an annotated local release tag")
    if not TAG_PATTERN.fullmatch(tag) or run_git(root, "check-ref-format", "--branch", primary).returncode:
        raise ReleaseError("cleanup requires a valid tag and local primary branch")
    if primary in branches:
        raise ReleaseError("cleanup cannot delete the primary branch")
    primary_commit = git_text(root, "rev-parse", "--verify", f"refs/heads/{primary}^{{commit}}")
    tag_commit = git_text(root, "rev-list", "-n", "1", tag)
    tag_object = git_text(root, "rev-parse", f"refs/tags/{tag}")
    release_tree = git_text(root, "rev-parse", f"{tag_commit}^{{tree}}")
    primary_tree = git_text(root, "rev-parse", f"{primary_commit}^{{tree}}")
    if not primary_commit or not release_tree or release_tree != primary_tree:
        raise ReleaseError("release tag and selected primary must have identical trees")
    evidence = None
    if tag_commit != primary_commit:
        if release_evidence is None:
            raise ReleaseError("different release and primary commits require release evidence including review")
        evidence = verify_commit_evidence(root, tag, release_evidence, tag_commit)
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
    observation = remote_observation(root, remote, [f"refs/heads/{primary}", f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}", *[f"refs/heads/{branch}" for branch in branches]])
    refs = observation["refs"]
    blockers = []
    if refs.get(f"refs/heads/{primary}") != primary_commit:
        blockers.append("remote primary does not match selected local primary")
    if refs.get(f"refs/tags/{tag}") != tag_object or refs.get(f"refs/tags/{tag}^{{}}") != tag_commit:
        blockers.append("published remote tag does not match the annotated local release tag")
    for item in rows:
        remote_commit = refs.get(f"refs/heads/{item['branch']}")
        if remote_commit and remote_commit != item.get("commit"):
            blockers.append(f"remote branch differs from proved local branch: {item['branch']}")
    result = {
        "schema_version": SCHEMA_VERSION,
        "mode": "cleanup-plan",
        "tag": tag,
        "primary": primary,
        "primary_commit": primary_commit,
        "release_commit": tag_commit,
        "tag_object": tag_object,
        "release_tree": release_tree,
        "primary_tree": primary_tree,
        "representation": "same-commit" if tag_commit == primary_commit else "identical-tree",
        "release_evidence_sha256": evidence["evidence_sha256"] if evidence else None,
        "project_root": str(root),
        "remote_observation": observation,
        "blockers": blockers,
        "safe_to_delete": not blockers and all(item["safe_to_delete"] for item in rows),
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
    *,
    release_evidence: Path | None = None,
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
        or audit.get("commit") != plan.get("release_commit")
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
    selected_repository = remote_repository(root, remote)
    if (not selected_repository or selected_repository.casefold() != audit["repository"].casefold()
        or audit["release_url"] != f"https://github.com/{audit['repository']}/releases/tag/{tag}"):
        raise ReleaseError("release audit repository does not match the selected GitHub remote and release URL")
    state = repository_state(root)
    if plan.get("project_root") != str(root) or plan.get("remote_observation", {}).get("remote") != remote:
        raise ReleaseError("cleanup plan belongs to another project or remote")
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
    if git_text(root, "rev-parse", f"refs/remotes/{remote}/{primary}") != primary_commit:
        raise ReleaseError("remote primary no longer matches the planned integrated primary commit")
    refreshed = cleanup_plan(root, str(tag), primary, [str(name) for name in branch_names],
                             remote=remote, release_evidence=release_evidence)
    if refreshed["report_sha256"] != plan["report_sha256"]:
        raise ReleaseError("cleanup plan is stale; generate and review a new plan")
    observed_refs = refreshed["remote_observation"]["refs"]
    if observed_refs.get(f"refs/tags/{tag}") != plan.get("tag_object") or observed_refs.get(f"refs/tags/{tag}^{{}}") != plan.get("release_commit"):
        raise ReleaseError("published remote tag no longer matches the audited annotated tag")
    for item in branches:
        branch = str(item["branch"])
        remote_commit = git_text(root, "rev-parse", f"refs/remotes/{remote}/{branch}")
        if remote_commit and remote_commit != item.get("commit"):
            raise ReleaseError(f"remote branch changed after planning: {branch}")
    switched = run_git(root, "switch", primary)
    if switched.returncode != 0:
        raise ReleaseError(f"cannot switch to primary branch: {redact_output(switched.stderr)[-500:]}")
    pulled = run_git(root, "merge", "--ff-only", f"refs/remotes/{remote}/{primary}")
    if pulled.returncode != 0 or git_text(root, "rev-parse", "HEAD") != primary_commit:
        raise ReleaseError("primary branch cannot be fast-forwarded to the planned integrated primary commit")
    deleted_remote: list[str] = []
    deleted_local: list[str] = []
    failure: str | None = None
    for item in branches:
        branch = str(item["branch"])
        worktrees = git_text(root, "worktree", "list", "--porcelain")
        if worktrees is None or f"branch refs/heads/{branch}" in worktrees.splitlines():
            failure = f"cannot delete branch checked out in a worktree or with unknown worktree state: {branch}"
            break
        try:
            current_remote = remote_observation(root, remote, list(observed_refs))
        except ReleaseError as error:
            failure = str(error)
            break
        stable_refs = [f"refs/heads/{primary}", f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}", f"refs/heads/{branch}"]
        if (current_remote["url_sha256"] != plan["remote_observation"]["url_sha256"]
            or any(current_remote["refs"][ref] != observed_refs[ref] for ref in stable_refs)):
            failure = f"remote identity changed before deletion: {branch}"
            break
        if git_text(root, "rev-parse", f"refs/heads/{branch}") != item["commit"]:
            failure = f"local branch changed before deletion: {branch}"
            break
        expected = observed_refs.get(f"refs/heads/{branch}")
        if expected:
            # Compare-and-delete, never a history-rewriting update refspec.
            try:
                deletion = run_git(root, "push", remote, f"--force-with-lease=refs/heads/{branch}:{expected}", f":refs/heads/{branch}")
            except ReleaseError as error:
                failure = f"remote deletion outcome uncertain for {branch}; inspect refs before retrying: {error}"
                break
            if deletion.returncode != 0:
                failure = f"remote branch deletion failed for {branch}: {redact_output(deletion.stderr)[-500:]}"
                break
            deleted_remote.append(branch)
        try:
            worktrees = git_text(root, "worktree", "list", "--porcelain")
            if worktrees is None or f"branch refs/heads/{branch}" in worktrees.splitlines():
                failure = f"local branch became checked out before deletion: {branch}"
                break
            if git_text(root, "symbolic-ref", "-q", f"refs/heads/{branch}") is not None:
                failure = f"local branch became a symbolic ref before deletion: {branch}"
                break
            deletion = run_git(root, "update-ref", "--no-deref", "-d", f"refs/heads/{branch}", str(item["commit"]))
        except ReleaseError as error:
            failure = f"local deletion outcome uncertain for {branch}; inspect refs before retrying: {error}"
            break
        if deletion.returncode != 0:
            failure = f"local branch deletion failed for {branch}: {redact_output(deletion.stderr)[-500:]}"
            break
        deleted_local.append(branch)
    final_state = repository_state(root)
    try:
        final_remote = remote_observation(root, remote, [f"refs/heads/{primary}", f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}"])
        if any(final_remote["refs"][ref] != observed_refs[ref] for ref in final_remote["refs"]):
            failure = failure or "remote primary or tag changed during cleanup; inspect retained refs"
    except ReleaseError as error:
        failure = failure or str(error)
    if (
        final_state.get("branch") != primary
        or final_state.get("dirty")
        or final_state.get("ahead") != 0
        or final_state.get("behind") != 0
    ):
        failure = failure or "cleanup did not finish on a clean current primary branch"
    result = {
        "schema_version": SCHEMA_VERSION,
        "mode": "cleanup-apply",
        "passed": failure is None,
        "tag": tag,
        "primary": primary,
        "commit": primary_commit,
        "release_commit": plan["release_commit"],
        "deleted_local": deleted_local,
        "deleted_remote": deleted_remote,
        "retained_local": [str(item["branch"]) for item in branches if item["branch"] not in deleted_local],
        "failure": failure,
        "mutates_repository": True,
    }
    result["report_sha256"] = canonical_digest(result)
    return result


def emit(result: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return
    mode = result["mode"]
    passed = result.get("passed", result.get("valid", result.get("safe_to_delete", not result.get("blockers"))))
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
    route = subparsers.add_parser("route-plan")
    route.add_argument("--project-root", type=Path, required=True)
    route.add_argument("--tag", required=True)
    route.add_argument("--policy", type=Path, required=True)
    route.add_argument("--pull-request", type=int, required=True)
    route.add_argument("--json", action="store_true")
    audit = subparsers.add_parser("audit-release")
    audit.add_argument("--project-root", type=Path, required=True)
    audit.add_argument("--tag", required=True)
    audit.add_argument("--repository", required=True)
    audit.add_argument("--json", action="store_true")
    cleanup = subparsers.add_parser("cleanup-plan")
    cleanup.add_argument("--project-root", type=Path, required=True)
    cleanup.add_argument("--tag", required=True)
    cleanup.add_argument("--primary", required=True)
    cleanup.add_argument("--branch", action="append", required=True)
    cleanup.add_argument("--remote", default="origin")
    cleanup.add_argument("--release-evidence", type=Path)
    cleanup.add_argument("--json", action="store_true")
    apply_cleanup = subparsers.add_parser("cleanup-apply")
    apply_cleanup.add_argument("--project-root", type=Path, required=True)
    apply_cleanup.add_argument("--plan", type=Path, required=True)
    apply_cleanup.add_argument("--audit", type=Path, required=True)
    apply_cleanup.add_argument("--confirm", required=True)
    apply_cleanup.add_argument("--remote", default="origin")
    apply_cleanup.add_argument("--release-evidence", type=Path)
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
        elif args.command == "route-plan":
            result = route_plan(root, args.tag, args.policy, args.pull_request)
        elif args.command == "audit-release":
            result = audit_release(root, args.tag, args.repository)
        elif args.command == "cleanup-plan":
            result = cleanup_plan(root, args.tag, args.primary, args.branch,
                                  remote=args.remote, release_evidence=args.release_evidence)
        else:
            result = cleanup_apply(
                root,
                load_object(args.plan.resolve(), "cleanup plan"),
                load_object(args.audit.resolve(), "release audit"),
                args.confirm,
                args.remote,
                release_evidence=args.release_evidence,
            )
        emit(result, args.json)
        passed = result.get("passed", result.get("valid", result.get("safe_to_delete", not result.get("blockers"))))
        return 0 if passed else 1
    except (ReleaseError, OSError, ValueError) as error:
        if getattr(args, "json", False):
            print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False, sort_keys=True))
        else:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
