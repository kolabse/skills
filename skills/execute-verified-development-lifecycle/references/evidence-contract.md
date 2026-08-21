# Evidence contract

Each checkpoint envelope contains the plan and configuration digests, checkpoint name, attempt, status, timezone-qualified observation time, immutable subjects, assertions, and a SHA-256 digest of retained provider/project evidence. `evidence_ref` must resolve to a regular, non-symlink JSON file outside every configured repository and matching [`../schemas/retained-evidence.schema.json`](../schemas/retained-evidence.schema.json). The helper canonicalizes that whole document, verifies its digest, and requires its plan, configuration, checkpoint, timestamp, subjects, and assertions to equal the checkpoint envelope. Digests detect substitution; they do not make unsupported claims true.

## Subject binding

Use repository roles and provider-neutral identity kinds rather than workstation paths:

- `commit`, `tree`, and `ref` for source state;
- `review-change` for a merge/pull/change request;
- `pipeline` and `check-run` for remote validation;
- `development-integration` for the durable development identity;
- `production-handoff` for delegated release acceptance;
- `deployment`, `marker`, and `smoke-run` for delivery observations;
- `documentation` and `notification` for declared readiness/completion;
- `cleanup-resource` and `durable-target` for representation proof.

Evidence for a later identity must trace to the earlier immutable subject. A successful request receipt is not proof of completion; record the resulting observed identity.

The helper requires exactly these checkpoint-specific assertion names (except an optional skipped gate, which uses only `not-required-by-config`):

- `task-claimed`: `task-identity-observed`, `single-owner-confirmed`.
- `feature-prepared`: `feature-ref-created`, `base-identity-matches`, `no-edits-before-feature`.
- `tdd-red`: `relevant-test-failed`, `failure-matches-missing-behavior`.
- `tdd-green`: `relevant-test-passed`, `required-local-checks-passed`.
- `changed-scope-preflight`: `changed-scope-covered`, `repository-rules-covered`, `references-covered`.
- `review-complete`: `review-approved`, `reviewed-commit-matches`.
- `push-verified`: `exact-state-verification-passed`, `verified-commit-matches`.
- `feature-published`: `remote-feature-commit-matches`.
- `feature-pipeline`: `feature-pipeline-passed`, `pipeline-commit-matches`.
- `documentation-ready`: `documentation-ready`, `notification-dispositions-recorded`.
- `development-integrated`: `development-integration-observed`, `integrated-commit-represented`.
- `documentation-published`: `documentation-published`, `documentation-traceability-recorded`.
- `production-delegated`: `production-handoff-accepted`, `development-identity-matches`.
- `deployment-observed`: `deployment-identity-observed`, `development-identity-deployed`.
- `marker-observed`: `marker-identity-observed`, `marker-matches-deployment`.
- `smoke-passed`: `smoke-checks-passed`, `smoke-target-matches-deployment`.
- `documentation-complete`: `documentation-complete`, `notification-outcomes-documented`.
- `cleanup-proved`: `cleanup-targets-enumerated`, `upstream-representation-proved`.

A passed checkpoint requires every assertion true. A failed checkpoint requires at least one false assertion and its configured same-or-earlier rewind. `not-required` is accepted only for a configured optional gate. Assertions cannot replace corresponding bound subjects.

## Assertions and coverage

Assertions use stable names and `passed` results. `changed-scope-preflight` must include `coverage` arrays containing all configured repository names, rule IDs, reference IDs, check IDs applicable to changed scope, documentation target IDs, and notification IDs. Plan creation already requires full declared rule/reference coverage; preflight confirms which declarations apply.

`cleanup-proved` lists exact resource identities and one configured representation method per deletable resource. The helper validates evidence structure and declared coverage but does not delete anything.

Every subject names `kind`, `role`, `repository`, and immutable `identity`; `repository` is null only for genuinely non-repository subjects. Source-state checkpoints must cover every configured repository. Commit identity is carried from green verification through review, push verification, feature publication, and feature pipeline. `production-delegated` and `deployment-observed` both carry the exact `development-integration` identity observed at `development-integrated`; deployment must also match the production handoff. Marker and smoke checkpoints carry the exact deployment identity.

Verification does not trust `completed`, `attempts`, flags, or the state digest alone. It validates state structure and ordered-prefix invariants, then deterministically replays the complete history through the advancement validator. Replay reopens and rehashes every retained evidence file, including evidence for checkpoints later invalidated by a failure rewind, and the reconstructed state must equal the supplied state. The supplied state file is never modified.

Raw logs, tokens, credentials, personal data, and internal URLs do not belong in evidence. Retain them in an approved external store and record only a non-sensitive reference label plus digest.
