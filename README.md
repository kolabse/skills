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

Use `--release v1.6.0` to pin a version. The bootstrap requires `gh` for
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
failure without changing the observed result of the primary operation.

### `release-skill-collection` (experimental)

Plan and locally verify deterministic skill-collection releases without
implicitly committing, tagging, pushing, dispatching a workflow, or publishing
assets. The skill checks version alignment, changelog readiness, repository
state, structural and security gates, unit tests, release archives, and
checksums while keeping model-backed holdout, consumer, supported-platform,
and attested publication evidence explicit.

### `verify-before-push`

Run project-declared checks and record evidence bound to the exact Git commits,
worktrees, upstream state, and verification configuration being pushed.

After installing it in a project, invoke it once with:

```text
$verify-before-push Configure this project's verification policy and checks.
```

The skill stores committed configuration outside its installed folder, keeps
generated evidence ignored, supports multiple repositories and commands, and
fails closed for configured repositories when evidence is missing, malformed,
failed, or stale. Its gate mode leaves unrelated repositories unaffected and
does not attempt to parse shell commands or install a product-specific hook.

### `synchronize-git-repositories`

Safely synchronize every Git repository involved in a task without overwriting
local work or rewriting history.

After installing it in a project, invoke it once with:

```text
$synchronize-git-repositories Configure this project's repository synchronization policy.
```

The skill preserves existing `AGENTS.md` instructions, discovers only
task-relevant repositories, fetches their tracked remotes, applies clean
fast-forward updates, and reports dirty, ahead, diverged, detached, or
untracked states without automatically stashing, resetting, rebasing, merging,
cleaning, switching branches, or force-pushing.

### `maintain-work-log`

Maintain a dated, chronological record of project changes, operations,
diagnostics, discussions, decisions, verification, blockers, and rollback
results in `docs/reports/work-log.md`.

After installing it in a project, invoke it once with:

```text
$maintain-work-log Configure this project to maintain its dated work log.
```

The skill adds or preserves a repository-level `AGENTS.md` policy so future
tasks invoke it, follows the project's existing journal format, keeps secrets
out of entries, and offers evidence-based reconstruction for non-empty projects
with missing history. Reconstruction uses Git and only the project conversation
history that is actually available to the agent.

### `notify-via-telegram`

Send concise Telegram notifications when long-running agent tasks start,
advance, produce intermediate results, encounter problems, become blocked, or
finish.

After installing it, invoke it once with:

```text
$notify-via-telegram Configure Telegram notifications for long tasks.
```

The skill opens an interactive first-run setup so the bot token does not enter
the conversation or shell history. It validates the bot, helps discover the
destination chat from a recent `/start` or group command, stores credentials in
the user's configuration directory outside the installed skill, and sends a
test notification. Its Python 3 helper uses only the standard library and runs
on Windows, macOS, and Linux.

### `operate-yandex-cloud`

Safely operate project-scoped Yandex Cloud infrastructure.

After installing it in a project, invoke it once with:

```text
$operate-yandex-cloud Configure this project for Yandex Cloud operations.
```

The skill asks for the project's Cloud ID, optional default Folder ID and
optional `yc` profile. It stores shared Cloud/Folder IDs in
`.agents/operate-yandex-cloud/project.yaml` and the workstation-specific
profile in an ignored `local.yaml`. It detects required toolsets from the
project, checks minimum tool versions, offers supported installations, and runs
a read-only cloud-context preflight. The scripts support JSON output and run on
Windows, macOS, and Linux with Python 3; PowerShell wrappers are included for
Windows compatibility.

### `sync-project-context`

Save and restore private, sanitized project and per-chat continuation state
between computers without adding context files to the team repository. It can
also reconcile explicitly declared project rules, skills, plugins, and safe
settings that are not already carried by Git. The skill is experimental while
its cross-device trigger and storage behavior is
evaluated independently.

After installing it on each computer, invoke it first with:

```text
$sync-project-context Configure this clone in metadata-only mode using my approved local synchronized folder or connected Google Drive.
```

The dependency-free helper stores machine-local configuration in the user's
configuration directory and immutable checkpoints through either an approved
local synchronized folder or the optional Google Drive plugin. Independent
opaque streams let each project chat keep a detailed first baseline followed by
short incremental updates, so repeated "save state" and "restore state"
requests can continue several implementation tracks across computers without
mixing them. In the desktop app, an explicit "save all project chats" command
can discover the 50 most recent non-pinned tasks plus all pinned tasks, create
baselines for new workstreams, append deltas only to changed workstreams, and
skip unchanged or active tasks. A machine-local hashed registry prevents
duplicate streams without storing task titles or transcripts. The matching
"restore all project chats" command resolves the destination local project by
its canonical path, creates one project task per missing saved stream, updates
an existing bound task when a newer delta arrives, and skips already-current
tasks without importing raw transcripts. The connector backend validates a
complete downloaded snapshot locally and reads uploads back before success.
Exact visible chat titles are stored as scanned metadata and restored without
semantic regeneration. The unified "sync all project chats" command plans
local saves, remote creates or updates, unchanged skips, and explicit conflicts
in one bidirectional pass on the active computer. It records reviewed summaries,
factual rationale, discussion outcomes, decisions, actions, verification,
questions, next steps, and Git fingerprints; it never copies source contents,
diffs, raw transcripts, or hidden reasoning. A separate immutable environment
manifest records Git coverage without duplicating tracked content, may carry
only reviewed untracked `AGENTS.md` text and scalar preferences, and declares
skill/plugin versions without copying installations or credentials. Its
read-only plan preserves Git and existing destination rules; explicit apply
can create only a missing untracked `AGENTS.md`. Metadata-only mode also omits
branch names and file paths; chat titles remain intentionally included.
Configuration requires an explicit storage-policy acknowledgement, repository
fingerprints prevent cross-project restore, and high-confidence secret patterns
fail closed.

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
