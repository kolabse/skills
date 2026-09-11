# Read-only task completeness check

This is an evidence review performed by the agent, not an automatic semantic
checker. It does not change the log, project rules, Git history or external
records. Keep any proposed corrections separate from the observed result.

## Establish the comparison boundary

Use the current task's factual milestones, the user-supplied milestone list,
and the relevant dated sections of the declared work log (default:
`docs/reports/work-log.md`). Name the task or
date range and the sources actually available. Read only explicitly referenced
validation or publication evidence needed to resolve a milestone. Do not crawl
older chats, unrelated repositories, inventories or the home directory.

If the available history is incomplete, mark the result limited to those
sources. A missing source is not proof that the work never happened, and a
summary in conversation is not proof that an entry was saved to the log.

## Compare outcomes rather than commands

1. List the material outcomes, decisions, checks, failures and unresolved work
   observed in the bounded task. Group routine commands that establish the
   same outcome. Use the project's dates and approved terminology.
2. Locate the actual saved entry covering each milestone. Check the outcome,
   date, verification and limitations, not just matching words. Several
   milestones may share one entry if its factual coverage is sufficient.
3. Classify each milestone using the table below. Link a specific entry or
   identify its date and short distinguishing text. Do not reproduce sensitive
   source material in the comparison.

| Status | Evidence needed |
| --- | --- |
| Covered | A saved dated entry accurately records the observed milestone and material limitations. |
| Partial | An entry exists but omits or overstates an important outcome, check or limitation. |
| Missing | No corresponding entry was found in the inspected sections. |
| External terminal record | Only the log's own final publication outcome is recorded in the authorized task record/final response, with an observed reference or an explicit failure/uncertainty. |
| Not applicable | A concrete reason shows why the candidate is not a material event requiring an entry. |

An agreed deferral should be recorded as a decision; it does not make missing
required work complete. A pending publication entry must not be treated as a
completed merge. Apply the terminal exception only as defined in `SKILL.md`.

## Report and follow up

Present a compact table of milestone, status, entry/evidence, and necessary
correction. State either that the inspected milestones are covered or that
specific gaps remain. Identify unavailable evidence and the comparison's date
range. Do not claim complete project history from a current-task review.

Offer proposed additions or corrections for partial/missing entries. The
read-only check itself does not apply them. If subsequent maintenance is
authorized, preserve existing language and local-only rules, check the saved
diff, and confirm the date and location of the actual update. Do not add an
entry solely to record a no-change completeness check unless it establishes a
material finding or an explicit project rule requires that event.

## Examples

| Observed situation | Correct result |
| --- | --- |
| Tests passed, but the entry describes only implementation | Partial; propose the observed test result. |
| The same deployment outcome is already accurately recorded | Covered; no duplicate append. |
| The log says review is pending; the final task response links the verified merge publishing it | External terminal record; no self-referential follow-up merge. |
| Another deployment occurs after that merge | A new material milestone; the terminal exception does not cover it. |
| Older task history is unavailable | Report bounded coverage and the unavailable history. |
| A write failed or the entry exists only as a draft | Missing; do not announce that the journal was updated. |
