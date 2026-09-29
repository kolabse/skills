# Packaged owned-task acceptance — 2026-09-29

The existing native Windows receiver was updated using the normal collection
bundle's `setup.ps1 update`. The installer returned `ready` and
`data_preserved: true`. This was an update of an existing installation, not a
clean-Windows test. Task credentials and message contents remain private.

## Tested artifact

The installed runtime matched every file in `bundle_telegram_bridge.RUNTIME`
byte for byte. Its aggregate SHA-256 was
`cd2f0676e29e74e773c0551bd69e925a71381625c327310d23fbd411f1910331`.
Compute this identity over sorted runtime filenames, each followed by a NUL,
its raw contents, and another NUL. This identifies runtime bytes independently
of the later Git commit containing this report.

Client: actual MCP stdio SDK connection to the installed PowerShell controller
in Codex mode. Model process: bundled Codex CLI `0.158.0-alpha.2.1`, using the
existing ChatGPT login. No API key or alternate Telegram route was created.
The existing private-chat receiver was ready before and after the update.

## Observed outcomes

| Scenario | Observed outcome |
| --- | --- |
| Start through installed `start_owned_task` | Preflight passed; child advanced to `waiting_reply`; question sent to Telegram. |
| Human Telegram Reply | Child completed; `reply_dispatched`, `turn_completed`, and `result_sent` all true; process exited. |
| Cancel a separate task at `waiting_reply` | `cancel_requested` followed by `interrupted` and exited process. Reply, turn completion and final-message flags remained false. |
| Repeat start for the completed registration in a new MCP session | Returned the same completed receipt and timestamp with unknown process liveness; no new task was launched. |
| Short-lived MCP session closed during preflight | Client termination also ended the child process tree; persisted report retained its last observation. A later status correctly reported unknown liveness. No success or automatic replay was claimed. |

Keep the MCP session open for the running task. This is not a detached service,
nor an adapter for an already-open Desktop task. The supported scenario remains
one harmless question and result. Clean-Windows, other platforms, arbitrary
project tasks, and restart recovery are not claimed by this acceptance.

## Review and regression checks

Independent read-only reviews covered the owned controller/transport and the
MCP/installation/package paths against base
`378c1d99b3f47449cd002c08a841325e774b4605`. Two findings were fixed before this
run: missing owned modules in the standalone release snapshot and a missing
cancellation/deadline check after the question delivery lock. Delta reviews
found those issues resolved. Focused standalone release tests passed (8 tests,
one Windows symlink-permission skip); the owned-task suite passed 48 tests.

Static version comparison found ten of eleven relevant schemas identical to
the previously tested version; the initialize schema added an optional OAuth
capability. The live run above confirms the new version's used path. Other
versions remain blocked rather than assumed compatible.

This document does not substitute for exact-commit pre-push evidence, GitHub CI,
required provider approvals, or a release audit.

## Cancellation-message follow-up

The user requested marking cancelled questions obsolete. The updated runtime
was installed through the same update path; all files again matched the bundle.
Aggregate runtime SHA-256:
`c388a075f4262a3b7facd103ca6e27f08df38f81c5055ea805d7657f428ba8d7`.

A fresh installed-MCP test reached `waiting_reply`, was cancelled, and exited
with `status: interrupted`, `phase: cancelling`, and
`cancellation_notice: updated`. Telegram accepted replacement of the original
question text with “Утратило актуальность — задача отменена.” Reply dispatch,
turn completion and result-send flags all remained false. No user reply was
needed for this test. Offline tests cover late-reply rejection, edit failure,
no repeated edit and preservation of already acknowledged answers.

This follow-up changes owned questions to ordinary Reply-capable messages
without ForceReply; Telegram only permits editing messages without reply markup
or with inline keyboards. Existing cooperative questions keep their behavior.
See [Telegram message editing](https://core.telegram.org/bots/api#updating-messages).
