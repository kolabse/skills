# Report the configured release route

Maintain one compact record derived from the frozen plan, actual gate results,
review, fresh remote observations and verification result. This is a report,
not a new helper schema or permission to perform external actions.

Identify the route, plan/configuration digests, source branch and full commit,
target branch, observed production identity and current development identity.
Name the configured source of any default-route decision. For hotfix, retain
the explicit intent; never reinterpret an ordinary merge as production repair.

| Stage | What the record must show |
| --- | --- |
| Plan | Selected route, source/target roles and immutable identities; blockers. |
| Gates | Every planned common and route-specific gate, result and evidence for the source SHA. |
| Review | Reviewed source and target, current policy approval, report digest and remaining findings/test gaps. |
| Publication | Actual production result and observed remote SHA, or pending/failed status. |
| Deployment | Observed identity and evidence, or a contract-supported not-required disposition. |
| Reintegration | Required route/project decision, target and represented commit, or explicit blocker. |
| Cleanup | Exact temporary resources, representation proof, actual removal or retention reason. |

Use pending, passed, failed, blocked, invalidated or not-required as display
labels justified by observations. Do not insert these labels into fixed helper
schemas where unsupported. Show failed attempts and retries without erasing
their outcomes. Required gates cannot be skipped because evidence is missing.

Revalidate source identity and review freshness before integration. Record
target-tip changes separately from the review baseline. Changes to the planned
source invalidate its gate and review evidence; use a fresh plan/evidence as
required by the existing contract. A no-findings review does not grant a
required provider or human approval.

The verifier reads current local remote-tracking refs but does not fetch them.
Synchronize first and report the observation time. Its passed result proves
the declared production/deployment conditions and, for hotfix, reintegration.
It does not prove that standard-route stabilization changes were returned to
development, that temporary branches were deleted, or that provider approval
is still current. Retain separate evidence for those project obligations.

Report production publication separately when hotfix reintegration is blocked.
For a standard preparation branch, keep required return of stabilization fixes
visible until observed. Do not label the entire requested workflow complete
while these required actions remain outstanding.

Cleanup needs exact resource identity and fresh project-approved representation
proof. Branch naming patterns or a successful pipeline are insufficient. Report
"retained; deletion not authorized" when appropriate instead of deleting to
make the table green. A request already authorizing cleanup remains sufficient;
do not ask again merely because this reporting step was reached.
