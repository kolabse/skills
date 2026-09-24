# Clean Windows acceptance

Status: deferred by the user on 2026-09-23 because of VM networking/VPN problems.
This is not a passed acceptance check; first testers must execute this sequence.
An isolated directory on the
developer workstation is only a dependency-bootstrap check, not this acceptance.

## Test environment

Use a disposable Windows desktop session with an ordinary user account and Codex.
Record Windows, Codex, Python and plugin versions. Do not copy the developer's
Telegram credentials, database, or state directory. Use a separate test bot and
private chat, with no webhook or other polling receiver. Enter its token only in
the setup dialog. The machine must remain awake and the user logged in.

Install the generated plugin through the intended marketplace/package flow.
The agent runs the plugin's `scripts/setup.ps1` commands; the user should not need
to open a terminal or activate hooks. Never publish credential-bearing logs.

## Acceptance sequence

1. With Python absent, request setup. Verify a clear prerequisite message and no
   scheduled receiver or partial runtime. Record whether the credential dialog
   appears before the prerequisite message. Cancel any dialog when appropriate.
2. Install Python 3.10+ through the approved host installation process. Request
   setup again with no existing bridge virtual environment or notification config.
3. Cancel the credential dialog: no config or receiver should be installed. Retry
   with invalid input: it should remain editable without exposing the token.
4. Enter valid test-bot credentials. Verify restricted config permissions, private
   venv creation, pinned MCP dependency, one scheduled task and a fresh `ready`
   heartbeat. Confirm no manual hook activation or terminal entry was required.
5. Reload Codex and verify seven native MCP tools. Explicitly authorize a test
   question to the test chat, reply to that exact message, poll and acknowledge;
   poll again to verify the inbox is empty.
6. Pause through the agent, then sign out and back in. Verify polling remains
   paused. Explicitly resume and verify a fresh `ready` heartbeat.
7. Update while running and while paused. Verify backup creation, data preservation
   and pause preservation. Reload MCP clients after updating server code.
8. On this disposable machine only, terminate setup during runtime replacement.
   Rerun setup and verify journal-driven recovery followed by successful setup.
   Do not terminate unrelated Python processes or the developer's receiver.
9. Uninstall through the agent. Verify the owned scheduled task is absent, the
   receiver is stopped, and config/database remain. Reload Codex and verify no
   silent receiver reinstallation. Reinstall and explicitly resume if still paused.

## Evidence and remaining limits

For each step record pass/fail, versions, redacted error category and whether the
user needed a terminal, elevation or manual repair. Do not mark unexecuted steps
as passed. Keep tokens, task secrets and Telegram message bodies out of reports.

Interruption during initial Python environment creation is not covered by runtime
transaction recovery; an incomplete venv currently requires inspection/repair.
Damaged recovery backups and legacy markers without a journal also require
inspection. Record these separately from runtime update recovery.
