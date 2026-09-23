# Telegram task bridge — capability prototype (#131)

Local MCP tools for cooperative Codex tasks. A separate receiver saves Telegram
replies in SQLite; each task explicitly polls its own inbox. The bridge does not
attach to Desktop's internal App Server, wake idle tasks, steer running turns, or
answer native questions/approval prompts. Telegram text grants no extra host permissions.

## Scope

- Six tools: `register_task`, `ask_question`, `open_instruction_slot`,
  `poll_replies`, `question_status`, `acknowledge_reply`.
- Registration returns a task id and secret. Retain both privately in that task.
  Labels should identify project/task for the human; they are not verified Desktop ids.
- Reply to the exact bot message using Telegram Reply. Plain messages are ignored.
  Each question/instruction slot accepts one reply. Open another slot when needed.
- Replies repeat until acknowledged; acknowledgment means consumed, not executed.
  This is not exactly-once execution. Questions expire after their TTL.
- Only a configured personal private chat is supported. Its owner is the sender
  allowlist. Groups, topics, forwarded messages, edits, media, callbacks are excluded.
- Existing webhooks are refused. A per-bot local lock excludes a second prototype
  receiver; a conflicting external poller produces an error and stops this receiver.
  Do not run alongside another getUpdates consumer. There is no automatic takeover.
- A delivery lock prevents a fast reply racing message-id persistence. A crash or
  network failure during sending can still leave an unknown/pending result with no
  recoverable anchor. Inspect Telegram; do not automatically resend.
- Credentials and SQLite stay outside Git. SQLite retains message text and task
  secrets are hashed. This is a local prototype, not a security boundary against
  other processes running as the same OS user. No automatic retention cleanup yet.

## Windows setup

For collection users, the normal update now delivers the receiver inside
`notify-via-telegram`. Ask the agent to update the collection and enable or update
Telegram replies; follow the installed skill's `references/task-bridge.md`.
No separate plugin or ZIP is needed for this path. Copying updated skill files
does not itself deploy or activate a receiver. The standalone packaging below
remains available for isolated prototype testing.

Maintainers: after changing prototype runtime/setup files, run
`python scripts/bundle_telegram_bridge.py` from the repository root. Collection
tests reject drift between the reviewed prototype and its shipped skill bundle.

### Experimental tester handoff

Clean-Windows acceptance was deferred by the maintainer on 2026-09-23 because
of the test VM's networking/VPN problems. This package is for voluntary testing;
see `WINDOWS-ACCEPTANCE.md` and `VALIDATION.md` for known gaps and recorded evidence.
It is separate from the stable skill-collection plugin and does not close all
requested capabilities of issue #131.

From a checkout, an agent can build a portable plugin directory:

```powershell
python prototypes/telegram_task_bridge/build_plugin.py "$env:TEMP/telegram-task-bridge"
```

The target must be empty or an existing matching plugin scaffold. The generated
directory includes its manifest, skill, setup scripts, runtime and Apache license;
it includes no credentials or message database. Register/install that directory
through Codex's supported local-plugin/personal-marketplace workflow. Then ask
the agent to run the installed plugin's `scripts/setup.ps1 install`.
Do not use the production bot on a second machine with another active poller.

Published experimental packages use tags `telegram-task-bridge-vX.Y.Z` and are
separate GitHub prereleases. Download the ZIP, `release-manifest.json` and
`SHA256SUMS` from the same release. Check the ZIP hash against `SHA256SUMS` and,
when GitHub CLI is available, verify each file with
`gh attestation verify <file> --repo kolabse/skills`. Extract the ZIP's
`telegram-task-bridge` folder and ask Codex to install that local plugin.

Maintainers build the release from a clean committed checkout using
`python scripts/build_release.py --telegram-bridge --source . --tag telegram-task-bridge-v0.1.0 --output <empty-directory-outside-repository>`.
The dedicated release workflow requires an annotated tag on integrated source
and successful main-branch CI for that exact commit before publishing assets.

### Installed plugin mode

The local `telegram-task-bridge` plugin packages this prototype, its MCP server
declaration and `telegram-bridge` skill. Receiver checks run at MCP startup;
the plugin has no lifecycle hooks. Source is
assembled reproducibly by `build_plugin.py` into a plugin-creator scaffold; only
the fixed runtime file allowlist is included. No database or credentials are bundled.

Ask in chat to install, update, or remove the receiver. The agent invokes plugin
`scripts/setup.ps1 install|update|uninstall|status` under the lifecycle mutex.
Install detects an existing Python 3.10+ interpreter, creates a private venv and
installs pinned requirements. Python itself is not downloaded automatically.
If it is absent, the agent reports the prerequisite and helps install it through
the normal host permissions; typing terminal commands is not a user requirement.
Existing notification credentials are reused. If missing, install opens a masked
Windows dialog for a BotFather token and numeric private chat ID, validates the
destination without polling/sending, and writes a restricted local config file.
Cancellation leaves existing configuration untouched. Never paste tokens in chat.

Update validates staged code and a read-only Telegram preflight before stopping
the receiver. It retains a runtime backup, preserves messages and pause state,
and restores the previous runtime if deployment or readiness fails. Backups contain
code only and are retained for inspection. Dependency changes beyond the current
pinned MCP version require a separate environment migration.
Before stopping the receiver, setup persists a recovery journal with the backup
file hashes and previous receiver state. If setup is interrupted, the next install
or update first verifies that backup and rolls back the incomplete transaction.
Recovery can itself be interrupted and retried, and respects a later user pause.
A damaged journal or backup stops recovery without replacing runtime files.
A deployment marker blocks new server startup while files are being replaced.
Recovery runs through the agent's setup command, not automatically at Windows boot.
Legacy interruptions without a journal still need manual backup restoration.
Existing MCP sessions must reconnect after an update to load the new server code.
The scheduled receiver refers to the stable external runtime under
`%LOCALAPPDATA%/codex/telegram-task-bridge/runtime`, not the plugin cache.

After installing the plugin, reload/restart Codex. No `/hooks` activation or manual
terminal step is required. Ask the agent to set up or inspect Telegram in chat;
the skill runs the necessary commands with ordinary host permissions.
The MCP launcher checks an existing receiver under the lifecycle mutex; it never
installs anything, duplicates a running receiver, or restarts a failed receiver.
Bootstrap diagnostics go to stderr so stdout remains valid MCP protocol traffic.
Updating the plugin removes its old generated hook declaration, without altering
user hook trust records or unrelated hooks.

The agent uses these commands for the installed plugin (manual use is optional):

```powershell
$bridgeControl = Join-Path $env:LOCALAPPDATA 'codex/telegram-task-bridge/runtime/plugin_control.ps1'
& powershell.exe -NoProfile -NonInteractive -File $bridgeControl status
# Other actions: start, stop, uninstall
```

`stop` persists a pause marker which MCP startup respects; explicit `start` clears it.
The direct scheduled receiver entry point checks the same marker before accessing
credentials, SQLite, or Telegram, so signing in again cannot override a pause.
If explicit resume fails, the pause marker is restored.
The plugin owns the MCP declaration. Remove the old standalone MCP entry during
migration to avoid two declarations. Removing the plugin alone does not remove
the external scheduled receiver; run `uninstall` first to stop/remove it while
preserving private data. The generated plugin is currently Windows-only.
Uninstall retains runtime, environment, backups and private configuration; it
removes the scheduled task and leaves a pause marker, so subsequent MCP sessions
cannot silently reinstall the receiver. It does not delete the bot at Telegram.

### Standalone prototype mode

From repository root, using PowerShell:

```powershell
$bridgeRoot = Join-Path $env:LOCALAPPDATA 'codex\telegram-task-bridge'
python -m venv "$bridgeRoot\venv"
$bridgePython = "$bridgeRoot\venv\Scripts\python.exe"
$bridgeServer = (Resolve-Path 'prototypes\telegram_task_bridge\server.py').Path
$bridgeConfig = Join-Path $env:LOCALAPPDATA 'codex\telegram-notify\config.json'
$bridgeDb = "$bridgeRoot\live.sqlite3"
& $bridgePython -m pip install -r prototypes/telegram_task_bridge/requirements.txt
& $bridgePython $bridgeServer preflight --db $bridgeDb --config $bridgeConfig
codex mcp add telegram-task-bridge -- $bridgePython $bridgeServer serve --db $bridgeDb --config $bridgeConfig
```

The configuration file uses existing notify-via-telegram fields `bot_token` and
`chat_id`. Do not put the token in commands, repository files, or MCP arguments.
Reload MCP connections in the host or restart the app when convenient. Adding
configuration does not prove that the current Desktop task has loaded the tools.

For a one-off receiver, run in a separate terminal (Ctrl+C stops it):

```powershell
& $bridgePython $bridgeServer receive --db $bridgeDb --config $bridgeConfig
```

For persistent Windows use, stop that one-off receiver and install the managed
receiver with the default paths above:

```powershell
./prototypes/telegram_task_bridge/manage_receiver.ps1 install
./prototypes/telegram_task_bridge/manage_receiver.ps1 start
./prototypes/telegram_task_bridge/manage_receiver.ps1 status
```

The Windows Task Scheduler starts `pythonw.exe` without a console, using the
current user's interactive session and limited privileges. It starts at that
user's logon and can be started immediately. No password is stored. It does not
require Desktop to remain open. The user must remain logged in and the computer
awake for delivery; this is not a system service or an idle Codex task wakeup.
The scheduled action points to this checkout and virtual environment, so keep
both paths available.

`stop` stops the registered receiver; `start` resumes it. `uninstall` stops and
removes only the owned scheduled task, keeping messages and configuration.
An unrelated or modified task with the same name is refused rather than replaced.
Registration can fail if local Windows policy denies Task Scheduler access.

The receiver writes `<database>.receiver-health.json` alongside its database.
Status combines task state with heartbeat freshness, not merely a saved PID.
Temporary transport failures, HTTP 429 and HTTP 5xx retry with backoff; sendMessage
is never automatically retried. Authentication errors, webhook/poller conflicts
and invalid state stop the receiver. After resolving their cause, run `start`.
There is no scheduler-level restart loop that would fight another poller.

Only one receiver is needed across MCP server instances. It must remain running
for replies to arrive; starting the MCP server alone does not start the receiver.
Database identity is bound to bot and chat. Use a new database when changing either.
Each live bot is also bound to one canonical database path in an external
`*.database.json` file under the bridge state directory. Changing that path requires
stopping every sender and receiver first, then deliberately removing its binding.
Do not switch databases while any questions still await replies.

## Verification

```powershell
& $bridgePython -m unittest discover -s prototypes/telegram_task_bridge -p 'test_*.py' -v
```

The protocol test starts two real MCP stdio subprocesses with an offline transport,
injects synthetic Telegram updates, and checks isolation and acknowledgement.
It does **not** prove Telegram delivery or integration in two Desktop tasks.

For a live test, with receiver running:

```powershell
& $bridgePython prototypes/telegram_task_bridge/live_probe.py send --db $bridgeDb --config $bridgeConfig --state "$bridgeRoot\probe.json"
# Reply АЛЬФА to A and БЕТА to B in Telegram, ideally in reverse order.
& $bridgePython prototypes/telegram_task_bridge/live_probe.py poll --db $bridgeDb --config $bridgeConfig --state "$bridgeRoot\probe.json"
```

`send` refuses an existing probe state file to avoid repeated sends. It creates two
SDK clients, not two Desktop tasks. Final Desktop acceptance requires calling the
tools from two existing user tasks, then polling/acknowledging their distinct replies.

Uninstall MCP configuration with `codex mcp remove telegram-task-bridge`, stop the
receiver, and remove external state only when its retained messages are no longer needed.
This prototype is not packaged or enabled as a production skill.
