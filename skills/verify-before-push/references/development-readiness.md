# Development mode and source readiness

This experimental read-only contract records a project's explicit development
mode and checks the consistency of source-readiness observations. It does not
execute tests, create pipelines, change Draft status or authorize an operation.
The existing project-policy diagnostics and canonical publication gates remain
in force.

## Keep the decisions separate

The project's `development.evidence_mode` selects `test_first` or
`final_verification`. Record this choice before implementation. When a choice
is first recorded after implementation has started, identify it as late. When
changing a recorded choice, retain the predecessor and the reason for the
change. A digest detects altered contents; it does not prove when a decision
was made or that implementation had not started.

`test_first` requires actual observed RED-to-GREEN evidence. Existing version 1
test-first evidence and its validator are unchanged. A final successful check
cannot establish a missing RED observation or test-first chronology.

`final_verification` records final check observations without a RED claim. It
is not an implicit exception to a project's required test-first workflow. A
conflicting policy or legacy instruction must be resolved explicitly; this
helper cannot relax it.

## Read-only commands

Use the installed skill's `scripts/development_readiness.py`. Supply the
project root and the same explicit repository role, operation and profile used
for policy diagnostics. JSON inputs are observation records, not shell commands.

```shell
python <skill-root>/scripts/development_readiness.py select-mode --project-root <project-root> --repository infrastructure --operation merge --decision <decision.json> --implementation-started false
python <skill-root>/scripts/development_readiness.py source-readiness --project-root <project-root> --repository infrastructure --operation merge --decision <decision.json> --subject <subject.json> --review <review.json> --implementation-complete true
python <skill-root>/scripts/development_readiness.py final-verification --project-root <project-root> --repository infrastructure --operation merge --decision <decision.json> --subject <subject.json> --evidence <final-evidence.json>
```

Add `--profile <name>` only for an explicitly selected profile. For a changed
decision, supply the immediately preceding record with `--previous-decision`.
Keep the full decision history; a supplied predecessor link does not prove that
earlier records were retained or that the history is authentic.

The CLI loads current policy diagnostics from the sibling policy loader. It
does not write or install records. Library callers provide that current report
explicitly through `select_mode`, `evaluate_source_readiness`, or
`validate_final_verification`; an arbitrary caller-constructed report is not
proof of actual project files.

## Record formats

Use the bundled closed schemas:

- [Mode decision](../schemas/development-mode-decision.schema.json).
- [Source-review observation](../schemas/development-source-review.schema.json).
- [Source-readiness diagnostic output](../schemas/development-source-readiness.schema.json).
- [Final-verification observation](../schemas/development-final-verification.schema.json).
- [Final-verification diagnostic output](../schemas/development-final-verification-result.schema.json).

Versions, record types, fields and digests are
validated; unknown fields are not silently ignored. Each decision identifies
the selected mode, repository/operation/profile scope, current policy digests,
selection subject, phase and rationale. A changed choice also identifies its
predecessor and change reason.

The phase is `pre_implementation` or `late_selection`. The explicit boolean
passed to `select-mode` describes the state when this selection is being
recorded. Reusing a prior record does not change its historical phase; the
helper cannot verify that phase against actual implementation history. A late
test-first choice cannot establish preimplementation test-first selection.

Decision records use `format: "development_mode_decision"`; source-review
records use `"development_source_review"`; final-check records use
`"development_final_verification"`. Each has `schema_version: 1`. The policy
digests retain the loader's bare hexadecimal form. Record bindings use
`sha256:<hex>`: remove only the record's own digest field, encode the remaining
JSON as UTF-8 with sorted keys, compact separators and unescaped Unicode, then
calculate SHA-256. The library's `digest(record, digest_key)` calculates this
binding without writing files. Rebinding a changed claim cannot make it true.

Successful source-readiness output retains its validated context, final subject,
decision/review digests and completion assertion in `bindings`, sealed by
`readiness_digest`. Final-verification output retains the corresponding context
and evidence digest with `report_digest`. Blocked reports use `bindings: null`;
the report digest still binds their diagnostics. These seals detect content
changes and do not attest the underlying claims.

`selection_subject` identifies the source when a mode was selected. `subject`
in review and final-check records identifies the final source. Each is either
`{"kind":"commit","identity":"<lowercase Git object ID>"}` or
`{"kind":"worktree","identity":"sha256:<manifest digest>"}` where supported.
The caller must supply and retain the actual source identity or manifest; shape
validation cannot reconstruct either. CI source-SHA observations require a
matching commit identity.

Final-verification observations use separate local and CI forms. Local runs
retain their argv and actual exit code. CI runs identify the provider, source
SHA, pipeline/job IDs, URL and observed status; they have no local exit code.
The source must match the selected policy. CI-only policy cannot be satisfied
by local-run observations. Unsupported merge-result subjects remain explicitly
unsupported rather than being treated as source-SHA checks.

This final-verification format does not replace the existing test-first format.
The distinct `validate_test_first_binding` library API accepts a policy-bound
wrapper using an injected trusted canonical v1 validator; the
`develop-with-test-first-evidence` consumer supplies that fixed validator through
its `evidence.py accept` command. The existing final-only API remains final-only.
Neither format alone proves that all checks in a separate project catalog were
executed.

The test-first wrapper and result use
[development-test-first-binding.schema.json](../schemas/development-test-first-binding.schema.json)
and [development-test-first-result.schema.json](../schemas/development-test-first-result.schema.json).
Nested v1 evidence is unchanged and must pass its canonical validator. Local
RED/GREEN observations cannot satisfy CI-only or forbidden-local execution;
native CI test-first evidence remains unsupported. The fixed runtime API and
capabilities are declared in [runtime-api.json](runtime-api.json). Installation
identity and API checks do not authenticate arbitrary filesystem contents.

Implementation completion, successful verification observations, and source
review are separate inputs. They must refer to the same final source identity.
A review of an earlier revision does not establish review of the final source.
Source-readiness consistency is separate from provider Ready status, independent
review requirements, and permission to push or merge.

The intended order is implementation completion, source review, provider Ready
transition, then final CI. Source readiness must not require a final CI result
that can only be produced after the Ready transition. Missing final CI remains
an unsatisfied verification result; it does not erase a separately consistent
source-readiness observation or authorize a merge.

## Evidence boundaries

The contract binds repository role, operation, selected profile, effective
policy and source-policy snapshot. Changed policy inputs require reevaluation,
even when the selected mode remains the same. Missing, malformed or stale
decision/review records cannot establish source readiness. Failed or missing
final-check observations leave final verification unsatisfied independently.

Caller-supplied records are assertions about observations. The helper does not
reconstruct Git objects, attest who reviewed the code, contact the CI provider,
or prove that a command ran. Preserve the actual command output or provider
evidence separately. Never manufacture local command exit codes from a CI job.

The helper does not replace the policy-bound GitLab CI collector, canonical
verifier receipts, or existing lifecycle state. Lifecycle version 1 still uses
its configured `tdd-red` and `tdd-green` checkpoints. Do not mark those required
checkpoints optional or synthesize records to force this diagnostic contract
into the old state machine.
