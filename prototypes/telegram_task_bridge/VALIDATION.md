# Capability check — 2026-09-18

## Claude Code Windows extension — 2026-09-23

Claude Code CLI 2.1.280 successfully registered the offline stdio server in an
isolated user scope and reported `Connected`. The optional `smoke_claude.py`
helper verified exact Cyrillic/spaced argument persistence, refusal to replace
an existing same-name entry, and scoped removal preserving unrelated entries.
Run it with `--claude <claude-executable> --python <python-with-bridge-requirements>`.
It does not install dependencies or modify the user's real configuration.

Targeted runtime tests passed (7 tests): client-labelled question/slot text,
Windows controller argument forwarding, existing bootstrap behaviour, and two
real MCP server processes (`codex` and `claude-code`) exchanging simulated replies
through one temporary database while rejecting mixed task credentials.
New identity tests failed before the implementation and passed afterward.

These are CLI connection and offline protocol results. An authenticated Claude
model session asking a question and consuming a human Telegram reply has not
been exercised. No live receiver settings or messages were changed for these tests.

## Original Codex qualification

Release qualification: experimental. On 2026-09-23 the user explicitly deferred
clean-Windows acceptance because the test VM could not obtain usable VPN/internet
connectivity. No successful clean-machine install or credential-dialog acceptance
is claimed. Offline CI is complementary evidence, not a substitute for this test.

Windows, Python 3.13, MCP Python SDK 2.2.0.

| Check | Result |
| --- | --- |
| Store and adapter tests | 9 passed |
| Receiver recovery and error classification tests | 6 passed |
| Plugin bundle and hook decision tests | 2 passed (including five hook-state scenarios) |
| Actual stdio MCP, two subprocesses, six tools | 1 passed |
| Task isolation, duplicate replies, expiry, restart, acknowledgements | Passed offline |
| Wrong sender/chat, forwarded/unbound replies, webhook refusal | Passed with fixtures |
| One bot / one database and local receiver exclusion | Passed |
| Live private-chat preflight | Passed; no webhook, no queued updates before receiver startup |
| Live MCP sends from two SDK clients | A and B both reported sent |
| Live human reply routing | Both replies received in their corresponding SDK tasks; A differed from the requested test word, B matched |
| Live MCP acknowledgement | Both replies acknowledged; both inboxes empty afterward |
| Global Codex MCP configuration | Added as `telegram-task-bridge` |
| Tools invoked from two actual Desktop tasks | Passed after application restart: registration, question, poll, acknowledgement, empty inbox |
| Desktop task A | Native MCP received the expected reply; acknowledged and verified empty inbox |
| Desktop task B | Separate task reported native MCP received its distinct expected reply; acknowledged and verified empty inbox |

The live SQLite database, health file, probe credentials and virtual environment
are outside the repository in `%LOCALAPPDATA%/codex/telegram-task-bridge`.
The original background receiver stopped after the app restart; it was restarted
manually before the Desktop reply tests. It has now been replaced by a Windows
Task Scheduler receiver with a current-user logon trigger and limited privileges.
Registration, idempotent installation, start, successful Telegram polling, stop,
and restart were exercised on the host. Process ancestry leads to Windows
`svchost.exe`, independently of the Desktop process. Status correctly reports
stopped even when an old healthy heartbeat remains on disk.
The logon trigger is configured but a Windows sign-out/reboot was not performed.
The existing notify-via-telegram configuration was reused without modification.

Review found a reply-loss risk when sender and receiver use different databases
for the same bot. The prototype now rejects that configuration before sending.
All 18 tests passed after the plugin changes. Temporary transport failures,
truncated HTTP responses, 429 backoff and permanent 409 refusal are tested with
fixtures; a live network outage was not induced. Scheduling does not restart fatal
conflicts, and no messages are resent automatically.

The local plugin was validated with plugin-creator and installed in the personal
marketplace. The generated skill also passed validation. Its exact `.mcp.json`
command initialized a real stdio MCP client and listed all six tools. Its exact
Windows hook command was executed directly; live pause/resume behavior was tested.
The receiver now uses the stable external runtime, preserving the same live DB and
private bot configuration. The standalone global MCP entry was removed in favor
of the plugin declaration. Windows PowerShell 5 setup compatibility was fixed.

The user subsequently trusted the hook, and its automatic `ready` context was
observed in a resumed Desktop session on 2026-09-21. No trust bypass was used.

## MCP startup migration — 2026-09-21

The updated plugin no longer declares SessionStart or requires hook activation.
The MCP launcher performs the same serialized receiver check before serving,
with diagnostics restricted to stderr. Five bootstrap scenarios were exercised
through the actual launcher with fixture servers: not installed, clean start,
fatal previous failure, already running, and user pause. Only a clean start
starts a receiver; protocol stdout remains uncontaminated in every scenario.
Bundle tests verify that old generated hook files are removed during upgrade.

The updated personal plugin was installed, its stable external controller updated,
and its exact installed MCP command initialized successfully with all six tools.
The live bootstrap reported ready. All 18 tests passed. Existing credentials,
database, scheduled receiver and user hook trust records were preserved.
Desktop must reload the updated plugin; the installed-command test does not by
itself prove that the current Desktop session has refreshed its plugin catalog.

No native Desktop input/approval handling, idle-task wakeup, external turn steering,
or production reliability claim is made. Changes remain local on the published
task branch; no implementation commit, PR, merge, or release was created.

## Installation lifecycle package — 2026-09-21

All 31 tests passed: this includes ten installer transaction tests, eight receiver
tests, and three plugin launcher/bundle tests. Installer tests use temporary files
and a simulated scheduler to cover initial deployment, failed preflight, partial
deployment, readiness failure and rollback, pause preservation, and uninstall.
PowerShell syntax, plugin manifest and generated skill validation passed.

Personal plugin version `0.1.0+codex.20260921040332` was installed. Its actual
setup command updated the live runtime, retained a code backup and returned
`ready`. A real scheduled-task start while paused wrote `paused`; explicit resume
removed the marker and restarted the receiver. The exact installed MCP command
initialized successfully and exposed all six tools. No Telegram messages were
sent by these checks.

Existing credentials were reused. The first-run credential dialog, Python/venv
bootstrap on a clean Windows installation, and another reboot were not exercised.
Rollback was tested with fixtures, not by damaging the live installation.
Abrupt termination during replacement still requires setup retry or manual
restoration from the retained backup; the deployment marker blocks new startup.
Desktop must reload the updated plugin. This remains a local prototype package,
not a published collection release.

## Interrupted runtime transaction recovery — 2026-09-21

All 39 tests passed. Eight additional cases cover interrupted update recovery
before a new preflight, repeated interruption of recovery, a later user pause,
backup corruption, backup path escape, interrupted first runtime deployment,
legacy marker refusal, and abrupt exit of a separate installer process using
`os._exit`. These tests use temporary runtime/data files and a simulated scheduler;
the production receiver was not deliberately crashed.

The journal is flushed before the receiver is stopped and kept until deployment
or rollback completes. A subsequent install/update validates backup hashes and
restores the previous runtime and scheduler state before starting a new attempt.
This supersedes the manual-recovery limitation above for transactions created
by this installer. Recovery is triggered by setup, not by Windows boot. Legacy
markers without a journal and damaged backups still require inspection. Recovery
does not cover interruption while initially creating the Python environment,
before a runtime transaction begins; clean-machine acceptance remains pending.

Plugin and generated skill validation passed. Personal plugin
`0.1.0+codex.20260921042216` was installed and its actual setup update completed
with `ready`, a retained backup, and `data_preserved: true`. There was no pending
live transaction to recover; crash recovery evidence comes from the tests above.

## Fresh dependency bootstrap — 2026-09-21

On the existing developer Windows host, the real installer environment method
created a fresh venv in an isolated temporary directory, installed MCP 2.2.0,
successfully imported MCPServer, and reused that environment on a second call.
No credentials, live database or scheduled task were used by this check.
This is not clean-Windows acceptance. Windows Sandbox is absent and querying
Hyper-V VMs was denied to the current process. The user selected a separate VM
or test PC; its location/access is pending. See WINDOWS-ACCEPTANCE.md for the
remaining first-run, credential-dialog, reboot and lifecycle checks.
