---
name: coordinate-code-documentation-repositories
description: "Coordinate one auditable change when implementation and canonical documentation live in separate Git repositories. Use when a requested code change must also update an authoritative documentation repository, or when publication must prove that both repositories describe the same outcome. Do not use for a digest, code comments, documentation stored in the same repository, or repository synchronization alone."
---

# Coordinate Code and Documentation Repositories

Treat implementation and canonical documentation as two required parts of one
project change. Compose with `$synchronize-git-repositories` for freshness and
`$verify-before-push` for declared checks; this skill owns repository roles,
documentation completeness, cross-repository traceability, and the joint
completion decision.

## Resolve the project contract

1. Inspect project instructions for the implementation repository,
   documentation repository, canonical documentation roots, and required
   documentation topics. Never infer roles from sibling directory names.
2. If the contract is not installed, prepare a version-1 document matching
   [`schemas/config.schema.json`](schemas/config.schema.json) and configure it:

   ```shell
   python <skill-root>/scripts/coordinate_change.py configure \
     --project-root <project-root> --config-source <config.json>
   ```

3. Run `status --json`. Stop when either role is missing, is not the exact Git
   root declared by the project, or has dirty, behind, diverged, detached, or
   untracked state after the synchronization workflow.
4. Repository paths are relative to the project root and may locate an
   approved sibling repository. Canonical documentation roots stay within the
   documentation repository. Do not place credentials or private URLs in the
   contract.

Use `migrate --json` after updating the skill. Unknown newer configuration
versions fail closed.

Completion criterion: both repository roles and every canonical documentation
root resolve unambiguously, and freshness evidence exists for each repository.

## Plan the paired change

Read the relevant canonical sources before implementation. Prepare a change
input matching [`schemas/change-input.schema.json`](schemas/change-input.schema.json)
with a concise outcome, exact documentation sources and targets, and the topics
the change must cover. Include every configured required topic.

Create a read-only, digest-bound plan:

```shell
python <skill-root>/scripts/coordinate_change.py plan \
  --project-root <project-root> --input <change-input.json> \
  --output <plan.json> --json
```

Keep the plan outside both repositories. It binds the configuration, source
commits, upstream identities, documentation paths, and requested outcome. Do
not begin a paired change from a plan with blockers.

Record requirements or missing decisions in the canonical documentation as
part of the authorized task, but never invent product requirements merely to
make the plan pass. Resolve conflicting guidance explicitly.

Completion criterion: the plan names the exact starting state, authoritative
sources, intended documentation targets, required topics, and no unresolved
repository role.

## Implement and publish coherently

- Keep code and documentation changes logically separated in their respective
  repositories. Do not rewrite either history solely to embed reciprocal
  commit hashes.
- Explain the originating requirement, decision, observable behavior,
  operational impact, validation result, and limitations when those topics are
  required by the contract. A statement that a topic is not applicable must be
  deliberate and reviewable, not silently omitted.
- Use review descriptions, release evidence, or another declared traceability
  mechanism to connect the changes without circular history edits.
- Obtain authorization independently for staging, commits, pushes, review
  requests, merges, or other external mutations. This skill does not broaden
  the user's permission.
- Preserve dirty or divergent state. Never stash, reset, merge, rebase,
  force-push, or delete branches as an automatic repair.

Use `$maintain-project-digest` only for an optional user-facing daily summary;
it never replaces canonical documentation.

## Verify joint completion

After publication, prepare a verification input matching
[`schemas/verification-input.schema.json`](schemas/verification-input.schema.json).
Bind it to the plan digest and include:

- the final implementation and documentation commits;
- documentation evidence for every required topic;
- passed validation results with evidence digests;
- traceability records that identify both repository changes.

Run:

```shell
python <skill-root>/scripts/coordinate_change.py verify \
  --project-root <project-root> --plan <plan.json> \
  --input <verification-input.json> --json
```

Verification fails unless both repositories changed from the planned state,
their worktrees are clean, their tracked upstream commits equal the final local
commits, every referenced documentation path exists inside a canonical root,
all required topics have evidence, all validation results passed, and both
repository roles are traceable.

Read [references/evidence-contract.md](references/evidence-contract.md) when
preparing or reviewing the plan and verification evidence.

Completion criterion: code, canonical documentation, validation evidence, and
both published histories agree. If either repository is unresolved, report the
paired change as blocked rather than partially complete.

## Safety boundaries

- Never copy secrets, personal data, production credentials, raw private rules,
  or internal URLs into documentation or evidence.
- Do not claim semantic agreement from file presence alone; review the actual
  documented claims against the implemented behavior.
- Do not weaken required topics, validation, or repository freshness to finish
  a change.
- The helper performs configuration writes only for explicit `configure` or
  `migrate`; `status`, `plan`, and `verify` do not modify either repository.
