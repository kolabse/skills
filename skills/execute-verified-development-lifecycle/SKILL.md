---
name: execute-verified-development-lifecycle
description: "Plan and verify a project-declared development lifecycle from feature preparation through reviewed development integration, delegated production delivery, documentation completion, and proved cleanup. Use when a change must cross configured repository, test, review, pipeline, deployment, notification, and documentation gates. Do not use for ad hoc edits, provider-specific automation, or direct production execution."
---

# Execute Verified Development Lifecycle

Use the project contract as the source of truth. This skill coordinates evidence; it does not call provider adapters, push, open or merge reviews, deploy, notify, edit documentation, or delete resources.

Compose with `$synchronize-git-repositories` before planning and whenever remote freshness matters. Use `$verify-before-push` for the exact-state push checkpoint. Production execution remains delegated to the project's approved release process.

In Codex, invoke composed skills as `$skill-name`; in Claude Code, invoke them
as `/skill-name`. Pass `--agent claude-code` to rule configuration, rule
status, and dependency installation. Omitting `--agent` preserves Codex and
its `AGENTS.md` rules as the default.

## Resolve the contract

Inspect project instructions and install a version-1 project-owned configuration matching [`schemas/config.schema.json`](schemas/config.schema.json):

```shell
python <skill-root>/scripts/development_lifecycle.py configure --project-root <root> --config-source <config.json>
python <skill-root>/scripts/development_lifecycle.py status --project-root <root> --json
```

The contract must declare every repository, applicable rule source, canonical reference, required check, evidence gate, provider-neutral adapter and required capability, notification audience, documentation target, development integration target, delegated production route, and cleanup proof method. Never infer these from provider conventions. A repository may explicitly declare unchanged feature-bootstrap CI suppression; absence of that declaration means its bootstrap pipeline runs normally. Use `migrate --json` after a skill update; unknown newer versions fail closed.

Install and inspect one managed skill reference in each configured repository only with explicit confirmation:

```shell
python <skill-root>/scripts/development_lifecycle.py rules-status --project-root <root> --json
python <skill-root>/scripts/development_lifecycle.py configure-rules --project-root <root> --apply --yes --json
```

`rules-status` is read-only. `configure-rules` preserves unrelated `AGENTS.md`
or `CLAUDE.md` content selected by `--agent`, is idempotent, and rejects
malformed or duplicate managed markers. Planning inspects declared project
files directly and blocks on a missing or stale reference.

Inspect the bundled dependency plan before starting:

```shell
python <skill-root>/scripts/development_lifecycle.py dependencies --json
```

It reports required workflow skills, optional lifecycle integrations, setup reminders, and the exact `npx` argv. It is read-only unless both `--apply` and `--yes` are present. Add `--include-integrations` only when the project will use those integrations. Read [`references/dependencies.json`](references/dependencies.json) when dependency availability or installation is in scope.

## Freeze the plan before editing

Read [`references/lifecycle-and-rewinds.md`](references/lifecycle-and-rewinds.md) and prepare a plan input matching [`schemas/plan-input.schema.json`](schemas/plan-input.schema.json). It must account for every configured repository rule and reference, identify the feature source/base and unchanged starting commits, and describe changed scope. Run:

```shell
python <skill-root>/scripts/development_lifecycle.py plan --project-root <root> --input <plan-input.json> --output <plan.json> --state-output <state.json> --json
```

Keep plan and state outside every configured repository. Planning independently inspects each exact Git root, operation/worktree/branch/base/upstream state, and declared regular rule/reference file; supplied booleans are not evidence. A feature workspace/branch must be prepared and remotely published from the verified base before the first edit. When `feature_bootstrap` is present in the plan, read [`references/bootstrap-ci-suppression.md`](references/bootstrap-ci-suppression.md) before publishing. Use only the repository-declared GitHub Actions or GitLab CI mechanism, never tags, empty commits, commit-message markers, or permanent branch exclusions. If suppression is unavailable or unproved, run the bootstrap pipeline and require it to pass. The plan reports reminders for declared notifications and documentation but does not satisfy those gates.

## Advance with retained evidence

After each external action, retain a JSON evidence file matching [`schemas/retained-evidence.schema.json`](schemas/retained-evidence.schema.json) outside every configured repository, then submit one checkpoint matching [`schemas/checkpoint.schema.json`](schemas/checkpoint.schema.json):

```shell
python <skill-root>/scripts/development_lifecycle.py advance --project-root <root> --plan <plan.json> --state <state.json> --checkpoint <checkpoint.json> --json
```

Checkpoints are ordered and digest-bound to the plan, configuration, repositories, commits, refs, and retained evidence. The normal route proves: task claim; remotely published feature-before-edit with an observed bootstrap-CI disposition; TDD red then green; changed-scope preflight; review; exact-state push verification; full feature pipeline for the implementation commit; documentation readiness and publication; reviewed merge-request integration into development; delegated production handoff; deployment, marker, and smoke observations; documentation completion; and cleanup representation proof.

A failed checkpoint enters the declared failure loop. Record failure evidence and rewind only to the configured checkpoint; invalidate every downstream checkpoint and rerun it. Never relabel failed, missing, stale, or subject-mismatched evidence as passed.

Read [`references/evidence-contract.md`](references/evidence-contract.md) when creating or assessing evidence.

## Verify completion

Synchronize observations as required by project policy, then run:

```shell
python <skill-root>/scripts/development_lifecycle.py verify --project-root <root> --plan <plan.json> --state <state.json> --json
```

Completion requires every configured gate, rule, reference, notification reminder disposition, documentation target, development integration identity, delegated production record, delivery observation, and cleanup proof. Verification validates state invariants and deterministically replays the complete history, reopening every retained evidence file; deleted, tampered, malformed, or forged evidence/state fails closed. The supplied state remains unchanged. Production execution is never performed or implied by this helper.

## Safety boundaries

- Obtain authorization independently for every external mutation; evidence of one action does not authorize the next.
- Preserve dirty, behind, diverged, detached, or untracked repositories. Never repair them automatically.
- Commands named `plan`, `status`, `rules-status`, and `verify` are read-only. `advance` changes only the explicit state artifact. `configure`, `migrate`, and explicitly confirmed `configure-rules` have only their documented project-local writes.
- Do not store secrets, credentials, private URLs, raw logs, or personal data in configuration or evidence. Store stable labels, immutable identities, timestamps, and SHA-256 digests.
- Cleanup requires fresh proof that every enumerated feature resource is represented in its configured durable target. A name pattern is not proof.
