# Calendar synchronization

Use the user's available calendar connector or supported tool. This skill ships
no credentials and no provider client. Read the tool's current schema before
calling it; use provider documentation when provider-specific semantics are
unclear. Never translate unsupported operations into guessed API calls.

## Establish the standing policy

Resolve the calendar, stable project identity, displayed project code, timezone,
timed-event duration and authorization. Record the user's chosen recurring
synchronization policy once in the appropriate private/project settings; reuse
it without repeated approval prompts. Calendar read access is not write
authorization. Adding guests or sending invitations requires explicit intent,
even when writing personal calendar events is already authorized.

Dates are desired execution dates unless the task explicitly defines a
deadline. Date-only items use all-day events. Timed items need an unambiguous
offset/timezone and positive duration. Respect the provider's all-day exclusive
end-date convention. Use actual project timezone rules when calculating a
dependent milestone; do not convert a desired date into a different local day.

## Identify and compare

Every title is `[PROJECT CODE] Task title`, for example
`[Дайджест] Проверить новые правила` or `[Анимация] Сделать новые фоны`.
Put a stable project/task marker in an event property or description, together
with a safe plan link and concise expected result. Do not expose private local
filesystem paths as public links.

The stable project identity must distinguish projects even if their display
codes or task prefixes match. Store the selected calendar ID, provider event ID,
task ID and last synchronized managed fields in local state outside Git and the
installed skill. This state is not completion evidence or a second task queue.
Preserve provider fields outside the managed title/date/time fields.

Read current events and local plan state before proposing changes. Compare
desired fields, observed remote fields and the last successful synchronized
fields. Remote changes since the baseline require reconciliation; do not
silently overwrite a manually moved or renamed event. If both sides independently
reach the same result, verify it and refresh the mapping. Match identity first,
never a similar event title.

The read-only `calendar-preview` helper can propose actions from these normalized
observations. Its input is a bounded snapshot, not authorization and not a live
provider query. Refresh observations immediately before each actual write.

## Execute and retain recoverable state

- Create only after a successful complete lookup proves no managed event exists.
  Use provider idempotency where available, or a searchable stable marker.
- After a create/update, read back and verify the event; only then save its
  identity and synchronized fields. Use provider revisions/ETags for conditional
  updates where supported.
- If a request times out or state persistence fails after creation, mark the
  outcome unknown. Search/read the provider for the marker or idempotency key
  before retrying; absence from a stale or partial list is not proof of absence.
  If identity cannot be established, stop that item as uncertain.
- If a previously linked event is missing, do not immediately recreate it:
  the user may have deleted it deliberately. Resolve the discrepancy.
- Removing a date, cancelling a task or completing it requires the agreed
  policy for an existing future event. The preview flags review; it never
  deletes events. Preserve past calendar history.
- If the connector is unavailable, keep document changes and report pending
  synchronization. If only some items succeed, preserve their mappings and
  retry only unresolved items after rereading current state.

A successful plan edit does not prove calendar synchronization. Report counts
or task IDs for verified, pending, conflicting and unsupported operations.
Do not claim end-to-end provider success from an offline preview test.
