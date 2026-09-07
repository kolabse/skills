---
name: coordinate-code-documentation-repositories
description: "Coordinate one auditable change across implementation and separate canonical documentation repositories, including required infrastructure or operations repositories. Use when application behavior and authoritative documentation (including operational contracts) in another repository must change together, or publication must prove their exact revisions agree. Do not use for independent multi-repository edits, a digest, same-repository documentation, or repository synchronization alone."
---

# Coordinate Code and Documentation Repositories

Treat implementation, canonical documentation, and any additional required
repository roles as parts of one project change. Compose with
`$synchronize-git-repositories` for freshness and
`$verify-before-push` for declared checks; this skill owns repository roles,
documentation completeness, cross-repository traceability, and the joint
completion decision.

Announce this workflow when the requested outcome requires that coordination.
An infrastructure repository may own the canonical documentation; establish
that ownership from project rules rather than requiring a repository named
"docs". Merely touching several independent repositories is insufficient.
Show the resolved roles, documentation owner, publication order, revision
identities, checks, and blockers using
[references/coordination-reporting.md](references/coordination-reporting.md).

## Resolve the project contract

1. Inspect project instructions for the implementation repository,
   documentation repository, additional required repository roles, canonical
   documentation roots, and required documentation topics. Never infer roles
   from sibling directory names.
2. If the contract is not installed, prepare a version-1 document matching
   [`schemas/config.schema.json`](schemas/config.schema.json) and configure it:

   ```shell
   python <skill-root>/scripts/coordinate_change.py configure \
     --project-root <project-root> --config-source <config.json>
   ```

3. Run `status --json`. Stop when any required role is missing, is not the exact Git
   root declared by the project, or has dirty, behind, diverged, detached, or
   untracked state or unpublished commits after the synchronization workflow.
4. Repository paths are relative to the project root and may locate an
   approved sibling repository. Canonical documentation roots stay within the
   documentation repository. Do not place credentials or private URLs in the
   contract.

The `repositories` map always contains `implementation` and `documentation`.
Add named roles such as `operations` only when they must change for this task;
every declared role is required and must resolve to a distinct Git root.
When documentation and operations share one repository, use `documentation`
for that repository and describe both responsibilities in the task record.
Do not duplicate its path under another role. Existing two-role version-1
contracts remain valid; updating the skill does not add roles automatically.

Use `migrate --json` after updating the skill. Unknown newer configuration
versions fail closed.

Completion criterion: all required repository roles and every canonical documentation
root resolve unambiguously, and freshness evidence exists for each repository.

## Plan the coordinated change

Read the relevant canonical sources before implementation. Prepare a change
input matching [`schemas/change-input.schema.json`](schemas/change-input.schema.json)
with a concise outcome, exact documentation sources and targets, and the topics
the change must cover. Include every configured required topic.
When the task has a publication dependency, include `publication_order` with
every configured role exactly once in the intended order. This records the
planned order; final upstream equality does not prove the actual chronology.

Create a read-only, digest-bound plan:

```shell
python <skill-root>/scripts/coordinate_change.py plan \
  --project-root <project-root> --input <change-input.json> \
  --output <plan.json> --json
```

Keep the plan outside all participating repositories. It binds the configuration, source
commits, upstream identities, documentation paths, and requested outcome. Do
not begin a coordinated change from a plan with blockers.

Record requirements or missing decisions in the canonical documentation as
part of the authorized task, but never invent product requirements merely to
make the plan pass. Resolve conflicting guidance explicitly.

Completion criterion: the plan names the exact starting state, authoritative
sources, intended documentation targets, required topics, and no unresolved
repository role. If the project already uses claims or task cards, follow the
mapping in [references/coordination-reporting.md](references/coordination-reporting.md)
and still run the formal helpers.

## Implement and prepare publication coherently

- Keep code and documentation changes logically separated in their respective
  repositories. Do not rewrite their histories solely to embed reciprocal
  commit hashes.
- Explain the originating requirement, decision, observable behavior,
  operational impact, validation result, and limitations when those topics are
  required by the contract. A statement that a topic is not applicable must be
  deliberate and reviewable, not silently omitted.
- Use review descriptions, release evidence, or another declared traceability
  mechanism to connect the changes without circular history edits.
- After all final local commits exist, run `$verify-before-push` for each
  repository and bind its evidence to those exact commits. This is a mandatory
  pre-publication checkpoint: do not publish any changed commit in any required
  role until every required repository passes. A project-required initial task-branch
  publication at an unchanged verified base is preparation, not delivery of the
  task's content changes.
- Publish the already-verified commits in the declared order without modifying
  them. If any commit changes, rerun the checkpoint for all required repositories
  before any further push. Retain the common pre-publication evidence and actual
  publication observations in the task record; `verify` does not reconstruct them.
- Use the user's existing authorization for staging, commits, pushes, review
  requests, merges, and other mutations. Ask only for an action not already
  authorized; this skill does not broaden the user's permission.
- Preserve dirty or divergent state. Never stash, reset, merge, rebase,
  force-push, or delete branches as an automatic repair.

Use `$maintain-project-digest` only for an optional user-facing daily summary;
it never replaces canonical documentation.

## Verify joint completion

After publication, prepare a verification input matching
[`schemas/verification-input.schema.json`](schemas/verification-input.schema.json).
Bind it to the plan digest and include:

- the final implementation and documentation commits, plus `additional_commits`
  covering exactly the configured extra roles when present;
- documentation evidence for every required topic;
- passed validation results with evidence digests; for a contract with extra
  roles, cover every role with a result naming its `repository` and final `commit`;
- traceability records that identify every required repository change.

Run:

```shell
python <skill-root>/scripts/coordinate_change.py verify \
  --project-root <project-root> --plan <plan.json> \
  --input <verification-input.json> --json
```

Verification fails unless all required repositories changed from the planned state,
their worktrees are clean, their tracked upstream commits equal the final local
commits, every referenced documentation path exists inside a canonical root,
all required topics have evidence, all validation results passed, and all
repository roles are traceable.

Read [references/evidence-contract.md](references/evidence-contract.md) when
preparing or reviewing the plan and verification evidence.

Completion criterion: code, canonical documentation, any required operational
changes, validation evidence, and all published histories agree. If any required
repository is unresolved, report the joint change as blocked and show which
roles have already been published.

## Safety boundaries

- Never copy secrets, personal data, production credentials, raw private rules,
  or internal URLs into documentation or evidence.
- Do not claim semantic agreement from file presence alone; review the actual
  documented claims against the implemented behavior.
- Do not weaken required topics, validation, or repository freshness to finish
  a change.
- The helper performs configuration writes only for explicit `configure` or
  `migrate`; `status`, `plan`, and `verify` do not modify participating repositories.
