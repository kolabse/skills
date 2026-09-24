"""Question delivery through fake MCP and Telegram; no network or live state."""
from contextlib import nullcontext
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import server
from store import Store
from telegram import Telegram, TelegramError


class ServerClientTests(unittest.TestCase):
    def run_update_scenario(self, scenario, *, send_error=False):
        """Exercise registered tools, real adapter filtering, and durable state."""
        with tempfile.TemporaryDirectory() as folder:
            registered_tools = {}
            stores = []
            calls = []

            class FakeTelegram(Telegram):
                def __init__(self, config):
                    self.chat_id = 123

                def preflight(self):
                    return 456

                def call(self, method, **payload):
                    calls.append((method, payload))
                    if send_error:
                        raise TelegramError("Simulated uncertain delivery")
                    return {"message_id": len(calls)}

            adapter = FakeTelegram(None)

            class FakeMCP:
                def __init__(self, *args, **kwargs):
                    pass

                def tool(self):
                    def register(function):
                        registered_tools[function.__name__] = function
                        return function
                    return register

                def run(self):
                    scenario(registered_tools, stores[0], adapter, calls)

            def open_store(path):
                store = Store(path)
                stores.append(store)
                return store

            argv = ["server.py", "serve", "--db", str(Path(folder) / "state.sqlite3"),
                    "--config", str(Path(folder) / "unused-config.json")]
            try:
                with patch.object(sys, "argv", argv), \
                        patch.dict(sys.modules, {"mcp.server": types.SimpleNamespace(MCPServer=FakeMCP)}), \
                        patch.object(server, "Telegram", return_value=adapter), \
                        patch.object(server, "Store", side_effect=open_store), \
                        patch.object(server, "bind_bot_database"), \
                        patch.object(server, "bind_database"), \
                        patch.object(server, "receiver_lock", return_value=nullcontext()):
                    server.main()
            finally:
                for store in stores:
                    store.close()

    @staticmethod
    def reply(adapter, store, update_id, message_id=1, text="Continue with option B"):
        return adapter.receive(store, {
            "update_id": update_id,
            "message": {"chat": {"id": 123, "type": "private"},
                        "from": {"id": 123}, "text": text,
                        "reply_to_message": {"message_id": message_id}},
        })

    def test_update_reply_is_optional_task_scoped_and_consumed_once(self):
        def scenario(tools, store, adapter, calls):
            task = tools["register_task"]("Build")
            other = tools["register_task"]("Other")
            with patch("store.time.time", return_value=1000):
                update = tools["send_update"](**task, text="Build passed")
                self.assertEqual(update["expires_at"], 4600)
                self.assertEqual(update["status"], "sent")
                self.assertEqual(update["mode"], "telegram")
                self.assertEqual(tools["poll_replies"](**task), [])
                payload = calls[0][1]
                self.assertNotIn("reply_markup", payload)
                self.assertIn("[Codex: Build]", payload["text"])
                for phrase in ("Build passed", "один ответ через Reply", "3600 сек.",
                               "контрольных точках", "автоматического пробуждения нет"):
                    self.assertIn(phrase, payload["text"])
                question_id = update["question_id"]
                self.assertEqual(self.reply(adapter, store, 1)["status"], "answered")
                self.assertEqual(self.reply(adapter, store, 1)["status"], "duplicate")
                self.assertEqual(self.reply(adapter, store, 2)["status"], "already_answered")
                self.assertEqual(store.offset(), 3)
                replies = tools["poll_replies"](**task)
                self.assertEqual(len(replies), 1)
                self.assertEqual(replies[0]["answer"], "Continue with option B")
                self.assertEqual(replies[0]["question_id"], question_id)
                self.assertEqual(tools["poll_replies"](**task), replies)
                self.assertEqual(tools["poll_replies"](**other), [])
                for tool in ("question_status", "acknowledge_reply"):
                    with self.assertRaises(ValueError):
                        tools[tool](**other, question_id=question_id)
                with self.assertRaises(PermissionError):
                    tools["send_update"](task["task_id"], other["secret"], "Forbidden")
                self.assertEqual(len(calls), 1)
                self.assertEqual(tools["acknowledge_reply"](**task, question_id=question_id),
                                 {"status": "acknowledged", "executed": False})
                self.assertEqual(tools["poll_replies"](**task), [])
                self.assertEqual(self.reply(adapter, store, 3)["status"], "already_answered")
        self.run_update_scenario(scenario)

    def test_update_expiry_rejects_late_reply(self):
        def scenario(tools, store, adapter, calls):
            task = tools["register_task"]("Build")
            with patch("store.time.time", return_value=1000):
                update = tools["send_update"](**task, text="Build passed", ttl_seconds=10)
            with patch("store.time.time", return_value=1010):
                self.assertEqual(self.reply(adapter, store, 1)["status"], "expired")
                self.assertEqual(tools["poll_replies"](**task), [])
                self.assertEqual(tools["question_status"](
                    **task, question_id=update["question_id"])["status"], "expired")
        self.run_update_scenario(scenario)

    def test_update_uncertain_send_is_not_retried_or_correlated(self):
        def scenario(tools, store, adapter, calls):
            task = tools["register_task"]("Build")
            update = tools["send_update"](**task, text="Build passed")
            self.assertEqual(update["status"], "unknown")
            self.assertEqual(len(calls), 1)
            self.assertEqual(tools["question_status"](
                **task, question_id=update["question_id"])["status"], "unknown")
            self.assertEqual(self.reply(adapter, store, 1)["status"], "unknown")
            self.assertEqual(tools["poll_replies"](**task), [])
        self.run_update_scenario(scenario, send_error=True)

    def test_question_and_instruction_slot_use_process_client_identity(self):
        for agent, display in ((None, "Codex"), ("codex", "Codex"),
                               ("claude-code", "Claude Code")):
            with self.subTest(agent=agent), tempfile.TemporaryDirectory() as folder:
                messages = []
                stores = []
                registered_tools = {}

                class FakeTelegram:
                    chat_id = 123

                    def __init__(self, config):
                        pass

                    def preflight(self):
                        return 456

                    def send(self, text):
                        messages.append(text)
                        return len(messages)

                class FakeMCP:
                    def __init__(self, *args, **kwargs):
                        pass

                    def tool(self):
                        def register(function):
                            registered_tools[function.__name__] = function
                            return function
                        return register

                    def run(self):
                        task = registered_tools["register_task"]("Example task")
                        for tool, arguments in (("ask_question", {"text": "Pick an option?"}),
                                                ("open_instruction_slot", {})):
                            result = registered_tools[tool](**task, **arguments)
                            self_test.assertEqual(result["status"], "sent")
                            self_test.assertEqual(result["mode"], "telegram")

                def open_store(path):
                    store = Store(path)
                    stores.append(store)
                    return store

                self_test = self
                argv = ["server.py", "serve", "--db", str(Path(folder) / "state.sqlite3"),
                        "--config", str(Path(folder) / "fake-config.json")]
                if agent is not None:
                    argv += ["--agent", agent]
                try:
                    with patch.object(sys, "argv", argv), \
                            patch.dict(sys.modules, {"mcp.server": types.SimpleNamespace(MCPServer=FakeMCP)}), \
                            patch.object(server, "Telegram", FakeTelegram), \
                            patch.object(server, "Store", side_effect=open_store), \
                            patch.object(server, "bind_bot_database"), \
                            patch.object(server, "bind_database"), \
                            patch.object(server, "receiver_lock", return_value=nullcontext()):
                        server.main()
                    self.assertEqual(len(messages), 2)
                    for message in messages:
                        self.assertTrue(message.startswith(f"[{display}: Example task]\n"), message)
                        self.assertTrue(message.endswith(
                            f"Ответьте на это сообщение. Ответ не заменяет разрешения {display}."), message)
                    self.assertIn("Pick an option?", messages[0])
                    self.assertIn("Следующее указание для этой задачи?", messages[1])
                finally:
                    for store in stores:
                        store.close()


if __name__ == "__main__":
    unittest.main()
