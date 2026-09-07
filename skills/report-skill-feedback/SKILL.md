---
name: report-skill-feedback
description: "Prepare and optionally submit a privacy-bounded feedback report about an installed skill after separate user approvals for collection and external submission. Use when a user wants to report whether a skill triggered, completed its workflow, failed, required manual intervention, or should be improved. Do not collect whole chats, source code, secrets, identifying project data, or submit anything without preview and fresh approval."
---

# Report Skill Feedback

Turn one observed skill use into a small, reviewable report that maintainers can
use as acceptance evidence. Consent is specific to one report and never expands
permission to inspect arbitrary project files, earlier chats, or external
systems.

## Prepare a consent request without collecting evidence

Use the declared skill name to generate a checklist and input questionnaire:

```shell
python <skill-root>/scripts/report_feedback.py prepare \
  --skill <skill-name> --language ru --json
```

`prepare` does not inspect an installation, read evidence, or create a report.
Fill the questionnaire only from the bounded observations approved below; do
not turn missing answers into an assumed successful outcome. English (`en`,
default) and Russian (`ru`) report templates are supported.

## Obtain collection consent

Before collecting evidence, tell the user:

- which skill use will be described;
- the exact categories of information proposed, including installation scope
  and the selected `SKILL.md` digest if artifact provenance will be recorded;
- that free text will be paraphrased and checked for identifiers;
- that declining has no effect on the original task or skill;
- that GitHub submission is attributable to the submitting account and is not
  anonymous even when the report body is de-identified.

Ask for explicit consent for this one report. Without it, stop without creating
a draft. Do not reuse consent from installation, telemetry preferences, another
report, or the original task.

An optional local session ledger can track which report is waiting, declined,
or prepared. Use [references/preparation-and-session.md](references/preparation-and-session.md)
only when the user wants that bookkeeping. A ledger entry is never evidence of
fresh authorization for collection or submission.

## Collect only bounded evidence

Prefer observable metadata already present in the current task:

- skill name and the version of the explicitly selected artifact, with optional
  installation scope and SHA-256 of its `SKILL.md` bytes;
- Codex or Claude Code and operating-system family;
- broad project kind and repository count, without names or paths;
- expected and observed invocation behavior;
- outcome: `success`, `partial`, `blocked`, or `error`;
- controlled trigger, workflow, safety, retry, and manual-intervention signals;
- short paraphrases of useful evidence, unclear instructions, and one proposed
  improvement.

Never include source code, full prompts or chat excerpts, logs, stack traces,
credentials, personal or organization names, repository names, absolute paths,
hostnames, internal or external URLs, issue links, or customer data. Do not scan
the project to enrich the report. If a safe paraphrase cannot preserve the
meaning, omit the field.

Select the root of the copy actually used, from the current task's invocation
evidence. Do not pick the newest installation or substitute the reporting
helper's version. If the target skill was not invoked, describe the selected
candidate as such; inspecting it does not prove that it ran. The helper reads
only the explicit root's `SKILL.md` and adjacent `collection-metadata.json`.
If identity cannot be resolved, report the gap instead of guessing a version.

After collection consent, use the questionnaire answers to build the input:

```shell
python <skill-root>/scripts/report_feedback.py build-input \
  --answers <approved-answers.json> --skill-root <selected-skill-root> \
  --installation-scope plugin --language ru \
  --collection-consent --output <approved-input.json> --json
```

The builder fills the artifact identity and validates the result. See
[`schemas/feedback-answers.schema.json`](schemas/feedback-answers.schema.json)
for the answer fields and
[`schemas/feedback-input.schema.json`](schemas/feedback-input.schema.json)
for the final input. Store temporary answers and input outside project
repositories in the approved local feedback location.

Machine output distinguishes `observed_skill` from `reporter`. Resolved roots
are local diagnostics only: never paste that output into the feedback body.
The report may contain the installation scope and `SKILL.md` hash, not the
root. The hash identifies those instruction bytes, not the whole installation
or an authenticated execution history. An artifact can change after the
observation; retain the observed identity rather than silently refreshing it.

To seal the built input, or an existing approved schema-valid input, run:

```shell
python <skill-root>/scripts/report_feedback.py draft \
  --input <approved-input.json> --collection-consent --json
```

The helper rejects oversized input and common secret, URL, email, path, and code
patterns. By default it writes the Markdown draft to the user's configuration
directory, outside the project. Pass `--output` only when the user approved that
exact location.

Completion criterion: the user sees the complete Markdown report and its path;
no external mutation has occurred.

Language changes headings and boilerplate, not free-text evidence. Prepare the
approved paraphrases in the selected language before sealing. Controlled enum
values and machine identifiers remain stable. A different language changes the
report identity and seal and requires a new complete preview. Existing
version-1 English inputs and sealed reports remain supported.

## Obtain separate submission consent

After showing the complete draft, state the destination and that the user's
GitHub identity will be visible. Ask for fresh approval to submit that exact
report. Editing the report, destination, or title invalidates the approval and
requires another preview.

With approval, submit through the authenticated GitHub CLI:

```shell
python <skill-root>/scripts/report_feedback.py submit \
  --report <reviewed-report.md> --submission-consent --json
```

The helper revalidates the sealed draft, targets only `kolabse/skills`, and
returns the created issue URL. If `gh` or authentication is unavailable, do not
silently choose another channel; offer the reviewed file for manual submission.

Read [references/preparation-and-session.md](references/preparation-and-session.md)
when a submission fails. Error categories are sanitized; a timeout, failed
process, or unrecognized success response can mean the issue was created even
though its URL was not received. Treat `submission_state: unknown` as unresolved,
not as proof that nothing was submitted. The helper does not retry automatically.
Reconcile the exact Report ID at the fixed destination before considering a
retry, preserving the existing approval only for the unchanged report and
destination. Any changed content still needs the new preview and approval above.

Completion criterion: report the observable issue URL, or clearly state that
only a local reviewed draft exists when submission was not attempted. If an
attempt has an unknown outcome, explicitly report that submission remains
unresolved and the reviewed draft is retained.
