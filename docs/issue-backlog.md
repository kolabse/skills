# Implementation queue

Updated: 2026-09-29. This queue records accepted work, not completed fixes or
release authorization. Existing Telegram changes remain in progress.

| Order | Item | State | Completion criteria |
| --- | --- | --- | --- |
| 1 | [#131: Telegram bridge](https://github.com/kolabse/skills/issues/131) | In progress | Review and required checks for the packaged owned-task prototype; installed-package live acceptance before release. Existing Desktop task control remains separate. |
| 2 | [#142: branch-name policy resolution](https://github.com/kolabse/skills/issues/142) | Queued | Resolve and record the effective naming rule before the first remote branch publication; explain mismatches; cover conflicting defaults in acceptance tests. |
| Release gate | `report-skill-feedback` stabilization | Candidate for promotion | Complete the [evidence assessment](reports/report-skill-feedback-stability.md), then promote in a versioned release with `stable_since`. |

## #142 — branch policy preflight

The report describes two published `codex/` bug-fix branches although the skill's
reference suggested `bugfix/`. The reference was read: this is not evidence of
a missing skill invocation. An application instruction had higher priority and
set `codex/` as its default, allowing explicit user preference to override it.
The gap is the missing visible policy-resolution step, not proof that `bugfix/`
must always win.

Planned scope:

- Before creating/publishing the task branch, determine the task type, proposed
  name/prefix, applicable rule source and priority, and any explicit user choice.
- Report the selected rule and explain a mismatch with a lower-priority default.
  A fully resolved default does not require an extra approval question.
- If an applicable higher-priority rule permits a user choice, honor an explicit
  choice; if ambiguity remains material, resolve it before publication.
- Check the final name immediately before the first remote publication. Syntax
  checks and application unit tests alone do not verify workflow policy.
- Record the selected skill artifact separately from the installed collection
  version when multiple copies exist. The report does not prove that duplicate
  copies caused the naming discrepancy.

### Installation and update preference (design clarification)

Offer an explicit naming-policy choice rather than blanket consent to transfer
control of all project branches to a skill. Installing a collection alone is
not consent to change branch conventions. The choice affects future branch
names only; it does not authorize branch creation, publication, renaming,
merging, release actions or changes to application instruction priority.

Offer these sources, showing examples and the actual detected source:

1. Preserve the application's naming default.
2. Use the `kolabse/skills` naming templates.
3. Use a specifically identified other collection or standalone skill.
4. Use the repository's declared naming policy.
5. Use the user's global naming policy for the selected application.

Recommend repository policy when it exists, with an explicitly selected global
fallback for repositories without a policy. These are two settings, not five
mutually exclusive sources: repository override behavior and the fallback
source. A safe initial proposal is to honor repository policy where applicable
and otherwise preserve current application behavior. Require an actual answer
before changing preferences; silence or unattended installation keeps behavior
unchanged. Exact higher-priority instructions remain authoritative; a saved
preference is effective only where those instructions permit user choice.

Store the confirmed preference in supported private user configuration, scoped
to the application, with a schema version, chosen source, fallback, and the
accepted template revision. Do not silently write every repository's AGENTS.md
or overwrite existing global user instructions. Adapters must establish how the
application actually loads this preference; a JSON file alone does not change
instruction priority or prove the agent honors the setting.

For another skill, resolve the concrete provider and show its current templates
before confirmation. Missing or ambiguous providers must not silently fall back
to this collection. Unsupported preferences must be reported rather than stored
as if they were effective.

Ask on first interactive configuration, including an existing installation's
first update that introduces this setting. Ordinary subsequent updates preserve
the choice without asking again. If the selected policy changes materially,
show the old/new templates and obtain confirmation before adopting new behavior;
retain the previous effective policy when confirmation is absent. Reverting to
application defaults must be supported without renaming existing branches.

Additional acceptance cases: fresh install and upgrade with no answer; existing
confirmed choice across updates; repository override versus fallback; missing
external provider; changed template revision; application-specific settings;
read-only status of the effective policy; no unrelated global/project edits.

Acceptance cases:

1. Higher-priority application default `codex/`, lower-priority skill default
   `bugfix/`, no explicit preference: select `codex/` and explain the source.
2. The same application rule explicitly permits user preference; user requests
   `bugfix/`: select `bugfix/` and record the permitted override.
3. Applicable project naming convention, no conflicting higher-priority rule:
   preserve the project convention.
4. Multiple skill installations: show provenance uncertainty accurately; do not
   invent a local artifact version from the plugin version.

Do not rename already published branches, change priorities, or force-push as a
side effect of this queue entry. Issue #142 remains open until implemented and
verified. No external comment or duplicate issue was created during this triage.
