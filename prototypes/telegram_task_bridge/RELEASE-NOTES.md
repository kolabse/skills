# Telegram Task Bridge 0.1.0 — experimental

Windows-only local plugin for cooperative Telegram replies in Codex tasks. This is a separate experimental plugin; the stable kolabse skills collection remains at v1.24.0.

## Included

- Six MCP tools for per-task registration, correlated questions, one-use instruction slots, reply polling, status and acknowledgement.
- A current-user Windows scheduled receiver with persistent SQLite storage and pause/resume.
- Private credential-entry dialog, setup, update backup/rollback and journal-based recovery on a subsequent setup invocation.
- Uninstall removes the receiver task while preserving private data.

## Try it

Download and verify the ZIP against SHA256SUMS, extract it, then ask Codex to install the local plugin from the extracted folder using the supported personal-marketplace workflow. Ask the agent to set up the Telegram receiver. Python 3.10+ is a prerequisite; setup creates its own virtual environment. Use a private test bot/chat and enter credentials only in the setup dialog.

## Known limits

Clean-Windows acceptance was explicitly deferred because of VM networking/VPN problems. Full first-run setup and the credential dialog remain unverified on a clean machine. The archive includes WINDOWS-ACCEPTANCE.md for testers.

Tasks must explicitly poll: no idle-task wakeup, native Desktop approval handling or mid-turn steering. One private bot/chat/database per host; no groups. Do not start a second poller for an existing bot. Recovery of an interrupted initial Python environment creation still requires inspection. This is not a production reliability release.

Report reproducible problems through GitHub issues without tokens, credentials, task secrets or private message contents. Related issue: #131.