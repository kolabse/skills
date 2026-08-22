---
name: maintain-work-log
description: "Maintain the canonical dated project work log at docs/reports/work-log.md. Use when the user or applicable project instructions require that log for the current task; when recording material changes, operations, diagnostics, decisions, verification, or blockers in an already configured work-log workflow; when initializing its policy in AGENTS.md or CLAUDE.md; or when reconstructing missing entries from Git history and available project conversations. Do not infer this skill from ordinary project work alone when no work-log requirement is present, and do not use it for application logs, time-tracking products, or personal notes."
---

# Maintain Work Log

Treat `docs/reports/work-log.md` as the project's durable operational record.
Record observable facts and decisions, not private reasoning, credentials, or a
transcript of routine command execution.

## Configure the project

1. Resolve the repository root and select the target agent explicitly when
   configuring rules. Codex uses `AGENTS.md` with `$skill-name`; Claude Code
   uses `CLAUDE.md` with `/skill-name`. Omit `--agent` only for Codex.
2. When no equivalent policy already exists, run the idempotent helper:

   ```shell
   python <skill-root>/scripts/configure_project.py configure --project-path <project-root> [--agent codex|claude-code]
   ```

   It preserves unrelated content, creates the log when absent, and adds one
   managed block:

   ```markdown
   <!-- maintain-work-log:start -->
   ## Work log

   Use `$maintain-work-log` for every project task. Maintain the dated,
   chronological log in `docs/reports/work-log.md`; record material changes,
   operations, diagnostics, discussions, decisions, verification, blockers,
   and rollback results before completing the task. Never record secrets,
   personal data, private reasoning, or raw sensitive logs.
   <!-- maintain-work-log:end -->
   ```

3. Do not add a duplicate block when an equivalent project rule already names
   the same log and obligations.
4. Read an existing log before editing it. Preserve its language, heading
   hierarchy, date format, tables, and entry style.
5. If the log is absent, create it with this minimal structure unless the
   project defines another template:

   ```markdown
   # Журнал работ

   ## YYYY-MM-DD

   - Выполнено действие; зафиксирован проверенный результат.
   ```

6. Determine whether the project is non-empty from tracked files and Git
   history. When work predates the earliest reliable log entry, offer to
   reconstruct the missing period. State the proposed date range and available
   sources before performing a large retrospective update.

Inspect configuration without changing files with:

```shell
python <skill-root>/scripts/configure_project.py status --project-path <project-root> [--agent codex|claude-code] --json
```

Completion criterion: the project policy names the log and invokes this skill,
the log exists in the project's established format, and any historical gap has
been either offered for reconstruction or explicitly deferred.

## Maintain the current record

1. Read the latest relevant entries before starting substantive work. Do not
   repeat an event that is already recorded.
2. Use the project's timezone. Resolve the actual calendar date instead of
   assuming it from commit timestamps or relative words such as "today".
3. Keep a short factual ledger while working. Capture every material event:
   - code, configuration, documentation, schema, or infrastructure changes;
   - commands or API calls that changed local or external state;
   - diagnostics and read-only investigations that established a useful fact;
   - user or team discussions that changed requirements or understanding;
   - accepted, rejected, deferred, or superseded decisions and concise reasons;
   - deployments, migrations, tests, validation evidence, failures, rollbacks,
     blockers, and unresolved follow-ups.
4. Summarize related low-level commands as one outcome. Do not turn the log into
   a terminal transcript, narrate private chain-of-thought, or claim an outcome
   that was not observed.
5. Update the log after a meaningful checkpoint and always before the final
   response. For a discussion-only task, record the resulting decision,
   clarification, open question, or confirmed absence of change.
6. Add entries under the correct date in chronological order. Insert a late
   discovery under its historical date rather than presenting it as current
   work. Preserve unrelated user edits in a dirty worktree.
7. Name affected resources and verification succinctly. Link repository files
   when that matches the existing style; describe external systems by stable
   identifiers without exposing access details.
8. Review the resulting diff for chronology, duplicate entries, accidental
   secrets, and statements stronger than the available evidence.

Completion criterion: all material work in the task is represented under the
correct date, verification and remaining risk are distinguishable, and the log
contains no sensitive values.

## Reconstruct missing history

Perform reconstruction only after the user accepts the proposed scope, unless
they explicitly requested reconstruction in the current task.

1. Determine existing coverage and gaps from dated headings and entries. Never
   replace or reorder reliable historical content merely to normalize style.
2. Gather evidence in this order:
   - Git commits with author dates, messages, changed paths, and focused diffs;
   - available project task or chat histories and their timestamps;
   - project documentation, inventories, plans, deployment records, and reports;
   - external system history when access is authorized and dates are reliable.
3. Treat commits as evidence, not as one-to-one work-log entries. Combine
   related commits into one event and separate unrelated work from broad commits.
4. Use conversation history only when tools or the current context expose it.
   Never claim that all chats were inspected when some histories are unavailable.
5. Reconcile conflicts by preferring observed deployed state and later explicit
   decisions. Preserve uncertainty with wording such as "по доступной истории"
   and record a date range when an exact date cannot be established.
6. Draft missing entries in chronological batches. Add only facts supported by
   evidence and leave existing entries intact unless a correction is clearly
   justified.
7. Report the reconstructed range, sources used, unavailable sources, and any
   remaining gaps.

Completion criterion: reconstructed entries are dated, evidence-based,
non-duplicative, and transparent about incomplete chat or external history.

## Protect sensitive information

- Never record passwords, tokens, private keys, access-key IDs, secret values,
  personal data, or full credential-bearing commands.
- Record that a secret was created, rotated, stored, or transferred without its
  value. Refer only to an approved secret store or ignored path when useful.
- Summarize logs and errors; redact authorization headers, query credentials,
  request bodies with personal data, and confidential payloads.
- Do not commit a work log that project policy requires to remain local. Follow
  `.gitignore`, repository instructions, and the user's explicit publication
  boundary.
