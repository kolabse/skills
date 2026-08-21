# Lifecycle and rewind rules

The lifecycle is provider-neutral. External systems perform actions; this skill accepts normalized evidence about their observed results.

## Ordered checkpoints

1. `task-claimed`: the configured task adapter reports one active owner and immutable task identity.
2. `feature-prepared`: the isolated feature ref/workspace exists at the planned base before edits.
3. `tdd-red`: a relevant test failed for the expected missing behavior before implementation.
4. `tdd-green`: the same behavior and configured local checks pass on the implementation commit.
5. `changed-scope-preflight`: changed paths were compared with configured repository rules and references; all applicable checks, documentation, and notification duties are enumerated.
6. `review-complete`: configured review requirements passed for the implementation commit.
7. `push-verified`: `$verify-before-push` or equivalent exact-state evidence passed immediately before publication.
8. `feature-published`: the exact verified commit is the remote feature identity.
9. `feature-pipeline`: configured remote feature checks passed for that identity.
10. `documentation-ready`: every planned documentation target is ready and all notification dispositions are recorded before integration.
11. `development-integrated`: the reviewed change is represented in the configured development target.
12. `documentation-published`: canonical documentation is published and traceable to the change.
13. `production-delegated`: an approved production process accepted the immutable development outcome. This is a handoff record, never direct production execution by this skill.
14. `deployment-observed`: the configured deployment identity is observed.
15. `marker-observed`: the configured release/deployment marker resolves to that identity.
16. `smoke-passed`: configured post-delivery smoke checks passed.
17. `documentation-complete`: final behavior, validation, delivery, limitations, and notification outcomes are documented as configured.
18. `cleanup-proved`: each enumerated temporary resource is merged, identical-tree, patch-equivalent, or otherwise represented by a configured proof method; retained resources have explicit reasons.

The configuration may disable only gates explicitly marked optional. Required gates cannot be skipped because a provider or environment is unavailable.

Planning runs Git with argv and `shell=False` for every configured repository. It requires the configured path to be the exact, non-symlink Git root; no operation in progress; a clean worktree including untracked files; an attached branch; and one matching HEAD, configured base, upstream, and supplied start/upstream identity. It also inspects every declared rule/reference as a regular non-symlink file within the project or repository boundary. Caller booleans are never accepted as proof of repository state.

## Failure loop

A failed checkpoint must include failure evidence and `rewind_to`. The target must equal that checkpoint's configured `failure_rewind`. Advancement truncates the target and every downstream success, increments the attempt, and records the failure in history. Examples:

- red/green or local preflight failure rewinds to `tdd-red`;
- review findings rewind to `tdd-red` or `changed-scope-preflight`, as declared;
- feature pipeline failure rewinds to `tdd-red` unless the project explicitly permits a narrower preflight rewind;
- integration conflict rewinds to `changed-scope-preflight` after freshness is re-established;
- deployment, marker, or smoke failure rewinds to `production-delegated` or another declared delivery checkpoint;
- documentation failure rewinds to `documentation-ready`;
- cleanup proof failure remains at `cleanup-proved` and retains resources.

Changing the plan, configuration, repository start identity, feature commit, development integration identity, or delivery identity invalidates dependent evidence. Create a new plan when the planned starting state or scope changes materially.

## Adapter capabilities

Configuration names provider-neutral adapters and the capabilities each supplies. Planning fails unless every declared required capability is covered. Version 1 recognizes task claim, changed-scope preflight, SCM review/pipeline/development integration, development publication, and deployment/marker/smoke observation. The helper never invokes an adapter; it validates normalized evidence produced by the approved external workflow.
