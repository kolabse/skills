---
name: retire-merged-task-branches
description: "Plan and apply cleanup of a merged task's local and remote Git branches and explicitly selected inactive worktrees, using fresh GitHub PR or GitLab MR evidence and exact revision checks. Use when retiring completed task resources or assessing whether a squash/rebase-merged branch is safe to remove. Do not use for merging reviews, deleting unmerged work, generic file cleanup, or collection release cleanup."
---

# Retire Merged Task Branches

Retire only resources belonging to one identified merged task. Use the project's
declared integration target and remote; a familiar branch name is not policy.
The helper observes provider and Git evidence, produces a digest-bound plan,
and applies only that plan. Planning does not authorize deletion.

This skill is experimental. Keep uncertain work and report its blocker. It does
not merge reviews, release software, deploy, reset a checkout, or delete an
arbitrary directory.

## Select the task and inspect prerequisites

1. Identify the repository, task branch, review number, provider, and configured
   primary branch. Establish repository freshness with
   `$synchronize-git-repositories` (Claude Code: `/synchronize-git-repositories`).
   The local primary must match the freshly observed remote primary. Preserve
   divergence instead of aligning it by resetting or rebasing.
2. Inspect available tooling without writing configuration:

   ```shell
   python <skill-root>/scripts/retire_branches.py status --json
   ```

   GitHub uses an authenticated `gh`; GitLab uses an authenticated `glab` and an
   explicit `--host`. Credentials stay in those tools' existing authentication
   stores. Never put tokens in repository URLs, plans, or command arguments.
3. Read [the proof and preservation contract](references/cleanup-contract.md)
   before selecting worktrees or interpreting rewritten integration evidence.
   Confirm which worktrees are inactive with the user or the task coordinator.
   Git cleanliness alone cannot establish that another agent has stopped work.

## Prepare a concrete plan

From a checkout that will remain available, run:

The task branch must not be current in this checkout. If the requested cleanup
includes restoring it to primary, first switch the clean retained checkout with
`git switch --no-overwrite-ignore <configured-primary>` using the existing task
authorization. Preserve ignored files if Git refuses that switch. The helper
does not remove its own checkout or silently switch away from a task branch.

```shell
python <skill-root>/scripts/retire_branches.py plan \
  --project-root <repository-root> --remote <remote> \
  --primary <configured-primary> --branch <task-branch> \
  --provider github --repository <owner/repository> --review <number> \
  --output <external-plan.json> --json
```

For GitLab use `--provider gitlab --host <gitlab-host>` and the full namespace
path for `--repository`. The helper is stateless; plans are per-operation
artifacts outside the repository, not project configuration.

The plan reads current provider and remote state without fetching or modifying
refs. If local state is stale, synchronize it and generate a new plan. A source
tip newer than the merged revision must be retained even if the review is merged.

Worktree removal is opt-in. For each inactive task worktree add all three:

```shell
--remove-worktree <absolute-task-worktree> \
--allowed-root <explicitly-approved-parent-directory> \
--inactive-worktree <same-absolute-task-worktree>
```

Only use the inactivity acknowledgement after checking task ownership. Do not
derive it from a clean status or an elapsed timeout. The current checkout and
the main worktree are preserved. Do not remove a worktree manually to bypass a
blocked plan. Add `--restore-primary` only when returning the retained checkout
to the configured primary is part of the requested cleanup.

Show the exact branch revisions, remote destination, selected worktree paths,
representation proof, proposed checkout change, and retained resources. If the
plan is blocked, report the reason and preserve all affected resources.

## Apply the reviewed scope

User authorization must cover the concrete resources and actions in the plan.
Reuse explicit authorization already given for that scope; ask only when it is
missing or the plan adds actions. Never interpret a request to inspect cleanup
as permission to execute it. The digest is a technical confirmation, not proof
that the user approved deletion.

```shell
python <skill-root>/scripts/retire_branches.py apply \
  --project-root <repository-root> --plan <external-plan.json> \
  --confirm <exact-plan-digest> --json
```

Apply refreshes and rechecks the plan. Changed tips, provider evidence, worktree
state, or repository identity invalidate it. Generate and review a new plan;
do not edit a plan or bypass a failed comparison. Respect any project-required
push verification for remote ref deletion; this helper is not a substitute for
that policy.

Report each completed and retained resource and the final checkout state. A
partial result is not full cleanup. Do not recreate deleted refs as an automatic
rollback, retry an old plan, or force removal after a failure.

## Compose without changing ownership

`execute-verified-development-lifecycle` coordinates cleanup evidence and does
not execute deletion. Supply this helper's observed result as a source artifact
for the project's configured cleanup evidence adapter; do not claim it is a
drop-in lifecycle checkpoint payload. Use `release-skill-collection` for its
audited collection-release cleanup contract. This task executor does not relax
that contract or start a release as a prerequisite to ordinary task cleanup.
