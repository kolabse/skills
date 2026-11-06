# Publication authorized after local work

Keep permission to edit, commit, publish, and integrate distinct. An explicit
instruction to postpone commit or publication takes precedence over the normal
publish-before-edit bootstrap. Do not ask again for authorization already given,
and do not infer remote publication from permission to make local changes.

## Prepare local work

1. Fetch and classify the repositories required by the task. Resolve and record
   each configured base and its current SHA before editing.
2. Use a clean local task branch/worktree when isolation is needed. Preserve
   unrelated dirty work and occupied branches. A branch deliberately prepared
   for local-only work may have no upstream; record that state rather than
   assigning the base branch as its task upstream or publishing it implicitly.
3. Record the local branch, base SHA, worktree, and authorization boundary in
   the existing task record. Keep the record local when publication is deferred.
   Work only within the authorized scope; do not create commits if the user
   postponed commits as well as pushes.

The clean worktree requirement applies at preparation. Authorized edits may
make it dirty afterward; do not discard them to recreate a clean base.

## Transition when publication is requested

Perform this checkpoint before the first authorized remote write and before
further implementation work. The already-authorized local changes remain valid.

1. Confirm the actual scope of the new request. Commit-only permission leaves
   publication deferred. Permission to push does not by itself authorize merge,
   release or deployment.
2. Fetch again and inspect the saved task branch, local commits, dirty paths,
   configured base and proposed remote task ref. Preserve all local work. If
   the base moved, show the new commits and whether the task includes them.
   Resolve any required integration as a deliberate development step under the
   existing authorization; do not automatically stash, reset, rebase, merge or
   clean as part of synchronization. Ask only if the target or preservation
   decision remains materially ambiguous.
3. Verify the current configured base in a clean anchor. If that base fails,
   use the bounded recovery procedure below instead of repeating this checkpoint.
   Otherwise use the
   [linked-worktree recipe](linked-worktrees.md) when the task worktree is dirty
   or already contains commits. Satisfy every applicable protected-push gate
   for that anchor; evidence for a dirty or different worktree is insufficient.
4. Resolve the branch naming policy and check the final name against its saved
   decision using [branch-policy preflight](branch-naming-policy.md), then
   select an unused remote task ref and publish the verified base SHA to it.
   Outside the explicitly selected failed-base recovery route below, do not
   push the local task HEAD in place of the base bootstrap. If the
   intended ref is occupied, establish its recorded ownership or choose a new
   unambiguous task name; never overwrite it to make the checkpoint pass.
5. Bind the existing local task branch to its own new remote ref, preserving
   local commits and edits. Verify the remote ref equals the checked base and
   the task's actual ahead/behind relationship. Unlike a fresh bootstrap, a
   task with prior local commits may legitimately be ahead. Missing required
   base changes or divergence must be resolved before content publication.
6. Commit the intended work when authorized, run the configured checks for the
   exact task state, validate its own gate, then push the task content. Anchor
   evidence authorizes only the base bootstrap; it cannot authorize the later
   task commit. Recheck freshness at each publication boundary.

Record the verified base, task ref, transition decision and both applicable
verification results. Do not rewrite timestamps or history to suggest the
remote branch existed before local edits. If publication is postponed again,
retain the local work and record the remaining checkpoint.

## Expected decisions

| Situation | Required outcome |
| --- | --- |
| Local edits allowed; commit and push postponed | Preserve local edits; no commit or remote task ref. |
| Local commits allowed; push postponed | Keep commits local; record intentional missing task upstream. |
| Publication later allowed; base unchanged | Gate the clean base, publish it, bind the task upstream, then gate and publish task content. |
| Base moved or task diverged | Preserve work; resolve required integration deliberately and obtain fresh evidence. |
| A remote task ref is unexpectedly occupied | Establish ownership or select another name; no forced replacement. |

## Recovery when the unchanged base fails its gate

A failing base is a recorded blocker, not permission to bypass verification.
Record the exact base SHA, failed check and observed failure before choosing a
route. Do not repeatedly demand a successful unchanged base as the prerequisite
for repairing that same failure.

First determine whether existing project instructions and authorization allow
local repair before the first publication. Reuse an applicable authorization;
otherwise obtain a bounded exception covering the local repair and, separately,
the proposed publication route. A mandatory project rule requiring a successful
unchanged-base bootstrap remains blocking until explicitly amended by its
authorized owner. This reference does not override that rule.

When the project permits a repair-first route:

1. Preserve the failed base and work in a local task branch from its recorded
   SHA. Record that no remote task ref exists yet. Limit edits to the authorized
   repair; retain unrelated work separately.
2. Review and commit the repair when authorized. Run every applicable protected
   push check against this exact repaired commit and worktree. A failed baseline
   is evidence of the defect, never successful push evidence.
3. The gate must support the actual unpublished branch state under the approved
   project contract. Do not fabricate an upstream, attach the primary ref as the
   task upstream, edit a receipt, or silently disable an upstream/check rule. If
   the gate cannot represent this route, stop publication and report the needed
   project configuration decision.
4. Fetch and re-evaluate base freshness, review validity, branch naming and the
   unused destination ref. Once the exact repaired state passes its gate, publish
   that commit as the first remote task revision and bind its own upstream.
   Continue through ordinary review/CI/integration requirements.

For example, base B fails a required check; bounded local repair produces R.
Under an explicitly permitted repair-first contract, review and all required
checks on R authorize its publication. The first remote task SHA is R, not B;
the record retains both the failure on B and success on R. Without that contract
or successful evidence on R, neither revision is publishable through this route.

Completion criterion: local work remains intact, publication starts only when
authorized, the task tracks its own remote ref, and each protected push has
evidence for the actual state being published. The normal route bootstraps the
verified unchanged base; an authorized failed-base recovery records the explicit
exception and the verified repaired first revision without rewriting history.
