# Bridge-owned Codex task prototype

This experiment starts a separate, ephemeral Codex App Server task using the
existing Codex login. It does not attach to an existing Desktop task. It is not
yet released to users. Its modules are now included in the collection and plugin
build inputs. [Packaged live acceptance](../../docs/reports/telegram-owned-task-acceptance.md)
passed on an existing Windows installation; clean-Windows acceptance remains pending.

The bounded scenario is: ask for a short word in Telegram, wait for an exact
reply, return that reply to the pending dynamic tool call, wait for the owned
turn to complete, then send its final message to Telegram.

## Current evidence

Fifteen transport, controller, and store adapter tests pass offline. On
2026-09-24, the controlled live run also completed: Telegram accepted the
question, the receiver stored the user's exact reply, the controller dispatched
it to the pending App Server request, the owned turn completed, and Telegram
accepted its final message. The process exited successfully and the receiver
remained `ready`. The local report records `status: completed`,
`reply_dispatched: true`, and `result_sent: true`, without message contents.

This proves one end-to-end task using the bundled version below; it does not
establish production readiness, restart recovery, or Desktop task attachment.
Before this run, the user closed Codex on the second PC and the local receiver
was explicitly restarted after an earlier HTTP 409 conflict. Do not start a
competing receiver or remove a webhook. Closing the UI alone is not proof that
another host's background receiver stopped; verify receiver health as done here.

Run offline tests from the repository root:

```powershell
python -m unittest discover -s prototypes/telegram_task_bridge -p 'test_owned_task*.py' -v
```

## Controlled live run

### Opt-in MCP entry point

Live Codex MCP sessions expose the three owned-task tools after runtime update
and MCP reload. Registering the tools does not launch a task. On explicit start,
the launcher discovers only the tested executable under the known local Codex
installation directory. `--owned-task-codex <absolute-exe>` remains an optional
host override; users do not need to type it. Claude Code and offline sessions
keep their existing cooperative tools. Do not claim the updated runtime is
installed merely because its source bundle has been built.

Once configured, an agent can fulfill these user requests through MCP:

- “Запусти тестовую задачу через Telegram”: call `register_task`, retain its
  credentials, then `start_owned_task` with those credentials.
- “Покажи состояние”: call `owned_task_status` with the same credentials.
- “Отмени задачу”: call `cancel_owned_task`, then inspect status until the child
  reports `interrupted` or another terminal outcome. `cancel_requested` alone
  does not confirm termination.

Each registration admits one launch. Repeating start reads its state and never
creates another process, even after an uncertain spawn or MCP restart. A new
registration means a new task and requires explicit intent. Tools authenticate
the registration before reading status or requesting cancellation. No executable,
prompt, directory or arbitrary command is accepted from Telegram or tool callers.

Preflight requires the known Codex version, existing ChatGPT login, local
configuration and a fresh `ready` receiver. Unsupported versions, missing login
or unhealthy receivers return a bounded error code; nothing is silently installed,
resumed or changed. The scenario remains the single-word communication test.

The child persists progress to disk, but the client may terminate its process
tree when closing an MCP session. Keep that session open until a terminal
outcome; this is not a detached service. After MCP restart, its process liveness
is `unknown`; the report is only the last observation. A
cooperative cancellation marker is still usable. Cancellation checks happen
before external actions and while waiting, but cannot recall already sent input
or messages, and can wait for an in-flight network call to finish. Only the
owned App Server is interrupted; no process is killed by a stored PID.

### Direct diagnostic invocation

First ensure exactly one receiver is running, using the configured bot and the
same local database. Its health must be `ready` and fresh. The script never
starts, stops, resumes, or polls a receiver; it only reads replies stored by it.
Use the executable matching the protocol schema verified for this experiment
(bundled Codex 0.155.0-alpha.16.3 or 0.158.0-alpha.2.1). This experimental protocol may
change; compatibility with other versions is not established.

Run `owned_task.py --live --codex-executable <absolute-exe> --database <existing-db>
--config <existing-private-config> --workdir <empty-scratch-directory>
--report <new-json-file>`. All arguments are required. Use a fresh report path
for every explicitly requested run. The config is read locally; do not copy its
contents into prompts, logs, or source control.

Reply to the bot's question using Telegram's Reply action within ten minutes.
The report records success only after the owned turn completes and Telegram
accepts the final message. No raw question, answer, token, or task secret is
written to the report. Question and answer remain in the existing bridge DB.

## Boundaries

- The task requests read-only permissions, no environment access, and no network
  access for sandboxed tools. It receives instructions to use only `askTelegram`.
  This is a harmless communication experiment, not a general tool isolation or
  production permission system. Installed capabilities may depend on the host.
- Unexpected server requests, including approvals, are rejected. Telegram input
  is data, never permission to execute an action.
- No delivery is automatically retried, and no crashed task is resumed. A pipe
  write or Telegram send can have an uncertain outcome. Acknowledgment means the
  reply was consumed for dispatch, not that a task action executed exactly once.
- The controller has a ten-minute deadline. Each active pipe write has a
  ten-second timeout by default; a timeout permanently retires that transport
  without retrying the frame. Cleanup and synchronous Telegram requests can add
  their own bounded waits. The prototype is not a background service or a
  process-tree supervisor.
- On failure, only the owned turn/process is interrupted or closed. An abandoned
  Telegram question expires; its late reply never resumes this prototype.
- Account-wide rate limits and the existing Codex login apply. No Platform API
  key is created or required by this implementation.

Protocol reference: [Codex App Server](https://learn.chatgpt.com/docs/app-server).

## Failure reporting added after the live experiment

The report now exists before preflight and is atomically replaced as the run
advances. `phase` is recorded before sending a question, dispatching a reply,
or sending a result. `reply_dispatched`, `turn_completed`, and `result_sent`
record separate observed outcomes. A failure sending the final message retains
`turn_completed: true` while leaving `result_sent: false`.

After a hard process kill, a report may retain `status: running`; this is the
last persisted observation, not a liveness check. A `sending_*` or
`dispatching_reply` phase can mean unknown delivery. Do not replay it. A new run
requires a fresh report path and explicit intent to create a new task. The
report never stores prompts, replies, raw exceptions, or credentials. Progress
write failure stops further task actions; the previous valid report is kept.

The hardening tests cover pipe backpressure, serialization, cancellation while
polling, reply deadlines, report replacement failure, and uncertain final
delivery. The September 29 packaged acceptance above covers the hardened
controller's completion and cancellation paths on the newer Codex version.
