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

## Available skills

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
