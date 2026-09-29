# Branch naming policy acceptance — 2026-09-29

This package implements the naming-policy preflight and opt-in preference
workflow for issue #142. It does not rename existing branches, modify native
global application instructions, or authorize publication/release operations.

## Observed behavior

- With no saved preference, installation/bootstrap adds synchronization rules
  without inserting branch-name defaults or creating private preferences.
  Existing project/default blocks remain intact, including custom content.
- Codex and Claude Code have separate private settings. Installation `--yes`
  never confirms naming preferences. A reviewed configure plan and its current
  digest plus explicit confirmation are required to save a choice.
- Confirmed settings survive repeated bootstrap/update setup byte for byte.
  External provider changes retain the accepted template snapshot; missing
  providers block resolution rather than select an unrelated fallback.
- The resolver respects declared priority and explicit delegation. It explains
  why an application default, project rule, explicit choice or saved fallback
  won. Mandatory project rules cannot be disabled by optional preference flags.
- An application with no naming rule is represented explicitly by null. Project
  instructions or a confirmed concrete fallback can resolve without fabricated
  application templates; wholly missing policy remains unresolved.
- Final-name checks reject changed context, settings, provider observations,
  helper/entrypoint artifacts or a different branch. They do not replace Git
  verification or independently prove completeness of the supplied context.
- CLI JSON supports non-ASCII rule/branch text even with an ASCII output
  encoding, including bootstrap and managed-update wrappers. Decision output cannot overwrite the selected provider source.

## Verification

Focused local suites exercised the helper (25 tests), project policy setup
(11), managed updates (52), copied-install smoke fixtures (11), and Claude
rules (6). These suites passed with Windows permission/platform-dependent
skips; symlink-capability skips are not evidence that those scenarios executed
on this machine. Helper tests first reproduced absent functionality; the two
later CLI/output regressions, including both installer wrappers, also failed
before their fixes.

The declared preflight profile passed: version/structure, all localizations and
translation freshness, marketplaces, security, and Codex/Claude bootstrap.
The changed README paragraph was updated in all twelve maintained translations.
Copied-skill tests execute outside the repository with an isolated config root.

A task-scoped resolver/check example used the actual applicable application
default allowing user preference and the user-supplied project rule. It selected
`feature/branch-naming-policy`, explained the unused `codex/` default and created
no private preference. This demonstrates the helper on supplied evidence, not
an independent audit of instruction hierarchy or a native application hook.

Independent read-only review of the resolver, installation integration and
reference found no actionable defect. Final publication still requires the
repository's exact-commit pre-push evidence and GitHub checks; this report does
not substitute for either, nor does it claim a release has been published.

## Delivery scope

The loading adapter is the updated skill workflow: it reads policy status before
choosing a name and checks its saved decision immediately before first remote
publication. Direct third-party installers cannot conduct the setup conversation;
the skill offers it on first use. Other workflows that do not use the skill are
not governed by the saved JSON. No changes were made to the user's live naming
preferences during development or acceptance.

## Full-suite runtime diagnosis

The first exact-commit run passed the Telegram bridge checks but exhausted the
unit-test limit of 1500 seconds. An unchanged diagnostic run completed all 732
tests successfully in 1809.378 seconds with nine platform-dependent skips on
Windows. The unit-test budget is now 2400 seconds, with 2700 seconds for the
full-profile wrappers and 45 minutes for CI. All checks remain required.
Timeout failures now retain their partial diagnostic output instead of reporting
an empty output digest. The runner regression test failed before that fix.
These observations do not replace the final exact-commit pre-push gate.
