from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


API_ROOT = "https://api.telegram.org"
MAX_MESSAGE_LENGTH = 4096
CONFIG_ENV = "TELEGRAM_NOTIFY_CONFIG"
TOKEN_ENV = "TELEGRAM_BOT_TOKEN"
CHAT_ENV = "TELEGRAM_CHAT_ID"
THREAD_ENV = "TELEGRAM_MESSAGE_THREAD_ID"
TOKEN_PATTERN = re.compile(r"^[0-9]+:[A-Za-z0-9_-]+$", re.ASCII)


class TelegramError(RuntimeError):
    pass


def normalize_bot_token(value: str) -> str:
    token = value.strip()
    if not token:
        raise TelegramError("Telegram bot token is empty")
    if not token.isascii() or TOKEN_PATTERN.fullmatch(token) is None:
        raise TelegramError(
            "Telegram bot token has an invalid format; copy the complete token "
            "from BotFather"
        )
    return token


def prompt_bot_token() -> str:
    while True:
        try:
            value = getpass.getpass("Telegram bot token (input hidden): ")
        except (EOFError, KeyboardInterrupt) as error:
            raise TelegramError("Telegram bot token entry was cancelled") from error
        try:
            return normalize_bot_token(value)
        except TelegramError as error:
            print(f"ERROR: {error}", file=sys.stderr)


def default_config_path(environ: dict[str, str] | None = None) -> Path:
    env = os.environ if environ is None else environ
    if env.get(CONFIG_ENV):
        return Path(env[CONFIG_ENV]).expanduser()
    if os.name == "nt" and env.get("LOCALAPPDATA"):
        return Path(env["LOCALAPPDATA"]) / "codex" / "telegram-notify" / "config.json"
    base = Path(env.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "codex" / "telegram-notify" / "config.json"


def load_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as error:
        raise TelegramError(f"Cannot read configuration at {path}: {error}") from error
    if not isinstance(value, dict):
        raise TelegramError(f"Configuration at {path} must contain a JSON object")
    version = value.get("version", 0)
    if version not in {0, 1}:
        raise TelegramError(f"Unsupported configuration version {version!r} at {path}")
    result: dict[str, Any] = {}
    if version:
        result["version"] = version
    for key in ("bot_token", "chat_id", "message_thread_id"):
        if value.get(key) is not None:
            result[key] = str(value[key])
    return result


def save_config(path: Path, config: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    handle, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=".telegram-notify-", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(config, stream, indent=2, ensure_ascii=False, sort_keys=True)
            stream.write("\n")
        try:
            temporary.chmod(0o600)
        except OSError:
            pass
        os.replace(temporary, path)
        try:
            path.chmod(0o600)
        except OSError:
            pass
    finally:
        if temporary.exists():
            temporary.unlink()


def api_call(
    token: str, method: str, payload: dict[str, str] | None = None
) -> Any:
    token = normalize_bot_token(token)
    try:
        url = f"{API_ROOT}/bot{token}/{method}"
        data = urllib.parse.urlencode(payload or {}).encode("utf-8")
        request = urllib.request.Request(url, data=data, method="POST")
    except (UnicodeError, ValueError) as error:
        raise TelegramError(f"Telegram {method} request could not be constructed") from error
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        try:
            body = error.read().decode("utf-8")
            detail = json.loads(body).get("description", f"HTTP {error.code}")
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            detail = f"HTTP {error.code}"
        raise TelegramError(f"Telegram {method} failed: {detail}") from error
    except urllib.error.URLError as error:
        raise TelegramError(f"Telegram {method} failed: {error.reason}") from error
    except UnicodeDecodeError as error:
        raise TelegramError(f"Telegram {method} returned a non-UTF-8 response") from error
    try:
        result = json.loads(body)
    except json.JSONDecodeError as error:
        raise TelegramError(f"Telegram {method} returned invalid JSON") from error
    if not result.get("ok"):
        raise TelegramError(
            f"Telegram {method} failed: {result.get('description', 'unknown error')}"
        )
    return result.get("result")


def chunk_text(text: str, limit: int = MAX_MESSAGE_LENGTH) -> list[str]:
    if not text or not text.strip():
        raise TelegramError("Message is empty")
    if limit < 1:
        raise ValueError("limit must be positive")
    chunks: list[str] = []
    remaining = text.strip()
    while len(remaining) > limit:
        boundary = remaining.rfind("\n", 0, limit + 1)
        if boundary < limit // 2:
            boundary = remaining.rfind(" ", 0, limit + 1)
        if boundary < limit // 2:
            boundary = limit
        chunks.append(remaining[:boundary].rstrip())
        remaining = remaining[boundary:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks


def chat_label(chat: dict[str, Any]) -> str:
    title = chat.get("title")
    if title:
        return str(title)
    name = " ".join(
        str(value) for value in (chat.get("first_name"), chat.get("last_name")) if value
    )
    if name:
        return name
    if chat.get("username"):
        return f"@{chat['username']}"
    return "unnamed chat"


def extract_chat_candidates(updates: list[dict[str, Any]]) -> list[dict[str, str]]:
    candidates: dict[tuple[str, str], dict[str, str]] = {}
    message_fields = (
        "message",
        "edited_message",
        "channel_post",
        "edited_channel_post",
        "my_chat_member",
        "chat_member",
        "chat_join_request",
    )
    for update in updates:
        for field in message_fields:
            event = update.get(field)
            if not isinstance(event, dict) or not isinstance(event.get("chat"), dict):
                continue
            chat = event["chat"]
            chat_id = str(chat.get("id", ""))
            if not chat_id:
                continue
            thread_id = str(event.get("message_thread_id", ""))
            key = (chat_id, thread_id)
            candidates[key] = {
                "chat_id": chat_id,
                "thread_id": thread_id,
                "type": str(chat.get("type", "unknown")),
                "label": chat_label(chat),
            }
    return list(candidates.values())


def resolve_credentials(
    config: dict[str, Any], environ: dict[str, str] | None = None
) -> tuple[str, str, str]:
    env = os.environ if environ is None else environ
    return (
        env.get(TOKEN_ENV, config.get("bot_token", "")),
        env.get(CHAT_ENV, config.get("chat_id", "")),
        env.get(THREAD_ENV, config.get("message_thread_id", "")),
    )


def discover_chats(token: str) -> list[dict[str, str]]:
    updates = api_call(token, "getUpdates", {"limit": "100", "timeout": "0"})
    if not isinstance(updates, list):
        raise TelegramError("Telegram getUpdates returned an unexpected result")
    return extract_chat_candidates(updates)


def print_candidates(candidates: list[dict[str, str]]) -> None:
    for index, candidate in enumerate(candidates, start=1):
        thread = (
            f", topic {candidate['thread_id']}" if candidate.get("thread_id") else ""
        )
        print(
            f"{index}. {candidate['label']} "
            f"({candidate['type']}, chat {candidate['chat_id']}{thread})"
        )


def select_candidate(candidates: list[dict[str, str]]) -> dict[str, str]:
    if not candidates:
        raise TelegramError(
            "No recent chats found. Send /start to the bot or a command addressed "
            "to it in the target group, then run configure again."
        )
    print_candidates(candidates)
    if len(candidates) == 1:
        return candidates[0]
    while True:
        answer = input(f"Select destination [1-{len(candidates)}]: ").strip()
        if answer.isdigit() and 1 <= int(answer) <= len(candidates):
            return candidates[int(answer) - 1]
        print("Enter one of the listed numbers.")


def send_message(
    token: str,
    chat_id: str,
    text: str,
    thread_id: str = "",
    silent: bool = False,
) -> int:
    if not chat_id:
        raise TelegramError("Chat ID is not configured")
    count = 0
    for chunk in chunk_text(text):
        payload = {"chat_id": chat_id, "text": chunk}
        if thread_id:
            payload["message_thread_id"] = thread_id
        if silent:
            payload["disable_notification"] = "true"
        api_call(token, "sendMessage", payload)
        count += 1
    return count


def command_configure(args: argparse.Namespace, path: Path) -> None:
    config = load_config(path)
    token, existing_chat, existing_thread = resolve_credentials(config)
    if not token:
        token = prompt_bot_token()
    else:
        token = normalize_bot_token(token)
    identity = api_call(token, "getMe")
    if not isinstance(identity, dict):
        raise TelegramError("Telegram getMe returned an unexpected result")

    chat_id = args.chat_id or existing_chat
    thread_id = args.thread_id or existing_thread
    if not chat_id:
        input(
            "Send /start to the bot or a command to it in the target group, then "
            "press Enter..."
        )
        selected = select_candidate(discover_chats(token))
        chat_id = selected["chat_id"]
        thread_id = args.thread_id or selected.get("thread_id", "")

    stored: dict[str, Any] = {"version": 1, "bot_token": token, "chat_id": str(chat_id)}
    if thread_id:
        stored["message_thread_id"] = str(thread_id)
    save_config(path, stored)
    username = identity.get("username", "unknown")
    print(f"Configured @{username} for chat {chat_id}.")
    print(f"Configuration saved to {path}.")
    if not args.skip_test:
        send_message(
            token,
            str(chat_id),
            "✅ Telegram notifications configured.",
            str(thread_id),
        )
        print("Test notification sent.")


def command_discover(path: Path) -> None:
    token, _, _ = resolve_credentials(load_config(path))
    if not token:
        token = prompt_bot_token()
    else:
        token = normalize_bot_token(token)
    candidates = discover_chats(token)
    if not candidates:
        raise TelegramError(
            "No recent chats found. Send /start to the bot or a command addressed "
            "to it in the target group."
        )
    print_candidates(candidates)


def command_status(args: argparse.Namespace, path: Path) -> bool:
    config = load_config(path)
    token, chat_id, thread_id = resolve_credentials(config)
    if token:
        token = normalize_bot_token(token)
    state = {
        "skill": "notify-via-telegram",
        "scope": "user",
        "configured": bool(token and chat_id),
        "valid": True,
        "version": config.get("version", 0),
        "config_file": str(path),
        "bot_token": "configured" if token else "missing",
        "chat_id": chat_id if chat_id else "missing",
        "thread_id": thread_id if thread_id else "not configured",
    }
    if args.verify:
        if not token or not chat_id:
            raise TelegramError("Bot token and chat ID are required for verification")
        identity = api_call(token, "getMe")
        username = identity.get("username", "unknown") if isinstance(identity, dict) else "unknown"
        state["verified_bot"] = f"@{username}"
    if args.json:
        print(json.dumps(state, ensure_ascii=False, sort_keys=True))
    else:
        print(f"Config: {path}")
        print(f"Bot token: {state['bot_token']}")
        print(f"Chat ID: {state['chat_id']}")
        print(f"Thread ID: {state['thread_id']}")
        if state.get("verified_bot"):
            print(f"Verified bot: {state['verified_bot']}")
    return bool(state["configured"])


def command_migrate(path: Path, as_json: bool) -> None:
    config = load_config(path)
    previous = path.read_bytes() if path.is_file() else None
    if not config.get("bot_token") or not config.get("chat_id"):
        raise TelegramError("Bot token and chat ID are required before migration")
    config["bot_token"] = normalize_bot_token(str(config["bot_token"]))
    config["version"] = 1
    save_config(path, config)
    state = {
        "skill": "notify-via-telegram",
        "version": 1,
        "changed": previous != path.read_bytes(),
        "config_file": str(path),
    }
    print(json.dumps(state, sort_keys=True) if as_json else f"Configuration is version 1: {path}")


def command_send(args: argparse.Namespace, path: Path) -> None:
    token, chat_id, configured_thread = resolve_credentials(load_config(path))
    if args.stdin:
        if args.message:
            raise TelegramError("Provide a message argument or --stdin, not both")
        message = sys.stdin.read()
    else:
        message = args.message or ""
    count = send_message(
        token,
        chat_id,
        message,
        args.thread_id or configured_thread,
        args.silent,
    )
    print(f"Sent {count} message{'s' if count != 1 else ''}.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Configure and send Telegram notifications for long-running tasks."
    )
    parser.add_argument("--config", type=Path, help="Override the local config path")
    subparsers = parser.add_subparsers(dest="command", required=True)

    configure = subparsers.add_parser("configure", help="Configure bot and destination")
    configure.add_argument("--chat-id", help="Use a known destination chat ID")
    configure.add_argument("--thread-id", help="Use a Telegram forum topic ID")
    configure.add_argument(
        "--skip-test", action="store_true", help="Do not send a test notification"
    )

    subparsers.add_parser("discover", help="List chats from recent bot updates")

    status = subparsers.add_parser("status", help="Show configuration presence")
    status.add_argument("--verify", action="store_true", help="Verify the bot token")
    status.add_argument("--json", action="store_true", help="Print machine-readable status")

    migrate = subparsers.add_parser("migrate", help="Migrate local configuration")
    migrate.add_argument("--json", action="store_true", help="Print machine-readable result")

    send = subparsers.add_parser("send", help="Send a plain-text notification")
    send.add_argument("message", nargs="?", help="Notification text")
    send.add_argument("--stdin", action="store_true", help="Read notification from stdin")
    send.add_argument("--thread-id", help="Override the configured topic ID")
    send.add_argument("--silent", action="store_true", help="Send without an alert")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path = args.config.expanduser() if args.config else default_config_path()
    try:
        if args.command == "configure":
            command_configure(args, path)
        elif args.command == "discover":
            command_discover(path)
        elif args.command == "status":
            if not command_status(args, path):
                return 1
        elif args.command == "migrate":
            command_migrate(path, args.json)
        elif args.command == "send":
            command_send(args, path)
    except (TelegramError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
