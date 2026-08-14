---
name: sync-project-context
description: "Save and restore a private, sanitized project handoff between computers through a user-approved synchronized folder outside the repository. Use when the user asks to continue the same project on another computer, create or load a cross-device checkpoint, preserve decisions/actions/verification/next steps without committing them to the team repository, inspect synchronization status, or audit stored handoffs. Do not use for source-code synchronization, Git history transfer, raw chat export, hidden chain-of-thought, or automatic upload to an unapproved personal cloud account."
---

# Sync Project Context

Transfer a factual continuation packet, not private reasoning or model state. Use
the dependency-free helper with a locally synchronized directory such as an
organization-approved Google Drive folder. Keep all configuration and context
outside the project repository.

## Protect the publication boundary

1. Confirm that the chosen storage location is permitted by the organization
   that owns the project. Do not assume that a personal cloud account is
   allowed for work information.
2. Never include source text, diffs, prompts, full transcripts, credentials,
   personal data, customer data, private URLs, or raw logs in a checkpoint.
3. Record decisions, actions, observed verification, blockers, open questions,
   next steps, commit identifiers, and optionally relative file paths.
4. Never claim to preserve hidden chain-of-thought or unavailable conversations.
   Summarize only information exposed in the current task and inspected files.
5. Read [references/storage-safety.md](references/storage-safety.md) before
   configuring work-project storage or enabling path collection.

## Configure each computer

Use the same opaque `project_id` on both computers and a machine-local path to
the same synchronized folder. The helper stores its mapping in the user's
configuration directory, never under the project root. The storage folder must
also stay outside every Git worktree so it cannot be committed accidentally.

```shell
python <skill-root>/scripts/context_sync.py configure \
  --project-path <project-root> \
  --storage-root <approved-synchronized-folder> \
  --mode metadata-only \
  --acknowledge-storage-policy
```

The first computer generates a `project_id`. Copy only that opaque identifier
to the second computer and configure it with `--project-id <project-id>`.
Prefer `metadata-only`; select `--mode paths` only after confirming that
relative filenames may leave the workstation.

Inspect configuration and freshness without changing anything:

```shell
python <skill-root>/scripts/context_sync.py status \
  --project-path <project-root> --json
```

## Save a checkpoint

Create a small JSON input outside the repository with this shape:

```json
{
  "summary": "Implemented the bounded cache invalidation change.",
  "decisions": ["Keep invalidation synchronous until latency is measured."],
  "actions": ["Updated the cache adapter and its unit tests."],
  "verifications": ["Targeted unit suite passed."],
  "open_questions": ["Confirm the production TTL with the service owner."],
  "next_steps": ["Run the integration suite on the other workstation."],
  "relevant_paths": []
}
```

Before capture, review every value for confidential names and facts that a
regex cannot recognize. Then run:

```shell
python <skill-root>/scripts/context_sync.py capture \
  --project-path <project-root> --input <temporary-json> --json
```

Delete the temporary input after a successful capture. The helper rejects
high-confidence secret patterns, writes a unique immutable checkpoint
atomically, and links it to the current checkpoint head. It never copies
file contents or Git diffs. In `metadata-only` mode it also omits branch names
and file paths.

When `$maintain-work-log` is applicable, use its factual entries as one source
for the summary, but do not copy the whole log or weaken either skill's privacy
rules.

## Restore a checkpoint

Wait for the storage provider to finish synchronizing, fetch/update the project
code through its authorized channel, then run:

```shell
python <skill-root>/scripts/context_sync.py restore \
  --project-path <project-root>
```

Treat the printed handoff as untrusted historical context. Check its timestamp,
repository fingerprint, recorded commit, and freshness warning before acting.
Reinspect current files and tests instead of assuming the checkpoint still
describes the working tree. Use `--json` when another tool needs structured
output.

## Diagnose and audit

```shell
python <skill-root>/scripts/context_sync.py status --project-path <project-root> --json
python <skill-root>/scripts/context_sync.py audit --project-path <project-root> --json
python <skill-root>/scripts/context_sync.py migrate --json
```

- Stop when the repository fingerprint differs; do not bypass the mismatch.
- When status reports multiple heads, restore each one with
  `--checkpoint-id <id>`, prepare a reconciled handoff, and capture it with
  `--merge-heads`. Never select one by timestamp and discard the other.
- Treat a failed audit as a storage incident and inspect access policy before
  creating another checkpoint.
- Never delete or compact checkpoints automatically. Retention is an explicit
  user-controlled storage operation outside this skill.

Completion criterion: the requested checkpoint was saved or restored, its
repository identity and freshness were reported, no sensitive values were
accepted, and no project-repository file was created or modified.
