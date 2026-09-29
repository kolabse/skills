"""Private, atomic progress receipt; intentionally not a replay/resume journal."""
import json
import os
from pathlib import Path
import tempfile
import time


class RunReport:
    PHASES = {"preflight", "initializing", "starting_thread", "starting_turn",
              "running", "sending_question", "waiting_reply", "dispatching_reply",
              "reply_dispatched", "reply_acknowledged", "turn_completed",
              "sending_result", "completed"}

    def __init__(self, path):
        self.path = Path(path)
        self.data = {"schema_version": 1, "status": "running", "phase": "preflight",
                     "updated_at": time.time(), "reply_dispatched": False,
                     "turn_completed": False, "result_sent": False}
        # Exclusive reservation precedes any network or model operation.
        with self.path.open("x", encoding="utf-8") as stream:
            self._write(stream, self.data)

    @staticmethod
    def _write(stream, data):
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())

    def _save(self, data):
        fd, name = tempfile.mkstemp(prefix=".owned-task-", suffix=".json", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                self._write(stream, data)
            os.replace(name, self.path)
            self.data = data
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def phase(self, phase):
        if phase not in self.PHASES or self.data["status"] != "running":
            raise ValueError("Invalid report transition")
        data = dict(self.data, phase=phase, updated_at=time.time())
        if phase == "reply_dispatched":
            data["reply_dispatched"] = True
        if phase == "turn_completed":
            data["turn_completed"] = True
        if phase == "completed":
            data.update(status="completed", result_sent=True)
        self._save(data)

    def stop(self, interrupted=False):
        # Keep the last phase: dispatch/send outcomes may be unknown.
        if self.data["status"] == "running":
            self._save(dict(self.data, status="interrupted" if interrupted else "failed",
                            updated_at=time.time()))
