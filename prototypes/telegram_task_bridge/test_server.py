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


class ServerClientTests(unittest.TestCase):
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
