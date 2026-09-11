# Completion transfer and recovery

Completion is a semantic decision made from observed results and the project's
acceptance conditions. The helper cannot establish it from task syntax.

1. Read the current plan, relevant log entries and completion evidence. Note
   their file hashes or revisions. Inspect unfinished child items and acceptance
   conditions, including deployment or user acceptance when required.
2. Keep partial, deferred, blocked and unverified work active. Record the
   completed portion in the journal without claiming whole-task completion.
   Retain the outstanding requirements or an explicitly linked follow-up; do
   not discard them while removing a parent.
3. Identify the completion record by stable task ID and the specific outcome.
   A historical mention of the ID is not proof of completion. Reuse a matching
   dated completion entry; if absent, add actual completion date, ID, outcome,
   verification/source references and material limitations through the journal
   workflow. Follow the journal's established structure and timezone.
4. Before writing, check that the observed documents have not changed. Use the
   project's locking/revision mechanism where available. On concurrent changes,
   reread and rebuild the affected edit; never overwrite them with an old
   whole-file snapshot. A hash check alone is not a filesystem transaction.
5. Save and reread the journal entry. If this fails, leave the active item
   intact. Only then remove the fully completed active item or update its
   owning generator. Preserve history and dependencies referencing its ID.
6. Reread both documents; verify unfinished content remains and regeneration
   does not restore completed work. Run reconciliation again conceptually:
   there must be no duplicate entry and no additional removal.
7. Report saved, partially saved, published and calendar states separately.
   Follow applicable synchronization/push rules for publication, without
   expanding publication authorization.

Recovery is deliberately log-first, not an atomic two-file transaction. If the
journal was saved but the plan update failed, retain that journal entry. On
retry, validate it against current evidence, reuse it and finish only the
remaining plan edit. Do not undo a durable result to conceal partial failure.
If the task changed after the journal entry (for example new acceptance work),
keep the new work active; the old completion does not authorize its removal.

For calendar events, preserve past history. Apply the project's agreed policy
for a future event that is no longer needed (keep, annotate or cancel), checking
for manual edits first. Without such a policy ask for the affected action;
task completion alone does not authorize deleting an event or notifying guests.
