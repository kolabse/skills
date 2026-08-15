---
name: notify-via-telegram
description: "Send Telegram notifications about long-running agent tasks. Use when a task is expected to take several minutes or span multiple stages, waits, deployments, builds, migrations, research passes, or other lengthy work that benefits from start, progress, milestone, problem, blocked, and completion updates; also use whenever the user asks to be notified or kept updated in Telegram."
---

# Notify via Telegram

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
python <skill-root>/scripts/telegram_notify.py send "<message>"
```

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
