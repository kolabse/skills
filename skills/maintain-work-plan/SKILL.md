---
name: maintain-work-plan
description: "Maintain a project's persistent active work plan: add or reorder tasks, preserve IDs and dependencies, reconcile verified completion with the work log, and synchronize dated plan items with the user's calendar. Use when the user or project rules require maintaining that plan, including its linked calendar events. Do not use for a one-off implementation outline, personal reminders unrelated to a project plan, or recording completed work only."
---

# Maintain Work Plan

Keep the project's active queue ordered and current. Pair it with
`maintain-work-log`: the plan owns upcoming work; the log owns dated outcomes
and verification. Announce activation once, naming the plan and requested
operation. Adding a task does not authorize executing it.

## Resolve the project contract

Read project rules and the declared plan before editing. Preserve the existing
format, language, ID scheme, status vocabulary, ordering and generator. Use
`docs/reports/work-plan.md` only as a default for a new plan when the project
has no existing location; use the declared work log, otherwise
`docs/reports/work-log.md`. Do not create a second plan or journal.

Resolve the project code, ID prefix, timezone, completion criteria and calendar
preferences from current instructions. Ask only for missing values needed for
the requested operation; undated planning does not require calendar setup.
The calendar project code is human-readable (for example `Пилот`), and need
not equal a technical ID prefix (`PILOT`).

For a new plan, follow [references/plan-format.md](references/plan-format.md).
When persistent use is requested, record the chosen paths and conventions in
the project's existing rules, using `$maintain-work-plan` for Codex or
`/maintain-work-plan` for Claude Code. Preserve unrelated rules and existing
authorization. Do not install a new policy merely to answer a one-time request.

The bundled helper is stateless and read-only. It checks a normalized snapshot,
not arbitrary Markdown and not the truth of completion claims. Read
[references/helper-contract.md](references/helper-contract.md) before using
it. Project rules and source documents remain authoritative; the snapshot is
a temporary validation artifact, never a second canonical plan.

## Maintain the active queue

1. Read the active plan and relevant historical IDs in the work log or owning
   registry. Allocate unused IDs; preserve them through renames, reordering and
   completion. Never allocate from the active maximum alone. If history is
   unavailable, resolve that gap before claiming an ID is unused.
2. Preserve the requested order. Dates are desired execution dates unless the
   project explicitly calls them deadlines. Do not silently sort by date or
   increase priority because a date is present.
3. Keep dependencies explicit. Flag cycles, missing predecessors and desired
   dates earlier than prerequisites. Completed predecessors remain resolvable
   through history. If an observation period controls a dependent milestone,
   calculate from the actual recorded completion and configured period in the
   project timezone; do not move unrelated dates automatically.
4. Distinguish planned, in progress, blocked and awaiting verification work.
   Record why work is blocked, what remains, and any acceptance requirements.
   An elapsed date or checked box is not completion evidence.
5. Edit only the affected items. Preserve nested content, acceptance criteria,
   unrelated edits and historical records. For generated plans, edit the owning
   source and regenerate; verify regeneration does not restore finished work.
6. Re-read the result and validate IDs, order, dependencies and retained work.
   Report date conflicts instead of silently inventing a schedule.

Completion criterion: requested changes appear once, IDs remain stable, the
active queue retains unfinished work, and unresolved dates or dependencies are
visible.

## Transfer verified completion to the work log

Read [references/completion-transfer.md](references/completion-transfer.md)
when closing or reconciling tasks. Verify all applicable acceptance conditions
and unfinished child tasks before proposing removal.

Use `maintain-work-log` when available, passing the resolved log path and task
ID. If it is unavailable, follow the same dated evidence contract in the
reference; report that composition was unavailable rather than claiming it ran.
Do not invoke its default-path configuration helper for a differently located
existing journal.

Persist and verify the dated outcome before removing its plan item. Reuse an
existing supported completion entry. A failed log write leaves the task active;
a saved log followed by failed plan update is recoverable and must be reported
as partial completion of the document update.

Do not automatically mark the calendar event as successfully synchronized
when only the documents changed.

## Synchronize dated items with the calendar

Recommend calendar synchronization when dated plan items and a usable calendar
connection exist. Read [references/calendar-sync.md](references/calendar-sync.md)
before calendar work. Resolve the selected calendar, timezone and standing
permission once; reuse applicable authorization on later runs. Access alone is
not permission to create events.

Every managed event title starts with the project code in square brackets:
`[Пилот] Провести презентацию`. Use stable project/task markers and provider
event IDs for matching, never titles alone. Preserve manual changes through
three-way comparison and treat unknown creation outcomes as uncertain until
resolved. Calendar access is optional: an unavailable connection must not
prevent local plan maintenance.

Completion criterion: each affected dated task has a verified linked event or
an explicit pending/conflict/unsupported result. Document publication, task
completion and calendar synchronization are reported separately.
