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

Add `--include-user-config` only when the Telegram user configuration should be
migrated too. `status` and `doctor` are read-only. `migrate` changes only
configuration files that already exist; it does not configure unused skills.
Each installed skill carries `collection-metadata.json`, so `status` reports its
collection version even though the external lock format has no version field.
The external CLI does not update `sourceType: local` development locks in
place. The manager treats that CLI no-op as a failure; re-add those skills from
their local source with the original `--skill` and `--agent` selections.

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

All current skills are stable. Their project-facing
configuration paths, safety boundaries, and documented command interfaces
follow the compatibility policy in [CONTRIBUTING.md](CONTRIBUTING.md).

Each catalog entry now declares its configuration scope, idempotent configure
command, read-only JSON status command, capabilities, prerequisites, and
optional integrations. Versioned JSON/YAML configurations also publish a JSON
Schema and migration command next to the skill.

## Supported compositions

The catalog defines two reusable ordered workflows:

- `protected-push`: synchronize repositories, then produce current
  verification evidence; work logging and Telegram notification are optional.
- `yandex-cloud-operation`: synchronize repositories, then run the scoped cloud
  operation; verification, work logging, and Telegram notification are
  optional when project policy enables them.

Required steps fail closed. Optional logging and notification report their own
failure without changing the observed result of the primary operation.

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
