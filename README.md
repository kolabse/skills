# kolabse/skills

Reusable agent skills maintained by kolabse.

Licensed under the [Apache License 2.0](LICENSE). Copyright 2026 kolabse.

## Install skills

Install one or more skills into the current project with the cross-agent
[`skills`](https://skills.sh) CLI:

```shell
npx skills@latest add kolabse/skills
```

The CLI discovers the folders under `skills/`, lets you select which skills to
install, and copies them to the selected coding agents. It is an external
installer; this repository does not publish or execute its own npm package.

Codex users can alternatively ask `$skill-installer` to install a skill from
this repository, for example from:

```text
https://github.com/kolabse/skills/tree/main/skills/operate-yandex-cloud
```

The repository is also packaged as the skills-only `kolabse-skills` plugin for
ChatGPT and Codex. Its manifest is in [`.codex-plugin/plugin.json`](.codex-plugin/plugin.json),
and every folder under `skills/` is included in the plugin. The cross-agent
`npx skills` installation remains available independently of the plugin.

## Update installed skills

The `skills` CLI records the GitHub source and a content hash in
`skills-lock.json`. Update every project installation from its recorded source:

```shell
npx skills@1.5.22 update -p -y
```

Update one skill or global installations with:

```shell
npx skills@1.5.22 update verify-before-push -p -y
npx skills@1.5.22 update -g -y
```

An unqualified `kolabse/skills` lock follows the repository's default branch;
it does not pin a collection release. Do not edit copied files under
`.agents/skills/` because update may replace them. Project and user
configuration remains outside installed skill folders.

From a cloned checkout or release archive, update and migrate supported project
configuration in one explicit operation:

```shell
python scripts/manage_installed_skills.py update --project-path . --yes --migrate
python scripts/manage_installed_skills.py doctor --project-path . --json
```

Preview the exact selection without invoking the external installer or changing
configuration:

```shell
python scripts/manage_installed_skills.py plan --project-path . --json
```

The plan reports source identity, current and target versions, provenance,
migration candidates, and `update`, `unchanged`, `adopt-and-update`, or
`blocked` actions. Its schema is `schemas/manager-plan.schema.json`. Add
`--json` to `update`; update and migrate outcomes follow
`schemas/manager-result.schema.json`.

With no names, the manager resolves the installed kolabse skills from the
project lock and passes those names explicitly to the external CLI; unrelated
project skills are never part of the update. Global updates require explicit
collection skill names. Project updates finish with the same fail-closed
diagnosis as `doctor`.

Add `--include-user-config` only when the Telegram user configuration should be
migrated too. `status` and `doctor` are read-only. `migrate` changes only
configuration files that already exist; it does not configure unused skills.
Each installed skill carries `collection-metadata.json`, so `status` reports its
collection version even though the external lock format has no version field.
It also reports `provenance_status`: `verified` requires both collection
metadata and a canonical GitHub or content-verified local lock source;
`legacy-unverified` identifies a pre-metadata installation; `mismatch` is never
updated. A checkout may be renamed because local identity comes from its plugin
manifest, catalog, and skill contents rather than the directory name.

Adopt a pre-v1.2 metadata-free installation only after reviewing its reported
source:

```shell
python scripts/manage_installed_skills.py status --project-path . --json
python scripts/manage_installed_skills.py update --project-path . --yes --adopt-legacy
```

The adoption flag does not bless arbitrary files: the source must already
normalize to `kolabse/skills` or pass local checkout validation, and the normal
post-update diagnosis must verify the installed metadata.
The external CLI does not update `sourceType: local` development locks in
place. The manager treats that CLI no-op as a failure; re-add those skills from
their local source with the original `--skill` and `--agent` selections.

### Run without cloning the repository

Download `scripts/bootstrap_update.py` from a trusted release or this
repository, then let it resolve the latest stable release, verify the release
ZIP against `SHA256SUMS` and GitHub build provenance, and run the manager from
an isolated temporary extraction:

```shell
python bootstrap_update.py doctor --json
python bootstrap_update.py plan --json
python bootstrap_update.py update --yes --migrate --json
```

Use `--release v1.12.0` to pin a version. The bootstrap requires `gh` for
attestation verification and removes its temporary directory on completion.
For an offline cache, provide both `--offline-archive` and
`--offline-checksums`. Provenance verification remains required when `gh` can
reach GitHub. `--allow-unattested-offline` is an explicit degraded mode: it
verifies only the cached checksum and should be used only for artifacts moved
through an independently trusted channel. Roll back by selecting an older
release and using the existing rollback procedure; configuration migrations
remain forward-only.

### Inspect global installations

The supported global layout is deliberately bounded to
`~/.agents/.skill-lock.json` v3 and `~/.agents/skills`; the manager does not
scan other user directories:

```shell
python scripts/manage_installed_skills.py status --scope global --json
python scripts/manage_installed_skills.py doctor --scope global --json
python scripts/manage_installed_skills.py plan verify-before-push --scope global --json
python scripts/manage_installed_skills.py update verify-before-push --scope global --yes --json
```

Use `--global-root` for read-only inspection of a test or explicitly relocated
compatible layout. Relocated roots cannot be updated because the external CLI
cannot target them. Unknown or ambiguous layouts are reported without mutation.

To roll back skill files, first back up project/user configuration, then
reinstall the required release tag with the same skills and agent targets used
for the original installation, for example:

```shell
npx skills@1.5.22 add kolabse/skills@v1.1.0 --skill verify-before-push --agent codex --copy -y
```

Configuration migrations are forward-only unless a release explicitly
documents a downgrade. Restoring older skill files does not downgrade config;
restore the matching configuration backup when the older release cannot read
the newer format.

## Install or update the personal Codex plugin

From a cloned checkout or release archive, create/update the default personal
marketplace entry, copy the plugin to the local plugin directory, add a Codex
cachebuster, and activate it:

```shell
python scripts/install_personal_plugin.py --activate
```

The installer preserves other personal marketplace entries. It does not edit
the repository manifest. Run it again after updating the checkout, then start a
new Codex task so the updated skills are loaded. Use `--json` to record the
installed version, plugin path, marketplace path, and marketplace name.

## Available skills

Stable skills and experimental additions are identified in `skill-catalog.json`.
Their project-facing configuration paths, safety boundaries, and documented
command interfaces follow the compatibility policy in
[CONTRIBUTING.md](CONTRIBUTING.md).

Each catalog entry now declares its configuration scope, read-only JSON status
command, capabilities, prerequisites, and optional integrations. Stateful
skills also declare an idempotent configure command; versioned JSON/YAML
configurations publish a JSON Schema and migration command next to the skill.

### `discover-skill-candidates` (experimental)

Find reusable skill ideas in bounded project and contextual evidence without
creating a skill.

**What it does:**

- inventories bounded project-relative `AGENTS.md` files with Git and
  line-level provenance;
- optionally inventories project documentation, selected files, bounded Git
  history, structure metadata, and user-confirmed summaries from available
  chats or `sync-project-context` handoffs;
- ranks candidates as recommended, investigate, or rejected and compares them
  with existing catalogs;
- exports a selected idea as a sanitized, digest-bound contribution package
  that maintainers can validate independently.

**What it does not do:**

- modify project rules or scaffold, publish, or install a skill;
- enumerate chats, ingest raw transcripts, or broadly scan source code;
- export raw rules, local paths, secrets, URLs, or email addresses;
- promote policy-only, volatile, sensitive, or one-off conventions as reusable
  workflows without review.

**How to invoke it:**

```text
$discover-skill-candidates Analyze this project's local rules and prepare an evidence-backed backlog of reusable skill ideas without creating anything.
```

### `release-skill-collection`

Plan, verify, audit, and clean up deterministic skill-collection releases.

**What it does:**

- checks versions, changelog readiness, repository state, tests, security,
  deterministic archives, and checksums;
- validates commit-bound holdout, consumer, platform, review, and local-check
  evidence;
- audits immutable GitHub assets, manifests, checksums, and attestations;
- proves whether temporary branches are merged, identical-tree, or
  patch-equivalent before cleanup;
- applies an explicitly confirmed cleanup only from an unchanged safe plan and
  a digest-valid audit of the published release.

**What it does not do:**

- infer permission to commit, tag, push, dispatch workflows, or publish assets;
- move an existing tag or replace published assets;
- delete branches from names alone, a stale plan, or an unaudited release.

**How to invoke it:**

```text
$release-skill-collection Plan and verify release vX.Y.Z of this skill collection, but do not publish it yet.
```

### `verify-before-push`

Bind project-declared checks to the exact Git state being pushed.

**What it does:**

- configures a repository-owned verification policy outside the installed
  skill folder;
- runs declared checks and records evidence for exact commits, worktrees,
  upstream state, and verification configuration;
- fails closed when protected evidence is missing, failed, malformed, or stale.

**What it does not do:**

- block unrelated repositories that are not covered by the policy;
- parse arbitrary shell commands or install an IDE- or agent-specific hook;
- treat a successful check from an older Git state as current evidence.

**How to invoke it:**

```text
$verify-before-push Configure this project's verification policy and checks.
```

### `synchronize-git-repositories`

Establish current remote state without overwriting local work.

**What it does:**

- discovers only task-relevant repositories and fetches their tracked remotes;
- fast-forwards clean behind-only branches;
- reports dirty, ahead, diverged, detached, untracked, and in-progress states;
- publishes an authorized feature branch from verified current `main` before
  the first edit when project policy requires it.

**What it does not do:**

- automatically stash, reset, rebase, merge, clean, switch, or force-push;
- hide divergence or treat a successful fetch as proof that the local branch
  was updated;
- scan or update unrelated repositories.

**How to invoke it:**

```text
$synchronize-git-repositories Configure this project's repository synchronization policy.
```

### `maintain-work-log`

Maintain the canonical dated project journal at `docs/reports/work-log.md`.

**What it does:**

- records material changes, operations, diagnostics, decisions, verification,
  blockers, and rollback results;
- preserves the project's existing journal format;
- reconstructs missing history from available Git and project-task evidence.

**What it does not do:**

- activate for ordinary work unless project policy or the user requires it;
- write secrets, application logs, time tracking, or personal notes;
- claim events that cannot be supported by available evidence.

**How to invoke it:**

```text
$maintain-work-log Configure this project to maintain its dated work log.
```

### `maintain-project-digest` (experimental)

Maintain a daily, user-facing digest of completed project changes in the
project documentation.

**What it does:**

- groups completed changes under today's date as new capabilities,
  improvements, fixes, security, documentation, or important behavior changes;
- writes short nontechnical outcomes and omits empty categories;
- keeps newest dates first and leaves every earlier date unchanged;
- uses a content-bound plan, cooperative lock, atomic replacement, and
  duplicate detection so several developers can safely contribute in one day.

**What it does not do:**

- choose or create a documentation location when the project does not identify
  one unambiguously;
- record plans, failed experiments, internal implementation activity, or
  unsupported user benefits;
- replace the technical work log, version release notes, or a conventional
  changelog;
- rewrite historical digest periods during an ordinary same-day update.

**How to invoke it:**

```text
$maintain-project-digest Add today's completed user-visible changes to the project digest.
```

### `notify-via-telegram`

Send lifecycle updates for long-running agent tasks through Telegram.

**What it does:**

- reports starts, milestones, intermediate results, problems, blockers, and
  completion;
- interactively validates the bot and helps discover a destination chat;
- provides a masked, paste-friendly first-use form for Codex Desktop on Windows;
- stores credentials in the user configuration directory and sends a test
  notification during setup;
- supports a separate chat or forum topic per project, with an explicit choice
  between global-plus-project delivery and project-only delivery;
- exports secret-free project routing values for reconciliation through
  `sync-project-context`;
- runs with the Python 3 standard library on Windows, macOS, and Linux.

**What it does not do:**

- place the bot token in the conversation, shell history, or repository;
- copy the global bot token or Telegram authentication state between computers;
- send notifications when the user asks to keep progress in the current task;
- act as a general Telegram bot-development framework.

**How to invoke it:**

```text
$notify-via-telegram Configure Telegram notifications for long tasks.
$notify-via-telegram Configure this project to notify its team chat only, instead of the global destination.
```

### `operate-yandex-cloud`

Operate explicitly configured, project-scoped Yandex Cloud infrastructure.

**What it does:**

- stores shared Cloud/Folder IDs in project configuration and the workstation
  `yc` profile in ignored local configuration;
- detects required toolsets, checks minimum versions, and runs a read-only
  context preflight;
- supports scoped CLI, SSH, Terraform, Ansible, Helm, Kubernetes, deployment,
  database, storage, DNS, monitoring, backup, and incident workflows;
- provides JSON output and cross-platform Python helpers.

**What it does not do:**

- infer Yandex Cloud from generic SSH, Kubernetes, Terraform, or deployment
  requests without provider context;
- store credentials in shared project configuration;
- apply a mutation before target, context, and authorization are established.

**How to invoke it:**

```text
$operate-yandex-cloud Configure this project for Yandex Cloud operations.
```

### `sync-project-context`

Synchronize private, sanitized project and per-chat continuation state between
computers. The skill remains experimental while its cross-device behavior is
evaluated independently.

**What it does:**

- stores immutable checkpoints in an approved synchronized folder or connected
  Google Drive, with machine-local configuration outside the repository;
- keeps one opaque stream per project task: a detailed baseline followed by
  short deltas, exact visible titles, decisions, verification, open questions,
  next steps, and Git fingerprints;
- saves, restores, or bidirectionally plans all recent and pinned project tasks,
  while skipping unchanged/active tasks and surfacing conflicts explicitly;
- validates downloaded snapshots, reads uploads back, prevents cross-project
  restore, and rejects high-confidence secret patterns;
- records a separate environment manifest for declared rules, skills, plugins,
  and safe scalar settings that Git does not already provide.

**What it does not do:**

- copy source files, diffs, raw transcripts, hidden reasoning, credentials,
  OAuth tokens, or skill/plugin installations;
- duplicate rules or dependencies already carried by Git;
- silently overwrite Git-owned destination rules: apply may only create a
  missing untracked `AGENTS.md` after an explicit plan;
- include branch names or file paths in metadata-only mode; visible task titles
  remain intentionally included.

**How to invoke it:**

Configure each computer once:

```text
$sync-project-context Configure this clone in metadata-only mode using my approved local synchronized folder or connected Google Drive.
```

Then use task-level or batch commands, for example:

```text
$sync-project-context Save the current task state.
$sync-project-context Restore all project tasks on this computer.
$sync-project-context Synchronize all project tasks bidirectionally and show conflicts before applying changes.
```

## Supported compositions

The catalog defines three reusable ordered workflows:

- `protected-push`: synchronize repositories, then produce current
  verification evidence; work logging and Telegram notification are optional.
- `yandex-cloud-operation`: synchronize repositories, then run the scoped cloud
  operation; verification, work logging, and Telegram notification are
  optional when project policy enables them.
- `skill-collection-release`: synchronize the repository, plan and locally
  verify the collection release, then bind pre-push evidence; work logging and
  Telegram notification are optional.

Required steps fail closed. Optional logging and notification report their own
failure without changing the observed result of the primary operation. Resolve
an exact plan with `scripts/compose_skills.py`; pass `--evidence` with a
digest-bound document matching `schemas/composition-evidence.schema.json` to
verify step order, required results, and non-blocking optional failures. The
verified result follows `schemas/composition-result.schema.json`.

## Add a skill

Follow [CONTRIBUTING.md](CONTRIBUTING.md) and start from
[`templates/skill-template.md`](templates/skill-template.md). Every skill must
have a matching `skill-catalog.json` entry that records its owner, platforms,
status, license, and provenance. Keep project-specific configuration outside
the installed skill folder so updates cannot overwrite it.

Do not add a repository-level installer for an individual skill. When the
collection needs managed installation and updates across ChatGPT and Codex,
package the collection as an OpenAI plugin in addition to this cross-agent
layout.

Run the collection checks locally with:

```shell
python scripts/validate_skills.py
python -m unittest discover -s tests -v
npx skills@1.5.22 add . --list
python scripts/smoke_install.py
```

Prepare a blind trigger suite for an agent or model selector with:

```shell
python scripts/trigger_evals.py prepare --output .trigger-evals/suite.json
```

The suite contains only skill names, public descriptions, opaque case IDs, and
prompts. It omits expected labels and author reasons. A selector returns strict
JSON listing every selected skill for each case; score the observations with:

```shell
python scripts/trigger_evals.py score \
  --predictions .trigger-evals/predictions.json \
  --json-output .trigger-evals/report.json \
  --markdown-output .trigger-evals/report.md
```

Use `run` with a command after `--` to invoke a selector that reads the suite
from standard input and writes predictions to standard output. Keep provider
credentials outside command arguments. The ignored `.trigger-evals/` directory
keeps generated suites, predictions, and reports out of commits by default.

Before a release, run the separately versioned and digest-locked holdout without
using it to tune descriptions during development:

```shell
python scripts/trigger_evals.py prepare \
  --corpus release-holdout \
  --output .trigger-evals/release-holdout.json
```

Compare a candidate report with a report produced for the same holdout version:

```shell
python scripts/trigger_evals.py compare \
  --candidate .trigger-evals/candidate-report.json \
  --markdown-output .trigger-evals/comparison.md
```

Comparison fails closed when assertion digests differ or overall accuracy,
precision, recall, or a per-skill metric drops beyond the configured limits.
By default it uses the published baseline named by `skill-catalog.json`; pass
`--baseline` only when intentionally comparing with another compatible report.

For model selectors that are not deterministic, collect an odd number of at
least three blind prediction runs and score their majority decision:

```shell
python scripts/trigger_evals.py aggregate \
  --corpus release-holdout \
  --predictions run-1.json run-2.json run-3.json \
  --predictions-output .trigger-evals/aggregate.json \
  --json-output .trigger-evals/candidate-report.json
```

## Verify a release

Versioned releases include deterministic ZIP and TAR.GZ archives,
`release-manifest.json`, and `SHA256SUMS`. Download all four assets into one
directory and verify them with:

```shell
python scripts/build_release.py --verify <download-directory>/SHA256SUMS
```

GitHub also exposes a SHA-256 `digest` for every uploaded release asset.
Release workflows additionally publish GitHub artifact attestations. Verify a
downloaded artifact against this repository with:

```shell
gh attestation verify <artifact> --repo kolabse/skills
```
