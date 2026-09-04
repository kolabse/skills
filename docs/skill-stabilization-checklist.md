# Experimental skill stabilization checklist

Use this checklist to decide whether one experimental skill has enough
observable evidence to become stable. It supplements the lifecycle policy in
[`CONTRIBUTING.md`](../CONTRIBUTING.md#manage-lifecycle-status); a skill-specific
checklist may add gates but must not weaken these shared gates.

Promotion is an evidence decision, not a documentation-only status change.
Missing, stale, private-only, or candidate-mismatched evidence keeps the skill
experimental.

## Identify the candidate

Record before testing:

- skill name and candidate version;
- exact Git commit and skill-content digest;
- supported agents and operating systems from `skill-catalog.json`;
- configuration version, schemas, migrations, and required capabilities;
- applicable compositions and external integrations;
- development trigger corpus and locked release holdout identities.

Run every gate against this identity. A later behavioral change invalidates the
affected results. A same-tree commit may be recorded as related evidence, but
does not silently replace the tested commit identity.

## Classify applicability

For each gate record `required` or `not-applicable` before executing it. Every
`not-applicable` decision needs a concrete reason tied to the skill contract.
Unavailable tooling, a failed test, or lack of a test environment is not a
valid reason to mark a required gate not applicable.

## Contract and deterministic behavior

- [ ] Frontmatter, catalog metadata, UI metadata, category, controlled tags,
  capabilities, dependencies, platforms, license, and provenance validate.
- [ ] The skill clearly states inputs, outputs, scope, authorization boundaries,
  failure behavior, and observable completion criteria.
- [ ] Project or user configuration has a documented location and scope.
- [ ] Stateful configuration has schema validation, read-only status, an
  idempotent configure/bootstrap path, and migration behavior where applicable.
- [ ] Deterministic helpers reject malformed, stale, conflicting, oversized,
  escaping, or otherwise unsafe inputs relevant to their contract.
- [ ] Repeated planning with identical inputs produces equivalent output; apply
  operations are digest-bound or revalidate mutable inputs before acting.
- [ ] Unit and integration tests cover success, refusal, partial failure, retry,
  and rollback or recovery boundaries that apply to the skill.

## Cross-platform and consumer installation

- [ ] Required checks pass on every platform declared by the skill.
- [ ] Windows path, encoding, subprocess, and sandbox behavior is exercised when
  Windows is supported; POSIX path and permission behavior is exercised when
  Linux or macOS is supported.
- [ ] A copied installation from the candidate works in a clean Codex profile.
- [ ] A copied installation works in a clean Claude Code profile when declared.
- [ ] Packaged release contents work without relying on repository-only files.
- [ ] Install, update, doctor/status, configuration bootstrap, and dependency
  resolution preserve unrelated global and project settings.

## Trigger and holdout evaluation

- [ ] The development corpus includes realistic positive, implicit, explicit,
  ambiguous, negative, and near-neighbor prompts.
- [ ] Trigger evaluation meets the collection thresholds without attracting
  unrelated requests or missing the skill's primary workflows.
- [ ] Failures are diagnosed against development cases; the locked release
  holdout is not used for iterative tuning.
- [ ] A new immutable release holdout covers the proposed stable trigger surface
  and passes for the exact release candidate.

## Independent forward tests

- [ ] At least two independent runs use projects, fixtures, or users whose
  evidence was not used to design the implementation.
- [ ] Testers receive realistic requests and the candidate skill, but not the
  expected answer or maintainer diagnosis.
- [ ] Each run records the platform, agent/version, candidate identity, bounded
  scenario, observed invocation, outcome, manual repair, false positives, false
  negatives, and sanitized evidence digests.
- [ ] Mutating workflows prove authorization and the external outcome; read-only
  workflows prove that no mutation occurred.
- [ ] Any required external service is exercised at least once in its supported
  configuration, including an expected refusal or failure path.
- [ ] Material defects are fixed and the affected gates are rerun on the new
  candidate identity.

Raw project rules, source code, prompts, chats, credentials, customer data,
private URLs, usernames, and workstation paths do not belong in shared
acceptance evidence. Use `report-skill-feedback` for consent-gated sanitized
reports; absence of feedback is not proof of success.

## Compositions, safety, and compatibility

- [ ] Every required capability resolves to an available provider, and supported
  compositions verify ordered handoffs and failure propagation.
- [ ] Optional logging or notification cannot turn failure into success or make
  the primary result fail after it already succeeded.
- [ ] Security checks cover secret handling, path containment, symlink/reparse
  traversal, command construction, untrusted historical context, and destructive
  actions where applicable.
- [ ] Existing configuration and documented commands remain compatible, or the
  release includes explicit migration guidance and tests.
- [ ] Known limitations and unsupported cases are documented without claiming
  them as passed behavior.

## Evidence summary

Attach a sanitized summary to the promotion pull request or release evidence.
Use one row per gate or scenario:

| Field | Required value |
| --- | --- |
| `skill` | Catalog skill name |
| `candidate_version` | Version being evaluated |
| `candidate_commit` | Exact 40-character Git commit |
| `skill_digest` | SHA-256 of the evaluated skill contents |
| `gate` | Stable gate or scenario identifier |
| `applicability` | `required` or `not-applicable` |
| `status` | `passed`, `failed`, or `blocked` |
| `environment` | Sanitized agent, agent version, OS, and integration kind |
| `evidence` | Reproducible command/result reference or sanitized digest |
| `observed_at` | UTC timestamp |
| `notes` | Limitation, repair, or not-applicable rationale |

Do not replace evidence with an unchecked box. A checklist is complete only
when every required row is passed and every not-applicable row is justified.

## Promote in a release

- [ ] The candidate has no unresolved required-gate failure or material known
  regression.
- [ ] Collection `preflight`, `full`, and `consumers` checks pass for the exact
  integrated primary commit intended for the release.
- [ ] The catalog status changes to `stable` and `stable_since` names the new
  versioned release; README maturity labels and changelog agree.
- [ ] Release evidence and audit cover the actual tag commit and artifacts.
- [ ] Post-release copied-install smoke confirms the published artifacts rather
  than the maintainer checkout.

If any required evidence is unavailable, publish improvements without promotion
and keep the skill experimental. Reassess only after new observable evidence is
available.
