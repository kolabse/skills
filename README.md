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

## Available skills

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
