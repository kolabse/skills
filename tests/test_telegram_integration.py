from __future__ import annotations

import importlib.util
import json
import os
import threading
import tempfile
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "skills/notify-via-telegram/scripts/telegram_notify.py"
SPEC = importlib.util.spec_from_file_location("telegram_notify_integration", SCRIPT)
assert SPEC and SPEC.loader
telegram = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(telegram)


class TelegramHandler(BaseHTTPRequestHandler):
    calls: list[tuple[str, dict[str, list[str]]]] = []

    def do_POST(self) -> None:  # noqa: N802 - stdlib callback name
        length = int(self.headers.get("Content-Length", "0"))
        payload = urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8"))
        self.__class__.calls.append((self.path, payload))
        method = self.path.rsplit("/", 1)[-1]
        result: object = {"id": 7, "username": "fixture_bot"} if method == "getMe" else {"message_id": 1}
        body = json.dumps({"ok": True, "result": result}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


class TelegramIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        TelegramHandler.calls = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), TelegramHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def test_configure_and_send_use_real_http_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.json"
            endpoint = f"http://127.0.0.1:{self.server.server_port}"
            environment = {"TELEGRAM_BOT_TOKEN": "123456:fixture-token"}
            with patch.dict(os.environ, environment, clear=False), patch.object(
                telegram, "API_ROOT", endpoint
            ):
                configured = telegram.main([
                    "--config", str(config), "configure", "--chat-id", "-1001"
                ])
                sent = telegram.main([
                    "--config", str(config), "send", "integration message"
                ])
            self.assertEqual(0, configured)
            self.assertEqual(0, sent)
            stored = json.loads(config.read_text(encoding="utf-8"))
            self.assertEqual(1, stored["version"])
            self.assertEqual("-1001", stored["chat_id"])
            methods = [path.rsplit("/", 1)[-1] for path, _ in TelegramHandler.calls]
            self.assertEqual(["getMe", "sendMessage", "sendMessage"], methods)
            self.assertEqual(
                "integration message",
                TelegramHandler.calls[-1][1]["text"][0],
            )

    def test_project_delivery_mode_routes_to_one_or_both_destinations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            config = root / "config.json"
            endpoint = f"http://127.0.0.1:{self.server.server_port}"
            environment = {"TELEGRAM_BOT_TOKEN": "123456:fixture-token"}
            with patch.dict(os.environ, environment, clear=False), patch.object(
                telegram, "API_ROOT", endpoint
            ):
                self.assertEqual(
                    0,
                    telegram.main(
                        [
                            "--config",
                            str(config),
                            "configure",
                            "--chat-id",
                            "100",
                            "--skip-test",
                        ]
                    ),
                )
                self.assertEqual(
                    0,
                    telegram.main(
                        [
                            "--config",
                            str(config),
                            "project-configure",
                            "--project-path",
                            str(project),
                            "--delivery-mode",
                            "project-only",
                            "--chat-id",
                            "-200",
                            "--skip-test",
                        ]
                    ),
                )
                TelegramHandler.calls = []
                self.assertEqual(
                    0,
                    telegram.main(
                        [
                            "--config",
                            str(config),
                            "send",
                            "project only",
                            "--project-path",
                            str(project),
                        ]
                    ),
                )
                project_only = [
                    payload["chat_id"][0]
                    for path, payload in TelegramHandler.calls
                    if path.endswith("/sendMessage")
                ]
                self.assertEqual(["-200"], project_only)

                self.assertEqual(
                    0,
                    telegram.main(
                        [
                            "--config",
                            str(config),
                            "project-configure",
                            "--project-path",
                            str(project),
                            "--delivery-mode",
                            "global-and-project",
                            "--skip-test",
                        ]
                    ),
                )
                TelegramHandler.calls = []
                self.assertEqual(
                    0,
                    telegram.main(
                        [
                            "--config",
                            str(config),
                            "send",
                            "both destinations",
                            "--project-path",
                            str(project),
                        ]
                    ),
                )
                both = [
                    payload["chat_id"][0]
                    for path, payload in TelegramHandler.calls
                    if path.endswith("/sendMessage")
                ]
                self.assertEqual(["100", "-200"], both)

            profile_path = telegram.project_config_path(config, project)
            stored = json.loads(profile_path.read_text(encoding="utf-8"))
            self.assertNotIn("bot_token", stored)


if __name__ == "__main__":
    unittest.main()
