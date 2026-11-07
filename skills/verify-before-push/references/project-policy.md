# Project policy diagnostics: v1 foundation

This package resolves declarations and reports conflicts. **Policy-bound action
gates remain unavailable.** The canonical verifier guards local
execution, GitHub CI collection and evidence acceptance: a present configured,
invalid or unsupported policy blocks these operations before checks or provider
calls. This includes local declarations; selecting `--source local` cannot override
a CI-only contract. Existing lifecycle, TDD, synchronization, publication and
cleanup consumers retain their existing contracts. A
`before_merge` declaration does not permit skipping a before-push gate.
Diagnostics never run tests, builds, pipelines, publication or provider calls.
Do not use this foundation to authorize a push, merge, deployment or cleanup.
The separate experimental [GitLab CI-only consumer](policy-gitlab-ci.md) derives
and revalidates evidence against current declarations without relaxing these
action gates or confirming source review and historical readiness.

## File, commands, and compatibility

The supported file is `.agents/kolabse/project-policy.json` beneath an existing,
explicitly selected project root. Use
[`project-policy.schema.json`](../schemas/project-policy.schema.json). YAML/YML
candidates are unsupported; simultaneous candidates are ambiguous. Sources
resolving outside the root are rejected. Repository roles never expand discovery.

```shell
python <skill-root>/scripts/project_policy.py status --project-root . --repository application --operation push --json
python <skill-root>/scripts/project_policy.py explain --project-root . --repository application --operation merge --json
python <skill-root>/scripts/project_policy.py validate --project-root . --json
python <skill-root>/scripts/project_policy.py migrate --project-root . --dry-run --json
```

All commands emit the same full JSON report, including origins and blockers.
Migration additionally includes its preview. Exit 2 means an invalid selected
policy; exit 0 means configured or absent. Definite action-specific conflicts
remain in `dependent_action_blockers`; `needs_review` observations are advisory
(`blocking: false`). Exit 0 is **not execution authorization** and does not mean
all actions are compatible.

Absence is a sentinel: `effective_policy: null`, `compatibility_mode: legacy`.
Invalid present input never becomes absent or silently selects local execution.
Duplicate keys, unknown fields/providers/versions, booleans used as versions,
malformed nested objects and invalid enums are rejected. Unknown-field values
and invalid JSON contents are withheld from error messages. Never put secrets in
policy strings; the foundation does not scan arbitrary strings for credentials.
Without a policy, legacy evidence acceptance and all existing v1/v2/v3 digest
inputs are unchanged. Under a configured contract, historical receipts cannot
satisfy the verifier gate. No policy-bound receipt version is implemented yet.

The guard examines the selected project root and explicitly configured repository
roots, including canonical source and effective workspace-map roots. It does not
discover other repositories. An unrelated repository still bypasses the gate.
Broken policy candidates and unsafe or broken policy-parent links fail closed.
Ordinary absent-policy installations do not require importing the new policy
modules; an incomplete installation with a present policy fails closed.

The verifier rechecks all these roots before each enabled local command, provider
collection, receipt save, reuse and acceptance. The low-level GitHub API helper
also checks the selected project root before each request; repository policies
that appear during a collection are caught by the receipt boundary checks.
Workspace maps retain their existing path
validation. These checks are observations, not atomic locks: a concurrent policy
change after a boundary observation cannot stop an already started command or
provider request. Read-only `status`, `explain`, `validate` and migration previews
remain available for diagnosing declarations; a successful diagnostic exit never
authorizes execution.

## Core contract

All core fields are required; there are no invisible execution defaults.

| Field | Accepted declarations |
| --- | --- |
| `schema_version` | Integer `1` |
| `verification.required_at` | `before_push`, `before_merge` |
| `verification.execution` | `local`, `ci` |
| `verification.provider` | `none` for local; `github`, `gitlab` for CI |
| `verification.subject` | `source_sha`, `merge_result_sha`; local requires `source_sha` |
| `verification.local_execution` | `allowed`, `forbidden` |
| `verification.reuse_successful_result` | Boolean |
| `development.evidence_mode` | `test_first`, `final_verification` |
| `publication.draft_until` | `implementation_and_source_review_complete` |
| `publication.pipeline.event` | `push`, `merge_request` |
| `publication.pipeline.target_branch` | Nonblank branch declaration |
| `publication.pipeline.require_ready` | Boolean |
| `publication.pipeline.bootstrap` | `suppress`, `allow` |
| `publication.pipeline.duplicate_active_run` | `forbidden`, `allowed` |
| `documentation.source_updates` | `required`, `optional` |
| `documentation.web.trigger` | `explicit_request`, `automatic` |
| `documentation.web.blocks_primary_task` | Boolean |
| `documentation.web.execution` | `local`, `ci` |
| `documentation.web.runner_tag` | Nonblank runner declaration |
| `documentation.web.require_success_for_published_sha` | Boolean |

Local execution with local prohibition or a CI provider, CI with provider `none`,
local documentation execution under global local prohibition, and local merge-result
verification are invalid. Provider names describe intent,
not adapters or accepted evidence. Constraints are `declared`; provider
confirmation is always `unconfirmed`. A final-verification declaration does not
remove an existing RED requirement. No profile implements independent per-check
gates, background suites, path matching or an execution DSL.

## Standard local example

```json
{
  "schema_version": 1,
  "verification": {
    "required_at": "before_push", "execution": "local", "provider": "none",
    "subject": "source_sha", "local_execution": "allowed",
    "reuse_successful_result": true
  },
  "development": {"evidence_mode": "test_first"},
  "publication": {
    "draft_until": "implementation_and_source_review_complete",
    "pipeline": {
      "event": "push", "target_branch": "main", "require_ready": true,
      "bootstrap": "suppress", "duplicate_active_run": "forbidden"
    }
  },
  "documentation": {
    "source_updates": "required",
    "web": {
      "trigger": "explicit_request", "blocks_primary_task": false,
      "execution": "ci", "runner_tag": "example-docs-runner",
      "require_success_for_published_sha": true
    }
  }
}
```

To describe cloud final-MR intent, change `verification.required_at` to
`before_merge`, `execution` to `ci`, `provider` to `gitlab`, `local_execution` to
`forbidden`, `development.evidence_mode` to `final_verification`, and
`publication.pipeline.event` to `merge_request`. These are declarations only;
review all resulting legacy conflicts before future consumer integration.

## Temporary profiles

Optional top-level `profiles` maps names to versioned profile objects. Add this
object as the `profiles` value in a complete document:

```json
{
  "migration": {
    "version": 1,
    "reason": "Review intended cloud migration before consumer integration",
    "scope": {"repositories": ["application"], "operations": ["merge"]},
    "overrides": {"development": {"evidence_mode": "final_verification"}},
    "expires_on": "2026-12-01",
    "review_condition": "Migration owner confirms remaining lifecycle requirements"
  }
}
```

Profiles require a reason, exact repository and operation lists, partial core
section overrides, and at least an expiry date or review condition. Supported
operations are `push`, `merge`, `build`, `deploy`, `cleanup`.
Select explicitly with `--profile migration`. Unknown, inapplicable or expired
selections are invalid, without renewal or fallback. Expiry dates are inclusive;
the library accepts injected `today`, while CLI uses the local calendar date.
Review-condition text stays `profile_review_unconfirmed`; no approval/observation
API discharges it in this package. Inactive profiles are not auto-activated.

## Library, provenance and legacy conflicts

The installed verifier includes the reusable standard-library API:

```python
load_project_policy(root, *, repository, operation, profile=None,
                    today=None, legacy_assertions=())
```

It performs no subprocess/network calls or explicit writes. `origins` maps each
effective leaf pointer to its value, source path/pointer and profile origin.
Overrides retain the base pointer. `effective_digest` hashes canonical effective
JSON; formatting and key order do not affect it. Unselected profiles are excluded
from effective values. `source_hashes` hashes bounded raw source bytes;
`source_snapshot_digest` hashes that map, including supplied assertion snapshots.
Thus changed formatting, profile reasons or legacy inputs remain detectable even
when declared values match. Neither hash is verification evidence or attestation.

Known legacy inputs are verifier/lifecycle/TDD `config.json` files beneath their
`.agents/<skill-name>/` directories plus root `AGENTS.md` and `CLAUDE.md`.
Enabled local commands (including optional checks) conflict with local prohibition
when the legacy verifier has no GitHub CI alternative. Required checks also
conflict with moving the gate to before-merge. Local plus GitHub configuration
is dual capability: command presence alone does not select execution. Required
lifecycle `tdd-red` conflicts with final mode. An explicit diagnostic TDD
`require_red: true` plus `red_execution: local` conflicts with local prohibition;
this release does not create or use that optional file for execution.

Only exact generated verifier managed blocks (Codex/Claude spelling, LF/CRLF)
are machine recognized. Customized markers and other prose stay advisory `needs_review`, scoped to the
requested operation. They never populate action blockers, including when policy
is absent; this preserves legacy semantics. No regex proves textual compatibility, and shell substrings are not interpreted
as builds. Malformed legacy inputs are review diagnostics. Conflicts carry both
source locations, operations and resolution guidance; no gate is silently weakened.

For bounded explicit observations, library callers may supply `legacy_assertions`
objects with required `repository`, `operations`, `declaration`, `source_path`,
`source_pointer` and optional positive `line`. Source paths must remain inside the
root. Supported declarations: `mandatory_before_push`, `local_execution_required`,
`local_red_required`, `tdd_red_required`, `bootstrap_run_pipeline_fallback`,
`website_required_for_task_completion`. Example:

```python
legacy_assertions=[{
    "repository": "application", "operations": ["push"],
    "declaration": "bootstrap_run_pipeline_fallback",
    "source_path": "AGENTS.md", "source_pointer": "", "line": 24
}]
```

These assertions report reviewed declarations; they never confirm provider gates
or confer authority. The CLI intentionally has no arbitrary assertion-file reader.

## Conservative migration preview

`migrate --dry-run` requires the explicit flag. Existing valid JSON is proposed
unchanged, including inactive profiles; absent or invalid input has no invented
proposal and leaves explicit choices unresolved. No provider jobs, evidence or
success states are inferred. Matching proposals report `no_op: true`.
`managed_block_edits` is always empty: existing execution instructions are
preserved unchanged until consumers implement enforcement. UTF-8 custom text,
including a UTF-8 BOM and CRLF, is retained byte-for-byte in `preserved_content`; legacy content
is also listed as unmapped. There is no `--apply` command.

The separate [development-readiness contract](development-readiness.md) records
explicit mode choices and checks source-readiness consistency without executing
checks or relaxing existing gates. It does not establish provider Ready status.

Future packages must implement operation planning, lifecycle decision history,
provider adapters with exact-subject/job evidence, and consumer integration
before declarations can change execution. This foundation does not complete
issues #150, #151 or #152.
