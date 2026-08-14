from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


TAG_PATTERN = re.compile(r"^v([0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?)$")
REQUIRED_FILES = (
    "skill-catalog.json",
    ".codex-plugin/plugin.json",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "scripts/validate_skills.py",
    "scripts/security_checks.py",
    "scripts/build_release.py",
    ".github/workflows/release.yml",
)
POST_PUBLICATION_STEPS = [
    "verify the published release, assets, checksums, and attestations",
    "fetch and prune remote refs after merge and publication",
    "switch to the configured primary branch and make it current with its upstream",
    "delete merged local and remote feature or release branches after proving their work is represented upstream",
    "finish with a clean worktree on the current primary branch and report any retained branch",
]


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, check=False
    )


def repository_state(root: Path) -> dict[str, Any]:
    inside = git(root, "rev-parse", "--is-inside-work-tree")
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return {"is_git_repository": False}
    branch = git(root, "branch", "--show-current").stdout.strip() or None
    head = git(root, "rev-parse", "HEAD").stdout.strip()
    upstream_result = git(root, "rev-parse", "--abbrev-ref", "@{upstream}")
    upstream = upstream_result.stdout.strip() if upstream_result.returncode == 0 else None
    ahead = behind = None
    if upstream:
        counts = git(root, "rev-list", "--left-right", "--count", f"HEAD...{upstream}")
        if counts.returncode == 0:
            ahead, behind = (int(item) for item in counts.stdout.split())
    return {
        "is_git_repository": True,
        "branch": branch,
        "head": head,
        "upstream": upstream,
        "ahead": ahead,
        "behind": behind,
        "dirty": bool(git(root, "status", "--porcelain=v1").stdout),
    }


def inspect(root: Path, tag: str | None = None) -> dict[str, Any]:
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
        catalog = load_object(root / "skill-catalog.json")
        versions["catalog"] = catalog.get("collection_version")
        holdout = catalog.get("release_holdout")
        if not isinstance(holdout, dict) or not holdout.get("sha256"):
            blockers.append("catalog release holdout is missing or incomplete")
        for entry in catalog.get("skills", []):
            if not isinstance(entry, dict):
                continue
            metadata = load_object(root / str(entry.get("path")) / "collection-metadata.json")
            versions[f"skill:{entry.get('name')}"] = metadata.get("version")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        blockers.append(f"collection metadata cannot be inspected: {error}")
    try:
        versions["plugin"] = load_object(root / ".codex-plugin" / "plugin.json").get("version")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        blockers.append(f"plugin manifest cannot be inspected: {error}")
    if version:
        mismatched = {name: value for name, value in versions.items() if value != version}
        if mismatched:
            blockers.append(f"release versions do not all match {version}: {mismatched}")
        try:
            changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
            if not re.search(rf"^## \[{re.escape(version)}\](?:\s|$)", changelog, re.MULTILINE):
                blockers.append(f"CHANGELOG.md has no versioned heading for {version}")
        except OSError as error:
            blockers.append(f"CHANGELOG.md cannot be read: {error}")
    state = repository_state(root)
    if not state.get("is_git_repository"):
        blockers.append("project root is not a Git repository")
    else:
        if state.get("dirty"):
            warnings.append("worktree is dirty; release evidence must be rebound after changes")
        if not state.get("upstream"):
            warnings.append("current branch has no upstream")
        if state.get("behind"):
            blockers.append(f"current branch is behind upstream by {state['behind']} commit(s)")
    if tag and state.get("is_git_repository"):
        tag_result = git(root, "show-ref", "--verify", "--quiet", f"refs/tags/{tag}")
        if tag_result.returncode == 0:
            warnings.append(f"tag {tag} already exists; it must never be moved")
    return {
        "schema_version": 1,
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


def run_command(root: Path, name: str, command: list[str]) -> dict[str, Any]:
    result = subprocess.run(command, cwd=root, text=True, capture_output=True, check=False)
    return {
        "name": name,
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "passed": result.returncode == 0,
    }


def check(root: Path, tag: str, output_root: Path | None) -> dict[str, Any]:
    plan = inspect(root, tag)
    results: list[dict[str, Any]] = []
    if plan["repository"].get("dirty"):
        plan["blockers"].append(
            "local release checks require a clean worktree so artifacts match the reviewed Git state"
        )
    if output_root is not None:
        resolved_output = output_root.resolve()
        if resolved_output == root or resolved_output.is_relative_to(root):
            plan["blockers"].append(
                "explicit output root must be outside the repository"
            )
    if plan["blockers"]:
        return {**plan, "mode": "check", "checks": results, "passed": False}
    temporary = None
    if output_root is None:
        temporary = tempfile.TemporaryDirectory(prefix="skill-release-")
        output = Path(temporary.name)
    else:
        output = resolved_output
        output.mkdir(parents=True, exist_ok=True)
    commands = [
        ("structural-validation", [sys.executable, "scripts/validate_skills.py"]),
        ("security", [sys.executable, "scripts/security_checks.py"]),
        ("unit-tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]),
        ("build", [sys.executable, "scripts/build_release.py", "--source", str(root), "--tag", tag, "--output", str(output)]),
    ]
    for name, command in commands:
        result = run_command(root, name, command)
        results.append(result)
        if not result["passed"]:
            break
    if results and results[-1]["passed"] and results[-1]["name"] == "build":
        results.append(run_command(root, "checksums", [sys.executable, "scripts/build_release.py", "--verify", str(output / "SHA256SUMS")]))
    passed = len(results) == 5 and all(item["passed"] for item in results)
    response = {
        **plan,
        "mode": "check",
        "checks": results,
        "passed": passed,
        "external_gates_remaining": [
            "locked model-backed holdout and baseline comparison",
            "consumer installation smoke test",
            "supported-platform CI",
            "reviewed immutable tag and GitHub attested publication",
        ],
    }
    if temporary is not None:
        temporary.cleanup()
    return response


def emit(result: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    print(f"{result['mode']}: {'ready' if not result['blockers'] else 'blocked'}")
    for blocker in result["blockers"]:
        print(f"BLOCKER: {blocker}")
    for warning in result["warnings"]:
        print(f"WARNING: {warning}")
    for item in result.get("checks", []):
        print(f"{'PASS' if item['passed'] else 'FAIL'}: {item['name']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan and verify a skill collection release without publishing it.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "plan", "check"):
        child = subparsers.add_parser(name)
        child.add_argument("--project-root", type=Path, required=True)
        child.add_argument("--json", action="store_true")
        if name != "status":
            child.add_argument("--tag", required=True)
        if name == "check":
            child.add_argument("--output-root", type=Path)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    result = check(root, args.tag, args.output_root) if args.command == "check" else inspect(root, getattr(args, "tag", None))
    emit(result, args.json)
    return 0 if not result["blockers"] and (args.command != "check" or result["passed"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
