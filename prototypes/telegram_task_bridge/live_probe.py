"""Explicit two-client live probe. `send` sends two messages to configured self-chat."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

from mcp import Client
from mcp.client.stdio import StdioServerParameters


def value(result):
    if result.is_error:
        raise RuntimeError("MCP tool failed; inspect local server status")
    if result.structured_content is not None:
        data = result.structured_content
        return data.get("result", data) if isinstance(data, dict) else data
    return json.loads(result.content[0].text)


async def run(args):
    params = StdioServerParameters(command=sys.executable, args=[
        str(Path(__file__).with_name("server.py")), "serve", "--db", args.db,
        "--config", args.config])
    state_path = Path(args.state)
    if args.action == "send":
        # Exclusive file creation prevents accidental retry and duplicate sends.
        with state_path.open("x", encoding="utf-8") as stream:
            json.dump([], stream)
        os.chmod(state_path, 0o600)
        state = []
        for label, word in [("Prototype A", "АЛЬФА"), ("Prototype B", "БЕТА")]:
            async with Client(params) as client:
                task = value(await client.call_tool("register_task", {"label": label}))
                entry = {"label": label, "task": task}
                state.append(entry)
                state_path.write_text(json.dumps(state), encoding="utf-8")
                question = value(await client.call_tool("ask_question", {
                    **task, "text": f"Тест связи. Ответьте словом {word} через Ответ/Reply именно на это сообщение.",
                    "ttl_seconds": 86400}))
                entry["question_id"] = question["question_id"]
                state_path.write_text(json.dumps(state), encoding="utf-8")
                print(json.dumps({"task": label, "status": question["status"]}))
    else:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        for entry in state:
            async with Client(params) as client:
                result = value(await client.call_tool("question_status", {
                    **entry["task"], "question_id": entry["question_id"]}))
                expected = "АЛЬФА" if entry["label"] == "Prototype A" else "БЕТА"
                print(json.dumps({"task": entry["label"], "status": result["status"],
                                  "expected_reply_received": result.get("answer") == expected}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["send", "poll"])
    for field in ["db", "config", "state"]:
        parser.add_argument("--" + field, required=True)
    asyncio.run(run(parser.parse_args()))
