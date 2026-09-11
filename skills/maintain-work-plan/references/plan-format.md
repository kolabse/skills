# Project plan conventions

Preserve an established plan instead of migrating it to this example. For a
new Markdown plan, keep an ordered table or list with stable IDs, task text,
status, optional desired date and dependencies. Keep detailed acceptance
criteria and subtasks beside their parent item.

| ID | Work | Status | Desired date | Depends on |
| --- | --- | --- | --- | --- |
| PILOT-014 | Prepare presentation | in_progress | 2026-09-18 | — |
| PILOT-015 | Present the project | planned | 2026-09-21 14:00 +05:00 | PILOT-014 |
| PILOT-016 | Process feedback | planned | — | PILOT-015 |

Resolve these conventions in existing project rules or an appropriate plan
preamble: canonical plan and log paths, project code, ID prefix, timezone,
status meanings, and completion/acceptance criteria. Preserve a declared
high-water mark or inspect historical IDs before allocation. Cancelled IDs are
also reserved; cancellation is a recorded decision, not successful completion.

The calendar selection and event mapping are user-specific. Keep calendar IDs,
event IDs and last-synchronized state in a user-approved local state file
outside the installed skill and excluded from Git. Do not put credentials or
private calendar details in shared rules or event descriptions.

Dates are optional. A date without a time maps to an all-day event. For timed
items, resolve a local time, timezone and duration; do not invent a midnight
meeting or default duration that the user has not accepted. Resolve ambiguous
or nonexistent daylight-saving times before sending a provider request.

Order and desired dates are separate. Flag conflicts rather than reorder the
plan or move unrelated tasks. If a dependent review requires N elapsed days
after actual shutdown, derive its earliest instant from the recorded shutdown
and project rule; use calendar-day arithmetic only when that is the declared
meaning. A scheduling change never authorizes shutdown or deletion.
