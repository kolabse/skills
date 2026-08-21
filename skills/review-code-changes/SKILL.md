---
name: review-code-changes
description: "Review a defined code change for actionable correctness, security, reliability, and compatibility defects with evidence-bound findings. Use for diffs, branches, commits, or pull requests; do not use for general code explanation or requests to implement review feedback."
---

# Review Code Changes

Review the requested change read-only unless the user separately authorizes publication or implementation.

## Establish scope

Resolve the exact baseline, changed state, applicable project instructions, and intended behavior. Inspect the diff and only the surrounding code, tests, schemas, and contracts needed to judge it. Disclose when the baseline or required context is unavailable.

## Evaluate findings

Prioritize defects that can cause incorrect results, security exposure, data loss, races, broken compatibility, or operational failure. Validate suspected findings with read-only checks where practical. A useful finding states the triggering condition, impact, evidence, tight file location, priority, and concise remediation direction.

Do not present style preferences or speculative possibilities as defects. Do not require parallel agents, issue-tracker setup, comments, approvals, or external publication. Never mutate the reviewed code merely to prove a point.

## Report

Order actionable findings by severity. Keep summaries secondary to findings. If none are supported, say so and identify remaining uncertainty or meaningful test gaps.

Completion criterion: the exact change scope was examined, each finding is reproducible or evidence-backed and precisely located, uncertainty is explicit, and no review action or code change occurred without authorization.
