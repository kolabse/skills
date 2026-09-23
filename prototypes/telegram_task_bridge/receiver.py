"""Durable receiver loop; retry only read requests after temporary errors."""
import json
import os
from pathlib import Path
import tempfile
import time

from telegram import TelegramError, bind_bot_database, bind_database, receiver_lock


class Health:
    def __init__(self, path):
        self.path = Path(path)
        self.last_poll_at = None

    def write(self, state, failures=0, error=None, retry_in=0):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"state": state, "pid": os.getpid(), "updated_at": time.time(),
                   "last_poll_at": self.last_poll_at, "consecutive_failures": failures,
                   "last_error": error, "retry_in_seconds": retry_in}
        fd, name = tempfile.mkstemp(prefix=".health-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(payload, stream)
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)


def read_with_retry(action, health, sleep=time.sleep):
    failures = 0
    while True:
        try:
            return action()
        except TelegramError as error:
            if not error.retryable:
                raise
            failures += 1
            delay = max(min(2 ** min(failures, 6), 60), error.retry_after or 0)
            health.write("retrying", failures, str(error), delay)
            # Keep a heartbeat even during a long Telegram retry_after period.
            remaining = delay
            while remaining > 0:
                step = min(remaining, 30)
                sleep(step)
                remaining -= step
                health.write("retrying", failures, str(error), remaining)


def run_receiver(telegram, store, database, health_path, sleep=time.sleep):
    canonical = os.path.normcase(str(Path(database).resolve()))
    # A duplicate receiver must not overwrite the healthy instance's heartbeat.
    with receiver_lock("lifecycle:" + canonical):
        health = Health(health_path)
        pause_path = Path(database).parent / "receiver-paused"
        if pause_path.exists():
            health.write("paused")
            return
        health.write("starting")
        try:
            bot_id = read_with_retry(telegram.preflight, health, sleep)
            bind_bot_database(bot_id, database)
            bind_database(database, f"{bot_id}:{telegram.chat_id}")
            with receiver_lock(bot_id):
                while True:
                    if pause_path.exists():
                        health.write("paused")
                        return
                    updates = read_with_retry(lambda: telegram.call(
                        "getUpdates", offset=store.offset(), timeout=25,
                        allowed_updates=["message"]), health, sleep)
                    for update in updates:
                        with receiver_lock("delivery:" + canonical.casefold(), wait_seconds=40):
                            telegram.receive(store, update)
                    health.last_poll_at = time.time()
                    health.write("ready")
        except KeyboardInterrupt:
            health.write("stopped")
        except TelegramError as error:
            health.write("failed", error=str(error))
            raise
        except Exception:
            health.write("failed", error="Receiver state or processing failure")
            raise
