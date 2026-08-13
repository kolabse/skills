---
name: synchronize-git-repositories
description: "Safely establish remote freshness for one or more existing Git repositories without overwriting local work. Use when a repository has a configured remote or upstream and the task depends on current remote state: before analysis, edits, validation, commits, pushes, deployments, or remote execution when project policy requires synchronization; across related code, infrastructure, or documentation repositories; when the user asks to fetch, pull, update, compare with upstream, or check whether repositories are current; and when configuring a synchronization policy in AGENTS.md. Do not use for local-only Git work, repository initialization, conceptual Git help, or destructive remote-ref operations unless synchronization is also requested."
---

# Synchronize Git Repositories

Treat synchronization as a freshness and preservation check. Bring safe
fast-forward updates into clean worktrees; never hide, overwrite, or rewrite
local work merely to make a repository appear current.

## Configure the project policy

1. Resolve the project boundary and inspect the applicable `AGENTS.md` files.
2. Preserve an existing equivalent policy. Otherwise add this managed block to
   the repository-level `AGENTS.md` without changing unrelated instructions:

   ```markdown
   <!-- synchronize-git-repositories:start -->
   ## Repository synchronization

   Use `$synchronize-git-repositories` before analysis, edits, validation,
   commits, pushes, deployments, or remote operations. Synchronize every
   repository involved in the task with its tracked upstream using safe
   fast-forward updates, preserve dirty worktrees, and never resolve divergence
   with an automatic stash, reset, rebase, merge, clean, or force-push.
   <!-- synchronize-git-repositories:end -->
   ```

3. Do not encode workstation-specific absolute paths. Name stable repository
   roles or relative locations only when the project must always coordinate a
   known set of repositories.
4. Run the synchronization workflow once after configuration.

Completion criterion: one effective project policy invokes this skill, existing
instructions remain intact, and the initial repository state is reported.

## Identify the synchronization set

1. Start with repositories explicitly named by the user and Git roots inside
   the active workspace. Include related code, infrastructure, configuration,
   and operational documentation repositories only when the current task uses
   them or project instructions require them.
2. Resolve each repository by its Git root and remote identity. Do not assume
   that related clones are adjacent or scan unrelated directories broadly.
3. Read applicable repository instructions before selecting remotes or branch
   policy. Follow a declared remote or upstream instead of assuming `origin`.
4. Treat submodules and linked worktrees as separate synchronization concerns
   when the task actually uses them. Do not initialize or update submodules
   implicitly.

Completion criterion: every repository whose changing state can affect the task
is listed once, and no unrelated repository is included.

## Inspect before updating

For each repository, collect read-only evidence equivalent to:

```shell
git status -sb
git remote -v
git branch --show-current
git rev-parse --abbrev-ref --symbolic-full-name @{upstream}
```

Adapt upstream syntax to the active shell. Record detached HEAD, missing
upstream, in-progress merge/rebase/cherry-pick, dirty tracked files, untracked
files, and local commits. Never print credential-bearing remote URLs; redact
embedded usernames, tokens, and query strings.

Completion criterion: the current branch or detached state, worktree condition,
tracking branch, and preservation risks are known before any fetch or pull.

## Fetch and classify

1. Fetch the tracking remote with pruning. Use `git fetch --prune <remote>`;
   use `--all` only when project policy requires every remote.
2. Re-read status and compare `HEAD` with the tracked upstream, for example with
   `git rev-list --left-right --count HEAD...@{upstream}`.
3. Classify the repository:
   - **current**: neither side has new commits;
   - **behind only**: upstream can fast-forward the local branch;
   - **ahead only**: local commits are unpublished, but no upstream commit is
     missing;
   - **diverged**: both sides contain unique commits;
   - **untracked**: no usable upstream exists;
   - **operation in progress**: Git metadata shows an unfinished operation.
4. A dirty worktree is an additional preservation constraint, not a divergence
   classification. Report it separately.

Completion criterion: classification uses fetched remote state rather than a
stale local tracking reference.

## Apply only safe updates

- For a clean **behind-only** branch, run `git pull --ff-only` or an equivalent
  explicit fast-forward from its tracked upstream, then re-read affected files
  and repeat dependent checks.
- For **current** or **ahead-only**, do not create a merge commit or rewrite
  history. Preserve local commits and report unpublished commit counts.
- For a dirty **behind-only** branch, do not pull automatically. Fetch, identify
  whether upstream changes overlap local paths, and report the exact condition.
  Continue only when the task can safely remain read-only or the user chooses a
  preservation strategy.
- For **diverged**, **untracked**, detached, or **operation in progress** states,
  do not invent a repair. Report the commits and state needed for a deliberate
  decision.
- Never run automatic `stash`, `reset`, `rebase`, `merge`, `checkout`, `switch`,
  `clean`, force-push, branch deletion, or submodule update as synchronization.

Completion criterion: every update is a clean fast-forward, and every unsafe or
ambiguous state remains preserved with a precise explanation.

## Maintain freshness during the task

Repeat fetch, classification, and any safe fast-forward:

- after a long analysis when remote state may have changed;
- immediately before editing when project policy requires it;
- before each commit and push;
- before deployment, remote execution, migration, or other external mutation.

If synchronization changes files already inspected, edited, generated, or
validated, re-read them and rerun the checks whose inputs changed. A successful
fetch alone does not prove that the working branch contains upstream changes.

## Report the result

For each repository report its branch, upstream, clean or dirty state,
ahead/behind classification, action taken, and remaining blocker. Distinguish
"fetched" from "fast-forwarded" and "current". Do not claim the whole project
is synchronized while a required repository remains behind or unresolved.

Completion criterion: the report proves which repositories are current, which
local work was preserved, what changed during synchronization, and what still
requires a decision.
