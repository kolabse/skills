---
name: review-code-changes
description: "Review a defined code change for actionable correctness, security, reliability, and compatibility defects with evidence-bound findings. Use for diffs, branches, commits, pull requests, and requests to merge or integrate a defined change; validate any current revision-bound review before reusing it. Do not use for general code explanation, merge-status questions, or requests only to implement review feedback."
---

# Review Code Changes

Review the requested change read-only unless the user separately authorizes publication or implementation.

## Activate at the review boundary

When asked to merge or integrate a defined change, select this workflow before
integration even if the user did not separately ask for review. Announce the
skill once and name the change being assessed. A status question, explanation
of merge strategies, or request only to implement existing feedback does not
activate a new review.

First inspect any existing review. If it covers the exact current change and
still satisfies project policy, validate and report its reuse instead of
repeating the same examination. Otherwise review the missing or changed scope.
This does not grant provider approval, publish comments, or authorize a merge
that the user has not requested.

## Establish scope

Resolve the exact baseline, changed state, applicable project instructions, and intended behavior. Inspect the diff and only the surrounding code, tests, schemas, and contracts needed to judge it. Disclose when the baseline or required context is unavailable.

Use [references/revision-bound-review.md](references/revision-bound-review.md)
to distinguish source commit, diff baseline and current target tip. Record the
review scope and evidence before treating it as a pre-merge result. A clean CI
run is relevant validation, but is not evidence that a code review occurred.

## Evaluate findings

Prioritize defects that can cause incorrect results, security exposure, data loss, races, broken compatibility, or operational failure. Validate suspected findings with read-only checks where practical. A useful finding states the triggering condition, impact, evidence, tight file location, priority, and concise remediation direction.

Do not present style preferences or speculative possibilities as defects. Do not require parallel agents, issue-tracker setup, comments, approvals, or external publication. Never mutate the reviewed code merely to prove a point.

## Report

Order actionable findings by severity. Keep summaries secondary to findings. If none are supported, say so and identify remaining uncertainty or meaningful test gaps.

After the findings, include a compact receipt: reviewed source/baseline/target
identities, review performed or reused, policy disposition, and meaningful test
gaps. Immediately before integration, recheck the actual source and target and
required approval state. Do not present an old review as current after the
subject or governing policy changes. Follow the reference when supplying the
existing lifecycle `review-complete` gate.

Completion criterion: the exact change scope was examined, each finding is reproducible or evidence-backed and precisely located, uncertainty is explicit, and no review action or code change occurred without authorization.
