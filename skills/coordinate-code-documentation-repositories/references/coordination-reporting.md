# Show and retain one coordinated outcome

Use this procedure when a change spans application behavior and authoritative
documentation in another repository, optionally with additional required roles.
Keep role labels meaningful without exposing private repository names or paths.

## Resolve responsibilities and show progress

At activation, identify the intended outcome, each required role, and which
role owns canonical documentation. For example, application code can be
`implementation`, an infrastructure repository containing the authoritative
runbook can be `documentation`, and separate deployment automation can be
`operations`. A shared Git root must appear only once. Do not invent a docs
repository or treat an unrelated repository as a required participant.

Show one compact table after planning, at publication transitions or failures,
and at completion. Use the existing task record rather than a second tracker:

| Role / responsibility | Planned → final SHA | Validation | Publication | Blocker / next action |
| --- | --- | --- | --- | --- |
| implementation / behavior | exact observed revisions | check receipt and covered SHA | pending / observed at SHA | remaining action |
| documentation / canonical sources | exact observed revisions | topic review and check receipt | pending / observed at SHA | remaining action |
| operations / required automation | exact observed revisions | role-bound check receipt | pending / observed at SHA | remaining action |

Include only configured roles. State the plan digest, canonical source/target
paths, planned publication order or absence of an ordering constraint, and
the latest synchronization observation. During work, unknown final commits
remain pending. A successful check of one role does not complete the others.
Distinguish final local commits, pushed task branches, merged changes, and
deployed behavior; the helper verifies the tracked branch, not all these stages.

## Adopt helpers alongside claims and task cards

Keep the project's claim system for ownership and scope. Map its requirements
to `outcome` and required documentation `topics`, its canonical files to
`documentation_sources` / `documentation_targets`, and its repository owners
to the configuration's roles. Include a required `operations` role only if it
owns a separate repository whose content must change.

Run `status` after synchronization and generate a blocker-free `plan` before
implementation. Retain the external plan path and `plan_sha256` in the approved
task evidence store. Reference that digest from the existing task card when
authorized. A card, a claim, or successful individual checks do not substitute
for this plan or for `verify`.

If work has already started without a plan, disclose the gap. Do not fabricate
a historical starting state or create a plan at the final revisions and claim
it covered earlier work. Preserve the changes and use a project-approved
recovery plan for the remaining work, with historical evidence reviewed
separately. Report retrospective review separately from helper verification.

Before the first push of task content in any required role, retain one record binding the plan to
all final commits and their passed pre-push evidence. Honor any configured
`publication_order`; if absent, resolve real dependencies from the project
before choosing an order. Record actual publication observations. If a later
publication fails, report the already-published roles and the blocked joint
outcome; resume only after refreshing state and the affected evidence.

After publication, assemble the formal verification input. Use the configured
traceability method; `project-record` may reference existing claim/task-card
evidence, while `change-request` uses the actual related changes. Do not change
the configured method just to accept an available artifact. Retain the helper's
verification result and compare the documented claims with the implemented
behavior and operational checks.

Prepare any tracked task-card updates before the common checkpoint. Keep final
SHA bindings and verification receipts outside the participating repositories
or in a separate approved evidence store, so recording completion does not
itself change a verified commit. A later tracked edit requires refreshed
commit-bound checks and joint verification; do not create circular commits
solely to embed their own final identities.

## State the limits of the result

`status`, `plan`, and `verify` inspect local Git and tracking refs; they do not
fetch live remote state. Run synchronization first and report its observation
separately. Digest checks detect content changes, not authenticity: the helper
does not open the referenced validation or traceability artifacts, reproduce
checks, establish semantic agreement, or prove publication order. Review the
retained evidence before asserting those properties.

If a role, scope, final SHA, configuration, or upstream changes, invalidate the
affected decision and re-plan or re-verify as required. Do not edit an old plan
digest to make earlier evidence appear current. Completion requires both the
helper's passing result and the task's actual semantic, publication, and any
separately required integration or deployment conditions.
