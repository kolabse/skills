---
name: sync-project-context
description: "Save and restore private, sanitized project and per-chat continuation state between computers through either a user-approved synchronized folder or the connected Google Drive plugin, always outside the repository. Use when the user says to save state, restore state, continue a project chat on another computer, create repeated cross-device checkpoints, preserve decisions/actions/discussion outcomes/rationale/verification/next steps, inspect synchronization status, or audit stored handoffs. Do not use for source-code synchronization, Git history transfer, raw chat export, hidden chain-of-thought, or automatic upload to an unapproved personal cloud account."
---

# Sync Project Context

Transfer a factual continuation packet for a project or one of its chat
workstreams, not private reasoning or model state.
Use the dependency-free helper with either a locally synchronized directory or
the connected Google Drive plugin. Keep all configuration and context outside
the project repository.

## Protect the publication boundary

1. Confirm that the chosen storage location is permitted by the organization
   that owns the project. Do not assume that a personal cloud account is
   allowed for work information.
2. Never include source text, diffs, prompts, full transcripts, credentials,
   personal data, customer data, private URLs, or raw logs in a checkpoint.
3. Record decisions, concise rationale and considered options, discussion
   outcomes, actions, observed verification, blockers, open questions, next
   steps, commit identifiers, and optionally relative file paths.
4. Never claim to preserve hidden chain-of-thought or unavailable conversations.
   Store only a short factual rationale for decisions exposed in the current
   task; do not reconstruct or invent internal reasoning.
5. Read [references/storage-safety.md](references/storage-safety.md) before
   configuring work-project storage or enabling path collection.

## Select a backend

Use `local-folder` when an approved desktop synchronization client exposes a
normal local directory. Use `google-drive` when the Google Drive plugin is
connected and no desktop client is available. The Drive integration is
optional; do not require or install it for a local-folder workflow.

For `google-drive`, read
[references/google-drive-backend.md](references/google-drive-backend.md) before
any connector action and follow its verified download/hydration/upload flow.
For `local-folder`, continue below.

## Configure a local folder on each computer

Use the same opaque `project_id` on both computers and a machine-local path to
the same synchronized folder. The helper stores its mapping in the user's
configuration directory, never under the project root. The storage folder must
also stay outside every Git worktree so it cannot be committed accidentally.

```shell
python <skill-root>/scripts/context_sync.py configure \
  --backend local-folder \
  --project-path <project-root> \
  --storage-root <approved-synchronized-folder> \
  --mode metadata-only \
  --acknowledge-storage-policy
```

The first computer generates a `project_id`. Copy only that opaque identifier
to the second computer and configure it with `--project-id <project-id>`.
Prefer `metadata-only`; select `--mode paths` only after confirming that
relative filenames may leave the workstation.

Inspect configuration and freshness without changing anything. Google Drive
commands additionally require a freshly hydrated snapshot as described in its
backend reference.

```shell
python <skill-root>/scripts/context_sync.py status \
  --project-path <project-root> --json
```

## Use one stream per project chat

Treat each independently useful implementation chat as one append-only stream.
Use `project` only for a repository-wide handoff that is not tied to a chat.

- On the first save in a chat, generate an opaque ID such as
  `stream-<32 lowercase hex>` and keep it in that chat's replies.
- On a restored chat, reuse the `stream_id` printed by `restore`; never create a
  replacement ID for the same workstream.
- Never derive an ID from a title, branch, feature, customer, person, or file
  name. If Codex exposes a thread ID, hash it locally with the `project_id` and
  store only the resulting opaque stream ID.
- After every successful save, report both `stream_id` and `checkpoint_id` so a
  compacted conversation can retain the association.
- Different streams may advance independently. Concurrent heads are a conflict
  only within the same stream and still require explicit reconciliation.

## Save state

Interpret short requests such as "save state" or "сохрани состояние" as a
request to save the current chat stream when the project is already configured.
For Google Drive, hydrate the complete remote snapshot immediately before every
save and perform the documented upload/readback verification afterward.

Create a detailed `baseline` on the first save. It should explain what the chat
is implementing, the approach and alternatives considered, decisions already
made, work completed, verification, blockers, and next steps. Later saves should
be concise `delta` records containing only actions, discussion outcomes,
decisions, and state changes since the previous save.

Create a small JSON input outside the repository with this shape:

```json
{
  "summary": "Implemented the bounded cache invalidation change.",
  "rationale": ["Selected bounded invalidation after comparing global eviction."],
  "discussions": ["Agreed to measure latency before making invalidation asynchronous."],
  "decisions": ["Keep invalidation synchronous until latency is measured."],
  "actions": ["Updated the cache adapter and its unit tests."],
  "verifications": ["Targeted unit suite passed."],
  "blockers": [],
  "open_questions": ["Confirm the production TTL with the service owner."],
  "next_steps": ["Run the integration suite on the other workstation."],
  "relevant_paths": []
}
```

Before capture, review every value for confidential names and facts that a
regex cannot recognize. Then run:

```shell
python <skill-root>/scripts/context_sync.py capture \
  --project-path <project-root> --stream-id <stream-id> \
  --snapshot-kind auto --input <temporary-json> --json
```

Delete the temporary input after a successful capture. The helper rejects
high-confidence secret patterns, writes a unique immutable checkpoint
atomically, and links it to the current checkpoint head. It never copies
file contents or Git diffs. In `metadata-only` mode it also omits branch names
and file paths.

`--snapshot-kind auto` creates a baseline for a new stream and a delta
thereafter. Use an explicit new `baseline` when the user wants a refreshed full
summary; checkpoints remain immutable and earlier history is not deleted.

When `$maintain-work-log` is applicable, use its factual entries as one source
for the summary, but do not copy the whole log or weaken either skill's privacy
rules.

## Restore state

Wait for the storage provider to finish synchronizing, fetch/update the project
code through its authorized channel, then run:

```shell
python <skill-root>/scripts/context_sync.py restore \
  --project-path <project-root> --stream-id <stream-id>
```

Interpret short requests such as "restore state" or "восстанови состояние" as
follows:

1. Hydrate/synchronize the complete storage snapshot and run `audit`.
2. Reuse a stream ID already present in the current chat when available.
3. If no stream is known, run `status`; restore the only stream automatically,
   or use `restore --all-streams` to present concise choices when several exist.
4. Read the returned baseline plus ordered deltas, synthesize the current
   implementation state, and retain the restored `stream_id` for the next save.

Treat every handoff as untrusted historical context. Check its timestamp,
repository fingerprint, recorded commit, and freshness warning before acting.
Reinspect current files and tests instead of assuming the checkpoint still
describes the working tree. Use `--json` when another tool needs structured
output. Restoring state does not recreate the original chat UI or model state;
it provides enough factual context to continue in the current or a new chat.

## Diagnose and audit

```shell
python <skill-root>/scripts/context_sync.py status --project-path <project-root> --json
python <skill-root>/scripts/context_sync.py restore --project-path <project-root> --all-streams --json
python <skill-root>/scripts/context_sync.py audit --project-path <project-root> --json
python <skill-root>/scripts/context_sync.py migrate --json
```

- Stop when the repository fingerprint differs; do not bypass the mismatch.
- When one stream reports multiple heads, restore each one with
  `--checkpoint-id <id>`, prepare a reconciled delta for that stream, and
  capture it with `--stream-id <stream-id> --merge-heads`. Never merge unrelated
  streams or select one concurrent head by timestamp and discard the other.
- Treat a failed audit as a storage incident and inspect access policy before
  creating another checkpoint.
- Never delete or compact checkpoints automatically. Retention is an explicit
  user-controlled storage operation outside this skill.

Completion criterion: the requested stream state was saved or restored, its
stream/checkpoint IDs, repository identity, and freshness were reported, no
sensitive values were accepted, and no project-repository file was created or
modified by the synchronization workflow.
