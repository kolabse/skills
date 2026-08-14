from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


class ClassificationError(RuntimeError):
    pass


def git(repository: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise ClassificationError(result.stderr.strip() or "Git command failed")
    return result


def git_text(repository: Path, *arguments: str) -> str:
    return git(repository, *arguments).stdout.strip()


def operation_in_progress(repository: Path) -> str | None:
    git_dir_text = git_text(repository, "rev-parse", "--git-dir")
    git_dir = Path(git_dir_text)
    if not git_dir.is_absolute():
        git_dir = (repository / git_dir).resolve()
    markers = (
        ("MERGE_HEAD", "merge"),
        ("CHERRY_PICK_HEAD", "cherry-pick"),
        ("REVERT_HEAD", "revert"),
        ("rebase-merge", "rebase"),
        ("rebase-apply", "rebase"),
    )
    for marker, operation in markers:
        if (git_dir / marker).exists():
            return operation
    return None


def worktree_counts(repository: Path) -> dict[str, int]:
    staged = unstaged = untracked = 0
    status = git(repository, "status", "--porcelain=v1", "--untracked-files=all").stdout
    for line in status.splitlines():
        if line.startswith("??"):
            untracked += 1
            continue
        if len(line) >= 2 and line[0] != " ":
            staged += 1
        if len(line) >= 2 and line[1] != " ":
            unstaged += 1
    return {"staged": staged, "unstaged": unstaged, "untracked": untracked}


def cherry_rows(repository: Path, upstream: str, head: str) -> list[str]:
    output = git(repository, "cherry", upstream, head, check=False)
    if output.returncode != 0:
        return []
    return [line for line in output.stdout.splitlines() if line.startswith(("+ ", "- "))]


def classify(repository: Path, upstream: str | None = None) -> dict[str, Any]:
    root = Path(git_text(repository, "rev-parse", "--show-toplevel")).resolve()
    head = git_text(root, "rev-parse", "HEAD")
    branch_result = git(root, "symbolic-ref", "--quiet", "--short", "HEAD", check=False)
    branch = branch_result.stdout.strip() or None
    operation = operation_in_progress(root)
    counts = worktree_counts(root)
    if upstream is None:
        upstream_result = git(
            root,
            "rev-parse",
            "--abbrev-ref",
            "--symbolic-full-name",
            "@{upstream}",
            check=False,
        )
        upstream = upstream_result.stdout.strip() or None
    result: dict[str, Any] = {
        "schema_version": 1,
        "repository": str(root),
        "branch": branch,
        "head": head,
        "upstream": upstream,
        "worktree": counts,
        "operation_in_progress": operation,
        "classification": "untracked",
        "divergence_equivalence": "not-applicable",
        "recommended_action": "configure-upstream",
        "mutates": False,
    }
    if operation:
        result.update(
            classification="operation-in-progress",
            recommended_action="finish-or-abort-operation-explicitly",
        )
        return result
    if branch is None:
        result.update(classification="detached", recommended_action="select-branch-explicitly")
        return result
    if upstream is None:
        return result
    upstream_head_result = git(root, "rev-parse", upstream, check=False)
    if upstream_head_result.returncode != 0:
        result.update(classification="untracked", recommended_action="fetch-or-fix-upstream")
        return result
    upstream_head = upstream_head_result.stdout.strip()
    count_text = git_text(root, "rev-list", "--left-right", "--count", f"HEAD...{upstream}")
    try:
        ahead, behind = (int(value) for value in count_text.split())
    except (ValueError, TypeError) as error:
        raise ClassificationError("Git returned invalid ahead/behind counts") from error
    result.update(upstream_head=upstream_head, ahead=ahead, behind=behind)
    if ahead == 0 and behind == 0:
        result.update(classification="current", recommended_action="none")
    elif ahead and not behind:
        result.update(classification="ahead-only", recommended_action="review-before-push")
    elif behind and not ahead:
        result.update(classification="behind-only", recommended_action="fast-forward-if-clean")
    else:
        result.update(classification="diverged", recommended_action="manual-reconcile")
        head_tree = git_text(root, "show", "-s", "--format=%T", "HEAD")
        upstream_tree = git_text(root, "show", "-s", "--format=%T", upstream)
        if head_tree == upstream_tree:
            equivalence = "identical-tree"
        else:
            local_rows = cherry_rows(root, upstream, "HEAD")
            upstream_rows = cherry_rows(root, "HEAD", upstream)
            local_represented = bool(local_rows) and all(row.startswith("- ") for row in local_rows)
            upstream_represented = bool(upstream_rows) and all(
                row.startswith("- ") for row in upstream_rows
            )
            if local_represented and upstream_represented:
                equivalence = "patch-equivalent"
            elif local_represented:
                equivalence = "local-patches-represented-upstream"
            elif upstream_represented:
                equivalence = "upstream-patches-represented-locally"
            else:
                equivalence = "none"
        result["divergence_equivalence"] = equivalence
        if equivalence != "none":
            result["recommended_action"] = "backup-then-align-with-user-approval"
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Classify Git freshness and divergence read-only.")
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--upstream")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = classify(args.repository.resolve(), args.upstream)
    except ClassificationError as error:
        if args.json:
            print(json.dumps({"schema_version": 1, "error": str(error), "mutates": False}))
        else:
            print(f"Classification failed: {error}")
        return 1
    print(json.dumps(result, indent=2, sort_keys=True) if args.json else result["classification"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
