"""Opt-in launcher for one bounded, dedicated task per authenticated registration."""
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from types import SimpleNamespace

from owned_task import TaskError, TelegramChannel
from owned_task_report import RunReport
from telegram import receiver_lock


class OwnedTaskManager:
    SUPPORTED_VERSION = "codex-cli 0.155.0-alpha.16.3"
    SUPPORTED_VERSIONS = {SUPPORTED_VERSION, "codex-cli 0.158.0-alpha.2.1"}
    MAX_DISCOVERY_CANDIDATES = 8
    DISCOVERY_TIMEOUT = 10

    def __init__(self, root: Path, codex: Path | None, database: Path, config: Path):
        self.root = Path(root).resolve()
        self.codex = Path(codex) if codex is not None else None
        self.database = Path(database).resolve()
        self.config = Path(config).resolve()
        self.children = {}

    def _discover_codex(self, options):
        # Only inspect the desktop app's known install directory. Never use PATH.
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data or not Path(local_app_data).is_absolute():
            return "codex_not_found"
        try:
            install = Path(local_app_data) / "OpenAI" / "Codex" / "bin"
            candidates = [(path.stat().st_mtime_ns, str(path), path)
                          for path in install.glob("*/codex.exe") if path.is_file()]
        except OSError:
            return "codex_not_found"
        candidates.sort(key=lambda item: (-item[0], item[1]))
        deadline = time.monotonic() + self.DISCOVERY_TIMEOUT
        error = "codex_not_found"
        for _, _, candidate in candidates[:self.MAX_DISCOVERY_CANDIDATES]:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return "codex_preflight_failed"
            try:
                version = subprocess.run([str(candidate), "--version"],
                                         **dict(options, timeout=remaining))
            except (OSError, subprocess.SubprocessError, UnicodeError):
                error = "codex_preflight_failed"
                continue
            if version.returncode == 0 and version.stdout.strip() in self.SUPPORTED_VERSIONS:
                self.codex = candidate
                return None
            error = "unsupported_codex_version"
        return error

    def preflight(self):
        if self.codex is not None and (not self.codex.is_absolute() or not self.codex.is_file()
                                       or self.codex.suffix.lower() != ".exe"):
            return {"ready": False, "error": "invalid_codex_executable"}
        if not self.database.is_file() or not self.config.is_file():
            return {"ready": False, "error": "missing_receiver_configuration"}
        try:
            TelegramChannel.ready(SimpleNamespace(database=self.database))
        except (TaskError, OSError):
            return {"ready": False, "error": "receiver_not_ready"}
        options = dict(capture_output=True, text=True, timeout=10, shell=False,
                       stdin=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        discovered = self.codex is None
        if discovered:
            error = self._discover_codex(options)
            if error:
                return {"ready": False, "error": error}
        try:
            if not discovered:
                version = subprocess.run([str(self.codex), "--version"], **options)
                if version.returncode != 0 or version.stdout.strip() not in self.SUPPORTED_VERSIONS:
                    return {"ready": False, "error": "unsupported_codex_version"}
            login = subprocess.run([str(self.codex), "login", "status"], **options)
            if login.returncode != 0 or (login.stdout + login.stderr).strip() != "Logged in using ChatGPT":
                return {"ready": False, "error": "chatgpt_login_required"}
        except (OSError, subprocess.SubprocessError, UnicodeError):
            return {"ready": False, "error": "codex_preflight_failed"}
        return {"ready": True}

    def _directory(self, task_id):
        if not isinstance(task_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", task_id):
            raise ValueError("invalid_task_id")
        path = self.root / task_id
        # Reject links/junctions leading outside the private run root.
        if path.resolve().parent != self.root or path.is_symlink():
            raise ValueError("invalid_task_directory")
        return path

    def _lock(self, directory):
        return receiver_lock("owned-task:" + os.path.normcase(str(directory)).casefold(), wait_seconds=30)

    @staticmethod
    def _error():
        return {"status": "error", "execution_state": "unknown", "error": "owned_task_operation_failed"}

    def start(self, task_id):
        try:
            directory = self._directory(task_id)
            with self._lock(directory):
                if (directory / "launch.json").exists():
                    return self._status(task_id, directory)
                ready = self.preflight()
                if not ready["ready"]:
                    return {"status": "blocked", "execution_state": "unknown", "error": ready["error"]}
                directory.mkdir(parents=True, exist_ok=True)
                # Never overwrite this reservation, even after spawn failure or restart.
                with (directory / "launch.json").open("x", encoding="utf-8") as stream:
                    json.dump({"schema_version": 1, "reserved": True}, stream)
                    stream.flush()
                    os.fsync(stream.fileno())
                scratch = directory / "scratch"
                scratch.mkdir(exist_ok=False)
                command = [sys.executable, str(Path(__file__).with_name("owned_task.py")),
                           "--live", "--codex-executable", str(self.codex),
                           "--database", str(self.database), "--config", str(self.config),
                           "--workdir", str(scratch), "--report", str(directory / "result.json"),
                           "--cancel-file", str(directory / "cancel-requested")]
                try:
                    self.children[task_id] = subprocess.Popen(
                        command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL, shell=False,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                except (OSError, subprocess.SubprocessError):
                    return {"status": "failed", "execution_state": "unknown", "error": "spawn_failed"}
                return self._status(task_id, directory)
        except Exception:
            return self._error()

    @staticmethod
    def _read_report(directory):
        try:
            path = directory / "result.json"
            if path.stat().st_size > 16384:
                return None
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("status") not in {"running", "completed", "failed", "interrupted", "cancelled"}:
                return None
            report = {"status": data["status"]}
            if data.get("cancellation_notice") in {"not_needed", "invalidation_failed", "edit_failed", "updated"}:
                report["cancellation_notice"] = data["cancellation_notice"]
            if data.get("phase") in RunReport.PHASES:
                report["phase"] = data["phase"]
            for key in ("reply_dispatched", "turn_completed", "result_sent"):
                if isinstance(data.get(key), bool):
                    report[key] = data[key]
            timestamp = data.get("updated_at")
            if type(timestamp) in (int, float) and math.isfinite(timestamp):
                report["updated_at"] = timestamp
            return report
        except (OSError, ValueError, TypeError):
            return None

    def _status(self, task_id, directory):
        child = self.children.get(task_id)
        execution = "unknown" if child is None else "running" if child.poll() is None else "exited"
        reserved = (directory / "launch.json").exists()
        report = self._read_report(directory) if reserved else None
        status = report["status"] if report else "running" if execution == "running" else "unknown" if reserved else "not_started"
        if status == "running" and execution != "running":
            status = "unknown"
        if status in {"running", "unknown"} and (directory / "cancel-requested").exists():
            status = "cancel_requested"
        result = {"status": status, "execution_state": execution}
        if report:
            result["report"] = report
        return result

    def status(self, task_id):
        try:
            directory = self._directory(task_id)
            with self._lock(directory):
                return self._status(task_id, directory)
        except Exception:
            return self._error()

    def cancel(self, task_id):
        try:
            directory = self._directory(task_id)
            with self._lock(directory):
                status = self._status(task_id, directory)
                if status["status"] in {"completed", "failed", "interrupted", "cancelled", "not_started"}:
                    return status
                (directory / "cancel-requested").touch(exist_ok=True)
                return dict(status, status="cancel_requested")
        except Exception:
            return self._error()
