"""Private-chat Telegram adapter. No credentials or message bodies in logs."""
import contextlib
import hashlib
import http.client
import json
import os
from pathlib import Path
import sqlite3
import time
import urllib.error
import urllib.request


class TelegramError(RuntimeError):
    def __init__(self, message, *, retryable=False, retry_after=None):
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = retry_after


def state_dir():
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local/share"))
    return base / "codex" / "telegram-task-bridge"


class Telegram:
    def __init__(self, config):
        data = json.loads(Path(config).read_text(encoding="utf-8"))
        self.token = data["bot_token"]
        self.chat_id = int(data["chat_id"])
        if self.chat_id <= 0 or data.get("message_thread_id"):
            raise TelegramError("Prototype supports a personal private chat only")

    def call(self, method, **payload):
        request = urllib.request.Request(
            f"https://api.telegram.org/bot{self.token}/{method}",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=35) as response:
                result = json.load(response)
        except urllib.error.HTTPError as error:
            retry_after = None
            if error.code == 429:
                try:
                    retry_after = int(json.load(error).get("parameters", {}).get("retry_after", 60))
                except (ValueError, TypeError, AttributeError):
                    retry_after = 60
            raise TelegramError(f"Telegram {method}: HTTP {error.code}",
                                retryable=error.code == 429 or 500 <= error.code < 600,
                                retry_after=retry_after) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError, http.client.IncompleteRead):
            raise TelegramError(f"Telegram {method}: transport failure", retryable=True) from None
        except (ValueError, TypeError):
            raise TelegramError(f"Telegram {method}: invalid response") from None
        if not result.get("ok"):
            raise TelegramError(f"Telegram {method}: API failure")
        return result["result"]

    def preflight(self):
        if self.call("getWebhookInfo").get("url"):
            raise TelegramError("Existing webhook: refusing polling; webhook left unchanged")
        chat = self.call("getChat", chat_id=self.chat_id)
        if chat.get("type") != "private" or chat.get("id") != self.chat_id:
            raise TelegramError("Destination is not the configured private chat")
        return self.call("getMe")["id"]

    def send(self, text, *, force_reply=True):
        payload = {"chat_id": self.chat_id, "text": text}
        if force_reply:
            payload["reply_markup"] = {"force_reply": True, "selective": True}
        result = self.call("sendMessage", **payload)
        return result["message_id"]

    def receive(self, store, update):
        message = update.get("message", {})
        # A private chat id identifies its sole human sender. Ignore forwards,
        # edits, channels, callbacks, groups, and messages without an exact reply.
        allowed = (message.get("chat", {}).get("id") == self.chat_id
                   and message.get("chat", {}).get("type") == "private"
                   and message.get("from", {}).get("id") == self.chat_id
                   and not message.get("from", {}).get("is_bot", False)
                   and not message.get("forward_origin"))
        if allowed and isinstance(message.get("text"), str):
            reply_id = message.get("reply_to_message", {}).get("message_id")
            if isinstance(reply_id, int):
                result = store.receive(update["update_id"], reply_id, message["text"])
                store.advance_offset(update["update_id"])
                return result
        store.advance_offset(update["update_id"])
        return {"status": "ignored"}


def bind_database(path, identity):
    """Prevent reusing message ids/offsets across bots or destinations."""
    with contextlib.closing(sqlite3.connect(path)) as db, db:
        db.execute("CREATE TABLE IF NOT EXISTS bridge_identity (id INTEGER PRIMARY KEY CHECK(id=1), identity TEXT)")
        db.execute("INSERT OR IGNORE INTO bridge_identity VALUES (1, ?)", (identity,))
        if db.execute("SELECT identity FROM bridge_identity").fetchone()[0] != identity:
            raise TelegramError("Database belongs to another bot/chat or offline mode")


def bind_bot_database(bot_id, path):
    """A bot has one global update stream: all local processes must share its DB."""
    root = state_dir()
    root.mkdir(parents=True, exist_ok=True)
    binding = root / (hashlib.sha256(str(bot_id).encode()).hexdigest() + ".database.json")
    canonical = os.path.normcase(str(Path(path).resolve()))
    with receiver_lock(f"binding:{bot_id}", wait_seconds=5):
        if binding.exists():
            if json.loads(binding.read_text(encoding="utf-8")) != canonical:
                raise TelegramError("This bot is already bound to a different local database")
        else:
            binding.write_text(json.dumps(canonical), encoding="utf-8")


@contextlib.contextmanager
def receiver_lock(bot_id, wait_seconds=0):
    root = state_dir()
    root.mkdir(parents=True, exist_ok=True)
    path = root / (hashlib.sha256(str(bot_id).encode()).hexdigest() + ".lock")
    with path.open("a+b") as handle:
        handle.seek(0)
        handle.write(b"0")
        handle.flush()
        handle.seek(0)
        deadline = time.monotonic() + wait_seconds
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TelegramError("Prototype resource is already locked") from None
                time.sleep(0.05)
        try:
            yield
        finally:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)
