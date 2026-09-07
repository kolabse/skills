# Prepare one report and track its local state

Use `report_feedback.py prepare` before collection to obtain the per-report
consent checklist and required answer fields. This is a questionnaire, not a
completed input or an observation of skill behavior. It does not scan project
files, other installations, or earlier conversations.

After explicit collection consent, provide `agent`, `environment`, `invocation`,
`outcome`, and `signals` in the answers document, plus only approved optional
paraphrases. `build-input` adds `schema_version` and the selected skill's identity.
It does not choose the outcome or interpret missing observations as a pass.

## Keep artifact identities separate

`--skill-root` is an explicit selection, not an installation search. Use the
root observed in the current invocation; for a failure to invoke, identify the
candidate copy without claiming it executed. The selected metadata version must
agree with that skill's name. Missing or conflicting metadata blocks identity
construction rather than borrowing a version from another copy.

Installation scope is declared by the caller: `global`, `project`, `plugin`,
`source`, or `unknown`. Choose `unknown` when the scope is not established.
`skill_sha256` covers the exact bytes of `SKILL.md`, including line endings;
it is not a digest of scripts, assets, dependencies, or the installed runtime.
Two copies with identical instruction bytes have the same digest even when
their local paths differ.

Local machine output names the reporting helper separately from the selected
subject. Absolute roots help diagnose mixed installations locally but are
excluded from the shareable report input and Markdown. Do not copy local
diagnostic objects into free-text evidence. Neither metadata nor a hash proves
which artifact executed historically; that claim needs current-task evidence.

## Use a ledger only as optional bookkeeping

The separate `feedback_session.py` helper stores only skill names and controlled
report states. Use an explicit local ledger outside participating project
repositories. Show its purpose and location when enabling it; do not create one
silently while collecting an unrelated report.

```shell
python <skill-root>/scripts/feedback_session.py create \
  --ledger <approved-local-ledger.json> --project-root <project-root> \
  --skill <skill-name>
python <skill-root>/scripts/feedback_session.py set \
  --ledger <approved-local-ledger.json> --project-root <project-root> \
  --entry 0 --state awaiting-collection
python <skill-root>/scripts/feedback_session.py show \
  --ledger <approved-local-ledger.json> --project-root <project-root>
```

Use `append --skill <skill-name>` with the same ledger and project-root arguments
for another report. Entries are addressed by zero-based index; `create` refuses
to overwrite an existing ledger. The path guard checks the explicitly declared
project boundary; choose a location outside any other participating repositories
as well. It does not discover all repositories on the workstation.

Each entry represents one report, including when several entries name the same
skill. Keep collection decisions separate from submission decisions. A declined
entry has no effect on the original task; a new report about that skill needs
its own decision. Do not record report text, artifact roots, account identities,
issue URLs, or evidence in this ledger.

The ledger is advisory and can be updated only from actually observed decisions
and outcomes. `collection-consented` and `submission-consented` are historical
notes, not authorization tokens. The reporting helper does not load the ledger;
it continues to require the applicable per-report consent flag. Do not turn a
session, list of skills, or one approved entry into batch consent.

If a report is edited, return it to the appropriate waiting state and preview
the complete new report before submission. `submitted` means a valid issue URL
was actually received or independently reconciled. An uncertain send remains
`submission-unknown`; do not mark it declined, unsubmitted, or completed just
because the command failed.

## Interpret external failures without exposing diagnostics

The submission helper returns fixed error categories rather than raw CLI
stderr, credentials, hostnames, or file errors. A missing executable or process
launch failure means `not-attempted`. Once the external process has started,
a nonzero result, timeout, or unexpected response is conservatively `unknown`.
No automatic retry follows an uncertain result.

Use the sealed report's Report ID for a bounded read-only check at
`kolabse/skills`. If the issue exists, record its actual URL. If the state cannot
be determined, keep it unresolved and retain the reviewed draft. If no issue
exists and retry is appropriate, use only the unchanged sealed report and the
existing applicable approval; changing content, title, or destination requires
a new preview and approval. Never include raw failure output in feedback to
explain the error category.

Russian and English templates translate report headings and consent boilerplate.
They do not translate the user's free text. Keep controlled signal values and
machine identifiers unchanged, and show the full sealed result in its chosen
language before seeking submission consent.
