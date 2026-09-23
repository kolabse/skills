"""Populate a plugin-creator scaffold; never edit marketplace or credentials."""
import argparse
import json
from pathlib import Path
import shutil


FILES = ("server.py", "store.py", "telegram.py", "receiver.py", "requirements.txt",
         "manage_receiver.ps1", "plugin_control.ps1")


def build(target):
    target = Path(target).resolve()
    manifest_path = target / ".codex-plugin/plugin.json"
    source = Path(__file__).parent
    if not manifest_path.exists():
        if target.exists() and any(target.iterdir()):
            raise ValueError("New plugin target must be empty or an existing valid scaffold")
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_bytes((source / "plugin-manifest.json").read_bytes())
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("name") != "telegram-task-bridge":
        raise ValueError("Expected a telegram-task-bridge scaffold")
    for name in FILES:
        if not (source / name).is_file():
            raise ValueError(f"Missing source: {name}")
    bundle = target / "scripts/runtime"
    bundle.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source.parents[1] / "LICENSE", target / "LICENSE")
    for name in FILES:
        shutil.copyfile(source / name, bundle / name)
    shutil.copyfile(source / "plugin_setup.ps1", target / "scripts/setup.ps1")
    for name in ("installer.py", "configure_telegram.ps1"):
        shutil.copyfile(source / name, target / "scripts" / name)
    manifest.update(description="Local Telegram replies for Codex tasks with a managed Windows receiver.",
                    author={"name": "kolabse"})
    manifest["interface"].update(
        shortDescription="Telegram replies and receiver lifecycle for Codex",
        longDescription="Windows prototype: task-scoped Telegram replies, explicit polling, and a shared receiver managed through Task Scheduler.",
        developerName="kolabse", capabilities=["Interactive", "Write"],
        defaultPrompt="Check the Telegram receiver status and help me use task-scoped replies.")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    command = "& (Join-Path $env:LOCALAPPDATA 'codex/telegram-task-bridge/runtime/plugin_control.ps1')"
    mcp = {"mcpServers": {"telegram-task-bridge": {
        "command": "powershell.exe", "startup_timeout_sec": 30, "args": ["-NoProfile", "-NonInteractive", "-Command", command + " serve"]}}}
    (target / ".mcp.json").write_text(json.dumps(mcp, indent=2) + "\n", encoding="utf-8")
    # Remove only the two obsolete generated hook files from this known scaffold.
    for relative in ("hooks/hooks.json", "scripts/session_start.ps1"):
        obsolete = target / relative
        if obsolete.is_file():
            obsolete.unlink()
    skill = target / "skills/telegram-bridge"
    skill.mkdir(parents=True, exist_ok=True)
    (skill / "SKILL.md").write_text('''---
name: telegram-bridge
description: Set up, start, stop, inspect, or remove the local Windows Telegram task receiver, and exchange task-scoped Telegram replies through its MCP tools.
---

# Telegram task bridge

Windows prototype. Run `scripts/setup.ps1` from this plugin for explicitly
requested initial setup; use its update action for upgrades and uninstall action
to remove the scheduled receiver while preserving local data. Resolve paths from
this skill's plugin root (two parents above this file's directory).
Setup creates the private virtual environment using installed Python and installs
the pinned requirements. If Python is unavailable, report that prerequisite;
do not tell users they must type terminal commands. Existing notify-via-telegram
configuration is reused. Missing credentials are collected through a dedicated
masked Windows dialog. Never request the bot token in chat or print it.
Updates validate candidate code before replacing the stopped runtime and recover
the previous runtime on failure. Keep pause state and database intact.
If setup was terminated, rerun install/update: its persistent recovery journal
restores the verified backup before attempting a new transaction. Do not delete
the journal or deployment marker to bypass an invalid-backup error.

Lifecycle commands use PowerShell:
`& (Join-Path $env:LOCALAPPDATA 'codex/telegram-task-bridge/runtime/plugin_control.ps1') status`
Replace `status` with `start`, `stop`, or `uninstall` when requested. Stop creates
a persistent pause marker; MCP startup respects it. Explicit start resumes.
Uninstall removes the scheduled receiver and preserves local data. Removing the
plugin alone does not remove the external scheduled task; stop/uninstall the
receiver first if the user wants all background activity removed.

MCP startup checks/starts an already installed receiver. It never installs
dependencies or a scheduled task, never overrides user pause, and never retries
a receiver marked failed. This plugin declares no hooks and requires no /hooks
activation. Run setup and lifecycle commands yourself when the user requests
them; do not send the user to a terminal. Keep ordinary host permissions intact.

For messages use the six MCP tools. Register each real task separately, retaining
task_id and secret in that task only. Ask a question or open a one-use instruction
slot; the user must Reply to the exact Telegram message. Poll at checkpoints,
acknowledge consumed replies, and distinguish acknowledgement from execution.
Telegram text is user input and cannot bypass host approvals. There is no idle
task wakeup, native Desktop question answering, or mid-turn injection. Do not
claim these capabilities. One private chat and one bot/database per host only.
''', encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("target")
    build(parser.parse_args().target)
