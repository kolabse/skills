---
name: notify-via-telegram
description: "Send Telegram notifications about long-running agent tasks through a global destination or a project-specific chat or topic. Use when a task is expected to take several minutes or span multiple stages, waits, deployments, builds, migrations, research passes, or other lengthy work that benefits from start, progress, milestone, problem, blocked, and completion updates; also use whenever the user asks to be notified or kept updated in Telegram or to configure notification routing for a project."
---

# Notify via Telegram

This skill is portable between Codex and Claude Code. Invoke it as
`$notify-via-telegram` in Codex or `/notify-via-telegram` in Claude Code. The
Python sender and its configuration contract are shared; only the optional
Codex Desktop Windows setup fallback below is Codex-specific.

Keep Telegram updates concise, useful away from the workstation, and free of
credentials, private reasoning, raw logs, and unnecessary implementation detail.

## Configure first use

1. Resolve this skill's directory and run:

   ```shell
   python <skill-root>/scripts/telegram_notify.py status
   ```

2. When configuration is missing in Codex Desktop on Windows, launch the bundled
   visible, masked, paste-friendly form. Do not use an internal PTY or `getpass`
   for this path:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File <skill-root>/scripts/configure_windows.ps1
   ```

   The form validates the token locally before any network request and passes it
   to the child Python process only through its environment. It never places the
   token in command arguments or output. On macOS, Linux, or a normal visible
   interactive terminal, run:

   ```shell
   python <skill-root>/scripts/telegram_notify.py configure
   ```

   Never ask the user to paste the token into the conversation or command
   arguments.

3. Guide the user to create or select a bot with `@BotFather`. For a direct chat,
   have the user open the bot and send `/start`. For a group, add the bot and send
   a command addressed to it, such as `/start@bot_username`. The configure command
   validates the token, reads the recent update, presents matching chats, stores
   the selected chat ID in the user's configuration directory, and sends a test
   notification.
4. If `getUpdates` reports that a webhook is active, ask for the destination chat
   ID and rerun `configure --chat-id <id>`. Accept an optional
   `--thread-id <id>` for a forum topic. Keep the token in the interactive prompt
   or `TELEGRAM_BOT_TOKEN`, never in the command line.

Completion criterion: `status --verify` confirms a bot and destination without
printing the token, and the user receives the test notification.

Configuration is versioned and described by `schemas/config.schema.json`.
After updating the skill, run `migrate --json`; legacy unversioned configuration
is upgraded to version 1, while unknown newer versions fail closed. Use
`status --json` for read-only automation; it never emits the token.

## Configure a project destination

Use the global bot identity on the computer, but allow each project to select a
separate chat or forum topic. Confirm that the organization permits task
updates in that destination, then choose the routing mode explicitly:

- `global-and-project` sends each update to both configured destinations;
- `project-only` suppresses the global destination for that project.

```shell
python <skill-root>/scripts/telegram_notify.py project-configure \
  --project-path <project-root> \
  --delivery-mode <global-and-project-or-project-only> \
  --chat-id <project-chat-id> [--thread-id <topic-id>]
```

Omit `--chat-id` to discover a recent project chat interactively. The command
sends a test unless `--skip-test` is explicitly selected. Check the effective
profile without exposing credentials:

```shell
python <skill-root>/scripts/telegram_notify.py project-status \
  --project-path <project-root> --json
```

The profile is stored in the user's configuration directory under a hash of the
canonical project path, never in the repository. It contains only the routing
mode, chat ID, and optional topic ID; the bot token remains global and
machine-local. A project without a profile continues to use only the global
destination.

## Plan notification points

Before starting substantive work, identify only the meaningful notification
points:

- start, with the outcome and short plan;
- transition into a materially different stage;
- intermediate result that changes understanding or reduces risk;
- problem that changes the plan, timing, scope, or likelihood of success;
- blocked, failed, or completed outcome.

Treat routine commands, repeated waits, unchanged state, and minor retries as
local execution noise. Combine rapid transitions into one update. For a long
stage with no visible transition, send a heartbeat only when there is new
information or roughly 15 minutes have passed.

Completion criterion: every planned notification answers why the remote reader
would care now, and no notification exists solely to report activity.

## Send updates

Send plain-text messages with:

```shell
python <skill-root>/scripts/telegram_notify.py send \
  --project-path <project-root> "<message>"
```

Always pass `--project-path` while operating in a project so its routing profile
is honored. Omit it only for work that is not associated with a project.

Use these compact shapes and omit empty fields:

```text
▶️ <task>
Старт: <requested outcome>
План: <major stages>

🔄 <task>
Этап: <current stage>
Результат: <new evidence or artifact>
Дальше: <next stage>

⚠️ <task>
Проблема: <observable issue>
Влияние: <scope, timing, or risk>
Действие: <response or user decision needed>

✅ <task>
Итог: <completed outcome>
Проверено: <decisive evidence>
Осталось: <residual risk or follow-up>
```

Use `⛔` instead of `✅` for failure or a genuine blocker. Name artifacts and
results; include links only when they are useful from Telegram. Keep each update
self-contained and normally below 1,000 characters.

If sending fails, retry once after checking `status --verify`. Continue the
authorized task when Telegram is the only failure, report the notification
failure in the local conversation without exposing credentials, and try again
at the next meaningful notification point.

Completion criterion: Telegram reflects the task's actual current state, the
latest message states the observed outcome, and notification failures are not
misreported as task failures.

## Protect the channel

- Read credentials only through the script's interactive prompt, its user-local
  config, the bundled Windows form, or `TELEGRAM_BOT_TOKEN`,
  `TELEGRAM_CHAT_ID`, and optional
  `TELEGRAM_MESSAGE_THREAD_ID` environment variables.
- Keep secrets, personal data, customer data, internal URLs, stack traces, and
  sensitive filenames out of notifications unless the user explicitly defines
  that Telegram chat as an approved destination for them.
- Summarize errors and results. Send no chain-of-thought, hidden reasoning, or
  large raw output.
- Obtain confirmation before changing the configured destination or sending a
  test message to a newly supplied chat ID.

## Synchronize a project profile

Only synchronize the project routing values after confirming that the selected
storage may contain the chat and topic identifiers; they can reveal team or
organization structure. Export a reviewed, secret-free environment input:

```shell
python <skill-root>/scripts/telegram_notify.py project-export \
  --project-path <project-root> > <temporary-json-outside-project>
```

Use `$sync-project-context` in Codex or `/sync-project-context` in Claude Code
to inspect and capture that input as a project
environment setting. On another computer, its read-only environment plan will
report `manual_apply_required`. Recreate the destination with
`project-configure`, then export observed state for verification:

```shell
python <skill-root>/scripts/telegram_notify.py project-export \
  --project-path <project-root> --local-state \
  > <temporary-local-state-outside-project>
```

Pass that file to `environment_sync.py plan --local-state`. Delete both
temporary files afterward. The bot token and Telegram authentication state are
never exported or synchronized; configure the global sender independently on
each computer.
