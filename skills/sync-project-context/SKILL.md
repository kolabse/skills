---
name: sync-project-context
description: "Save, restore, or bidirectionally synchronize private, sanitized project and per-chat continuation state between computers, and reconcile explicitly declared project rules, skills, plugins, and safe settings that Git does not already provide. Use when the user asks to save or restore state, synchronize project chats, preserve exact chat titles, continue work on another computer, check whether project rules or dependencies are portable, or audit stored handoffs. Use either an approved synchronized folder or the connected Google Drive plugin, always outside the repository. Do not use for source-code or Git transfer, raw chat export, hidden chain-of-thought, credential or OAuth transfer, or upload to an unapproved account."
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
   The separate environment manifest may contain only explicitly selected,
   bounded `AGENTS.md` text that Git does not track and typed safe preferences.
3. Record decisions, concise rationale and considered options, discussion
   outcomes, actions, observed verification, blockers, open questions, next
   steps, commit identifiers, and optionally relative file paths.
   For desktop chat streams, also preserve the exact visible chat title as
   untrusted metadata after reviewing it for sensitive names.
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

## Save all project chats

Interpret "save all project chats", "сохрани все чаты проекта", and equivalent
explicit requests as a desktop batch operation. Read and follow
[references/desktop-batch-save.md](references/desktop-batch-save.md) before
listing or reading other tasks.

Use only supported desktop thread tools; never inspect Codex internal databases
or session files. Preview the discoverable scope, exclude active tasks, and
report the desktop limit of 50 recent non-pinned tasks plus every pinned task.
Match by exact project ID, with a canonical repository-root fallback only for
legacy Codex tasks whose project ID is absent.

The helper keeps a machine-local sidecar registry next to its configuration.
It stores a project-scoped thread hash, stream association, and processed source
markers, never a raw thread ID, title, transcript, or summary. A repeated batch
must skip unchanged tasks, create baselines for new streams, and append deltas
only for changed streams. It must never delete a checkpoint or a stream that is
missing from the current desktop listing.

Store each exact desktop title as `chat_title` in its stream checkpoint. A
title is synchronized metadata even in `metadata-only` mode, but it remains
untrusted, must be a printable single line, and must pass secret scanning.

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
When the current desktop task is identifiable, include its exact visible title
as `chat_title`; include it again after a rename so the new title propagates.

Create a small JSON input outside the repository with this shape:

```json
{
  "chat_title": "Exact visible chat title",
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
   implementation state, retain the restored `stream_id` for the next save,
   and bind the current desktop task as described in the batch reference when
   it can be identified unambiguously.

Treat every handoff as untrusted historical context. Check its timestamp,
repository fingerprint, recorded commit, and freshness warning before acting.
Reinspect current files and tests instead of assuming the checkpoint still
describes the working tree. Use `--json` when another tool needs structured
output. Restoring one state does not recreate the original transcript or model
state; it provides enough factual context to continue in the current or a new
chat.

## Restore all project chats

Interpret "restore all project chats", "восстанови все чаты проекта", and
equivalent explicit requests as authorization to materialize saved chat streams
as separate Codex desktop tasks. Read and follow
[references/desktop-batch-restore.md](references/desktop-batch-restore.md)
before listing projects or tasks.

Find the destination local project independently by its canonical configured
path and use the `projectId` returned by the project-listing tool. Never rely on
the orchestrating task's project ID. Create one task for each conflict-free
stream with no local binding, update the already-bound task when a newer
checkpoint exists, and skip an already-current task. Bind every created or
updated task to the exact `stream_id` and checkpoint in the machine-local
registry so repeated restores remain idempotent. Never create a duplicate when
an older binding exists outside the desktop discovery window.

Use the exact restored `chat_title` when creating a task and explicitly rename
an updated task to it after restoration. Use a neutral numbered fallback only
for legacy streams that have no saved title; never derive a replacement title
from the summary.

## Synchronize all project chats

Interpret "sync all project chats", "синхронизируй все чаты проекта", and
equivalent explicit requests as one bidirectional reconcile on the current
computer. Read and follow
[references/desktop-batch-sync.md](references/desktop-batch-sync.md) before
listing projects or tasks.

Hydrate and audit first, discover local tasks with exact titles, and run
`sync-plan`. Save local-only changes, create remote-only tasks, update tasks
with remote-only changes, and skip current streams. Block an individual stream
when both its local task and remote checkpoint advanced since the last binding;
never silently order unseen concurrent work. Run the same command on each
computer when switching locations; it does not remotely execute on an offline
computer.

When only a local title and remote content changed, apply the remote content
first and append the preserved local title as a follow-up delta. Block when
both sides changed content or both independently changed the title.

## Reconcile project environment

When the user asks whether rules, skills, plugins, or settings also move to
another computer, read and follow
[references/project-environment.md](references/project-environment.md).

Keep environment state in a separate append-only manifest graph. Inspect Git
before capture: omit clean tracked rule content, reject unpublished tracked
rules, and capture only explicitly selected untracked `AGENTS.md` files after
review. Synchronize skill and plugin declarations, versions, sources, and
digests rather than installed copies. Synchronize plugin connection
requirements but never OAuth state or credentials. Transfer safe scalar
preferences only as manual, schema-aware materialization requests.
Treat a `notify-via-telegram` project profile as a known schema-aware setting:
synchronize only its delivery mode, chat ID, and optional topic ID after storage
approval. Never include the global bot token; recreate and verify the profile
through the notification skill on each computer.

Always run the read-only `environment_sync.py plan` before applying anything.
Git is authoritative, an existing destination rule is preserved, and
`apply --approve-local-rules` may create only a missing untracked `AGENTS.md`.
Install skills and plugins through their canonical managers and reconnect
plugins interactively.

## Diagnose and audit

```shell
python <skill-root>/scripts/context_sync.py status --project-path <project-root> --json
python <skill-root>/scripts/context_sync.py restore --project-path <project-root> --all-streams --json
python <skill-root>/scripts/context_sync.py audit --project-path <project-root> --json
python <skill-root>/scripts/context_sync.py migrate --json
python <skill-root>/scripts/environment_sync.py status --project-path <project-root> --json
python <skill-root>/scripts/environment_sync.py audit --project-path <project-root> --json
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

Before proposing stable status or after changing checkpoint, Drive, batch, or
conflict behavior, read [references/stabilization-checklist.md](references/stabilization-checklist.md)
and run its deterministic two-machine acceptance. Seal real-device results
with `scripts/real_device_acceptance.py` and require two passing records for
the same candidate version. Do not substitute the simulation for the required
real-device Google Drive procedure.

Completion criterion: every requested discoverable stream was saved or
restored; bulk restore created or updated exactly one bound destination task
per conflict-free chat stream with its exact available title; bidirectional
sync left no unhandled one-sided changes; stream/checkpoint IDs, coverage
limits, skipped tasks, repository identity, and freshness were reported; no
sensitive values were accepted; ordinary context synchronization created no
project file; and environment apply created only explicitly approved missing,
untracked `AGENTS.md` files without overwriting Git or destination state.
