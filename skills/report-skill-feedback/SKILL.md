---
name: report-skill-feedback
description: "Prepare and optionally submit a privacy-bounded feedback report about an installed skill after separate user approvals for collection and external submission. Use when a user wants to report whether a skill triggered, completed its workflow, failed, required manual intervention, or should be improved. Do not collect whole chats, source code, secrets, identifying project data, or submit anything without preview and fresh approval."
---

# Report Skill Feedback

Turn one observed skill use into a small, reviewable report that maintainers can
use as acceptance evidence. Consent is specific to one report and never expands
permission to inspect arbitrary project files, earlier chats, or external
systems.

## Obtain collection consent

Before collecting evidence, tell the user:

- which skill use will be described;
- the exact categories of information proposed;
- that free text will be paraphrased and checked for identifiers;
- that declining has no effect on the original task or skill;
- that GitHub submission is attributable to the submitting account and is not
  anonymous even when the report body is de-identified.

Ask for explicit consent for this one report. Without it, stop without creating
a draft. Do not reuse consent from installation, telemetry preferences, another
report, or the original task.

## Collect only bounded evidence

Prefer observable metadata already present in the current task:

- skill name and installed collection version;
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

Create a schema-valid input document and run:

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

Completion criterion: report the observable issue URL, or clearly state that
only a local reviewed draft exists.
