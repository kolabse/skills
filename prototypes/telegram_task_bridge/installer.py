"""Explicit setup transaction. Invoke through setup.ps1's lifecycle mutex."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import uuid


FILES = ("server.py", "store.py", "telegram.py", "receiver.py", "requirements.txt",
         "manage_receiver.ps1", "plugin_control.ps1")


class SetupError(RuntimeError):
    pass


def run(command, timeout=180):
    """Suppress child output, including possibly sensitive dependency/config errors."""
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        raise SetupError("Setup subprocess failed or timed out; inspect prerequisites and retry.") from None
    if result.returncode:
        raise SetupError("Setup subprocess failed; check Python, dependencies, Telegram configuration and connectivity.")
    return result.stdout


class Installer:
    def __init__(self, root, bundle, config):
        self.root, self.bundle, self.config = map(Path, (root, bundle, config))
        self.runtime = self.root / "runtime"
        self.python = self.root / "venv/Scripts/python.exe"
        self.database = self.root / "live.sqlite3"
        self.pause = self.root / "receiver-paused"
        self.deployment_marker = self.root / "deployment-in-progress"
        self.journal = self.root / "installation-transaction.json"

    def checkpoint(self, backup, previous, before):
        record = {"version": 1, "backup": backup.name,
                  "files": {name: hashlib.sha256((backup / name).read_bytes()).hexdigest()
                            for name in previous},
                  "installed": bool(before.get("installed")),
                  "running": before.get("scheduler_state") in ("Running", "Queued")}
        pending = self.journal.with_suffix(".pending")
        with pending.open("w", encoding="utf-8") as stream:
            json.dump(record, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(pending, self.journal)

    def recover(self):
        """Repeatable rollback before a new setup, including interrupted rollback."""
        if not self.journal.exists():
            if self.deployment_marker.exists():
                raise SetupError("Interrupted legacy deployment has no recovery journal; restore its backup manually.")
            return False
        try:
            record = json.loads(self.journal.read_text(encoding="utf-8"))
            name = record["backup"]
            if (record["version"] != 1 or not isinstance(name, str)
                    or not name.startswith("backup-") or len(name) != 39
                    or any(c not in "0123456789abcdef" for c in name[7:])
                    or type(record["installed"]) is not bool or type(record["running"]) is not bool
                    or not isinstance(record["files"], dict)
                    or not set(record["files"]).issubset(FILES)):
                raise ValueError()
            backup = self.root / name
            if backup.resolve().parent != self.root.resolve() or backup.is_symlink():
                raise ValueError()
            for filename, digest in record["files"].items():
                path = backup / filename
                if path.resolve().parent != backup.resolve() or path.is_symlink():
                    raise ValueError()
                if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                    raise ValueError()
        except (ValueError, KeyError, TypeError, OSError):
            raise SetupError("Recovery journal or backup is invalid; no runtime files changed. Preserve them for inspection.") from None
        self.manager("stop")
        self.wait_stopped()
        # Remove a partially registered first installation before removing its files.
        if not record["installed"]:
            self.manager("uninstall")
        self.restore(backup, record["files"])
        if record["installed"]:
            self.manager("install")
        if record["running"] and not self.pause.exists():
            started_at = time.time()
            self.manager("start")
            self.wait_ready(started_at)
        self.journal.unlink()
        return True

    def manager(self, action):
        # The bundled manager stays available while stable files are restored.
        output = run(["powershell.exe", "-NoProfile", "-NonInteractive", "-File",
                      str(self.bundle / "manage_receiver.ps1"), "-Action", action,
                      "-PythonPath", str(self.python.with_name("pythonw.exe")),
                      "-ServerPath", str(self.runtime / "server.py"),
                      "-DatabasePath", str(self.database), "-ConfigPath", str(self.config)])
        try:
            return json.loads(output.lstrip("\ufeff"))
        except ValueError:
            raise SetupError("Receiver manager returned invalid status.") from None

    def environment(self, candidate):
        if self.python.is_file():
            # Never upgrade a working environment as part of a code update.
            run([str(self.python), "-c", "import sys,importlib.metadata as m; "
                 "assert sys.version_info >= (3,10); assert m.version('mcp') == '2.2.0'"])
            return
        venv = self.root / "venv"
        if venv.exists():
            raise SetupError("Incomplete bridge venv exists. Preserve it for inspection; repair or move it before retrying setup.")
        try:
            run([sys.executable, "-m", "venv", str(venv)])
            run([str(self.python), "-m", "pip", "install", "--disable-pip-version-check",
                 "-r", str(candidate / "requirements.txt")], timeout=600)
        except Exception:
            # Only a newly created environment may be removed on bootstrap failure.
            resolved_root = self.root.resolve()
            if not venv.is_symlink() and venv.resolve() == resolved_root / "venv":
                shutil.rmtree(venv, ignore_errors=True)
            raise

    def validate(self, candidate):
        script = ("import sys,pathlib; sys.path.insert(0,sys.argv[1]); "
                  "[compile(p.read_bytes(),str(p),'exec') for p in pathlib.Path(sys.argv[1]).glob('*.py')]; "
                  "import server,store,telegram,receiver; from mcp.server import MCPServer; "
                  "telegram.Telegram(sys.argv[2]).preflight()")
        # Read-only API preflight: no polling, sends, or live database migrations.
        run([str(self.python), "-c", script, str(candidate), str(self.config)])

    def wait_stopped(self):
        for _ in range(30):
            status = self.manager("status")
            if status.get("scheduler_state") not in ("Running", "Queued"):
                return
            time.sleep(1)
        raise SetupError("Receiver did not stop; runtime files were left unchanged.")

    def wait_ready(self, started_at):
        for _ in range(60):
            status = self.manager("status")
            health = status.get("health") or {}
            if status.get("receiver_state") == "ready" and health.get("updated_at", 0) >= started_at:
                return
            if status.get("receiver_state") == "failed":
                break
            time.sleep(1)
        raise SetupError("Updated receiver did not become healthy.")

    def deploy(self, candidate):
        self.deployment_marker.write_text("Runtime replacement in progress.", encoding="utf-8")
        self.runtime.mkdir(parents=True, exist_ok=True)
        for name in FILES:
            pending = self.runtime / ("." + name + ".pending")
            shutil.copy2(candidate / name, pending)
            os.replace(pending, self.runtime / name)
        self.deployment_marker.unlink()

    def restore(self, backup, previous):
        self.deployment_marker.write_text("Runtime rollback in progress.", encoding="utf-8")
        for name in FILES:
            target = self.runtime / name
            if name in previous:
                shutil.copy2(backup / name, target)
            else:
                target.unlink(missing_ok=True)
        self.deployment_marker.unlink()

    def install(self, action):
        recovered = self.recover()
        if not self.config.is_file():
            raise SetupError("Private Telegram config is missing. Run install to configure it privately, "
                             "or configure notify-via-telegram at %LOCALAPPDATA%/codex/telegram-notify/config.json. "
                             "Never put bot tokens in commands or chat.")
        if action == "update" and not (self.runtime / "server.py").is_file():
            raise SetupError("No stable runtime exists. Use install for initial setup.")
        for name in FILES:
            if not (self.bundle / name).is_file():
                raise SetupError("Plugin runtime bundle is incomplete; reinstall the plugin package.")
        if (self.bundle / "requirements.txt").read_text().strip() != "mcp==2.2.0":
            raise SetupError("Unsupported dependency change; a separate environment migration is required.")
        self.root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="candidate-", dir=self.root) as staging:
            candidate = Path(staging)
            for name in FILES:
                shutil.copy2(self.bundle / name, candidate / name)
            self.environment(candidate)
            self.validate(candidate)
            before = self.manager("status")
            running = before.get("scheduler_state") in ("Running", "Queued")
            previous = {name for name in FILES if (self.runtime / name).is_file()}
            backup = self.root / ("backup-" + uuid.uuid4().hex)
            backup.mkdir()
            for name in previous:
                shutil.copy2(self.runtime / name, backup / name)
            self.checkpoint(backup, previous, before)
            mutated = False
            try:
                if before.get("installed"):
                    self.manager("stop")
                    self.wait_stopped()
                mutated = True
                self.deploy(candidate)
                self.manager("install")
                if not self.pause.exists():
                    started_at = time.time()
                    self.manager("start")
                    self.wait_ready(started_at)
            except Exception as original:
                if not mutated:
                    raise SetupError("Receiver stop failed before runtime replacement; backup retained at " + str(backup)) from original
                try:
                    self.manager("stop")
                    self.wait_stopped()
                    if not before.get("installed"):
                        self.manager("uninstall")
                    self.restore(backup, previous)
                    if running and not self.pause.exists():
                        started_at = time.time()
                        self.manager("start")
                        self.wait_ready(started_at)
                    self.journal.unlink()
                except Exception:
                    raise SetupError("Update failed and automatic rollback needs attention. "
                                     "Runtime backup retained at " + str(backup)) from None
                raise SetupError("Setup failed; prior runtime and receiver state restored. "
                                 "Backup retained at " + str(backup)) from original
            self.journal.unlink()
            return {"state": "paused" if self.pause.exists() else "ready",
                    "recovered_interrupted_setup": recovered,
                    "backup": str(backup), "data_preserved": True}

    def execute(self, action):
        if action == "status":
            return self.manager("status")
        if action == "uninstall":
            self.root.mkdir(parents=True, exist_ok=True)
            self.pause.write_text("Receiver paused by explicit uninstall.", encoding="utf-8")
            return self.manager("uninstall")
        return self.install(action)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "update", "status", "uninstall"))
    parser.add_argument("--bundle", required=True, type=Path)
    args = parser.parse_args()
    root = Path(os.environ["LOCALAPPDATA"]) / "codex/telegram-task-bridge"
    config = Path(os.environ["LOCALAPPDATA"]) / "codex/telegram-notify/config.json"
    try:
        print(json.dumps(Installer(root, args.bundle, config).execute(args.action)))
    except (SetupError, OSError) as error:
        print(str(error) if isinstance(error, SetupError) else "Filesystem setup failed; check permissions and retry.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
