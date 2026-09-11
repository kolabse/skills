# Read-only normalized snapshot helper

`scripts/work_plan.py` uses only Python's standard library. It reads JSON and
prints JSON; it never writes a plan, log, configuration, calendar or network
resource. It does not parse arbitrary Markdown. Preserve an established plan's
format and custom ID scheme through the agent workflow instead of converting it
solely to use this helper.

## Commands and Python API

```sh
python scripts/work_plan.py status --json
python scripts/work_plan.py validate --input snapshot.json --json
python scripts/work_plan.py calendar-preview --input snapshot.json --calendar-state calendar.json --json
```

`status` reports capabilities without discovering or configuring a project.
`validate_snapshot(payload)` returns `valid`, `next_id`, and `warnings`.
`calendar_preview(snapshot, state)` returns `calendar_id`, `project_id`,
`operations`, and validation `warnings`. Neither mutates its arguments.
Malformed data raises `PlanError`; CLI input errors print an `error` object and
exit 2. Successful commands exit 0; conflict operations are review results,
not malformed input. Output is JSON with or without the explicit `--json` flag.

The [snapshot schema](../schemas/snapshot.schema.json) and
[calendar-state schema](../schemas/calendar-state.schema.json) describe
structural constraints; the helper additionally checks
real dates, dynamic ID prefixes, aliases, dependencies, identity uniqueness and
cycles. JSON Schema alone does not establish semantic validity.

## Snapshot semantics

Use schema version 1 with stable `project_id`, display `project_code`,
`id_prefix`, `historical_ids`, and an ordered `tasks` array. Every task has `id`,
`title`, `status`, `depends_on`, and nullable `desired_date`.
Allowed active statuses are `planned`, `in_progress`, `blocked`, `partial`, and
`acceptance_pending`. Tasks remain active until the agent verifies completion,
logs its outcome first, and removes the active item through the established
workflow. This helper neither verifies acceptance nor performs that transfer.

IDs use the configured prefix and a positive numeric suffix. Preserve existing
padding and all original identifiers. Numeric aliases such as `TASK-1` and
`TASK-001` cannot coexist. `next_id` is one greater than the largest active or
historical suffix, padded to the largest existing width, with a minimum width
of three. Historical IDs reserve completed and cancelled identities; they may
overlap active IDs during log-first recovery. They do not prove completion.
Dependencies on historical-only IDs generate an outcome-unknown warning.

Array order expresses priority; validation never reorders tasks. Unknown,
self, duplicate or cyclic dependencies fail validation. A predecessor later
in the list produces `dependency_order`; a predecessor with a later desired
date produces `dependency_date`. Both are warnings for agent review.

`desired_date` is an actual `YYYY-MM-DD` date or null. It is not a booked time.
Date-only tasks preview a one-day all-day event using `date`. Timed scheduling
requires both `starts_at` in
`YYYY-MM-DDTHH:MM:SS+HH:MM` format (a negative offset is also allowed) and a
positive integer `duration_minutes`. Timed tasks require a nonnull
`desired_date` equal to the local date portion of `starts_at`. No time or
duration is inferred. `project_code` cannot contain square brackets. Supported
numeric ID suffixes have at most 100 digits.

Save this minimal date-only example as `snapshot.json`:

```json
{
  "schema_version": 1,
  "project_id": "stable-example-project",
  "project_code": "APP",
  "id_prefix": "TASK",
  "historical_ids": [],
  "tasks": [{
    "id": "TASK-001",
    "title": "Implement export",
    "status": "planned",
    "depends_on": [],
    "desired_date": "2026-10-01"
  }]
}
```

Save the following as `calendar.json` only after verified complete observation
establishes no matching events or links. The commands above then validate the
snapshot and preview an all-day `create` operation.

```json
{
  "schema_version": 1,
  "calendar_id": "example-calendar",
  "observation_complete": true,
  "unknown_outcome_task_ids": [],
  "events": [],
  "links": []
}
```

## Calendar observations and retry handling

Calendar state is a normalized observation snapshot, not persistent skill
configuration. The helper is stateless and does not store provider credentials
or links. State is scoped to one `calendar_id`. Events carry `event_id`, stable
`project_id`, `task_id`, and `managed` fields. Links carry the same identifiers
and `last_synced` managed fields. Managed fields are either `title` and `date`
for an all-day event, or `title`, `starts_at`, and `duration_minutes` for a timed
event. Mixing the two shapes is invalid. Exclude attendees and provider secrets.
Unrelated provider fields must stay outside this normalized projection.
Identity is `(calendar_id, project_id, task_id)`, never the mutable title or
project code. Desired titles are `[project_code] Task title`.

`observation_complete` must mean all relevant identity and mapped-event lookups
were verified, not merely that a date-window listing finished. Incomplete
observations block scheduled-task operations with a conflict. Add task IDs to
`unknown_outcome_task_ids` after uncertain provider outcomes. They block creation
and updates until the result is verified; an exact unique observed match allows
recovery/noop. Never clear uncertainty merely because a request timed out.

Operations:

- `create`: verified absence, no existing link, no uncertain outcome.
- `recover`: one unlinked identity match with exactly desired managed fields.
- `noop`: the linked event already matches desired fields.
- `update`: observed fields still equal `last_synced`, but desired fields differ.
- `conflict`: remote changes, missing/mismatched links, duplicate identity,
  incomplete observation, unknown outcome, or differing unlinked match.
- `unlink_review`: a previously represented task is no longer active or no
  longer scheduled. This never authorizes event deletion or link mutation.

Equivalent timestamps with different numeric offsets compare equal. Updates
include `expected_managed`; the executing agent must re-read provider state
and enforce provider preconditions immediately before a separately authorized
write. A preview alone cannot prevent a race. After successful writes, persist
provider identity and the actual managed snapshot. Use provider-supported
idempotency or a searchable stable marker before retrying creation.

The helper creates no invitations and supplies no attendees. Actual calendar
writes, link persistence, completion transfer and external acceptance are the
agent workflow's responsibility. Explicit invitation intent remains required.
