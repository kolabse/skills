# Project environment reconciliation

Use this workflow only for project requirements that may not be carried by
Git. Git remains authoritative. Absence from Git is necessary but is not by
itself permission to transfer an item.

## Supported boundary

The environment manifest may contain:

- explicitly selected project-relative `AGENTS.md` or `CLAUDE.md` files that are not tracked
  by Git, limited to 32 KiB of reviewed UTF-8 text;
- tracked `AGENTS.md` or `CLAUDE.md` coverage records containing only path, Git blob, and
  commit identifiers;
- skill and plugin identifiers, versions, canonical source identifiers, and
  optional SHA-256 digests;
- small schema-versioned scalar preferences that contain no credential-like
  keys or detected secrets.

Never capture arbitrary files, installed skill or plugin directories, OAuth
state, tokens, sessions, cookies, machine paths, private repository URLs, or
system and organization policy. A plugin connection is recreated interactively
on every computer. Settings are materialized only through the owning
component's schema-aware interface; this helper never writes them directly.

Chat and topic identifiers can reveal team or organization structure. Obtain
explicit approval for the chosen storage before capturing notification routing.

## Inspect and capture

Create a reviewed input outside the project:

```json
{
  "rules": [
    {"id": "project-rules", "path": "CLAUDE.md", "scope": "project"}
  ],
  "skills": [
    {"id": "sync-project-context", "source": "kolabse-skills", "version": "1.8.0", "required": true, "declaration_path": "plugin.json"}
  ],
  "plugins": [
    {"id": "google-drive", "version": "0.1.11", "required": true}
  ],
  "settings": [
    {"id": "project-preferences", "scope": "project", "schema_version": "1", "preferences": {"mode": "safe"}, "required": true}
  ]
}
```

Run the read-only classifier first:

```shell
python <skill-root>/scripts/environment_sync.py inspect \
  --project-path <project-root> --input <reviewed-json> --json
```

It classifies a clean tracked rule as `satisfied_by_git` and omits its content.
It rejects tracked rules with unpublished changes. Only an explicitly listed,
untracked regular `AGENTS.md` or `CLAUDE.md` becomes `local_portable`.

For a skill, plugin, or setting, optionally provide `declaration_path`. A clean
tracked declaration becomes Git coverage and the requirement is not duplicated
in portable content. An absent or untracked declaration leaves the sanitized
requirement in the manifest. A modified tracked declaration blocks capture.

After reviewing the output and storage policy, append an immutable manifest:

```shell
python <skill-root>/scripts/environment_sync.py capture \
  --project-path <project-root> --input <reviewed-json> \
  --acknowledge-environment-policy --json
```

Concurrent manifest heads require separate review and a reconciled capture
with `--merge-heads`. Never select one merely by timestamp.

### Project Telegram routing

`notify-via-telegram` exports a known version 1 project setting containing only
`delivery_mode`, `chat_id`, and optional `message_thread_id`. Generate the input
outside the repository instead of transcribing it:

```shell
python <notify-skill-root>/scripts/telegram_notify.py project-export \
  --project-path <project-root> > <reviewed-json-outside-project>
```

Inspect and capture that file through the commands above. The environment
helper validates both supported modes (`global-and-project` and `project-only`)
and rejects extra fields, including `bot_token`. Never synchronize the global
sender token or Telegram authentication state.

## Plan and apply on another computer

After Git and the storage snapshot are current, run:

```shell
python <skill-root>/scripts/environment_sync.py plan \
  --project-path <project-root> --json
```

Optionally pass `--local-state <json-outside-project>` with installed skill,
plugin, connection, and setting digests. Treat it as observed state, not as an
installation request. The plan uses these statuses:

- `satisfied_by_git` or `satisfied_locally`: no action;
- `apply_local_rule`: a missing untracked rule may be created;
- `install_required`: install from the declared canonical source and verify
  provenance;
- `manual_apply_required`: use the owning component's safe settings interface;
- `approval_required`: reconnect interactively or resolve a conflict.

Apply only reviewed missing rules:

```shell
python <skill-root>/scripts/environment_sync.py apply \
  --project-path <project-root> --approve-local-rules --json
```

The helper creates only absent, untracked `AGENTS.md` or `CLAUDE.md` files with exclusive
creation. It never overwrites an existing or Git-owned rule. Re-run `plan`
after installing skills, plugins, or settings through their own tools.

For project Telegram routing, run `project-configure` from the notification
skill with the planned chat, topic, and mode. Then export observed state with
`project-export --local-state` and pass it to `plan --local-state`; the setting
must change from `manual_apply_required` to `satisfied_locally` before treating
the destination as reconciled.

## Google Drive transport

Store environment manifests in the existing opaque project's `checkpoints`
Drive folder. Accept only files named `environment-<32 lowercase hex>.json`.
Download all of them alongside checkpoints, hydrate the checkpoint snapshot,
then add the manifests:

```shell
python <skill-root>/scripts/environment_sync.py hydrate \
  --project-path <project-root> --snapshot-root <hydrated-snapshot> \
  --environment-file <downloaded-manifest> --json
```

Repeat `--environment-file` for each manifest. After capture, upload only the
returned path, verify exact name, parent, raw bytes, and uniqueness, then
download it and run `hydrate` plus `audit` again.

## Audit

```shell
python <skill-root>/scripts/environment_sync.py status --project-path <project-root> --json
python <skill-root>/scripts/environment_sync.py audit --project-path <project-root> --json
```

Stop on repository fingerprint mismatch, missing parents, concurrent heads,
digest corruption, unexpected fields, secrets, or rule conflicts.
