---
name: synchronize-git-repositories
description: "Safely establish remote freshness for one or more existing Git repositories without overwriting local work, and bootstrap an authorized publishable feature branch at a verified primary-branch SHA before the first code edit. Use when a repository has a configured remote or upstream and the task depends on current remote state: before analysis, edits, validation, commits, pushes, deployments, or remote execution when project policy requires synchronization; across related code, infrastructure, or documentation repositories; when the user asks to fetch, pull, update, compare with upstream, check whether repositories are current, or publish a feature branch before work; and when configuring a synchronization policy in AGENTS.md. Do not use for local-only Git work, repository initialization, conceptual Git help, or destructive remote-ref operations unless synchronization is also requested."
---

# Synchronize Git Repositories

Treat synchronization as a freshness and preservation check. Bring safe
fast-forward updates into clean worktrees; never hide, overwrite, or rewrite
local work merely to make a repository appear current.

## Configure the project policy

1. Resolve the project boundary and inspect the applicable `AGENTS.md` files.
2. When no equivalent policy already exists, run the idempotent helper:

   ```shell
   python <skill-root>/scripts/configure_project.py configure --project-path <project-root>
   ```

   It preserves unrelated content and adds exactly one managed block:

   ```markdown
   <!-- synchronize-git-repositories:start -->
   ## Repository synchronization

   Use `$synchronize-git-repositories` before analysis, edits, validation,
   commits, pushes, deployments, or remote operations. Synchronize every
   repository involved in the task with its tracked upstream using safe
   fast-forward updates, preserve dirty worktrees, and never resolve divergence
   with an automatic stash, reset, rebase, merge, clean, or force-push.
   For authorized changes intended for publication, publish a feature branch
   from the verified current primary-branch SHA before the first code edit and
   track that branch's own remote ref rather than the primary branch.
   <!-- synchronize-git-repositories:end -->
   ```

3. Do not encode workstation-specific absolute paths. Name stable repository
   roles or relative locations only when the project must always coordinate a
   known set of repositories.
4. Run the synchronization workflow once after configuration.

Inspect configuration without changing files with:

```shell
python <skill-root>/scripts/configure_project.py status --project-path <project-root> --json
```

Completion criterion: one effective project policy invokes this skill, existing
instructions remain intact, and the initial repository state is reported.

## Publish the feature branch before editing

Apply this bootstrap only when the user has authorized repository changes that
are intended for publication. Do not create remote branches for read-only or
local-only work.

1. Fetch and prove that the primary branch is clean and current with its
   tracked upstream. Resolve divergence before proceeding.
2. Satisfy any protected push gate for that unchanged primary-branch SHA.
3. Choose a task-specific feature-branch name and confirm that its remote ref
   does not already exist. Never overwrite or reuse an ambiguous remote branch.
4. Publish the verified SHA as the new remote feature ref before changing any
   tracked file, then create the local branch tracking that exact ref. For
   example:

   ```shell
   git push origin HEAD:refs/heads/codex/example-change
   git switch --create codex/example-change --track origin/codex/example-change
   ```

5. Prove that local HEAD, the new remote feature ref, and the verified primary
   SHA are identical, that the worktree is clean, and that the feature branch
   tracks its own remote ref. Only then begin editing.

Do not temporarily assign `origin/main` or another primary ref as the feature
branch upstream. Subsequent commits and pushes use the feature branch's own
upstream and the normal verification gate.

Completion criterion: the remote feature branch exists before the first edit,
the local feature branch tracks it at the verified base SHA, and no source or
history change was included in the bootstrap push.

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

After fetching, run the dependency-free classifier when available:

```shell
python <skill-root>/scripts/classify_repository.py \
  --repository <repository-root> --json
```

For diverged branches, distinguish ordinary divergence from `identical-tree`,
`patch-equivalent`, and one-sided patch representation. These equivalence
signals show that content may already be represented under different commit
IDs; they do not authorize rewriting a branch.

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
- For equivalent divergence, offer a separate explicit plan that first creates
  a recoverable backup ref and then aligns the branch only after user approval.
  Never perform that plan as part of ordinary synchronization.
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
