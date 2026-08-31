# Contributing skills

English | [Русский](docs/i18n/ru/CONTRIBUTING.md) | [Español](docs/i18n/es/CONTRIBUTING.md) | [Français](docs/i18n/fr/CONTRIBUTING.md) | [Deutsch](docs/i18n/de/CONTRIBUTING.md)

This repository is the canonical home for reusable kolabse skills. Keep each
skill focused, portable, attributable, and independently installable.

## Before adding a skill

1. Identify the canonical source. Decide whether this repository will own the
   skill or mirror another source.
2. Establish the right to redistribute every copied instruction, script,
   reference, and asset. Original contributions are accepted under the
   repository's Apache-2.0 license unless explicitly marked otherwise. Preserve
   third-party license files, copyright notices, attribution, and modification
   notices; record their SPDX expression in the catalog. Do not publish
   third-party material with an unresolved license.
3. Search existing descriptions for overlapping triggers. Extend an existing
   skill when the workflow has the same purpose; add a new skill when it has an
   independently useful trigger and completion criterion.
4. Choose a lowercase, verb-led, hyphenated name of at most 63 characters.

Completion criterion: ownership, provenance, license, scope, and skill name are
known before files are copied.

## Track a candidate through implementation

When a new or extended skill originates from a GitHub Issue, keep that Issue
as the canonical work item until implementation is represented in the primary
branch.

1. Record the source Issue in the implementation pull request.
2. Put `Closes #<issue-number>` in the pull request body. If the change must
   not close the Issue, state the reason and intended disposition explicitly.
3. After merge, inspect the Issue rather than assuming the closing keyword was
   applied. If it remains open unexpectedly, close it as completed with links
   to the implementation pull request and, when available, the release.
4. If implementation is rejected, superseded, or only partially delivered,
   leave an explanatory comment and use the corresponding Issue disposition;
   never report a candidate as completed merely because a branch or pull
   request existed.

Completion criterion: every implemented candidate is traceable from its source
Issue to the merged pull request, and the Issue has a verified final state with
an implementation or non-completion explanation.

## Add or migrate the skill

1. Synchronize both source and destination repositories without overwriting
   local work.
2. Create `skills/<skill-name>/SKILL.md`. Keep only `name` and `description` in
   its YAML frontmatter, and make the folder name match `name`.
3. Put deterministic helpers in `scripts/`, agent-facing detail in
   `references/`, output material in `assets/`, and optional UI metadata in
   `agents/openai.yaml`. Keep project configuration outside the skill folder.
4. Write imperative steps with checkable completion criteria. Keep the body
   below 500 lines; disclose branch-specific detail through direct references.
5. Add one entry to `skill-catalog.json`:
   - `name` and repository-relative `path`;
   - exactly one primary `category`, following the documented priority order;
   - one or more controlled `tags` for lifecycle phase, scope, behavior, and
     integrations;
   - `status`: `experimental`, `stable`, or `deprecated`;
   - GitHub handles in `maintainers`;
   - supported `platforms`;
   - SPDX expression in `license`;
   - provenance kind, source, previous names, and canonical repository.
   Validate category and tag values against
   `schemas/skill-catalog.schema.json`; maturity status is independent of both.
6. Add the skill to the README catalog with its purpose, installation notes,
   and required first-run action.
7. Add tests for deterministic scripts and realistic prompts that should and
   should not trigger the skill. Store at least three positive and three nearby
   negative cases in `evals/<skill-name>.json`, and reference that file from
   `skill-catalog.json` as `trigger_evals`.

For a migrated skill, preserve its history in the catalog even after this
repository becomes canonical. For a vendored skill, record an immutable source
revision, keep its license and notices in the skill folder, and keep upstream
changes separate from local patches. Confirm license compatibility before
combining third-party content with Apache-2.0 content.

Completion criterion: a reader can determine where the skill came from, who
owns it, how it is licensed, where it runs, and how to validate it.

## Configuration contract

Every configurable skill declares a `configuration` object in
`skill-catalog.json` and follows these rules:

- `configure` is an argv array, is safe to repeat, preserves unrelated project
  content, and reports no change on an identical second pass;
- `status` is read-only, supports machine-readable JSON, exits zero only when
  the declared configuration is present and valid, and never prints secrets;
- project and user scope are explicit; configuration remains outside the
  installed skill directory;
- JSON and YAML configuration has a positive integer version, a bundled JSON
  Schema describing its decoded document, and a fail-closed migration command;
- managed text uses paired, skill-specific markers, rejects malformed or
  duplicate markers, and does not rewrite text outside its block.
- stateless skills use format `none`, expose only a read-only status command,
  and must not invent placeholder configuration artifacts.

Commands are stored as arrays rather than shell strings. Use placeholders such
as `<project-root>` for caller-supplied values and never put credentials in a
catalog command. Keep migration steps incremental and idempotent; reject a
newer unknown version instead of guessing how to downgrade it.

Completion criterion: repeated configure produces byte-identical output where
configuration exists, status performs no writes, migrations preserve supported
input, and tests cover missing, malformed, current, and legacy configuration.

## Preserve the consumer update path

- Keep `.codex-plugin/plugin.json`, `.claude-plugin/plugin.json`,
  `skill-catalog.json.collection_version`, and every
  `skills/*/collection-metadata.json` version identical in a release.
- Test copied installation and an update from the oldest supported previous
  release through the pinned `skills` CLI for both `codex` and `claude-code`.
- Keep project/user configuration outside installed skill folders. Never make
  an updater silently create configuration for an unused skill.
- Document required migrations and rollback limitations in the README and
  changelog. Treat configuration downgrade as unsupported unless tested.
- Preserve unrelated entries when changing the personal marketplace. Apply one
  cachebuster suffix to the installed plugin copy and require a new Codex task
  after activation.

Completion criterion: a consumer can identify installed versions, update,
migrate existing configuration, diagnose mixed versions, and reinstall a prior
tag without relying on repository-private knowledge.

## Preserve cross-agent behavior

Keep shared `SKILL.md` instructions and helpers portable. Codex remains the
default for existing command-line interfaces; an explicit Claude Code target
uses `.claude/skills`, `CLAUDE.md`, and `/skill-name`. Do not replace existing
`.agents` configuration APIs merely to rename them for another consumer.

Treat `agents/openai.yaml` as OpenAI UI metadata and `.codex-plugin` as Codex
packaging. Claude packaging belongs under `.claude-plugin`; neither manifest may
silently stand in for the other's validation. When an agent lacks a capability
such as Codex Desktop task enumeration, report that bounded operation as
unsupported while preserving the portable subset.

Completion criterion: both consumer installs contain identical skill payloads,
their native project rule and skill layouts are respected, Codex defaults are
unchanged, and consumer-smoke evidence names both agents explicitly.

## Compose skills by capability

Declare small capability names in `provides`, mandatory prerequisites in
`requires`, and non-blocking integrations in `optional_integrations`. Add a
named collection composition only for a recurring workflow with at least two
skills. Its `required_steps` are ordered; `optional_steps` run only when the
project or user has enabled their capability.

Do not copy one skill's workflow into another. Invoke the prerequisite skill,
consume its observable completion result, and stop when a required capability
is unavailable. Optional notification or logging must never turn a successful
primary operation into a false success, nor conceal its failure.

Completion criterion: every required capability has a provider, composition
steps reference existing skills once, and the order has an integration test or
an executable completion criterion.

## Manage lifecycle status

- Keep a new or materially redesigned skill `experimental` until its metadata,
  deterministic helpers, cross-platform tests, development trigger corpus,
  independent forward-test, copied-install smoke test, and release holdout have
  all passed. Requirements that do not apply, such as bundled scripts for a
  prose-only workflow, may be recorded as not applicable.
- Mark a skill `stable` only in a versioned collection release. Add
  `stable_since` with that release version. Stable means documented inputs,
  configuration locations, safety boundaries, and CLI behavior will remain
  compatible within the current collection major version or receive migration
  guidance.
- Mark a skill `deprecated` before removal. Name its supported replacement or
  migration path in the skill and changelog, and retain it for at least one
  minor release unless an urgent safety issue requires earlier removal.

Completion criterion: lifecycle status is backed by observable validation and
communicates a clear compatibility expectation.

## Preserve installed provenance

Treat a known skill name only as a candidate, never as collection identity.
Correlate the external lock source with installed `collection-metadata.json`.
Normalize supported GitHub spellings to `https://github.com/kolabse/skills`;
verify local development sources from their plugin manifest, catalog, and
requested skill content without depending on the checkout directory name.

Fail closed on a same-name skill from another source or contradictory metadata.
Keep legacy adoption explicit and allow it only when the lock source itself is
verified; successful adoption must end with current metadata and a healthy
post-update diagnosis.

Completion criterion: status exposes the provenance classification, update
selects only verified skills (or explicitly adopted legacy skills), and tests
cover source collisions, release refs, renamed local checkouts, and legacy
installations.

## Keep consumer automation inspectable

Keep `plan` read-only: it must not invoke installers, migrations, or network
operations. Publish versioned JSON Schemas for plan and result payloads and
distinguish unchanged, updated, migrated, skipped, blocked, and failed states
without parsing human-oriented CLI output.

Bound global discovery to documented lock and installation roots. Do not scan
the home directory for possible installations. Apply the same provenance,
explicit selection, and post-update diagnosis rules at global scope.

The standalone bootstrap must verify the archive checksum before extraction,
verify GitHub build provenance before execution, reject traversal and symlink
archive entries, use a temporary directory, and propagate the manager exit
code. Keep unattested offline execution behind an explicit degraded-mode flag.

Completion criterion: schemas parse, dry-run leaves byte-identical fixtures,
global fixtures cover supported and ambiguous layouts, and the bootstrap smoke
passes on every supported CI operating system.

## Validate the change

Run:

```shell
python scripts/validate_skills.py
python scripts/validate_localizations.py
python -m unittest discover -s tests -v
npx skills@1.5.22 add . --list
python scripts/smoke_install.py --agent codex
python scripts/smoke_install.py --agent claude-code
```

Exercise the trigger corpus against an actual agent, including the skill's
first-run path. Structural CI checks keep the corpus complete, but do not
substitute for observing model invocation. Include the prompts and observed
result in the pull request.

For collection-wide trigger evaluation, prepare a blind suite and score the
selector observations:

```shell
python scripts/trigger_evals.py prepare --output .trigger-evals/suite.json
python scripts/trigger_evals.py score \
  --predictions .trigger-evals/predictions.json \
  --json-output .trigger-evals/report.json \
  --markdown-output .trigger-evals/report.md
```

Selectors may choose multiple skills or none. Do not expose the source eval
files, expected labels, author reasons, suspected failures, or prior reports to
the selector. Record provider/model identity in the prediction metadata, keep
raw predictions with the review evidence, and inspect each false positive and
false negative before changing a description. A higher score is not sufficient
reason to broaden a trigger when that would make nearby workflows ambiguous.

Treat `evals/release-holdout-vN.json` as append-only release evidence. Do not
read or run the active holdout while tuning descriptions. Existing holdout
versions are immutable: create `vN+1`, update the catalog name, path, and
canonical digest, and retain every published version. Run the active holdout
only after the candidate descriptions are frozen, then compare its report with
a baseline generated from the same holdout version and selector configuration.
Never compare reports with different assertion digests. After release, retain
the accepted report under `evals/baselines/` and update the catalog baseline
pointer; baseline files are release evidence and must not be rewritten.
When the selector is nondeterministic, use an odd number of at least three
independent blind runs and compare the majority-vote aggregate. Do not rerun a
single observation until it passes or discard valid failed observations.

Completion criterion: every command passes on each supported operating system,
and the pull request checklist contains evidence for the affected skill.

## Protect the release chain

- Pin every external GitHub Action to a full commit SHA and retain its release
  version in a comment. Let Dependabot propose reviewed SHA updates.
- Grant each workflow only its required `GITHUB_TOKEN` permissions.
- Build release archives through `scripts/build_release.py`; verify
  `SHA256SUMS` before uploading assets.
- Publish GitHub artifact attestations for every release asset and verify them
  with `gh attestation verify <artifact> --repo kolabse/skills`.
- Never replace an existing release asset. A repeated workflow run must verify
  that the published bytes are identical or fail.
- Keep version tags immutable. Publish a correction as a new version instead
  of moving an existing tag or replacing its source commit.

Completion criterion: the tag resolves to the reviewed commit, the uploaded
assets match `SHA256SUMS`, and workflow dependencies are immutable references.
