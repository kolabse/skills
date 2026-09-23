"""Offline MCP stdio integration; does not test Telegram or Codex Desktop.

Run with the Python interpreter that has requirements.txt installed:
    python -m unittest discover -s prototypes/telegram_task_bridge -p test_protocol.py -v
"""

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from store import Store


class OfflineProtocolTest(unittest.IsolatedAsyncioTestCase):
    async def call(self, client, name, **arguments):
        result = await client.call_tool(name, arguments)
        self.assertFalse(result.is_error, f"{name} failed: {result.content}")
        value = result.structured_content
        if value is None:
            # A bare dict annotation uses JSON text content in SDK 2.2.
            parsed = [json.loads(block.text) for block in result.content]
            if name == "poll_replies":
                return parsed
            self.assertEqual(len(parsed), 1)
            return parsed[0]
        # SDK 2.2 wraps non-object return types, including list[dict].
        return value["result"] if isinstance(value, dict) and set(value) == {"result"} else value

    async def denied(self, client, name, **arguments):
        result = await client.call_tool(name, arguments)
        self.assertTrue(result.is_error, f"{name} accepted unauthorized access")

    async def test_two_stdio_servers_share_state_but_isolate_task_credentials(self):
        expected_tools = {
            "register_task", "ask_question", "open_instruction_slot",
            "poll_replies", "question_status", "acknowledge_reply",
        }
        with tempfile.TemporaryDirectory(prefix="bridge-offline-protocol-") as directory:
            database = Path(directory) / "state.sqlite3"
            def parameters(agent):
                return StdioServerParameters(
                    command=sys.executable,
                    args=[str(Path(__file__).with_name("server.py").resolve()),
                          "serve", "--offline", "--db", str(database), "--agent", agent],
                    cwd=str(Path(__file__).resolve().parent),
                )
            # Each Client starts its own actual server subprocess and MCP session.
            async with Client(parameters("codex"), read_timeout_seconds=15) as first:
                async with Client(parameters("claude-code"), read_timeout_seconds=15) as second:
                    for client in (first, second):
                        listed = await client.list_tools()
                        self.assertEqual({tool.name for tool in listed.tools}, expected_tools)

                    task_a = await self.call(first, "register_task", label="offline task A")
                    task_b = await self.call(second, "register_task", label="offline task B")
                    self.assertNotEqual(task_a["task_id"], task_b["task_id"])
                    self.assertNotEqual(task_a["secret"], task_b["secret"])
                    question_a = await self.call(first, "ask_question", **task_a,
                                                 text="Which option for task A?")
                    question_b = await self.call(second, "open_instruction_slot", **task_b)
                    for question in (question_a, question_b):
                        self.assertEqual(question["mode"], "offline")
                        self.assertEqual(question["status"], "sent")
                    q_a, q_b = question_a["question_id"], question_b["question_id"]

                    # Only simulated inbound delivery bypasses MCP. Read stored IDs
                    # because public question_status intentionally hides transport IDs.
                    with closing(sqlite3.connect(database)) as connection:
                        rows = dict(connection.execute(
                            "SELECT question_id,message_id FROM questions"))
                    self.assertEqual(set(rows), {q_a, q_b})
                    self.assertNotEqual(rows[q_a], rows[q_b])
                    for message_id in rows.values():
                        self.assertIsInstance(message_id, int)
                        self.assertGreaterEqual(message_id, 0)
                    for client, task in ((first, task_a), (second, task_b)):
                        self.assertEqual(await self.call(client, "poll_replies", **task), [])

                    with closing(Store(database)) as receiver:
                        self.assertEqual(receiver.receive(101, rows[q_b], "B instruction")["status"],
                                         "answered")
                        self.assertEqual(await self.call(first, "poll_replies", **task_a), [])
                        self.assertEqual(receiver.receive(102, rows[q_a], "A answer")["status"],
                                         "answered")
                        self.assertEqual(receiver.receive(102, rows[q_a], "duplicate")["status"],
                                         "duplicate")

                    # Sessions are interchangeable; authorization comes from the
                    # task credentials, not which process registered that task.
                    for client, task, question_id, answer in (
                        (second, task_a, q_a, "A answer"),
                        (first, task_b, q_b, "B instruction"),
                    ):
                        replies = await self.call(client, "poll_replies", **task)
                        self.assertEqual(len(replies), 1)
                        self.assertEqual(replies[0]["question_id"], question_id)
                        self.assertEqual(replies[0]["answer"], answer)
                        self.assertEqual(await self.call(client, "poll_replies", **task), replies)
                        status = await self.call(client, "question_status", **task,
                                                 question_id=question_id)
                        self.assertEqual(status["status"], "answered")

                    mixed = {"task_id": task_a["task_id"], "secret": task_b["secret"]}
                    await self.denied(second, "poll_replies", **mixed)
                    await self.denied(second, "ask_question", **mixed, text="unauthorized")
                    await self.denied(second, "open_instruction_slot", **mixed)
                    for tool in ("question_status", "acknowledge_reply"):
                        await self.denied(second, tool, **mixed, question_id=q_a)
                        await self.denied(second, tool, **task_b, question_id=q_a)

                    ack = await self.call(second, "acknowledge_reply", **task_a, question_id=q_a)
                    self.assertEqual(ack, {"status": "acknowledged", "executed": False})
                    self.assertEqual(await self.call(first, "poll_replies", **task_a), [])
                    self.assertEqual(len(await self.call(second, "poll_replies", **task_b)), 1)
                    self.assertEqual((await self.call(first, "question_status", **task_a,
                                                     question_id=q_a))["status"], "acknowledged")
                    await self.call(first, "acknowledge_reply", **task_a, question_id=q_a)
                    await self.call(first, "acknowledge_reply", **task_b, question_id=q_b)
                    self.assertEqual(await self.call(second, "poll_replies", **task_b), [])


if __name__ == "__main__":
    unittest.main()
