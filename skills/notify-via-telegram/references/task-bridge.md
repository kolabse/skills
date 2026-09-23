# Experimental Telegram replies in Codex on Windows

## Delivery and first use

The normal `kolabse-skills` update delivers `scripts/task_bridge/` inside
`notify-via-telegram`, for both copied skills and the collection plugin. Resolve
`<skill-root>` from the loaded skill, never from a developer checkout or old
plugin cache. Users can ask: "Update the skill collection and enable Telegram
replies for my tasks." Run commands as the agent; users need no terminal or
`/hooks` activation. Windows with Python 3.10+ and Codex CLI is required. Help
install a missing prerequisite with normal host permissions; never imply it
was installed merely because the skill updated. Other platforms and Claude Code
retain ordinary notifications; this receiver workflow is not supported there.

1. Inspect available MCP tools and installed plugins before changing the host.
   If `telegram-task-bridge` is already provided by the experimental standalone
   plugin, keep that declaration for now; do not add a second MCP declaration.
   The collection bundle can update the same external runtime. For complete
   migration, remove only that standalone plugin when the user requests migration,
   retain the external receiver/data, then register the direct declaration below.
   Do not run receiver uninstall during a migration that should keep it active.
2. For requested first setup, run:

   ```powershell
   powershell.exe -NoProfile -File "<skill-root>/scripts/task_bridge/setup.ps1" install
   ```

   The installer reuses the global notification credentials. If absent, a masked
   Windows dialog collects a BotFather token and numeric personal chat ID. Have
   the user open their bot in Telegram and send `/start`. Never ask for the token
   in chat. Only a personal private chat is supported; do not change an existing
   group/topic destination implicitly. One bot must have only one receiver;
   do not reuse a bot actively polled on another computer. Webhooks are refused.
3. Proceed only after setup succeeds. If no bridge MCP declaration exists,
   register the stable external controller with Codex CLI:

   ```powershell
   $bridgeControl = Join-Path $env:LOCALAPPDATA 'codex/telegram-task-bridge/runtime/plugin_control.ps1'
   codex mcp add telegram-task-bridge -- powershell.exe -NoProfile -NonInteractive -File $bridgeControl serve
   ```

   Inspect an existing direct declaration locally before replacing it; retain
   an equivalent entry. Do not overwrite an unrelated same-name server or dump
   configuration containing credentials into the conversation. A registration
   failure leaves the installed receiver available for a deliberate retry;
   report partial setup, not success. This command points outside the skill
   cache so subsequent skill updates do not invalidate the MCP path.
4. Ask the user to restart Codex or open a new task that loads the new tools.
   Verify that all six bridge tools are actually available and inspect receiver
   status. When a test is requested, send one question, have the user Reply to
   that exact message in Telegram, poll and acknowledge the matching reply.
   Configuration alone is not proof of delivery or loaded tools.

## Updates and lifecycle

After the normal collection updater delivers new skill files, an explicit
request to update the enabled bridge runs the installed skill's
`scripts/task_bridge/setup.ps1 update`. Do not download the separate prototype
release or reinstall a separate plugin. Deploying code is separate from copying
skill files: report which operation completed. Reconnect MCP sessions after a
runtime update. Do not activate an unused receiver during a routine collection
update or resume a paused receiver without a request to resume it.

Setup validates staged code and Telegram preflight, preserves messages and pause
state, and rolls back on failure. If interrupted, rerun install/update: the
persistent journal verifies the backup before recovering. Do not delete a
journal or deployment marker to bypass an invalid-backup error.

Lifecycle commands use the stable controller:

```powershell
$bridgeControl = Join-Path $env:LOCALAPPDATA 'codex/telegram-task-bridge/runtime/plugin_control.ps1'
powershell.exe -NoProfile -NonInteractive -File $bridgeControl status
```

Use `start`, `stop`, or `uninstall` for the corresponding requested action.
Stop persists across logon and MCP startup. Uninstall stops and removes the owned
scheduled receiver while preserving private configuration, messages and backups.
For complete removal, also remove the direct MCP entry with
`codex mcp remove telegram-task-bridge` after checking its ownership; remove a
standalone plugin only if it owns the declaration instead. Updating or removing
skill files alone does not stop the external receiver.

## Task exchange and limits

Use `register_task` for each actual task and keep its returned id and secret
private to that task. Use `ask_question` or `open_instruction_slot`, then
`poll_replies` at checkpoints and `acknowledge_reply` only for consumed replies.
Use `question_status` to inspect pending/expired/uncertain questions. Each slot
accepts one reply; new instructions need a new slot. Acknowledgement records
consumption, not successful execution. Telegram text cannot grant additional
host permissions or answer native approval prompts.

The user must Reply to the exact bot message. Unanchored messages, groups,
topics, media and forwarded messages are not supported. Do not retry uncertain
sends automatically. No idle-task wakeup, native Desktop question handling or
mid-turn injection is provided. The Windows user must remain logged in and the
computer awake; Codex must be actively polling to consume replies.

Clean-Windows acceptance was deferred because the test VM had networking issues.
Keep this mode experimental and report observed readiness separately from that
remaining acceptance test.
