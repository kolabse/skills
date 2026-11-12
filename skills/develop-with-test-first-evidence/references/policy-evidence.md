# Policy-aware development evidence

Use this route when `.agents/kolabse/project-policy.json` explicitly configures
the development workflow. It consumes recorded observations; it never runs
checks, starts pipelines, installs dependencies or authorizes publication.
Without a policy, the original v1 test-first workflow remains available.

## Choose the mode before implementation

Use the shared `verify-before-push` runtime's policy diagnostics to resolve the
repository role, operation and explicitly selected profile. The effective
`development.evidence_mode` selects `test_first` or `final_verification`.
Record that choice using its `development_readiness.py select-mode` command
and the development-mode-decision schema before changing implementation.
Read that runtime's `references/development-readiness.md` for decision fields
and predecessor history.

For example, with a reviewed installed dependency:

```shell
python <policy-runtime-root>/scripts/development_readiness.py select-mode --project-root <project-root> --repository application --operation merge --decision <decision.json> --implementation-started false
```

Select `--profile <name>` only when declared for this repository and operation.
A later selection uses `--implementation-started true` and its explicit late
phase. Retain previous decisions and the reason for a change. Late selection
does not establish preimplementation test-first chronology; hashes do not prove
when a decision was recorded.

## Accept recorded observations

The consumer CLI loads current project policy and delegates its interpretation
to that shared runtime:

```shell
python <skill-root>/scripts/evidence.py accept --project-root <project-root> --repository application --operation merge --input <record.json> --decision <decision.json> --subject <subject.json>
```

Add `--previous-decision <previous.json>` for a linked changed decision and the
same `--profile` used at selection. Missing or stale context, policy conflicts,
unsupported versions and invalid records block acceptance rather than select a
different workflow. A source identity is a lowercase Git commit ID or, for
supported local observations, a worktree manifest digest. The helper checks
identity agreement; it does not reconstruct Git objects or that manifest.

### Test-first mode

Keep the strict [v1 evidence](evidence-contract.md) unchanged inside a
`development_test_first_binding` wrapper. The shared runtime supplies
`schemas/development-test-first-binding.schema.json`. Its exact fields are:

- `schema_version: 1` and `format: "development_test_first_binding"`.
- `repository`, `operation`, nullable `profile`, `policy_digest` and
  `source_snapshot_digest` from current policy diagnostics.
- `decision_digest`, final `subject`, unchanged `test_first_evidence` and
  `binding_digest`.

The wrapper's subject, the original v1 subject and the expected subject must
agree. Its canonical digest uses the shared `digest(record, "binding_digest")`
convention: omit only `binding_digest`, serialize sorted compact UTF-8 JSON
with unescaped Unicode, then prefix its SHA-256 hex with `sha256:`. Preserve the
nested v1 `evidence_digest`; do not use the legacy v1 digest command to seal
the wrapper.

The consumer injects its fixed canonical v1 validator into the shared binding
validator. This does not import another consumer copy or reinterpret RED.
Schema shape alone is insufficient: nested v1 validation and current context
checks are also required. The original local argv/exit-code evidence is
supported only when local execution is allowed and selected. CI-only
test-first observations remain unsupported; do not invent local exit codes
from CI jobs or run forbidden local checks to obtain a v1 receipt.

### Final-verification mode

Use the runtime's `development_final_verification` record and existing
`schemas/development-final-verification.schema.json`. It has explicit focused
and broader observations bound to the decision and final source. Local records
retain actual commands and exit codes; native CI observations retain provider,
pipeline/job IDs, URL, SHA and status. The selected execution source/provider
must match policy. Merge-result subjects remain unsupported by this adapter.

This mode neither requires RED nor establishes RED/GREEN chronology. Keep
background quality separate from the declared final checks; accepting this
contract is not proof that a project's entire check catalog was satisfied.
Source review, provider Ready status and independent review requirements remain
separate from these final-check observations.

## Shared runtime installation

By default, resolve only the sibling `verify-before-push` skill beside this
consumer. A separately installed copy may be selected per invocation:

```shell
python <skill-root>/scripts/evidence.py accept --project-root <project-root> --repository application --operation merge --input <record.json> --decision <decision.json> --subject <subject.json> --policy-runtime-root <installed-verify-before-push-root>
```

The adapter checks collection/skill/source metadata, the declared API version
and capabilities in `references/runtime-api.json`, and fixed entrypoint/schema
files before importing provider code. Compatible API versions are independent
of collection release numbers. It does not search CWD, global installations or
unrelated directories, and does not install anything automatically. Keep
workstation paths out of the project's committed policy.

These checks establish installation consistency, not code authenticity. The
selected installed dependency is trusted code. Provenance records the actual
artifact hashes; a changed dependency during validation cannot receive a
successful acceptance result.
Consumer provenance also binds the fixed validator and adapter installation
when accepting legacy evidence without a provider. A library-supplied callable
remains trusted caller input; unrelated callback source files are not searched
or attributed to the canonical validator.

If the implicit dependency is missing and the bounded policy candidates are
absent, `accept` may validate legacy v1 evidence without it. A selected explicit
dependency that is missing or incompatible blocks even in a no-policy project.
Explicit profiles, decisions, predecessors and subjects cannot be ignored in
the no-policy path. Invalid/unreadable roots, unsafe or dangling policy
boundaries, ambiguous JSON/YAML candidates and malformed policy never become
an absent-policy fallback. YAML is not a supported policy format.

## Result boundaries

The closed [acceptance envelope](../schemas/development-evidence-acceptance.schema.json)
seals the input hash, runtime provenance, diagnostics and unchanged provider
result with its own `acceptance_digest`. A provider's existing result digest
continues to seal that inner result, not the expanded envelope. Keep raw logs
and observation history separately; evidence digests cannot attest execution,
chronology, reviewer independence or Git provenance.

Acceptance grants no push/merge/deployment authorization and does not replace
lifecycle checkpoints. Existing lifecycle version 1 still requires its real
RED/GREEN checkpoints. Mode-specific lifecycle integration is a subsequent
package; never synthesize RED or mark a required checkpoint optional to bridge
that gap.
