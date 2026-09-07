# Show lifecycle progress from evidence

Use the existing plan, state and retained checkpoint evidence as the source of
truth. The table is a human-readable projection, not another state file or a
new schema. Keep output concise: show the full ordered gate list at planning
and completion, and changed rows plus the current blocker during work.

## Report header and rows

Name the lifecycle ID, plan/configuration digests, current checkpoint and the
actual source commits by repository role. At delivery, also identify the
development integration and delegated production/deployment subjects. Report
when the evidence was observed and when external freshness was last checked.

| Gate | Applicability | State / attempt | Evidence and subject | Next action / blocker |
| --- | --- | --- | --- | --- |
| review-complete | Required by contract | Pending | Source SHA; required approval not yet observed | Obtain the configured review result. |
| feature-pipeline | Required by contract | Pending | No completed run for this source SHA | Wait for the matching pipeline. |
| cleanup-proved | Required by contract | Pending | No representation proof yet | Retain enumerated resources. |

These are illustrative pending rows, not results to copy into a real task.
Populate every row from actual observations:

- **Passed:** the current accepted checkpoint has matching retained evidence.
- **Not required:** the configuration permits the skip and the accepted
  checkpoint records `not-required` with `not-required-by-config`.
- **Excluded by delivery configuration:** the configured delivery flags remove
  an optional deployment, marker or smoke gate from the active order. Cite that configuration
  decision; no checkpoint can or must be submitted for the excluded stage.
  Keep this distinct from skipping an optional active gate.
- **Pending:** required evidence has not arrived; do not manufacture a failure
  event or approval merely to fill the table.
- **Failed / retry:** history records failure and its configured rewind. Show
  the attempt count and next required checkpoint from the actual state.
- **Invalidated:** a downstream result was removed by rewind or no longer
  matches the planned subject. Keep the historical result distinguishable from
  the current decision; do not count it as passed.
- **Blocked / unverified:** a missing capability, contract input, invalid
  artifact or unavailable external observation prevents a justified decision.

Unavailable tools or services do not turn required gates into optional ones.
Explain cross-repository dependencies using configured roles and exact revision
pairings; a result for one repository cannot silently satisfy another's gate.

## Verify the view

Use the existing read-only `verify --project-root ... --plan ... --state ...
--json` command to replay retained history. An unfinished lifecycle can return
valid progress information with `passed: false` and missing-checkpoint blockers;
that is not a completed lifecycle. Invalid/tampered evidence must not be shown
as accepted merely because the state file contains a success flag.

Replay proves internal consistency of retained evidence, not live external
freshness. Separately synchronize Git and inspect relevant current review/CI/
delivery observations at their authorized boundaries. Distinguish "retained
evidence verified" from "current remote state observed". A stale source commit
or changed plan requires the contract's invalidation/replanning procedure.

If work occurred before a plan existed, identify those observations and the
missing formal evidence honestly. Do not fabricate a pre-edit plan, backdate
checkpoints, or claim ordered stages merely because normal development happened.

## Completion and delivery limits

At completion, show all configured gates and remaining limitations. A passed
handoff means production was delegated, not deployed. Deployment, marker and
smoke rows must use the observed matching delivery identities. Documentation
and required notification dispositions must remain visible.

`cleanup-proved` establishes representation of enumerated resources; it does
not delete them. State which resources were actually removed by an authorized
operation and which were retained, with reasons and observation references.
Do not call the full task complete while an explicitly required cleanup action
is still outstanding, even if representation proof passed.
