# Review the actual integration candidate

Keep one review record in the existing approved task or review evidence store.
A standalone review may report it in the response; a configured lifecycle may
require a retained artifact. Do not create project configuration just to review
a diff. `scripts/status.py` reports skill availability, not review completion.

## Bind the scope

Record repository roles/identities, source ref and full commit SHA, the diff
method and exact baseline SHA, target ref and observed target-tip SHA, reviewed
paths, applicable policy identity, reviewer and observation time. Keep the
findings, their dispositions and test gaps with this record. Use non-sensitive
labels and digests where raw paths or provider URLs would expose private data.

The merge-base used to compute a diff can differ from the target tip. Record
both; an unchanged diff alone does not prove that an advancing target remains
compatible. If reviewing uncommitted content, identify its content fingerprint
and state that the result covers that worktree. HEAD equality alone cannot
authorize integration of different staged or committed content.

## Check reuse and freshness

Before integration, freshly inspect the source and target identities, outstanding
findings and required approval state. Validate that an existing review covers
the complete intended scope and current project policy. Report reuse explicitly.

An amended/rebased commit, conflict resolution, changed baseline or changed
policy invalidates the old exact-revision decision. Review the affected delta
and its interactions, then issue an updated record covering the complete new
candidate; do not merely replace the SHA on old evidence. If only the target
advanced, assess integration impact and approval validity before updating the
target observation. A changed target must not silently inherit the prior
decision just because the merge-base stayed the same.

Recheck identity at the merge operation using the provider's supported expected
head/merge-queue mechanism when available. If the candidate changes while
review or merge is in progress, stop that integration attempt and refresh its
review evidence. Do not force or bypass a protected-branch gate.

## Findings and policy disposition

Lead with actionable findings, ordered by severity. If none are supported, say
"No actionable findings" and state meaningful gaps such as unrun integration
tests or unavailable runtime context. This is a bounded review conclusion,
not a guarantee of correctness or an automatic human approval.

Then report:

| Item | Required observation |
| --- | --- |
| Candidate | Repository role, full source SHA, diff baseline and target tip. |
| Review | Newly examined or reused; retained record and its observed identity. |
| Findings | Open findings and disposition, or explicit no-findings statement. |
| Policy | Required reviewers/approvals satisfied, pending, rejected or unverified. |
| Limits | Tests not run, inaccessible context and any remaining integration risk. |

A configured independent or human approval must be observed from its actual
source. Never create an approval or publish a review comment without the
applicable authorization. Outstanding policy requirements remain blockers even
when an agent finds no defects.

## Supply existing lifecycle evidence

When `execute-verified-development-lifecycle` applies, use its existing schemas:

- `commit` subjects cover every configured repository and match the corresponding
  `tdd-green` commits. Do not substitute branch names or the eventual merge SHA.
- `review-change` subjects identify the actual review event/change revision.
  Pair the event with its exact commit; a mutable PR number alone is insufficient.
- Set `reviewed-commit-matches` only after validating this identity pairing.
- Set `review-approved` only when the configured review conditions are satisfied,
  including any required independent/human approval. Otherwise retain a failed
  checkpoint or report pending evidence, according to the existing contract.
- Retain the review report and bind its digest through `artifact_sha256` in the
  retained evidence document. Keep the existing envelope fields and assertions;
  do not insert display fields into the schema or invent a passing checkpoint.

The lifecycle helper checks envelope integrity and commit continuity. It does
not fetch provider approvals or independently prove the truth of the review
report. The producer must inspect and retain the supporting observations.

GitFlow review evidence likewise names the planned source commit and source/
target branches with the report digest. Its verifier does not reopen that report
or validate live target-tip approval freshness; perform those checks before
integration rather than claiming the helper did them.
