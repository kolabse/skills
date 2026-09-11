#!/usr/bin/env python3
"""Retire one proved merged task. Stdlib only; no release-audit dependency.

CAS deletion and remote identity binding adapted from release-skill-collection's
release_collection.py cleanup implementation; release artifacts are out of scope.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import quote, urlsplit


class Blocked(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise Blocked(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                                     separators=(",", ":")).encode()).hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON field")
        result[key] = value
    return result


def execute(argv, cwd, input_text=None):
    try:
        result = subprocess.run(argv, cwd=cwd, input=input_text, text=True,
                                encoding="utf-8", capture_output=True, timeout=120,
                                env={**os.environ, "GIT_OPTIONAL_LOCKS": "0",
                                     "GIT_TERMINAL_PROMPT": "0"})
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Blocked("Command unavailable or outcome uncertain: " + argv[0]) from exc
    require(result.returncode == 0, "Command failed: " + argv[0] + " " + argv[1])
    require(len(result.stdout) <= 16 * 1024 * 1024, "Command output exceeds conservative proof limit")
    return result.stdout.rstrip("\r\n")


def git(root, *args):
    return execute(["git", *args], root)


def oid(root, ref):
    output = git(root, "for-each-ref", "--format=%(refname) %(objectname) %(symref)", ref)
    matches = [line.split() for line in output.splitlines()
               if line.split() and line.split()[0] == ref]
    if not matches:
        return None
    require(len(matches) == 1 and len(matches[0]) == 2, "Ambiguous or symbolic ref")
    value = matches[0][1]
    require(re.fullmatch(r"[0-9a-f]{40,64}", value), "Invalid object identity")
    return value


def ancestor(root, older, newer):
    return older == git(root, "merge-base", older, newer)


def identity(url):
    if "://" in url:
        parsed = urlsplit(url)
        require(parsed.scheme in {"ssh", "https"} and not parsed.password
                and not parsed.query and not parsed.fragment,
                "Remote URL must be credential-free SSH or HTTPS")
        require(not parsed.username or (parsed.scheme == "ssh" and parsed.username == "git"),
                "Embedded remote credentials are prohibited")
        return parsed.hostname, parsed.path.strip("/").removesuffix(".git")
    match = re.fullmatch(r"git@([A-Za-z0-9.-]+):([A-Za-z0-9_./-]+)", url)
    require(match, "Remote URL must identify an explicit hosted repository")
    return match[1], match[2].removesuffix(".git")


def worktrees(root):
    result = []
    for block in git(root, "worktree", "list", "--porcelain", "-z").split("\0\0"):
        if not block.strip("\0"):
            continue
        item = {}
        for line in block.split("\0"):
            if line:
                key, _, value = line.partition(" ")
                item[key] = value
        require("worktree" in item, "Malformed worktree registration")
        result.append(item)
    return result


def safe_path(value):
    path = Path(value)
    require(path.is_absolute(), "Worktree and allowed-root paths must be absolute")
    for parent in (path, *path.parents):
        require(not parent.is_symlink() and not (parent.exists() and
                getattr(parent.lstat(), "st_file_attributes", 0) & 1024),
                "Symlink or reparse point in worktree path")
    require(path.exists(), "Worktree or allowed root is missing")
    return path.resolve()


def clean(root, ignored=False):
    require(not git(root, "status", "--porcelain=v1", "--untracked-files=all",
                    *(["--ignored"] if ignored else [])), "Worktree is dirty")
    for name in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge",
                 "rebase-apply", "BISECT_START", "sequencer", "index.lock"):
        require(not Path(git(root, "rev-parse", "--path-format=absolute", "--git-path", name)).exists(),
                "Git operation or lock in progress")
    common = Path(git(root, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    require(not any((common / name).exists() for name in ("packed-refs.lock", "config.lock", "shallow.lock"))
            and not any((common / "refs").rglob("*.lock")), "Repository ref lock in progress")


def provider_review(root, options):
    repository, review = options["repository"], options["review"]
    if options["provider"] == "github":
        data = json.loads(execute(["gh", "api", "--hostname", "github.com", f"repos/{repository}/pulls/{review}"], root))
        require(data.get("merged") is True, "Review is not merged")
        require(data["base"]["repo"]["full_name"] == repository and
                data["head"]["repo"]["full_name"] == repository,
                "Review repository identity mismatch; forks are unsupported")
        return {"source": data["head"]["sha"], "merge": data["merge_commit_sha"],
                "base": data["base"]["ref"], "branch": data["head"]["ref"]}
    prefix = f"projects/{quote(repository, safe='')}"
    data = json.loads(execute(["glab", "api", "--hostname", options["host"],
                              f"{prefix}/merge_requests/{review}"], root))
    project = json.loads(execute(["glab", "api", "--hostname", options["host"], prefix], root))
    require(project.get("path_with_namespace") == repository and
            data.get("source_project_id") == project["id"] == data.get("target_project_id"),
            "Review repository identity mismatch; forks are unsupported")
    require(data.get("state") == "merged", "Review is not merged")
    return {"source": data.get("sha"),
            "merge": data.get("merge_commit_sha") or data.get("squash_commit_sha"),
            "base": data.get("target_branch"), "branch": data.get("source_branch")}


def unprotected_source(root, options):
    branch = quote(options["branch"], safe="")
    if options["provider"] == "github":
        argv = ["gh", "api", "--hostname", "github.com", f"repos/{options['repository']}/branches/{branch}"]
    else:
        repository = quote(options["repository"], safe="")
        argv = ["glab", "api", "--hostname", options["host"],
                f"projects/{repository}/repository/branches/{branch}"]
    data = json.loads(execute(argv, root))
    require(data.get("protected") is False, "Task branch is protected or protection is unknown")
    require(data.get("name") == options["branch"], "Provider branch identity differs")
    return data.get("commit", {}).get("sha") or data.get("commit", {}).get("id")


def patch(root, base, tip):
    diff = git(root, "diff", "--no-ext-diff", "--no-textconv", "--binary", base, tip)
    require(diff, "Empty patch cannot prove integration")
    value = execute(["git", "patch-id", "--stable"], root, diff + "\n")
    require(len(value.splitlines()) == 1 and len(value.split()) == 2,
            "Patch identity is ambiguous")
    # Patch-id alone ignores whitespace, which is semantic in Python and other
    # formats. Bind exact diff payload as well; only index object IDs may differ.
    # Hunk locations and function context remain binding: dropping
    # them can confuse identical edits in different functions. Even harmless
    # offset changes deliberately block cleanup without a stronger tree proof.
    payload = "\n".join(line for line in diff.split("\n")
                        if not line.startswith("index "))
    return value.split()[0], digest(payload)


def proof(root, source, merge, target):
    require(ancestor(root, merge, target), "Review merge commit is absent from target")
    if ancestor(root, source, target):
        return "ancestry"
    base = git(root, "merge-base", source, merge)
    parents = git(root, "rev-list", "--parents", "-n", "1", merge).split()[1:]
    require(len(parents) == 1, "Non-ancestral multi-parent integration is unsupported")
    if patch(root, base, source) == patch(root, parents[0], merge):
        return "squash-patch"
    original = git(root, "rev-list", "--reverse", f"{base}..{source}").splitlines()
    require(original and len(original) <= 1000, "Rebase history is missing or too large")
    integrated = git(root, "rev-list", "--first-parent", f"--max-count={len(original)}", merge).splitlines()[::-1]
    require(len(integrated) == len(original), "Rebase sequence is incomplete")
    for old, new in zip(original, integrated):
        left = git(root, "rev-list", "--parents", "-n", "1", old).split()
        right = git(root, "rev-list", "--parents", "-n", "1", new).split()
        require(len(left) == len(right) == 2, "Rebase proof requires linear nonempty commits")
        require(patch(root, left[1], old) == patch(root, right[1], new),
                "Task patches are not represented in target")
    return "rebase-patches"


def observe(options):
    root = safe_path(options["project_root"])
    require(git(root, "rev-parse", "--show-toplevel") == str(root).replace("\\", "/") or
            Path(git(root, "rev-parse", "--show-toplevel")).resolve() == root,
            "Project root must be the worktree root")
    branch, primary, remote = (options[key] for key in ("branch", "primary", "remote"))
    for ref in (branch, primary):
        require(isinstance(ref, str) and not ref.startswith("-") and ref != "HEAD",
                "Dangerous branch name")
        git(root, "check-ref-format", "refs/heads/" + ref)
    require(branch != primary, "Cannot retire the primary branch")
    require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", remote), "Invalid remote name")
    require(options["provider"] in {"github", "gitlab"}, "Unsupported provider")
    require(re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+", options["repository"]),
            "Explicit repository identity required")
    require(type(options["review"]) is int and options["review"] > 0, "Positive review ID required")
    host = "github.com" if options["provider"] == "github" else options.get("host")
    require(host and re.fullmatch(r"[A-Za-z0-9.-]+", host), "Explicit provider host required")
    urls = [git(root, "remote", "get-url", "--all", remote),
            git(root, "remote", "get-url", "--push", "--all", remote)]
    require(all(len(url.splitlines()) == 1 and identity(url) == (host, options["repository"])
                for url in urls), "Remote and provider repository identities differ")
    clean(root)
    current = git(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    require(current != branch, "Cannot retire the current branch; switch away explicitly first")
    refs = ["refs/heads/" + primary, "refs/heads/" + branch]
    observed = {}
    for line in git(root, "ls-remote", "--refs", remote, *refs).splitlines():
        sha, name = line.split()
        require(name in refs and name not in observed, "Ambiguous remote observation")
        observed[name] = sha
    target = oid(root, refs[0])
    require(target and observed.get(refs[0]) == target, "Synchronize primary before planning")
    require(git(root, "for-each-ref", "--format=%(upstream)", refs[0]) ==
            f"refs/remotes/{remote}/{primary}", "Primary must track selected remote primary")
    require(oid(root, f"refs/remotes/{remote}/{primary}") == target,
            "Fetch primary before planning")
    local, remote_tip = oid(root, refs[1]), observed.get(refs[1])
    require(local or remote_tip, "Task branch is absent locally and remotely")
    review = provider_review(root, options)
    require(review["base"] == primary and review["branch"] == branch,
            "Merged review target or source branch differs")
    for sha in (review["source"], review["merge"]):
        require(isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{40,64}", sha),
                "Merged review has no exact commit identity")
    require(all(tip == review["source"] for tip in (local, remote_tip) if tip),
            "Task branch changed since merge")
    if remote_tip:
        require(unprotected_source(root, options) == remote_tip,
                "Provider source identity differs from remote observation")
    representation = proof(root, review["source"], review["merge"], target)
    registered = worktrees(root)
    selected = {str(safe_path(p)) for p in options.get("remove_worktree", [])}
    require(len(selected) == len(options.get("remove_worktree", [])),
            "Duplicate worktree removal selection")
    inactive = {str(safe_path(p)) for p in options.get("inactive_worktree", [])}
    allowed = [safe_path(p) for p in options.get("allowed_root", [])]
    found = set()
    for index, item in enumerate(registered):
        path = Path(item["worktree"]).resolve()
        if item.get("branch") == refs[1]:
            require(str(path) in selected, "Task branch is protected by a linked worktree")
        if str(path) not in selected:
            continue
        require(index != 0 and path != root, "Cannot remove main or current worktree")
        require(item.get("branch") == refs[1], "Selected worktree does not belong to task branch")
        require(item.get("HEAD") == review["source"], "Selected worktree HEAD differs from merged source")
        require(not any(key in item for key in ("locked", "prunable", "bare")),
                "Selected worktree is locked or unavailable")
        require(str(path) in inactive, "Explicit inactive-worktree acknowledgement required")
        require(any(path != boundary and path.is_relative_to(boundary) for boundary in allowed),
                "Worktree is outside approved allowed roots")
        clean(path, ignored=True)
        require(not git(path, "ls-files", "--stage").startswith("160000 ") and
                "\n160000 " not in git(path, "ls-files", "--stage"), "Submodule worktrees are protected")
        found.add(str(path))
    require(found == selected, "Selected worktree is not registered")
    if options.get("restore_primary"):
        require(not any(item.get("branch") == refs[0] and Path(item["worktree"]).resolve() != root
                        for item in registered), "Primary is occupied by another worktree")
    require(git(root, "ls-remote", "--refs", remote, *refs) ==
            "\n".join(f"{observed[name]}\t{name}" for name in sorted(observed)),
            "Remote refs changed during observation")
    return {"project_root": str(root), "common_dir": git(root, "rev-parse", "--path-format=absolute", "--git-common-dir"),
            "urls_digest": digest(urls), "current": current, "head": git(root, "rev-parse", "HEAD"),
            "target": target, "local_source": local, "remote_source": remote_tip,
            "review": review, "representation": representation, "worktrees": registered}


def make_plan(options):
    value = {"schema_version": 1, "status": "ready", "options": options,
             "snapshot": observe(options)}
    value["digest"] = digest(value)
    return value


def external(path, root):
    path = path.resolve()
    require(not path.is_relative_to(root.resolve()), "Plan must be outside the project root")
    common = Path(git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")).resolve()
    require(not path.is_relative_to(common), "Plan must be outside Git metadata")
    for item in worktrees(root):
        require(not path.is_relative_to(Path(item["worktree"]).resolve()),
                "Plan must be outside every registered worktree")
    return path


def apply_plan(root, path, confirm):
    root = safe_path(str(root))
    plan = json.loads(external(path, root).read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    require(isinstance(plan, dict), "Plan must be a JSON object")
    recorded = plan.pop("digest", None)
    require(recorded == digest(plan) == confirm, "Exact plan digest confirmation required")
    require(plan.get("schema_version") == 1 and plan.get("status") == "ready", "Unsupported plan")
    options = plan["options"]
    require(Path(options["project_root"]).resolve() == root.resolve(), "Plan belongs to another root")
    require(observe(options) == plan["snapshot"], "Plan is stale; regenerate and review")
    git(root, "fetch", "--no-tags", options["remote"])
    require(observe(options) == plan["snapshot"], "Plan changed after fetch; regenerate and review")
    completed = []
    action = None
    snapshot = plan["snapshot"]
    def verify_action_boundary():
        # Re-observe the complete proof immediately before each mutation. Only
        # changes already completed by this execution may differ from the plan.
        expected = dict(snapshot)
        remaining_options = dict(options)
        removed = {str(Path(item["resource"]).resolve()) for item in completed
                   if item["kind"] == "remove-worktree"}
        remaining_options["remove_worktree"] = [value for value in options.get("remove_worktree", [])
                                                if str(Path(value).resolve()) not in removed]
        remaining_options["inactive_worktree"] = [value for value in options.get("inactive_worktree", [])
                                                  if str(Path(value).resolve()) not in removed]
        expected["worktrees"] = [item for item in snapshot["worktrees"]
                                 if str(Path(item["worktree"]).resolve()) not in removed]
        if any(item["kind"] == "restore-primary" for item in completed):
            expected["current"], expected["head"] = options["primary"], snapshot["target"]
            expected["worktrees"] = [dict(item) for item in expected["worktrees"]]
            for item in expected["worktrees"]:
                if Path(item["worktree"]).resolve() == root:
                    item["branch"] = "refs/heads/" + options["primary"]
                    item["HEAD"] = snapshot["target"]
        if any(item["kind"] == "delete-remote" for item in completed):
            expected["remote_source"] = None
        require(observe(remaining_options) == expected,
                "Repository or merged proof changed before destructive action")
    def verify_remote_identity():
        urls = [git(root, "remote", "get-url", "--all", options["remote"]),
                git(root, "remote", "get-url", "--push", "--all", options["remote"])]
        require(digest(urls) == snapshot["urls_digest"], "Remote destination changed")
    def verify_before_removal(value):
        verify_remote_identity()
        branch_ref = "refs/heads/" + options["branch"]
        require(oid(root, branch_ref) == snapshot["local_source"], "Local source changed before worktree removal")
        expected = snapshot["remote_source"]
        observed = git(root, "ls-remote", "--refs", options["remote"], branch_ref)
        require(observed == (f"{expected}\t{branch_ref}" if expected else ""),
                "Remote source changed before worktree removal")
        if expected:
            require(unprotected_source(root, options) == expected, "Source protection or identity changed")
        path_value = safe_path(value)
        require(any(path_value != safe_path(boundary) and path_value.is_relative_to(safe_path(boundary))
                    for boundary in options["allowed_root"]), "Worktree left allowed roots")
        actual = [item for item in worktrees(root) if Path(item["worktree"]).resolve() == path_value]
        planned = [item for item in snapshot["worktrees"] if Path(item["worktree"]).resolve() == path_value]
        require(actual == planned and len(actual) == 1, "Worktree registration changed")
        clean(path_value, ignored=True)
    def final_state():
        branch_ref = "refs/heads/" + options["branch"]
        return {"local_source": oid(root, branch_ref),
                "remote_source": git(root, "ls-remote", "--refs", options["remote"], branch_ref),
                "checkout": git(root, "symbolic-ref", "--quiet", "--short", "HEAD"),
                "checkout_status": git(root, "status", "--porcelain=v1", "--untracked-files=all"),
                "head": git(root, "rev-parse", "HEAD"),
                "primary": oid(root, "refs/heads/" + options["primary"]),
                "remote_primary": git(root, "ls-remote", "--refs", options["remote"], "refs/heads/" + options["primary"]),
                "worktrees": worktrees(root)}
    try:
        if options.get("restore_primary") and plan["snapshot"]["current"] != options["primary"]:
            action = {"kind": "restore-primary", "resource": options["primary"]}
            verify_action_boundary()
            git(root, "switch", "--no-overwrite-ignore", options["primary"])
            completed.append(action)
        for value in options.get("remove_worktree", []):
            action = {"kind": "remove-worktree", "resource": value}
            verify_action_boundary()
            verify_before_removal(value)
            git(root, "worktree", "remove", value)
            completed.append(action)
        branch, remote = options["branch"], options["remote"]
        ref = "refs/heads/" + branch
        require(not any(item.get("branch") == ref for item in worktrees(root)),
                "Task branch became checked out")
        require(oid(root, ref) == plan["snapshot"]["local_source"], "Local branch changed before deletion")
        if plan["snapshot"]["remote_source"]:
            action = {"kind": "delete-remote", "resource": branch}
            verify_action_boundary()
            verify_remote_identity()
            require(unprotected_source(root, options) == snapshot["remote_source"],
                    "Source protection or identity changed before remote deletion")
            git(root, "push", remote, f"--force-with-lease={ref}:{plan['snapshot']['remote_source']}", ":" + ref)
            completed.append(action)
        if plan["snapshot"]["local_source"]:
            action = {"kind": "delete-local", "resource": branch}
            verify_action_boundary()
            require(not any(item.get("branch") == ref for item in worktrees(root)), "Task branch became checked out")
            require(oid(root, ref) == plan["snapshot"]["local_source"], "Local branch changed")
            git(root, "update-ref", "--no-deref", "-d", ref, plan["snapshot"]["local_source"])
            completed.append(action)
        action = {"kind": "verify-final", "resource": options["branch"]}
        final = final_state()
        require(not final["checkout_status"], "Checkout became dirty during retirement")
        require(not final["local_source"] and not final["remote_source"], "Task refs remain after deletion")
        require(final["primary"] == snapshot["target"] and final["remote_primary"] ==
                f"{snapshot['target']}\trefs/heads/{options['primary']}", "Primary changed during retirement")
        wanted_checkout = options["primary"] if options.get("restore_primary") else snapshot["current"]
        require(final["checkout"] == wanted_checkout, "Checkout changed during retirement")
        require(final["head"] == (snapshot["target"] if options.get("restore_primary") else snapshot["head"]),
                "Checkout HEAD changed during retirement")
        require(not any(Path(item["worktree"]).resolve() == Path(value).resolve()
                        for item in final["worktrees"] for value in options.get("remove_worktree", [])),
                "Selected worktree remains registered")
    except (Blocked, OSError, ValueError, KeyError, TypeError) as exc:
        try:
            retained = final_state()
        except (Blocked, OSError, ValueError, KeyError, TypeError):
            retained = {"state": "unknown; inspect repository before retrying"}
        return {"schema_version": 1, "status": "partial" if completed else "blocked",
                "completed": completed, "failed_or_uncertain": action,
                "final_state": retained, "error": str(exc)}
    return {"schema_version": 1, "status": "applied", "completed": completed, "final_state": final}


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    subs = result.add_subparsers(dest="command", required=True)
    for command in ("status", "plan", "apply"):
        sub = subs.add_parser(command)
        sub.add_argument("--json", action="store_true")
        if command == "status":
            continue
        sub.add_argument("--project-root", required=True)
        if command == "apply":
            sub.add_argument("--plan", required=True)
            sub.add_argument("--confirm", required=True)
            continue
        for flag in ("remote", "primary", "branch", "repository"):
            sub.add_argument("--" + flag, required=True)
        sub.add_argument("--provider", choices=("github", "gitlab"), required=True)
        sub.add_argument("--review", required=True, type=int)
        sub.add_argument("--host")
        for flag in ("remove-worktree", "allowed-root", "inactive-worktree"):
            sub.add_argument("--" + flag, action="append", default=[])
        sub.add_argument("--restore-primary", action="store_true")
        if command == "plan":
            sub.add_argument("--output", required=True)
    return result


def main(argv=None):
    args = vars(parser().parse_args(argv))
    command = args.pop("command")
    args.pop("json")
    if command == "status":
        print(json.dumps({"schema_version": 1, "status": "ready",
                          "commands": ["status", "plan", "apply"],
                          "dependencies": {name: bool(shutil.which(name))
                                           for name in ("git", "gh", "glab")}}, ensure_ascii=True))
        return 0
    try:
        root = safe_path(args["project_root"])
        args["project_root"] = str(root)
        if command == "apply":
            result = apply_plan(root, Path(args["plan"]), args["confirm"])
        else:
            output = args.pop("output", None)
            result = make_plan(args)
            if output:
                destination = external(Path(output), root)
                with destination.open("x", encoding="utf-8") as handle:
                    json.dump(result, handle, ensure_ascii=True, indent=2)
                    handle.write("\n")
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0 if result["status"] in {"ready", "applied"} else 1
    except (Blocked, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"schema_version": 1, "status": "blocked", "error": str(exc)}, ensure_ascii=True))
        return 1


if __name__ == "__main__":
    sys.exit(main())
