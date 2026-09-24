# Issue 131: delivered subset and remaining work

Reviewed for collection 1.25.0. The parent issue remains open: the cooperative
MCP receiver covers a useful subset, not the proposed Desktop control adapter.
Source: https://github.com/kolabse/skills/issues/131.

| Scenario | Current implementation and evidence | Remaining work |
| --- | --- | --- |
| Reply to a specific question | Per-task credentials and message/question correlation; offline MCP and store tests cover two tasks, stale replies, replay and acknowledgement. | Client-specific live acceptance remains separate from automated tests. |
| Reply to an ordinary notification | Issue 140 adds `send_update`, compatible-route selection and checkpoint/final polling. Adapter and offline MCP tests exercise the round trip. | Verify a live ordinary-update Reply after deploying this runtime; a question-only self-check does not prove this path. |
| Additional instruction to a known task | One-use `open_instruction_slot` or Reply to its update; consumed acknowledgement does not claim execution. | The active agent must poll and interpret the instruction. |
| `/tasks`, `/projects`, buttons and creating/selecting existing Desktop tasks | Not implemented; labels are display text, not a discovery API. | A supported authenticated task adapter and an explicit selection/ownership contract are prerequisites. Do not substitute an unrelated App Server's tasks. |
| Wakeup, mid-turn steering and native questions/approvals | Not implemented; Telegram input cannot bypass host permissions. | Version-specific integration proof for the intended client, including cancellation, archived tasks and turn identity. |
| Durable delivery | SQLite retains offsets, deduplication and unconsumed replies; receiver tests cover reconnect/restart and competing receivers. Unknown sends are not blindly retried. | Do not promise exactly-once execution: consuming input and executing its instruction are separate operations. |
| Late replies | A reply captured before TTL survives until acknowledgement; after-TTL input is rejected. Completion waits are bounded and resuming the same task polls retained credentials. | No automatic resumption; credentials lost with a task cannot be recovered by creating a different registration. |
| Sender-visible receipt/execution states | Tools distinguish sent/unknown/answered/acknowledged/expired; agents report observed outcomes. | Automatic Telegram receipts, persistent execution reconciliation and message-retention policy need a separate design. |
| Installation and clients | Standard collection update bundles runtime, with Windows setup/controller and per-client Codex/Claude registration. | Clean-Windows acceptance remains deferred; live tests must name the client and deployed runtime. |

The next implementation stage should first establish supported access to the
intended existing task. Task menus, external steering and idle wakeup must not
be advertised from the existence of internal app tools alone. Keep the mode
experimental until its remaining acceptance boundaries have observed evidence.

This review does not enable a receiver, send a test message, modify a user's
client configuration, or declare the parent issue complete.
